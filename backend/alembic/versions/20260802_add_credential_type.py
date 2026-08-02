"""add credential_type column to llm_oauth_credentials

Revision ID: 20260802_credential_type
Revises: 20260801_gateway_models
Create Date: 2026-08-02 09:00:00.000000

Phase D (subscription-credential reuse): tags an OAuth grant as either a
regular token grant (``oauth``, the default) or a subscription-linked grant
(``subscription`` — ChatGPT Plus / Claude Pro reuse). The value is carried in
the OAuth ``state`` on connect and stored here.

Guarded for SQLite (dev DB is hybrid — schema via ``create_all``, alembic
bookkeeping lags). Existing rows get ``credential_type='oauth'`` via the
server default, preserving current behaviour.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260802_credential_type"
down_revision: Union[str, Sequence[str], None] = "20260801_gateway_models"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _table_exists("llm_oauth_credentials"):
        print("    [skip] llm_oauth_credentials table not present")
        return

    if _column_exists("llm_oauth_credentials", "credential_type"):
        print("    [skip] llm_oauth_credentials.credential_type already exists")
        return

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.add_column(
            "llm_oauth_credentials",
            sa.Column(
                "credential_type",
                sa.String(length=20),
                nullable=False,
                server_default="oauth",
            ),
        )
    else:
        # SQLite has no native ALTER COLUMN — batch_alter_table recreates the table.
        with op.batch_alter_table("llm_oauth_credentials") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "credential_type",
                    sa.String(length=20),
                    nullable=False,
                    server_default="oauth",
                )
            )


def downgrade() -> None:
    if not _table_exists("llm_oauth_credentials"):
        return
    if not _column_exists("llm_oauth_credentials", "credential_type"):
        return

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_column("llm_oauth_credentials", "credential_type")
    else:
        with op.batch_alter_table("llm_oauth_credentials") as batch_op:
            batch_op.drop_column("credential_type")
