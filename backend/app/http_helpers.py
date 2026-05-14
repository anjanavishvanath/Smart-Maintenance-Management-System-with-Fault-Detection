import logging
from datetime import datetime, timezone
from flask import jsonify, request

logger = logging.getLogger(__name__)
from db import (
    insert_user,
    get_user_by_email,
    get_user_by_id,
    insert_refresh_token,
    revoke_refresh_token,
    is_refresh_token_revoked,
    update_user_password,
    revoke_jti,
    write_audit_log,
)
from auth import hash_password, verify_password, build_tokens, validate_password_strength
from flask_jwt_extended import get_jwt_identity, get_jwt, create_access_token, decode_token

def signup() -> tuple:
    data = request.get_json() or {}
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    role = data.get("role", "technician")  # Default role is 'technician' if not provided
    organization = data.get("organization", None)
    # Basic validation
    if not username:
        return jsonify({"error": "Username is required"}), 400
    if not email:
        return jsonify({"error": "Email is required"}), 400
    if not password:
        return jsonify({"error": "Password is required"}), 400
    pw_problem = validate_password_strength(password)
    if pw_problem:
        return jsonify({"error": pw_problem}), 400
    if get_user_by_email(email):
        return jsonify({"error": "Email already registered"}), 400
    # Hash password and inset user
    try:
        pw_hash = hash_password(password)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    insert_user(username, email, pw_hash, role, organization)
    return jsonify({"message": "User registered successfully"}), 201

def login() -> tuple:
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400
    ip = request.remote_addr
    user = get_user_by_email(email)
    if not user:
        write_audit_log(
            action="auth.login.failure", entity="user",
            metadata={"email": email, "reason": "unknown_email", "ip": ip},
        )
        return jsonify({"error": "Invalid email or password"}), 401
    user_id = user.get("id")
    username = user.get("username")
    email = user.get("email")
    password_hash = user.get("password_hash")
    role = user.get("role")
    organization = user.get("organization")
    if not verify_password(password, password_hash):
        write_audit_log(
            user_id=user_id, organization=organization,
            action="auth.login.failure", entity="user", entity_id=user_id,
            metadata={"reason": "bad_password", "ip": ip},
        )
        return jsonify({"error": "Invalid email or password"}), 401
    identity = {
        "user_id": user_id,
        "username": username,
        "email": email,
        "role": role,
        "organization": organization
    }
    # tokens
    access, refresh, jti, expires_at = build_tokens(identity)
    # Store refresh token jti in DB for revocation check
    insert_refresh_token(jti, user_id, expires_at)
    write_audit_log(
        user_id=user_id, organization=organization,
        action="auth.login.success", entity="user", entity_id=user_id,
        metadata={"ip": ip},
    )
    return jsonify({
        "access_token": access,
        "refresh_token": refresh
    }), 200

def refresh() -> tuple:
    """
    Rotate the refresh token: issue a new access + refresh pair AND invalidate the
    old refresh token. This means a leaked refresh token is single-use — once the
    legitimate client exchanges it, the attacker's copy is dead.
    """
    identity_str = get_jwt_identity()
    claims = get_jwt()
    old_jti = claims.get("jti")

    # Defense-in-depth: the JWT blocklist loader already rejects revoked tokens
    # before this function runs. Keep this explicit check too — cheap and clear.
    if is_refresh_token_revoked(old_jti):
        return jsonify({"error": "Token has been revoked"}), 401

    identity_claims = {
        "user_id": int(identity_str),
        "username": claims.get("username"),
        "email": claims.get("email"),
        "role": claims.get("role"),
        "organization": claims.get("organization"),
    }
    new_access, new_refresh, new_jti, new_exp = build_tokens(identity_claims)

    # Persist the new refresh token, then revoke the old one + add it to the blocklist.
    insert_refresh_token(new_jti, int(identity_str), new_exp)
    revoke_refresh_token(old_jti)
    old_exp = datetime.fromtimestamp(claims.get("exp", 0), tz=timezone.utc)
    revoke_jti(old_jti, old_exp)

    return jsonify({"access_token": new_access, "refresh_token": new_refresh}), 200


def logout() -> tuple:
    """
    Revoke the JWT used for this request (works with either access or refresh thanks
    to verify_type=False on the route). Optionally also revokes a paired refresh
    token sent in the body, so a single logout call kills both halves of the pair.
    """
    claims = get_jwt() or {}
    primary_jti = claims.get("jti")
    primary_type = claims.get("type", "access")

    if primary_jti:
        primary_exp = datetime.fromtimestamp(claims.get("exp", 0), tz=timezone.utc)
        revoke_jti(primary_jti, primary_exp)
        if primary_type == "refresh":
            revoke_refresh_token(primary_jti)

    body = request.get_json(silent=True) or {}
    paired = body.get("refresh_token") or body.get("access_token")
    if paired:
        try:
            decoded = decode_token(paired)
            paired_jti = decoded.get("jti")
            if paired_jti and paired_jti != primary_jti:
                paired_exp = datetime.fromtimestamp(decoded.get("exp", 0), tz=timezone.utc)
                revoke_jti(paired_jti, paired_exp)
                if decoded.get("type") == "refresh":
                    revoke_refresh_token(paired_jti)
        except Exception as e:
            # An expired or malformed paired token isn't fatal; we've still revoked the primary.
            logger.warning("Failed to decode paired token on logout: %s", e)

    return jsonify({"message": "Logged out"}), 200


def change_password() -> tuple:
    """
    Change the caller's password. Requires the current password for verification.
    Body: { "current_password": "...", "new_password": "..." }
    """
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}
    current_password = data.get("current_password")
    new_password = data.get("new_password")

    if not current_password or not new_password:
        return jsonify({"error": "current_password and new_password are required"}), 400
    pw_problem = validate_password_strength(new_password)
    if pw_problem:
        return jsonify({"error": pw_problem}), 400
    if current_password == new_password:
        return jsonify({"error": "New password must differ from the current password"}), 400

    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    if not verify_password(current_password, user["password_hash"]):
        return jsonify({"error": "Current password is incorrect"}), 401

    try:
        new_hash = hash_password(new_password)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if not update_user_password(user_id, new_hash):
        return jsonify({"error": "Failed to update password"}), 500
    write_audit_log(
        user_id=user_id, organization=user.get("organization"),
        action="auth.password_change", entity="user", entity_id=user_id,
        metadata={"ip": request.remote_addr},
    )
    return jsonify({"message": "Password updated successfully"}), 200