"""org ingestion sharing: ingestion_settings persistence cols + sharing tables

Revision ID: 20260816_org_ingestion_sharing
Revises: 20260813_add_workspace_satellite_api_key
Create Date: 2026-08-16 00:00:00.000000

Org Ingestion Sharing plan (docs/architecture/ORG_INGESTION_SHARING_PLAN.md):
- Phase 0: persist the hybrid ingestion pipeline state that previously lived
  only in in-memory dicts (HybridDataIngestionService.sync_configs /
  usage_stats). New columns on ``ingestion_settings``.
- Phase 1/2: new tables ``org_public_keys``, ``ingestion_profile_imports``,
  ``bundle_exports``, ``bundle_imports``.

Guarded for the hybrid SQLite/PostgreSQL setup (mirrors mini-app migrations;
SQLite must use batch_alter_table).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260816_org_ingestion_sharing"
down_revision: Union[str, Sequence[str], None] = "20260813_add_workspace_satellite_api_key"
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
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade() -> None:
    # --- Phase 0: ingestion_settings persistence columns ---
    if _table_exists("ingestion_settings"):
        with op.batch_alter_table("ingestion_settings") as batch:
            if not _column_exists("ingestion_settings", "entity_types"):
                batch.add_column(sa.Column("entity_types", sa.JSON(), nullable=True))
            if not _column_exists("ingestion_settings", "sync_last_n_days"):
                batch.add_column(sa.Column("sync_last_n_days", sa.Integer(), nullable=True))
            if not _column_exists("ingestion_settings", "max_records_per_sync"):
                batch.add_column(sa.Column("max_records_per_sync", sa.Integer(), nullable=True))
            if not _column_exists("ingestion_settings", "sync_mode"):
                batch.add_column(sa.Column("sync_mode", sa.String(), nullable=True))
            if not _column_exists("ingestion_settings", "usage_stats_json"):
                batch.add_column(sa.Column("usage_stats_json", sa.JSON(), nullable=True))

    # --- Phase 2b: sensitivity taint on graph nodes ---
    if _table_exists("graph_nodes") and not _column_exists("graph_nodes", "sensitivity"):
        with op.batch_alter_table("graph_nodes") as batch:
            batch.add_column(sa.Column(
                "sensitivity", sa.String(20), nullable=True,
                server_default="internal",
            ))

    # --- Phase 1/2: org key registry + profile import audit ---
    if not _table_exists("org_public_keys"):
        op.create_table(
            "org_public_keys",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
            sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True),
            sa.Column("label", sa.String(255), nullable=False),
            sa.Column("public_key", sa.String(128), nullable=False),
            sa.Column("fingerprint", sa.String(64), nullable=False),
            sa.Column("is_own", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_org_public_keys_tenant_id", "org_public_keys", ["tenant_id"])
        op.create_index("ix_org_public_keys_workspace_id", "org_public_keys", ["workspace_id"])
        op.create_index("ix_org_public_keys_public_key", "org_public_keys", ["public_key"])
        op.create_index("ix_org_public_keys_fingerprint", "org_public_keys", ["fingerprint"])
        op.create_index("ix_org_public_keys_own", "org_public_keys", ["workspace_id", "is_own"])

    if not _table_exists("ingestion_profile_imports"):
        op.create_table(
            "ingestion_profile_imports",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
            sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
            sa.Column("profile_version", sa.Integer(), nullable=False),
            sa.Column("signature_valid", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("applied_integrations", sa.JSON(), nullable=True),
            sa.Column("performed_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_ingestion_profile_imports_tenant_id", "ingestion_profile_imports", ["tenant_id"])
        op.create_index("ix_ingestion_profile_imports_workspace_id", "ingestion_profile_imports", ["workspace_id"])

    # --- Phase 2: bundle export/import audit ---
    if not _table_exists("bundle_exports"):
        op.create_table(
            "bundle_exports",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
            sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
            sa.Column("payload_hash", sa.String(64), nullable=False),
            sa.Column("sources", sa.JSON(), nullable=True),
            sa.Column("record_count", sa.Integer(), nullable=True),
            sa.Column("sensitivity_breakdown", sa.JSON(), nullable=True),
            sa.Column("section_counts", sa.JSON(), nullable=True),
            sa.Column("destination", sa.String(255), nullable=True),
            sa.Column("performed_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_bundle_exports_tenant_id", "bundle_exports", ["tenant_id"])
        op.create_index("ix_bundle_exports_workspace_id", "bundle_exports", ["workspace_id"])
        op.create_index("ix_bundle_exports_payload_hash", "bundle_exports", ["payload_hash"])

    if not _table_exists("bundle_imports"):
        op.create_table(
            "bundle_imports",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
            sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
            sa.Column("payload_hash", sa.String(64), nullable=False),
            sa.Column("records_total", sa.Integer(), nullable=True),
            sa.Column("records_ingested", sa.Integer(), nullable=True),
            sa.Column("records_skipped", sa.Integer(), nullable=True),
            sa.Column("tombstones_applied", sa.Integer(), nullable=True),
            sa.Column("section_counts", sa.JSON(), nullable=True),
            sa.Column("performed_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_bundle_imports_tenant_id", "bundle_imports", ["tenant_id"])
        op.create_index("ix_bundle_imports_workspace_id", "bundle_imports", ["workspace_id"])
        op.create_index("ix_bundle_imports_payload_hash", "bundle_imports", ["payload_hash"])


def downgrade() -> None:
    if _table_exists("bundle_imports"):
        op.drop_table("bundle_imports")
    if _table_exists("bundle_exports"):
        op.drop_table("bundle_exports")
    if _table_exists("ingestion_profile_imports"):
        op.drop_table("ingestion_profile_imports")
    if _table_exists("org_public_keys"):
        op.drop_table("org_public_keys")
    if _table_exists("graph_nodes") and _column_exists("graph_nodes", "sensitivity"):
        with op.batch_alter_table("graph_nodes") as batch:
            batch.drop_column("sensitivity")
    if _table_exists("ingestion_settings"):
        with op.batch_alter_table("ingestion_settings") as batch:
            for col in ("entity_types", "sync_last_n_days", "max_records_per_sync", "sync_mode", "usage_stats_json"):
                if _column_exists("ingestion_settings", col):
                    batch.drop_column(col)
