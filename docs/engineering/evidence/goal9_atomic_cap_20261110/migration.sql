-- Goal 9 atomic hard-stop reservation columns — reversible DDL.
-- NOT APPLIED by this branch. SQLite installs use the existing startup hook
-- (core.sqlite_schema_repair.repair_known_drift ->
-- ensure_token_usage_upgrade), which preserves rows/FKs/custom indexes.
-- PostgreSQL owner applies the equivalent DDL through the normal process.

ALTER TABLE token_usage ADD COLUMN reserved_cost_usd FLOAT;
ALTER TABLE token_usage ADD COLUMN reservation_status VARCHAR(20)
    NOT NULL DEFAULT 'none';
CREATE INDEX ix_token_usage_reservation_status
    ON token_usage (reservation_status);

-- reservation_status:
--   none      legacy/non-reservation row
--   active    conservative pre-dispatch reservation
--   settled   actual settlement (reserved_cost_usd = 0)
--   uncertain missing/unknown actual; reserved bound retained until reconcile
--
-- Down (only after reconciling active/uncertain reservations):
DROP INDEX IF EXISTS ix_token_usage_reservation_status;
ALTER TABLE token_usage DROP COLUMN reservation_status;
ALTER TABLE token_usage DROP COLUMN reserved_cost_usd;
