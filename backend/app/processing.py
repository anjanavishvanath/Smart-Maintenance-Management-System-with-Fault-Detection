"""Per-batch vibration feature extraction.

Inputs are tri-axial acceleration samples in g (matching the ESP32 firmware
output). Each public function returns metric values in physically meaningful
units (m/s² internally; mm/s for velocity RMS so the result is comparable to
ISO 10816/20816 severity charts).

Tier 1 upgrade (May 2026):
  * Velocity RMS in the 10 Hz - Nyquist band (was: broadband acceleration RMS).
  * Kurtosis and crest factor added — both spike for impulsive faults
    (bearings, gear teeth) before broadband RMS does.
  * Band-energy helper to support the rewritten diagnose_fault layer.
  * sampling_rate is now a required argument (was: misleading default of 100).
"""

import numpy as np
from scipy.fft import rfft, rfftfreq

# Acceleration unit conversion. Firmware streams in g; ISO velocity RMS is mm/s.
_G_TO_MPS2 = 9.80665
_MPS_TO_MMPS = 1000.0

# Lower bound for the velocity band. Everything below this is dominated by
# integration drift and rigid-body motion, not machine condition. Matches the
# 10 Hz floor in ISO 10816-3 / 20816 for general industrial machinery.
_VELOCITY_BAND_LOW_HZ = 10.0


def _band_rms_from_one_sided_spectrum(amps_one_sided, freqs, f_low, f_high, n_samples):
    """RMS of a band-limited signal computed from its one-sided amplitude spectrum.

    Uses Parseval's theorem with the standard one-sided correction (interior
    bins count twice; DC and the Nyquist bin count once when n_samples is even).
    """
    in_band = (freqs >= f_low) & (freqs <= f_high)
    a = amps_one_sided * in_band
    n = n_samples
    if n_samples % 2 == 0 and len(a) > 1:
        # Even-length transforms include a unique Nyquist bin at the end.
        sum_sq = a[0] ** 2 + a[-1] ** 2 + 2.0 * np.sum(a[1:-1] ** 2)
    else:
        sum_sq = a[0] ** 2 + 2.0 * np.sum(a[1:] ** 2)
    return float(np.sqrt(sum_sq) / n)


def _velocity_rms_mmps(accel_amps_g, freqs, n_samples, f_low=_VELOCITY_BAND_LOW_HZ, f_high=None):
    """Convert an acceleration FFT (in g) to a velocity FFT (in m/s) and band-RMS it.

    V(f) = A(f) / (2 pi f). Bins below f_low are zeroed to prevent the 1/f term
    from amplifying the low-frequency drift that always sits near DC.
    """
    if f_high is None:
        f_high = float(freqs[-1])
    accel_amps_mps2 = accel_amps_g * _G_TO_MPS2
    velocity_amps = np.zeros_like(accel_amps_mps2, dtype=float)
    nonzero = freqs > 0
    velocity_amps[nonzero] = accel_amps_mps2[nonzero] / (2.0 * np.pi * freqs[nonzero])
    rms_mps = _band_rms_from_one_sided_spectrum(velocity_amps, freqs, f_low, f_high, n_samples)
    return rms_mps * _MPS_TO_MMPS


def band_energy(amplitudes, freqs, f_low, f_high):
    """Sum of squared amplitudes in [f_low, f_high]. Unitless 'energy' proxy.

    Used by the diagnosis layer to compute ratios like E(2x) / E(1x). The
    absolute value is meaningless on its own; only ratios and z-scores matter.
    """
    in_band = (freqs >= f_low) & (freqs <= f_high)
    return float(np.sum((amplitudes * in_band) ** 2))


def _kurtosis(x):
    """Excess kurtosis (Fisher definition: Gaussian -> 0).

    Sensitive to occasional large samples — exactly what bearing-defect impacts
    look like in raw acceleration before RMS smears them out.
    """
    x = np.asarray(x, dtype=float)
    centred = x - np.mean(x)
    var = np.mean(centred ** 2)
    if var <= 0:
        return 0.0
    return float(np.mean(centred ** 4) / (var ** 2) - 3.0)


def _crest_factor(x):
    """Peak amplitude / RMS amplitude, AC-coupled. Dimensionless.

    A pure sine wave has crest = sqrt(2) ~ 1.41. Crest above ~3-4 indicates
    impulsive content (bearing wear, gear-mesh damage, looseness).
    """
    x = np.asarray(x, dtype=float)
    centred = x - np.mean(x)
    rms = np.sqrt(np.mean(centred ** 2))
    if rms <= 0:
        return 0.0
    return float(np.max(np.abs(centred)) / rms)


def calculate_vibration_metrics(samples, sampling_rate):
    """Compute features for a single tumbling-window batch on one axis.

    Args:
        samples: iterable of acceleration values in g.
        sampling_rate: samples-per-second of the input. REQUIRED — must match
            the producer (firmware) rate, otherwise frequency-domain values
            are off by a constant factor.

    Returns a dict, or None if the batch is too short to characterise.
    """
    data = np.array(samples, dtype=float)
    n = len(data)
    if n < 2:
        return None

    ac = data - np.mean(data)
    rms_g = float(np.sqrt(np.mean(ac ** 2)))
    peak_to_peak = float(np.ptp(ac))

    yf = rfft(ac)
    xf = rfftfreq(n, 1.0 / sampling_rate)
    amplitudes = np.abs(yf)

    # Dominant frequency: skip DC bin to avoid the trivial answer.
    if len(amplitudes) > 1:
        dominant_freq = float(xf[1 + int(np.argmax(amplitudes[1:]))])
    else:
        dominant_freq = 0.0

    # Velocity RMS in mm/s, ISO band (10 Hz - Nyquist). With 200 Hz sampling
    # Nyquist is 100 Hz, so we cover the 10-100 Hz portion of ISO 10816's
    # 10-1000 Hz band — sufficient for rotating equipment up to ~6000 RPM.
    velocity_rms_mmps = _velocity_rms_mmps(amplitudes, xf, n)

    return {
        "rms": round(rms_g, 4),                               # acceleration RMS in g (legacy/diagnostic)
        "velocity_rms": round(velocity_rms_mmps, 4),          # mm/s, ISO-aligned severity
        "peak_to_peak": round(peak_to_peak, 4),
        "dominant_freq": round(dominant_freq, 2),
        "kurtosis": round(_kurtosis(data), 4),                # impulsiveness
        "crest_factor": round(_crest_factor(data), 4),        # impulsiveness
        "frequencies": xf.tolist(),
        "amplitudes": amplitudes.tolist(),
    }
