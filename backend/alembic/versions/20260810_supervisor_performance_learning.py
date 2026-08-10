"""add supervisor_performance learning columns

Revision ID: 20260810_supervisor_performance_learning
Revises: 20260808_add_turn_fact_versioning
Create Date: 2026-08-10

Restores the two-way-learning schema onto ``supervisor_performance``. The
Hive-port rewrite of ``core.models.SupervisorPerformance`` dropped the
learning columns every consumer uses (``SupervisorLearningService``,
``FeedbackService.rate_supervisor``, ``SupervisorPerformanceService``),
crashing the whole two-way-learning path from ``supervision_service`` with
"'confidence_score' is an invalid keyword argument for SupervisorPerformance".
See tests/test_covpush_w20_supervisor_performance.py.

Guard: SQLite has no native ADD COLUMN-alongside-ALTER support; batch mode
recreates the table. Column adds are idempotent via existence checks.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260810_supervisor_performance_learning"
down_revision: Union[str, Sequence[str], None] = "20260808_add_turn_fact_versioning"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


LEARNING_COLUMNS = [
    sa.Column("confidence_score", sa.Float(), server_default="0.5"),
    sa.Column("competence_level", sa.String(50), server_default="novice"),
    sa.Column("learning_rate", sa.Float(), server_default="0.0"),
    sa.Column("performance_trend", sa.String(50), server_default="stable"),
    sa.Column("total_sessions_supervised", sa.Integer(), server_default="0"),
    sa.Column("total_interventions", sa.Integer(), server_default="0"),
    sa.Column("average_rating", sa.Float(), server_default="0.0"),
    sa.Column("total_ratings", sa.Integer(), server_default="0"),
    sa.Column("rating_1_count", sa.Integer(), server_default="0"),
    sa.Column("rating_2_count", sa.Integer(), server_default="0"),
    sa.Column("rating_3_count", sa.Integer(), server_default="0"),
    sa.Column("rating_4_count", sa.Integer(), server_default="0"),
    sa.Column("rating_5_count", sa.Integer(), server_default="0"),
    sa.Column("successful_interventions", sa.Integer(), server_default="0"),
    sa.Column("failed_interventions", sa.Integer(), server_default="0"),
    sa.Column("agents_promoted", sa.Integer(), server_default="0"),
    sa.Column("agent_confidence_boosted", sa.Float(), server_default="0.0"),
    sa.Column("total_comments_given", sa.Integer(), server_default="0"),
    sa.Column("total_upvotes_received", sa.Integer(), server_default="0"),
    sa.Column("total_downvotes_received", sa.Integer(), server_default="0"),
    sa.Column("last_updated", sa.DateTime(timezone=True), nullable=True),
]


def _columns_exist(table_name: str) -> set[str]:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return {c["name"] for c in inspector.get_columns(table_name)}


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "supervisor_performance" not in inspector.get_table_names():
        print("    [skip] supervisor_performance table missing")
        return

    existing = _columns_exist("supervisor_performance")
    missing = [c for c in LEARNING_COLUMNS if c.name not in existing]
    if not missing:
        print("    [skip] supervisor_performance already has learning columns")
        return

    with op.batch_alter_table("supervisor_performance") as batch_op:
        for col in missing:
            batch_op.add_column(col)
    print(f"    [ok] added {len(missing)} learning columns to supervisor_performance")


def downgrade() -> None:
    existing = _columns_exist("supervisor_performance")
    with op.batch_alter_table("supervisor_performance") as batch_op:
        for col in LEARNING_COLUMNS:
            if col.name in existing:
                batch_op.drop_column(col.name)
