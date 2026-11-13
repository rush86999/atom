"""Add the revocable device-session identity to ``user_sessions`` (WA-075).

Revision ID: 20261113_user_session_token_jti
Revises: 20261107_task_operation_result
Create Date: 2026-11-13

Active Sessions revokes a device through the durable ``revoked_tokens``
ledger, which needs the JWT id (``jti``) of the session. ``user_sessions``
never had a column for it, so production PostgreSQL had no way to record or
revoke an individual device session.

Local SQLite files are repaired by
``core.sqlite_schema_repair.ensure_sqlite_columns`` at startup; PostgreSQL is
owned by Alembic, so this revision adds the same nullable column and the
model-declared unique index there. The upgrade is guarded: it is a no-op when
the table is absent (fresh ``create_all`` deployment) or already has the
column/index (a database created from current models or already repaired).

``user_sessions.tenant_id`` is added when missing for the same reason: it was
added to the model after the original table-creating revision and was never
migrated. The new inventory writer sets it on every login, so leaving it out
would make each inventory INSERT fail on a PostgreSQL schema that only has
the original table shape.

No legacy row is backfilled: pre-WA-075 rows hold a raw bearer token, whose
``jti`` cannot be derived without decoding it. ``core.session_registry``
upgrades those rows lazily on the next matching login/touch, and treats rows
it cannot verify as non-revocable rather than claiming they were revoked.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20261113_user_session_token_jti"
down_revision = "20261107_task_operation_result"
branch_labels = None
depends_on = None

TOKEN_JTI_INDEX = "ix_user_sessions_token_jti"
TENANT_ID_INDEX = "ix_user_sessions_tenant_id"


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return column_name in [
        column["name"] for column in inspector.get_columns(table_name)
    ]


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    try:
        indexes = inspector.get_indexes(table_name)
    except Exception:
        return False
    return index_name in {index.get("name") for index in indexes}


def upgrade() -> None:
    if not _table_exists("user_sessions"):
        print("    [skip] user_sessions does not exist")
        return

    if not _column_exists("user_sessions", "tenant_id"):
        op.add_column(
            "user_sessions",
            sa.Column("tenant_id", sa.String(), nullable=True),
        )
    if not _index_exists("user_sessions", TENANT_ID_INDEX):
        op.create_index(
            TENANT_ID_INDEX, "user_sessions", ["tenant_id"], unique=False)

    if not _column_exists("user_sessions", "token_jti"):
        op.add_column(
            "user_sessions",
            sa.Column("token_jti", sa.String(), nullable=True),
        )
    if not _index_exists("user_sessions", TOKEN_JTI_INDEX):
        op.create_index(
            TOKEN_JTI_INDEX, "user_sessions", ["token_jti"], unique=True)


def downgrade() -> None:
    if not _table_exists("user_sessions"):
        return

    if _index_exists("user_sessions", TOKEN_JTI_INDEX):
        op.drop_index(TOKEN_JTI_INDEX, table_name="user_sessions")
    if _column_exists("user_sessions", "token_jti"):
        with op.batch_alter_table("user_sessions") as batch_op:
            batch_op.drop_column("token_jti")

    # ``tenant_id`` predates this revision (it was added to the model without
    # a migration), so downgrade deliberately keeps the column and its index:
    # dropping them would destroy inventory data this revision did not create.
