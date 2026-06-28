"""add canvas_type column to canvas_audit

Revision ID: 20260627_canvas_audit_canvas_type
Revises: 20260624_reasoning_verified
Create Date: 2026-06-27 00:00:00.000000

Adds a denormalized `canvas_type` column to the `canvas_audit` table.

Purpose: previously `canvas_type` lived only inside the JSON payload of
`details_json`. 15+ filter sites across the codebase scope queries by
canvas type (e.g. CanvasAudit.canvas_type == "sheets"). Keeping it as a
real indexed column lets those filters work natively; `details_json`
still holds a redundant copy for backward compatibility with any reader
that reads from there.

The new column is nullable because existing rows may not have a
canvas_type embedded in their details_json (e.g. recording-audit rows).
For rows where details_json does carry a canvas_type, we backfill the
column from JSON so the new index is immediately useful.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260627_canvas_audit_canvas_type"
down_revision: Union[str, Sequence[str], None] = "20260624_reasoning_verified"
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
    if not _table_exists("canvas_audit"):
        return

    if not _column_exists("canvas_audit", "canvas_type"):
        with op.batch_alter_table("canvas_audit") as batch_op:
            batch_op.add_column(
                sa.Column("canvas_type", sa.String(length=100), nullable=True)
            )

    # Backfill canvas_type from details_json for existing rows where possible.
    # We do this portably across SQLite/PostgreSQL by reading rows back and
    # issuing parameterized updates. JSON extraction differs by dialect:
    #   - PostgreSQL: details_json->>'canvas_type'
    #   - SQLite: json_extract(details_json, '$.canvas_type')
    # We only backfill rows where the column is still NULL, so re-runs are
    # idempotent and never overwrite a value the application layer has set.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            UPDATE canvas_audit
               SET canvas_type = details_json->>'canvas_type'
             WHERE canvas_type IS NULL
               AND details_json IS NOT NULL
               AND details_json->>'canvas_type' IS NOT NULL
            """
        )
    elif bind.dialect.name == "sqlite":
        op.execute(
            """
            UPDATE canvas_audit
               SET canvas_type = json_extract(details_json, '$.canvas_type')
             WHERE canvas_type IS NULL
               AND details_json IS NOT NULL
               AND json_extract(details_json, '$.canvas_type') IS NOT NULL
            """
        )

    # Index the new column. The index name mirrors the one declared on the
    # ORM model (idx_canvas_audit_canvas_type) so metadata.create_all and
    # alembic agree.
    if not _index_exists("canvas_audit", "idx_canvas_audit_canvas_type"):
        if bind.dialect.name == "postgresql":
            op.execute(
                "CREATE INDEX IF NOT EXISTS idx_canvas_audit_canvas_type "
                "ON canvas_audit (canvas_type)"
            )
        else:
            # SQLite also supports CREATE INDEX IF NOT EXISTS, but go through
            # op.create_index for batch-alter consistency on the SQLite path.
            op.create_index(
                "idx_canvas_audit_canvas_type",
                "canvas_audit",
                ["canvas_type"],
            )


def downgrade() -> None:
    if not _table_exists("canvas_audit"):
        return

    bind = op.get_bind()

    if _index_exists("canvas_audit", "idx_canvas_audit_canvas_type"):
        if bind.dialect.name == "postgresql":
            op.execute("DROP INDEX IF EXISTS idx_canvas_audit_canvas_type")
        else:
            try:
                op.drop_index("idx_canvas_audit_canvas_type", table_name="canvas_audit")
            except Exception:
                pass

    if _column_exists("canvas_audit", "canvas_type"):
        with op.batch_alter_table("canvas_audit") as batch_op:
            batch_op.drop_column("canvas_type")
