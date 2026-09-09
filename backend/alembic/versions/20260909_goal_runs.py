"""GoalRun orchestration (docs/architecture/GOAL_RUN_ORCHESTRATION.md):
the goal_runs table + canvas back-links so a role agent's multi-step,
multi-canvas pursuit of one goal is a durable, auditable unit.

Revision ID: 20260909_goal_runs
Revises: 20260908_playbook_dense_recall
Create Date: 2026-09-09

Canvas back-links are plain nullable indexed strings (logical FK, no
constraint) — sqlite-safe ALTER, and ordinary canvas flows never set them.
"""
from alembic import op
import sqlalchemy as sa


revision = "20260909_goal_runs"
down_revision = "20260908_playbook_dense_recall"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "goal_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("goal_id", sa.String(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=True),
        sa.Column("role", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="planning"),
        sa.Column("supervision_mode", sa.String(20), nullable=False, server_default="shadow"),
        sa.Column("plan", sa.JSON(), nullable=True),
        sa.Column("cursor", sa.String(64), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("waiting_on", sa.JSON(), nullable=True),
        sa.Column("pending_decision", sa.JSON(), nullable=True),
        sa.Column("decision_log", sa.JSON(), nullable=True),
        sa.Column("replan_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("steps_executed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("human_interventions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_goal_runs_tenant_id", "goal_runs", ["tenant_id"])
    op.create_index("ix_goal_runs_workspace_id", "goal_runs", ["workspace_id"])
    op.create_index("ix_goal_runs_goal_id", "goal_runs", ["goal_id"])
    op.create_index("ix_goal_runs_agent_id", "goal_runs", ["agent_id"])
    op.create_index("ix_goal_runs_status", "goal_runs", ["status"])

    with op.batch_alter_table("canvases") as batch:
        batch.add_column(sa.Column("goal_run_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("goal_run_step_id", sa.String(), nullable=True))
    op.create_index("ix_canvases_goal_run_id", "canvases", ["goal_run_id"])


def downgrade() -> None:
    op.drop_index("ix_canvases_goal_run_id", table_name="canvases")
    with op.batch_alter_table("canvases") as batch:
        batch.drop_column("goal_run_step_id")
        batch.drop_column("goal_run_id")
    op.drop_index("ix_goal_runs_status", table_name="goal_runs")
    op.drop_index("ix_goal_runs_agent_id", table_name="goal_runs")
    op.drop_index("ix_goal_runs_goal_id", table_name="goal_runs")
    op.drop_index("ix_goal_runs_workspace_id", table_name="goal_runs")
    op.drop_index("ix_goal_runs_tenant_id", table_name="goal_runs")
    op.drop_table("goal_runs")
