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

-- assets
CREATE TABLE IF NOT EXISTS assets (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    max_rpm INTEGER NOT NULL DEFAULT 0,
    power FLOAT NOT NULL DEFAULT 0,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization TEXT,
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
    asset_id INTEGER REFERENCES assets(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- sensor_data
CREATE TABLE IF NOT EXISTS sensor_data (
    time TIMESTAMPTZ NOT NULL,
    device_mac TEXT NOT NULL,
    asset_id INTEGER, -- We link it to the asset here too for fast queries
    accel_x DOUBLE PRECISION,
    accel_y DOUBLE PRECISION,
    accel_z DOUBLE PRECISION 
);
-- Transform it into a hypertable and partition data by time automatically
SELECT create_hypertable('sensor_data', 'time', if_not_exists => TRUE);
-- Creating an index for fast lookups by device
CREATE INDEX IF NOT EXISTS idx_device_time ON sensor_data (device_mac, time DESC);

CREATE TABLE asset_health_metrics (
    time TIMESTAMPTZ NOT NULL,
    asset_id INT NOT NULL,
    rms_x FLOAT,
    rms_y FLOAT,
    rms_z FLOAT,
    rms_total FLOAT,
    dom_freq_x FLOAT,
    dom_freq_y FLOAT,
    dom_freq_z FLOAT,
    peak_to_peak_z FLOAT,
    condition_score INT -- 0 for Healthy, 1 for Warning, 2 for Critical
);
-- Convert to hypertable for TimescaleDB performance
SELECT create_hypertable('asset_health_metrics', 'time');
CREATE INDEX IF NOT EXISTS idx_asset_health_time ON asset_health_metrics (asset_id, time DESC);

CREATE TABLE asset_baselines (
    asset_id INTEGER PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
    mean_rms_x FLOAT DEFAULT 0.0,
    std_rms_x FLOAT DEFAULT 0.0,
    mean_rms_y FLOAT DEFAULT 0.0,
    std_rms_y FLOAT DEFAULT 0.0,
    mean_rms_z FLOAT DEFAULT 0.0,
    std_rms_z FLOAT DEFAULT 0.0,
    mean_rms_total FLOAT DEFAULT 0.0,
    std_rms_total FLOAT DEFAULT 0.0,
    calibrated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    
);