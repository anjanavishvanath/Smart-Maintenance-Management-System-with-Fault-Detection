import { useAuth } from "../auth/AuthProvider";

export default function Dashboard() {
    const {user} = useAuth();
    console.log(user);
    return (
        <h1>Welcome to the dashboard</h1>
    )
}