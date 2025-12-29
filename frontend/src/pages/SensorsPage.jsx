import { useAuth } from "../auth/AuthProvider";
import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import DeviceProvisioning from "../components/DeviceProvisioning";

import api from "../api";

export default function SensorsPage() {
    const { user } = useAuth();
    const [showForm, setShowForm] = useState(false);
    const [sensors, setSensors] = useState([]);

    const fetchSensors = async () => {
        try {
            const response = await api.get('/devices/by_user');
            console.log("Sensors fetched:", response.data.devices);
            setSensors(response.data.devices);
        } catch (error) {
            console.error("Error fetching devices:", error);
        }
    }

    useEffect(() => { fetchSensors(); }, []);

    const sensorList = sensors.map((sensor) => (
        <div key={sensor.id} className="card">
            <h3>{sensor.device_name ? sensor.device_name : "Unnamed Device"}</h3>
            <p className="text-muted">ID: {sensor.id}</p>
            <p><span className="text-highlight">Created:</span> {new Date(sensor.created_at).toLocaleDateString()}</p>
            <p><span className="text-highlight">Asset ID:</span> {sensor.asset_id || 'Unassigned'}</p>
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
        </div>
    )
}