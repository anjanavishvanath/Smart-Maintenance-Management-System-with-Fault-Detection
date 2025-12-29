import { useAuth } from "../auth/AuthProvider";
import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import AssetProvisioning from "../components/AssetProvisioning";
import api from "../api";

export default function AssetPage() {
    const { user } = useAuth();
    const [showForm, setShowForm] = useState(false);
    const [assets, setAssets] = useState([]);

    const fetchAssets = async () => {
        try {
            const response = await api.get('/assets/by_organization');
            console.log("Assets fetched:", response.data.assets);
            setAssets(response.data.assets);
        } catch (error) {
            console.error("Error fetching assets:", error);
        }
    }

    useEffect(() => { fetchAssets(); }, []);

    const assetList = assets.map((asset) => (
        <div key={asset.id} className="card">
            <h3>{asset.name}</h3>
            <p><span className="text-highlight">Max RPM:</span> {asset.max_rpm}</p>
            <p><span className="text-highlight">Power:</span> {asset.power} kW</p>
        </div>
    ))

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