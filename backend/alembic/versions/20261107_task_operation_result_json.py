"""Persist the exact durable result/receipt on an outbound operation claim.

A succeeded ``task_operation_records`` claim must carry the exact provider
resource identity and authorized material so a later replay can re-read the
SAME resource instead of guessing from a title or permanently reporting a
known success as unverifiable.  Local SQLite installs are repaired by
``core.sqlite_schema_repair.ensure_sqlite_columns`` at startup; PostgreSQL is
owned by alembic, so this revision adds the same nullable column there.

The upgrade is guarded: it is a no-op when the table does not exist (fresh
``create_all`` deployments) or the column is already present (a database
created from the current models or already repaired).  No receipt is
backfilled; a pre-existing succeeded claim legitimately has no identity
receipt and must continue to replay as ``committed_unverified``.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20261107_task_operation_result_json"
down_revision = "a2f0c1d4e5b6"
branch_labels = None
depends_on = None


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


def upgrade() -> None:
    if not _table_exists("task_operation_records"):
        print("    [skip] task_operation_records does not exist")
        return
    if _column_exists("task_operation_records", "result_json"):
        print("    [skip] task_operation_records.result_json already exists")
        return
    op.add_column(
        "task_operation_records",
        sa.Column("result_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    if not _table_exists("task_operation_records"):
        return
    if not _column_exists("task_operation_records", "result_json"):
        return
    with op.batch_alter_table("task_operation_records") as batch_op:
        batch_op.drop_column("result_json")
