import os
from passlib.hash import bcrypt
from datetime import timedelta
from flask_jwt_extended import create_access_token, create_refresh_token, decode_token
from datetime import datetime, timezone, timedelta

JWT_ACCESS_EXPIRES = int(os.getenv("JWT_ACCESS_EXPIRES_SEC", 900)) # default 15 minutes
JWT_REFRESH_EXPIRES = int(os.getenv("JWT_REFRESH_EXPIRES_SEC", 60*60*24*7)) # default 7 days

def hash_password(password) -> str:
    """
    Hash a password using passlib bcrypt backend, but guard against
    passwords longer than bcrypt's 72-byte limit.
    """
    if password is None:
        raise ValueError("Password is required")
    if not isinstance(password, str):
        # do not log raw password values
        raise ValueError("Password must be a string")
    pw_bytes = password.encode("utf-8")
    if len(pw_bytes) > 72:
        # return a helpful error; don't auto-truncate silently
        raise ValueError("Password too long (more than 72 bytes). Please use a shorter password.")
    # now it's safe to hash
    return bcrypt.hash(password)

def verify_password(plaintext, hashed):
    return bcrypt.verify(plaintext, hashed)

def build_tokens(identity_claims: dict):
    '''
    identity_claims must contain: {"user_id": int, "email": str, "username": str, "role": str}
    Returns: (access, refresh, jti, expires_at)
    '''
    # Make identity a string (user id)
    identity_str = str(identity_claims.get("user_id"))
    additional = {
        "email": identity_claims.get("email"),
        "role": identity_claims.get("role"),
        "username": identity_claims.get("username")
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
    