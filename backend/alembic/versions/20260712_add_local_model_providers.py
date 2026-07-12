"""add local_model_providers + local_model_capabilities tables

Revision ID: 20260712_local_models
Revises: 20260711_llm_routing_feedback
Create Date: 2026-07-12 00:00:00.000000

Adds two tables backing the local-model provider system:
- ``local_model_providers``: user-registered OpenAI-compatible local endpoints
  (Ollama, LM Studio, vLLM, LocalAI, custom).
- ``local_model_capabilities``: per-model capability overrides (tools, vision,
  reasoning, quality/speed scores, context window) since local models aren't
  in the dynamic pricing cache.

Uses the guarded ``_table_exists`` pattern for SQLite-dev idempotency.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260712_local_models"
down_revision: Union[str, Sequence[str], None] = "20260711_llm_routing_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("local_model_providers"):
        op.create_table(
            "local_model_providers",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("tenant_id", sa.String(), nullable=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("provider_type", sa.String(), nullable=False),
            sa.Column("base_url", sa.String(), nullable=False),
            sa.Column("api_key", sa.String(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_local_model_provider_workspace"),
            "local_model_providers",
            ["workspace_id"],
            unique=False,
        )
        op.create_index(
            "ix_local_model_provider_tenant_id",
            "local_model_providers",
            ["tenant_id"],
            unique=False,
        )
    else:
        print("    [skip] local_model_providers already exists")

    if not _table_exists("local_model_capabilities"):
        op.create_table(
            "local_model_capabilities",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("provider_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("model_id", sa.String(), nullable=False),
            sa.Column("supports_tools", sa.Boolean(), nullable=True),
            sa.Column("supports_vision", sa.Boolean(), nullable=True),
            sa.Column("supports_reasoning", sa.Boolean(), nullable=True),
            sa.Column("quality_score", sa.Float(), nullable=True),
            sa.Column("speed_score", sa.Float(), nullable=True),
            sa.Column("context_window", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["provider_id"], ["local_model_providers.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_local_model_caps_provider_model",
            "local_model_capabilities",
            ["provider_id", "model_id"],
            unique=False,
        )
        op.create_index(
            "ix_local_model_caps_workspace",
            "local_model_capabilities",
            ["workspace_id"],
            unique=False,
        )
    else:
        print("    [skip] local_model_capabilities already exists")


def downgrade() -> None:
    op.drop_index("ix_local_model_caps_workspace", table_name="local_model_capabilities")
    op.drop_index("ix_local_model_caps_provider_model", table_name="local_model_capabilities")
    op.drop_table("local_model_capabilities")
    op.drop_index("ix_local_model_provider_tenant_id", table_name="local_model_providers")
    op.drop_index(op.f("ix_local_model_provider_workspace"), table_name="local_model_providers")
    op.drop_table("local_model_providers")
