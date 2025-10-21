import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider.jsx";
import logo from '../assets/logo.svg';
import bg from '../assets/bg.jpg';

export default function Signup() {
  const { signup } = useAuth();
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');    // <-- renamed
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('technician');
  const [err, setErr] = useState('');
  const nav = useNavigate();

  async function onSubmit(e) {
    e.preventDefault();
    setErr("");

    const u = username.trim();
    const mail = email.trim();

    if (!/^[a-zA-Z0-9_.-]{3,30}$/.test(u)) {
      setErr("Username must be 3-30 chars, letters, numbers, _.- allowed");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(mail)) {
      setErr("Please enter a valid email address.");
      return;
    }
    if (password.length < 8) {
      setErr("Password must be at least 8 characters long.");
      return;
    }

    try {
      // IMPORTANT: pass username first, then email
      await signup(u, mail, password, role);
      nav('/login');
    } catch (e) {
      setErr(e.response?.data?.msg || e.message || "Signup failed");
    }
  }

  return (
    <div className="form-container">
      <div className="buffer-pane">
        <img src={bg} alt="background" />
      </div>
      <form onSubmit={onSubmit}>
        <img src={logo} alt="preSense Logo" className="logo" />
        <div className="form-topic">
          <h2>Get Started Now</h2>
        </div>

        <div className="form-group">
          <label htmlFor="usernameInput">Username</label>
          <input
            id="usernameInput"
            type="text"
            placeholder="e.g., john_doe"
            value={username}
            onChange={e => setUsername(e.target.value)}
            required
          />
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

        <div className="form-group">
          <label htmlFor="roleSelect">Select your role</label>
          <select value={role} onChange={e => setRole(e.target.value)} id="roleSelect">
            <option value="manager">Manager</option>
            <option value="engineer">Engineer</option>
            <option value="technician">Technician</option>
          </select>
        </div>

        {err && <div className="error-msg">{err}</div>}
        <button type="submit" className="btn submit">Create account</button>
        <h3>Have an account? <Link to="/login">Log in</Link></h3>
      </form>
    </div>
  );
}
