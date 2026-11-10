-- Goal 9 durable TokenUsage settlement — reversible DDL
-- NOT APPLIED by this branch. Owner applies after review; scratch tests use
-- SQLAlchemy create_all from the current model.
--
-- Why no Alembic revision file: the current backend/alembic/versions tree has
-- 42 divergent heads and no single safe down_revision; adding a 43rd head
-- would not be a reliable production migration. The exact reversible DDL is
-- provided here and the owner applies it with the normal migration process.

-- PostgreSQL
ALTER TABLE token_usage ALTER COLUMN agent_id DROP NOT NULL;
ALTER TABLE token_usage ALTER COLUMN tenant_id DROP NOT NULL;
ALTER TABLE token_usage ALTER COLUMN model_name DROP NOT NULL;

ALTER TABLE token_usage ADD COLUMN provider_id VARCHAR(100);
ALTER TABLE token_usage ADD COLUMN request_id VARCHAR(255);
ALTER TABLE token_usage ADD COLUMN attempt_id VARCHAR(255);
CREATE UNIQUE INDEX uq_token_usage_attempt_id
    ON token_usage (attempt_id);
CREATE INDEX ix_token_usage_provider_id ON token_usage (provider_id);
CREATE INDEX ix_token_usage_request_id ON token_usage (request_id);

ALTER TABLE token_usage ADD COLUMN pricing_status VARCHAR(20)
    NOT NULL DEFAULT 'priced';
CREATE INDEX ix_token_usage_pricing_status ON token_usage (pricing_status);

-- Existing rows default to 'priced' (their historical cost is unchanged).
-- New settlement writes 'unknown' when pricing is unavailable, 'free' for
-- known 0.0, and 'priced' otherwise.

-- SQLite:
--   ADD COLUMN / CREATE INDEX statements above work directly. Dropping
--   NOT NULL on agent_id/tenant_id/model_name requires the standard table
--   rebuild (Alembic batch_alter_table or a create-copy-swap with the
--   existing data). cost_usd was already nullable in SQLite.

-- Down (reversible; only if no NULLs/unknown rows remain in the reverted
-- columns):
DROP INDEX IF EXISTS ix_token_usage_pricing_status;
DROP INDEX IF EXISTS ix_token_usage_request_id;
DROP INDEX IF EXISTS ix_token_usage_provider_id;
DROP INDEX IF EXISTS uq_token_usage_attempt_id;
ALTER TABLE token_usage DROP COLUMN pricing_status;
ALTER TABLE token_usage DROP COLUMN attempt_id;
ALTER TABLE token_usage DROP COLUMN request_id;
ALTER TABLE token_usage DROP COLUMN provider_id;
ALTER TABLE token_usage ALTER COLUMN model_name SET NOT NULL;
ALTER TABLE token_usage ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE token_usage ALTER COLUMN agent_id SET NOT NULL;
