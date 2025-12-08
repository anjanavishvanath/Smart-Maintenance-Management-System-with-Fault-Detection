from flask import Flask
from http_helpers import signup, login, refresh, logout

app = Flask(__name__) 


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