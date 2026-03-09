import pytest
import requests

BASE_URL = "http://localhost:5000"

def test_login_success():
    payload = {"email": "demo@example.com", "password": "password123"}
    response = requests.post(f"{BASE_URL}/api/auth/login", json=payload)
    
    assert response.status_code == 200
    assert "access_token" in response.json()
    print("Test Passed: Login successful, Token received.")

if __name__ == "__main__":
    test_login_success()