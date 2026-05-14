import { useAuth } from "../auth/AuthProvider";
import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { toast } from 'react-toastify';
import AssetProvisioning from "../components/AssetProvisioning";
import api from "../api";
import VibrationSpectrum from "../components/VibrationSpectrum";
import HealthTrend from "../components/HealthTrend";
import { assetService } from "../utils/deviceHelpers";

export default function AssetPage() {
    const { user } = useAuth();
    const [selectedAsset, setSelectedAsset] = useState(null);
    const [showForm, setShowForm] = useState(false);
    const [assets, setAssets] = useState([]);
    const [spectrumData, setSpectrumData] = useState(null);
    const [healthHistory, setHealthHistory] = useState([]);
    const [isCalibrating, setIsCalibrating] = useState(false);
    const [isResettingBaseline, setIsResettingBaseline] = useState(false);
    const [baselineData, setBaselineData] = useState(null);
    const [lastUpdated, setLastUpdated] = useState(null);
    const [secondsAgo, setSecondsAgo] = useState(0);

    // Edit / delete state
    const [editingAsset, setEditingAsset] = useState(null);
    const [editForm, setEditForm] = useState({ name: "", max_rpm: 0, power: 0 });
    const [isSavingEdit, setIsSavingEdit] = useState(false);
    const [deletingAssetId, setDeletingAssetId] = useState(null);

    const fetchAssets = async () => {
        try {
            const response = await api.get('/assets/by_organization');
            setAssets(response.data.assets);
        } catch (error) {
            console.error("Error fetching assets:", error);
        }
    };

    const fetchData = async () => {
        if (!selectedAsset) return;
        try {
            // Fetch Spectrum (FFT)
            const specRes = await api.get(`/analytics/spectrum/${selectedAsset}`);
            setSpectrumData(specRes.data.metrics);

            // Fetch Trend History
            const healthRes = await api.get(`/analytics/health/${selectedAsset}`);
            setHealthHistory(healthRes.data.history);

            // Baseline can legitimately be missing (404) — swallow that case.
            try {
                const baselineRes = await api.get(`/assets/baseline/${selectedAsset}`);
                setBaselineData(baselineRes.data);
            } catch (err) {
                if (err.response?.status === 404) setBaselineData(null);
                else throw err;
            }
            setLastUpdated(Date.now());
        } catch (error) {
            console.error("Error fetching live data:", error);
        }
    };

    // Tick once a second so the "X seconds ago" label stays fresh between fetches.
    useEffect(() => {
        if (!lastUpdated) return;
        setSecondsAgo(Math.floor((Date.now() - lastUpdated) / 1000));
        const tick = setInterval(() => {
            setSecondsAgo(Math.floor((Date.now() - lastUpdated) / 1000));
        }, 1000);
        return () => clearInterval(tick);
    }, [lastUpdated]);

    const formatLastUpdated = () => {
        if (!lastUpdated) return null;
        if (secondsAgo < 5) return "just now";
        if (secondsAgo < 60) return `${secondsAgo}s ago`;
        const mins = Math.floor(secondsAgo / 60);
        return `${mins}m ago`;
    };

    const handleSetBaseline = async (assetId) => {
        setIsCalibrating(true);
        try {
            await api.post(`/assets/baseline/${assetId}`);
            toast.success("Baseline calibration initiated successfully.");
            // Refresh baseline so the chart's reference line updates.
            try {
                const baselineRes = await api.get(`/assets/baseline/${assetId}`);
                setBaselineData(baselineRes.data);
            } catch { /* ignore */ }
        } catch (error) {
            toast.error(error.response?.data?.error || "Failed to initiate baseline calibration.");
        } finally {
            setIsCalibrating(false);
        }
    };

    const handleResetBaseline = async (assetId) => {
        if (!window.confirm("Reset this asset's baseline? You'll need to calibrate again before anomaly detection works correctly.")) {
            return;
        }
        setIsResettingBaseline(true);
        try {
            await assetService.resetBaseline(assetId);
            setBaselineData(null);
            toast.success("Baseline cleared. Click 'Set Baseline' when the machine is healthy to calibrate again.");
        } catch (err) {
            console.error("Failed to reset baseline", err);
            toast.error(err.response?.data?.error || "Failed to reset baseline.");
        } finally {
            setIsResettingBaseline(false);
        }
    };

    const startEditAsset = (asset) => {
        setEditingAsset(asset);
        setEditForm({
            name: asset.name || "",
            max_rpm: asset.max_rpm ?? 0,
            power: asset.power ?? 0,
        });
    };

    const cancelEditAsset = () => {
        setEditingAsset(null);
    };

    // Close edit modal on Escape
    useEffect(() => {
        if (!editingAsset) return;
        const handleKeyDown = (e) => {
            if (e.key === 'Escape') cancelEditAsset();
        };
        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [editingAsset]);

    const saveEditAsset = async (e) => {
        e.preventDefault();
        if (!editingAsset) return;
        const trimmedName = editForm.name.trim();
        if (!trimmedName) {
            toast.error("Asset name is required.");
            return;
        }
        setIsSavingEdit(true);
        try {
            await assetService.update(editingAsset.id, {
                name: trimmedName,
                max_rpm: parseInt(editForm.max_rpm) || 0,
                power: parseFloat(editForm.power) || 0,
            });
            // Optimistic update
            setAssets(prev => prev.map(a => a.id === editingAsset.id
                ? { ...a, name: trimmedName, max_rpm: parseInt(editForm.max_rpm) || 0, power: parseFloat(editForm.power) || 0 }
                : a
            ));
            toast.success("Asset updated.");
            cancelEditAsset();
        } catch (err) {
            console.error("Failed to update asset", err);
            toast.error(err.response?.data?.error || "Failed to update asset.");
        } finally {
            setIsSavingEdit(false);
        }
    };

    const handleDeleteAsset = async (asset) => {
        if (!window.confirm(
            `Delete "${asset.name}"? It will disappear from the UI but its sensor data, ` +
            `event history, and tickets will be preserved for audit. This cannot be undone from the UI.`
        )) {
            return;
        }
        setDeletingAssetId(asset.id);
        try {
            await assetService.remove(asset.id);
            setAssets(prev => prev.filter(a => a.id !== asset.id));
            if (selectedAsset === asset.id) setSelectedAsset(null);
            toast.success("Asset deleted.");
        } catch (err) {
            console.error("Failed to delete asset", err);
            toast.error(err.response?.data?.error || "Failed to delete asset.");
        } finally {
            setDeletingAssetId(null);
        }
    };

    useEffect(() => { fetchAssets(); }, []);

    useEffect(() => {
        fetchData();
        const interval = setInterval(() => {
            if (selectedAsset) {
                fetchData();
            }
        }, 5000);
        return () => clearInterval(interval);
    }, [selectedAsset]);

    const stop = (e) => e.stopPropagation();

    const assetList = assets.map((asset) => (
        <React.Fragment key={asset.id}>
            <div
                className={`card card-hover ${selectedAsset === asset.id ? 'card-selected' : ''}`}
                onClick={() => setSelectedAsset(prev => prev !== asset.id ? asset.id : null)}
            >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <h3 style={{ margin: 0 }}>{asset.name}</h3>
                    <div style={{ display: 'flex', gap: '0.25rem' }} onClick={stop}>
                        <button
                            className="btn btn-sm"
                            style={{ padding: '0.1rem 0.4rem', fontSize: '0.8rem' }}
                            onClick={() => startEditAsset(asset)}
                            title="Edit asset"
                        >
                            Edit
                        </button>
                        <button
                            className="btn btn-sm"
                            style={{ padding: '0.1rem 0.4rem', fontSize: '0.8rem', backgroundColor: '#ff4d4d', color: '#fff' }}
                            onClick={() => handleDeleteAsset(asset)}
                            disabled={deletingAssetId === asset.id}
                            title="Delete asset"
                        >
                            {deletingAssetId === asset.id ? "..." : "Delete"}
                        </button>
                    </div>
                </div>
                <p><span className="text-highlight">Max RPM:</span> {asset.max_rpm}</p>
                <p><span className="text-highlight">Power:</span> {asset.power} kW</p>
            </div>

            {selectedAsset === asset.id && (
                <>
                    <div className="asset-controls">
                        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                            <button
                                className="btn btn-secondary"
                                onClick={() => handleSetBaseline(asset.id)}
                                disabled={isCalibrating}
                            >
                                {isCalibrating ? "Calibrating..." : "Set Baseline"}
                            </button>
                            <button
                                className="btn"
                                onClick={() => handleResetBaseline(asset.id)}
                                disabled={isResettingBaseline || !baselineData}
                                title={!baselineData ? "No baseline to reset" : "Clear baseline so it can be recalibrated"}
                            >
                                {isResettingBaseline ? "Resetting..." : "Reset Baseline"}
                            </button>
                        </div>
                        <p className="text-muted">* Ensure machine is running in a healthy state before calibrating.</p>
                        {lastUpdated && (
                            <p className="text-muted" style={{ fontSize: '0.85rem' }}>
                                Live data — updated {formatLastUpdated()}
                            </p>
                        )}
                    </div>
                    <div className="chart-card">
                        <h3>Vibration Trend (Health)</h3>
                        <HealthTrend history={healthHistory} baseline={baselineData}/>
                    </div>
                    <div className="chart-card">
                        <h3>Diagnostic Spectrum (FFT)</h3>
                        <VibrationSpectrum data={spectrumData} />
                    </div>
                </>
            )}
        </React.Fragment>
    ));

    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h1>Asset Registry</h1>
                <Link to="/dashboard" className="btn">Back to Dashboard</Link>
            </div>

            <button className="btn btn-primary" onClick={() => setShowForm(prevState => !prevState)}>
                {showForm ? 'Cancel' : 'Add New Asset'}
            </button>

            {showForm && (
                <div style={{ marginTop: '2rem', padding: '2rem', backgroundColor: 'var(--bg-panel)', border: '1px solid var(--border-color)', borderRadius: '6px' }}>
                    <h2>Register New Asset</h2>
                    <AssetProvisioning onSuccess={() => {
                        fetchAssets();
                        setShowForm(false);
                    }} />
                </div>
            )}

            <div className="grid-view">
                {assets.length === 0 ? (
                    <div className="card" style={{ textAlign: 'center', padding: '2rem', gridColumn: '1 / -1' }}>
                        <p className="text-muted">
                            No assets yet. Click <strong>Add New Asset</strong> to register your first machine.
                        </p>
                    </div>
                ) : assetList}
            </div>

            {editingAsset && (
                <div className="modalOverlayStyle">
                    <div className="modalContentStyle">
                        <h2>Edit Asset</h2>
                        <form onSubmit={saveEditAsset}>
                            <div className="form-group">
                                <label htmlFor="editAssetName">Asset Name</label>
                                <input
                                    id="editAssetName"
                                    type="text"
                                    value={editForm.name}
                                    onChange={e => setEditForm({ ...editForm, name: e.target.value })}
                                    required
                                    autoFocus
                                />
                            </div>
                            <div className="form-group">
                                <label htmlFor="editAssetRpm">Max RPM</label>
                                <input
                                    id="editAssetRpm"
                                    type="number"
                                    min="0"
                                    value={editForm.max_rpm}
                                    onChange={e => setEditForm({ ...editForm, max_rpm: e.target.value })}
                                />
                            </div>
                            <div className="form-group">
                                <label htmlFor="editAssetPower">Power (kW)</label>
                                <input
                                    id="editAssetPower"
                                    type="number"
                                    min="0"
                                    step="0.1"
                                    value={editForm.power}
                                    onChange={e => setEditForm({ ...editForm, power: e.target.value })}
                                />
                            </div>
                            <div className="modal-actions">
                                <button type="button" className="btn" onClick={cancelEditAsset} disabled={isSavingEdit}>
                                    Cancel
                                </button>
                                <button type="submit" className="btn btn-primary" disabled={isSavingEdit}>
                                    {isSavingEdit ? "Saving..." : "Save Changes"}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    )
}
