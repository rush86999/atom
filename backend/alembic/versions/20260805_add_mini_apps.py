"""add mini-app models (mini_apps, canvas_states, mini_app_assets)

Revision ID: 20260805_mini_apps
Revises: 20260805_canvas_logic
Create Date: 2026-08-05 00:00:00.000000

Mini Apps — stateful, resumable canvas-UI apps on Firecracker microVMs.

Adds three tables plus a nullable ``canvases.mini_app_id`` link:

* ``mini_apps``       — the app definition (Model). Manifest + runtime_image.
* ``canvas_states``   — versioned instance-state store (one row per instance
  canvas; ``canvas_id`` unique; latest-wins ``state`` + monotonic ``version``).
  Deliberately separate from ``canvas_audit`` (the append-only audit trail).
* ``mini_app_assets`` — host-mediated file/object rows for instance canvases;
  unique on ``(canvas_id, key)``.

The ``canvases.mini_app_id`` column is nullable so ordinary canvases are
unaffected (backward-compatible).

Guarded for the hybrid SQLite/PostgreSQL setup (mirrors
``20260804_add_doc_freshness.py``): tables/columns are only created when
absent, and SQLite column adds use ``op.batch_alter_table``.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260805_mini_apps"
down_revision: Union[str, Sequence[str], None] = "20260805_canvas_logic"
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


def _index_exists(table_name: str, index_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if table_name not in inspector.get_table_names():
        return False
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    # 1. mini_apps
    if not _table_exists("mini_apps"):
        op.create_table(
            "mini_apps",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True),
            sa.Column("created_by", sa.String(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("version", sa.String(length=32), nullable=True, server_default="1.0.0"),
            sa.Column("manifest", sa.JSON(), nullable=False),
            sa.Column("runtime_image", sa.String(length=500), nullable=True),
            sa.Column("runtime_version", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("blueprint_canvas_id", sa.String(), sa.ForeignKey("canvases.id"), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=True, server_default="draft"),
            sa.Column("is_public", sa.Boolean(), nullable=True, server_default="0"),
            sa.Column("share_token", sa.String(length=255), nullable=True, unique=True),
            sa.Column("credential_metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        )
        if _is_postgres():
            op.create_index("ix_mini_apps_tenant_id", "mini_apps", ["tenant_id"])
            op.create_index("ix_mini_apps_workspace_id", "mini_apps", ["workspace_id"])
            op.create_index("ix_mini_apps_created_by", "mini_apps", ["created_by"])

    # 2. canvas_states
    if not _table_exists("canvas_states"):
        op.create_table(
            "canvas_states",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("canvas_id", sa.String(), sa.ForeignKey("canvases.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_by", sa.String(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("state", sa.JSON(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        )
        op.create_index("ix_canvas_states_canvas_id", "canvas_states", ["canvas_id"], unique=True)
        op.create_index("ix_canvas_states_tenant_id", "canvas_states", ["tenant_id"])

    # 3. mini_app_assets
    if not _table_exists("mini_app_assets"):
        op.create_table(
            "mini_app_assets",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("canvas_id", sa.String(), sa.ForeignKey("canvases.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("key", sa.String(length=500), nullable=False),
            sa.Column("uri", sa.String(length=1000), nullable=False),
            sa.Column("content_type", sa.String(length=100), nullable=True),
            sa.Column("size", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("created_by", sa.String(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.UniqueConstraint("canvas_id", "key", name="uq_mini_app_assets_canvas_key"),
        )
        op.create_index("ix_mini_app_assets_canvas_id", "mini_app_assets", ["canvas_id"])

    # 4. canvases.mini_app_id (nullable link)
    if _table_exists("canvases") and not _column_exists("canvases", "mini_app_id"):
        if _is_postgres():
            op.add_column(
                "canvases",
                sa.Column("mini_app_id", sa.String(), sa.ForeignKey("mini_apps.id"), nullable=True),
            )
        else:
            with op.batch_alter_table("canvases") as batch_op:
                batch_op.add_column(
                    sa.Column("mini_app_id", sa.String(), sa.ForeignKey("mini_apps.id"), nullable=True)
                )


def downgrade() -> None:
    if _table_exists("canvases") and _column_exists("canvases", "mini_app_id"):
        if _is_postgres():
            op.drop_column("canvases", "mini_app_id")
        else:
            with op.batch_alter_table("canvases") as batch_op:
                batch_op.drop_column("mini_app_id")

    for table in ("mini_app_assets", "canvas_states", "mini_apps"):
        if _table_exists(table):
            op.drop_table(table)
