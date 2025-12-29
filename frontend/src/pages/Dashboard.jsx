import { useAuth } from "../auth/AuthProvider";
import { Link } from "react-router-dom";

export default function Dashboard() {
    const { user } = useAuth();
    return (
        <div>
            <h1>Dashboard</h1>
            <p className="text-muted">Welcome back, <span className="text-highlight">{user.username}</span> from {user.organization}</p>

            <div className="grid-view">
                <div className="card">
                    <h3>Asset Registry</h3>
                    <p>Manage your industrial assets and machines.</p>
                    <Link to="/asset_registry" className="btn btn-primary" style={{ marginTop: '1rem', display: 'inline-block' }}>View Assets</Link>
                </div>
                <div className="card">
                    <h3>Sensor Registry</h3>
                    <p>Provision and monitor IoT devices.</p>
                    <Link to="/sensor_registry" className="btn btn-primary" style={{ marginTop: '1rem', display: 'inline-block' }}>View Sensors</Link>
                </div>
            </div>
        </div>
    );
}