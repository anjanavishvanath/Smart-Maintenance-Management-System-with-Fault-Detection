-- Migration 001: Add soft-delete support to the assets table.
--
-- Run ONCE against an existing database. New installs already get this column
-- via init_schema.sql. Idempotent: safe to re-run.
--
-- How to apply:
--   PowerShell:  Get-Content sql/migrations/001_asset_soft_delete.sql | docker exec -i cm_timescaledb psql -U cm_user -d cm_db
--   bash/zsh:    docker exec -i cm_timescaledb psql -U cm_user -d cm_db < sql/migrations/001_asset_soft_delete.sql
--   Or copy + -f: docker cp sql/migrations/001_asset_soft_delete.sql cm_timescaledb:/tmp/m.sql
--                 docker exec cm_timescaledb psql -U cm_user -d cm_db -f /tmp/m.sql

ALTER TABLE assets ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

-- Partial index so the common "active assets in org" query stays cheap.
CREATE INDEX IF NOT EXISTS idx_assets_active
    ON assets (organization)
    WHERE deleted_at IS NULL;
