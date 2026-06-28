"""add action_target column to browser_audit

Revision ID: 20260628_browser_audit_action_target
Revises: 20260627_canvas_audit_canvas_type
Create Date: 2026-06-28 00:00:00.000000

Adds a denormalized `action_target` column to the `browser_audit` table.

Purpose: previously `action_target` was being set as an ad-hoc kwarg in
~10 production/test sites even though it was never declared as a real
column on the BrowserAudit model (the legacy-kwarg drift bug — same
shape as the CanvasAudit canvas_type drift fixed in c5c98078f). The
`browser_routes.py` API response reads `a.action_target` and ~10 test
assertion sites read `audit.action_target`. Keeping it as a real
indexed column lets those reads/filters work natively; `action_params`
/ `metadata_json` continue to hold the rest of the per-action payload.

This migration is the second half of the legacy-kwarg cleanup for the
BrowserAudit/DeviceAudit sibling models. The other half (rewriting
caller kwarg names: workspace_id -> tenant_id, audit_metadata ->
metadata_json, url -> action_target, action -> action_type,
ip_address/user_agent -> metadata_json keys) is done in code and does
not require schema changes because those target columns already exist.

The new column is nullable because existing rows may not have an
action_target value. For rows where `action_params` carries a `url` or
`selector` key, we backfill action_target from JSON so the new index
is immediately useful.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260628_browser_audit_action_target"
down_revision: Union[str, Sequence[str], None] = "20260627_canvas_audit_canvas_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if table_name not in inspector.get_table_names():
        return False
    cols = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in cols


def _index_exists(table_name: str, index_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if table_name not in inspector.get_table_names():
        return False
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    # Fresh DBs create the table (with our column + index) via
    # Base.metadata.create_all at app start. No-op here.
    if not _table_exists("browser_audit"):
        return

    if not _column_exists("browser_audit", "action_target"):
        with op.batch_alter_table("browser_audit") as batch_op:
            batch_op.add_column(
                sa.Column("action_target", sa.Text(), nullable=True)
            )

    # Backfill action_target from action_params for existing rows where possible.
    # We prefer the `url` key, then fall back to `selector`, then `path`.
    # Idempotent: only touches rows where action_target is still NULL.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            UPDATE browser_audit
               SET action_target = COALESCE(
                     action_params->>'url',
                     action_params->>'selector',
                     action_params->>'path'
                   )
             WHERE action_target IS NULL
               AND action_params IS NOT NULL
            """
        )
    elif bind.dialect.name == "sqlite":
        op.execute(
            """
            UPDATE browser_audit
               SET action_target = COALESCE(
                     json_extract(action_params, '$.url'),
                     json_extract(action_params, '$.selector'),
                     json_extract(action_params, '$.path')
                   )
             WHERE action_target IS NULL
               AND action_params IS NOT NULL
            """
        )

    # Index the new column. The index name mirrors the one declared on the
    # ORM model (idx_browser_audit_action_target) so metadata.create_all and
    # alembic agree.
    if not _index_exists("browser_audit", "idx_browser_audit_action_target"):
        if bind.dialect.name == "postgresql":
            op.execute(
                "CREATE INDEX IF NOT EXISTS idx_browser_audit_action_target "
                "ON browser_audit (action_target)"
            )
        else:
            op.create_index(
                "idx_browser_audit_action_target",
                "browser_audit",
                ["action_target"],
            )


def downgrade() -> None:
    if not _table_exists("browser_audit"):
        return

    bind = op.get_bind()

    if _index_exists("browser_audit", "idx_browser_audit_action_target"):
        if bind.dialect.name == "postgresql":
            op.execute("DROP INDEX IF EXISTS idx_browser_audit_action_target")
        else:
            try:
                op.drop_index(
                    "idx_browser_audit_action_target",
                    table_name="browser_audit",
                )
            except Exception:
                pass

    if _column_exists("browser_audit", "action_target"):
        with op.batch_alter_table("browser_audit") as batch_op:
            batch_op.drop_column("action_target")
