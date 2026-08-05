"""add canvas_logic table + custom_components schema columns

Revision ID: 20260805_canvas_logic
Revises: 20260805_doc_sensitivity
Create Date: 2026-08-05 00:00:00.000000

Phase P7 (Cloudflare G7b) — per-canvas server runtime + CustomComponent schema fix:

* Creates the ``canvas_logic`` table (canvas_id, language, source, created_by,
  timestamps) storing Python handlers executed via SandboxRuntime.execute_python
  with a per-canvas storage namespace.
* Adds the missing columns to ``custom_components`` (slug, props_schema,
  default_props, is_public, current_version, min_maturity_level, tenant_id) that
  ``core/custom_components_service.py`` writes/reads but the stub model did not
  declare (live schema drift; would crash at runtime).

Guarded for SQLite (dev DB is hybrid — schema via ``create_all``, alembic
bookkeeping lags). Mirrors the guard pattern in ``20260804_add_doc_freshness.py``.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260805_canvas_logic"
down_revision: Union[str, Sequence[str], None] = "20260805_doc_sensitivity"
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
    bind = op.get_bind()

    # 1. canvas_logic table (create only if absent).
    if not _table_exists("canvas_logic"):
        op.create_table(
            "canvas_logic",
            sa.Column("id", sa.String(length=255), primary_key=True),
            sa.Column("canvas_id", sa.String(length=255), nullable=False, index=True),
            sa.Column("language", sa.String(length=32), nullable=False, server_default="python"),
            sa.Column("source", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_by", sa.String(length=255), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        print("    [ok] created canvas_logic table")

    # 2. custom_components schema repair (add missing columns, guarded).
    if _table_exists("custom_components"):
        _add_column("custom_components", "slug", sa.String(length=255), nullable=True)
        _add_column("custom_components", "tenant_id", sa.String(length=255), nullable=True)
        _add_column("custom_components", "is_public", sa.Boolean(), server_default=sa.text("0"))
        _add_column("custom_components", "props_schema", sa.Text(), nullable=True)
        _add_column("custom_components", "default_props", sa.Text(), nullable=True)
        _add_column("custom_components", "min_maturity_level", sa.String(length=32), nullable=True)
        _add_column("custom_components", "current_version", sa.Integer(), server_default=sa.text("1"))


def _add_column(table: str, col_name: str, col_type, nullable=True, server_default=None) -> None:
    if _column_exists(table, col_name):
        return
    kwargs = {}
    if server_default is not None:
        kwargs["server_default"] = server_default
    col = sa.Column(col_name, col_type, nullable=nullable, **kwargs)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.add_column(table, col)
    else:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(col)
    print(f"    [ok] added {table}.{col_name}")


def downgrade() -> None:
    if _table_exists("canvas_logic"):
        op.drop_table("canvas_logic")
    # custom_components columns: left in place (additive, nullable/defaulted —
    # safe to keep on downgrade to avoid data loss).
