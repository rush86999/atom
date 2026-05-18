"""fix_acu_usage_logs_foreign_key_to_tenants

Revision ID: 20260518_fix_acu_fk
Revises: 20260507_fix_acu_uuid
Create Date: 2026-05-18 09:45:00.000000

Fixes foreign key reference in acu_usage_logs table.
Changes tenant_id FK from workspaces.id to tenants.id to match model definition.

Issue: #7489445485 - Error tracking ACU usage due to UndefinedColumn

The model (core/models.py:10942) defines:
    tenant_id = Column(UUID, ForeignKey("tenants.id", ondelete="CASCADE"))

But migration 20260507_fix_acu_uuid incorrectly referenced workspaces.id.

"""
from __future__ import annotations
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260518_fix_acu_fk"
down_revision = "20260507_fix_acu_uuid"
branch_labels = None
depends_on = None


def upgrade():
    """
    Fix acu_usage_logs foreign key to reference tenants instead of workspaces.

    Strategy:
    1. Drop the incorrect foreign key constraint to workspaces
    2. Create the correct foreign key constraint to tenants
    """
    # Step 1: Drop the incorrect foreign key constraint
    with op.batch_alter_table('acu_usage_logs') as batch_op:
        batch_op.drop_constraint('acu_usage_logs_tenant_id_fkey', type_='foreignkey')

    # Step 2: Create the correct foreign key constraint to tenants table
    op.create_foreign_key(
        'acu_usage_logs_tenant_id_fkey',
        'acu_usage_logs', 'tenants',
        ['tenant_id'], ['id'],
        ondelete='CASCADE'
    )


def downgrade():
    """
    Revert back to workspaces reference (incorrect but this is the inverse).
    """
    # Drop the correct foreign key constraint
    with op.batch_alter_table('acu_usage_logs') as batch_op:
        batch_op.drop_constraint('acu_usage_logs_tenant_id_fkey', type_='foreignkey')

    # Recreate the incorrect foreign key constraint to workspaces
    op.create_foreign_key(
        'acu_usage_logs_tenant_id_fkey',
        'acu_usage_logs', 'workspaces',
        ['tenant_id'], ['id'],
        ondelete='CASCADE'
    )
