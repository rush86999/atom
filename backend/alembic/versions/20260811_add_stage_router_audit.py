"""add llm_stage_router_audit table

Revision ID: 20260811_stage_router_audit
Revises: 20260810_supervisor_performance_learning
Create Date: 2026-08-11 12:00:00.000000

Backs the stage router (Switchyard port, core/llm/stage_router.py): one row
per turn-level tier decision, carrying both the router's would-have pick and
the group that actually ran (A/B harness mode). See
docs/architecture/SWITCHYARD_GAP_ANALYSIS.md.

No backfill — the router starts shadow/off and populates from the next turn.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260811_stage_router_audit"
down_revision: Union[str, Sequence[str], None] = "20260810_supervisor_performance_learning"
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


def _ensure_column(table_name: str, column_name: str, column: sa.Column) -> None:
    """SQLite-safe additive column (batch_alter_table + exists guard)."""
    if _column_exists(table_name, column_name):
        print(f"    [skip] {table_name}.{column_name} already exists")
        return
    with op.batch_alter_table(table_name) as batch:
        batch.add_column(column)


def upgrade() -> None:
    if _table_exists("llm_stage_router_audit"):
        print("    [skip] llm_stage_router_audit already exists")
        # Already-created dev DBs get the outcome columns additively.
        _ensure_column("llm_stage_router_audit", "success", sa.Column("success", sa.Boolean(), nullable=True))
        _ensure_column(
            "llm_stage_router_audit", "quality_satisfied", sa.Column("quality_satisfied", sa.Boolean(), nullable=True)
        )
        _ensure_column("llm_stage_router_audit", "actual_cost", sa.Column("actual_cost", sa.Float(), nullable=True))
        _ensure_column(
            "llm_stage_router_audit", "actual_latency_ms", sa.Column("actual_latency_ms", sa.Float(), nullable=True)
        )
        _ensure_column("llm_stage_router_audit", "actual_model", sa.Column("actual_model", sa.String(), nullable=True))
        _ensure_column(
            "llm_stage_router_audit", "actual_provider", sa.Column("actual_provider", sa.String(), nullable=True)
        )
        _ensure_column(
            "llm_stage_router_audit", "policy_source", sa.Column("policy_source", sa.String(length=16), nullable=True)
        )
        return

    op.create_table(
        "llm_stage_router_audit",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=True),
        sa.Column("workspace_id", sa.String(), nullable=True),
        sa.Column("agent_id", sa.String(), nullable=True),
        sa.Column("execution_id", sa.String(), nullable=True),
        sa.Column("step_index", sa.Integer(), nullable=True),
        sa.Column("picker", sa.String(length=24), nullable=True),
        sa.Column("confidence_threshold", sa.Float(), nullable=True),
        sa.Column("signals", sa.JSON(), nullable=True),
        sa.Column("selected_group", sa.String(length=16), nullable=True),
        sa.Column("applied_group", sa.String(length=16), nullable=True),
        sa.Column("split_group", sa.String(length=16), nullable=True),
        sa.Column("default_group", sa.String(length=16), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("decision_source", sa.String(length=24), nullable=True),
        sa.Column("enforced", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("policy_source", sa.String(length=16), nullable=True),
        sa.Column("model_type", sa.String(length=24), nullable=True),
        sa.Column("handoff_note", sa.Text(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("quality_satisfied", sa.Boolean(), nullable=True),
        sa.Column("actual_cost", sa.Float(), nullable=True),
        sa.Column("actual_latency_ms", sa.Float(), nullable=True),
        sa.Column("actual_model", sa.String(), nullable=True),
        sa.Column("actual_provider", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_stage_router_audit_ws_created", "llm_stage_router_audit", ["workspace_id", "created_at"]
    )
    op.create_index(
        "ix_stage_router_audit_agent", "llm_stage_router_audit", ["agent_id", "created_at"]
    )


def downgrade() -> None:
    if _table_exists("llm_stage_router_audit"):
        op.drop_table("llm_stage_router_audit")
