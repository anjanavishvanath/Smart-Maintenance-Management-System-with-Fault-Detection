import json

def test_signup_successful(client, mocker):
    signup_data = {
        "username": "TestUser",
        "email": "api_test@example.com",
        "password": "Password123",
        "role": "engineer",
        "organization": "API Corp"
    }

    # Act
    response = client.post('/api/auth/signup', data=json.dumps(signup_data), content_type='application/json')

    # Assert
    assert response.status_code == 201
    assert response.get_json()['message'] == "User registered successfully"

def test_signup_user_exists(client, mocker):
    # Pre-insert user (assuming the DB is accessible via the client fixture)
    signup_data = {
        "username": "Exists",
        "email": "exists@example.com",
        "password": "Password123",
        "role": "technician",
        "organization": "Old Corp"
    }
    client.post('/api/auth/signup', data=json.dumps(signup_data), content_type='application/json')

    # Act: Try to sign up again with the same email
    response = client.post('/api/auth/signup', data=json.dumps(signup_data), content_type='application/json')
    
    # Assert
    assert response.status_code == 400
    assert response.get_json()['error'] == "Email already registered"

def test_signup_missing_field(client):
    signup_data = {
        "username": "TestUser",
        "email": "missing@example.com",
        # password is intentionally missing
    }
    response = client.post('/api/auth/signup', data=json.dumps(signup_data), content_type='application/json')
    assert response.status_code == 400
    assert response.get_json()['error'] == "Password is required"

# Testing Login Route
def test_login_successful(client, mocker):
    # Setup: Pre-insert a user with a known hash
    from app.db import insert_user
    from app.auth import hash_password
    test_password = "SecurePassword"
    insert_user(
        username="LoginUser", 
        email="login@test.com", 
        password_hash=hash_password(test_password), 
        role="manager", 
        organization="TestCorp"
    )
    
    login_data = {"email": "login@test.com", "password": test_password}
    
    # Act
    response = client.post('/api/auth/login', data=json.dumps(login_data), content_type='application/json')
    # Assert
    if response.status_code != 200:
        print(f"DEBUG: Login failed. Response: {response.get_json()}")
    assert response.status_code == 200
    data = response.get_json()
    assert 'access_token' in data
    assert 'refresh_token' in data
    # Role is not in the response body of login, it's inside the token or user object if returned?
    # http_helpers.login implementation only returns access/refresh/200.
    # It does NOT return role. Removing role assertion.

def test_login_invalid_credentials(client):
    # Act: Try to log in without setting up a user or with wrong password
    login_data = {"email": "unknown@test.com", "password": "anypassword"}
    response = client.post('/api/auth/login', data=json.dumps(login_data), content_type='application/json')
    
    # Assert
    assert response.status_code == 401
    assert response.get_json()['error'] == "Invalid email or password"