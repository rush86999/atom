"""add agent_org_events table

Revision ID: 20260822_org_events
Revises: 20260822_trust_cal_assess
Create Date: 2026-08-22 00:00:00.000000

Backs org-dynamics telemetry Phase 0 (docs/architecture/AGENT_ORG_POLITICS_PLAN.md):
append-only recruitment / radio / review-verdict events for the incumbency,
reviewer-favoritism, and conflict-of-interest baseline reports. Write-only
telemetry — no runtime decision reads this table.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260822_org_events"
down_revision: Union[str, Sequence[str], None] = "20260822_trust_cal_assess"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def _index_exists(index_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return index_name in {
        i["name"] for i in inspector.get_indexes("agent_org_events")
    }


def upgrade() -> None:
    if not _table_exists("agent_org_events"):
        op.create_table(
            "agent_org_events",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.Column("event_type", sa.String(length=32), nullable=False),
            sa.Column("actor_agent_id", sa.String(), nullable=True),
            sa.Column("target_agent_id", sa.String(), nullable=True),
            sa.Column("execution_id", sa.String(), nullable=True),
            sa.Column("chain_id", sa.String(), nullable=True),
            sa.Column("workspace_id", sa.String(), nullable=True),
            sa.Column("tenant_id", sa.String(), nullable=True),
            sa.Column("payload_json", sa.JSON(), nullable=True),
        )
    # Indexes are guarded separately — the dev DB is hybrid (schema often
    # exists via create_all while alembic bookkeeping lags).
    if not _index_exists("ix_agent_org_events_created_at"):
        op.create_index(
            "ix_agent_org_events_created_at", "agent_org_events", ["created_at"]
        )
    if not _index_exists("ix_agent_org_events_event_type"):
        op.create_index(
            "ix_agent_org_events_event_type", "agent_org_events", ["event_type"]
        )
    if not _index_exists("ix_agent_org_events_actor_agent_id"):
        op.create_index(
            "ix_agent_org_events_actor_agent_id",
            "agent_org_events",
            ["actor_agent_id"],
        )
    if not _index_exists("ix_agent_org_events_target_agent_id"):
        op.create_index(
            "ix_agent_org_events_target_agent_id",
            "agent_org_events",
            ["target_agent_id"],
        )
    if not _index_exists("ix_agent_org_events_execution_id"):
        op.create_index(
            "ix_agent_org_events_execution_id", "agent_org_events", ["execution_id"]
        )
    if not _index_exists("ix_agent_org_events_chain_id"):
        op.create_index(
            "ix_agent_org_events_chain_id", "agent_org_events", ["chain_id"]
        )
    if not _index_exists("ix_agent_org_events_workspace_id"):
        op.create_index(
            "ix_agent_org_events_workspace_id", "agent_org_events", ["workspace_id"]
        )
    if not _index_exists("ix_agent_org_events_tenant_id"):
        op.create_index(
            "ix_agent_org_events_tenant_id", "agent_org_events", ["tenant_id"]
        )
    if not _index_exists("ix_org_events_pair_created"):
        op.create_index(
            "ix_org_events_pair_created",
            "agent_org_events",
            ["actor_agent_id", "target_agent_id", "created_at"],
        )
    if not _index_exists("ix_org_events_type_created"):
        op.create_index(
            "ix_org_events_type_created",
            "agent_org_events",
            ["event_type", "created_at"],
        )


def downgrade() -> None:
    if _table_exists("agent_org_events"):
        op.drop_table("agent_org_events")
