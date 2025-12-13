# Fixtures and configuration
import os
import pytest
from unittest import mock
from app.main import app as flask_app
from sqlalchemy import create_engine, text
from app.db import engine

# --- 1. Fixture for Test Database Engine ---
@pytest.fixture(scope="session")
def db_engine():
    # Use a file-based SQLite database for robust persistence in tests
    test_db_path = "/tmp/test_db.sqlite"
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
        
    test_engine = create_engine(
        f"sqlite:///{test_db_path}", 
        future=True
    )

    # Patch the engine in app.db so the app code uses our test DB
    # Also patch 'db.engine' because http_helpers imports from 'db', not 'app.db'
    with mock.patch("app.db.engine", test_engine), \
         mock.patch("db.engine", test_engine):
        with test_engine.connect() as conn:
            # SQLite compatible DDL
            conn.execute(text("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'technician', 
                    organization TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            conn.execute(text("""
                CREATE TABLE refresh_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    jti TEXT UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    revoked BOOLEAN NOT NULL DEFAULT 0,
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            conn.commit()
        yield test_engine

# --- 2. Fixture for Flask Test Client ---
@pytest.fixture(scope="session")
def client(db_engine):
    # Override the application's real engine with the test engine
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as client:
        yield client

# --- 3. Fixture to Clean DB After Each Test ---
@pytest.fixture(autouse=True)
def clean_db(db_engine):
    yield # Test runs here
    # Teardown after test
    with db_engine.connect() as conn:
        conn.execute(text("DELETE FROM refresh_tokens;"))
        conn.execute(text("DELETE FROM users;"))
        conn.commit()