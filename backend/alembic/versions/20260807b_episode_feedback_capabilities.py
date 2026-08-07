"""add episode_feedback capability columns

Revision ID: 20260807b_episode_feedback_capabilities
Revises: 20260807_mini_app_marketplace
Create Date: 2026-08-07 01:00:00.000000

Adds ``episode_feedback.capability_domain`` / ``capability_name`` columns so
``EpisodeFeedback`` matches the model (RLHF feedback submission + domain
feedback metrics were crashing with TypeError on every call). Both columns are
nullable — no backfill required; existing rows remain valid.

Guarded for the hybrid SQLite/PostgreSQL setup: SQLite column adds use
``op.batch_alter_table`` and both helpers skip cleanly when the table/column
already exists (Personal Edition creates schema via ``create_all`` and its
alembic bookkeeping lags).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260807b_episode_feedback_capabilities"
down_revision: Union[str, Sequence[str], None] = "20260807_mini_app_marketplace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return column_name in [c["name"] for c in inspector.get_columns(table_name)]


def _add_column(table_name: str, column_name: str, column_type: sa.types.TypeEngine) -> None:
    if not _table_exists(table_name):
        print(f"    [skip] {table_name} does not exist")
        return
    if _column_exists(table_name, column_name):
        print(f"    [skip] {table_name}.{column_name} already exists")
        return
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.add_column(sa.Column(column_name, column_type, nullable=True))


def upgrade() -> None:
    _add_column("episode_feedback", "capability_domain", sa.String(100))
    _add_column("episode_feedback", "capability_name", sa.String(100))


def downgrade() -> None:
    for column_name in ("capability_name", "capability_domain"):
        if not _table_exists("episode_feedback"):
            return
        if not _column_exists("episode_feedback", column_name):
            continue
        with op.batch_alter_table("episode_feedback") as batch_op:
            batch_op.drop_column(column_name)
