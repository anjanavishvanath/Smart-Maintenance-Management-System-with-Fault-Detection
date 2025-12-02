// frontend/src/components/DeviceReadingsChart.jsx
import React, { useEffect, useState, useRef } from "react";
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  TimeScale,
  LinearScale,
  LogarithmicScale,
  CategoryScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Title,
  Filler,
} from "chart.js";
import "chartjs-adapter-date-fns";
import { deviceService } from "../services/deviceService";

// register ChartJS components (required)
ChartJS.register(
  TimeScale,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Title,
  Filler
);

/**
 * DeviceReadingsChart (time-domain + spectrum)
 *
 * Props:
 *  - deviceId: string (required)
 *  - limit: number (how many metric points to fetch)
 *  - refreshMs: number (auto-refresh)
 */
export default function DeviceReadingsChart({ deviceId, limit = 200, refreshMs = 5000 }) {
  const [readings, setReadings] = useState([]);           // time-domain metrics list
  const [spectrum, setSpectrum] = useState([]);           // spectrum rows from backend
  const [loading, setLoading] = useState(false);
  const [loadingSpectrum, setLoadingSpectrum] = useState(false);
  const [metricType, setMetricType] = useState("rms");    // rms | peak | mean
  const [spectrumAxis, setSpectrumAxis] = useState("magnitude"); // ax/ay/az/magnitude
  const intervalRef = useRef(null);
  const spectrumIntervalRef = useRef(null);

  // fetch metrics (time domain)
  useEffect(() => {
    let mounted = true;
    async function fetchMetrics() {
      if (!deviceId) return;
      setLoading(true);
      try {
        const res = await deviceService.getReadings(deviceId, limit);
        const rows = res.readings || [];
        if (!mounted) return;

        const cleaned = rows
          .map(r => {
            let m = r.metrics || {};
            if (typeof m === "string") {
              try { m = JSON.parse(m); } catch (e) { m = {}; }
            }
            return { time: r.time, metrics: m };
          })
          .filter(r => r.time);

        setReadings(cleaned.reverse());
      } catch (err) {
        console.error("DeviceReadingsChart: failed to fetch readings", err);
      } finally {
        if (mounted) setLoading(false);
      }
    }

    fetchMetrics();
    if (refreshMs > 0) intervalRef.current = setInterval(fetchMetrics, refreshMs);
    return () => { mounted = false; if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [deviceId, limit, refreshMs]);

  // fetch spectrum (for selected axis)
  useEffect(() => {
    let mounted = true;
    async function fetchSpec() {
      if (!deviceId) return;
      setLoadingSpectrum(true);
      try {
        // fetch last 12 spectrum records by default
        const res = await deviceService.getSpectrum(deviceId, { axis: spectrumAxis, limit: 12 });
        if (!mounted) return;
        setSpectrum(res.spectrum || []);
      } catch (err) {
        console.error("DeviceReadingsChart: failed to fetch spectrum", err);
        setSpectrum([]);
      } finally {
        if (mounted) setLoadingSpectrum(false);
      }
    }
    fetchSpec();
    // periodically refresh spectrum (slower)
    spectrumIntervalRef.current = setInterval(fetchSpec, Math.max(10000, refreshMs * 2));
    return () => { mounted = false; if (spectrumIntervalRef.current) clearInterval(spectrumIntervalRef.current); };
  }, [deviceId, spectrumAxis, refreshMs]);

  // helper to read metric value
  const getValue = (metrics, axis, type) => {
    if (!metrics) return null;
    const key = `${axis}_${type}_g`; // same as backend naming
    const val = metrics[key];
    return (val !== undefined && val !== null) ? Number(val) : null;
  };

  // ----------------- Time-domain chart (top) -----------------
  const times = readings.map(r => new Date(r.time).getTime());
  const datasetTime = (axis, color) => ({
    label: `${axis} (${metricType})`,
    data: readings.map((r, i) => {
      const val = getValue(r.metrics, axis, metricType);
      return { x: times[i], y: (val === null || Number.isNaN(val)) ? null : val };
    }),
    tension: 0.15,
    fill: false,
    borderWidth: 2,
    pointRadius: 0,
    borderColor: color,
    spanGaps: false,
  });
  const timeData = {
    datasets: [
      datasetTime("ax", "rgb(255, 99, 132)"),
      datasetTime("ay", "rgb(54, 162, 235)"),
      datasetTime("az", "rgb(75, 192, 192)")
    ]
  };
  const timeOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { position: "top" },
      title: { display: true, text: `Device ${deviceId} — Vibration (${metricType.toUpperCase()})` }
    },
    scales: {
      x: {
        type: "time",
        time: {
          unit: "second",
          tooltipFormat: "yyyy-MM-dd HH:mm:ss",
          displayFormats: { second: "HH:mm:ss", minute: "HH:mm", hour: "HH:mm" }
        },
        title: { display: true, text: "Time (UTC)" }
      },
      y: { title: { display: true, text: "Acceleration (g)" } }
    }
  };

  // ----------------- Spectrum chart (bottom) -----------------
  // Build a spectrum plot using the most recent spectrum row (if present).
  // Backend returns rows ordered newest->oldest; pick first available with freqs+amps.
  const latestSpectrumRow = spectrum && spectrum.length > 0 ? spectrum[0] : null;

  // freq/amp arrays
  const freqs = (latestSpectrumRow && latestSpectrumRow.freqs) ? latestSpectrumRow.freqs : [];
  const amps = (latestSpectrumRow && latestSpectrumRow.amps) ? latestSpectrumRow.amps : [];

  // Limit bins to reasonable number for plotting (e.g., 1..N)
  const maxBins = 512;
  const binCount = Math.min(freqs.length, amps.length, maxBins);
  const freqDataPoints = [];
  for (let i = 0; i < binCount; i++) {
    freqDataPoints.push({ x: freqs[i], y: amps[i] });
  }

  const spectrumData = {
    datasets: [
      {
        label: `Spectrum — ${spectrumAxis} (latest)`,
        data: freqDataPoints,
        tension: 0.05,
        fill: false,
        borderWidth: 1.5,
        pointRadius: 0,
        borderColor: "rgb(75, 192, 192)",
      }
    ]
  };

  const spectrumOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: "top" },
      title: { display: true, text: `Frequency Spectrum — axis: ${spectrumAxis}` }
    },
    scales: {
      x: {
        type: "linear",
        title: { display: true, text: "Frequency (Hz)" },
        ticks: { autoSkip: true },
      },
      y: {
        title: { display: true, text: "Amplitude (units from backend)" },
        // let Chart.js auto-scale
      }
    },
    interaction: { mode: "nearest", intersect: false }
  };

  // small UI: top-right controls
  const controlsStyle = { position: "absolute", right: 10, top: 6, zIndex: 5, display: "flex", gap: 8 };

  return (
    <div style={{ width: "100%" }}>
      {/* Controls */}
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
        <div>
          <strong>Device:</strong> {deviceId}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <label style={{ fontSize: 12 }}>Metric</label>
          <select value={metricType} onChange={e => setMetricType(e.target.value)} style={{ padding: 6 }}>
            <option value="rms">RMS</option>
            <option value="peak">Peak</option>
            <option value="mean">Mean</option>
          </select>

          <label style={{ fontSize: 12 }}>Spectrum axis</label>
          <select value={spectrumAxis} onChange={e => setSpectrumAxis(e.target.value)} style={{ padding: 6 }}>
            <option value="magnitude">magnitude</option>
            <option value="ax">ax</option>
            <option value="ay">ay</option>
            <option value="az">az</option>
          </select>
        </div>
      </div>

      {/* Time-domain chart */}
      <div style={{ width: "100%", height: 320, position: "relative", marginBottom: 18 }}>
        {loading && <div style={{ position: "absolute", left: 10, top: 10, zIndex: 10, background: "rgba(255,255,255,0.85)", padding: "6px 8px", borderRadius: 4 }}>Loading...</div>}
        {readings.length === 0 && !loading ? (
          <div style={{ padding: 20 }}>No time-domain metrics available yet.</div>
        ) : (
          <Line data={timeData} options={timeOptions} />
        )}
      </div>

      {/* Spectrum chart */}
      <div style={{ width: "100%", height: 320, position: "relative" }}>
        {loadingSpectrum && <div style={{ position: "absolute", left: 10, top: 10, zIndex: 10, background: "rgba(255,255,255,0.85)", padding: "6px 8px", borderRadius: 4 }}>Loading spectrum...</div>}
        {!latestSpectrumRow && !loadingSpectrum ? (
          <div style={{ padding: 20 }}>No spectrum data available yet for this axis.</div>
        ) : (
          <Line data={spectrumData} options={spectrumOptions} />
        )}
      </div>
    </div>
  );
}
