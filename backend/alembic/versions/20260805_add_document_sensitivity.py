"""add sensitivity column to ingested_documents and knowledge_documents

Revision ID: 20260805_doc_sensitivity
Revises: 20260805_add_workspace_scoping
Create Date: 2026-08-05 00:00:00.000000

Phase P4 (Cloudflare G4) — observation-based data taint:

Adds a nullable ``sensitivity`` column to ``ingested_documents`` and
``knowledge_documents`` so the data-taint tracker can classify documents by
sensitivity (public|internal|confidential|restricted) and gate outbound actions
that would send restricted data to external destinations. Existing rows default
to ``internal`` via the server default — no data migration needed for existing
content, and nullable so the column add never fails on a populated table.

Guarded for SQLite (dev DB is hybrid — schema via ``create_all``, alembic
bookkeeping lags). Mirrors the guard pattern in
``20260804_add_doc_freshness.py``: ``_table_exists``/``_column_exists``
helpers plus ``op.batch_alter_table`` for column adds.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260805_doc_sensitivity"
down_revision: Union[str, Sequence[str], None] = "20260805_add_workspace_scoping"
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


def _add_sensitivity(table_name: str) -> None:
    if not _table_exists(table_name):
        print(f"    [skip] {table_name} table not present")
        return
    if _column_exists(table_name, "sensitivity"):
        print(f"    [skip] {table_name}.sensitivity already exists")
        return

    bind = op.get_bind()
    col = sa.Column(
        "sensitivity",
        sa.String(length=20),
        nullable=True,
        server_default="internal",
    )
    if bind.dialect.name == "postgresql":
        op.add_column(table_name, col)
    else:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(col)
    print(f"    [ok] added {table_name}.sensitivity")


def _drop_sensitivity(table_name: str) -> None:
    if not _table_exists(table_name):
        return
    if not _column_exists(table_name, "sensitivity"):
        return
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_column(table_name, "sensitivity")
    else:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_column("sensitivity")


def upgrade() -> None:
    _add_sensitivity("ingested_documents")
    _add_sensitivity("knowledge_documents")


def downgrade() -> None:
    _drop_sensitivity("ingested_documents")
    _drop_sensitivity("knowledge_documents")
