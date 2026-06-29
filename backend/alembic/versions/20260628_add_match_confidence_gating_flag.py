"""add match_confidence_gating_enabled column to agent_registry

Revision ID: 20260628_match_confidence_gating
Revises: 20260628_browser_audit_action_target
Create Date: 2026-06-28 00:00:00.000000

Adds an optional per-agent opt-in/opt-out column for the pre-action
match-confidence gating layer (Phase 6 of MATCH_CONFIDENCE.md).

Semantics:
  - NULL (default) → fall through to the global MATCH_CONFIDENCE_FORCE_PROPOSAL
    env flag (shadow mode by default — computation + audit always on,
    gating off).
  - TRUE  → agent opts IN to gating regardless of global flag.
  - FALSE → agent opts OUT of gating (single-misbehaving-agent kill switch).

The column is nullable so existing rows inherit global behavior without
backfill. Reads via AgentRegistry.match_confidence_gating_enabled return
None for legacy rows; the gating helper in tools/browser_tool.py treats
None as "use global".

Uses the guarded batch_alter_table + _column_exists pattern from
20260624_add_turn_facts.py — SQLite hybrid DB compatibility (the dev DB
has schema advanced via Base.metadata.create_all while alembic bookkeeping
lags; unguarded migrations fail with "duplicate column").
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260628_match_confidence_gating"
# Linearizes the two existing heads (browser_audit_action_target and
# 0e360bb1a3d3) by depending on both. Without this, applying the migration
# against a fully-migrated DB would create a third branch. With it, the
# result is a single new head: this revision.
down_revision: Union[str, Sequence[str], None] = (
    "20260628_browser_audit_action_target",
    "0e360bb1a3d3",
)
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


def upgrade() -> None:
    # Fresh DBs create the table (with our column) via
    # Base.metadata.create_all at app start. No-op here.
    if not _table_exists("agent_registry"):
        return

    if not _column_exists("agent_registry", "match_confidence_gating_enabled"):
        with op.batch_alter_table("agent_registry") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "match_confidence_gating_enabled",
                    sa.Boolean(),
                    nullable=True,
                )
            )


def downgrade() -> None:
    if not _table_exists("agent_registry"):
        return

    if _column_exists("agent_registry", "match_confidence_gating_enabled"):
        with op.batch_alter_table("agent_registry") as batch_op:
            batch_op.drop_column("match_confidence_gating_enabled")
