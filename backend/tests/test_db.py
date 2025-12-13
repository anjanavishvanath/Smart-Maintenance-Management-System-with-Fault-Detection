from app.db import insert_user, get_user_by_email, insert_refresh_token, revoke_refresh_token, is_refresh_token_revoked

def test_insert_and_retrieve_user(db_engine):
    test_email = "test@example.com"
    # Act: Insert a user
    insert_user(
        username="TestUser", 
        email=test_email, 
        password_hash="test_hash", 
        role="manager", 
        organization="TestOrg"
    )

    # Assert 1: Retrieve the user
    user = get_user_by_email(test_email)
    assert user is not None
    assert user['email'] == test_email
    assert user['role'] == 'manager'
    assert user['organization'] == 'TestOrg'

    # Assert 2: Non-existent user
    non_user = get_user_by_email("nonexistent@test.com")
    assert non_user is None

# Test the insertion of a refresh token and revocation status
def test_refresh_token_db_operations(db_engine):
    insert_user(
        username="TokenUser", 
        email="token@test.com", 
        password_hash="hash", 
        role="tech", 
        organization="TokenCorp"
    )
    user = get_user_by_email("token@test.com")
    user_id = user['id']
    jti_value = "unique_jti_123"
    
    # Test insertion
    insert_refresh_token(jti_value, user_id, "2025-12-31 23:59:59")
    
    # Test checking status (Should not be revoked)
    assert is_refresh_token_revoked(jti_value) is False
    
    # Test revocation
    revoke_refresh_token(jti_value)
    assert is_refresh_token_revoked(jti_value) is True