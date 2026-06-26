"""add verified column to agent_reasoning_steps

Revision ID: 20260624_reasoning_verified
Revises: 20260624_reasoning_fts
Create Date: 2026-06-24 18:00:00.000000

Adds two columns to agent_reasoning_steps:
  - verified (String(24), default 'unverified', NOT NULL, indexed)
      Tri-state: 'verified' | 'unverified' | 'failed_verification'
  - verification_evidence (Text, nullable)

Purpose: defend against silent no-op tool returns. A tool returning
``{"success": true}`` without verifiable evidence is recorded as
'unverified'. Graduation gates on 'verified' outcomes only, so silent
no-ops can no longer inflate capability success ratios.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260624_reasoning_verified"
down_revision: Union[str, Sequence[str], None] = "20260624_reasoning_fts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if table_name not in inspector.get_table_names():
        return False
    cols = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in cols


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("agent_reasoning_steps"):
        # base table missing — fresh DBs create it (with our column) via
        # Base.metadata.create_all at app start. No-op here.
        return
    # SQLite batch_alter_table recreates the whole table per call, so add
    # both columns in ONE batch to avoid the second batch clobbering the first.
    need_verified = not _column_exists("agent_reasoning_steps", "verified")
    need_evidence = not _column_exists("agent_reasoning_steps", "verification_evidence")
    if need_verified or need_evidence:
        with op.batch_alter_table("agent_reasoning_steps") as batch_op:
            if need_verified:
                batch_op.add_column(
                    sa.Column(
                        "verified",
                        sa.String(length=24),
                        server_default="unverified",
                        nullable=False,
                    )
                )
            if need_evidence:
                batch_op.add_column(
                    sa.Column("verification_evidence", sa.Text(), nullable=True)
                )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_agent_reasoning_steps_verified "
            "ON agent_reasoning_steps (verified)"
        )


def downgrade() -> None:
    if not _column_exists("agent_reasoning_steps", "verified"):
        return
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_agent_reasoning_steps_verified")
    with op.batch_alter_table("agent_reasoning_steps") as batch_op:
        batch_op.drop_column("verification_evidence")
        batch_op.drop_column("verified")
