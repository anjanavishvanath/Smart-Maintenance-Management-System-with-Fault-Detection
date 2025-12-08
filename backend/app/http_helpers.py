from flask import jsonify, request
from db import insert_user, get_user_by_email, insert_refresh_token, revoke_refresh_token, is_refresh_token_revoked
from auth import hash_password, verify_password, build_tokens
from flask_jwt_extended import get_jwt_identity, get_jwt, create_access_token

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
    user = get_user_by_email(email)
    if not user:
        return jsonify({"error": "Invalid email or password"}), 401
    user_id = user.get("id")
    username = user.get("username")
    email = user.get("email")
    password_hash = user.get("password_hash")
    role = user.get("role")
    organization = user.get("organization")
    if not verify_password(password, password_hash):
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
    return jsonify({
        "access_token": access,
        "refresh_token": refresh
    }), 200

def refresh() -> tuple:  #called with refresh token in Authorization header or cookie
    identity = get_jwt_identity()
    claims = get_jwt()
    jti = claims.get("jti")
    # if token (jti) is revoked, reject
    if is_refresh_token_revoked(jti):
        return jsonify({"message": "Token has been revoked"}), 401
    # build new tokens using identity claims
    additional = {k: claims.get(k) for k in ("email", "role", "username", "organization") if claims.get(k) is not None}
    access = create_access_token(identity=identity, additional_claims=additional)
    return jsonify({"access_token": access}), 200

def logout() -> tuple:
    claims = get_jwt()
    jti = claims.get("jti")
    # mark jti as revoked in DB
    revoke_refresh_token(jti)
    return jsonify({"message": "Logged out"}), 200