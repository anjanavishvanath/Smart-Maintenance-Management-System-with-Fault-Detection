import { useState } from "react";
import api from "../api";
import { useAuth } from "../auth/AuthProvider";
import { Link } from "react-router-dom";

export default function AssetProvisioning() {
    const user = useAuth();

    const [assetName, setAssetName] = useState('');
    const [maxRPM, setMaxRPM] = useState(0);
    const [power, setPower] = useState(0);
    // list of users in org and in charge person?, pic?, location?. See what other information about assets will be usefull for CM
    const [isLoading, setIsLoading] = useState(false);

    const handleAddAssetRequest = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        try {
            const response = await api.post("/assets/add", {
                name: assetName,
                max_rpm: maxRPM,
                power: power,
                organization: user.organization,
                user_id: user.id
            });
            console.log("Asset added successfully:", response.data);
            setIsLoading(false);
        } catch (e) {
            console.error("Error adding asset:", e);
        }
    }

    return (
        <div>
            <form onSubmit={handleAddAssetRequest}>
                <div className="form-group">
                    <label htmlFor="assetNameInput">Asset Name</label>
                    <input
                        id="assetNameInput"
                        type="text"
                        value={assetName}
                        onChange={(e) => setAssetName(e.target.value)}
                    />
                </div>
                <div className="form-group">
                    <label htmlFor="maxRPMInput">Max RPM</label>
                    <input
                        id="maxRPMInput"
                        type="number"
                        value={maxRPM}
                        onChange={(e) => setMaxRPM(e.target.value)}
                    />
                </div>
                <div className="form-group">
                    <label htmlFor="powerInput">Power (W)</label>
                    <input
                        id="powerInput"
                        type="number"
                        value={power}
                        onChange={(e) => setPower(e.target.value)}
                    />
                </div>
                <button type="submit" disabled={isLoading}>Add Asset</button>
            </form>
        </div>
    )
}