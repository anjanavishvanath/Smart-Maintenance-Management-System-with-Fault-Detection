import os
import re
from passlib.hash import bcrypt
from datetime import datetime, timedelta, timezone
from flask_jwt_extended import create_access_token, create_refresh_token, decode_token

JWT_ACCESS_EXPIRES = int(os.getenv("JWT_ACCESS_EXPIRES_SEC", 900)) # default 15 minutes default
JWT_REFRESH_EXPIRES = int(os.getenv("JWT_REFRESH_EXPIRES_SEC", 60*60*24*7)) # default 7 days

# Password complexity policy: >=8 chars, with upper, lower, digit, and symbol.
PASSWORD_MIN_LENGTH = 8
_RE_UPPER = re.compile(r"[A-Z]")
_RE_LOWER = re.compile(r"[a-z]")
_RE_DIGIT = re.compile(r"\d")
_RE_SYMBOL = re.compile(r"[^A-Za-z0-9]")


def validate_password_strength(password) -> str | None:
    """Return None if password passes the complexity policy, else a human-readable error string."""
    if password is None or not isinstance(password, str):
        return "Password is required"
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"
    if not _RE_UPPER.search(password):
        return "Password must contain at least one uppercase letter"
    if not _RE_LOWER.search(password):
        return "Password must contain at least one lowercase letter"
    if not _RE_DIGIT.search(password):
        return "Password must contain at least one digit"
    if not _RE_SYMBOL.search(password):
        return "Password must contain at least one symbol (e.g. !@#$%)"
    return None


def hash_password(password) -> str:
    '''
        Hash a password using passlib bcrypt backend, but guard against
        passwords longer than bcrypt's 72-byte limit.
    '''
    if password is None:
        raise ValueError("Password is required")
    if not isinstance(password, str): #enforce str type for hashing
        raise ValueError("Password must be a string")
    pw_bytes = password.encode('utf-8')
    if len(pw_bytes) > 72:
        raise ValueError("Password too long (max 72 bytes)")
    return bcrypt.hash(password)

def verify_password(plaintext, hashed) -> bool:
    return bcrypt.verify(plaintext, hashed)
    
def build_tokens(identity_claims: dict):
    '''
    identity_claims must contain: {"user_id": int, "email": str, "username": str, "role": str, "organization": str or None, "user_id": int}
    Returns: (access, refresh, jti, expires_at)
    '''
    identity_str = str(identity_claims.get("user_id"))
    additional = {
        "username": identity_claims.get("username"),
        "email": identity_claims.get("email"),
        "role": identity_claims.get("role"),
        "organization": identity_claims.get("organization")
    }
    access = create_access_token(identity=identity_str, additional_claims=additional,
                                 expires_delta=timedelta(seconds=JWT_ACCESS_EXPIRES))
    refresh = create_refresh_token(identity=identity_str, additional_claims=additional,
                                   expires_delta=timedelta(seconds=JWT_REFRESH_EXPIRES))
    decoded = decode_token(refresh)
    jti = decoded.get("jti")
    exp = decoded.get("exp")
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    return access, refresh, jti, expires_at