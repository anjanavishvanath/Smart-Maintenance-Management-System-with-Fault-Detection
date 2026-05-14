-- Migration 003: Add last_seen heartbeat tracking to devices.
--
-- The MQTT ingestor stamps `last_seen` on every metrics batch so the dashboard
-- can show online/offline status without inferring it from the data hypertable.
--
-- How to apply:
--   PowerShell:  Get-Content sql/migrations/003_device_last_seen.sql | docker exec -i cm_timescaledb psql -U cm_user -d cm_db
--   bash/zsh:    docker exec -i cm_timescaledb psql -U cm_user -d cm_db < sql/migrations/003_device_last_seen.sql

ALTER TABLE devices ADD COLUMN IF NOT EXISTS last_seen TIMESTAMPTZ;
