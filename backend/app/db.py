# sqlAlchemy helpers for DB access
import os
import time
import base64
import json
from typing import Optional
from cryptography.fernet import Fernet
from datetime import datetime, timedelta, timezone
import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://cm_user:cm_pass@timescaledb:5432/cm_db')

engine = create_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)

def wait_for_db():
    max_retries = 10
    wait_seconds = 2
    print(f"[DB] Attempting to connect to {DATABASE_URL}", flush=True)
    for i in range(max_retries):
        try:
            # testing with a simple connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("[DB] Connection successful", flush=True)
            return
        except OperationalError as e:
            print(f"[DB] Connection failed (Attempt {i+1}/{max_retries}). Retrying in {wait_seconds}s...", flush=True)
            time.sleep(wait_seconds)
    print("[DB] Could not connect to database after multiple attempts. Exiting.", flush=True)
    exit(1)

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
def insert_metrics_bulk(readings_list: list):
    """
    Bulk-insert metrics. Uses ON CONFLICT DO UPDATE to avoid duplicate (time, device_id) primary key errors.
    readings_list: list of dicts with keys time (datetime), device_id, sample_rate, samples, metrics (json string or dict)
    """
    if not readings_list:
        return

    stmt = text("""
        INSERT INTO readings_parameters (time, device_id, sample_rate, samples, metrics)
        VALUES (:time, :device_id, :sample_rate, :samples, :metrics)
        ON CONFLICT (time, device_id)
        DO UPDATE SET
            sample_rate = COALESCE(EXCLUDED.sample_rate, readings_parameters.sample_rate),
            samples = COALESCE(EXCLUDED.samples, readings_parameters.samples),
            metrics = COALESCE(EXCLUDED.metrics, readings_parameters.metrics)
    """)
    with engine.begin() as conn:
        conn.execute(stmt, readings_list)

def get_recent_metrics(device_id, limit=100):
    """Return up to `limit` recent readings metrics for device_id as list of dicts (newest first)."""
    with engine.connect() as conn:
        r = conn.execute(text("""
            SELECT time, device_id, sample_rate, samples, metrics
            FROM readings_parameters
            WHERE device_id = :device_id
            ORDER BY time DESC
            LIMIT :limit
        """), {"device_id": device_id, "limit": limit})
        rows = r.fetchall() # Convert Result object to list of Row objects
    results = []
    for row in rows:
        # handle JSON deserialization safely
        raw_metrics = row.metrics # accessing by attribute is cleaner in newer SQLAlchemy
        # Check if it's already a dict (sqlalchemy does this sometimes) or needs parsing
        if isinstance(raw_metrics, str):
             try:
                metrics_parsed = json.loads(raw_metrics)
             except ValueError:
                metrics_parsed = {}
        else:
             metrics_parsed = raw_metrics
        results.append({
            "time": row.time.isoformat() if row.time else None,
            "device_id": row.device_id,
            "sample_rate": row.sample_rate,
            "samples": row.samples,
            "metrics": metrics_parsed
        })
    return results

# --- Raw blocks helpers ---
def insert_raw_block(block_id: str, device_id: str, time_ts_ms, sample_rate: int, samples: int,
                     encoding: str, payload_bytes: bytes, crc32: int | None = None):
    """
    Insert a raw block into raw_blocks table.
    payload_bytes: Python bytes (binary)
    time_ts_ms: milliseconds since epoch (int) or datetime
    """
    # normalize time
    if isinstance(time_ts_ms, (int, float)):
        ts = datetime.fromtimestamp(float(time_ts_ms) / 1000.0, tz=timezone.utc)
    elif isinstance(time_ts_ms, datetime):
        ts = time_ts_ms if time_ts_ms.tzinfo else time_ts_ms.replace(tzinfo=timezone.utc)
    else:
        ts = datetime.now(tz=timezone.utc)
    # Use raw connection to pass psycopg2.Binary for bytea <- turns out this is not nessesary
    # SQLAlchemy knows payload_bytes is type bytes and will map to bytea automatically
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO raw_blocks (time, device_id, block_id, sample_rate, samples, encoding, crc32, payload)
                VALUES (:time, :device_id, :block_id, :sample_rate, :samples, :encoding, :crc32, :payload)
                 """),
                 {
                    "time": ts,
                    "device_id": device_id,
                    "block_id": block_id,
                    "sample_rate": sample_rate,
                    "samples": samples,
                    "encoding": encoding,
                    "crc32": crc32,
                    "payload": payload_bytes
                 }
        ) 
    

# return metadata about recent raw blocks. Fetch payload itself separately if needed.
def get_recent_raw_blocks(device_id: str, limit: int = 20):
    with engine.connect() as conn:
        r = conn.execute(text("""
            SELECT time, device_id, block_id, sample_rate, samples, encoding, crc32, octet_length(payload) as payload_len
            FROM raw_blocks
            WHERE device_id = :device_id
            ORDER BY time DESC
            LIMIT :limit
        """), {"device_id": device_id, "limit": limit})
        rows = r.fetchall()
    results = []
    for row in rows:
        results.append({
            "block_id": row["block_id"],
            "device_id": row["device_id"],
            "time": row["time"].isoformat() if row["time"] else None,
            "sample_rate": row["sample_rate"],
            "samples": row["samples"],
            "encoding": row["encoding"],
            "crc32": row["crc32"],
            "payload_len": int(row["payload_len"]) if row["payload_len"] is not None else 0
        })
    return results