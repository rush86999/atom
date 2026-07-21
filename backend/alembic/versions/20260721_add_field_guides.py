"""add field_guides table

Revision ID: 20260721_add_field_guides
Revises: 20260716_add_hypothesis_trees
Create Date: 2026-07-21 00:00:00.000000

Adds the ``field_guides`` table backing the Stigmergic Field Guide service.
Each row stores the full Markdown content of one workspace's operational
Field Guide — the agent-curated shared memory injected into system prompts.

One row per workspace (``workspace_id`` unique constraint).  Content is a
TEXT column; ``line_count`` is a denormalised counter for cheap budget checks.

Uses the guarded ``_table_exists`` pattern for SQLite hybrid-DB compatibility.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260721_add_field_guides"
down_revision: Union[str, Sequence[str], None] = "20260716_add_hypothesis_trees"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("field_guides"):
        print("    [skip] field_guides already exists")
        return

    op.create_table(
        "field_guides",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("line_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", name="uq_field_guides_workspace_id"),
    )

    op.create_index(
        op.f("ix_field_guides_workspace_id"),
        "field_guides",
        ["workspace_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_field_guides_workspace_id"), table_name="field_guides")
    op.drop_table("field_guides")
