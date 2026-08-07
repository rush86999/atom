"""add scaling_operations table

Revision ID: 20260807d_add_scaling_operations
Revises: 20260807_merge_heads
Create Date: 2026-08-07 09:00:00.000000

Adds ``scaling_operations`` backing ``ScalingOperation`` (fleet scaling audit
trail). The model was missing entirely, so ``FleetScalerService`` silently
dropped every persist/read. Guarded: skips cleanly when the table already
exists (Personal Edition creates schema via ``create_all``).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260807d_add_scaling_operations"
down_revision: Union[str, Sequence[str], None] = "20260807c_restore_user_2fa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("scaling_operations"):
        print("    [skip] scaling_operations already exists")
        return

    op.create_table(
        "scaling_operations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("chain_id", sa.String(), nullable=False),
        sa.Column("proposal_id", sa.String(), nullable=True),
        sa.Column("operation_type", sa.String(50), nullable=False),
        sa.Column("from_size", sa.Integer(), nullable=False),
        sa.Column("to_size", sa.Integer(), nullable=False),
        sa.Column("agents_added", sa.JSON(), nullable=True),
        sa.Column("agents_removed", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["chain_id"], ["delegation_chains.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scaling_operations_chain_started",
        "scaling_operations",
        ["chain_id", "started_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scaling_operations_chain_id"),
        "scaling_operations",
        ["chain_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scaling_operations_proposal_id"),
        "scaling_operations",
        ["proposal_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scaling_operations_status"),
        "scaling_operations",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    if not _table_exists("scaling_operations"):
        return
    op.drop_index(op.f("ix_scaling_operations_status"), table_name="scaling_operations")
    op.drop_index(op.f("ix_scaling_operations_proposal_id"), table_name="scaling_operations")
    op.drop_index(op.f("ix_scaling_operations_chain_id"), table_name="scaling_operations")
    op.drop_index("ix_scaling_operations_chain_started", table_name="scaling_operations")
    op.drop_table("scaling_operations")
