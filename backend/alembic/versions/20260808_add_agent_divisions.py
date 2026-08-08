"""add agent_divisions table + AgentRegistry division columns

Revision ID: 20260808_add_agent_divisions
Revises: 20260808_add_lateral_messaging
Create Date: 2026-08-08 00:00:00.000000

P1c — division hierarchy with REAL depth enforcement (plan v4, W4):

- ``agent_divisions`` — a domain-scoped team of specialist agents. The
  division lead (``lead_agent_id``) is a REAL ``AgentRegistry`` row
  (GenericAgent config + division prompt + allowlist), never a fabricated
  placeholder ID, so the P9 sandbox gate applies to leads like any agent.
- ``agent_registry.division_id`` — which division an agent belongs to.
- ``agent_registry.parent_agent_id`` — reporting/recursion lineage; the
  per-parent depth walk in ``agent_governance_service`` bounds nesting via
  ``DelegationChain.max_depth``.
- ``agent_registry.specialty`` — domain specialty (e.g. "finance").

Tables/columns are created idempotently so this is safe to run on databases
that received the schema via ``create_all`` as well as via the migration chain.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260808_add_agent_divisions"
down_revision: Union[str, Sequence[str], None] = "20260808_add_lateral_messaging"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return column_name in [c["name"] for c in inspector.get_columns(table_name)]


def upgrade() -> None:
    # --- agent_divisions ---
    if not _table_exists("agent_divisions"):
        op.create_table(
            "agent_divisions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(),
                      sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
            sa.Column("workspace_id", sa.String(),
                      sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("lead_agent_id", sa.String(),
                      sa.ForeignKey("agent_registry.id", ondelete="SET NULL"), nullable=True),
            sa.Column("parent_id", sa.String(),
                      sa.ForeignKey("agent_divisions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("domain", sa.String(), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_agent_divisions_tenant_id", "agent_divisions", ["tenant_id"])
        op.create_index("ix_agent_divisions_workspace_id", "agent_divisions", ["workspace_id"])

    # --- agent_registry.division_id / parent_agent_id / specialty ---
    if _table_exists("agent_registry"):
        if not _column_exists("agent_registry", "division_id"):
            with op.batch_alter_table("agent_registry") as batch_op:
                batch_op.add_column(sa.Column(
                    "division_id", sa.String(),
                    sa.ForeignKey("agent_divisions.id", ondelete="SET NULL"), nullable=True))
            op.create_index("ix_agent_registry_division_id", "agent_registry", ["division_id"])

        if not _column_exists("agent_registry", "parent_agent_id"):
            with op.batch_alter_table("agent_registry") as batch_op:
                batch_op.add_column(sa.Column(
                    "parent_agent_id", sa.String(),
                    sa.ForeignKey("agent_registry.id", ondelete="SET NULL"), nullable=True))
            op.create_index("ix_agent_registry_parent_agent_id", "agent_registry", ["parent_agent_id"])

        if not _column_exists("agent_registry", "specialty"):
            with op.batch_alter_table("agent_registry") as batch_op:
                batch_op.add_column(sa.Column("specialty", sa.String(length=128), nullable=True))


def downgrade() -> None:
    if _table_exists("agent_registry"):
        for col in ("specialty", "parent_agent_id", "division_id"):
            if _column_exists("agent_registry", col):
                with op.batch_alter_table("agent_registry") as batch_op:
                    batch_op.drop_column(col)

    if _table_exists("agent_divisions"):
        op.drop_table("agent_divisions")
