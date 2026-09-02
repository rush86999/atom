"""Installation Adaptation Plan tables: installation_profiles, playbooks,
incident_evals.

Revision ID: 20260902_installation_adaptation
Revises: 20260902_verify_panel_runs
Create Date: 2026-09-02

docs/architecture/INSTALLATION_ADAPTATION_PLAN.md — per-install knowledge
as data (profile), processes as procedural memory (playbooks), and live
failures as replayable regression cases (incident_evals).
"""
from alembic import op
import sqlalchemy as sa


revision = "20260902_installation_adaptation"
down_revision = "20260902_verify_panel_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "installation_profiles",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("workspace_id", sa.String(255), nullable=True, index=True),
        sa.Column("identity", sa.JSON(), nullable=True),
        sa.Column("people", sa.JSON(), nullable=True),
        sa.Column("templates", sa.JSON(), nullable=True),
        sa.Column("facts", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "playbooks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(255), nullable=False, index=True),
        sa.Column("workspace_id", sa.String(255), nullable=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("trigger_canvas_type", sa.String(64), nullable=True, index=True),
        sa.Column("trigger_keywords", sa.JSON(), nullable=True),
        sa.Column("steps", sa.JSON(), nullable=True),
        sa.Column("template_questions", sa.JSON(), nullable=True),
        sa.Column("examples", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="authored"),
        sa.Column("approval_state", sa.String(32), nullable=False, server_default="draft", index=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("fingerprint", sa.String(64), nullable=True, index=True),
        sa.Column("origin_ids", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "incident_evals",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(255), nullable=False, index=True),
        sa.Column("canvas_id", sa.String(255), nullable=True, index=True),
        sa.Column("canvas_type", sa.String(64), nullable=True),
        sa.Column("taxonomy", sa.String(32), nullable=False, index=True),
        sa.Column("instruction", sa.Text(), nullable=True),
        sa.Column("context_snapshot", sa.JSON(), nullable=True),
        sa.Column("expected_property", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="correction"),
        sa.Column("fingerprint", sa.String(64), nullable=False, index=True),
        sa.Column("occurrences", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_result", sa.JSON(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("incident_evals")
    op.drop_table("playbooks")
    op.drop_table("installation_profiles")
