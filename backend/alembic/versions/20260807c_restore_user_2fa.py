"""restore user 2FA columns

Revision ID: 20260807c_restore_user_2fa
Revises: 20260807_merge_heads
Create Date: 2026-08-07 08:00:00.000000

``two_factor_enabled`` / ``two_factor_secret`` / ``two_factor_backup_codes``
were commented out of the ``User`` model on 2026-04-29 (d212681f32), silently
breaking the 2FA management endpoints (``api/auth_2fa_routes.py`` reads
``current_user.two_factor_enabled`` directly → AttributeError) and the login
TOTP flow. The columns are restored in ``core/models.py``; this migration adds
them for existing databases (PostgreSQL production, and SQLite deployments
whose tables were created after the columns were removed).

Guarded for the hybrid SQLite/PostgreSQL setup: SQLite column adds use
``op.batch_alter_table`` and both helpers skip cleanly when the table/column
already exists.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260807c_restore_user_2fa"
down_revision: Union[str, Sequence[str], None] = "20260807_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return column_name in [c["name"] for c in inspector.get_columns(table_name)]


def upgrade() -> None:
    if not _table_exists("users"):
        print("    [skip] users does not exist")
        return
    additions = (
        ("two_factor_enabled", sa.Boolean(), True),
        ("two_factor_secret", sa.String(), None),
        ("two_factor_backup_codes", sa.JSON(), None),
    )
    with op.batch_alter_table("users") as batch_op:
        for column_name, column_type, default in additions:
            if _column_exists("users", column_name):
                print(f"    [skip] users.{column_name} already exists")
                continue
            batch_op.add_column(
                sa.Column(column_name, column_type, nullable=True, default=default)
            )


def downgrade() -> None:
    if not _table_exists("users"):
        return
    for column_name in ("two_factor_backup_codes", "two_factor_secret", "two_factor_enabled"):
        if not _column_exists("users", column_name):
            continue
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column(column_name)
