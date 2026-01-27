import numpy as np
from scipy.fft import rfft, rfftfreq

def calculate_vibration_metrics(samples, sampling_rate=100):
    """
    Analyzes a batch of samples.
    sampling_rate: How many samples per second the ESP32 is sending (Hz).
    """
    data = np.array(samples)
    n = len(data)

    if n < 2: # Need at least 2 samples for peak-to-peak
        return None
    
    # Remove DC component
    ac_component = data - np.mean(data)

    # Time Domain: RMS (Root Mean Square)
    # This represents the total energy/intensity of the vibration.
    rms = np.sqrt(np.mean(ac_component**2))

    # Time Domain: Peak-to-Peak
    peak_to_peak = np.ptp(ac_component)

    # Frequency Domain: FFT
    # rfft is optimized for real-valued sensor data
    yf = rfft(ac_component)
    xf = rfftfreq(n, 1 / sampling_rate)
    
    # Get the magnitude of the frequencies
    amplitudes = np.abs(yf)
    
    # Find the dominant frequency (where amplitude is highest)
    dominant_freq = xf[np.argmax(amplitudes[1:])+1] if len(amplitudes) > 0 else 0

    return {
        "rms": round(float(rms), 4),
        "peak_to_peak": round(float(peak_to_peak), 4),
        "dominant_freq": round(float(dominant_freq), 2),
        "frequencies": xf.tolist(),      # X-axis for your chart (Hz)
        "amplitudes": amplitudes.tolist() # Y-axis for your chart
    }