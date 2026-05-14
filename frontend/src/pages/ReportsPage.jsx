import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { toast } from "react-toastify";
import api from "../api";
import { API_BASE_url } from "../api";
import tokenService from "../utils/tokenHelpers";

// User's local timezone, e.g. "Asia/Colombo" — shown as a hint so timestamps
// aren't ambiguous. Values are stored as UTC server-side.
const USER_TZ = Intl.DateTimeFormat().resolvedOptions().timeZone || "local";

/** Append a date-range query string if either bound is set. */
function withRange(path, from, to, extra = "") {
    const params = new URLSearchParams();
    if (from) params.set("from", new Date(from).toISOString());
    if (to) params.set("to", new Date(to).toISOString());
    if (extra) params.set(extra.split("=")[0], extra.split("=")[1]);
    const qs = params.toString();
    return qs ? `${path}?${qs}` : path;
}

/** Authenticated download → save as a file with the given name. */
async function downloadAuthed(url, filename) {
    const access = tokenService.getAccess();
    const response = await fetch(url, { headers: { Authorization: `Bearer ${access}` } });
    if (!response.ok) throw new Error(`Export failed (${response.status})`);
    const blob = await response.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = blobUrl;
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    link.parentNode.removeChild(link);
    window.URL.revokeObjectURL(blobUrl);
}

export default function ReportsPage() {
    const [reliabilityReport, setReliabilityReport] = useState([]);
    const [alertReport, setAlertReport] = useState([]);
    const [assets, setAssets] = useState([]);
    const [selectedAssetForExport, setSelectedAssetForExport] = useState("");

    // Shared date range. Empty strings = no filter.
    const [fromDate, setFromDate] = useState("");
    const [toDate, setToDate] = useState("");

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    const fetchReports = useCallback(async () => {
        setLoading(true);
        setError("");
        try {
            const [relRes, alertRes] = await Promise.all([
                api.get(withRange("/reports/reliability", fromDate, toDate)),
                api.get(withRange("/reports/alert_resolution", fromDate, toDate)),
            ]);
            setReliabilityReport(relRes.data);
            setAlertReport(alertRes.data);
        } catch (err) {
            console.error("Failed to load reports", err);
            setError("Failed to load one or more reports. Check connection.");
        } finally {
            setLoading(false);
        }
    }, [fromDate, toDate]);

    useEffect(() => {
        async function fetchAssets() {
            try {
                const assetRes = await api.get("/assets/by_organization");
                setAssets(assetRes.data.assets || []);
            } catch (err) {
                console.error("Failed to load assets", err);
            }
        }
        fetchAssets();
        fetchReports();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const applyDateRange = () => {
        if (fromDate && toDate && new Date(fromDate) > new Date(toDate)) {
            toast.error("'From' date must be before 'To' date.");
            return;
        }
        fetchReports();
    };

    const clearDateRange = () => {
        setFromDate("");
        setToDate("");
        // Refetch with empty range
        setTimeout(fetchReports, 0);
    };

    const handleDownloadFFT = async () => {
        if (!selectedAssetForExport) return;
        try {
            const url = `${API_BASE_url}/api/${withRange(
                `reports/fft_export/${selectedAssetForExport}`,
                fromDate,
                toDate,
            )}`;
            await downloadAuthed(url, `fft_analysis_asset_${selectedAssetForExport}.csv`);
        } catch (err) {
            console.error(err);
            toast.error("Failed to download FFT export.");
        }
    };

    const handleDownloadReliability = async () => {
        try {
            const url = `${API_BASE_url}/api/${withRange("reports/reliability/export", fromDate, toDate)}`;
            await downloadAuthed(url, "reliability_report.csv");
        } catch (err) {
            console.error(err);
            toast.error("Failed to download reliability report.");
        }
    };

    const handleDownloadAlertResolution = async () => {
        try {
            const url = `${API_BASE_url}/api/${withRange("reports/alert_resolution/export", fromDate, toDate)}`;
            await downloadAuthed(url, "alert_resolution_report.csv");
        } catch (err) {
            console.error(err);
            toast.error("Failed to download alert resolution report.");
        }
    };

    if (loading) return <div>Loading reports...</div>;
    if (error) return <div className="text-danger">{error}</div>;

    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h1>MIS Reporting Module</h1>
                <Link to="/dashboard" className="btn">Back to Dashboard</Link>
            </div>

            {/* Shared date-range filter */}
            <section className="card" style={{ padding: '1rem', marginBottom: '1.5rem' }}>
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
                    <div className="form-group" style={{ margin: 0 }}>
                        <label htmlFor="fromDate">From</label>
                        <input
                            id="fromDate"
                            type="datetime-local"
                            value={fromDate}
                            onChange={e => setFromDate(e.target.value)}
                        />
                    </div>
                    <div className="form-group" style={{ margin: 0 }}>
                        <label htmlFor="toDate">To</label>
                        <input
                            id="toDate"
                            type="datetime-local"
                            value={toDate}
                            onChange={e => setToDate(e.target.value)}
                        />
                    </div>
                    <button className="btn btn-primary" onClick={applyDateRange}>Apply</button>
                    <button className="btn" onClick={clearDateRange} disabled={!fromDate && !toDate}>
                        Clear
                    </button>
                    <p className="text-muted" style={{ margin: 0, fontSize: '0.85rem' }}>
                        Times shown in <strong>{USER_TZ}</strong>. Stored as UTC.
                    </p>
                </div>
            </section>

            <section style={{ marginTop: '2rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h2>Asset Reliability & KPI Report</h2>
                    <button className="btn btn-secondary" onClick={handleDownloadReliability}>
                        Download CSV
                    </button>
                </div>
                <div className="card">
                    <table className="table" style={{ width: '100%', textAlign: 'left' }}>
                        <thead>
                            <tr>
                                <th>Asset ID</th>
                                <th>Asset Name</th>
                                <th>Uptime (%)</th>
                                <th>Critical Alerts</th>
                                <th>Health Score</th>
                                <th>Diagnosis</th>
                            </tr>
                        </thead>
                        <tbody>
                            {reliabilityReport.length === 0 && <tr><td colSpan="6">No data available.</td></tr>}
                            {reliabilityReport.map(r => (
                                <tr key={r.asset_id}>
                                    <td>{r.asset_id}</td>
                                    <td>{r.asset_name}</td>
                                    <td>{r.uptime_percentage}%</td>
                                    <td>{r.critical_alert_count}</td>
                                    <td>{r.condition_score === 0 ? 'Healthy' : r.condition_score === 1 ? 'Warning' : 'Critical'}</td>
                                    <td>{r.diagnosis}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </section>

            <section style={{ marginTop: '2rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h2>Alert Resolution & Maintenance Audit</h2>
                    <button className="btn btn-secondary" onClick={handleDownloadAlertResolution}>
                        Download CSV
                    </button>
                </div>
                <div className="card">
                    <table className="table" style={{ width: '100%', textAlign: 'left' }}>
                        <thead>
                            <tr>
                                <th>Ticket ID</th>
                                <th>Asset Name</th>
                                <th>Diagnosis</th>
                                <th>Status</th>
                                <th>Timestamp</th>
                                <th>Response Time (Hrs)</th>
                            </tr>
                        </thead>
                        <tbody>
                            {alertReport.length === 0 && <tr><td colSpan="6">No tickets found.</td></tr>}
                            {alertReport.map(a => (
                                <tr key={a.ticket_id}>
                                    <td>{a.ticket_id}</td>
                                    <td>{a.asset_name}</td>
                                    <td>{a.diagnosis || 'N/A'}</td>
                                    <td>{a.status}</td>
                                    <td>{new Date(a.timestamp).toLocaleString()}</td>
                                    <td>{a.response_time_hours !== null ? a.response_time_hours : 'Pending'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </section>

            <section style={{ marginTop: '2rem' }}>
                <h2>Technical FFT Deep-Dive Export</h2>
                <div className="card" style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
                    <select
                        className="form-control"
                        value={selectedAssetForExport}
                        onChange={e => setSelectedAssetForExport(e.target.value)}
                        style={{ maxWidth: '300px' }}
                    >
                        <option value="">-- Select Asset --</option>
                        {assets.map(a => (
                            <option key={a.id} value={a.id}>{a.name} (ID: {a.id})</option>
                        ))}
                    </select>
                    <button
                        className="btn btn-primary"
                        onClick={handleDownloadFFT}
                        disabled={!selectedAssetForExport}
                    >
                        Export CSV
                    </button>
                    <p className="text-muted" style={{ margin: 0 }}>
                        Exports a CSV containing timestamps, X/Y/Z dominant frequencies, RMS velocities, and Z-scores.
                        Honours the date range above.
                    </p>
                </div>
            </section>
        </div>
    );
}
