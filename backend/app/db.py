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
    
def insert_provisioning_token(slpt_value, user_id, enrollment_id, expires_at):
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO provisioning_tokens (slpt_value, user_id, enrollment_id, expires_at) VALUES (:slpt_value, :user_id, :enrollment_id, :expires_at)"
        ), {
            "slpt_value": slpt_value, 
            "user_id": user_id, 
            "enrollment_id": enrollment_id, 
            "expires_at": expires_at
            })
        
def get_provisioning_token(slpt_value) -> dict | None:
    with engine.connect() as conn:
        # fetch token, associated user, enrollment_id, and expiry
        r = conn.execute(text(
            "SELECT user_id, enrollment_id, expires_at, is_used FROM provisioning_tokens WHERE slpt_value = :slpt"
        ), {"slpt": slpt_value}).mappings().first()
        if r is None:
            return None
        return dict(r)
    
def activate_device_in_db(mac, user_id, mqtt_pass, os_version):
    with engine.begin() as conn:
        # Creating permanent device record
        conn.execute(text(
            "INSERT INTO devices (device_mac, user_id, mqtt_password, os_version) VALUES (:mac, :user_id, :mqtt_pass, :os_version) "
            "ON CONFLICT (device_mac) DO UPDATE SET mqtt_password = :pass"
        ), {
            "mac": mac,
            "user_id": user_id,
            "mqtt_pass": mqtt_pass,
            "pass": mqtt_pass,
            "os_version": os_version
        })
        # mark the provisioning token as used
        conn.execute(text(
            "UPDATE provisioning_tokens SET is_used = TRUE WHERE enrollment_id = :mac"
        ), {"mac": mac})

def insert_asset(name, max_rpm, power, organization, user_id):
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO assets (name, max_rpm, power, organization, user_id) VALUES (:name, :max_rpm, :power, :organization, :user_id)"
        ), {
            "name": name,
            "max_rpm": max_rpm,
            "power": power,
            "organization": organization,
            "user_id": user_id
        })