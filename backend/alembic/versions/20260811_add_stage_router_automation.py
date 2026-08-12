"""add stage_router_automation_actions table

Revision ID: 20260811_stage_router_automation
Revises: 20260811_stage_router_audit
Create Date: 2026-08-11 14:00:00.000000

Approval queue + audit trail for automated per-workload stage-router
certification (core/llm/stage_router_automation.py). Rows in state
``approval`` wait for the user to approve/reject via the management API;
``applied``/``rejected``/``revoked`` states are the durable audit record.

No backfill — the automation starts recording from its first pass.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260811_stage_router_automation"
down_revision: Union[str, Sequence[str], None] = "20260811_stage_router_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("stage_router_automation_actions"):
        print("    [skip] stage_router_automation_actions already exists")
        return

    op.create_table(
        "stage_router_automation_actions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("verdict", sa.String(length=16), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False, server_default="approval"),
        sa.Column("stats_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_stage_router_auto_agent_created", "stage_router_automation_actions", ["agent_id", "created_at"]
    )


def downgrade() -> None:
    if _table_exists("stage_router_automation_actions"):
        op.drop_table("stage_router_automation_actions")
