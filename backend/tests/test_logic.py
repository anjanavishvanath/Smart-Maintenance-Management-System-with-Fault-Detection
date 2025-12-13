from app.auth import hash_password, verify_password, build_tokens 
from datetime import timedelta, datetime, timezone
from unittest import mock
import pytest

def test_password_hashing_and_verification():
    password = "MyStrongPassword123"
    pw_hash = hash_password(password)
    
    # Assert 1: Hash is created
    assert isinstance(pw_hash, str)
    assert pw_hash.startswith('$2b$') # Standard bcrypt prefix
    
    # Assert 2: Verification works
    assert verify_password(password, pw_hash) is True
    
    # Assert 3: Wrong password fails
    assert verify_password("WrongPassword", pw_hash) is False

def test_password_length_limit():
    # Test password slightly too long (if 72 byte limit)
    long_password = "a" * 80 # A string that will encode to more than 72 bytes
    
    # Assert: Should raise a ValueError
    with pytest.raises(ValueError, match="Password too long"):
        hash_password(long_password)


def test_token_building(mocker):
    # Mocking JWT functions and expiration times for predictability
    mocker.patch('app.auth.JWT_ACCESS_EXPIRES', 300)
    mocker.patch('app.auth.JWT_REFRESH_EXPIRES', 86400)
    
    identity = {"user_id": 1, "email": "test@test.com", "username": "Tester", "role": "admin"}
    
    from app.main import app
    with app.app_context():
        access, refresh, jti, expires_at = build_tokens(identity)
    
    # Assert: Tokens are strings and we get a JTI and expiration timestamp
    assert isinstance(access, str)
    assert isinstance(refresh, str)
    assert isinstance(jti, str)
    assert isinstance(expires_at, type(datetime.now(timezone.utc)))