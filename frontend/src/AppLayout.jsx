import { Outlet, Link, useNavigate } from 'react-router-dom';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import { useAuth } from "./auth/AuthProvider";
import logo from "./assets/logo.svg";

export default function AppLayout() {
    const { user, logout } = useAuth();
    const nav = useNavigate();

    async function onLogout() {
        await logout();
        nav("/login");
    }
    return (
        <div className="main-layout">
            {user ? <header className="navbar">
                <Link to="/dashboard"><img src={logo} alt='preSense logo' className='logo' /></Link>
                <div className="nav-links">
                    <span>{user.username} | {user.organization}</span>
                    <Link to="/settings">Settings</Link>
                    <Link to="logout" onClick={onLogout}>Logout</Link>
                </div>
            </header> : null}
            <main className="page-content"><Outlet /></main>
            <ToastContainer position="bottom-right" autoClose={4000} theme="dark" newestOnTop />
        </div>
    );
}