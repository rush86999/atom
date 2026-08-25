"""add domain_experience_ledger table

Revision ID: 20260826_domain_ledger
Revises: 20260826_ontology_draft_actions
Create Date: 2026-08-26

Per-role outcome ledger so the generalist meta agent can EARN super-mentor
status per business domain (R86c). Written by core/domain_attribution.py
from the meta agent's execution recording path; read by the promotion gate's
mentor eligibility check. No backfill — attribution starts fresh.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260826_domain_ledger"
down_revision: Union[str, Sequence[str], None] = "20260826_ontology_draft_actions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("domain_experience_ledger"):
        op.create_table(
            "domain_experience_ledger",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("agent_id", sa.String(255), nullable=False, index=True),
            sa.Column("domain", sa.String(64), nullable=False, index=True),
            sa.Column("outcome", sa.String(20), nullable=False),
            sa.Column("task_summary", sa.String(500), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
        )
        op.create_index(
            "ix_domain_ledger_agent_domain_outcome",
            "domain_experience_ledger",
            ["agent_id", "domain", "outcome"],
        )


def downgrade() -> None:
    if _table_exists("domain_experience_ledger"):
        op.drop_table("domain_experience_ledger")
