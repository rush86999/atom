"""Add opt-in never-autonomous task-basket rules.

Revision ID: 20261116_action_autonomy_rules
Revises: 20261113_user_session_token_jti
Create Date: 2026-11-16

Creates ``action_autonomy_rules`` — the durable per-user store behind
``/api/autonomy/never-rules``. The table is additive and starts empty, so
existing topic policy behavior is unchanged until a user creates and enables
a rule.

Guarded create pattern for the hybrid SQLite/PostgreSQL setup: fresh
``Base.metadata.create_all`` deployments already have the table, and no live
row is read, backfilled, or rewritten here.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261116_action_autonomy_rules"
down_revision: Union[str, Sequence[str], None] = "20261113_user_session_token_jti"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("action_autonomy_rules"):
        return
    op.create_table(
        "action_autonomy_rules",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=True),
        sa.Column("workspace_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1" if op.get_bind().dialect.name == "sqlite"
                                   else "true"),
        ),
        sa.Column("match_json", sa.JSON(), nullable=False),
        sa.Column(
            "revision",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_action_autonomy_rules_user_id",
        "action_autonomy_rules",
        ["user_id"],
    )
    op.create_index(
        "ix_action_autonomy_rules_tenant_id",
        "action_autonomy_rules",
        ["tenant_id"],
    )
    op.create_index(
        "ix_action_autonomy_rules_workspace_id",
        "action_autonomy_rules",
        ["workspace_id"],
    )
    op.create_index(
        "ix_action_autonomy_rules_owner_scope",
        "action_autonomy_rules",
        ["user_id", "tenant_id", "workspace_id"],
    )


def downgrade() -> None:
    if not _table_exists("action_autonomy_rules"):
        return
    for index_name in (
        "ix_action_autonomy_rules_owner_scope",
        "ix_action_autonomy_rules_workspace_id",
        "ix_action_autonomy_rules_tenant_id",
        "ix_action_autonomy_rules_user_id",
    ):
        try:
            op.drop_index(index_name, table_name="action_autonomy_rules")
        except Exception:
            pass
    op.drop_table("action_autonomy_rules")
