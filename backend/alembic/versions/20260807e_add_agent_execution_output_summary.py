"""add agent_executions.output_summary column

Revision ID: 20260807e_add_agent_execution_output_summary
Revises: 20260807d_add_scaling_operations
Create Date: 2026-08-07 10:00:00.000000

``AgentExecution.output_summary`` was created by migration 4ea149ecf75f but
never declared on the ORM model — five production files write it
(proposal_service, byok_handler, atom_agent_endpoints,
supervised_queue_service, agent_learning_enhanced) and the supervision
service reads it, so the column silently never persisted. The column is
already present on databases that ran the full migration chain; this
guarded migration adds it where missing (e.g. hybrid SQLite deployments
whose schema came from ``create_all``).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260807e_add_agent_execution_output_summary"
down_revision: Union[str, Sequence[str], None] = "20260807d_add_scaling_operations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return column_name in [c["name"] for c in inspector.get_columns(table_name)]


def upgrade() -> None:
    if not _table_exists("agent_executions"):
        print("    [skip] agent_executions does not exist")
        return
    if _column_exists("agent_executions", "output_summary"):
        print("    [skip] agent_executions.output_summary already exists")
        return
    with op.batch_alter_table("agent_executions") as batch_op:
        batch_op.add_column(sa.Column("output_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    if not _table_exists("agent_executions"):
        return
    if not _column_exists("agent_executions", "output_summary"):
        return
    with op.batch_alter_table("agent_executions") as batch_op:
        batch_op.drop_column("output_summary")
