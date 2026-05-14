import { useAuth } from "../auth/AuthProvider";
import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { toast } from "react-toastify";
import DeviceProvisioning from "../components/DeviceProvisioning";
import { deviceService } from "../utils/deviceHelpers";
import api from "../api";

export default function SensorsPage() {
    const { user } = useAuth();
    const [showForm, setShowForm] = useState(false);
    const [sensors, setSensors] = useState([]);
    const [assets, setAssets] = useState([]);
    const [pairingDevice, setPairingDevice] = useState(null); // The device currently being paired
    const [editingId, setEditingId] = useState(null);          // Device whose name is being edited inline
    const [editingName, setEditingName] = useState("");
    const [savingId, setSavingId] = useState(null);
    const [deletingId, setDeletingId] = useState(null);

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

    // Close pairing modal on Escape key
    useEffect(() => {
        if (!pairingDevice) return;
        const handleKeyDown = (e) => {
            if (e.key === 'Escape') setPairingDevice(null);
        };
        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [pairingDevice]);

    const handlePairing = async (assetId) => {
        try {
            await api.post("/assets/link_sensor", {
                device_mac: pairingDevice.device_mac,
                asset_id: assetId === "" ? null : assetId
            });
            setPairingDevice(null);
            toast.success(assetId ? "Sensor paired with asset." : "Sensor unpaired.");
            fetchSensors();
        } catch (err) {
            console.error("Error pairing device with asset", err);
            toast.error("Error pairing device with asset.");
        }
    }

    const startEditName = (sensor) => {
        setEditingId(sensor.id);
        setEditingName(sensor.device_name || "");
    };

    const cancelEditName = () => {
        setEditingId(null);
        setEditingName("");
    };

    const saveEditName = async (sensor) => {
        const trimmed = editingName.trim();
        if (!trimmed) {
            toast.error("Device name cannot be empty.");
            return;
        }
        if (trimmed === (sensor.device_name || "")) {
            cancelEditName();
            return;
        }
        setSavingId(sensor.id);
        try {
            await deviceService.updateName(sensor.id, trimmed);
            // Optimistic update; no need to re-fetch the world.
            setSensors(prev => prev.map(s => s.id === sensor.id ? { ...s, device_name: trimmed } : s));
            toast.success("Device renamed.");
            cancelEditName();
        } catch (err) {
            console.error("Failed to rename device", err);
            toast.error(err.response?.data?.error || "Failed to rename device.");
        } finally {
            setSavingId(null);
        }
    };

    const handleDelete = async (sensor) => {
        const label = sensor.device_name || sensor.device_mac || `device #${sensor.id}`;
        if (!window.confirm(`Delete ${label}? This cannot be undone. Existing sensor data will be kept.`)) {
            return;
        }
        setDeletingId(sensor.id);
        try {
            await deviceService.deleteDevice(sensor.id);
            setSensors(prev => prev.filter(s => s.id !== sensor.id));
            toast.success("Device deleted.");
        } catch (err) {
            console.error("Failed to delete device", err);
            toast.error(err.response?.data?.error || "Failed to delete device.");
        } finally {
            setDeletingId(null);
        }
    };

    const formatLastSeen = (iso) => {
        if (!iso) return { label: "Never seen", className: "badge badge-secondary" };
        const seen = new Date(iso);
        const ageMs = Date.now() - seen.getTime();
        const ageMin = ageMs / 60000;
        if (ageMin < 2) return { label: "Online", className: "badge badge-success" };
        if (ageMin < 60) return { label: `${Math.floor(ageMin)} min ago`, className: "badge badge-warning" };
        if (ageMin < 60 * 24) return { label: `${Math.floor(ageMin / 60)} h ago`, className: "badge badge-secondary" };
        return { label: `${Math.floor(ageMin / 1440)} d ago`, className: "badge badge-secondary" };
    };

    const sensorList = sensors.map((sensor) => (
        <div key={sensor.id} className="card">
            {editingId === sensor.id ? (
                <div className="form-group">
                    <input
                        type="text"
                        value={editingName}
                        onChange={(e) => setEditingName(e.target.value)}
                        autoFocus
                        maxLength={100}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') saveEditName(sensor);
                            if (e.key === 'Escape') cancelEditName();
                        }}
                    />
                    <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                        <button
                            className="btn btn-sm btn-primary"
                            onClick={() => saveEditName(sensor)}
                            disabled={savingId === sensor.id}
                        >
                            {savingId === sensor.id ? "Saving..." : "Save"}
                        </button>
                        <button
                            className="btn btn-sm"
                            onClick={cancelEditName}
                            disabled={savingId === sensor.id}
                        >
                            Cancel
                        </button>
                    </div>
                </div>
            ) : (
                <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    {sensor.device_name ? sensor.device_name : "Unnamed Device"}
                    <button
                        className="btn btn-sm"
                        onClick={() => startEditName(sensor)}
                        title="Rename device"
                        style={{ padding: '0.1rem 0.4rem', fontSize: '0.8rem' }}
                    >
                        Edit
                    </button>
                </h3>
            )}
            <p className="text-muted">ID: {sensor.id}</p>
            <p><span className="text-highlight">MAC:</span> <code>{sensor.device_mac}</code></p>
            <p><span className="text-highlight">Created:</span> {new Date(sensor.created_at).toLocaleDateString()}</p>
            <p><span className="text-highlight">Asset ID:</span> {sensor.asset_id || 'Unassigned'}</p>
            <p>
                <span className="text-highlight">Status:</span>{' '}
                <span className={formatLastSeen(sensor.last_seen).className}>
                    {formatLastSeen(sensor.last_seen).label}
                </span>
            </p>
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                <button
                    className="btn btn-secondary"
                    onClick={() => setPairingDevice(sensor)}
                >
                    {sensor.asset_id ? 'Change Asset' : 'Pair with Asset'}
                </button>
                <button
                    className="btn btn-sm"
                    style={{ backgroundColor: '#ff4d4d', color: '#fff' }}
                    onClick={() => handleDelete(sensor)}
                    disabled={deletingId === sensor.id}
                >
                    {deletingId === sensor.id ? "Deleting..." : "Delete"}
                </button>
            </div>
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
                {sensors.length === 0 ? (
                    <div className="card" style={{ textAlign: 'center', padding: '2rem', gridColumn: '1 / -1' }}>
                        <p className="text-muted">
                            No sensors yet. Click <strong>Provision New Device</strong> to enrol your first ESP32.
                        </p>
                    </div>
                ) : sensorList}
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