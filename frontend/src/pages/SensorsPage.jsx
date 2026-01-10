import { useAuth } from "../auth/AuthProvider";
import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import DeviceProvisioning from "../components/DeviceProvisioning";
import api from "../api";

export default function SensorsPage() {
    const { user } = useAuth();
    const [showForm, setShowForm] = useState(false);
    const [sensors, setSensors] = useState([]);
    const [assets, setAssets] = useState([]);
    const [pairingDevice, setPairingDevice] = useState(null); // The device currently being paired

    const fetchSensors = async () => {
        try {
            const responseSensors = await api.get('/devices/by_user');
            const responseAssets = await api.get('/assets/by_organization');
            console.log("Sensors fetched:", responseSensors.data.devices);
            setSensors(responseSensors.data.devices);
            setAssets(responseAssets.data.assets);
        } catch (error) {
            console.error("Error fetching devices:", error);
        }
    }

    useEffect(() => { fetchSensors(); }, []);

    const handlePairing = async (assetId) => {
        try {
            await api.post("/assets/link_sensor", {
                device_mac: pairingDevice.device_mac,
                asset_id: assetId === "" ? null : assetId
            });
            setPairingDevice(null);
            fetchSensors();
        } catch {
            alert ("Error pairing device with asset.");
        }
    }

    const sensorList = sensors.map((sensor) => (
        <div key={sensor.id} className="card">
            <h3>{sensor.device_name ? sensor.device_name : "Unnamed Device"}</h3>
            <p className="text-muted">ID: {sensor.id}</p>
            <p><span className="text-highlight">Created:</span> {new Date(sensor.created_at).toLocaleDateString()}</p>
            <p><span className="text-highlight">Asset ID:</span> {sensor.asset_id || 'Unassigned'}</p>
            <button 
                className="btn btn-secondary" 
                onClick={() => setPairingDevice(sensor)}>
                    {sensor.asset_id ? 'Change Asset' : 'Pair with Asset'}
            </button>
        </div>
    ))

    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h1>Sensors Registry</h1>
                <Link to="/dashboard" className="btn">Back to Dashboard</Link>
            </div>

            <button className="btn btn-primary" onClick={() => setShowForm(prevState => !prevState)}>
                {showForm ? 'Cancel' : 'Provision New Device'}
            </button>

            {showForm && (
                <div style={{ marginTop: '2rem' }}>
                    <h2>Get Activation Code</h2>
                    <DeviceProvisioning />
                </div>
            )}

            <div className="grid-view">
                {sensorList}
            </div>

            {pairingDevice && (
                <div className="modalOverlayStyle">
                    <div className="modalContentStyle">
                        <h2>Pair Device with Asset</h2>
                        <p>Select asset for <strong>{pairingDevice.device_mac}</strong></p>
                        <select className="selectStyle"
                            onChange={(e) => handlePairing(e.target.value)}
                            defaultValue={pairingDevice.asset_id || ''}
                        >
                            <option value=""> -- Unassign / None --</option>
                            {assets.map(asset => (
                                <option key={asset.id} value={asset.id}>
                                    {asset.name} ({asset.organization})
                                </option>
                            ))}
                        </select>
                        <br />
                        <button className="btn" onClick={() => setPairingDevice(null)}>Cancel</button>
                    </div>
                </div>
            )}
        </div>
    )
}