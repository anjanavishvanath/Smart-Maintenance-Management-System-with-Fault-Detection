from sqlalchemy import create_engine, text
import os
import json
import logging
from processing import calculate_vibration_metrics
import numpy as np
from psycopg2 import extras

logger = logging.getLogger(__name__)

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

# --- JWT blocklist (covers both access and refresh tokens) ---
def revoke_jti(jti: str, expires_at) -> None:
    """Add a JTI to the blocklist. Idempotent so calling twice is safe."""
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO revoked_tokens (jti, expires_at) VALUES (:jti, :exp) "
            "ON CONFLICT (jti) DO NOTHING"
        ), {"jti": jti, "exp": expires_at})

def is_jti_revoked(jti: str) -> bool:
    """Check whether a JTI is in the blocklist. Used by the JWT decoder."""
    if not jti:
        return True
    with engine.connect() as conn:
        r = conn.execute(text(
            "SELECT 1 FROM revoked_tokens WHERE jti = :jti"
        ), {"jti": jti}).fetchone()
        return r is not None

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
    for key in ("created_at", "expires_at", "last_seen"):
        if key in d and d[key]:
            d[key] = d[key].isoformat()
    return d

def get_user_devices(user_id) -> list[dict]:
    with engine.connect() as conn:
        r = conn.execute(text(
            "SELECT id, device_mac, os_version, created_at, device_name, asset_id, last_seen "
            "FROM devices WHERE user_id = :user_id"
        ), {"user_id": user_id}).mappings().all()
        return [row_to_dict(row) for row in r]

def update_device_last_seen(device_mac: str) -> None:
    """Stamp last_seen=now() for the given device. Called from the ingestor on every metrics batch."""
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE devices SET last_seen = CURRENT_TIMESTAMP WHERE device_mac = :mac"
        ), {"mac": device_mac})

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

def get_organization_assets(organization, *, limit: int = 100, offset: int = 0) -> list[dict]:
    """Paginated list of active assets in an organization."""
    limit = max(1, min(int(limit), 500))   # clamp 1..500
    offset = max(0, int(offset))
    with engine.connect() as conn:
        r = conn.execute(text(
            "SELECT id, name, max_rpm, power, organization, created_at "
            "FROM assets WHERE organization = :organization AND deleted_at IS NULL "
            "ORDER BY created_at DESC "
            "LIMIT :limit OFFSET :offset"
        ), {"organization": organization, "limit": limit, "offset": offset}).mappings().all()
        return [row_to_dict(row) for row in r]

def get_asset_details(asset_id) -> dict:
    with engine.connect() as conn:
        r = conn.execute(text(
            "SELECT id, name, max_rpm, power, organization, created_at "
            "FROM assets WHERE id = :asset_id AND deleted_at IS NULL"
        ), {"asset_id": asset_id}).mappings().first()
        if r is None:
            return {}
        return row_to_dict(r)

def update_asset(asset_id: int, organization: str, name: str, max_rpm, power) -> bool:
    """Update asset metadata. Org-scoped to block cross-tenant edits.
    Returns True if a row was updated (i.e. asset exists, is active, and belongs to the org)."""
    with engine.begin() as conn:
        result = conn.execute(text("""
            UPDATE assets
               SET name = :name, max_rpm = :max_rpm, power = :power
             WHERE id = :id AND organization = :org AND deleted_at IS NULL
        """), {"name": name, "max_rpm": max_rpm, "power": power, "id": asset_id, "org": organization})
        return result.rowcount > 0

def soft_delete_asset(asset_id: int, organization: str) -> bool:
    """Mark asset as deleted while preserving linked history. Org-scoped."""
    with engine.begin() as conn:
        result = conn.execute(text("""
            UPDATE assets
               SET deleted_at = CURRENT_TIMESTAMP
             WHERE id = :id AND organization = :org AND deleted_at IS NULL
        """), {"id": asset_id, "org": organization})
        return result.rowcount > 0

def link_asset_to_device(asset_id, device_mac):
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE devices SET asset_id = :asset_id WHERE device_mac = :device_mac"
        ), {
            "asset_id": asset_id,
            "device_mac": device_mac
        })

def update_device_name(device_id: int, user_id: int, new_name: str) -> bool:
    """Rename a device the caller owns. Returns True if a row was updated."""
    with engine.begin() as conn:
        result = conn.execute(text(
            "UPDATE devices SET device_name = :name WHERE id = :id AND user_id = :uid"
        ), {"name": new_name, "id": device_id, "uid": user_id})
        return result.rowcount > 0

def delete_device(device_id: int, user_id: int) -> bool:
    """Hard-delete a device owned by the caller. Returns True if a row was deleted.
    Note: existing sensor_data rows reference the MAC and are kept for history."""
    with engine.begin() as conn:
        result = conn.execute(text(
            "DELETE FROM devices WHERE id = :id AND user_id = :uid"
        ), {"id": device_id, "uid": user_id})
        return result.rowcount > 0

def delete_asset_baseline(asset_id: int) -> bool:
    """Remove a baseline so a fresh one can be calculated. Returns True if a row was deleted."""
    with engine.begin() as conn:
        result = conn.execute(text(
            "DELETE FROM asset_baselines WHERE asset_id = :id"
        ), {"id": asset_id})
        return result.rowcount > 0

def update_user_password(user_id: int, new_password_hash: str) -> bool:
    """Update a user's password hash. Returns True if a row was updated."""
    with engine.begin() as conn:
        result = conn.execute(text(
            "UPDATE users SET password_hash = :h WHERE id = :uid"
        ), {"h": new_password_hash, "uid": user_id})
        return result.rowcount > 0


# --- Audit log ---
def write_audit_log(
    *,
    user_id=None,
    organization=None,
    action: str,
    entity: str | None = None,
    entity_id=None,
    metadata: dict | None = None,
) -> None:
    """Record a security-relevant event. Best-effort: failures are logged but never raise,
    so the audit subsystem can never block a legitimate user action."""
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO audit_logs (user_id, organization, action, entity, entity_id, metadata)
                VALUES (:uid, :org, :action, :entity, :eid, CAST(:meta AS JSONB))
            """), {
                "uid": user_id,
                "org": organization,
                "action": action,
                "entity": entity,
                "eid": str(entity_id) if entity_id is not None else None,
                "meta": json.dumps(metadata) if metadata is not None else None,
            })
    except Exception as e:
        # Never let audit failure break a request. Log loudly so we notice.
        logger.warning("Failed to record audit log for %s: %s", action, e)

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
        logger.exception("Bulk sensor_data insert failed: %s", e)
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

def get_asset_spectrum(asset_id: int, limit: int = 500, *, until=None):
    """Fetch the latest `limit` raw samples for an asset; pass `until` (UTC datetime)
    to anchor the FFT window at a specific point in time instead of 'now'."""
    if until is not None:
        query = text("""
            SELECT accel_x, accel_y, accel_z
            FROM sensor_data
            WHERE asset_id = :asset_id AND time <= :until
            ORDER BY time DESC
            LIMIT :limit
        """)
        params = {"asset_id": asset_id, "limit": limit, "until": until}
    else:
        query = text("""
            SELECT accel_x, accel_y, accel_z
            FROM sensor_data
            WHERE asset_id = :asset_id
            ORDER BY time DESC
            LIMIT :limit
        """)
        params = {"asset_id": asset_id, "limit": limit}

    with engine.connect() as conn:
        result = conn.execute(query, params).fetchall()
    
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

def get_asset_health(asset_id: int, limit: int = 50, *, from_ts=None, to_ts=None):
    """Fetch up to `limit` health-metric rows for an asset. Optional from/to filter
    expects UTC datetime objects. When supplied, results come back in chronological
    order so the chart line-renders correctly without an extra reverse step."""
    where = ["asset_id = :asset_id"]
    params = {"asset_id": asset_id, "limit": int(limit)}
    if from_ts is not None:
        where.append("time >= :from_ts")
        params["from_ts"] = from_ts
    if to_ts is not None:
        where.append("time <= :to_ts")
        params["to_ts"] = to_ts
    query = text(f"""
        SELECT time, rms_x, rms_y, rms_z, rms_total, dom_freq_x, peak_to_peak_z, condition_score
        FROM asset_health_metrics
        WHERE {" AND ".join(where)}
        ORDER BY time DESC 
        LIMIT :limit
    """)

    with engine.connect() as conn:
        result = conn.execute(query, params).fetchall()

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

        # Sanity-check: if any std is below the noise floor, warn loudly.
        # A near-zero std means the calibration window was too narrow / too quiet,
        # and z-scores against this baseline will be unreliable.
        WEAK_STD_THRESHOLD = 0.005
        weak_axes = [i for i, s in enumerate(stds) if s < WEAK_STD_THRESHOLD]
        if weak_axes:
            axis_names = ["rms_x", "rms_y", "rms_z", "rms_total",
                          "dom_freq_x", "dom_freq_y", "dom_freq_z"]
            weak = ", ".join(axis_names[i] for i in weak_axes if i < len(axis_names))
            logger.warning(
                "Baseline for asset %s has near-zero std on [%s]. "
                "Consider recalibrating across a longer healthy window for reliable z-scores.",
                asset_id, weak,
            )

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
    
    return {"message": "Baseline calculated and set successfully."}

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

def get_recent_alerts(organization: str, limit: int = 20, offset: int = 0):
    """Latest asset_events for the caller's organization, paginated.

    Scoped by `assets.organization` so that one tenant never sees another
    tenant's history log. Callers MUST pass the JWT-derived organization;
    if it's missing/empty we return an empty list rather than leaking data.
    """
    if not organization:
        return []
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    query = text("""
        SELECT e.id, e.asset_id, e.start_time, e.end_time, e.severity,
               e.initial_diagnosis, e.max_z_score, a.name as asset_name
        FROM asset_events e
        JOIN assets a ON e.asset_id = a.id
        WHERE a.deleted_at IS NULL
          AND a.organization = :organization
        ORDER BY e.start_time DESC
        LIMIT :limit OFFSET :offset
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {
            "organization": organization,
            "limit": limit,
            "offset": offset,
        }).fetchall()
        return [dict(row._mapping) for row in result]

# --- Maintenance related DB operations ---
def create_ticket(asset_id, event_id, created_by, assigned_to, title, description, priority, due_date, status):
    query = text("""
        INSERT INTO maintenance_tickets (asset_id, event_id, created_by, assigned_to, title, description, priority, due_date, status)
        VALUES (:asset_id, :event_id, :created_by, :assigned_to, :title, :description, :priority, :due_date, :status)
    """)
    with engine.connect() as conn:
        conn.execute(query, {
            "asset_id": asset_id,
            "event_id": event_id,
            "created_by": created_by,
            "assigned_to": assigned_to,
            "title": title,
            "description": description,
            "status": status,
            "priority": priority,
            "due_date": due_date
        })
        conn.commit()

def get_tickets_by_org(organization: str, *, limit: int = 100, offset: int = 0):
    """Paginated tickets for an org, newest first."""
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    query = text("""
        SELECT mt.*, a.name as asset_name, u.username as assigned_to_name
        FROM maintenance_tickets mt
        JOIN assets a ON mt.asset_id = a.id
        LEFT JOIN users u ON mt.assigned_to = u.id
        WHERE a.organization = :organization AND a.deleted_at IS NULL
        ORDER BY mt.created_at DESC
        LIMIT :limit OFFSET :offset
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {
            "organization": organization, "limit": limit, "offset": offset
        }).fetchall()
        return [dict(row._mapping) for row in result]

def get_assignable_users(organization: str, role: str):
    """
    Managers can assign to Engineers and Technicians.
    Engineers can assign to Technicians.
    """
    if role == 'manager':
        valid_roles = ['engineer', 'technician']
    elif role == 'engineer':
        valid_roles = ['technician']
    else:
        return []

    # Requires tuple conversion for IN clause with multiple parameters safely, or using string binding.
    # The safest is ANY(:roles) in PG.
    query = text("""
        SELECT id, username, email, role 
        FROM users 
        WHERE organization = :organization AND role = ANY(:roles)
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"organization": organization, "roles": valid_roles}).fetchall()
        return [dict(row._mapping) for row in result]

def delete_ticket(ticket_id: int, user_id: int, role: str, organization: str) -> tuple[bool, str | None]:
    """
    Delete a ticket honouring role-based rules:
      - manager: may delete any ticket whose asset belongs to their organization
      - engineer/technician: may only delete their own tickets, and only while status='open'

    Returns (success, reason). reason is None on success, otherwise a human-readable string
    explaining why the delete was refused (so the route can pick the right HTTP status).
    """
    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT mt.created_by, mt.status, a.organization
              FROM maintenance_tickets mt
              JOIN assets a ON mt.asset_id = a.id
             WHERE mt.id = :id
        """), {"id": ticket_id}).mappings().first()

        if not row:
            return False, "Ticket not found"
        if (row["organization"] or "").strip() != (organization or "").strip():
            return False, "Ticket does not belong to your organization"

        if role == "manager":
            allowed = True
        else:
            allowed = (row["created_by"] == user_id and row["status"] == "open")

        if not allowed:
            return False, "You don't have permission to delete this ticket"

        result = conn.execute(text(
            "DELETE FROM maintenance_tickets WHERE id = :id"
        ), {"id": ticket_id})
        return result.rowcount > 0, None

def update_ticket_status(ticket_id: int, status: str, user_id: int):
    """
    Updates ticket status. 
    If status is 'resolved', we record the resolved_at timestamp.
    """
    if status == 'resolved':
        query = text("""
            UPDATE maintenance_tickets 
            SET status = :status, resolved_at = now(), updated_at = now() 
            WHERE id = :ticket_id
        """)
    else:
        query = text("""
            UPDATE maintenance_tickets 
            SET status = :status, updated_at = now() 
            WHERE id = :ticket_id
        """)
        
    with engine.begin() as conn:
        result = conn.execute(query, {"status": status, "ticket_id": ticket_id})
        return result.rowcount > 0

# --- MIS Reports ---
def get_org_health_summary(organization: str):
    query = text("""
        WITH latest_metrics AS (
            SELECT DISTINCT ON (asset_id) asset_id, condition_score
            FROM asset_health_metrics
            ORDER BY asset_id, time DESC
        )
        SELECT
            COUNT(*) FILTER (WHERE condition_score = 0) as healthy,
            COUNT(*) FILTER (WHERE condition_score = 1) as warning,
            COUNT(*) FILTER (WHERE condition_score = 2) as critical,
            COUNT(*) as total_assets
        FROM assets a
        LEFT JOIN latest_metrics lm ON a.id = lm.asset_id
        WHERE a.organization = :organization AND a.deleted_at IS NULL
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"organization": organization}).fetchone()
        return dict(result._mapping)

def get_asset_reliability_report(organization: str, *, from_ts=None, to_ts=None):
    """Reliability KPIs per asset. Optional from_ts/to_ts (UTC) clip the events window."""
    event_where = []
    params = {"organization": organization}
    if from_ts is not None:
        event_where.append("e.start_time >= :from_ts")
        params["from_ts"] = from_ts
    if to_ts is not None:
        event_where.append("e.start_time <= :to_ts")
        params["to_ts"] = to_ts
    event_filter = " AND " + " AND ".join(event_where) if event_where else ""
    query = text(f"""
        WITH uptime_stats AS (
            SELECT
                a.id as asset_id,
                a.name as asset_name,
                a.created_at as asset_created,
                COALESCE(SUM(EXTRACT(EPOCH FROM (COALESCE(e.end_time, CURRENT_TIMESTAMP) - e.start_time))) FILTER (WHERE e.severity = 2), 0) as critical_downtime_sec,
                COUNT(e.id) FILTER (WHERE e.severity = 2) as critical_alert_count
            FROM assets a
            LEFT JOIN asset_events e ON a.id = e.asset_id{event_filter}
            WHERE a.organization = :organization AND a.deleted_at IS NULL
            GROUP BY a.id, a.name, a.created_at
        ),
        latest_health AS (
            SELECT DISTINCT ON (asset_id) asset_id, condition_score, diagnosis
            FROM asset_health_metrics
            ORDER BY asset_id, time DESC
        )
        SELECT 
            u.asset_id,
            u.asset_name,
            u.critical_alert_count,
            u.critical_downtime_sec,
            EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - u.asset_created)) as total_time_sec,
            lh.condition_score,
            lh.diagnosis
        FROM uptime_stats u
        LEFT JOIN latest_health lh ON u.asset_id = lh.asset_id
        ORDER BY u.asset_name
    """)
    with engine.connect() as conn:
        result = conn.execute(query, params).fetchall()
        report = []
        for r in result:
            d = dict(r._mapping)
            total_time = float(d['total_time_sec'] or 0)
            downtime = float(d['critical_downtime_sec'] or 0)
            # Calculate uptime percentage
            uptime = 100.0
            if total_time > 0 and downtime > 0:
                uptime = max(0.0, 100.0 * (1.0 - (downtime / total_time)))
            d['uptime_percentage'] = round(uptime, 2)
            # Make sure these are native Python types before returning for JSON
            d['total_time_sec'] = total_time
            d['critical_downtime_sec'] = downtime
            report.append(d)
        return report

def get_alert_resolution_report(organization: str, *, from_ts=None, to_ts=None):
    """Ticket / alert audit. Optional from_ts/to_ts (UTC datetimes) clip by ticket creation time."""
    where = ["a.organization = :organization", "a.deleted_at IS NULL"]
    params = {"organization": organization}
    if from_ts is not None:
        where.append("mt.created_at >= :from_ts")
        params["from_ts"] = from_ts
    if to_ts is not None:
        where.append("mt.created_at <= :to_ts")
        params["to_ts"] = to_ts
    query = text(f"""
        SELECT
            mt.id as ticket_id,
            mt.event_id as alert_id,
            mt.created_at as timestamp,
            COALESCE(e.initial_diagnosis, mt.description) as diagnosis,
            mt.status,
            mt.resolved_at,
            a.name as asset_name
        FROM maintenance_tickets mt
        JOIN assets a ON mt.asset_id = a.id
        LEFT JOIN asset_events e ON mt.event_id = e.id
        WHERE {" AND ".join(where)}
        ORDER BY mt.created_at DESC
    """)
    with engine.connect() as conn:
        result = conn.execute(query, params).fetchall()
        report = []
        for r in result:
            d = dict(r._mapping)
            d['timestamp'] = d['timestamp'].isoformat() if d['timestamp'] else None
            
            response_time_hours = None
            if d.get('resolved_at') and d.get('timestamp'):
                # Handle timezone aware datetimes
                # Both are datetime objects from PG.
                diff = d['resolved_at'] - r.timestamp 
                response_time_hours = round(diff.total_seconds() / 3600.0, 2)
            
            d['response_time_hours'] = response_time_hours
            if d.get('resolved_at'):
                d['resolved_at'] = d['resolved_at'].isoformat()
                
            report.append(d)
        return report

def get_fft_deep_dive(asset_id: int, limit: int = 1000, *, from_ts=None, to_ts=None):
    """FFT export feed. Supports optional time-window filtering for scoped CSV exports."""
    where = ["h.asset_id = :asset_id"]
    params = {"asset_id": asset_id, "limit": int(limit)}
    if from_ts is not None:
        where.append("h.time >= :from_ts")
        params["from_ts"] = from_ts
    if to_ts is not None:
        where.append("h.time <= :to_ts")
        params["to_ts"] = to_ts
    query = text(f"""
        SELECT
            h.time as timestamp,
            h.dom_freq_x as freq_x, h.dom_freq_y as freq_y, h.dom_freq_z as freq_z,
            h.rms_x as vel_x, h.rms_y as vel_y, h.rms_z as vel_z,
            b.mean_rms_x, b.std_rms_x,
            b.mean_rms_y, b.std_rms_y,
            b.mean_rms_z, b.std_rms_z,
            b.mean_dom_freq_x, b.std_dom_freq_x,
            b.mean_dom_freq_y, b.std_dom_freq_y,
            b.mean_dom_freq_z, b.std_dom_freq_z
        FROM asset_health_metrics h
        LEFT JOIN asset_baselines b ON h.asset_id = b.asset_id
        WHERE {" AND ".join(where)}
        ORDER BY h.time DESC
        LIMIT :limit
    """)
    with engine.connect() as conn:
        result = conn.execute(query, params).fetchall()
        report = []
        for r in result:
            d = dict(r._mapping)
            timestamp = d['timestamp'].isoformat() if d['timestamp'] else None
            
            # Helper to calculate z-score
            def calc_z(val, mean, std):
                if val is None or mean is None or std is None or std == 0:
                    return 0.0
                return (val - mean) / std

            # We flatten this for CSV export: one row per axis per timestamp
            # X-Axis
            report.append({
                "timestamp": timestamp,
                "axis": "X",
                "dominant_freq_hz": d['freq_x'],
                "rms_velocity": d['vel_x'],
                "rms_z_score": round(calc_z(d['vel_x'], d['mean_rms_x'], d['std_rms_x']), 2),
                "freq_z_score": round(calc_z(d['freq_x'], d['mean_dom_freq_x'], d['std_dom_freq_x']), 2)
            })
            # Y-Axis
            report.append({
                "timestamp": timestamp,
                "axis": "Y",
                "dominant_freq_hz": d['freq_y'],
                "rms_velocity": d['vel_y'],
                "rms_z_score": round(calc_z(d['vel_y'], d['mean_rms_y'], d['std_rms_y']), 2),
                "freq_z_score": round(calc_z(d['freq_y'], d['mean_dom_freq_y'], d['std_dom_freq_y']), 2)
            })
            # Z-Axis
            report.append({
                "timestamp": timestamp,
                "axis": "Z",
                "dominant_freq_hz": d['freq_z'],
                "rms_velocity": d['vel_z'],
                "rms_z_score": round(calc_z(d['vel_z'], d['mean_rms_z'], d['std_rms_z']), 2),
                "freq_z_score": round(calc_z(d['freq_z'], d['mean_dom_freq_z'], d['std_dom_freq_z']), 2)
            })
        
        return report