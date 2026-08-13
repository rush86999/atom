"""restore debug system schema columns

Revision ID: 20260813_restore_debug_schema
Revises: 20260811_stage_router_automation
Create Date: 2026-08-13 13:30:00.000000

Restores columns lost from core/models.py during a refactor (schema drift):
the debug subsystem still references them everywhere.

- debug_insights: resolution_notes, source_event_id, expires_at
  (original definition in 20260206_add_debug_system.py)
- debug_state_snapshots: operation_id, checkpoint_name, diff_from_previous
- debug_metrics: dimensions (metric_type kept, made nullable via model default)

All additive and nullable — safe on SQLite (batch_alter_table) and Postgres.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260813_restore_debug_schema"
down_revision: Union[str, Sequence[str], None] = "20260811_stage_router_automation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def _ensure_column(table_name: str, column_name: str, column: sa.Column) -> None:
    """SQLite-safe additive column (batch_alter_table + exists guard)."""
    if _column_exists(table_name, column_name):
        print(f"    [skip] {table_name}.{column_name} already exists")
        return
    with op.batch_alter_table(table_name) as batch:
        batch.add_column(column)


def upgrade() -> None:
    if _table_exists("debug_insights"):
        _ensure_column("debug_insights", "resolution_notes",
                       sa.Column("resolution_notes", sa.Text(), nullable=True))
        _ensure_column("debug_insights", "source_event_id",
                       sa.Column("source_event_id", sa.String(), nullable=True))
        _ensure_column("debug_insights", "expires_at",
                       sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    else:
        print("    [skip] debug_insights does not exist")

    if _table_exists("debug_state_snapshots"):
        _ensure_column("debug_state_snapshots", "operation_id",
                       sa.Column("operation_id", sa.String(), nullable=True))
        _ensure_column("debug_state_snapshots", "checkpoint_name",
                       sa.Column("checkpoint_name", sa.String(length=100), nullable=True))
        _ensure_column("debug_state_snapshots", "diff_from_previous",
                       sa.Column("diff_from_previous", sa.JSON(), nullable=True))
    else:
        print("    [skip] debug_state_snapshots does not exist")

    if _table_exists("debug_metrics"):
        _ensure_column("debug_metrics", "dimensions",
                       sa.Column("dimensions", sa.JSON(), nullable=True))
    else:
        print("    [skip] debug_metrics does not exist")


def downgrade() -> None:
    # Additive-only restore; nothing to tear down safely (columns may be
    # referenced by live code after this migration).
    pass
