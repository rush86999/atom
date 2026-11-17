"""Upgrade existing ``dataset_entries`` with exact source-document lineage.

Revision ID: 20261117_dataset_entry_lineage
Revises: 20261116_action_autonomy_rules
Create Date: 2026-11-17

Why this revision exists
------------------------
``DatasetEntry.source_document_id`` is the exact lineage that lets document
deletion revoke (tombstone) the sheet-dataset rows materialized from that
document instead of leaving them ``active`` as current grounding. The ORM
column and the SQLite startup repair (``core.sqlite_schema_repair``) landed
with the lineage/tombstone work, but neither reaches an existing PostgreSQL
database:

* the only runtime schema hook is ``Base.metadata.create_all`` (main_api_app
  lifespan, minimal_app startup), and ``create_all`` never ALTERs an existing
  table, so an existing ``dataset_entries`` keeps its old shape;
* PostgreSQL deployments upgrade through Alembic (``alembic upgrade heads``;
  a fresh install is ``create_all`` + ``alembic stamp heads``), and no
  revision added this column.

Every ORM catalog read selects ``source_document_id``, so without this
upgrade an existing PostgreSQL install fails the whole sheet-dataset read
path after the code deploys, and the delete-time revocation sweep has no
lineage to match. ``dataset_entries`` itself has no earlier Alembic revision
(it is a ``create_all`` table), so this guarded upgrade may be the first
migration to touch it.

Upgrade contract
----------------
General guarded existing-table upgrade, following the shape used by
``20261107_task_operation_result_json`` and ``20261113_user_session_token_jti``:

* no-op if ``dataset_entries`` is absent — the fresh ``create_all`` path
  already builds the current shape and stays authoritative;
* no-op if the nullable column already exists (database created from current
  models, or already repaired), so re-running against any state is safe;
* creates the model-declared ``ix_dataset_entries_source_document_id`` index
  only when missing;
* never backfills: a legacy row's source document cannot be proven from a
  filename or content address, and the lineage contract only revokes on
  proven identity. Pre-existing rows therefore stay NULL and are treated as
  unprovable/never-revoked-by-filename, exactly as the service expects;
* does not rewrite, drop, or recreate any row, the version unique constraint,
  or the existing file-lookup index. ``ADD COLUMN`` with no default is a
  metadata-only change on PostgreSQL.

SQLite files keep using ``core.sqlite_schema_repair.ensure_sqlite_columns``
at startup; this revision neither replaces nor duplicates that path.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# Alembic's installed version column is VARCHAR(32) on both SQLite and
# existing PostgreSQL databases (core/alembic_version_table.py only widens
# fresh PostgreSQL bootstraps). Keep the identifier within 32 characters.
revision = "20261117_dataset_entry_lineage"
down_revision = "20261116_action_autonomy_rules"
branch_labels = None
depends_on = None

TABLE = "dataset_entries"
COLUMN = "source_document_id"
INDEX = "ix_dataset_entries_source_document_id"


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    inspector = sa.inspect(op.get_bind())
    return column_name in {
        column["name"] for column in inspector.get_columns(table_name)
    }


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    inspector = sa.inspect(op.get_bind())
    try:
        indexes = inspector.get_indexes(table_name)
    except Exception:
        return False
    return index_name in {index.get("name") for index in indexes}


def upgrade() -> None:
    if not _table_exists(TABLE):
        print(f"    [skip] {TABLE} does not exist (fresh create_all path)")
        return

    if not _column_exists(TABLE, COLUMN):
        op.add_column(
            TABLE,
            sa.Column(COLUMN, sa.String(), nullable=True),
        )

    if not _index_exists(TABLE, INDEX):
        op.create_index(INDEX, TABLE, [COLUMN], unique=False)


def downgrade() -> None:
    if not _table_exists(TABLE):
        return

    if _index_exists(TABLE, INDEX):
        op.drop_index(INDEX, table_name=TABLE)

    if _column_exists(TABLE, COLUMN):
        # batch_alter_table keeps the downgrade portable to SQLite (which
        # cannot DROP COLUMN on older versions). The named version unique
        # constraint and the file-lookup index are reflected and recreated
        # as part of that batch; the test round-trip asserts both survive.
        with op.batch_alter_table(TABLE) as batch_op:
            batch_op.drop_column(COLUMN)
