import logging
from flask_jwt_extended import get_jwt_identity, get_jwt
from flask import request, jsonify

logger = logging.getLogger(__name__)
from db import (
    insert_asset,
    get_organization_assets,
    get_user_by_id,
    update_asset as db_update_asset,
    soft_delete_asset as db_soft_delete_asset,
    delete_asset_baseline,
    get_asset_details,
    write_audit_log,
)


def _parse_pagination(default_limit: int = 100, max_limit: int = 500):
    """Parse limit/offset from the request and clamp them. Used by list endpoints."""
    try:
        limit = int(request.args.get("limit", default_limit))
    except (TypeError, ValueError):
        limit = default_limit
    try:
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        offset = 0
    return max(1, min(limit, max_limit)), max(0, offset)


def add_asset_to_db():
    """Create a new asset belonging to the current user's organization."""
    user_identity = get_jwt_identity()
    user_id = int(user_identity)
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    max_rpm = data.get("max_rpm", 0)
    power = data.get("power", 0)

    user_data = get_user_by_id(user_id)
    if not user_data:
        return jsonify({"error": "User not found"}), 404

    organization = (user_data["organization"] or "").strip()

    if not name:
        return jsonify({"error": "Asset name is required"}), 400

    try:
        insert_asset(name, max_rpm, power, organization, user_id)
        write_audit_log(
            user_id=user_id, organization=organization,
            action="asset.create", entity="asset",
            metadata={"name": name, "max_rpm": max_rpm, "power": power},
        )
        return jsonify({"message": "Asset added successfully"}), 201
    except Exception as e:
        logger.exception("Error inserting asset: %s", e)
        return jsonify({"error": "Internal server error during asset insertion"}), 500


def get_assets_by_organization():
    """Return all assets registered to the current user's organization."""
    user_id = int(get_jwt_identity())
    user_data = get_user_by_id(user_id)
    if user_data is None:
        return jsonify({"error": "User not found"}), 404

    organization = (user_data["organization"] or "").strip()
    if not organization:
        return jsonify({"error": "Organization is required"}), 400

    limit, offset = _parse_pagination()
    try:
        assets = get_organization_assets(organization, limit=limit, offset=offset)
        return jsonify({"assets": assets, "limit": limit, "offset": offset}), 200
    except Exception as e:
        logger.exception("Error retrieving assets: %s", e)
        return jsonify({"error": "Internal server error during asset retrieval"}), 500


def _caller_organization():
    """Read the current user's organization from their JWT (preferred) or DB fallback."""
    claims = get_jwt() or {}
    org = (claims.get("organization") or "").strip()
    if org:
        return org
    user = get_user_by_id(int(get_jwt_identity()))
    return (user["organization"] or "").strip() if user else ""


def update_asset_route(asset_id: int):
    """Update an asset's metadata. Org-scoped."""
    organization = _caller_organization()
    if not organization:
        return jsonify({"error": "Organization is required"}), 400

    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    max_rpm = data.get("max_rpm")
    power = data.get("power")

    if not name:
        return jsonify({"error": "Asset name is required"}), 400
    try:
        max_rpm = int(max_rpm) if max_rpm is not None else 0
        power = float(power) if power is not None else 0.0
    except (TypeError, ValueError):
        return jsonify({"error": "max_rpm must be an integer and power must be a number"}), 400
    if max_rpm < 0 or power < 0:
        return jsonify({"error": "max_rpm and power must be non-negative"}), 400

    try:
        # Snapshot previous state for the audit before/after diff.
        before = get_asset_details(asset_id) or {}
        updated = db_update_asset(asset_id, organization, name, max_rpm, power)
        if not updated:
            return jsonify({"error": "Asset not found in your organization"}), 404
        write_audit_log(
            user_id=int(get_jwt_identity()), organization=organization,
            action="asset.update", entity="asset", entity_id=asset_id,
            metadata={
                "before": {k: before.get(k) for k in ("name", "max_rpm", "power")},
                "after": {"name": name, "max_rpm": max_rpm, "power": power},
            },
        )
        return jsonify({"message": "Asset updated successfully"}), 200
    except Exception as e:
        logger.exception("Error updating asset: %s", e)
        return jsonify({"error": "Internal server error during asset update"}), 500


def delete_asset_route(asset_id: int):
    """Soft-delete an asset. Linked sensor_data, events, and tickets are preserved."""
    organization = _caller_organization()
    if not organization:
        return jsonify({"error": "Organization is required"}), 400
    try:
        before = get_asset_details(asset_id) or {}
        deleted = db_soft_delete_asset(asset_id, organization)
        if not deleted:
            return jsonify({"error": "Asset not found in your organization"}), 404
        write_audit_log(
            user_id=int(get_jwt_identity()), organization=organization,
            action="asset.delete", entity="asset", entity_id=asset_id,
            metadata={"name": before.get("name"), "soft_delete": True},
        )
        return jsonify({"message": "Asset deleted"}), 200
    except Exception as e:
        logger.exception("Error deleting asset: %s", e)
        return jsonify({"error": "Internal server error during asset deletion"}), 500


def reset_baseline_route(asset_id: int):
    """Clear an asset's baseline so the next 'Set Baseline' call can recalculate it."""
    organization = _caller_organization()
    if not organization:
        return jsonify({"error": "Organization is required"}), 400
    # Org-boundary check: only allow resetting baselines for assets in the caller's org.
    asset = get_asset_details(asset_id)
    if not asset or (asset.get("organization") or "").strip() != organization:
        return jsonify({"error": "Asset not found in your organization"}), 404
    try:
        deleted = delete_asset_baseline(asset_id)
        if not deleted:
            return jsonify({"error": "No baseline exists for this asset"}), 404

        # Tell the ingestor to drop its cached baseline for this asset, otherwise
        # subsequent samples are scored against stale stats until it next refreshes.
        try:
            import os
            import paho.mqtt.publish as publish
            broker = os.getenv("MQTT_BROKER", "mqtt_broker")
            publish.single("cmd/clear_cache", payload=str(asset_id), hostname=broker, port=1883)
        except Exception as e:
            logger.warning("Failed to invalidate MQTT cache after baseline reset: %s", e)

        write_audit_log(
            user_id=int(get_jwt_identity()), organization=organization,
            action="asset.baseline_reset", entity="asset", entity_id=asset_id,
        )
        return jsonify({"message": "Baseline cleared. Calibrate again to set a new one."}), 200
    except Exception as e:
        logger.exception("Error resetting baseline: %s", e)
        return jsonify({"error": "Internal server error during baseline reset"}), 500
