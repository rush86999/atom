"""auditable local invoice -> provider invoice binding

Adds the current binding row and its append-only revision receipts.

The uniqueness rules are part of the safety contract:

* ``(workspace_id, invoice_id, provider)`` keeps one current row per scoped
  local invoice/provider.
* ``(workspace_id, provider, provider_account_id, provider_mode,
  external_invoice_id)`` prevents two local invoices from claiming the same
  external provider invoice.

No provider credentials or application customer content are stored here.

Revision ID: 20261119_invoice_provider_binding
Revises: 20261118_local_model_audio_capability
Create Date: 2026-11-19 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261119_invoice_provider_binding"
down_revision: Union[str, Sequence[str], None] = "20261118_local_model_audio_capability"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BINDINGS = "accounting_invoice_provider_bindings"
_REVISIONS = "accounting_invoice_provider_binding_revisions"


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists(_BINDINGS):
        op.create_table(
            _BINDINGS,
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("invoice_id", sa.String(), nullable=False),
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("provider_account_id", sa.String(), nullable=False),
            sa.Column("provider_mode", sa.String(), nullable=False),
            sa.Column("external_invoice_id", sa.String(), nullable=False),
            sa.Column("connection_id", sa.String(), nullable=False),
            sa.Column(
                "revision",
                sa.Integer(),
                nullable=False,
                server_default="1",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["workspace_id"],
                ["workspaces.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["invoice_id"],
                ["accounting_invoices.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["connection_id"],
                ["user_connections.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "workspace_id",
                "invoice_id",
                "provider",
                name="_accounting_invoice_provider_binding_uc",
            ),
            sa.UniqueConstraint(
                "workspace_id",
                "provider",
                "provider_account_id",
                "provider_mode",
                "external_invoice_id",
                name="_accounting_provider_invoice_binding_uc",
            ),
        )
        op.create_index(
            "ix_accounting_invoice_provider_bindings_workspace_id",
            _BINDINGS,
            ["workspace_id"],
        )
        op.create_index(
            "ix_accounting_invoice_provider_bindings_invoice_id",
            _BINDINGS,
            ["invoice_id"],
        )
        op.create_index(
            "ix_accounting_invoice_provider_bindings_provider",
            _BINDINGS,
            ["provider"],
        )
        op.create_index(
            "ix_accounting_invoice_provider_bindings_connection_id",
            _BINDINGS,
            ["connection_id"],
        )

    if not _table_exists(_REVISIONS):
        op.create_table(
            _REVISIONS,
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("binding_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("invoice_id", sa.String(), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("actor_id", sa.String(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("prior_provider", sa.String(), nullable=True),
            sa.Column("prior_provider_account_id", sa.String(), nullable=True),
            sa.Column("prior_provider_mode", sa.String(), nullable=True),
            sa.Column("prior_external_invoice_id", sa.String(), nullable=True),
            sa.Column("prior_connection_id", sa.String(), nullable=True),
            sa.Column("new_provider", sa.String(), nullable=False),
            sa.Column("new_provider_account_id", sa.String(), nullable=False),
            sa.Column("new_provider_mode", sa.String(), nullable=False),
            sa.Column("new_external_invoice_id", sa.String(), nullable=False),
            sa.Column("new_connection_id", sa.String(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["binding_id"],
                [f"{_BINDINGS}.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["workspace_id"],
                ["workspaces.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["invoice_id"],
                ["accounting_invoices.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["actor_id"],
                ["users.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "binding_id",
                "revision",
                name="_accounting_invoice_provider_binding_revision_uc",
            ),
        )
        op.create_index(
            "ix_accounting_invoice_provider_binding_revisions_binding_id",
            _REVISIONS,
            ["binding_id"],
        )
        op.create_index(
            "ix_accounting_invoice_provider_binding_revisions_workspace_id",
            _REVISIONS,
            ["workspace_id"],
        )
        op.create_index(
            "ix_accounting_invoice_provider_binding_revisions_invoice_id",
            _REVISIONS,
            ["invoice_id"],
        )


def downgrade() -> None:
    if _table_exists(_REVISIONS):
        op.drop_table(_REVISIONS)
    if _table_exists(_BINDINGS):
        op.drop_table(_BINDINGS)
