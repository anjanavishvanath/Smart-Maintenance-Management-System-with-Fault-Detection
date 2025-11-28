// DeviceReadingsChart.jsx
import React, { useEffect, useState, useRef } from "react";
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  TimeScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Title,
  Filler,
  CategoryScale,
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
 * DeviceReadingsChart
 *
 * Props:
 *  - deviceId: string (required) — the device to show
 *  - limit: number (optional) — number of recent readings to fetch (default 200)
 *  - refreshMs: number (optional) — auto-refresh interval in ms (default 5000)
 *
 * Expects API to return rows with { time: ISO-string, ax, ay, az }
 */
export default function DeviceReadingsChart({ deviceId, limit = 200, refreshMs = 5000 }) {
  const [readings, setReadings] = useState([]);
  const [loading, setLoading] = useState(false);
  const [metricType, setMetricType] = useState("rms"); // rms, peak, mean
  const intervalRef = useRef(null);

  // fetch once and schedule refresh
  useEffect(() => {
    let mounted = true;
    async function fetchData() {
      if (!deviceId) return;
      setLoading(true);
      try {
        const res = await deviceService.getReadings(deviceId, limit);
        // deviceService returns { device_id, count, readings }
        const rows = res.readings || [];
        if (!mounted) return;

        // Parse rows. The backend returns `metrics` as a JSON object (or stringified JSON).
        // We expect keys like: ax_rms_g, ay_rms_g, az_rms_g, ax_peak_g, ...
        const cleaned = rows
          .map(r => {
            let m = r.metrics || {};
            if (typeof m === 'string') {
              try { m = JSON.parse(m); } catch (e) { }
            }
            return {
              time: r.time,
              metrics: m
            };
          })
          .filter(r => r.time);

        setReadings(cleaned.reverse()); // reverse so earliest->latest order for chart
      } catch (err) {
        console.error("DeviceReadingsChart: failed to fetch readings", err);
      } finally {
        if (mounted) setLoading(false);
      }
    }

    fetchData();
    // schedule periodic refresh
    if (refreshMs > 0) {
      intervalRef.current = setInterval(fetchData, refreshMs);
    }
    return () => {
      mounted = false;
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [deviceId, limit, refreshMs]);

  // Helper to extract value based on metric type
  const getValue = (metrics, axis, type) => {
    if (!metrics) return null;
    // key pattern: ax_rms_g, ay_peak_g, etc.
    const key = `${axis}_${type}_g`;
    const val = metrics[key];
    return (val !== undefined && val !== null) ? Number(val) : null;
  };

  // prepare chart data
  const times = readings.map(r => new Date(r.time).getTime());

  const dataset = (axis, color) => ({
    label: `${axis} (${metricType})`,
    data: readings.map((r, i) => {
      const val = getValue(r.metrics, axis, metricType);
      return {
        x: times[i],
        y: val
      };
    }),
    tension: 0.15,
    fill: false,
    borderWidth: 2,
    pointRadius: 0,
    borderColor: color,
    spanGaps: false,
  });

  const chartData = {
    datasets: [
      dataset("ax", "rgb(255, 99, 132)"),
      dataset("ay", "rgb(54, 162, 235)"),
      dataset("az", "rgb(75, 192, 192)")
    ]
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: "index",
      intersect: false,
    },
    stacked: false,
    plugins: {
      legend: {
        position: "top",
      },
      title: {
        display: true,
        text: `Device ${deviceId} — Vibration (${metricType.toUpperCase()})`,
      }
    },
    scales: {
      x: {
        type: "time",
        time: {
          unit: "second",
          tooltipFormat: "yyyy-MM-dd HH:mm:ss",
          displayFormats: {
            second: "HH:mm:ss",
            minute: "HH:mm",
            hour: "HH:mm"
          }
        },
        title: {
          display: true,
          text: "Time (UTC)"
        }
      },
      y: {
        title: {
          display: true,
          text: "Acceleration (g)"
        },
        // Remove hardcoded min/max to allow auto-scaling for different metrics
        // suggestedMin: -2, 
        // suggestedMax: 2,
      }
    }
  };

  return (
    <div style={{ width: "100%", height: "360px", position: "relative" }}>
      <div style={{ position: "absolute", right: 10, top: 0, zIndex: 5 }}>
        <select
          value={metricType}
          onChange={e => setMetricType(e.target.value)}
          style={{ padding: "4px 8px", borderRadius: "4px", border: "1px solid #ccc" }}
        >
          <option value="rms">RMS</option>
          <option value="peak">Peak</option>
          <option value="mean">Mean</option>
        </select>
      </div>

      {loading && <div style={{ position: "absolute", left: 10, top: 10, zIndex: 10, background: "rgba(255,255,255,0.8)", padding: "6px 8px", borderRadius: 4 }}>Loading...</div>}
      {readings.length === 0 && !loading ? (
        <div style={{ padding: 20 }}>No readings available yet for this device.</div>
      ) : (
        <Line data={chartData} options={options} />
      )}
    </div>
  );
}
