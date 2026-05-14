-- Migration 002: JWT blocklist table for revoking access AND refresh tokens.
--
-- The existing `refresh_tokens` table tracks refresh-token issuance. This new
-- table is the canonical "is this JTI revoked?" lookup used by the
-- flask-jwt-extended token-in-blocklist callback for BOTH token types.
--
-- How to apply:
--   PowerShell:  Get-Content sql/migrations/002_token_blocklist.sql | docker exec -i cm_timescaledb psql -U cm_user -d cm_db
--   bash/zsh:    docker exec -i cm_timescaledb psql -U cm_user -d cm_db < sql/migrations/002_token_blocklist.sql

CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti TEXT PRIMARY KEY,
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index supports a future cleanup job that purges entries past `expires_at`.
CREATE INDEX IF NOT EXISTS idx_revoked_tokens_expires
    ON revoked_tokens (expires_at);
