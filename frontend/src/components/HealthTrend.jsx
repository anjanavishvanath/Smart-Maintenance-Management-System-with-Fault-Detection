import { Line } from 'react-chartjs-2';

export default function HealthTrend({ history, baseline }) {
  if (!history || history.length === 0) {
    return <p style={{ color: '#888', textAlign: 'center' }}>Waiting for trend data...</p>;
  }

  const chartData = {
    labels: history.map(h => new Date(h.time).toLocaleTimeString()),
    datasets: [
      {
        label: 'Total RMS (Resultant)',
        data: history.map(h => h.rms_total),
        borderColor: '#f39c12', // Gold/Orange - Main focus
        borderWidth: 3,
        pointRadius: 3,
        fill: false,
        tension: 0.1,
      },
      {
        label: 'Baseline (Total)',
        data: new Array(history.length).fill(baseline?.mean_rms_total || 0),
        borderColor: 'rgba(255, 255, 255, 0.6)',
        borderDash: [5, 5],
        pointRadius: 0,
        fill: false,
      },
      // Keep X, Y, Z but make them thinner and slightly transparent
      { 
        label: 'RMS X', 
        data: history.map(h => h.rms_x), 
        borderColor: 'rgba(255, 75, 43, 0.4)', 
        borderWidth: 1,
        pointRadius: 0 
      },
      { 
        label: 'RMS Y', 
        data: history.map(h => h.rms_y), 
        borderColor: 'rgba(43, 175, 255, 0.4)', 
        borderWidth: 1,
        pointRadius: 0 
      },
      { 
        label: 'RMS Z', 
        data: history.map(h => h.rms_z), 
        borderColor: 'rgba(43, 255, 128, 0.4)', 
        borderWidth: 1,
        pointRadius: 0 
      },
    ],
  };

  const options = {
    responsive: true,
    plugins: {
      legend: {
        labels: { color: '#fff' }
      },
      tooltip: {
        mode: 'index',
        intersect: false,
      }
    },
    scales: {
      y: {
        title: { display: true, text: 'Vibration (g)', color: '#fff' },
        ticks: { color: '#ccc' },
        grid: { color: 'rgba(255, 255, 255, 0.1)' }
      },
      x: {
        ticks: { color: '#ccc' },
        grid: { display: false }
      }
    }
  };

  return <Line data={chartData} options={options} />;
}