"""turn facts: source-attribution columns (epistemic_type, sensitivity)

Revision ID: 20260821_turn_facts_source_attribution
Revises: 20260821_graph_community_snapshots
Create Date: 2026-08-21 00:00:00.000000

Source-attribution memory hardening (P0.4 §7 re-ranked plan):
- ``epistemic_type``: "stated" (a source said it) vs "inferred" (the agent
  concluded it). Recall may prefer stated over inferred — attribution
  outranks confidence (survey §7.3).
- ``sensitivity``: P4 data-taint vocabulary on facts so downstream consumers
  can align fact handling with document sensitivity. Enforcement is a
  separate change; this column enables it.

Guarded for the hybrid SQLite/PostgreSQL setup.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260821_turn_facts_source_attribution"
down_revision: Union[str, Sequence[str], None] = "20260821_graph_community_snapshots"
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


def upgrade() -> None:
    if not _table_exists("turn_facts"):
        return
    with op.batch_alter_table("turn_facts") as batch_op:
        if not _column_exists("turn_facts", "epistemic_type"):
            batch_op.add_column(
                sa.Column("epistemic_type", sa.String(length=16),
                          nullable=False, server_default="stated")
            )
        if not _column_exists("turn_facts", "sensitivity"):
            batch_op.add_column(
                sa.Column("sensitivity", sa.String(length=16),
                          nullable=False, server_default="internal")
            )


def downgrade() -> None:
    if not _table_exists("turn_facts"):
        return
    with op.batch_alter_table("turn_facts") as batch_op:
        if _column_exists("turn_facts", "sensitivity"):
            batch_op.drop_column("sensitivity")
        if _column_exists("turn_facts", "epistemic_type"):
            batch_op.drop_column("epistemic_type")
