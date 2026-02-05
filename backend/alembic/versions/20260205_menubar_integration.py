"""Menu bar integration for macOS companion app

Add app_type and last_command_at fields to DeviceNode model for menu bar support.

Revision ID: 20260205_menubar_integration
Revises: 20260205_offline_sync_enhancements
Create Date: 2026-02-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260205_menubar_integration'
down_revision = '20260205_offline_sync_enhancements'
branch_labels = None
depends_on = None


def upgrade():
    """Add menu bar specific fields to device_nodes table."""

    # Add app_type column to distinguish between desktop, mobile, menubar apps
    op.add_column(
        'device_nodes',
        sa.Column('app_type', sa.String(), nullable=True, server_default='desktop')
    )

    # Add last_command_at to track when menu bar last executed a command
    op.add_column(
        'device_nodes',
        sa.Column('last_command_at', sa.DateTime(timezone=True), nullable=True)
    )

    # Create index on app_type for filtering by app type
    op.create_index(
        'ix_device_nodes_app_type',
        'device_nodes',
        ['app_type'],
        unique=False
    )

    # Create composite index on status and app_type for active menu bar devices
    op.create_index(
        'ix_device_nodes_status_app_type',
        'device_nodes',
        ['status', 'app_type'],
        unique=False
    )


def downgrade():
    """Remove menu bar specific fields from device_nodes table."""

    # Drop indexes
    op.drop_index('ix_device_nodes_status_app_type', table_name='device_nodes')
    op.drop_index('ix_device_nodes_app_type', table_name='device_nodes')

    # Drop columns
    op.drop_column('device_nodes', 'last_command_at')
    op.drop_column('device_nodes', 'app_type')
