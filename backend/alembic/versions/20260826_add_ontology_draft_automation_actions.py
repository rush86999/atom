"""add ontology_draft_actions table

Revision ID: 20260826_ontology_draft_actions
Revises: 20260824_runtime_settings
Create Date: 2026-08-26 00:00:00.000000

Consent-gated automation ledger for ontology draft promotion — mirrors
trust_calibration_actions. Guarded create per repo convention.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260826_ontology_draft_actions"
down_revision: Union[str, Sequence[str], None] = "20260824_runtime_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("ontology_draft_actions"):
        return
    op.create_table(
        "ontology_draft_actions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("entity_type_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("verdict", sa.String(length=16), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False,
                  server_default="approval"),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), index=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_ontology_draft_auto_type_created",
        "ontology_draft_actions",
        ["tenant_id", "entity_type_id", "created_at"],
    )


def downgrade() -> None:
    if _table_exists("ontology_draft_actions"):
        op.drop_table("ontology_draft_actions")
