"""add graph community snapshots for global-search time travel (W7 temporal evolution)

Revision ID: 20260821_graph_community_snapshots
Revises: 20260820_add_graph_community_parent
Create Date: 2026-08-21 00:00:00.000000

W7: when community detection replaces a workspace's live rows the outgoing
generation is archived into ``graph_community_snapshots`` with a validity
interval so ``global_search(as_of=...)`` can synthesize from the generation
that was active at that instant. See docs/architecture/TEMPORAL_EVOLUTION.md.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260821_graph_community_snapshots"
down_revision: Union[str, Sequence[str], None] = "20260820_add_graph_community_parent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("graph_community_snapshots"):
        return
    op.create_table(
        "graph_community_snapshots",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=True),
        sa.Column("node_ids", sa.JSON(), nullable=True),
        sa.Column("parent_label", sa.String(), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invalid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_graph_community_snapshots_workspace",
        "graph_community_snapshots",
        ["workspace_id"],
    )
    op.create_index(
        "ix_graph_community_snapshots_invalid_at",
        "graph_community_snapshots",
        ["invalid_at"],
    )


def downgrade() -> None:
    if not _table_exists("graph_community_snapshots"):
        return
    op.drop_index("ix_graph_community_snapshots_invalid_at", "graph_community_snapshots")
    op.drop_index("ix_graph_community_snapshots_workspace", "graph_community_snapshots")
    op.drop_table("graph_community_snapshots")
