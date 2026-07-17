"""add hypothesis_trees table

Revision ID: 20260716_add_hypothesis_trees
Revises: 20260712b_federation_persistence
Create Date: 2026-07-16 00:00:00.000000

Adds the ``hypothesis_trees`` table backing the Arbor Hypothesis Tree
Refinement (HTR) framework's DB persistence layer.

Each row is a completed tree session:
  - Denormalised outcome columns (total_nodes, successful_nodes, pruned_nodes,
    total_tokens_used, total_cost_usd, optimization_score, winning_path) enable
    fast analytics queries without unpacking the full JSON.
  - ``tree_snapshot`` stores the full to_dict() output for offline replay,
    cross-session constraint propagation, and auditability.
  - ``negative_constraints`` is also stored top-level so future /create calls
    can inherit constraints from the N most-recent sessions without loading the
    whole snapshot.

Uses the guarded ``_table_exists`` pattern (SQLite hybrid DB compatibility).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_add_hypothesis_trees"
down_revision: Union[str, Sequence[str], None] = "20260712b_federation_persistence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("hypothesis_trees"):
        print("    [skip] hypothesis_trees already exists")
        return

    op.create_table(
        "hypothesis_trees",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("task_description", sa.Text(), nullable=False),
        sa.Column("task_type", sa.String(50), nullable=False, server_default="coding"),
        sa.Column("tier", sa.String(20), nullable=False, server_default="solo"),
        sa.Column("session_id", sa.String(36), nullable=True),
        # Denormalised outcome columns
        sa.Column("total_nodes", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("successful_nodes", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("pruned_nodes", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("total_tokens_used", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("total_cost_usd", sa.Float(), nullable=True, server_default="0"),
        sa.Column("optimization_score", sa.Float(), nullable=True),
        sa.Column("winning_path", sa.JSON(), nullable=True),
        sa.Column("negative_constraints", sa.JSON(), nullable=True),
        # Full tree for replay / audit
        sa.Column("tree_snapshot", sa.JSON(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_hypothesis_trees_tenant_id",
        "hypothesis_trees",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_hypothesis_trees_session",
        "hypothesis_trees",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_hypothesis_trees_tenant_type",
        "hypothesis_trees",
        ["tenant_id", "task_type"],
        unique=False,
    )
    op.create_index(
        "ix_hypothesis_trees_tenant_tier",
        "hypothesis_trees",
        ["tenant_id", "tier"],
        unique=False,
    )
    op.create_index(
        "ix_hypothesis_trees_tenant_created",
        "hypothesis_trees",
        ["tenant_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_hypothesis_trees_tenant_created", table_name="hypothesis_trees")
    op.drop_index("ix_hypothesis_trees_tenant_tier", table_name="hypothesis_trees")
    op.drop_index("ix_hypothesis_trees_tenant_type", table_name="hypothesis_trees")
    op.drop_index("ix_hypothesis_trees_session", table_name="hypothesis_trees")
    op.drop_index("ix_hypothesis_trees_tenant_id", table_name="hypothesis_trees")
    op.drop_table("hypothesis_trees")
