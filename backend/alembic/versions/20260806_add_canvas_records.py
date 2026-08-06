"""add canvas_records (mini-app structured record store)

Revision ID: 20260806_canvas_records
Revises: 20260805_mini_apps
Create Date: 2026-08-06 00:00:00.000000

Mini-app data layer — the per-instance, series-scoped, append-friendly record
store. Adds one table:

* ``canvas_records`` — structured rows (``series`` namespace + monotonic
  ``seq`` + JSON ``data``) scoped by canvas/tenant/app, host-mediated
  (mirrors ``canvas_states``/``mini_app_assets`` conventions).

Guarded for the hybrid SQLite/PostgreSQL setup (mirrors
``20260805_add_mini_apps.py``): the table is only created when absent.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260806_canvas_records"
down_revision: Union[str, Sequence[str], None] = "20260805_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if table_name not in inspector.get_table_names():
        return False
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _table_exists("canvas_records"):
        op.create_table(
            "canvas_records",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("canvas_id", sa.String(), sa.ForeignKey("canvases.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("app_id", sa.String(), sa.ForeignKey("mini_apps.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_by", sa.String(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("series", sa.String(length=200), nullable=False),
            sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("data", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        )
        if not _index_exists("canvas_records", "ix_canvas_records_canvas_id"):
            op.create_index("ix_canvas_records_canvas_id", "canvas_records", ["canvas_id"])
        if not _index_exists("canvas_records", "ix_canvas_records_tenant_id"):
            op.create_index("ix_canvas_records_tenant_id", "canvas_records", ["tenant_id"])
        if not _index_exists("canvas_records", "ix_canvas_records_app_id"):
            op.create_index("ix_canvas_records_app_id", "canvas_records", ["app_id"])
        if not _index_exists("canvas_records", "ix_canvas_records_series"):
            op.create_index("ix_canvas_records_series", "canvas_records", ["series"])
        if not _index_exists("canvas_records", "ix_canvas_records_canvas_series_seq"):
            op.create_index(
                "ix_canvas_records_canvas_series_seq", "canvas_records", ["canvas_id", "series", "seq"]
            )


def downgrade() -> None:
    if _table_exists("canvas_records"):
        op.drop_table("canvas_records")
