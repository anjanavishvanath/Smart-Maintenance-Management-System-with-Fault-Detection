from flask import Flask, jsonify, request, make_response
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity, get_jwt, create_access_token, get_jti
import paho.mqtt.client as mqtt
import os
import threading
import time
import traceback
from dotenv import load_dotenv
import json
#import db and auth helpers
from db import engine, get_user_by_email, insert_user, insert_refresh_token, revoke_refresh_token, is_refresh_token_revoked
from auth import hash_password, verify_password, build_tokens
# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "your-secret-key")  # Change this in production!
app.config["JWT_ALGORITHM"] = "HS256"
jwt = JWTManager(app)

#------------Authentication endpoints
@app.route("/api/auth/signup", methods=["POST"])
def signup():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")
    role = data.get("role", "technician")  # default role
    if not email or not password:
        return jsonify({"msg": "Missing email or password"}), 400
    # Check if user already exists
    if get_user_by_email(email):
        return jsonify({"msg": "User already exists"}), 409
    # Hash password and insert user
    try:
        pw_hash = hash_password(password)
    except ValueError as e:
        return jsonify({"msg": str(e)}), 400
    
    insert_user(email, pw_hash, role)
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
    user_id = user[0]
    pw_hash = user[2]
    role = user[3]
    if not verify_password(password, pw_hash):
        return jsonify({"msg": "invalid email or password"}), 401
    identity = {"user_id": user_id, "email": email, "role": role}
    access, refresh, jti, expires_at = build_tokens(identity)
    # Store refresh token jti in DB for revocation check
    insert_refresh_token(jti, user_id, expires_at)
    # return tokens (for SPA, consider storing refresh token in HttpOnly cookie)
    return jsonify({"access_token": access, "refresh_token": refresh, "role": role}), 200

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
    additional = {}
    if "role" in claims:
        additional["role"] = claims.get("role")
    if "email" in claims:
        additional["email"] = claims.get("email")

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

# MQTT stuff
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
MQTT_TOPIC_SUB = read_env_val("MQTT_TOPIC_SUB", alt="MQTT_TOPIC", default="test/topic")
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
    # update shared variable
    global latest_message
    latest_message = {"topic": msg.topic, "payload": payload, "qos": msg.qos, "timestamp": time.time()}

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

@app.route("/latest")
def get_latest_message():
    if latest_message:
        return jsonify({"mqtt_connected": mqtt_connected, "data": latest_message})
    else:
        return jsonify({"message": "No data received yet", "mqtt_connected": mqtt_connected}), 404

if __name__ == "__main__":
    # Start MQTT thread (guarded by __main__ so it does not run on import)
    mqtt_thread = threading.Thread(target=start_mqtt_thread, daemon=True)
    mqtt_thread.start()
    # Start Flask (dev). In production, use WSGI server and run mqtt client separately.
    app.run(host="0.0.0.0", port=5000)


'''
 Only for development: use threaded=True so the app and the mqtt thread can coexist.
 For production, run via gunicorn / uwsgi. When using multiple worker processes,
 run this MQTT client as a separate service (or use one worker (in docker?)).

 For DB schema changes over time (development, production, iterative work) 
 you should use a proper migration tool (Alembic) or explicit psql commands.
'''