
import React, { useEffect, useState } from 'react';
import { API_BASE_url } from '../api';
import './AlertsDashboard.css'; // We will create this next

export default function AlertsDashboard({ token }) {
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!token) return;
        fetchAlerts();
        const interval = setInterval(fetchAlerts, 10000); // 10s poll
        return () => clearInterval(interval);
    }, [token]);

    const fetchAlerts = async () => {
        try {
            const res = await fetch(`${API_BASE_url}/api/alerts/recent`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                setAlerts(data);
            }
        } catch (err) {
            console.error("Failed to fetch alerts:", err);
        } finally {
            setLoading(false);
        }
    };

    // --- Helpers ---
    const getDuration = (start, end) => {
        const s = new Date(start);
        const e = end ? new Date(end) : new Date(); // If null, use now
        const diffMs = e - s;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHrs = Math.floor(diffMins / 60);

        if (diffHrs > 0) return `${diffHrs}h ${diffMins % 60}m`;
        return `${diffMins}m`;
    };

    const activeAlerts = alerts.filter(a => !a.end_time);
    const historyAlerts = alerts.filter(a => a.end_time);

    if (loading && alerts.length === 0) return <div>Loading Alerts...</div>;

    return (
        <div className="alerts-dashboard">
            <div className="alerts-section">
                <h3>Active Issues ({activeAlerts.length})</h3>
                <div className="active-cards-container">
                    {activeAlerts.length === 0 && <p className="all-good">No active issues detected.</p>}
                    {activeAlerts.map(alert => (
                        <div key={alert.id} className={`alert-card severity-${alert.severity}`}>
                            <div className="card-header">
                                <span className="asset-name">{alert.asset_name}</span>
                                <span className="badge">{alert.severity === 2 ? 'CRITICAL' : 'WARNING'}</span>
                            </div>
                            <div className="card-body">
                                <p className="diagnosis">{alert.initial_diagnosis}</p>
                                <p className="duration">Active for: {getDuration(alert.start_time, null)}</p>
                                <p className="z-score">Max Z-Score: {alert.max_z_score?.toFixed(1)}</p>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <div className="alerts-section">
                <h3>History Log</h3>
                <table className="alerts-table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Asset</th>
                            <th>Severity</th>
                            <th>Diagnosis</th>
                            <th>Duration</th>
                        </tr>
                    </thead>
                    <tbody>
                        {historyAlerts.length === 0 && <tr><td colSpan="5">No history yet.</td></tr>}
                        {historyAlerts.map(alert => (
                            <tr key={alert.id}>
                                <td>{new Date(alert.start_time).toLocaleString()}</td>
                                <td>{alert.asset_name}</td>
                                <td>
                                    <span className={`badge-sm severity-${alert.severity}`}>
                                        {alert.severity === 2 ? 'Critical' : 'Warning'}
                                    </span>
                                </td>
                                <td>{alert.initial_diagnosis}</td>
                                <td>{getDuration(alert.start_time, alert.end_time)}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
