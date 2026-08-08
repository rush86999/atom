"""add AgentRadio lateral-messaging tables (agent_threads, lateral_messages)

Revision ID: 20260808_add_lateral_messaging
Revises: 20260807e_add_agent_execution_output_summary
Create Date: 2026-08-08 00:00:00.000000

Introduces the AgentRadio-style lateral (peer-to-peer) coordination layer:

- ``agent_threads`` — a shared channel a team of agents communicate on
  (typically one per DelegationChain / recruited fleet).
- ``lateral_messages`` — directed @mention messages between agents on a thread.
- ``agent_executions.thread_id`` — optional FK tying a run to its coordination
  thread (mirrors the existing ``chain_id`` pattern).

Tables/columns are created idempotently so this is safe to run on databases
that received the schema via ``create_all`` as well as via the migration chain.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260808_add_lateral_messaging"
down_revision: Union[str, Sequence[str], None] = "20260807e_add_agent_execution_output_summary"
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
    # --- agent_threads ---
    if not _table_exists("agent_threads"):
        op.create_table(
            "agent_threads",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
            sa.Column("chain_id", sa.String(), sa.ForeignKey("delegation_chains.id", ondelete="CASCADE"), nullable=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("created_by_agent_id", sa.String(),
                      sa.ForeignKey("agent_registry.id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="open"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("member_agent_ids", sa.JSON(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
        )
        op.create_index("ix_agent_threads_tenant_id", "agent_threads", ["tenant_id"])
        op.create_index("ix_agent_threads_chain_id", "agent_threads", ["chain_id"])
        op.create_index("ix_agent_threads_created_by_agent_id", "agent_threads", ["created_by_agent_id"])

    # --- lateral_messages ---
    if not _table_exists("lateral_messages"):
        op.create_table(
            "lateral_messages",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("thread_id", sa.String(),
                      sa.ForeignKey("agent_threads.id", ondelete="CASCADE"), nullable=False),
            sa.Column("from_agent_id", sa.String(),
                      sa.ForeignKey("agent_registry.id", ondelete="SET NULL"), nullable=True),
            sa.Column("to_agent_id", sa.String(),
                      sa.ForeignKey("agent_registry.id", ondelete="SET NULL"), nullable=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("mentions", sa.JSON(), nullable=True),
            sa.Column("delivered", sa.Boolean(), nullable=False, server_default=sa.sql.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
        )
        op.create_index("ix_lateral_messages_thread_id", "lateral_messages", ["thread_id"])
        op.create_index("ix_lateral_messages_from_agent_id", "lateral_messages", ["from_agent_id"])
        op.create_index("ix_lateral_messages_to_agent_id", "lateral_messages", ["to_agent_id"])
        op.create_index("ix_lateral_messages_created_at", "lateral_messages", ["created_at"])

    # --- agent_executions.thread_id (mirrors chain_id) ---
    if _table_exists("agent_executions") and not _column_exists("agent_executions", "thread_id"):
        with op.batch_alter_table("agent_executions") as batch_op:
            batch_op.add_column(sa.Column(
                "thread_id", sa.String(),
                sa.ForeignKey("agent_threads.id", ondelete="SET NULL"), nullable=True))
        op.create_index("ix_agent_executions_thread_id", "agent_executions", ["thread_id"])


def downgrade() -> None:
    if _table_exists("agent_executions") and _column_exists("agent_executions", "thread_id"):
        with op.batch_alter_table("agent_executions") as batch_op:
            batch_op.drop_column("thread_id")

    if _table_exists("lateral_messages"):
        op.drop_table("lateral_messages")

    if _table_exists("agent_threads"):
        op.drop_table("agent_threads")
