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
        // Filter rows that have valid time + numeric ax/ay/az
        const cleaned = rows
          .map(r => ({
            time: r.time, // expecting ISO8601 string (server sends isoformat)
            ax: r.ax !== undefined ? Number(r.ax) : null,
            ay: r.ay !== undefined ? Number(r.ay) : null,
            az: r.az !== undefined ? Number(r.az) : null,
            meta: r.meta || null
          }))
          // drop points with no timestamp
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

  // prepare chart data
  // When building datasets, skip null datapoints (Chart.js accepts null to create gaps).
  const times = readings.map(r => new Date(r.time).getTime()); // epoch ms
  const dataset = (key, label, color) => ({
    label,
    data: readings.map((r, i) => {
      const val = r[key];
      return {
        x: times[i],
        y: val === null || Number.isNaN(val) ? null : val
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
      dataset("ax", "ax (g)", "rgb(255, 99, 132)"),
      dataset("ay", "ay (g)", "rgb(54, 162, 235)"),
      dataset("az", "az (g)", "rgb(75, 192, 192)")
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
        text: `Device ${deviceId} — accelerometer (ax/ay/az)`,
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
        suggestedMin: -2,
        suggestedMax: 2,
      }
    }
  };

  return (
    <div style={{ width: "100%", height: "360px", position: "relative" }}>
      {loading && <div style={{position:"absolute",left:10,top:10,zIndex:10,background:"rgba(255,255,255,0.8)",padding:"6px 8px",borderRadius:4}}>Loading...</div>}
      {readings.length === 0 && !loading ? (
        <div style={{ padding: 20 }}>No readings available yet for this device.</div>
      ) : (
        <Line data={chartData} options={options} />
      )}
    </div>
  );
}
