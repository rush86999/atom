"""exchange_examples table (rated query/response pairs for learning)

Revision ID: 20260902_exchange_examples
Revises: 20260826_reasoning_model_provenance
Create Date: 2026-09-02 00:00:00.000000

Positive/negative example learning loop (Phase 56): full-text (query,
response) pairs captured at feedback time. Consumers: chat-time example
retrieval (memory_context_assembler leg), the teaching circuit
(human_correction lessons for STUDENT agents), and training/eval evidence.

Guarded create pattern for the hybrid SQLite/PostgreSQL setup.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260902_exchange_examples"
down_revision: Union[str, Sequence[str], None] = "20260826_reasoning_model_provenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def _index_exists(index_name: str, table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return index_name in (i["name"] for i in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _table_exists("exchange_examples"):
        op.create_table(
            "exchange_examples",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("workspace_id", sa.String(), nullable=True),
            sa.Column("conversation_id", sa.String(), nullable=True),
            sa.Column("message_id", sa.String(), nullable=True),
            sa.Column("assistant_message_id", sa.String(), nullable=True),
            sa.Column("agent_id", sa.String(), nullable=True),
            sa.Column("user_query", sa.Text(), nullable=False),
            sa.Column("assistant_response", sa.Text(), nullable=False),
            sa.Column("label", sa.String(), nullable=False),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("model", sa.String(), nullable=True),
            sa.Column("provider", sa.String(), nullable=True),
            sa.Column("embedded", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("consolidated", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )

    if not _index_exists("idx_exchange_examples_recall", "exchange_examples"):
        op.create_index(
            "idx_exchange_examples_recall",
            "exchange_examples",
            ["workspace_id", "label", "created_at"],
        )
    for col in ("tenant_id", "user_id", "workspace_id", "conversation_id", "agent_id"):
        ix_name = f"ix_exchange_examples_{col}"
        if not _index_exists(ix_name, "exchange_examples"):
            op.create_index(ix_name, "exchange_examples", [col])


def downgrade() -> None:
    if _table_exists("exchange_examples"):
        op.drop_table("exchange_examples")
