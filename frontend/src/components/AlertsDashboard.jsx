
import React, { useEffect, useState } from 'react';
import { toast } from 'react-toastify';
import api from '../api';
import './AlertsDashboard.css';
import CreateTicketModal from './CreateTicketModal';

export default function AlertsDashboard() {
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedAlert, setSelectedAlert] = useState(null);
    const [isModalOpen, setIsModalOpen] = useState(false);

    useEffect(() => {
        fetchAlerts();
        const interval = setInterval(fetchAlerts, 10000); // 10s poll
        return () => clearInterval(interval);
    }, []);

    const fetchAlerts = async () => {
        try {
            const res = await api.get('/alerts/recent');
            setAlerts(res.data);
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
                                <div style={{ marginTop: '1rem' }}>
                                    <button
                                        className="btn btn-primary btn-sm"
                                        onClick={() => {
                                            setSelectedAlert(alert);
                                            setIsModalOpen(true);
                                        }}
                                    >
                                        Raise Ticket
                                    </button>
                                </div>
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

            {isModalOpen && selectedAlert && (
                <CreateTicketModal
                    onClose={() => {
                        setIsModalOpen(false);
                        setSelectedAlert(null);
                    }}
                    onSuccess={() => {
                        setIsModalOpen(false);
                        setSelectedAlert(null);
                        toast.success("Ticket created successfully!");
                    }}
                    initialData={{
                        asset_id: selectedAlert.asset_id,
                        event_id: selectedAlert.id,
                        title: selectedAlert.initial_diagnosis
                    }}
                />
            )}
        </div>
    );
}
