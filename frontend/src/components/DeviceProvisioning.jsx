import { useState } from "react";
import api from "../api"
import { useAuth } from "../auth/AuthProvider";
import { Link } from "react-router-dom";

export default function DeviceProvisioning() {
    const user = useAuth(); //to ensure the user is logged in
    const [macAddress, setMacAddress] = useState('');
    const [slpt, setSlpt] = useState("");
    const [message, setMessage] = useState("");
    const [isLoading, setIsLoading] = useState(false);

    const handleProvisionRequest = async (e) => {
        e.preventDefault();
        setMessage("");
        setSlpt(null);
        setIsLoading(true);
        try {
            if (!/^[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}$/.test(macAddress)) {
                setMessage("Please enter a valid MAC address (e.g., AA:BB:CC:DD:EE:FF).");
                setIsLoading(false);
                return;
            }
            const response = await api.post("/devices/provision", {
                enrollment_id: macAddress.toUpperCase()
            });
            setSlpt(response.data.slpt);
            setMessage("Provisioning Token generated successfully. See instructions below.");
        } catch (e) {
            console.log("Provisioning error: ", e);
            const errMsg = e.response?.data?.error || e.response?.data?.msg || "An unexpected error occured";
            setMessage(`Error: ${errMsg}`);
        } finally {
            setIsLoading(false);
        }
    };
    return (
        <div className="provisioning-container">
            <form onSubmit={handleProvisionRequest}>
                <div className="form-group">
                    <label htmlFor="macInput">Device Enrollment ID (MAC Address)</label>
                    <input
                        id="macInput"
                        type="text"
                        value={macAddress}
                        onChange={(e) => setMacAddress(e.target.value)}
                        placeholder="AA:BB:CC:DD:EE:FF"
                        required
                    />
                </div>

                <button type="submit" className="btn btn-primary" disabled={isLoading} style={{ marginTop: '1rem' }}>
                    {isLoading ? 'Generating...' : 'Generate Provision Token'}
                </button>
            </form>

            {message && <p className={slpt ? "success-msg" : "error-msg"}>{message}</p>}
            {slpt && (
                <div className="provisioning-instructions">
                    <h3>Instructions for Device Activation:</h3>
                    <p>1. Connect to the device's Wi-Fi access point (e.g., "preSense_provision").</p>
                    <p>2. Go to <code>http://192.168.4.1/</code> in your browser.</p>
                    <p>3. Enter your Home Wi-Fi credentials.</p>
                    <p>4. **Enter the Enrollment ID (MAC) again.**</p>
                    <p>5. **Copy and paste the following token into the form:**</p>
                    <code className="slpt-code">{slpt}</code>
                    <p>6. Submit the form to complete device activation.</p>
                </div>
            )}
        </div>
    );
};