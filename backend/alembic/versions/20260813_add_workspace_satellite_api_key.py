"""add workspaces.satellite_api_key for the Satellite CLI WebSocket handshake

Revision ID: 20260813_add_workspace_satellite_api_key
Revises: 20260813_restore_debug_schema
Create Date: 2026-08-13 00:00:00.000000

Wave 90 bug fix: api/satellite_routes.py has always queried
``Workspace.satellite_api_key`` but the column never existed — every
``/api/ws/satellite/connect`` handshake and the key GET/POST endpoints
raised AttributeError (WS closed 1011, HTTP 500). The column is nullable:
the HTTP key endpoint auto-generates it on demand.

Guarded for the hybrid SQLite/PostgreSQL setup (mirrors mini-app
migrations; SQLite must use batch_alter_table).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260813_add_workspace_satellite_api_key"
down_revision: Union[str, Sequence[str], None] = "20260813_restore_debug_schema"
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
    if not _table_exists("workspaces"):
        return
    if _column_exists("workspaces", "satellite_api_key"):
        return
    if _is_postgres():
        op.add_column("workspaces", sa.Column("satellite_api_key", sa.String(128), nullable=True))
    else:
        with op.batch_alter_table("workspaces") as batch_op:
            batch_op.add_column(sa.Column("satellite_api_key", sa.String(128), nullable=True))


def downgrade() -> None:
    if _table_exists("workspaces") and _column_exists("workspaces", "satellite_api_key"):
        if _is_postgres():
            op.drop_column("workspaces", "satellite_api_key")
        else:
            with op.batch_alter_table("workspaces") as batch_op:
                batch_op.drop_column("satellite_api_key")
