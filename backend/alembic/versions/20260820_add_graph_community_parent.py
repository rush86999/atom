"""add graph community parent lineage column (W2 temporal evolution)

Revision ID: 20260820_add_graph_community_parent
Revises: 20260816_org_ingestion_sharing
Create Date: 2026-08-20 00:00:00.000000

W2 community->hierarchy lineage: ``graph_communities.parent_community_id``
points at the level-(level-1) community with maximal node overlap (see
docs/architecture/TEMPORAL_EVOLUTION.md). Nullable for existing rows.

Guarded for the hybrid SQLite/PostgreSQL setup (SQLite requires
batch_alter_table; dev DB is schema-via-create_all + alembic bookkeeping lags).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260820_add_graph_community_parent"
down_revision: Union[str, Sequence[str], None] = "20260816_org_ingestion_sharing"
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
    if not _table_exists("graph_communities"):
        return
    if _column_exists("graph_communities", "parent_community_id"):
        return
    with op.batch_alter_table("graph_communities") as batch_op:
        batch_op.add_column(sa.Column("parent_community_id", sa.String(), nullable=True))
        batch_op.create_index(
            "ix_graph_communities_parent", ["parent_community_id"]
        )


def downgrade() -> None:
    if not _table_exists("graph_communities"):
        return
    with op.batch_alter_table("graph_communities") as batch_op:
        batch_op.drop_index("ix_graph_communities_parent")
        batch_op.drop_column("parent_community_id")