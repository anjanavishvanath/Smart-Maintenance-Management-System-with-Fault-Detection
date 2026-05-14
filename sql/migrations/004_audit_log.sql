-- Migration 004: Audit log for security-relevant mutations.
--
-- Captures who did what to which entity, with optional before/after JSON payloads
-- so we can reconstruct state changes after the fact. Hooks fire on:
--   * asset create/update/delete, baseline reset
--   * ticket create/delete/status_change
--   * device rename/delete
--   * password change, login (success/failure)
--
-- How to apply:
--   PowerShell:  Get-Content sql/migrations/004_audit_log.sql | docker exec -i cm_timescaledb psql -U cm_user -d cm_db
--   bash/zsh:    docker exec -i cm_timescaledb psql -U cm_user -d cm_db < sql/migrations/004_audit_log.sql

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    -- user_id is nullable so we can record events for unauthenticated paths (e.g. failed login)
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    organization TEXT,
    action TEXT NOT NULL,         -- e.g. "asset.create", "ticket.delete", "auth.login.success"
    entity TEXT,                  -- "asset" / "device" / "ticket" / "user"
    entity_id TEXT,               -- text so it can hold MAC addresses or numeric ids uniformly
    metadata JSONB,               -- before/after, IP, etc.
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs (action, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs (entity, entity_id, created_at DESC);
