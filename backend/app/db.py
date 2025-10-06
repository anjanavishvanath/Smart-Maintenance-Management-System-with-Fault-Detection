# sqlAlchemy helpers for DB access
import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://cm_user:cm_pass@timescaledb:5432/cm_db')

engine = create_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)

# --- Users ---
def get_user_by_email(email):
    with engine.connect() as conn:
        r = conn.execute(text("SELECT id, email, password_hash, role FROM users WHERE email = :email"), {"email": email})
        return r.fetchone()  # returns Row or None

def insert_user(email, password_hash, role="technician"):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO users (email, password_hash, role) VALUES (:email, :password_hash, :role)"),
            {"email": email, "password_hash": password_hash, "role": role}
        )

# --- Refresh tokens ---
def insert_refresh_token(jti, user_id, expires_at):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO refresh_tokens (jti, user_id, expires_at) VALUES (:jti, :user_id, :expires_at)"),
            {"jti": jti, "user_id": user_id, "expires_at": expires_at}
        )

def revoke_refresh_token(jti):
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE refresh_tokens SET revoked = TRUE WHERE jti = :jti"),
            {"jti": jti}
        )

def is_refresh_token_revoked(jti):
    with engine.connect() as conn:
        r = conn.execute(text("SELECT revoked FROM refresh_tokens WHERE jti = :jti"), {"jti": jti})
        row = r.fetchone()
        if row is None:
            return True  # treat missing token as revoked/invalid
        return bool(row[0])

