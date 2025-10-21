import { Link } from "react-router-dom"
import { useAuth } from "../auth/AuthProvider"
export default function Dashboard(){
    const {user} = useAuth();
    console.log("user in dashboard:", user);
    return(
        <div>
            <div className="dash-welcome">
                <h2>Welcome {user.username}</h2>
                {/* subscribed company */}
            </div>
            <div className="dash-add-device">
                <Link to="/add-device">Add Device</Link>
                {/* devices or groups */}
            </div>
        </div>
    )
}