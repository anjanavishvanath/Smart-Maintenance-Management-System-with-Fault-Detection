import { useAuth } from "../auth/AuthProvider";
import { Link } from "react-router-dom";

export default function Dashboard() {
    const {user} = useAuth();
    console.log(user);
    return (
        <div>
            <h1>Welcome {user.username}</h1>
            <Link to="/add_device">Add Device</Link>
        </div>
    )
}