"""experience marketplace: lesson item + role registry + audit tables

Revision ID: 20260820_experience_marketplace
Revises: 20260816_org_ingestion_sharing
Create Date: 2026-08-20 00:00:00.000000

Experience Marketplace MVP (docs/architecture/EXPERIENCE_MARKETPLACE.md):
- ``experience_items``: idempotent lesson store (dedup key
  (workspace_id, source_agent_id, item_id); content-hash dedup; tombstones
  via superseded_at).
- ``experience_role_registry``: deterministic entity-name -> role-token map
  (names are identities — never exported, tokens only).
- ``experience_exports`` / ``experience_imports``: audit rows for the
  CRITICAL/HIGH gates.

Guarded for the hybrid SQLite/PostgreSQL setup (SQLite requires
batch_alter_table; dev DB is schema-via-create_all + alembic bookkeeping lags).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260820_experience_marketplace"
down_revision: Union[str, Sequence[str], None] = "20260816_org_ingestion_sharing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return index_name in {ix["name"] for ix in inspector.get_indexes(table_name)}


def upgrade() -> None:
    if not _table_exists("experience_items"):
        op.create_table(
            "experience_items",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("workspace_id", sa.String(length=64), nullable=False),
            sa.Column("tenant_id", sa.String(length=64), nullable=True),
            sa.Column("source_agent_id", sa.String(length=255), nullable=False),
            sa.Column("kind", sa.String(length=32), nullable=False),
            sa.Column("item_id", sa.String(length=255), nullable=False),
            sa.Column("sensitivity", sa.String(length=32), nullable=False, server_default="internal"),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("content_hash", sa.String(length=64), nullable=False),
            sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("imported_from", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("workspace_id", "source_agent_id", "item_id", name="uq_experience_item_key"),
        )
        op.create_index("ix_experience_items_workspace_kind", "experience_items", ["workspace_id", "kind"])
        op.create_index("ix_experience_items_workspace_agent", "experience_items", ["workspace_id", "source_agent_id"])
        op.create_index("ix_experience_items_content_hash", "experience_items", ["content_hash"])

    if not _table_exists("experience_role_registry"):
        op.create_table(
            "experience_role_registry",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("workspace_id", sa.String(length=64), nullable=False),
            sa.Column("entity_type", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("token", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("workspace_id", "entity_type", "name", name="uq_experience_role_name"),
        )
        op.create_index("ix_experience_role_token", "experience_role_registry", ["workspace_id", "token"])

    if not _table_exists("experience_exports"):
        op.create_table(
            "experience_exports",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("workspace_id", sa.String(length=64), nullable=False),
            sa.Column("tenant_id", sa.String(length=64), nullable=True),
            sa.Column("agent_id", sa.String(length=255), nullable=False),
            sa.Column("sensitivity_ceiling", sa.String(length=32), nullable=False, server_default="internal"),
            sa.Column("destination", sa.String(length=255), nullable=True),
            sa.Column("sections", sa.JSON(), nullable=True),
            sa.Column("delta", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("section_counts", sa.JSON(), nullable=True),
            sa.Column("excluded_by_sensitivity", sa.JSON(), nullable=True),
            sa.Column("payload_hash", sa.String(length=64), nullable=False),
            sa.Column("signature", sa.Text(), nullable=False),
            sa.Column("signed_by", sa.String(length=255), nullable=True),
            sa.Column("performed_by", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_experience_exports_workspace_agent", "experience_exports", ["workspace_id", "agent_id"])

    if not _table_exists("experience_imports"):
        op.create_table(
            "experience_imports",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("workspace_id", sa.String(length=64), nullable=False),
            sa.Column("tenant_id", sa.String(length=64), nullable=True),
            sa.Column("source_agent_id", sa.String(length=255), nullable=True),
            sa.Column("payload_hash", sa.String(length=64), nullable=False),
            sa.Column("signature_valid", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("signature_strip_credentials", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("sensitivity_ceiling", sa.String(length=32), nullable=True),
            sa.Column("item_total", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("item_applied", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("item_skipped", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("item_excluded", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("tombstones_applied", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("nodes_applied", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("edges_applied", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("edges_skipped", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("section_counts", sa.JSON(), nullable=True),
            sa.Column("failure_reason", sa.String(length=255), nullable=True),
            sa.Column("performed_by", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_experience_imports_workspace", "experience_imports", ["workspace_id"])


def downgrade() -> None:
    for table in ("experience_imports", "experience_exports", "experience_role_registry", "experience_items"):
        if _table_exists(table):
            op.drop_table(table)