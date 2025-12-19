import re
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from provision_logic import generate_slpt
import secrets
from datetime import datetime, timezone
from db import get_provisioning_token, activate_device_in_db

def provision_device():
    user_identity = get_jwt_identity()
    user_id = int(user_identity)
    data = request.get_json() # parse request body
    enrollment_id = data.get('enrollment_id').upper().strip()
    if not enrollment_id:
        return jsonify({"msg":"Enrollment ID (MAC Address) is required"}), 400
    mac_pattern = r"^([0-9A-F]{2}[:-]){5}([0-9A-F]{2})$"
    if not re.match(mac_pattern, enrollment_id):
        return jsonify({"msg":"Enrollment ID (MAC Address) is not valid"}), 400
    try:
        token_data = generate_slpt(user_id, enrollment_id)
        return jsonify ({
            "msg": "Token successfully generated",
            "slpt": token_data['slpt'],
            "expires_in_seconds": token_data['expires_in_seconds'],
            "expires_at_unix": token_data['expires_timestamp_unix']
        }), 201
    except Exception as e:
        print(f"Error generating SLPT: {e}")
        return jsonify({"msg": "Internal server error during token generation"}), 500
    
def activate_device():
    data = request.get_json()
    slpt = data.get("slpt").strip()
    mac = data.get("mac").upper().strip()
    print(f"DEBUG: Attempting activation for MAC: [{mac}] with SLPT: [{slpt}]")
    if not slpt or not mac:
        return jsonify({"msg":"Missing token or MAC"}), 400
    token_record = get_provisioning_token(slpt) # lookup token
    if not token_record:
        return jsonify({"msg": "Invalid provisioning token"}), 404
    #  security checks
    if token_record["is_used"]:
        return jsonify({"msg": "Token already used"}), 403
    if token_record["enrollment_id"] != mac:
        return jsonify({"msg": "MAC address mismatch"}), 403
    if token_record['expires_at'].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        return jsonify({"msg": "Token expired"}), 403
    try:
        # Success. Generate a random mqtt password
        mqtt_password = secrets.token_hex(16)
        activate_device_in_db(mac, token_record["user_id"], mqtt_password, data.get("os_version", "unknown"))
        return jsonify({
            "msg": "Device activated",
            "device_id": mac,        # fornow setting mac, later can have separate device ids
            "mqtt_user": mac,        # same for mqqt user
            "mqtt_pass": mqtt_password,
            "broker_url": "192.168.1.2" # laptop IP for the MQTT broker
        }), 200
    except Exception as e:
        print(f"Error activating device: {e}")
        return jsonify({"msg": "Internal server error during device activation"}), 500