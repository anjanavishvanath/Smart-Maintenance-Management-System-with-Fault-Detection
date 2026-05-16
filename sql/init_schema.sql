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

-- refresh tokens (issuance tracking)
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id SERIAL PRIMARY KEY,
    jti TEXT UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- JWT blocklist: revoked JTIs for BOTH access and refresh tokens.
-- The flask-jwt-extended `token_in_blocklist_loader` queries this table.
CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti TEXT PRIMARY KEY,
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_revoked_tokens_expires
    ON revoked_tokens (expires_at);

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
-- `deleted_at` enables soft-delete: assets disappear from the UI but their
-- sensor_data, events, and ticket history are preserved for audit/reporting.
CREATE TABLE IF NOT EXISTS assets (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    max_rpm INTEGER NOT NULL DEFAULT 0,
    power FLOAT NOT NULL DEFAULT 0,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_assets_active
    ON assets (organization)
    WHERE deleted_at IS NULL;

-- devices
-- `last_seen` is stamped by the MQTT ingestor whenever a metrics batch lands,
-- and is used by the UI to show online/offline status without scanning sensor_data.
CREATE TABLE IF NOT EXISTS devices (
    id SERIAL PRIMARY KEY,
    device_mac TEXT UNIQUE NOT NULL,      -- The permanent physical ID
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_name TEXT,
    os_version TEXT,
    mqtt_password TEXT NOT NULL,
    asset_id INTEGER REFERENCES assets(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen TIMESTAMPTZ
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

-- asset_health_metrics
-- One row per processed batch (~1 per second per asset). The Tier 1 columns
-- (velocity_rms_*, kurtosis_*, crest_factor_total, mahalanobis_distance) feed
-- the ISO-aligned severity metric and the Mahalanobis-distance scorer; see
-- backend/app/processing.py and backend/app/mqtt_ingestor.py.
CREATE TABLE asset_health_metrics (
    time TIMESTAMPTZ NOT NULL,
    asset_id INT NOT NULL,
    -- Acceleration features (g)
    rms_x FLOAT,
    rms_y FLOAT,
    rms_z FLOAT,
    rms_total FLOAT,
    dom_freq_x FLOAT,
    dom_freq_y FLOAT,
    dom_freq_z FLOAT,
    peak_to_peak_z FLOAT,
    -- Tier 1: velocity RMS in mm/s, ISO 10816/20816 band (10 Hz - Nyquist)
    velocity_rms_x FLOAT,
    velocity_rms_y FLOAT,
    velocity_rms_z FLOAT,
    velocity_rms_total FLOAT,
    -- Tier 1: impulsiveness features (dimensionless)
    kurtosis_x FLOAT,            -- excess kurtosis; Gaussian = 0
    kurtosis_y FLOAT,
    kurtosis_z FLOAT,
    crest_factor_total FLOAT,    -- peak / RMS; pure sine ~= 1.41
    -- Tier 1: multivariate anomaly score (D^2, ~chi-square with k DoF)
    mahalanobis_distance FLOAT,
    -- Severity + diagnosis
    condition_score INT,          -- 0 Healthy, 1 Warning, 2 Critical
    diagnosis TEXT DEFAULT 'Healthy'
);
-- Convert to hypertable for TimescaleDB performance
SELECT create_hypertable('asset_health_metrics', 'time');
CREATE INDEX IF NOT EXISTS idx_asset_health_time ON asset_health_metrics (asset_id, time DESC);

-- asset_baselines
-- The legacy per-axis means/stds are still populated for the old z-score
-- fallback path and for dashboard widgets that consume them directly. The
-- mahalanobis_baseline JSONB holds the new feature-vector mean + inverse
-- covariance matrix used by the Tier 1 scorer (see db.calculate_and_set_baseline).
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
    mean_dom_freq_x FLOAT DEFAULT 0.0,
    std_dom_freq_x FLOAT DEFAULT 0.0,
    mean_dom_freq_y FLOAT DEFAULT 0.0,
    std_dom_freq_y FLOAT DEFAULT 0.0,
    mean_dom_freq_z FLOAT DEFAULT 0.0,
    std_dom_freq_z FLOAT DEFAULT 0.0,
    calibrated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Tier 1: { feature_names: [...], mean: [...], cov_inv: [[...]], n_samples: int }
    mahalanobis_baseline JSONB
);

CREATE TABLE asset_events (
    id SERIAL PRIMARY KEY,
    asset_id INTEGER REFERENCES assets(id) ON DELETE CASCADE,
    start_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP WITH TIME ZONE, -- NULL if currently active
    severity INTEGER, -- 1 for Warning, 2 for Critical
    initial_diagnosis TEXT,
    max_z_score FLOAT
);

CREATE INDEX idx_asset_events_active ON asset_events (asset_id) WHERE end_time IS NULL;

-- Statuses: 'open', 'in_progress', 'resolved', 'closed'
-- Priorities: 1 (Low) to 4 (Urgent)
CREATE TABLE IF NOT EXISTS maintenance_tickets (
    id SERIAL PRIMARY KEY,
    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    event_id INTEGER REFERENCES asset_events(id) ON DELETE SET NULL, -- Optional link to an anomaly
    created_by INTEGER NOT NULL REFERENCES users(id),
    assigned_to INTEGER REFERENCES users(id), -- The technician/engineer assigned
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    priority INTEGER DEFAULT 1,
    due_date TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- For tracking communication or updates on a specific ticket
CREATE TABLE IF NOT EXISTS ticket_logs (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES maintenance_tickets(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    log_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tickets_asset ON maintenance_tickets(asset_id);
CREATE INDEX idx_tickets_status ON maintenance_tickets(status);

-- Audit log: who did what to which entity, with optional JSON metadata.
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    organization TEXT,
    action TEXT NOT NULL,
    entity TEXT,
    entity_id TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs (action, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs (entity, entity_id, created_at DESC);