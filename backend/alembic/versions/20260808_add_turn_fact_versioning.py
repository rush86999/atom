"""add git-like versioning columns to turn_facts

Revision ID: 20260808_add_turn_fact_versioning
Revises: 20260808_add_confidence_provenance
Create Date: 2026-08-08 02:00:00.000000

P3d/W2 — git-like versioning for durable facts (plan v4):

A fact's history is a chain of commits. ``parent_id`` links a superseding row
to the row it replaced (mirrors the existing status=superseded lifecycle);
the other columns describe who/what authored this version and why it changed.
Oracle confirmation of a fact is recorded as a commit authored by the oracle
(``author_type='oracle'``). See docs/architecture/ORACLE_VERIFICATION.md.

Columns are created idempotently so this is safe on databases that received
the schema via ``create_all`` as well as via the migration chain.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260808_add_turn_fact_versioning"
down_revision: Union[str, Sequence[str], None] = "20260808_add_confidence_provenance"
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


_VERSIONING_COLUMNS = (
    ("parent_id", sa.String()),
    ("commit_message", sa.Text()),
    ("author_type", sa.String(length=16)),
    ("branch_name", sa.String(length=64)),
    ("diff_summary", sa.Text()),
)

_INDEXES = {
    "ix_turn_facts_parent_id": ("turn_facts", ["parent_id"]),
    "ix_turn_facts_author_type": ("turn_facts", ["author_type"]),
}


def upgrade() -> None:
    if not _table_exists("turn_facts"):
        return
    missing = [
        (name, typ)
        for name, typ in _VERSIONING_COLUMNS
        if not _column_exists("turn_facts", name)
    ]
    with op.batch_alter_table("turn_facts") as batch_op:
        for col_name, col_type in missing:
            batch_op.add_column(sa.Column(col_name, col_type, nullable=True))
    for index_name, (table, cols) in _INDEXES.items():
        if _column_exists(table, cols[0]) and not _index_exists(table, index_name):
            op.create_index(index_name, table, cols)


def downgrade() -> None:
    if not _table_exists("turn_facts"):
        return
    for index_name, (table, cols) in reversed(list(_INDEXES.items())):
        if _index_exists(table, index_name):
            op.drop_index(index_name, table_name=table)
    existing = [
        name for name, _ in _VERSIONING_COLUMNS
        if _column_exists("turn_facts", name)
    ]
    with op.batch_alter_table("turn_facts") as batch_op:
        for col_name in reversed(existing):
            batch_op.drop_column(col_name)
