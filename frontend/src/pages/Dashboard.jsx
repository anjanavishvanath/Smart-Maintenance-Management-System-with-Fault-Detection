import { useAuth } from "../auth/AuthProvider";
import { Link } from "react-router-dom";

export default function Dashboard() {
    const {user} = useAuth();
    console.log(user);
    return (
        <div>
            <h1>Welcome {user.username} | {user.organization}</h1>
            <Link to="/asset_registry">Asset Registry</Link>
            <Link to="/sensor_registry">Sensor Registry</Link>
        </div>
    );
}