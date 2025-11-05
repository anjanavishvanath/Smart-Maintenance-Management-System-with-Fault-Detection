from flask import Flask, jsonify, request, make_response
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity, get_jwt, create_access_token, get_jti
import paho.mqtt.client as mqtt
import os
import threading
import time
import traceback
from dotenv import load_dotenv
import json
from queue import Queue
import secrets
from datetime import datetime, timedelta, timezone
from flask_cors import CORS
from sqlalchemy import text
#import db and auth helpers
from db import engine, get_user_by_email, insert_user, insert_refresh_token, revoke_refresh_token, is_refresh_token_revoked
from db import get_device_by_device_id, insert_device, insert_device_credentials, get_active_credentials_for_device
from db import insert_reading, get_recent_readings, get_all_devices
from auth import hash_password, verify_password, build_tokens
# Load environment variables from .env file
load_dotenv()


app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "your-secret-key")  # Change this in production!
app.config["JWT_ALGORITHM"] = "HS256"
jwt = JWTManager(app)

CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5173"]}})

# Creating a in memmory queue and worker to perform DB writes off the MQTT thread
write_queue = Queue(maxsize=1000)

def db_writer_worker():
    # Background worker that consumes items from write_queue and inserts in to DB
    while True:
        item = write_queue.get() # block unitll available
        if item is None:
            #  sentinel to stop worker if needed
            break
        try:
            # item expected format: dict with keys ts_ms or time, device_id, ax, ay, az, sample_rate, meta
            time_ms = item.get("ts_ms") or item.get("time")
            device_id = item.get("device_id")
            ax = float(item.get("ax")) if item.get("ax") is not None else None
            ay = float(item.get("ay")) if item.get("ay") is not None else None
            az = float(item.get("az")) if item.get("az") is not None else None
            sample_rate = item.get("sample_rate") if item.get("sample_rate") is not None else None
            meta = item.get("meta") or item # store whole payload if meta is missing
            # have a way to accept aggregate inserts later for performance

            # Call DB insert function
            insert_reading(time_ms, device_id, ax, ay, az, sample_rate, meta)
        except Exception:
            # continue without crashing
            print("[DB WORKER] Exception writing the reading to DB:", flush=True)
            import traceback; traceback.print_exc()
        finally:
            write_queue.task_done()



#------------Authentication endpoints
@app.route("/api/auth/signup", methods=["POST"])
def signup():
    data = request.get_json() or {}
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    role = data.get("role", "technician")  # default role
    if not email or not password or not username:
        return jsonify({"msg": "Missing email, password or username"}), 400
    # Check if user already exists
    if get_user_by_email(email):
        return jsonify({"msg": "User already exists"}), 409
    # Hash password and insert user
    try:
        pw_hash = hash_password(password)
    except ValueError as e:
        return jsonify({"msg": str(e)}), 400
    
    insert_user(username, email, pw_hash, role)
    return jsonify({"msg": "User created successfully"}), 201

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        return jsonify({"msg": "Missing email or password"}), 400
    user = get_user_by_email(email)
    if not user:
        return jsonify({"msg": "invalid email or password"}), 401
    user_id = user.get("id")
    username = user.get("username")
    email = user.get("email")
    pw_hash = user.get("password_hash")
    role = user.get("role")
    if not verify_password(password, pw_hash):
        return jsonify({"msg": "invalid email or password"}), 401
    identity = {"user_id": user_id, "email": email, "username":username , "role": role}
    access, refresh, jti, expires_at = build_tokens(identity)
    # Store refresh token jti in DB for revocation check
    insert_refresh_token(jti, user_id, expires_at)
    # return tokens (for SPA, consider storing refresh token in HttpOnly cookie)
    return jsonify({"access_token": access, "refresh_token": refresh, "role": role, "username": username}), 200

@app.route("/api/auth/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    #called with refresh token in Authorization header or cookie
    identity = get_jwt_identity()
    claims = get_jwt()
    jti = claims.get("jti")
    # if jti is revoked, reject
    if is_refresh_token_revoked(jti):
        return jsonify({"msg": "Token has been revoked"}), 401
    # re-issue access token using same identity and additional claims
    additional = {k: claims.get(k) for k in ("email", "role", "username") if claims.get(k) is not None}

    access = create_access_token(identity=identity, additional_claims=additional)
    return jsonify({"access_token": access}), 200

@app.route("/api/auth/logout", methods=["POST"])
@jwt_required(refresh=True)
def logout():
    claims = get_jwt()
    jti = claims.get("jti")
    # mark this jti as revoked in DB
    revoke_refresh_token(jti)
    return jsonify({"msg": "Refresh token revoked"}), 200

# --- Device provisioning endpoints ---
# Utility to generate username/password for device
def generate_mqtt_creds(device_id):
    # username: device_id + random suffix
    username = f"{device_id}-{secrets.token_urlsafe(6)}"
    # password: random urlsafe
    password = secrets.token_urlsafe(24)
    return username, password

@app.route("/api/devices/provision", methods=["POST"])
@jwt_required()   # ensure caller is an authenticated user
def provision_device():
    """
    Expected body: { "device_id": "dev0001", "claim_token": "...", "mac": "AA:BB:CC:..", "fw_version": "v0.1.0" }
    Any authenticated user may create a device; device will be associated with that user (created_by).
    """
    data = request.get_json(silent=True) or {}
    device_id = data.get("device_id")
    claim = data.get("claim_token") or data.get("claim")
    mac = data.get("mac")
    fw = data.get("fw_version")

    if not device_id:
        return jsonify({"msg": "device_id required"}), 400

    # determine calling user id (JWT identity was stored as string in build_tokens)
    try:
        identity = get_jwt_identity()
        created_by = int(identity) if identity is not None else None
    except Exception:
        created_by = None

    # If device already exists, we can return its active creds (or create fresh ones)
    device = get_device_by_device_id(device_id)
    if not device:
        # insert minimal device row and record created_by
        insert_device(device_id, name=device_id, config={"fw_version": fw, "mac": mac}, created_by=created_by)
    else:
        # optional: update last known fw/mac into config
        try:
            cfg = device.get("config") or {}
            if isinstance(cfg, str):
                cfg = json.loads(cfg)
            cfg.update({"fw_version": fw, "mac": mac})
            with engine.begin() as conn:
                conn.execute(text("UPDATE devices SET config = :cfg WHERE device_id = :device_id"),
                             {"cfg": json.dumps(cfg), "device_id": device_id})
        except Exception:
            pass

    # Generate one-time creds
    username, password = generate_mqtt_creds(device_id)

    # Optionally set expiry (e.g., 7 days) — or do not expire
    expires_at = datetime.utcnow() + timedelta(days=30)
    insert_device_credentials(device_id, username, password, expires_at=expires_at)

    # Prepare config returned to device.
    config = {
        "mqtt_host": MQTT_HOST,
        "mqtt_port": MQTT_PORT,
        "client_id": device_id,
        "topic_prefix": f"v1/device/{device_id}",
        "fw_version": "v0.1.0",
    }

    resp = {
        "credentials": {"username": username, "password": password},
        "config": config
    }
    return jsonify(resp), 200

# --- MQTT stuff ---
def read_env_val(name, alt=None, required=False, default=None):
    val = os.getenv(name, alt)
    if not val and alt:
        val = os.getenv(alt)
    if (not val) and (default is not None):
        val = default
    if required and (not val):
        return RuntimeError(f"Required env variable not set: {name} (alt: {alt})")
    return val

# MQTT Configuration
MQTT_HOST = read_env_val("MQTT_HOST", alt="MQTT_BROKER" ,required=True)
MQTT_PORT = int(read_env_val("MQTT_PORT", alt="MQTT_PORT", default="8883"))
MQTT_USERNAME = read_env_val("MQTT_USER", alt="MQTT_USERNAME", default=None)
MQTT_PASSWORD = read_env_val("MQTT_PASSWORD", alt="MQTT_PASS", default=None)
MQTT_TOPIC_SUB = read_env_val("MQTT_TOPIC_SUB", alt="MQTT_TOPIC", default="v1/device/+/telemetry")
CLIENT_ID = read_env_val("CLIENT_ID", default="cm-backend")

print("[CONFIG] MQTT_HOST=", MQTT_HOST, "MQTT_PORT=", MQTT_PORT, "MQTT_TOPIC_SUB=", MQTT_TOPIC_SUB)

# using absolute path for the certificate
BASEDIR = os.path.abspath(os.path.dirname(__file__))
CA_FILE = os.path.join(BASEDIR, "ca-chain.pem")

# Global storage
latest_message = {}
mqtt_connected = False
mqtt_client = None

def on_connect(client, userdata, flags, rc):
    global mqtt_connected
    print(f"[MQTT CB] on_connect rc={rc}")
    if rc == 0:
        mqtt_connected = True
        try:
            client.subscribe(MQTT_TOPIC_SUB, qos=0)
            print(f"[MQTT CB] Subscribed to {MQTT_TOPIC_SUB}")
        except Exception as e:
            print("[MQTT CB] subscribe() error:", e)
    else:
        mqtt_connected = False
        print(f"[MQTT CB] Connect failed with rc={rc}")

def on_disconnect(client, userdata, rc):
    global mqtt_connected
    mqtt_connected = False
    print(f"[MQTT CB] on_disconnect rc={rc}")

def on_subscribe(client, userdata, mid, granted_qos):
    print(f"[MQTT CB] on_subscribe mid={mid} granted_qos={granted_qos}")

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8", errors="replace")
    except Exception:
        payload = str(msg.payload)
    print(f"[MQTT CB] on_message {msg.topic} -> {payload}")
    
    # Quick topic parsing: expecting v1/device/{device_id}/telemetry
    topic_parts = msg.topic.split("/")
    device_id = None
    if(len(topic_parts) >= 3 and topic_parts[0] == "v1" and topic_parts[1] == "device"):
        device_id = topic_parts[2]
    # parsing the payload as JSON
    try:
        data = json.loads(payload)
    except Exception:
        data = None

    item = {}
    if isinstance(data, dict):
        item = dict(data)  # make a copy
    
    #Enqueue for DB write (non-blocking, drop and log if full)
    try:
        write_queue.put_nowait(item)
    except Exception:
         print("[MQTT CB] write_queue full - dropping telemetry", flush=True)


def on_log(client, userdata, level, buf):
    # Paho log levels: 0-4. Print everything for debugging:
    print(f"[MQTT LOG] {level}: {buf}")

def start_mqtt_thread():
    global mqtt_client, mqtt_connected
    print("[MQTT] START: start_mqtt_thread() called", flush=True)
    try:
        print("[MQTT] creating client object...", flush=True)
        mqtt_client = mqtt.Client(client_id=CLIENT_ID, protocol=mqtt.MQTTv311)
        print("[MQTT] setting username/password...", flush=True)
        mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

        print(f"[MQTT] checking CA file exists at: {CA_FILE}", flush=True)
        if not os.path.isfile(CA_FILE):
            raise FileNotFoundError(f"CA file not found at: {CA_FILE}")
        print("[MQTT] CA file found", flush=True)

        print("[MQTT] calling tls_set()", flush=True)
        try:
            mqtt_client.tls_set(ca_certs=CA_FILE)
            print("[MQTT] tls_set() ok", flush=True)
        except Exception as e:
            print("[MQTT] tls_set() ERROR:", e, flush=True)
            raise

        # bind callbacks (these print when called)
        mqtt_client.on_connect = on_connect
        mqtt_client.on_disconnect = on_disconnect
        mqtt_client.on_subscribe = on_subscribe
        mqtt_client.on_message = on_message
        mqtt_client.on_log = on_log
        mqtt_client.enable_logger()
        print("[MQTT] callbacks bound", flush=True)

        print(f"[MQTT] Attempting connect to {MQTT_HOST}:{MQTT_PORT} ...", flush=True)
        try:
            mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            print("[MQTT] connect() returned (no exception)", flush=True)
        except Exception as e:
            print("[MQTT] connect() raised:", repr(e), flush=True)
            raise

        print("[MQTT] starting network loop (loop_start)", flush=True)
        mqtt_client.loop_start()
        print("[MQTT] loop_start() done", flush=True)

        # wait up to 20s for on_connect to set the flag
        timeout = 20
        for i in range(timeout):
            print(f"[MQTT] wait loop {i+1}/{timeout} mqtt_connected={mqtt_connected}", flush=True)
            if mqtt_connected:
                print("[MQTT] mqtt_connected flag TRUE, connected", flush=True)
                break
            time.sleep(1)

        if not mqtt_connected:
            print("[MQTT] connection timed out - mqtt_connected still False", flush=True)

    except Exception as e:
        print("[MQTT] Exception in start_mqtt_thread():", flush=True)
        traceback.print_exc()
        print("[MQTT] end exception", flush=True)
    
#----------------------------------------------------Flask routes
@app.route("/")
def index():
    return jsonify({"message": "Welcome to the Flask API!", "mqtt_connected": mqtt_connected})

@app.route("/api/devices", methods=["GET"])
@jwt_required()
def api_list_devices():
    try:
        limit = int(request.args.get("limit", "100"))
    except Exception:
        limit = 100
    
    # get current user id from JWT
    try:
        identity = get_jwt_identity()
        user_id = int(identity) if identity is not None else None
    except Exception:
        user_id = None

    try:
        rows = get_all_devices(limit=limit, user_id=user_id)
        return jsonify({"count": len(rows), "devices": rows}), 200
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"msg": "Error retrieving devices", "error": str(e)}), 500


@app.route("/api/devices/<device_id>", methods=["GET"])
@jwt_required()
def api_get_device(device_id):
    # fetch device
    device = get_device_by_device_id(device_id)
    if not device:
        return jsonify({"msg": "Device not found"}), 404
    #enforce ownership
    try:
        caller_id = int(get_jwt_identity())
        if device.get("created_by") and device.get("created_by") != caller_id:
            return jsonify({"msg": "Not authorized to access this device"}), 403
    except Exception:
        pass
    # prepare response. Check if this is needed or we can return as is 
    cfg = device.get("config")
    try:
        cfg_parsed = json.loads(cfg) if cfg and isinstance(cfg, str) else cfg
    except Exception:
        cfg_parsed = cfg
    resp = {
        "device_id": device.get("device_id"),
        "name": device.get("name"),
        "status": device.get("status"),
        "last_seen": device.get("last_seen") if device.get("last_seen") else None,
        "config": cfg_parsed
    }
    return jsonify(resp), 200


@app.route("/api/devices/<device_id>/readings", methods=["GET"])
def api_get_device_readings(device_id):
    try:
        limit = int(request.args.get("limit", "100"))
    except Exception:
        limit = 100
    
    try:
        rows = get_recent_readings(device_id, limit=limit)
        return jsonify({"device_id": device_id, "count": len(rows), "readings": rows}), 200
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"msg": "Error retrieving readings", "error": str(e)}), 500

if __name__ == "__main__":
    # Start MQTT thread (guarded by __main__ so it does not run on import)
    mqtt_thread = threading.Thread(target=start_mqtt_thread, daemon=True)
    db_worker_thread = threading.Thread(target=db_writer_worker, daemon=True)
    mqtt_thread.start()
    db_worker_thread.start()
    # Start Flask (dev). In production, use WSGI server and run mqtt client separately.
    app.run(host="0.0.0.0", port=5000)


'''
 Only for development: use threaded=True so the app and the mqtt thread can coexist.
 For production, run via gunicorn / uwsgi. When using multiple worker processes,
 run this MQTT client as a separate service (or use one worker (in docker?)).

 For DB schema changes over time (development, production, iterative work) 
 you should use a proper migration tool (Alembic) or explicit psql commands.
'''