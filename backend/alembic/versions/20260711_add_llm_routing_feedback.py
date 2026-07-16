"""add llm_routing_feedback table

Revision ID: 20260711_llm_routing_feedback
Revises: 20260630_sandbox_tables
Create Date: 2026-07-11 00:00:00.000000

Adds the ``llm_routing_feedback`` table backing the learning-based LLM
router's persistence layer. Each row is one observed routing outcome used to
train per-model satisfaction predictors. Survives process restarts so learned
data is not lost. The ``prompt_features`` column stores the 10 features
captured at route time so training can reproduce them.

Uses the guarded ``_table_exists`` pattern (SQLite hybrid DB compatibility —
the dev DB has schema advanced via ``Base.metadata.create_all`` while alembic
bookkeeping lags; unguarded migrations fail with "table already exists").
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260711_llm_routing_feedback"
down_revision: Union[str, Sequence[str], None] = "20260630_sandbox_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("llm_routing_feedback"):
        print("    [skip] llm_routing_feedback already exists")
        return

    op.create_table(
        "llm_routing_feedback",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("routing_result_id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("task_type", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("quality_satisfied", sa.Boolean(), nullable=False),
        sa.Column("cost_within_budget", sa.Boolean(), nullable=False),
        sa.Column("user_satisfaction", sa.Float(), nullable=True),
        sa.Column("actual_cost", sa.Float(), nullable=True),
        sa.Column("actual_latency_ms", sa.Float(), nullable=True),
        sa.Column("prompt_features", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_llm_routing_feedback_routing_result_id"),
        "llm_routing_feedback",
        ["routing_result_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_routing_feedback_tenant_id"),
        "llm_routing_feedback",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_routing_feedback_task_type"),
        "llm_routing_feedback",
        ["task_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_routing_feedback_model_id"),
        "llm_routing_feedback",
        ["model_id"],
        unique=False,
    )
    op.create_index(
        "ix_llm_routing_fb_tenant_task",
        "llm_routing_feedback",
        ["tenant_id", "task_type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_llm_routing_fb_tenant_task", table_name="llm_routing_feedback"
    )
    op.drop_index(
        op.f("ix_llm_routing_feedback_model_id"),
        table_name="llm_routing_feedback",
    )
    op.drop_index(
        op.f("ix_llm_routing_feedback_task_type"),
        table_name="llm_routing_feedback",
    )
    op.drop_index(
        op.f("ix_llm_routing_feedback_tenant_id"),
        table_name="llm_routing_feedback",
    )
    op.drop_index(
        op.f("ix_llm_routing_feedback_routing_result_id"),
        table_name="llm_routing_feedback",
    )
    op.drop_table("llm_routing_feedback")
