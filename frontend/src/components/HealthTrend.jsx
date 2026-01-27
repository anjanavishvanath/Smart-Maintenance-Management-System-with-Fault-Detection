// Line chart for vibration level changes over time

import { Line } from 'react-chartjs-2';

export default function HealthTrend({ history }) {
  if (!history || history.length === 0) return <p>Waiting for trend data...</p>;

  const chartData = {
    labels: history.map(h => new Date(h.time).toLocaleTimeString()),
    datasets: [
      { label: 'RMS X', data: history.map(h => h.rms_x), borderColor: '#ff4b2b' },
      { label: 'RMS Y', data: history.map(h => h.rms_y), borderColor: '#2bafff' },
      { label: 'RMS Z', data: history.map(h => h.rms_z), borderColor: '#2bff80' },
    ],
  };

  return <Line data={chartData} options={{ responsive: true, elements: { point: { radius: 2 } } }} />;
}