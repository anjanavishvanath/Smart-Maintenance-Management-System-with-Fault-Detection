import { Link } from "react-router-dom";
import React, { useEffect, useState } from 'react';
import { useAuth } from "../auth/AuthProvider";
import { deviceService } from "../services/deviceService";
import DeviceReadingsChart from "../components/DeviceReadingsChart";

export default function Dashboard() {
    const { user } = useAuth();
    const [devices, setDevices] = useState([]);
    const [loadingDevices, setLoadingDevices] = useState(false);
    const [selected, setSelected] = useState(null);
    const [readings, setReadings] = useState([]);
    const [loadingReadings, setLoadingReadings] = useState(false);

    console.log("user in dashboard:", user);

    const fetchDevices = async () => {
        setLoadingDevices(true);
        try {
            const res = await deviceService.listDevices(200);
            setDevices(res.devices || []);
        } catch (e) {
            console.error("Failed to fetch devices", e);
        } finally {
            setLoadingDevices(false);
        }
    };

    const selectDevice = async (d) => {
        setSelected(d);
        setLoadingReadings(true);
        try {
            const r = await deviceService.getReadings(d.device_id, 50);
            setReadings(r.readings || []);
        } catch (e) {
            console.error("Failed to fetch readings", e);
            setReadings([]);
        } finally {
            setLoadingReadings(false);
        }
    };

    useEffect(() => {
        fetchDevices();
        // optional: poll devices every 30s
        const tid = setInterval(fetchDevices, 30000);
        return () => clearInterval(tid);
    }, []);


    return (
        <div>
            <div className="dash-welcome">
                <h2>Welcome {user.username}</h2>
                {/* subscribed company */}
            </div>
            <div className="dash-add-device">
                <Link to="/add-device">Add Device</Link>
            </div>

            <section>
                <h3>Devices</h3>
                {loadingDevices ? <div>Loading devices...</div> : null}
                <table className="devices-table">
                    <thead><tr><th>Device ID</th><th>Name</th><th>Status</th><th>Last seen</th><th>Actions</th></tr></thead>
                    <tbody>
                        {devices.map(d => (
                            <tr key={d.device_id}>
                                <td>{d.device_id}</td>
                                <td>{d.name}</td>
                                <td>{d.status}</td>
                                <td>{d.last_seen || "-"}</td>
                                <td>
                                    <button onClick={() => selectDevice(d)}>View readings</button>
                                </td>
                            </tr>
                        ))}
                        {devices.length === 0 && <tr><td colSpan="5">No devices</td></tr>}
                    </tbody>
                </table>
            </section>

            {selected && (
                <section className="device-detail">
                    <h3>Readings for {selected.device_id}</h3>
                    <div style={{ marginBottom: 12 }}>
                        <button onClick={() => selectDevice(selected)} disabled={loadingReadings}>Refresh</button>
                    </div>

                    <div style={{ marginBottom: 20 }}>
                        {/* Chart component; limit 300 points and refresh every 5s */}
                        <DeviceReadingsChart deviceId={selected.device_id} limit={300} refreshMs={5000} />
                    </div>

                    {/* keep raw table below if you want */}
                    <details>
                        <summary>Raw readings table</summary>
                        <table>
                            <thead><tr><th>Time (UTC)</th><th>ax</th><th>ay</th><th>az</th></tr></thead>
                            <tbody>
                                {readings.map((r, i) => (
                                    <tr key={i}>
                                        <td>{r.time}</td>
                                        <td>{r.ax}</td>
                                        <td>{r.ay}</td>
                                        <td>{r.az}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </details>
                </section>
            )}
        </div>
    )
}