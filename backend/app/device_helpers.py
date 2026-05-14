import re
import os
import secrets
import logging
import paho.mqtt.publish as publish
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity

logger = logging.getLogger(__name__)
from provision_logic import generate_slpt
from datetime import datetime, timezone
from db import (
    get_provisioning_token,
    activate_device_in_db,
    link_asset_to_device,
    get_user_devices,
    calculate_and_set_baseline,
    update_device_name as db_update_device_name,
    delete_device as db_delete_device,
    write_audit_log,
)

MAC_PATTERN = r"^([0-9A-F]{2}[:-]){5}([0-9A-F]{2})$"


def provision_device():
    """Create a short-lived provisioning token (SLPT) for a given MAC address."""
    user_identity = get_jwt_identity()
    user_id = int(user_identity)
    data = request.get_json() or {}
    enrollment_id = (data.get("enrollment_id") or "").upper().strip()
    if not enrollment_id:
        return jsonify({"error": "Enrollment ID (MAC Address) is required"}), 400
    if not re.match(MAC_PATTERN, enrollment_id):
        return jsonify({"error": "Enrollment ID (MAC Address) is not valid"}), 400
    try:
        token_data = generate_slpt(user_id, enrollment_id)
        return jsonify({
            "message": "Token successfully generated",
            "slpt": token_data["slpt"],
            "expires_in_seconds": token_data["expires_in_seconds"],
            "expires_at_unix": token_data["expires_timestamp_unix"],
        }), 201
    except Exception as e:
        logger.exception("Error generating SLPT: %s", e)
        return jsonify({"error": "Internal server error during token generation"}), 500


def activate_device():
    """Activate a device using a previously issued SLPT and a matching MAC address."""
    data = request.get_json() or {}
    slpt = (data.get("slpt") or "").strip()
    mac = (data.get("mac") or "").upper().strip()
    logger.debug("Attempting activation for MAC: [%s] with SLPT: [%s]", mac, slpt)
    if not slpt or not mac:
        return jsonify({"error": "Missing token or MAC"}), 400
    if not re.match(MAC_PATTERN, mac):
        return jsonify({"error": "MAC address is not valid"}), 400

    token_record = get_provisioning_token(slpt)
    if not token_record:
        return jsonify({"error": "Invalid provisioning token"}), 404
    if token_record["is_used"]:
        return jsonify({"error": "Token already used"}), 403
    if token_record["enrollment_id"] != mac:
        return jsonify({"error": "MAC address mismatch"}), 403
    if token_record["expires_at"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        return jsonify({"error": "Token expired"}), 403

    try:
        # Generate a random MQTT password for this device.
        mqtt_password = secrets.token_hex(16)
        activate_device_in_db(
            mac,
            token_record["user_id"],
            mqtt_password,
            data.get("os_version", "unknown"),
        )
        # We deliberately do NOT return a broker_url here. In the dev compose
        # stack (and any single-host deployment) the MQTT broker shares the
        # host the device hit for /activate, so the firmware's fallback —
        # "if broker_url is empty, keep the host you provisioned with" — is
        # already correct. If a future deployment splits the API and the
        # broker onto different hosts, set MQTT_PUBLIC_HOST in the backend
        # env and return it here.
        broker_url = os.getenv("MQTT_PUBLIC_HOST", "")
        response = {
            "message": "Device activated",
            "device_id": mac,        # for now setting MAC; later we can have separate device IDs
            "mqtt_user": mac,        # same for MQTT user
            "mqtt_pass": mqtt_password,
        }
        if broker_url:
            response["broker_url"] = broker_url
        return jsonify(response), 200
    except Exception as e:
        logger.exception("Error activating device: %s", e)
        return jsonify({"error": "Internal server error during device activation"}), 500


def get_devices_for_user():
    """Return all devices belonging to the current user."""
    user_identity = get_jwt_identity()
    user_id = int(user_identity)
    try:
        devices = get_user_devices(user_id)
        return jsonify({"devices": devices}), 200
    except Exception as e:
        logger.exception("Error retrieving devices: %s", e)
        return jsonify({"error": "Internal server error during device retrieval"}), 500


def link_sensor_to_asset():
    """Link or unlink a sensor (by MAC) to an asset (by id, or None to unassign)."""
    data = request.get_json() or {}
    device_mac = (data.get("device_mac") or "").upper().strip()
    asset_id = data.get("asset_id")  # may be None to decouple
    try:
        link_asset_to_device(asset_id, device_mac)
        return jsonify({"message": "Asset linked to device successfully"}), 200
    except Exception as e:
        logger.exception("Error linking asset to device: %s", e)
        return jsonify({"error": "Internal server error during asset linking"}), 500


def update_device_name_route(device_id: int):
    """Rename a device the caller owns."""
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}
    new_name = (data.get("device_name") or "").strip()
    if not new_name:
        return jsonify({"error": "device_name is required"}), 400
    if len(new_name) > 100:
        return jsonify({"error": "device_name must be 100 characters or fewer"}), 400
    try:
        updated = db_update_device_name(device_id, user_id, new_name)
        if not updated:
            return jsonify({"error": "Device not found"}), 404
        write_audit_log(
            user_id=user_id, action="device.rename",
            entity="device", entity_id=device_id,
            metadata={"new_name": new_name},
        )
        return jsonify({"message": "Device renamed"}), 200
    except Exception as e:
        logger.exception("Error renaming device: %s", e)
        return jsonify({"error": "Internal server error during device rename"}), 500


def delete_device_route(device_id: int):
    """Hard-delete a device the caller owns. Historical sensor_data rows are kept (they reference the MAC)."""
    user_id = int(get_jwt_identity())
    try:
        deleted = db_delete_device(device_id, user_id)
        if not deleted:
            return jsonify({"error": "Device not found"}), 404
        write_audit_log(
            user_id=user_id, action="device.delete",
            entity="device", entity_id=device_id,
        )
        return jsonify({"message": "Device deleted"}), 200
    except Exception as e:
        logger.exception("Error deleting device: %s", e)
        return jsonify({"error": "Internal server error during device deletion"}), 500


def set_asset_baseline(asset_id: int):
    """Trigger a baseline (re)calculation for an asset and notify the ingestor to flush its cache."""
    result = calculate_and_set_baseline(asset_id)
    if "error" in result:
        return jsonify(result), 400

    # Notify the MQTT ingestor to clear its cached baseline so the new values take effect.
    try:
        broker = os.getenv("MQTT_BROKER", "mqtt_broker")
        # Note: publish.single may block briefly if the broker is unreachable. Wrap in try/except.
        logger.info("Publishing clear_cache for asset %s to %s", asset_id, broker)
        publish.single("cmd/clear_cache", payload=str(asset_id), hostname=broker, port=1883)
    except Exception as e:
        logger.warning("Failed to invalidate MQTT cache: %s", e)

    return jsonify(result), 200
