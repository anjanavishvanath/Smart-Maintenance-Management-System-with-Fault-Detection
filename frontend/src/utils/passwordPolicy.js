// Mirrors the backend policy in auth.py:validate_password_strength.
// Returns null if password is valid, otherwise a human-readable error string.

const MIN_LENGTH = 8;

export function validatePasswordStrength(password) {
    if (typeof password !== "string" || password.length === 0) {
        return "Password is required";
    }
    if (password.length < MIN_LENGTH) {
        return `Password must be at least ${MIN_LENGTH} characters long`;
    }
    if (!/[A-Z]/.test(password)) {
        return "Password must contain at least one uppercase letter";
    }
    if (!/[a-z]/.test(password)) {
        return "Password must contain at least one lowercase letter";
    }
    if (!/\d/.test(password)) {
        return "Password must contain at least one digit";
    }
    if (!/[^A-Za-z0-9]/.test(password)) {
        return "Password must contain at least one symbol (e.g. !@#$%)";
    }
    return null;
}

export const PASSWORD_HINT =
    "At least 8 characters with uppercase, lowercase, a digit, and a symbol.";
