"""add trust_calibration_actions table

Revision ID: 20260822_trust_cal_actions
Revises: 20260822_trust_cal_assess
Create Date: 2026-08-22 00:00:00.000000

Consent-gated automation ledger for the trust gateway (R81o) — mirrors
fleet_router automation actions. Guarded create per repo convention.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260822_trust_cal_actions"
down_revision: Union[str, Sequence[str], None] = "20260822_trust_cal_assess"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("trust_calibration_actions"):
        return
    op.create_table(
        "trust_calibration_actions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workload_key", sa.String(length=32), nullable=False,
                  server_default="__global__", index=True),
        sa.Column("verdict", sa.String(length=16), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False,
                  server_default="approval"),
        sa.Column("stats_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    if _table_exists("trust_calibration_actions"):
        op.drop_table("trust_calibration_actions")
