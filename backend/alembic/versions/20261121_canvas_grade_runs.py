"""durable Canvas mini-app grading runs

Adds one idempotent run per tenant/workspace/user/app and client submission
UUID, bound to the saved source and test digests. The table stores the current
worker ownership claim, its fencing token, the terminal report/failure code and
the lifecycle timestamps. No grader output or client content is stored beyond
the caller-supplied report.

Revision ID: 20261121_canvas_grade_runs
Revises: 20261119_invoice_provider_binding
Create Date: 2026-11-21 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261121_canvas_grade_runs"
down_revision: Union[str, Sequence[str], None] = "20261119_invoice_provider_binding"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "canvas_grade_runs"


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def _json_type() -> sa.types.TypeEngine:
    """Use JSONB on PostgreSQL and portable JSON everywhere else."""
    if op.get_bind().dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import JSONB

        return JSONB()
    return sa.JSON()


def upgrade() -> None:
    if _table_exists(_TABLE):
        return

    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("app_id", sa.String(), nullable=False),
        sa.Column("submission_id", sa.String(), nullable=False),
        sa.Column("source_digest", sa.String(), nullable=False),
        sa.Column("test_digest", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("owner_metadata", _json_type(), nullable=True),
        sa.Column(
            "fence",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("report", _json_type(), nullable=True),
        sa.Column("failure_code", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', "
            "'interrupted')",
            name="ck_canvas_grade_runs_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "user_id",
            "app_id",
            "submission_id",
            name="_canvas_grade_runs_submission_uc",
        ),
    )
    op.create_index(
        "ix_canvas_grade_runs_tenant_id",
        _TABLE,
        ["tenant_id"],
    )
    op.create_index(
        "ix_canvas_grade_runs_workspace_id",
        _TABLE,
        ["workspace_id"],
    )
    op.create_index(
        "ix_canvas_grade_runs_user_id",
        _TABLE,
        ["user_id"],
    )
    op.create_index(
        "ix_canvas_grade_runs_app_id",
        _TABLE,
        ["app_id"],
    )
    op.create_index(
        "ix_canvas_grade_runs_submission_id",
        _TABLE,
        ["submission_id"],
    )
    op.create_index(
        "ix_canvas_grade_runs_status",
        _TABLE,
        ["status"],
    )
    op.create_index(
        "ix_canvas_grade_runs_status_updated_at",
        _TABLE,
        ["status", "updated_at"],
    )


def downgrade() -> None:
    if _table_exists(_TABLE):
        op.drop_table(_TABLE)
