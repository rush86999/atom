"""self_consistency_votes: hash_algo column (R83 gap #8)

Revision ID: 20260823_scv_hash_algo
Revises: 20260822_trust_cal_actions
Create Date: 2026-08-23 00:00:00.000000

Tags every ``self_consistency_votes`` row with the canonicalization that
produced its hashes:

- ``"jcs-sha256"``  — RFC 8785 (vendored ``core/llm/jcs.py``), current
  default; numeric equivalence + UTF-16 key ordering.
- ``NULL``          — legacy ``sha256-sortkeys`` rows written before the
  switch (and any future legacy-mode rows are also tagged explicitly;
  only pre-R83 rows rely on the NULL convention).

Hashes under different algorithms are NOT comparable — version, don't
migrate. Kill switch: ``ATOM_SC_HASH_ALGO=sha256-sortkeys``.

Guarded batch pattern for the hybrid SQLite/PostgreSQL setup
(mirrors ``20260821_turn_facts_source_attribution``).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260823_scv_hash_algo"
down_revision: Union[str, Sequence[str], None] = "20260822_trust_cal_actions"
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
    if not _table_exists("self_consistency_votes"):
        return
    with op.batch_alter_table("self_consistency_votes") as batch_op:
        if not _column_exists("self_consistency_votes", "hash_algo"):
            batch_op.add_column(
                sa.Column("hash_algo", sa.String(length=16), nullable=True)
            )


def downgrade() -> None:
    if not _table_exists("self_consistency_votes"):
        return
    with op.batch_alter_table("self_consistency_votes") as batch_op:
        if _column_exists("self_consistency_votes", "hash_algo"):
            batch_op.drop_column("self_consistency_votes", "hash_algo")
