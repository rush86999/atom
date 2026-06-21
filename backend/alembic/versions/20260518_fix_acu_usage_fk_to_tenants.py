"""fix_acu_usage_logs_foreign_key_to_tenants

Revision ID: 20260518_fix_acu_fk
Revises: 20260505_add_discovered_entities
Create Date: 2026-05-18 09:45:00.000000

Fixes foreign key reference in acu_usage_logs table.

NOTE: The original parent revision `20260507_fix_acu_uuid` was never committed
to the repository, creating a broken reference that blocked ALL alembic
operations (`alembic current`, `alembic upgrade head`, etc.) with:
    RevisionError: Can't locate revision identified by '20260507_fix_acu_uuid'

Rewired to `atom_merge_20260510` (the mergepoint that unifies the packages and
gea branches) and added an existence guard — the `acu_usage_logs` table does not
exist in any known database state (the actual model is `acu_consumption`), so
this migration is effectively a no-op. It exists to keep the migration chain
intact for fresh clones and to provide a single linear head.

Issue: #7489445485 - Error tracking ACU usage due to UndefinedColumn
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260518_fix_acu_fk"
down_revision = "atom_merge_20260510"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    """Check if a table exists in the current database."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade():
    """Fix acu_usage_logs foreign key to reference tenants instead of workspaces.

    Guarded: if acu_usage_logs does not exist (which is the case in all known
    database states — the actual model is acu_consumption), this is a no-op.
    """
    if not _table_exists("acu_usage_logs"):
        print("    [skip] acu_usage_logs table not found — migration is a no-op")
        return

    # Step 1: Drop the incorrect foreign key constraint
    with op.batch_alter_table("acu_usage_logs") as batch_op:
        batch_op.drop_constraint(
            "acu_usage_logs_tenant_id_fkey", type_="foreignkey"
        )

    # Step 2: Create the correct foreign key constraint to tenants table
    op.create_foreign_key(
        "acu_usage_logs_tenant_id_fkey",
        "acu_usage_logs",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade():
    """Revert back to workspaces reference (incorrect but this is the inverse)."""
    if not _table_exists("acu_usage_logs"):
        print("    [skip] acu_usage_logs table not found — migration is a no-op")
        return

    with op.batch_alter_table("acu_usage_logs") as batch_op:
        batch_op.drop_constraint(
            "acu_usage_logs_tenant_id_fkey", type_="foreignkey"
        )

    op.create_foreign_key(
        "acu_usage_logs_tenant_id_fkey",
        "acu_usage_logs",
        "workspaces",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
