import { useAuth } from "../auth/AuthProvider";
import { useState } from "react";
import { Link } from "react-router-dom";
import AssetProvisioning from "../components/AssetProvisioning";

export default function AssetPage() {
    const {user} = useAuth();
    const [showForm, setShowForm] = useState(false);

    return (
        <div>
            <h1>Asset Registry</h1>
            <p>Welcome {user.username} | {user.organization}</p>
            <Link to="/dashboard">Back</Link>
            <button onClick={() => setShowForm(prevState => !prevState)}>Add Asset</button>
            {showForm && (
                <div>
                    <h2>Get Activation Code</h2>
                    <AssetProvisioning />
                </div>
            )}
        </div>
    )
}