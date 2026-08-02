"""add gateway_api_keys and gateway_request_logs tables

Revision ID: 20260801_gateway_models
Revises: b55b0f499509
Create Date: 2026-08-01 12:00:00.000000

Adds the inbound LLM-gateway tables backing the OpenAI/Anthropic-compatible
gateway (Phase A) and the full-body request/response log (Phase B).

Guarded for SQLite (dev DB is hybrid — schema via ``create_all``, alembic
bookkeeping lags). See CLAUDE.md "Database Migrations".
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260801_gateway_models"
down_revision: Union[str, Sequence[str], None] = "b55b0f499509"
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
    if not _table_exists("gateway_api_keys"):
        op.create_table(
            "gateway_api_keys",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("key_hash", sa.String(length=64), nullable=False),
            sa.Column("key_prefix", sa.String(length=12), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("tenant_id", sa.String(), nullable=True),
            sa.Column("workspace_id", sa.String(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("rate_limit_per_minute", sa.Integer(), nullable=True, server_default="60"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_used", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_rotated", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("total_requests", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("key_hash"),
        )
        op.create_index("ix_gateway_api_keys_key_hash", "gateway_api_keys", ["key_hash"])
        op.create_index("ix_gateway_api_keys_key_prefix", "gateway_api_keys", ["key_prefix"])
        op.create_index("ix_gateway_api_keys_user_id", "gateway_api_keys", ["user_id"])
        op.create_index("ix_gateway_api_keys_is_active", "gateway_api_keys", ["is_active"])
    else:
        print("    [skip] gateway_api_keys already exists")

    if not _table_exists("gateway_request_logs"):
        op.create_table(
            "gateway_request_logs",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("tenant_id", sa.String(), nullable=True),
            sa.Column("workspace_id", sa.String(), nullable=True),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("api_key_id", sa.String(), nullable=True),
            sa.Column("request_json", sa.Text(), nullable=True),
            sa.Column("response_json", sa.Text(), nullable=True),
            sa.Column("provider", sa.String(length=100), nullable=True),
            sa.Column("model", sa.String(length=200), nullable=True),
            sa.Column("stream", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("status_code", sa.Integer(), nullable=True),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("prompt_tokens", sa.Integer(), nullable=True),
            sa.Column("completion_tokens", sa.Integer(), nullable=True),
            sa.Column("cost_usd", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_gateway_request_logs_user_id", "gateway_request_logs", ["user_id"])
        op.create_index("ix_gateway_request_logs_created_at", "gateway_request_logs", ["created_at"])
        op.create_index("ix_gateway_request_logs_provider", "gateway_request_logs", ["provider"])
        op.create_index("ix_gateway_request_logs_model", "gateway_request_logs", ["model"])
    else:
        print("    [skip] gateway_request_logs already exists")


def downgrade() -> None:
    if _table_exists("gateway_request_logs"):
        op.drop_table("gateway_request_logs")
    if _table_exists("gateway_api_keys"):
        op.drop_table("gateway_api_keys")
