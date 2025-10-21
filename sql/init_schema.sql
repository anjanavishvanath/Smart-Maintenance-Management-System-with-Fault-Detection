-- sql/init_schema.sql
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- users table
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  username TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'technician', -- admin / manager / engineer / technician
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- refresh tokens table (for revocation & management)
CREATE TABLE IF NOT EXISTS refresh_tokens (
  id SERIAL PRIMARY KEY,
  jti TEXT UNIQUE NOT NULL,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  revoked BOOLEAN NOT NULL DEFAULT FALSE,
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- assets table (grouping of devices)
CREATE TABLE IF NOT EXISTS assets (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  location TEXT,
  created_by INTEGER REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- devices
CREATE TABLE IF NOT EXISTS devices (
  id SERIAL PRIMARY KEY,
  device_id TEXT UNIQUE NOT NULL,
  name TEXT,
  asset_id INTEGER REFERENCES assets(id),
  status TEXT DEFAULT 'offline',
  last_seen TIMESTAMPTZ,
  config JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- alerts / tickets
CREATE TABLE IF NOT EXISTS alerts (
  id SERIAL PRIMARY KEY,
  device_id TEXT,
  asset_id INTEGER,
  severity TEXT,         -- info / warning / critical
  rule TEXT,
  message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  acknowledged_by INTEGER REFERENCES users(id),
  acknowledged_at TIMESTAMPTZ
);

-- readings (time-series)
CREATE TABLE IF NOT EXISTS readings (
  time TIMESTAMPTZ NOT NULL,
  device_id TEXT NOT NULL,
  ax DOUBLE PRECISION,
  ay DOUBLE PRECISION,
  az DOUBLE PRECISION,
  sample_rate INTEGER,
  meta JSONB,
  PRIMARY KEY (time, device_id)
);

-- convert readings to hypertable (TimescaleDB)
SELECT create_hypertable('readings', 'time', if_not_exists => TRUE);
