import { useAuth } from "../auth/AuthProvider";
import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { toast } from 'react-toastify';
import AssetProvisioning from "../components/AssetProvisioning";
import api from "../api";
import VibrationSpectrum from "../components/VibrationSpectrum";
import HealthTrend from "../components/HealthTrend";

export default function AssetPage() {
    const { user } = useAuth();
    const [selectedAsset, setSelectedAsset] = useState(null);
    const [showForm, setShowForm] = useState(false);
    const [assets, setAssets] = useState([]);
    const [spectrumData, setSpectrumData] = useState(null);
    const [healthHistory, setHealthHistory] = useState([]);
    const [isCalibrating, setIsCalibrating] = useState(false);
    const [baselineData, setBaselineData] = useState(null);

    const fetchAssets = async () => {
        try {
            const response = await api.get('/assets/by_organization');
            console.log("Assets fetched:", response.data.assets);
            setAssets(response.data.assets);
        } catch (error) {
            console.error("Error fetching assets:", error);
        }
    };

    const fetchData = async () => {
        if (!selectedAsset) return;
        console.log("Fetching data for asset:", selectedAsset);
        try {
            // Fetch Spectrum (FFT)
            const specRes = await api.get(`/analytics/spectrum/${selectedAsset}`);
            setSpectrumData(specRes.data.metrics); // Your backend returns { metrics: {...} }

            // Fetch Trend History
            const healthRes = await api.get(`/analytics/health/${selectedAsset}`);
            setHealthHistory(healthRes.data.history);

            const baselineRes = await api.get(`/assets/baseline/${selectedAsset}`);
            setBaselineData(baselineRes.data);
        } catch (error) {
            console.error("Error fetching spectrum:", error);
        }
    };

    const handleSetBaseline = async (assetId) => {
        setIsCalibrating(true);
        try {
            const response = await api.post(`/assets/baseline/${assetId}`);
            console.log(response.data.message);
            toast.success("Baseline calibration initiated successfully.");
        } catch (error) {
            toast.error("Failed to initiate baseline calibration.");
        } finally {
            setIsCalibrating(false);
        }
    };

    useEffect(() => { fetchAssets(); }, []);

    useEffect(() => {
        fetchData();
        const interval = setInterval(() => {
            if (selectedAsset) {
                console.log("Refreshing live data...");
                fetchData();
            }
        }, 5000);
        return () => clearInterval(interval);
    }, [selectedAsset]);

    const assetList = assets.map((asset) => (
        <React.Fragment key={asset.id}>
            <div
                className={`card card-hover ${selectedAsset === asset.id ? 'card-selected' : ''}`}
                onClick={() => setSelectedAsset(prev => prev !== asset.id ? asset.id : null)}
            >
                <h3>{asset.name}</h3>
                <p><span className="text-highlight">Max RPM:</span> {asset.max_rpm}</p>
                <p><span className="text-highlight">Power:</span> {asset.power} kW</p>
            </div>

            {selectedAsset === asset.id && (
                <>
                    <div className="asset-controls">
                        <button
                            className="btn btn-secondary"
                            onClick={() => handleSetBaseline(asset.id)}
                            disabled={isCalibrating}
                        >
                            {isCalibrating ? "Calibrating..." : "Set Baseline"}
                        </button>
                        <p className="text-muted">* Ensure machine is running in a healthy state before calibrating.</p>
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
                {assetList}
            </div>
        </div>
    )
}