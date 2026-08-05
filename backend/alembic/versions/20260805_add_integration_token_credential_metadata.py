"""add credential_metadata column to integration_tokens

Revision ID: 20260805_integration_token_credential_metadata
Revises: 20260804_doc_freshness
Create Date: 2026-08-05 00:00:00.000000

P0 (Cloudflare OS G1): tags encrypted IntegrationToken rows so the migration
audit (``scripts/verify_token_encryption.py``) can distinguish Fernet-encrypted
rows from legacy plaintext rows. Adds a nullable JSON ``credential_metadata``
column and backfills ``{"encryption": "fernet"}`` on rows whose ``access_token``
already looks like Fernet ciphertext (``gAAAA%``).

Guarded for SQLite (dev DB is hybrid — schema via ``create_all``, alembic
bookkeeping lags). Existing rows keep the column NULL until re-encrypted.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260805_integration_token_credential_metadata"
down_revision: Union[str, Sequence[str], None] = "20260804_doc_freshness"
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


def upgrade() -> None:
    if not _table_exists("integration_tokens"):
        print("    [skip] integration_tokens table not present")
        return

    if not _column_exists("integration_tokens", "credential_metadata"):
        with op.batch_alter_table("integration_tokens") as batch_op:
            batch_op.add_column(sa.Column("credential_metadata", sa.JSON(), nullable=True))

    # Backfill the encryption flag on rows that already hold Fernet ciphertext.
    bind = op.get_bind()
    try:
        rows = bind.execute(
            sa.text(
                "SELECT id FROM integration_tokens "
                "WHERE access_token LIKE 'gAAAA%' "
                "AND (credential_metadata IS NULL OR credential_metadata = '{}' "
                "OR json_extract(credential_metadata, '$.encryption') IS NULL)"
            )
        ).fetchall()
        for (rid,) in rows:
            bind.execute(
                sa.text(
                    "UPDATE integration_tokens SET credential_metadata = :meta WHERE id = :rid"
                ),
                {"meta": sa.text("'{\"encryption\": \"fernet\"}'"), "rid": rid},
            )
    except Exception as e:  # pragma: no cover - dialect quirks (e.g. SQLite json_extract)
        print(f"    [warn] credential_metadata backfill skipped: {e}")


def downgrade() -> None:
    if not _table_exists("integration_tokens"):
        return
    if not _column_exists("integration_tokens", "credential_metadata"):
        return
    with op.batch_alter_table("integration_tokens") as batch_op:
        batch_op.drop_column("credential_metadata")
