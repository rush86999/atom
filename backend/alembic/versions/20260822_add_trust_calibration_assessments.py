"""add trust_calibration_assessments table

Revision ID: 20260822_trust_cal_assess
Revises: 20260821_fleet_routing_audit
Create Date: 2026-08-22 00:00:00.000000

Backs the trust-calibration gateway shadow mode (P1,
docs/architecture/TRUST_CALIBRATION_PLAN.md): one row per ask-the-human
moment, joined live to HITLAction via decision_ref for Brier/ECE metrics.
No backfill — the gateway starts recording from the next HITL pause.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260822_trust_cal_assess"
down_revision: Union[str, Sequence[str], None] = "20260821_fleet_routing_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("trust_calibration_assessments"):
        return
    op.create_table(
        "trust_calibration_assessments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
            index=True,
        ),
        sa.Column("agent_id", sa.String(), nullable=True, index=True),
        sa.Column("action_type", sa.String(), nullable=False, index=True),
        sa.Column("platform", sa.String(), nullable=True),
        sa.Column("features_json", sa.JSON(), nullable=True),
        sa.Column("p_approve", sa.Float(), nullable=False),
        sa.Column("uncertainty", sa.Float(), nullable=False),
        sa.Column("recommendation", sa.String(), nullable=False),
        sa.Column("source_path", sa.String(), nullable=False, index=True),
        sa.Column("decision_ref", sa.String(), nullable=True, index=True),
        sa.Column("half_life_days", sa.Float(), nullable=True),
        sa.Column("n_obs", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    if _table_exists("trust_calibration_assessments"):
        op.drop_table("trust_calibration_assessments")
