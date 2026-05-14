import os
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from sqlalchemy import text
from log_config import configure_logging
configure_logging()
logger = logging.getLogger(__name__)
from http_helpers import signup, login, refresh, logout, change_password
from flask_jwt_extended import JWTManager, jwt_required, get_jwt
from device_helpers import (
    provision_device,
    activate_device,
    link_sensor_to_asset,
    get_devices_for_user,
    set_asset_baseline,
    update_device_name_route,
    delete_device_route,
)
from asset_helpers import (
    add_asset_to_db,
    get_assets_by_organization,
    update_asset_route,
    delete_asset_route,
    reset_baseline_route,
)
from db import get_asset_spectrum, get_asset_health, get_asset_baseline, get_recent_alerts, engine, is_jti_revoked
from tickets_routes import create_ticket, get_org_tickets, get_assignable_users_route, delete_ticket_route, update_ticket_status_route
from reports_routes import (
    get_reliability_report_route,
    get_alert_resolution_report_route,
    get_fft_export_route,
    get_reliability_export_route,
    get_alert_resolution_export_route,
)
from datetime import datetime

load_dotenv()

# Fail fast if a critical secret is missing — never fall back to a hardcoded default in production.
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY environment variable must be set")

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = JWT_SECRET_KEY
app.config["JWT_ALGORITHM"] = "HS256"
jwt = JWTManager(app)


# --- Normalised JWT error responses ---
# By default flask-jwt-extended returns {"msg": ...}. Standardise on {"error": ...}
# so the frontend can rely on a single key shape.
@jwt.unauthorized_loader
def _custom_unauthorized(reason):
    return jsonify({"error": reason}), 401

@jwt.invalid_token_loader
def _custom_invalid_token(reason):
    return jsonify({"error": reason}), 422

@jwt.expired_token_loader
def _custom_expired_token(jwt_header, jwt_payload):
    return jsonify({"error": "Token has expired"}), 401

@jwt.revoked_token_loader
def _custom_revoked_token(jwt_header, jwt_payload):
    return jsonify({"error": "Token has been revoked"}), 401

# --- JWT blocklist ---
# Called automatically by flask-jwt-extended on every @jwt_required request.
# Returning True causes the request to be rejected with the revoked_token_loader response.
@jwt.token_in_blocklist_loader
def _check_token_blocklist(jwt_header, jwt_payload):
    return is_jti_revoked(jwt_payload.get("jti"))

# CORS: in production, restrict origins via the CORS_ORIGINS env var (comma-separated).
# Defaults to "*" only when not set, to keep dev frictionless.
_cors_origins = os.getenv("CORS_ORIGINS", "*")
_origins = [o.strip() for o in _cors_origins.split(",")] if _cors_origins != "*" else "*"
CORS(app, resources={r"/api/*": {"origins": _origins}})

# --- Rate limiting ---
# Per-IP limits on auth and provisioning endpoints to slow brute-force / token-stuffing attacks.
# In production set RATE_LIMIT_STORAGE_URI to a Redis URL ("redis://redis:6379/0") so limits are
# shared across worker processes. The in-memory backend is fine for dev / single-worker setups.
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],  # no global default; we annotate sensitive routes individually
    storage_uri=os.getenv("RATE_LIMIT_STORAGE_URI", "memory://"),
)

# --- LIVENESS / READINESS ---
@app.route("/api/health", methods=["GET"])
def health_route():
    """Liveness probe: returns 200 as long as the process is running."""
    return jsonify({"status": "ok"}), 200

@app.route("/api/ready", methods=["GET"])
def ready_route():
    """Readiness probe: verifies the API can reach its critical dependencies (DB)."""
    checks = {"db": False}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["db"] = True
    except Exception as e:
        return jsonify({"status": "not_ready", "checks": checks, "error": str(e)}), 503
    return jsonify({"status": "ready", "checks": checks}), 200

# --- AUTHENTICATION ROUTES ---
@app.route("/api/auth/signup", methods=["POST"])
@limiter.limit("5 per hour;3 per minute")
def signup_route():
    return signup()

@app.route("/api/auth/login", methods=["POST"])
@limiter.limit("10 per minute;30 per hour")
def login_route():
    return login()

@app.route("/api/auth/refresh", methods=["POST"])
@jwt_required(refresh=True)
@limiter.limit("60 per minute")
def refresh_route():
    return refresh()

@app.route("/api/auth/logout", methods=["POST"])
@jwt_required(verify_type=False)
def logout_route():
    return logout()

@app.route("/api/auth/change-password", methods=["POST"])
@jwt_required()
@limiter.limit("5 per minute;20 per hour")
def change_password_route():
    return change_password()

# --- DEVICE PROVISIONING ROUTES ---
@app.route('/api/devices/provision', methods=["POST"])
@jwt_required()
@limiter.limit("10 per minute;100 per hour")
def request_provisioning_token_route():
    return provision_device()

@app.route('/api/devices/activate', methods=["POST"])
@limiter.limit("20 per minute;200 per hour")
def activate_device_route():
    return activate_device()

@app.route('/api/devices/by_user', methods=["GET"])
@jwt_required()
def get_devices_route():
    return get_devices_for_user()

@app.route('/api/devices/<int:device_id>/name', methods=["PUT"])
@jwt_required()
def api_update_device_name(device_id: int):
    return update_device_name_route(device_id)

@app.route('/api/devices/<int:device_id>', methods=["DELETE"])
@jwt_required()
def api_delete_device(device_id: int):
    return delete_device_route(device_id)

@app.route('/api/assets/link_sensor', methods=["POST"])
@jwt_required()
def link_sensor_to_asset_route():
    return link_sensor_to_asset()

# --- ASSET MANAGEMENT ROUTES ---
@app.route('/api/assets/add', methods=["POST"])
@jwt_required()
def add_asset_route():
    return add_asset_to_db()

@app.route('/api/assets/by_organization', methods=["GET"])
@jwt_required()
def get_assets_by_organization_route():
    return get_assets_by_organization()

@app.route('/api/assets/<int:asset_id>', methods=["PUT"])
@jwt_required()
def api_update_asset(asset_id: int):
    return update_asset_route(asset_id)

@app.route('/api/assets/<int:asset_id>', methods=["DELETE"])
@jwt_required()
def api_delete_asset(asset_id: int):
    return delete_asset_route(asset_id)

def _parse_iso(value):
    """Best-effort ISO-8601 parser used for analytics/report query strings.
    Returns a tz-aware datetime, or None if the input is missing/invalid."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None

@app.get("/api/analytics/spectrum/<int:asset_id>")
@jwt_required()
def get_asset_spectrum_route(asset_id: int):
    until = _parse_iso(request.args.get("until"))
    try:
        limit = int(request.args.get("limit", 500))
    except (TypeError, ValueError):
        limit = 500
    return get_asset_spectrum(asset_id, limit=limit, until=until)

@app.get("/api/analytics/health/<int:asset_id>")
@jwt_required()
def get_asset_health_route(asset_id: int):
    from_ts = _parse_iso(request.args.get("from"))
    to_ts = _parse_iso(request.args.get("to"))
    try:
        limit = int(request.args.get("limit", 50))
    except (TypeError, ValueError):
        limit = 50
    return get_asset_health(asset_id, limit=limit, from_ts=from_ts, to_ts=to_ts)

@app.route("/api/assets/baseline/<int:asset_id>", methods=["GET", "POST", "DELETE"])
@jwt_required()
def handle_asset_baseline(asset_id: int):
    if request.method == "POST":
        return set_asset_baseline(asset_id)
    if request.method == "DELETE":
        return reset_baseline_route(asset_id)

    # GET
    baseline = get_asset_baseline(asset_id)
    if not baseline:
        return jsonify({"error": "No baseline found"}), 404
    return jsonify(baseline), 200

# --- EVENT MANAGEMENT ROUTES ---
@app.route('/api/alerts/recent', methods=['GET'])
@jwt_required()
def get_recent_alerts_route():
    # Scope the history log to the caller's organization. Without this filter
    # users from one tenant could see events from every other tenant.
    claims = get_jwt() or {}
    organization = claims.get("organization")
    if not organization:
        return jsonify({"error": "Organization claim missing from token"}), 403
    try:
        limit = int(request.args.get("limit", 20))
    except (TypeError, ValueError):
        limit = 20
    try:
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        offset = 0
    alerts = get_recent_alerts(organization=organization, limit=limit, offset=offset)
    return jsonify(alerts), 200

# --- MAINTENANCE ROUTES ---
@app.route('/api/tickets/create', methods=["POST"])
@jwt_required()
def create_ticket_route():
    return create_ticket()

@app.route('/api/tickets/by_org', methods=["GET"])
@jwt_required()
def get_org_tickets_route():
    return get_org_tickets()

@app.route('/api/tickets/<int:ticket_id>', methods=["DELETE"])
@jwt_required()
def api_delete_ticket(ticket_id: int):
    return delete_ticket_route(ticket_id)

@app.route('/api/tickets/<int:ticket_id>/status', methods=["PATCH"])
@jwt_required()
def api_update_ticket_status(ticket_id: int):
    return update_ticket_status_route(ticket_id)

@app.route('/api/users/assignable', methods=["GET"])
@jwt_required()
def api_get_assignable_users():
    return get_assignable_users_route()

# --- REPORTS ROUTES ---
@app.route('/api/reports/reliability', methods=['GET'])
@jwt_required()
def call_get_reliability_report_route():
    return get_reliability_report_route()

@app.route('/api/reports/alert_resolution', methods=['GET'])
@jwt_required()
def call_get_alert_resolution_report_route():
    return get_alert_resolution_report_route()

@app.route('/api/reports/fft_export/<int:asset_id>', methods=['GET'])
@jwt_required()
def call_get_fft_export_route(asset_id: int):
    return get_fft_export_route(asset_id)

@app.route('/api/reports/reliability/export', methods=['GET'])
@jwt_required()
def call_get_reliability_export_route():
    return get_reliability_export_route()

@app.route('/api/reports/alert_resolution/export', methods=['GET'])
@jwt_required()
def call_get_alert_resolution_export_route():
    return get_alert_resolution_export_route()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000) # Start Flask (dev). In production, use WSGI server and run mqtt client separately.