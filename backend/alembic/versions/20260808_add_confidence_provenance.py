"""add confidence provenance columns to browser_audit + agent_reasoning_steps

Revision ID: 20260808_add_confidence_provenance
Revises: 20260808_add_agent_divisions
Create Date: 2026-08-08 01:00:00.000000

P3c/W2 — two-tier confidence provenance (plan v4):

The pre-action match-confidence layer and the reasoning-step trail both need
to record WHICH tier produced a confidence level, or INTERNAL_HIGH would be
indistinguishable from EXTERNAL_VERIFIED (the credibility-laundering gap,
plan H5). These indexed columns let audit/reviewers distinguish internal
self-assessment from oracle re-derivation:

- ``match_level`` — the stored confidence level (high|partial|ambiguous|
  external_verified|external_refuted|needs_external_validation)
- ``match_confidence_provenance`` — "internal" | "oracle" | "self_report"
- ``match_confidence_score`` — raw internal 0.0-1.0 score
- ``external_validated_at`` — when the oracle confirmed (None = not oracle-verified)

Tables/columns are created idempotently so this is safe on databases that
received the schema via ``create_all`` as well as via the migration chain.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260808_add_confidence_provenance"
down_revision: Union[str, Sequence[str], None] = "20260808_add_agent_divisions"
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


def _index_exists(table_name: str, index_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return any(i["name"] == index_name for i in inspector.get_indexes(table_name))


_PROVENANCE_COLUMNS = (
    ("match_level", sa.String(length=24)),
    ("match_confidence_provenance", sa.String(length=16)),
    ("match_confidence_score", sa.Float()),
    ("external_validated_at", sa.DateTime(timezone=True)),
)

_INDEXES = {
    "ix_browser_audit_match_level": ("browser_audit", ["match_level"]),
    "ix_browser_audit_conf_provenance": ("browser_audit", ["match_confidence_provenance"]),
    "ix_reasoning_match_level": ("agent_reasoning_steps", ["match_level"]),
    "ix_reasoning_conf_provenance": ("agent_reasoning_steps", ["match_confidence_provenance"]),
}


def upgrade() -> None:
    for table in ("browser_audit", "agent_reasoning_steps"):
        if not _table_exists(table):
            continue
        missing = [
            (name, typ)
            for name, typ in _PROVENANCE_COLUMNS
            if not _column_exists(table, name)
        ]
        with op.batch_alter_table(table) as batch_op:
            for col_name, col_type in missing:
                batch_op.add_column(sa.Column(col_name, col_type, nullable=True))
    for index_name, (table, cols) in _INDEXES.items():
        if _column_exists(table, cols[0]) and not _index_exists(table, index_name):
            op.create_index(index_name, table, cols)


def downgrade() -> None:
    for index_name, (table, cols) in reversed(list(_INDEXES.items())):
        if _index_exists(table, index_name):
            op.drop_index(index_name, table_name=table)
    for table in ("browser_audit", "agent_reasoning_steps"):
        if not _table_exists(table):
            continue
        existing = [
            name for name, _ in _PROVENANCE_COLUMNS
            if _column_exists(table, name)
        ]
        with op.batch_alter_table(table) as batch_op:
            for col_name in reversed(existing):
                batch_op.drop_column(col_name)
