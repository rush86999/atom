"""add fts5 indexes over ingested_documents and knowledge_documents

Revision ID: 20260808_documents_fts
Revises: 0e360bb1a3d3_agent_message_from_user
Create Date: 2026-08-08 20:00:00.000000

Adds FTS5 external-content virtual tables over IngestedDocument
(file_name + content_preview) and KnowledgeDocument (title + content) so
documents.search gets a real BM25 lexical leg — the SQLite/PG twin of the
agent_reasoning_steps_fts pattern (20260624_add_reasoning_fts).

Postgres: generated tsvector column + GIN index per table.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260808_documents_fts"
down_revision: Union[str, Sequence[str], None] = "0e360bb1a3d3_agent_message_from_user"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def _create_fts_sqlite(fts_name: str, base_name: str, cols: str) -> None:
    op.execute(
        f"CREATE VIRTUAL TABLE {fts_name} USING fts5("
        f"{cols}, content='{base_name}', content_rowid='rowid')"
    )
    col_sql = ", ".join(f"COALESCE({c},'')" for c in cols.split(", "))
    op.execute(
        f"INSERT INTO {fts_name}(rowid, {cols}) "
        f"SELECT rowid, {col_sql} FROM {base_name}"
    )
    op.execute(
        f"CREATE TRIGGER {fts_name}_ai AFTER INSERT ON {base_name} BEGIN "
        f"INSERT INTO {fts_name}(rowid, {cols}) "
        f"VALUES (new.rowid, {col_sql}); END"
    )
    op.execute(
        f"CREATE TRIGGER {fts_name}_ad AFTER DELETE ON {base_name} BEGIN "
        f"INSERT INTO {fts_name}({fts_name}, rowid, {cols}) "
        f"VALUES('delete', old.rowid, {col_sql}); END"
    )
    op.execute(
        f"CREATE TRIGGER {fts_name}_au AFTER UPDATE ON {base_name} BEGIN "
        f"INSERT INTO {fts_name}({fts_name}, rowid, {cols}) "
        f"VALUES('delete', old.rowid, {col_sql}); "
        f"INSERT INTO {fts_name}(rowid, {cols}) "
        f"VALUES (new.rowid, {col_sql}); END"
    )


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        if _table_exists("ingested_documents") and not _table_exists("ingested_documents_fts"):
            _create_fts_sqlite(
                "ingested_documents_fts",
                "ingested_documents",
                "file_name, content_preview",
            )
        if _table_exists("knowledge_documents") and not _table_exists("knowledge_documents_fts"):
            _create_fts_sqlite(
                "knowledge_documents_fts",
                "knowledge_documents",
                "title, content",
            )

    elif bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE ingested_documents "
            "ADD COLUMN IF NOT EXISTS search_vector tsvector "
            "GENERATED ALWAYS AS "
            "(to_tsvector('english', coalesce(file_name,'') || ' ' || coalesce(content_preview,''))) STORED"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_ingested_documents_search "
            "ON ingested_documents USING gin(search_vector)"
        )
        op.execute(
            "ALTER TABLE knowledge_documents "
            "ADD COLUMN IF NOT EXISTS search_vector tsvector "
            "GENERATED ALWAYS AS "
            "(to_tsvector('english', coalesce(title,'') || ' ' || coalesce(content,''))) STORED"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_knowledge_documents_search "
            "ON knowledge_documents USING gin(search_vector)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        for fts, base in (
            ("ingested_documents_fts", "ingested_documents"),
            ("knowledge_documents_fts", "knowledge_documents"),
        ):
            op.execute(f"DROP TRIGGER IF EXISTS {fts}_au")
            op.execute(f"DROP TRIGGER IF EXISTS {fts}_ad")
            op.execute(f"DROP TRIGGER IF EXISTS {fts}_ai")
            op.execute(f"DROP TABLE IF EXISTS {fts}")
    elif bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_ingested_documents_search")
        op.execute(
            "ALTER TABLE ingested_documents DROP COLUMN IF EXISTS search_vector"
        )
        op.execute("DROP INDEX IF EXISTS ix_knowledge_documents_search")
        op.execute(
            "ALTER TABLE knowledge_documents DROP COLUMN IF EXISTS search_vector"
        )
