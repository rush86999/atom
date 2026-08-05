"""add workspace scoping (workspace_skills + workspace_id columns)

Revision ID: 20260805_add_workspace_scoping
Revises: 20260805_integration_token_credential_metadata
Create Date: 2026-08-05 00:00:00.000000

Phase P8 (Cloudflare G8) — workspace-scoped curated context:

* Creates the ``workspace_skills`` association table (many-to-many between
  ``workspaces`` and ``skills``) used to assign skills to a workspace so they
  pre-load into that workspace's agents.
* Adds a nullable ``workspace_id`` column to ``knowledge_documents`` and
  ``agent_episodes`` (currently NOT workspace-scoped). Nullable so no data
  migration is needed for existing rows.

Guarded for SQLite (dev DB is hybrid — schema via ``create_all``, alembic
bookkeeping lags). Mirrors the guard pattern in
``20260804_add_doc_freshness.py``: ``_table_exists``/``_column_exists``
helpers plus ``op.batch_alter_table`` for column adds.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260805_add_workspace_scoping"
down_revision: Union[str, Sequence[str], None] = "20260805_integration_token_credential_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if table_name not in inspector.get_table_names():
        return False
    cols = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in cols


def upgrade() -> None:
    # 1. workspace_skills association table (create only if absent).
    if not _table_exists("workspace_skills"):
        op.create_table(
            "workspace_skills",
            sa.Column(
                "workspace_id",
                sa.String(),
                sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "skill_id",
                sa.String(),
                sa.ForeignKey("skills.id", ondelete="CASCADE"),
                primary_key=True,
            ),
        )

    # 2. workspace_id on knowledge_documents (nullable, additive).
    if _table_exists("knowledge_documents") and not _column_exists(
        "knowledge_documents", "workspace_id"
    ):
        with op.batch_alter_table("knowledge_documents") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "workspace_id",
                    sa.String(),
                    sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
                    nullable=True,
                )
            )

    # 3. workspace_id on agent_episodes (nullable, additive).
    if _table_exists("agent_episodes") and not _column_exists(
        "agent_episodes", "workspace_id"
    ):
        with op.batch_alter_table("agent_episodes") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "workspace_id",
                    sa.String(),
                    sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
                    nullable=True,
                )
            )


def downgrade() -> None:
    if _table_exists("agent_episodes") and _column_exists("agent_episodes", "workspace_id"):
        with op.batch_alter_table("agent_episodes") as batch_op:
            batch_op.drop_column("workspace_id")

    if _table_exists("knowledge_documents") and _column_exists(
        "knowledge_documents", "workspace_id"
    ):
        with op.batch_alter_table("knowledge_documents") as batch_op:
            batch_op.drop_column("workspace_id")

    if _table_exists("workspace_skills"):
        op.drop_table("workspace_skills")
