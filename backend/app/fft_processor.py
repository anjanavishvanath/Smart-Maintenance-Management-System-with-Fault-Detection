import numpy as np
from scipy.signal import windows
import math
from typing import Tuple, Dict, List

def bytes_to_interleaved_int16(payload: bytes, samples: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Assumes payload is interleaved int16 ax,ay,az little-endian, length = samples*3*2."""
    arr = np.frombuffer(payload, dtype=np.int16)
    if arr.size % 3 != 0:
        # trim incomplete tail
        arr = arr[: (arr.size // 3) * 3]
    arr = arr.reshape(-1, 3)  # shape (N,3)
    ax = arr[:,0].astype(np.float64)
    ay = arr[:,1].astype(np.float64)
    az = arr[:,2].astype(np.float64)
    return ax, ay, az

def compute_spectrum(signal: np.ndarray, sample_rate: int, window='hann') -> Tuple[List[float], List[float]]:
    """
    Returns (freqs, amps) where amps are RMS amplitude per bin (converted to g if you scale input).
    Use rFFT (real-input).
    """
    N = len(signal)
    if N == 0:
        return [], []
    # apply window
    if window == 'hann':
        win = windows.hann(N, sym=False)
    else:
        win = np.ones(N)

    xw = signal * win
    # rfft
    X = np.fft.rfft(xw)
    # compute amplitude scaling: convert to RMS amplitude per bin
    # scale factor for window & FFT:
    # amplitude_spectrum = (2/N) * |X| for single-sided spectrum (except DC and Nyquist)
    amp = np.abs(X)
    # correction for window coherent gain:
    coh_gain = np.sum(win) / N
    # normalize
    with np.errstate(divide='ignore', invalid='ignore'):
        amps = (2.0 / (N * coh_gain)) * amp
    freqs = np.fft.rfftfreq(N, d=1.0 / sample_rate)
    return freqs.tolist(), amps.tolist()

def dominant_frequency(freqs: List[float], amps: List[float]) -> Tuple[float, float]:
    if not freqs or not amps:
        return 0.0, 0.0
    idx = int(np.argmax(np.array(amps)))
    return float(freqs[idx]), float(amps[idx])

def band_energy(freqs: List[float], amps: List[float], bands: List[Tuple[float,float]]) -> Dict[str,float]:
    """
    bands: list of (low, high) in Hz
    returns dict "low-high": energy (sum of amp^2) or RMS energy
    """
    f = np.array(freqs)
    a = np.array(amps)
    out = {}
    for (lo, hi) in bands:
        mask = (f >= lo) & (f < hi)
        if mask.any():
            # energy = sqrt(sum(a^2)) or sum(a^2) depending on usage
            energy = float(np.sqrt(np.sum(a[mask]**2)))
        else:
            energy = 0.0
        out[f"{int(lo)}-{int(hi)}"] = energy
    return out

def process_raw_payload(payload: bytes, sample_rate: int, samples: int, accel_sens=16384.0):
    """
    High-level processor: convert binary payload -> per-axis freqs/amps, magnitude
    accel_sens: LSB per g (to convert int16 -> g)
    Returns dict of axis -> spectrum info
    """
    ax, ay, az = bytes_to_interleaved_int16(payload, samples)
    # convert to g
    ax_g = ax / accel_sens
    ay_g = ay / accel_sens
    az_g = az / accel_sens
    # compute per-axis
    freqs, ax_amps = compute_spectrum(ax_g, sample_rate)
    _, ay_amps = compute_spectrum(ay_g, sample_rate)
    _, az_amps = compute_spectrum(az_g, sample_rate)
    # magnitude time series and spectrum
    mag_ts = np.sqrt(ax_g**2 + ay_g**2 + az_g**2)
    _, mag_amps = compute_spectrum(mag_ts, sample_rate)

    # bands (example bands: 0-50, 50-200, 200-1000 Hz) — tune to machine
    bands = [(0,50), (50,200), (200,1000)]
    ax_bands = band_energy(freqs, ax_amps, bands)
    ay_bands = band_energy(freqs, ay_amps, bands)
    az_bands = band_energy(freqs, az_amps, bands)
    mag_bands = band_energy(freqs, mag_amps, bands)

    ax_dom = dominant_frequency(freqs, ax_amps)
    ay_dom = dominant_frequency(freqs, ay_amps)
    az_dom = dominant_frequency(freqs, az_amps)
    mag_dom = dominant_frequency(freqs, mag_amps)

    return {
        "freqs": freqs,
        "ax": {"amps": ax_amps, "dominant_freq": ax_dom[0], "dominant_amp": ax_dom[1], "bands": ax_bands},
        "ay": {"amps": ay_amps, "dominant_freq": ay_dom[0], "dominant_amp": ay_dom[1], "bands": ay_bands},
        "az": {"amps": az_amps, "dominant_freq": az_dom[0], "dominant_amp": az_dom[1], "bands": az_bands},
        "magnitude": {"amps": mag_amps, "dominant_freq": mag_dom[0], "dominant_amp": mag_dom[1], "bands": mag_bands},
    }
