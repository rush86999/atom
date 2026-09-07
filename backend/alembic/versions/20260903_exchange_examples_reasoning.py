"""exchange_examples.reasoning — chain-of-thought captured with rated pairs

Revision ID: 20260903_exchange_reasoning
Revises: 20260902_exchange_examples
Create Date: 2026-09-03 00:00:00.000000

The model's chain-of-thought for the rated reply ("what the agent was
thinking") is now captured at reply time (ChatMessage.metadata_json.reasoning)
and/or from POST /api/chat/feedback, and persisted on the ExchangeExample so
feedback training judges the reasoning that produced the response — not just
the response text.

Guarded add-column pattern for the hybrid SQLite/PostgreSQL setup.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260903_exchange_reasoning"
down_revision: Union[str, Sequence[str], None] = "20260902_exchange_examples"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return column_name in (c["name"] for c in inspector.get_columns(table_name))


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("exchange_examples") and not _column_exists("exchange_examples", "reasoning"):
        op.add_column("exchange_examples", sa.Column("reasoning", sa.Text(), nullable=True))


def downgrade() -> None:
    if _table_exists("exchange_examples") and _column_exists("exchange_examples", "reasoning"):
        op.drop_column("exchange_examples", "reasoning")
