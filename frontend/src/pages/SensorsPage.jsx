import { useAuth } from "../auth/AuthProvider";
import { useState } from "react";
import { Link } from "react-router-dom";
import DeviceProvisioning from "../components/DeviceProvisioning";

export default function SensorsPage() {
    const {user} = useAuth();
    const [showForm, setShowForm] = useState(false);

    return (
        <div>
            <h1>Sensors Registry</h1>
            <p>Welcome {user.username} | {user.organization}</p>
            <Link to="/dashboard">Back</Link>
            <button onClick={() => setShowForm(prevState => !prevState)}>Add Device</button>
            {showForm && (
                <div>
                    <h2>Get Activation Code</h2>
                    <DeviceProvisioning />
                </div>
            )}
        </div>
    )
}