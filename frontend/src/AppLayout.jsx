import { Outlet, Link, useNavigate } from 'react-router-dom';
import { useAuth } from "./auth/AuthProvider";
import logo from "./assets/logo.svg";

export default function AppLayout() {
    const { user, logout } = useAuth();
    const nav = useNavigate();

    function onLogout() {
        logout();
        nav("/login");
    }
    return (
        <div className="main-layout">
            {user ? <header className="navbar">
                <Link to="/dashboard"><img src={logo} alt='preSense logo' className='logo' /></Link>
                <div className="nav-links">
                    <span>{user.username} | {user.organization}</span>
                    <Link to="logout" onClick={onLogout}>Logout</Link>
                </div>
            </header> : null}
            <main className="page-content"><Outlet /></main>
        </div>
    );
}