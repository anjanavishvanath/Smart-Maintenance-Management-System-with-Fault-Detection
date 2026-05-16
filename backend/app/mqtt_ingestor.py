import os
import json
import math
import time
import logging
import paho.mqtt.client as mqtt
from collections import Counter, OrderedDict
from datetime import datetime, timezone, timedelta
from log_config import configure_logging
configure_logging()
logger = logging.getLogger("mqtt_ingestor")
from db import (
    insert_sensor_data,
    insert_sensor_metrics,
    get_asset_baseline,
    insert_sensor_data_bulk,
    get_asset_details,
    update_device_last_seen,
)
from db import get_active_event, create_event, close_event
from processing import calculate_vibration_metrics, band_energy
import numpy as np

# --- CONFIG ---
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt_broker")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_SUB = "presense/#"

SAMPLING_RATE = 200          # 200 Hz (must match ESP32 firmware)
DT_MS = 1000 / SAMPLING_RATE  # 5 ms per sample

# --- Sensor mounting orientation ---
# These name the axis that points along (axial) and perpendicular to (radial)
# the motor shaft, given the current physical mount. Change here if you remount.
# Standard textbook fault signatures: unbalance + parallel misalignment show
# strongest on the RADIAL axis; angular misalignment + thrust on the AXIAL.
AXIAL_AXIS = "x"
RADIAL_AXIS = "y"
# 'z' on the current sensor is at ~45 deg to the shaft, so it mixes axial + radial.
# Kept for total-RMS aggregation but excluded from primary diagnosis.

# --- Anomaly detection thresholds ---
# Mahalanobis D^2 is approximately chi-square distributed with k DoF (k = number
# of features in the baseline). For our 4-feature vector:
#   chi^2(0.95, 4) =  9.488  -> Warning
#   chi^2(0.99, 4) = 13.277  -> Critical
# Tighten/loosen if you see noise-driven false positives.
MAHAL_WARNING = 9.488
MAHAL_CRITICAL = 13.277

# Legacy z-score thresholds (kept for the fallback path used while an asset has
# not yet been re-baselined under the Tier 1 feature set).
Z_CRITICAL = 5.0
Z_WARNING = 3.0
SIGMA_FLOOR = 0.005

# Pre-baseline triage (no baseline of any kind exists yet). Velocity in mm/s
# against ISO 20816 Class II (small machines, < 15 kW).
FALLBACK_VELOCITY_CRITICAL_MMPS = 11.2
FALLBACK_VELOCITY_WARNING_MMPS  = 4.5

# Diagnosis: half-width windows for band-energy probes around the fundamental.
# +/- 10% covers slip and minor speed variation without bleeding into the next
# harmonic for typical RPMs (1500-3600).
BAND_HALFWIDTH_FRAC = 0.10

# --- Cache / buffer bounds ---
# Tumbling windows clear at SAMPLING_RATE. Cap at 5x as a safety net so a stuck
# accumulator can't blow up RAM if the metrics path ever fails to reset it.
ACCUMULATOR_MAX_SIZE = SAMPLING_RATE * 5    # ~5 seconds of samples per axis
SCORE_HISTORY_MAX = 5                       # Last N processed batches per asset
MAX_TRACKED_ASSETS = 1024                   # LRU eviction beyond this many distinct assets
BASELINE_CACHE_TTL_SEC = 5 * 60             # 5 minutes; matches the docstring promise

# --- LRU-style state, bounded by MAX_TRACKED_ASSETS ---
# Format: { asset_id: {'x': [...], 'y': [...], 'z': [...]} }
data_accumulators: "OrderedDict[int, dict]" = OrderedDict()
score_history: "OrderedDict[int, list]" = OrderedDict()
# baseline_cache value is (baseline_dict_or_none, fetched_at_unix_seconds)
baseline_cache: "OrderedDict[int, tuple]" = OrderedDict()


def _lru_touch(d: OrderedDict, key) -> None:
    """Move `key` to the end of the OrderedDict so least-recent entries are evicted first."""
    if key in d:
        d.move_to_end(key)


def _lru_evict(d: OrderedDict, max_size: int) -> None:
    """Drop the oldest entries until len(d) <= max_size."""
    while len(d) > max_size:
        evicted, _ = d.popitem(last=False)
        logger.info("LRU: evicted asset %s from %#x cache (over %d).", evicted, id(d), max_size)


def fetch_cached_baseline(asset_id):
    """Return the cached baseline if fresh, otherwise refresh from the DB.

    Caches entries for BASELINE_CACHE_TTL_SEC seconds. Receiving cmd/clear_cache
    on the broker forcibly evicts a single asset id; the TTL is a fallback that
    ensures a stale cache eventually heals itself even if the broker hint is missed.
    """
    now = time.time()
    cached = baseline_cache.get(asset_id)
    if cached is not None:
        value, fetched_at = cached
        if now - fetched_at < BASELINE_CACHE_TTL_SEC:
            _lru_touch(baseline_cache, asset_id)
            return value
        # Otherwise expired — fall through to refresh.

    logger.info("Refreshing baseline cache for Asset %s", asset_id)
    value = get_asset_baseline(asset_id)
    baseline_cache[asset_id] = (value, now)
    _lru_touch(baseline_cache, asset_id)
    _lru_evict(baseline_cache, MAX_TRACKED_ASSETS)
    return value


def on_connect(client, userdata, flags, rc):
    """Standard Paho v1 callback signature."""
    if rc == 0:
        logger.info("Connected to broker. Subscribing...")
        client.subscribe([(MQTT_TOPIC_SUB, 0), ("cmd/clear_cache", 0)])
    else:
        logger.error("Connection failed with code %s", rc)


def on_disconnect(client, userdata, rc):
    """Log disconnects so we can diagnose broker bounces in the logs.

    Paho's loop_forever() handles reconnect automatically when reconnect_delay_set is
    configured; we just need to surface the fact that it happened.
    """
    if rc == 0:
        logger.info("MQTT disconnected cleanly.")
    else:
        logger.warning("MQTT disconnected unexpectedly (rc=%s). loop_forever will retry with backoff.", rc)


def _axis(metrics_by_axis: dict, name: str) -> dict:
    """Lookup a per-axis metrics dict by axis name ('x', 'y', 'z')."""
    return metrics_by_axis[name]


def diagnose_fault(asset_rpm, metrics_by_axis, score, baseline):
    """Classify the fault type from spectral content in a triggered batch.

    Decision is driven by *band-energy ratios* on the diagnostic axes, not
    argmax-of-FFT — the latter flips on noise and is order-dependent.

    Logic:
      * Unbalance:    RADIAL axis, strong 1x energy relative to broadband.
      * Misalignment: 2x energy comparable to or exceeding 1x energy on the
                      RADIAL axis (parallel misalignment) or AXIAL axis
                      (angular misalignment).
      * Bearing wear: high-frequency band energy (>= 4x fundamental, up to
                      Nyquist) elevated relative to the rest of the spectrum.
    """
    if score == 0:
        return "Healthy"

    b = baseline if baseline else {}
    base_freq = b.get('mean_dom_freq_x') or (asset_rpm / 60.0) if asset_rpm else 0.0
    if not base_freq or base_freq <= 0:
        base_freq = 25.0  # Final fallback for 1500 RPM

    radial = _axis(metrics_by_axis, RADIAL_AXIS)
    axial  = _axis(metrics_by_axis, AXIAL_AXIS)

    # All axes share the same FFT bins (same window length, same sampling rate),
    # so we can pull frequencies once and reuse.
    freqs = np.asarray(radial["frequencies"])
    nyquist = float(freqs[-1])

    half = base_freq * BAND_HALFWIDTH_FRAC

    def _energies(metrics):
        amps = np.asarray(metrics["amplitudes"])
        e_1x = band_energy(amps, freqs, base_freq - half, base_freq + half)
        e_2x = band_energy(amps, freqs, 2 * base_freq - half, 2 * base_freq + half)
        e_high = band_energy(amps, freqs, max(4 * base_freq, 0.0), nyquist)
        e_total = band_energy(amps, freqs, 0.0, nyquist) or 1e-12
        return e_1x, e_2x, e_high, e_total

    er_1x, er_2x, er_high, er_total = _energies(radial)
    ea_1x, ea_2x, ea_high, ea_total = _energies(axial)

    # --- Bearing wear: dominant high-frequency content on either axis ---
    # If >40% of broadband energy sits above 4x the fundamental, that's a
    # textbook bearing/gear-mesh signature.
    if (er_high / er_total) > 0.40 or (ea_high / ea_total) > 0.40:
        return "High-Frequency Anomaly (Potential Bearing Wear)"

    # --- Misalignment: 2x energy comparable to or exceeding 1x ---
    # Threshold of 0.5 is the textbook rule-of-thumb (Goldman et al.); higher
    # ratios than ~0.7 strongly suggest misalignment over unbalance.
    radial_2x_ratio = er_2x / (er_1x + 1e-12)
    axial_2x_ratio  = ea_2x / (ea_1x + 1e-12)
    if radial_2x_ratio > 0.5:
        return "Misalignment Suspected (Strong 2X on Radial Axis)"
    if axial_2x_ratio > 0.5:
        return "Angular Misalignment Suspected (Strong 2X on Axial Axis)"

    # --- Unbalance: 1x dominates the radial spectrum ---
    if (er_1x / er_total) > 0.30:
        return "Unbalance Detected (Strong 1X Peak on Radial Axis)"

    return "Generic Vibration Increase"


def _parse_telemetry_topic(topic: str):
    """Validate and parse a presense telemetry topic.

    Expected layout: presense/{org}/{asset_id}/{mac}[/...]
    Returns (asset_id: int, device_mac: str) on success, or None to signal "skip this message".
    """
    parts = topic.split('/')
    if len(parts) < 4 or parts[0] != "presense":
        logger.warning("Ignoring unexpected topic %r", topic)
        return None

    asset_str = parts[2]
    if not asset_str.isdigit():
        # Default asset_id used to be 0, which silently routed bad data into a phantom asset.
        # Reject instead so the misconfiguration is visible in the logs.
        logger.warning("Non-numeric asset_id in topic %r; skipping", topic)
        return None

    asset_id = int(asset_str)
    if asset_id <= 0:
        logger.warning("Invalid asset_id %s in topic %r; skipping", asset_id, topic)
        return None

    device_mac = parts[3]
    if not device_mac:
        logger.warning("Missing device MAC in topic %r; skipping", topic)
        return None

    return asset_id, device_mac


def _ensure_accumulator(asset_id: int) -> dict:
    """Return the per-asset sample buffer, creating + LRU-touching as needed."""
    buf = data_accumulators.get(asset_id)
    if buf is None:
        buf = {'x': [], 'y': [], 'z': []}
        data_accumulators[asset_id] = buf
        _lru_evict(data_accumulators, MAX_TRACKED_ASSETS)
    _lru_touch(data_accumulators, asset_id)
    return buf


def _trim_accumulator(buf: dict) -> None:
    """Cap each axis to ACCUMULATOR_MAX_SIZE by dropping the oldest samples."""
    for axis in ('x', 'y', 'z'):
        if len(buf[axis]) > ACCUMULATOR_MAX_SIZE:
            overflow = len(buf[axis]) - ACCUMULATOR_MAX_SIZE
            buf[axis] = buf[axis][overflow:]
            logger.warning(
                "Accumulator overflow — dropped %d oldest samples on axis %s.",
                overflow, axis,
            )


def on_message(client, userdata, msg):
    # Cache-clear control channel, runs outside the telemetry parse path.
    if msg.topic == "cmd/clear_cache":
        try:
            target_id = int(msg.payload.decode())
            if target_id in baseline_cache:
                del baseline_cache[target_id]
                logger.info("Cleared baseline cache for Asset %s", target_id)
            else:
                logger.info("Request to clear Asset %s, but not in cache.", target_id)
        except (ValueError, UnicodeDecodeError):
            logger.warning("Invalid payload for clear_cache: %r", msg.payload)
        return

    # --- Telemetry path ---
    parsed_topic = _parse_telemetry_topic(msg.topic)
    if parsed_topic is None:
        return
    asset_id, device_mac = parsed_topic

    # Parse JSON payload defensively. A malformed batch must NOT take down the ingestor.
    try:
        payload = json.loads(msg.payload.decode())
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning("Bad JSON on %s (%s); first 80 bytes: %r", msg.topic, e, msg.payload[:80])
        return

    if "samples" not in payload or not isinstance(payload["samples"], list):
        # Not a telemetry batch we know how to process; just drop it.
        return

    try:
        _process_telemetry(asset_id, device_mac, payload)
    except Exception as e:
        # Don't let one bad message tip over the long-running ingestor.
        logger.exception("Error processing message for asset %s: %s", asset_id, e)


def _process_telemetry(asset_id: int, device_mac: str, payload: dict) -> None:
    arrival_time = datetime.now(timezone.utc)

    buf = _ensure_accumulator(asset_id)
    baseline = fetch_cached_baseline(asset_id)

    raw_samples = payload["samples"]
    bulk_data = []

    for i, s in enumerate(raw_samples):
        ax = float(s.get("ax", 0))
        ay = float(s.get("ay", 0))
        az = float(s.get("az", 0))

        # Reconstruct a per-sample timestamp by assuming uniform 5 ms spacing from
        # the batch arrival time. (Tier 6: send per-sample timestamps from the ESP32.)
        sample_time = arrival_time + timedelta(milliseconds=i * DT_MS)
        bulk_data.append((sample_time, device_mac, asset_id, ax, ay, az))
        buf['x'].append(ax)
        buf['y'].append(ay)
        buf['z'].append(az)

    _trim_accumulator(buf)
    insert_sensor_data_bulk(bulk_data)

    current_buffer_size = len(buf['x'])
    if current_buffer_size < SAMPLING_RATE:
        return  # Not yet enough samples for this tumbling window.

    logger.info(
        "Buffer full (%d samples). Processing metrics for Asset %s...",
        current_buffer_size, asset_id,
    )

    asset_info = get_asset_details(asset_id)
    asset_rpm = asset_info.get('max_rpm', 1500)

    # Snapshot + clear so concurrent batches don't double-count.
    x_vals, y_vals, z_vals = buf['x'], buf['y'], buf['z']
    data_accumulators[asset_id] = {'x': [], 'y': [], 'z': []}

    mx = calculate_vibration_metrics(x_vals, sampling_rate=SAMPLING_RATE)
    my = calculate_vibration_metrics(y_vals, sampling_rate=SAMPLING_RATE)
    mz = calculate_vibration_metrics(z_vals, sampling_rate=SAMPLING_RATE)

    if mx is None or my is None or mz is None:
        logger.error("Error calculating metrics for device %s", device_mac)
        return  # Buffer was already cleared above.

    metrics_by_axis = {"x": mx, "y": my, "z": mz}
    total_rms = math.sqrt(mx['rms']**2 + my['rms']**2 + mz['rms']**2)
    velocity_rms_total = math.sqrt(
        mx['velocity_rms']**2 + my['velocity_rms']**2 + mz['velocity_rms']**2
    )
    crest_factor_total = max(mx['crest_factor'], my['crest_factor'], mz['crest_factor'])

    # New scorer: Mahalanobis when available, falls back to legacy z-score
    # then magnitude triage. anomaly_metric is D^2 for Mahalanobis, max-z for
    # legacy, or 0 for triage. Stored on the metrics row regardless.
    score, anomaly_metric = _score_anomaly(metrics_by_axis, baseline)

    # Update score history (LRU-bounded by MAX_TRACKED_ASSETS).
    history = score_history.get(asset_id)
    if history is None:
        history = []
        score_history[asset_id] = history
        _lru_evict(score_history, MAX_TRACKED_ASSETS)
    _lru_touch(score_history, asset_id)
    history.append(score)
    if len(history) > SCORE_HISTORY_MAX:
        history.pop(0)

    reported_score = Counter(history).most_common(1)[0][0]
    diagnosis = diagnose_fault(asset_rpm, metrics_by_axis, reported_score, baseline)

    # --- Asset event lifecycle ---
    active_event = get_active_event(asset_id)
    if reported_score > 0:
        if not active_event:
            logger.info("Opening new alert for Asset %s (Severity: %s)", asset_id, reported_score)
            create_event(asset_id, reported_score, diagnosis, anomaly_metric)
        elif active_event.severity != reported_score:
            close_event(active_event.id)
            create_event(asset_id, reported_score, diagnosis, anomaly_metric)
    else:
        if active_event:
            logger.info("Resolving alert for Asset %s. Machine is healthy.", asset_id)
            close_event(active_event.id)

    insert_sensor_metrics(
        time=arrival_time,
        asset_id=asset_id,
        rms_x=mx['rms'],
        rms_y=my['rms'],
        rms_z=mz['rms'],
        rms_total=round(total_rms, 4),
        peak_to_peak_z=mz['peak_to_peak'],
        dominant_freq_x=mx['dominant_freq'],
        dominant_freq_y=my['dominant_freq'],
        dominant_freq_z=mz['dominant_freq'],
        condition_score=reported_score,
        diagnosis=diagnosis,
        velocity_rms_x=mx['velocity_rms'],
        velocity_rms_y=my['velocity_rms'],
        velocity_rms_z=mz['velocity_rms'],
        velocity_rms_total=round(velocity_rms_total, 4),
        kurtosis_x=mx['kurtosis'],
        kurtosis_y=my['kurtosis'],
        kurtosis_z=mz['kurtosis'],
        crest_factor_total=round(crest_factor_total, 4),
        mahalanobis_distance=round(anomaly_metric, 4),
    )

    # Heartbeat: stamp last_seen once per processed batch (not per sample) so the
    # dashboard can show online/offline without hammering the DB.
    try:
        update_device_last_seen(device_mac)
    except Exception as e:
        logger.warning("Failed to update last_seen for %s: %s", device_mac, e)

    logger.info("Inserted metrics for asset %s (Score: %s, Freq Res: ~1Hz)", asset_id, reported_score)


def _build_feature_vector(metrics_by_axis: dict) -> np.ndarray:
    """Pack per-batch metrics into the Mahalanobis feature vector.

    Order MUST match db.MAHAL_FEATURE_NAMES:
      [velocity_rms_total, crest_factor_total, kurtosis_max, dom_freq_y]
    """
    mx = metrics_by_axis["x"]
    my = metrics_by_axis["y"]
    mz = metrics_by_axis["z"]
    velocity_rms_total = math.sqrt(
        mx["velocity_rms"] ** 2 + my["velocity_rms"] ** 2 + mz["velocity_rms"] ** 2
    )
    # Crest factor on the resultant magnitude isn't well-defined from per-axis
    # crests; pick the maximum across axes as a conservative impulsiveness summary.
    crest_factor_total = max(mx["crest_factor"], my["crest_factor"], mz["crest_factor"])
    kurtosis_max = max(mx["kurtosis"], my["kurtosis"], mz["kurtosis"])
    dom_freq_radial = metrics_by_axis[RADIAL_AXIS]["dominant_freq"]
    return np.array(
        [velocity_rms_total, crest_factor_total, kurtosis_max, dom_freq_radial],
        dtype=float,
    )


def _score_anomaly(metrics_by_axis: dict, baseline):
    """Return (severity_score, anomaly_metric) for this batch.

    Three scoring paths, in priority order:
      1) MAHALANOBIS (preferred)  — full multivariate distance against a
         baseline that includes mean vector + inverse covariance.
      2) LEGACY Z-SCORE (fallback) — when an asset has the old per-axis
         baseline but no Mahalanobis JSON. ONE-SIDED on RMS now (a quieter
         motor isn't a fault).
      3) MAGNITUDE TRIAGE (last resort) — pre-calibration; uses ISO 20816
         Class II velocity thresholds on broadband velocity RMS.

    The second return value is the anomaly metric used (D^2 for path 1, max
    z-score for path 2, 0 for path 3) — persisted as `mahalanobis_distance`
    for path 1 and `max_z_score` on the event row.
    """
    feature_vec = _build_feature_vector(metrics_by_axis)
    velocity_rms_total = float(feature_vec[0])

    # --- Path 1: Mahalanobis ---
    mahal_baseline = baseline.get("mahalanobis_baseline") if baseline else None
    if mahal_baseline:
        # JSONB columns come back as dicts already; tolerate raw strings too.
        if isinstance(mahal_baseline, str):
            try:
                mahal_baseline = json.loads(mahal_baseline)
            except json.JSONDecodeError:
                mahal_baseline = None

    if mahal_baseline:
        mean = np.asarray(mahal_baseline["mean"], dtype=float)
        cov_inv = np.asarray(mahal_baseline["cov_inv"], dtype=float)
        if mean.shape[0] == feature_vec.shape[0] and cov_inv.shape == (mean.shape[0], mean.shape[0]):
            diff = feature_vec - mean
            d2 = float(diff @ cov_inv @ diff)

            # ONE-SIDED guard on velocity RMS: never flag if the machine is
            # running quieter than baseline. Distance can still be large for
            # frequency / kurtosis drift, but those are real signals worth alerting on.
            quieter = velocity_rms_total < mean[0]
            if quieter and d2 < MAHAL_CRITICAL:
                # Quieter than baseline AND not extreme => suppress.
                return 0, d2

            if d2 > MAHAL_CRITICAL:
                return 2, d2
            if d2 > MAHAL_WARNING:
                return 1, d2
            return 0, d2
        else:
            logger.warning(
                "Mahalanobis baseline shape mismatch (mean=%s, cov_inv=%s, vec=%s) — "
                "feature schema may have changed; falling back to legacy z-score.",
                mean.shape, cov_inv.shape, feature_vec.shape,
            )

    # --- Path 2: Legacy z-score (with one-sided RMS) ---
    if baseline and baseline.get('std_rms_total') and baseline['std_rms_total'] > 0:
        # Use velocity RMS in mm/s if available on the baseline; otherwise the
        # legacy mean_rms_total stored as acceleration RMS in g.
        total_rms_g = math.sqrt(
            metrics_by_axis["x"]["rms"] ** 2
            + metrics_by_axis["y"]["rms"] ** 2
            + metrics_by_axis["z"]["rms"] ** 2
        )
        mu_rms = baseline['mean_rms_total']
        sigma_rms = max(baseline['std_rms_total'], SIGMA_FLOOR)
        # ONE-SIDED: clamp negative deviations to zero. A drop in RMS isn't a fault.
        z_rms = max((total_rms_g - mu_rms) / sigma_rms, 0.0)

        mu_freq = baseline.get('mean_dom_freq_x', 0)
        sigma_freq = max(baseline.get('std_dom_freq_x', 0), SIGMA_FLOOR)
        z_freq = abs(metrics_by_axis["x"]['dominant_freq'] - mu_freq) / sigma_freq

        max_z = max(z_rms, z_freq)
        if max_z > Z_CRITICAL:
            return 2, max_z
        if max_z > Z_WARNING:
            return 1, max_z
        return 0, max_z

    # --- Path 3: Magnitude triage on velocity RMS, ISO 20816 Class II ---
    if velocity_rms_total > FALLBACK_VELOCITY_CRITICAL_MMPS:
        return 2, 0.0
    if velocity_rms_total > FALLBACK_VELOCITY_WARNING_MMPS:
        return 1, 0.0
    return 0, 0.0


# --- INITIALISE (Paho v1.x style) ---
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect

# Exponential backoff on disconnect: start retrying after 1s, cap at 60s between attempts.
client.reconnect_delay_set(min_delay=1, max_delay=60)

logger.info("Attempting connection to %s:%s...", MQTT_BROKER, MQTT_PORT)
client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)

# loop_forever() will automatically reconnect (with the configured backoff) if the
# broker drops the connection, instead of exiting the process.
client.loop_forever(retry_first_connection=True)
