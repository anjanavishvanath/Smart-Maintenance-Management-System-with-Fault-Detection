import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "react-toastify";
import { useAuth } from "../auth/AuthProvider";
import { validatePasswordStrength, PASSWORD_HINT } from "../utils/passwordPolicy";
import api from "../api";

export default function SettingsPage() {
    const { user } = useAuth();
    const [currentPassword, setCurrentPassword] = useState("");
    const [newPassword, setNewPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [err, setErr] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);

    const handleChangePassword = async (e) => {
        e.preventDefault();
        setErr("");

        const pwProblem = validatePasswordStrength(newPassword);
        if (pwProblem) {
            setErr(pwProblem);
            return;
        }
        if (newPassword !== confirmPassword) {
            setErr("New password and confirmation do not match.");
            return;
        }
        if (newPassword === currentPassword) {
            setErr("New password must differ from your current password.");
            return;
        }

        setIsSubmitting(true);
        try {
            await api.post("/auth/change-password", {
                current_password: currentPassword,
                new_password: newPassword,
            });
            toast.success("Password updated successfully.");
            setCurrentPassword("");
            setNewPassword("");
            setConfirmPassword("");
        } catch (e) {
            const msg = e.response?.data?.error || e.response?.data?.msg || "Failed to update password";
            setErr(msg);
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h1>Settings</h1>
                <Link to="/dashboard" className="btn">Back to Dashboard</Link>
            </div>

            <section className="card" style={{ maxWidth: '500px', padding: '1.5rem' }}>
                <h2>Profile</h2>
                <p><span className="text-highlight">Username:</span> {user?.username}</p>
                <p><span className="text-highlight">Email:</span> {user?.email}</p>
                <p><span className="text-highlight">Role:</span> {user?.role}</p>
                <p><span className="text-highlight">Organization:</span> {user?.organization}</p>
            </section>

            <section className="card" style={{ maxWidth: '500px', padding: '1.5rem', marginTop: '1.5rem' }}>
                <h2>Change Password</h2>
                <form onSubmit={handleChangePassword}>
                    <div className="form-group">
                        <label htmlFor="currentPw">Current Password</label>
                        <input
                            id="currentPw"
                            type="password"
                            value={currentPassword}
                            onChange={(e) => setCurrentPassword(e.target.value)}
                            required
                            autoComplete="current-password"
                        />
                    </div>
                    <div className="form-group">
                        <label htmlFor="newPw">New Password</label>
                        <input
                            id="newPw"
                            type="password"
                            value={newPassword}
                            onChange={(e) => setNewPassword(e.target.value)}
                            required
                            minLength={8}
                            autoComplete="new-password"
                        />
                        <small className="text-muted">{PASSWORD_HINT}</small>
                    </div>
                    <div className="form-group">
                        <label htmlFor="confirmPw">Confirm New Password</label>
                        <input
                            id="confirmPw"
                            type="password"
                            value={confirmPassword}
                            onChange={(e) => setConfirmPassword(e.target.value)}
                            required
                            minLength={8}
                            autoComplete="new-password"
                        />
                    </div>
                    {err && <div className="error-msg">{err}</div>}
                    <button
                        type="submit"
                        className="btn btn-primary"
                        disabled={isSubmitting}
                        style={{ marginTop: '1rem' }}
                    >
                        {isSubmitting ? "Updating..." : "Update Password"}
                    </button>
                </form>
            </section>
        </div>
    );
}
