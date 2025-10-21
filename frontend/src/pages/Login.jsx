import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from "../auth/AuthProvider.jsx";
import logo from '../assets/logo.svg';
import bg from '../assets/bg.jpg';

export default function Login() {
    const { login } = useAuth();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [err, setErr] = useState('');
    const nav = useNavigate();
    const location = useLocation(); //hook to retrieve current location object from react-router
    //use optional chaining to determine the path
    const from = location.state?.from?.pathname || '/dashboard';
    /*
    Check for 3 posibilities
     - location.state: if location object has an associated "state" object. This state is typically passed when a user is redirected to the login page (e.g., by a <ProtectedRoute>) because they tried to access a protected route first.
     - ?.from: Safely attempts to access a nested property named from within that state. In a protected route setup, the from object often holds the previous location the user was trying to visit.
     - ?.pathname: Safely retrieves the specific path of the previous location (e.g., /admin/settings).

     If all these properties exist, the user's intended destination (ex: /admin/settings) is assigned to from. or fallback to /dashboard
    */


    async function onSubmit(e) {
        e.preventDefault();
        setErr("");
        try {
            await login(email.trim(), password);
            nav(from, {replace: true}); //navigate to the intended destination after login
        }catch (e) {
            setErr(e.response?.data?.msg || e.message || "Login failed");
        }
    }

    return (
        <div className="form-container">
            <div className="buffer-pane">
                <img src={bg} alt="background" />
            </div>
            <form onSubmit={onSubmit}>
                <img src={logo} alt="preSense Logo" className="logo" />
                <div className='form-topic'>
                    <h2>Welcome Back!</h2>
                    <h3>Enter your credentials to access the account</h3>
                </div>
                <div className="form-group">
                    <label htmlFor="emailInput">Email Address</label>
                    <input
                        id="emailInput"
                        type="email"
                        placeholder="e.g., john@example.com"
                        value={email}
                        onChange={e => setEmail(e.target.value)}
                        required
                    />
                </div>
                <div className="form-group">
                    <label htmlFor="passInput">Enter Password</label>
                    <input
                        id="passInput"
                        type="password"
                        placeholder="Create a password"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        required
                    />
                </div>
                {err && <div className="error-msg">{err}</div>}
                <button type="submit" className="btn submit">Login</button>
                <h3>Don't have an account? <Link to="/signup">Sign up</Link></h3>
            </form>
        </div>
    )
}