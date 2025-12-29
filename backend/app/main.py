import os
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from http_helpers import signup, login, refresh, logout
from flask_jwt_extended import JWTManager, jwt_required
from device_helpers import provision_device, activate_device, link_sensor_to_asset, get_devices_for_user
from asset_helpers import add_asset_to_db, get_assets_by_organization

load_dotenv()
app = Flask(__name__) 
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "my-secret-key")
app.config["JWT_ALGORITHM"] = "HS256"
jwt = JWTManager(app)

CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5173"]}})

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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000) # Start Flask (dev). In production, use WSGI server and run mqtt client separately.