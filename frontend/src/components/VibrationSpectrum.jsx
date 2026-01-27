import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler // Adding Filler for a nice area-chart look
} from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);

export default function VibrationSpectrum({ data }) {
  // 1. Updated Guard Clause: Check for data.z (or data.x / data.y)
  if (!data || !data.z || !data.z.frequencies) {
    return <p style={{ color: '#888', textAlign: 'center' }}>No spectrum data available.</p>;
  }

  const chartData = {
    // 2. Map labels from the specific axis
    labels: data.z.frequencies.map(f => f.toFixed(1) + " Hz"),
    datasets: [
      {
        label: 'Z-Axis Amplitude (g)',
        data: data.z.amplitudes,
        borderColor: '#00f2ff',
        backgroundColor: 'rgba(0, 242, 255, 0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 0,
        borderWidth: 2,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false, // Allows the container to control height
    plugins: {
      legend: { labels: { color: '#e0e0e0' } },
    },
    scales: {
      x: { 
        grid: { color: '#333' }, 
        ticks: { color: '#888', maxTicksLimit: 10 } 
      },
      y: { 
        grid: { color: '#333' }, 
        ticks: { color: '#888' },
        beginAtZero: true 
      },
    },
  };

  return (
    <div style={{ height: '300px' }}>
      <Line data={chartData} options={options} />
    </div>
  );
}