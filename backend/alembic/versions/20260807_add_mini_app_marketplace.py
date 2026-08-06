"""add mini-app marketplace columns (is_approved) + mini_app_installations

Revision ID: 20260807_mini_app_marketplace
Revises: 20260806_canvas_records
Create Date: 2026-08-07 00:00:00.000000

Two changes for the mini-app marketplace (3rd-party publish/install support):

* ``mini_apps.is_approved`` — Boolean (default false). Public install requires
  ``is_public AND is_approved`` (an admin/moderation gate); owner-installs are
  unaffected.
* ``mini_app_installations`` — tracks which app version an instance canvas was
  installed from, enabling update-available signals.

Guarded for the hybrid SQLite/PostgreSQL setup (mirrors prior mini-app
migrations).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260807_mini_app_marketplace"
down_revision: Union[str, Sequence[str], None] = "20260806_canvas_records"
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
    return column_name in [c["name"] for c in inspector.get_columns(table_name)]


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    # 1. mini_apps.is_approved
    if _table_exists("mini_apps") and not _column_exists("mini_apps", "is_approved"):
        if _is_postgres():
            op.add_column("mini_apps", sa.Column("is_approved", sa.Boolean(), server_default="0"))
        else:
            with op.batch_alter_table("mini_apps") as batch_op:
                batch_op.add_column(sa.Column("is_approved", sa.Boolean(), server_default="0"))

    # 2. mini_app_installations
    if not _table_exists("mini_app_installations"):
        op.create_table(
            "mini_app_installations",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("app_id", sa.String(), sa.ForeignKey("mini_apps.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("canvas_id", sa.String(), sa.ForeignKey("canvases.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("installed_by", sa.String(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("installed_version", sa.String(length=32), nullable=True),
            sa.Column("installed_runtime_version", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("source", sa.String(length=20), nullable=True, server_default="owned"),  # owned|marketplace|share_token
            sa.Column("installed_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        )


def downgrade() -> None:
    if _table_exists("mini_app_installations"):
        op.drop_table("mini_app_installations")
    if _table_exists("mini_apps") and _column_exists("mini_apps", "is_approved"):
        if _is_postgres():
            op.drop_column("mini_apps", "is_approved")
        else:
            with op.batch_alter_table("mini_apps") as batch_op:
                batch_op.drop_column("is_approved")
