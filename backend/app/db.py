from sqlalchemy import create_engine, text
import os
from processing import calculate_vibration_metrics
import numpy as np
from psycopg2 import extras

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

def get_user_by_id(user_id) -> dict | None:
    with engine.connect() as conn:
        r = conn.execute(text(
             "SELECT id, username, email, password_hash, role, organization FROM users WHERE id = :user_id"
        ), {"user_id": user_id})
        row = r.fetchone()
        if row is None:
            return None
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

# --- Sensor Device related DB operations ---
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

def row_to_dict(row):
    d = dict(row)
    # Serialize datetime objects to ISO format string
    if 'created_at' in d and d['created_at']:
        d['created_at'] = d['created_at'].isoformat()
    if 'expires_at' in d and d['expires_at']:
        d['expires_at'] = d['expires_at'].isoformat()
    return d

def get_user_devices(user_id) -> list[dict]:
    with engine.connect() as conn:
        r = conn.execute(text(
            "SELECT id, device_mac, os_version, created_at, device_name, asset_id FROM devices WHERE user_id = :user_id"
        ), {"user_id": user_id}).mappings().all()
        return [row_to_dict(row) for row in r]

# --- Asset related DB operations ---
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

def get_organization_assets(organization) -> list[dict]:
    with engine.connect() as conn:
        r = conn.execute(text(
            "SELECT id, name, max_rpm, power, organization, created_at FROM assets WHERE organization = :organization"
        ), {"organization": organization}).mappings().all()
        return [row_to_dict(row) for row in r]

def get_asset_details(asset_id) -> dict:
    with engine.connect() as conn:
        r = conn.execute(text(
            "SELECT id, name, max_rpm, power, organization, created_at FROM assets WHERE id = :asset_id"
        ), {"asset_id": asset_id}).mappings().first()
        if r is None:
            return {}
        return row_to_dict(r)

def link_asset_to_device(asset_id, device_mac):
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE devices SET asset_id = :asset_id WHERE device_mac = :device_mac"
        ), {
            "asset_id": asset_id,
            "device_mac": device_mac
        })

# --- Sensor data related DB operations ---
def insert_sensor_data(time, device_mac, asset_id, x, y, z):
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO sensor_data (time, device_mac, asset_id, accel_x, accel_y, accel_z) VALUES (:time, :device_mac, :asset_id, :x, :y, :z)"
        ), {
            "time": time,
            "device_mac": device_mac,
            "asset_id": asset_id,
            "x": x,
            "y": y,
            "z": z
        })

def insert_sensor_data_bulk(data_list):
    """
    data_list: A list of tuples [(time, mac, asset_id, ax, ay, az), ...]
    """
    conn = engine.raw_connection()
    try:
        with conn.cursor() as cur:
            # This is the magic: it builds one giant INSERT statement
            query = """
                INSERT INTO sensor_data (time, device_mac, asset_id, accel_x, accel_y, accel_z)
                VALUES %s
            """
            extras.execute_values(cur, query, data_list)
            conn.commit()
    except Exception as e:
        print(f"Bulk insert error: {e}")
        conn.rollback()
    finally:
        conn.close()


def insert_sensor_metrics(time, asset_id, rms_x, rms_y, rms_total, rms_z, peak_to_peak_z, dominant_freq_x, dominant_freq_y, dominant_freq_z, condition_score=0, diagnosis="Healthy"):
    with engine.begin() as conn:
        conn.execute(text(
            """INSERT INTO asset_health_metrics 
               (time, asset_id, rms_x, rms_y, rms_total, rms_z, dom_freq_x, dom_freq_y, dom_freq_z, peak_to_peak_z, condition_score, diagnosis) 
               VALUES (:time, :asset_id, :rms_x, :rms_y, :rms_total, :rms_z, :dominant_freq_x, :dominant_freq_y, :dominant_freq_z, :peak_to_peak_z, :condition_score, :diagnosis)"""
        ), {
            "time": time,
            "asset_id": asset_id,
            "rms_x": rms_x,
            "rms_y": rms_y,
            "rms_z": rms_z,
            "rms_total": rms_total,
            "dominant_freq_x": dominant_freq_x,
            "dominant_freq_y": dominant_freq_y,
            "dominant_freq_z": dominant_freq_z,
            "peak_to_peak_z": peak_to_peak_z,
            "condition_score": condition_score,
            "diagnosis": diagnosis
        })

def get_asset_spectrum(asset_id: int, limit: int = 500):
    query = text("""
        SELECT accel_x, accel_y, accel_z 
        FROM sensor_data 
        WHERE asset_id = :asset_id 
        ORDER BY time DESC 
        LIMIT :limit
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"asset_id": asset_id, "limit": limit}).fetchall()
    
    if not result:
        return {"error": "No data found"}

    # Separate X, Y, Z for individual analysis
    x_samples = [r[0] for r in result]
    y_samples = [r[1] for r in result]
    z_samples = [r[2] for r in result]

    # Process the X-axis (as an example)
    # IMPORTANT: Ensure 'sampling_rate' matches your ESP32 code!
    metrics_x = calculate_vibration_metrics(x_samples, sampling_rate=200)
    metrics_y = calculate_vibration_metrics(y_samples, sampling_rate=200)
    metrics_z = calculate_vibration_metrics(z_samples, sampling_rate=200)
    return {
        "asset_id": asset_id,
        "metrics": {
            "x": metrics_x,
            "y": metrics_y,
            "z": metrics_z
        }
    }

def get_asset_health(asset_id: int, limit: int = 50):
    query = text("""
        SELECT time, rms_x, rms_y, rms_z, rms_total, dom_freq_x, peak_to_peak_z, condition_score
        FROM asset_health_metrics 
        WHERE asset_id = :asset_id 
        ORDER BY time DESC 
        LIMIT :limit
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"asset_id": asset_id, "limit": limit}).fetchall()
    
    if not result:
        return {"history": []}

    history = []
    for r in reversed(result):
        history.append({
            "time": r[0].isoformat(),
            "rms_x": float(r[1]),
            "rms_y": float(r[2]),
            "rms_z": float(r[3]),
            "rms_total": float(r[4]), # ADD THIS
            "dom_freq": float(r[5]),
            "peak_to_peak": float(r[6]),
            "score": int(r[7]) 
        })
    return {"history": history}



def calculate_and_set_baseline(asset_id: int):
    # Fetch total along with individual axes
    query = text("""
        SELECT rms_x, rms_y, rms_z, rms_total, dom_freq_x, dom_freq_y, dom_freq_z
        FROM asset_health_metrics 
        WHERE asset_id = :asset_id AND condition_score = 0
        ORDER BY time DESC LIMIT 100
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query, {"asset_id": asset_id}).fetchall()
        
        if len(result) < 10:
            return {"error": "Need at least 10 healthy samples."}

        data = np.array(result)
        means = np.mean(data, axis=0)
        stds = np.std(data, axis=0)

        upsert_query = text("""
            INSERT INTO asset_baselines 
                (asset_id, mean_rms_x, std_rms_x, mean_rms_y, std_rms_y, 
                 mean_rms_z, std_rms_z, mean_rms_total, std_rms_total,
                 mean_dom_freq_x, std_dom_freq_x, mean_dom_freq_y, std_dom_freq_y,
                 mean_dom_freq_z, std_dom_freq_z, calibrated_at)
            VALUES 
                (:id, :mx, :sx, :my, :sy, :mz, :sz, :mt, :st, 
                 :mdfx, :sdfx, :mdfy, :sdfy, :mdfz, :sdfz, CURRENT_TIMESTAMP)
            ON CONFLICT (asset_id) DO UPDATE SET
                mean_rms_total = EXCLUDED.mean_rms_total,
                std_rms_total = EXCLUDED.std_rms_total,
                mean_dom_freq_x = EXCLUDED.mean_dom_freq_x,
                std_dom_freq_x = EXCLUDED.std_dom_freq_x,
                mean_dom_freq_y = EXCLUDED.mean_dom_freq_y,
                std_dom_freq_y = EXCLUDED.std_dom_freq_y,
                mean_dom_freq_z = EXCLUDED.mean_dom_freq_z,
                std_dom_freq_z = EXCLUDED.std_dom_freq_z,
                calibrated_at = EXCLUDED.calibrated_at
        """)
        
        # means/stds indices:
        # 0: rms_x, 1: rms_y, 2: rms_z, 3: rms_total, 4: dom_freq_x, 5: dom_freq_y, 6: dom_freq_z
        
        conn.execute(upsert_query, {
            "id": asset_id,
            "mx": float(means[0]), "sx": float(stds[0]),
            "my": float(means[1]), "sy": float(stds[1]),
            "mz": float(means[2]), "sz": float(stds[2]),
            "mt": float(means[3]), "st": float(stds[3]),
            "mdfx": float(means[4]), "sdfx": float(stds[4]),
            "mdfy": float(means[5]), "sdfy": float(stds[5]),
            "mdfz": float(means[6]), "sdfz": float(stds[6])
        })
        conn.commit()
    
    return {"msg": "Baseline calculated and set successfully."}

def get_asset_baseline(asset_id: int):
    query = text("SELECT * FROM asset_baselines WHERE asset_id = :asset_id")
    with engine.connect() as conn:
        row = conn.execute(query, {"asset_id": asset_id}).fetchone()
        if not row:
            return None
        # Convert row to dict (handle SQLAlchemy Row object)
        return dict(row._mapping)
    
# --- Event related DB operations ---
def get_active_event(asset_id: int):
    query = text("""
        SELECT id, severity FROM asset_events 
        WHERE asset_id = :asset_id AND end_time IS NULL
        LIMIT 1
    """)
    with engine.connect() as conn:
        return conn.execute(query, {"asset_id": asset_id}).fetchone()

def create_event(asset_id, severity, diagnosis, z_score):
    query = text("""
        INSERT INTO asset_events (asset_id, start_time, severity, initial_diagnosis, max_z_score)
        VALUES (:id, CURRENT_TIMESTAMP, :sev, :diag, :z)
    """)
    with engine.connect() as conn:
        conn.execute(query, {"id": asset_id, "sev": severity, "diag": diagnosis, "z": z_score})
        conn.commit()

def close_event(event_id):
    query = text("UPDATE asset_events SET end_time = CURRENT_TIMESTAMP WHERE id = :id")
    with engine.connect() as conn:
        conn.execute(query, {"id": event_id})
        conn.commit()

def get_recent_alerts():
    query = text("""
        SELECT e.*, a.name as asset_name 
        FROM asset_events e
        JOIN assets a ON e.asset_id = a.id
        ORDER BY e.start_time DESC
        LIMIT 20
    """)
    with engine.connect() as conn:
        result = conn.execute(query).fetchall()
        # Return list of dicts. The route handler in main.py will json-enocde it.
        return [dict(row._mapping) for row in result]