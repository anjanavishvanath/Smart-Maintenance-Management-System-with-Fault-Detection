from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://cm_user:cm_pass@timescaledb:5432/cm_db')

engine = create_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)

#  --- User-related DB operations ---
def insert_user(username, email, password_hash, role, organization):
    with engine.begin() as conn:
        conn.execute(text(
            """
                INSERT INTO users (username, email, password_hash, role, organization)
                VALUES (:username, :email, :password_hash, :role, :organization)
            """
        ), {
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "role": role,
            "organization": organization
        })

def get_user_by_email(email) -> dict | None:
    with engine.connect() as conn:
        r = conn.execute(text(
             "SELECT id, username, email, password_hash, role, organization FROM users WHERE email = :email"
        ), {"email": email})
        row = r.fetchone()
        if row is None:
            return None
        # Convert row to plain dictionary to avoid positional index confusion
        return dict(row._mapping)

# --- Token-related DB operations ---
def insert_refresh_token(jti, user_id, expires_at):
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO refresh_tokens (jti, user_id, expires_at) VALUES (:jti, :user_id, :expires_at)"
        ), {"jti": jti, "user_id": user_id, "expires_at": expires_at})

def revoke_refresh_token(jti):
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE refresh_tokens SET revoked = TRUE WHERE jti = :jti"
        ), {"jti": jti})

def is_refresh_token_revoked(jti) -> bool:
    with engine.connect() as conn:
        r = conn.execute(text(
            "SELECT revoked FROM refresh_tokens WHERE jti = :jti"
        ), {"jti": jti})
        row = r.fetchone()
        if row is None:
            return True  # treat missing token as revoked/invalid
        return bool(row[0])