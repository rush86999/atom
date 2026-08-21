"""add ingested_documents.role column

Revision ID: 20260821_ingested_docs_role
Revises: 20260818_org_ingestion_sharing
Create Date: 2026-08-21 00:00:00.000000

Round 80 (integration-journey audit) — data-ingestion relevance to AI-employee
memory. The AI employee is an AgentRegistry row (category = role, specialty =
responsibility). Ingested org data was stored with NO role/agent attribution and
recalled the same for every employee. This adds a nullable ``role`` column to
``ingested_documents`` carrying the AgentRegistry.category (lowercased) that the
document was ingested FOR; NULL = general knowledge. Recall-side filtering lives
in core/agent_world_model.py (WorldModelService._recall_general_knowledge).

Guarded for SQLite (dev DB is hybrid — schema via ``create_all``, alembic
bookkeeping lags). Mirrors the guard pattern in ``20260805_add_canvas_logic_and_custom_component_columns.py``.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260821_ingested_docs_role"
down_revision: Union[str, Sequence[str], None] = "20260821_graph_community_snapshots"
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
    if not _table_exists("ingested_documents"):
        return
    if _column_exists("ingested_documents", "role"):
        return
    with op.batch_alter_table("ingested_documents") as batch:
        batch.add_column(sa.Column("role", sa.String(length=64), nullable=True))
    print("    [ok] added ingested_documents.role")


def downgrade() -> None:
    if not _table_exists("ingested_documents"):
        return
    if not _column_exists("ingested_documents", "role"):
        return
    with op.batch_alter_table("ingested_documents") as batch:
        batch.drop_column("role")
