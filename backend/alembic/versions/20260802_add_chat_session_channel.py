"""add channel_id/thread_id columns to chat_sessions

Revision ID: 20260802_chat_session_channel
Revises: 20260802_credential_type
Create Date: 2026-08-02 16:00:00.000000

R72 Workstream I (channel-binding fix): locks a ChatSession to the messaging
channel/thread it was created from so a single sender on two channels of one
platform gets distinct sessions instead of sharing context.

Guarded for SQLite (dev DB is hybrid — schema via ``create_all``, alembic
bookkeeping lags). Both columns are nullable, so pre-existing sessions keep
working untouched; only newly created external-platform sessions populate them.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260802_chat_session_channel"
down_revision: Union[str, Sequence[str], None] = "20260802_credential_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _table_exists("chat_sessions"):
        print("    [skip] chat_sessions table not present")
        return

    if _column_exists("chat_sessions", "channel_id"):
        print("    [skip] chat_sessions.channel_id already exists")
        return

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.add_column("chat_sessions", sa.Column("channel_id", sa.String(), nullable=True))
        op.add_column("chat_sessions", sa.Column("thread_id", sa.String(), nullable=True))
        op.create_index(op.f("ix_chat_sessions_channel_id"), "chat_sessions", ["channel_id"], unique=False)
    else:
        # SQLite has no native ALTER COLUMN — batch_alter_table recreates the table.
        with op.batch_alter_table("chat_sessions") as batch_op:
            batch_op.add_column(sa.Column("channel_id", sa.String(), nullable=True))
            batch_op.add_column(sa.Column("thread_id", sa.String(), nullable=True))
            batch_op.create_index(op.f("ix_chat_sessions_channel_id"), ["channel_id"], unique=False)


def downgrade() -> None:
    if not _table_exists("chat_sessions"):
        return
    if not _column_exists("chat_sessions", "channel_id"):
        return

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_index(op.f("ix_chat_sessions_channel_id"), table_name="chat_sessions")
        op.drop_column("chat_sessions", "thread_id")
        op.drop_column("chat_sessions", "channel_id")
    else:
        with op.batch_alter_table("chat_sessions") as batch_op:
            batch_op.drop_index(op.f("ix_chat_sessions_channel_id"))
            batch_op.drop_column("thread_id")
            batch_op.drop_column("channel_id")
