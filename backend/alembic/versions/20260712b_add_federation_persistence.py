"""add federation_dids + federation_credentials tables

Revision ID: 20260712b_federation_persist
Revises: 20260712_local_models
Create Date: 2026-07-12 00:00:00.000000

Adds durable storage for the zero-trust federation identity system. Previously
DIDManager and VerifiableCredentialManager used in-memory dicts that reset on
every restart. These tables let identity state persist.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260712b_federation_persist"
down_revision: Union[str, Sequence[str], None] = "20260712_local_models"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("federation_dids"):
        op.create_table(
            "federation_dids",
            sa.Column("did", sa.String(), nullable=False),
            sa.Column("entity_type", sa.String(), nullable=False),
            sa.Column("entity_id", sa.String(), nullable=False),
            sa.Column("document_json", sa.JSON(), nullable=True),
            sa.Column("public_key_pem", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("did"),
        )
        op.create_index("ix_federation_dids_entity_id", "federation_dids", ["entity_id"])
    else:
        print("    [skip] federation_dids already exists")

    if not _table_exists("federation_credentials"):
        op.create_table(
            "federation_credentials",
            sa.Column("credential_id", sa.String(), nullable=False),
            sa.Column("issuer_did", sa.String(), nullable=False),
            sa.Column("subject_did", sa.String(), nullable=False),
            sa.Column("credential_type", sa.String(), nullable=False),
            sa.Column("claims_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revocation_reason", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("credential_id"),
        )
        op.create_index("ix_federation_credentials_issuer_did", "federation_credentials", ["issuer_did"])
        op.create_index("ix_federation_credentials_subject_did", "federation_credentials", ["subject_did"])
    else:
        print("    [skip] federation_credentials already exists")


def downgrade() -> None:
    op.drop_index("ix_federation_credentials_subject_did", table_name="federation_credentials")
    op.drop_index("ix_federation_credentials_issuer_did", table_name="federation_credentials")
    op.drop_table("federation_credentials")
    op.drop_index("ix_federation_dids_entity_id", table_name="federation_dids")
    op.drop_table("federation_dids")
