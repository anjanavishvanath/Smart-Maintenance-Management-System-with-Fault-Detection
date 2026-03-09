import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from http_helpers import signup, login, refresh, logout
from flask_jwt_extended import JWTManager, jwt_required
from device_helpers import provision_device, activate_device, link_sensor_to_asset, get_devices_for_user, set_asset_baseline 
from asset_helpers import add_asset_to_db, get_assets_by_organization
from db import get_asset_spectrum, get_asset_health, get_asset_baseline, get_recent_alerts
from tickets_routes import create_ticket, get_org_tickets, get_assignable_users_route, delete_ticket_route, update_ticket_status_route

load_dotenv()
app = Flask(__name__) 
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "my-secret-key")
app.config["JWT_ALGORITHM"] = "HS256"
jwt = JWTManager(app)

CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- AUTHENTICATION ROUTES ---
@app.route("/api/auth/signup", methods=["POST"])
def signup_route():
    return signup()

@app.route("/api/auth/login", methods=["POST"])
def login_route():
    return login()

@app.route("/api/auth/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh_route():
    return refresh()

@app.route("/api/auth/logout", methods=["POST"])
def logout_route():
    return logout()

# --- DEVICE PROVISIONING ROUTES ---
@app.route('/api/devices/provision', methods=["POST"])
@jwt_required()
def request_provisioning_token_route():
    return provision_device()

@app.route('/api/devices/activate', methods=["POST"])
def activate_device_route():
    return activate_device()

@app.route('/api/devices/by_user', methods=["GET"])
@jwt_required()
def get_devices_route():
    return get_devices_for_user()

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

@app.get("/api/analytics/spectrum/<int:asset_id>")
@jwt_required()
def get_asset_spectrum_route(asset_id: int):
    return get_asset_spectrum(asset_id)

@app.get("/api/analytics/health/<int:asset_id>")
@jwt_required()
def get_asset_health_route(asset_id: int):
    return get_asset_health(asset_id)

@app.route("/api/assets/baseline/<int:asset_id>", methods=["GET", "POST"])
@jwt_required()
def handle_asset_baseline(asset_id: int):
    if request.method == "POST":
        return set_asset_baseline(asset_id)
    
    # It's a GET request
    baseline = get_asset_baseline(asset_id)
    if not baseline:
        return jsonify({"error": "No baseline found"}), 404
    return jsonify(baseline), 200

# --- EVENT MANAGEMENT ROUTES ---
@app.route('/api/alerts/recent', methods=['GET'])
@jwt_required()
def get_recent_alerts_route():
    alerts = get_recent_alerts()
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000) # Start Flask (dev). In production, use WSGI server and run mqtt client separately.