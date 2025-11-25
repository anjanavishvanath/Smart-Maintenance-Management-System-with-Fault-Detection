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
  created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS device_credentials (
  id SERIAL PRIMARY KEY,
  device_id TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
  username TEXT NOT NULL,
  password_enc TEXT NOT NULL,   -- encrypted (Fernet) or otherwise encrypted blob
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ
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

-- readings - parameters (time-series)
CREATE TABLE IF NOT EXISTS readings_parameters (
  time TIMESTAMPTZ NOT NULL,
  device_id TEXT NOT NULL,
  sample_rate INTEGER,
  samples INTEGER,
  metrics JSONB, -- e.g. {"device_id":"dev000","ts_ms":1763239260000,"sample_rate_hz":1000,"samples":256,"metrics":{"ax_mean_g":0.935537338,"ay_mean_g":0.034338951,"az_mean_g":0.423355103,"ax_rms_g":0.935540127,"ay_rms_g":0.0343999,"az_rms_g":0.423374336,"ax_peak_g":0.941650391,"ay_peak_g":0.039794922,"az_peak_g":0.43359375,"magnitude_rms_g":1.027455357,"magnitude_peak_g":1.035909213}
  PRIMARY KEY (time, device_id)
);

-- readings - raw blocks (time-series)
CREATE TABLE IF NOT EXISTS raw_blocks (
  time TIMESTAMPTZ NOT NULL, -- block capture time (UTC)
  device_id TEXT NOT NULL,
  block_id TEXT NOT NULL, -- device provided id (timestamp-rand)
  sample_rate INTEGER,
  samples INTEGER, -- number of samples in block
  encoding TEXT, --  e.g. "int16_le_axayaz_bin_chunks"
  crc32 BIGINT, -- optional crc32 checksum
  payload BYTEA, -- compressed or raw binary payload (little-endian int16 interleaved)
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (time, device_id, block_id)
);

-- convert readings to hypertable (TimescaleDB)
SELECT create_hypertable('readings_parameters', 'time', if_not_exists => TRUE);
SELECT create_hypertable('raw_blocks', 'time', if_not_exists => TRUE);

-- indexes for quick device/time queries
CREATE INDEX IF NOT EXISTS idx_raw_blocks_device_time ON raw_blocks(device_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_readings_device_time ON readings_parameters(device_id, time DESC);