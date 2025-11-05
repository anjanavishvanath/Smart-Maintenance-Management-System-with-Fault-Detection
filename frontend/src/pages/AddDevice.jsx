import React, {useState} from 'react';
import { deviceService } from '../services/deviceService';

export default function AddDevice() {
  const [deviceId, setDeviceId] = useState("");
  const [claim, setClaim] = useState("");
  const [mac, setMac] = useState("");
  const [fw, setFw] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const onSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    try{
        const payload = {device_id: deviceId.trim(), claim_token: claim.trim(), mac: mac.trim(), fw_version: fw.trim()};
        const res = await deviceService.provisionDevice(payload);
        setResult(res);
    }catch(err){
        setError(err?.response?.data?.msg || err.message || "Provision failed");
    } finally {
        setBusy(false);
    }
  };

  return (
    <div className='add-device-page'>
        <h2>Provision Device</h2>
        <form onSubmit={onSubmit}>
            <div className='form-group'>
                <label htmlFor="deviceId">Device ID</label>
                <input 
                    type="text"
                    id="deviceId"
                    placeholder='e.g., dev000'
                    value={deviceId}  
                    onChange={e => setDeviceId(e.target.value)}
                    required
                />
            </div>

            <div className='form-group'>
                <label htmlFor="claim">Claim Token (Optional)</label>
                <input 
                    type="text"
                    id="claim"
                    value={claim}  
                    onChange={e => setClaim(e.target.value)}
                />
            </div>

            <div className='form-group'>
                <label htmlFor="mac">MAC (Optional)</label>
                <input 
                    type="text"
                    id="mac"
                    value={mac}  
                    onChange={e => setMac(e.target.value)}
                />
            </div>

            <div className='form-group'>
                <label htmlFor="firmware">Firmware (Optional)</label>
                <input 
                    type="text"
                    id="firmware"
                    value={fw}  
                    onChange={e => setFw(e.target.value)}
                />
            </div>

            <button type="submit" disabled={busy}>{busy?"Provisioning":"Provision Device"}</button>
        </form>

        {error && <div className='error-msg'>Error: {error}</div>}
        
        {result && (
            <div>
                <h3>Device Provisioned</h3>
                <p><strong>Device ID: </strong> {deviceId}</p>
                <h4>MQTT Cridentials</h4>
                <pre>{JSON.stringify(result.credentials, null, 2)}</pre>
                <p>
                    <ul>
                      <li>Cluster → Access management → Credentials → Add credential</li>
                      <li>Set username & password exactly as returned</li>
                      <li>Grant topic publish/subscribe permissions (e.g. <code>v1/device/{deviceId}/#</code>)</li>
                    </ul>
                </p>
                <h4>Device config</h4>
                <pre>{JSON.stringify(result.config, null, 2)}</pre>
            </div>
        )}
    </div> 
  )
}

