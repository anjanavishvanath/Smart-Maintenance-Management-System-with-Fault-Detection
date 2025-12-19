CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- users
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'technician', --  manager / engineer / technician
    organization TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- refresh tokens
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id SERIAL PRIMARY KEY,
    jti TEXT UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- provisioning tokens
CREATE TABLE IF NOT EXISTS provisioning_tokens(
    id SERIAL PRIMARY KEY,
    slpt_value TEXT UNIQUE NOT NULL,  -- the generated uuid
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    enrollment_id TEXT NOT NULL,  -- The MAC address / Enrollment ID
    expires_at TIMESTAMPTZ,  -- When the token becomes invalid
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- devices
CREATE TABLE IF NOT EXISTS devices (
    id SERIAL PRIMARY KEY,
    device_mac TEXT UNIQUE NOT NULL,      -- The permanent physical ID
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_name TEXT,
    os_version TEXT,
    mqtt_password TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);