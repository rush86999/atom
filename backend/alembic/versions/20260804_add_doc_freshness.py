"""add document freshness tracking columns

Revision ID: 20260804_doc_freshness
Revises: 20260802_chat_session_channel
Create Date: 2026-08-04 00:00:00.000000

Adds freshness/outdated-tracking columns to ``ingested_documents`` so the
ingestion pipeline can detect when an ingested document has gone stale
relative to its source (content changed upstream, aged out, or removed
upstream) and record a filterable ``freshness_status``.

It also adds a ``superseded_by`` column for document supersession: when a
newer document on the same topic (same integration) is ingested, older
same-topic docs are marked ``freshness_status='superseded'`` and linked to
the newer doc via ``superseded_by``.

Mirrors the ``GovernanceDocument.last_verified`` pattern
(models.py:2121) and the ``policy_search_service._get_verification_status``
derivation. The ``freshness_status`` column gets a server default of
``'fresh'`` so existing rows are considered fresh until the first
reevaluation pass runs (see core/doc_freshness_service.py).

All new columns are nullable (or defaulted) so this migration is safe on
the hybrid SQLite/PostgreSQL setup and ``Base.metadata.create_all`` stays
consistent with alembic.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260804_doc_freshness"
down_revision: Union[str, Sequence[str], None] = "20260802_chat_session_channel"
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


def _index_exists(table_name: str, index_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if table_name not in inspector.get_table_names():
        return False
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    # Fresh DBs create the table (with our columns + index) via
    # Base.metadata.create_all at app start. Nothing to do here.
    if not _table_exists("ingested_documents"):
        return

    new_columns = [
        ("source_url", sa.Column("source_url", sa.String(length=1024), nullable=True)),
        ("source_content_hash", sa.Column("source_content_hash", sa.String(), nullable=True)),
        (
            "last_verified_at",
            sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        ),
        (
            "source_modified_at",
            sa.Column("source_modified_at", sa.DateTime(timezone=True), nullable=True),
        ),
        (
            "freshness_status",
            sa.Column(
                "freshness_status",
                sa.String(length=32),
                nullable=False,
                server_default="fresh",
            ),
        ),
        (
            "superseded_by",
            sa.Column("superseded_by", sa.String(), nullable=True),
        ),
    ]

    for col_name, col_def in new_columns:
        if not _column_exists("ingested_documents", col_name):
            with op.batch_alter_table("ingested_documents") as batch_op:
                batch_op.add_column(col_def)

    # Index freshness_status so retrieval can prefilter stale/outdated rows
    # cheaply. This mirrors the column added to the ORM model.
    if not _index_exists("ingested_documents", "ix_ingested_documents_freshness_status"):
        bind = op.get_bind()
        if bind.dialect.name == "postgresql":
            op.execute(
                "CREATE INDEX IF NOT EXISTS ix_ingested_documents_freshness_status "
                "ON ingested_documents (freshness_status)"
            )
        else:
            op.create_index(
                "ix_ingested_documents_freshness_status",
                "ingested_documents",
                ["freshness_status"],
            )


def downgrade() -> None:
    if not _table_exists("ingested_documents"):
        return

    bind = op.get_bind()

    if _index_exists("ingested_documents", "ix_ingested_documents_freshness_status"):
        if bind.dialect.name == "postgresql":
            op.execute("DROP INDEX IF EXISTS ix_ingested_documents_freshness_status")
        else:
            try:
                op.drop_index(
                    "ix_ingested_documents_freshness_status",
                    table_name="ingested_documents",
                )
            except Exception:
                pass

    for col_name in [
        "superseded_by",
        "freshness_status",
        "source_modified_at",
        "last_verified_at",
        "source_content_hash",
        "source_url",
    ]:
        if _column_exists("ingested_documents", col_name):
            with op.batch_alter_table("ingested_documents") as batch_op:
                batch_op.drop_column(col_name)
