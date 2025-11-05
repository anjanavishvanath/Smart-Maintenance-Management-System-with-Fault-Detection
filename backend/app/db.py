# sqlAlchemy helpers for DB access
import os
import base64
import json
from cryptography.fernet import Fernet
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://cm_user:cm_pass@timescaledb:5432/cm_db')

engine = create_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)

# --- Users ---
def get_user_by_email(email):
    with engine.connect() as conn:
        r = conn.execute(text(
            "SELECT id, username, email, password_hash, role FROM users WHERE email = :email"
        ), {"email": email})
        row = r.fetchone()
        if row is None:
            return None
        # convert Row to plain dict to avoid positional index confusion
        return dict(row)

def insert_user(username, email, password_hash, role="technician"):
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO users (username, email, password_hash, role)
                VALUES (:username, :email, :password_hash, :role)
            """),
            {
                "username": username,
                "email": email,
                "password_hash": password_hash,
                "role": role
            }
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

# --- Device credentials ---
DEVICE_SECRET_KEY = os.getenv("DEVICE_SECRET_KEY")
if not DEVICE_SECRET_KEY:
    # For dev only: generate ephemeral key (DO NOT do in prod)
    # raise RuntimeError("DEVICE_SECRET_KEY not set")
    DEVICE_SECRET_KEY = Fernet.generate_key().decode()

fernet = Fernet(DEVICE_SECRET_KEY.encode())

def encrypt_password(plain_text: str) -> str:
    return fernet.encrypt(plain_text.encode()).decode()

def decrypt_password(enc_text: str) -> str:
    return fernet.decrypt(enc_text.encode()).decode()

# --- Devices helpers (add)
def get_device_by_device_id(device_id):
    with engine.connect() as conn:
        r = conn.execute(text("SELECT * FROM devices WHERE device_id = :device_id"), {"device_id": device_id})
        row = r.fetchone()
        return dict(row) if row else None
    
def insert_device(device_id, name=None, asset_id=None, config=None, created_by=None):
    """
    Insert device row. If device already exists, do nothing.
    created_by: integer user id who created/provisioned this device (nullable)
    """
    cfg_json = json.dumps(config or {})
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO devices (device_id, name, asset_id, config, status, last_seen, created_by)
            VALUES (:device_id, :name, :asset_id, :config, :status, :last_seen, :created_by)
            ON CONFLICT (device_id) DO NOTHING
        """), {
            "device_id": device_id,
            "name": name,
            "asset_id": asset_id,
            "config": cfg_json,
            "status": "offline",
            "last_seen": None,
            "created_by": created_by
        })

def get_all_devices(limit=100, user_id=None):
    """
    Return list of devices. If user_id is provided, only returns devices created_by that user.
    """
    with engine.connect() as conn:
        if user_id is not None:
            r = conn.execute(text("""
                SELECT device_id, name, status, last_seen, config
                FROM devices
                WHERE created_by = :user_id
                ORDER BY created_at DESC
                LIMIT :limit
            """), {"user_id": user_id, "limit": limit})
        else:
            r = conn.execute(text("""
                SELECT device_id, name, status, last_seen, config
                FROM devices
                ORDER BY created_at DESC
                LIMIT :limit
            """), {"limit": limit})
        rows = r.fetchall()

    results = []
    for row in rows:
        cfg = row["config"]
        try:
            cfg_parsed = json.loads(cfg) if cfg and isinstance(cfg, str) else cfg
        except Exception:
            cfg_parsed = cfg
        results.append({
            "device_id": row["device_id"],
            "name": row["name"],
            "status": row["status"],
            "last_seen": row["last_seen"].isoformat() if row["last_seen"] else None,
            "config": cfg_parsed
        })
    return results

    

# --- Credentials
def insert_device_credentials(device_id, username, password_plain, expires_at=None):
    enc = encrypt_password(password_plain)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO device_credentials (device_id, username, password_enc, active, expires_at)
            VALUES (:device_id, :username, :password_enc, TRUE, :expires_at)
        """), {
            "device_id": device_id,
            "username": username,
            "password_enc": enc,
            "expires_at": expires_at
        })

def get_active_credentials_for_device(device_id):
    with engine.connect() as conn:
        r = conn.execute(text("""
            SELECT username, password_enc, expires_at FROM device_credentials
            WHERE device_id = :device_id AND active = TRUE
            ORDER BY created_at DESC LIMIT 1
        """), {"device_id": device_id})
        row = r.fetchone()
        if not row:
            return None
        username, password_enc, expires_at = row
        return {"username": username, "password": decrypt_password(password_enc), "expires_at": expires_at}

def revoke_credentials(username):
    with engine.begin() as conn:
        conn.execute(text("UPDATE device_credentials SET active = FALSE WHERE username = :username"),
                     {"username": username})
        
#  --- vibration readings ---
def insert_reading(time_ts, device_id, ax, ay, az, sample_rate=None, meta=None):
    '''
        Insert single reaiding row into readings hypertable
        time_ts: datetime (tz-aware UTC) or UNIX ms int
        meta: dict or JSON serializable object
    '''

    #  normalize time to timestamptz
    if isinstance(time_ts, (int, float)):
        # assume milliseconds
        ts = datetime.fromtimestamp(float(time_ts) / 1000.0, tz=timezone.utc)
    elif isinstance(time_ts, datetime):
        ts = time_ts
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    else:
        # fallback to currrent time UTC
        ts = datetime.now(tz=timezone.utc)

    meta_json = json.dumps(meta) if meta is not None else None

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO readings (time, device_id, ax, ay, az, sample_rate, meta)
                VALUES (:time, :device_id, :ax, :ay, :az, :sample_rate, :meta)
            """),
            {
                "time": ts,
                "device_id": device_id,
                "ax": ax,
                "ay": ay,
                "az": az,
                "sample_rate": sample_rate,
                "meta": meta_json
            },
        )

def get_recent_readings(device_id, limit=100):
    """Return up to `limit` recent readings for device_id as list of dicts (newest first)."""
    with engine.connect() as conn:
        r = conn.execute(text("""
            SELECT time, device_id, ax, ay, az, sample_rate, meta
            FROM readings
            WHERE device_id = :device_id
            ORDER BY time DESC
            LIMIT :limit
        """), {"device_id": device_id, "limit": limit})
        rows = r.fetchall()
    results = []
    for row in rows:
        # row might be a Row object; convert to dict-like
        meta = row["meta"]
        try:
            meta_parsed = json.loads(meta) if meta else None
        except Exception:
            meta_parsed = meta
        results.append({
            "time": row["time"].isoformat() if row["time"] is not None else None,
            "device_id": row["device_id"],
            "ax": row["ax"],
            "ay": row["ay"],
            "az": row["az"],
            "sample_rate": row["sample_rate"],
            "meta": meta_parsed
        })
    return results