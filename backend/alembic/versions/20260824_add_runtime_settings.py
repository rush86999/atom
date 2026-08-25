"""runtime_settings + setting_change_audit tables (env vars as UI settings)

Revision ID: 20260824_runtime_settings
Revises: 20260823_scv_hash_algo
Create Date: 2026-08-24 00:00:00.000000

Creates the generic key-value store behind the admin runtime-settings
surface (``core/runtime_settings.py`` + ``api/admin_runtime_settings_routes.py``):

- ``runtime_settings``      — one row per UI-overridden env var
                              (explicit env still wins — kill-switch semantics)
- ``setting_change_audit``  — append-only who/when/what trail

Guarded create pattern for the hybrid SQLite/PostgreSQL setup.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260824_runtime_settings"
down_revision: Union[str, Sequence[str], None] = "20260823_scv_hash_algo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("runtime_settings"):
        op.create_table(
            "runtime_settings",
            sa.Column("key", sa.String(length=128), primary_key=True),
            sa.Column("value_json", sa.JSON(), nullable=True),
            sa.Column("updated_by", sa.String(), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )

    if not _table_exists("setting_change_audit"):
        op.create_table(
            "setting_change_audit",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("setting_key", sa.String(length=128), nullable=False),
            sa.Column("old_value_json", sa.JSON(), nullable=True),
            sa.Column("new_value_json", sa.JSON(), nullable=True),
            sa.Column("changed_by", sa.String(), nullable=True),
            sa.Column(
                "changed_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_setting_change_audit_setting_key",
            "setting_change_audit",
            ["setting_key"],
        )


def downgrade() -> None:
    if _table_exists("setting_change_audit"):
        op.drop_index(
            "ix_setting_change_audit_setting_key", table_name="setting_change_audit"
        )
        op.drop_table("setting_change_audit")
    if _table_exists("runtime_settings"):
        op.drop_table("runtime_settings")
