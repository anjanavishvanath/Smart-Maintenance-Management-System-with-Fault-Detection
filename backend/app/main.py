import os
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from http_helpers import signup, login, refresh, logout
from flask_jwt_extended import JWTManager, jwt_required

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
def refresh_route():
    return refresh()

@app.route("/api/auth/logout", methods=["POST"])
def logout_route():
    return logout()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000) # Start Flask (dev). In production, use WSGI server and run mqtt client separately.