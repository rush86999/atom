"""add org_politics_actions table

Revision ID: 20260822_org_actions
Revises: 20260822_org_events
Create Date: 2026-08-22 00:00:00.000000

Backs the consent-gated org-politics lifecycle automation
(docs/architecture/AGENT_ORG_POLITICS_PLAN.md): approval queue + audit trail
for P2/P3/P5 enforcement flips. Escalation needs consent; revocation is
always automatic (fail-safe).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260822_org_actions"
down_revision: Union[str, Sequence[str], None] = "20260822_org_events"
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
        i["name"] for i in inspector.get_indexes("org_politics_actions")
    }


def upgrade() -> None:
    if not _table_exists("org_politics_actions"):
        op.create_table(
            "org_politics_actions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(
                "flag_key", sa.String(length=32), nullable=False,
                server_default="__global__",
            ),
            sa.Column("verdict", sa.String(length=24), nullable=False),
            sa.Column("mode", sa.String(length=16), nullable=False),
            sa.Column("state", sa.String(length=16), nullable=False,
                      server_default="approval"),
            sa.Column("stats_json", sa.JSON(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _index_exists("ix_org_politics_actions_flag_key"):
        op.create_index(
            "ix_org_politics_actions_flag_key",
            "org_politics_actions",
            ["flag_key"],
        )
    if not _index_exists("ix_org_politics_actions_flag_created"):
        op.create_index(
            "ix_org_politics_actions_flag_created",
            "org_politics_actions",
            ["flag_key", "created_at"],
        )


def downgrade() -> None:
    if _table_exists("org_politics_actions"):
        op.drop_table("org_politics_actions")
