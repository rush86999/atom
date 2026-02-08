"""Offline sync enhancements for mobile devices

Add conflict resolution fields to SyncState model and create indexes for better performance.

Revision ID: 20260205_offline_sync_enhancements
Revises: 20260205_mobile_biometric_support
Create Date: 2026-02-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260205_offline_sync_enhancements'
down_revision = '20260205_mobile_biometric'
branch_labels = None
depends_on = None


def upgrade():
    """Add conflict resolution fields to sync_states table."""

    # Add conflict_resolution column
    op.add_column(
        'sync_states',
        sa.Column('conflict_resolution', sa.String(), nullable=True, server_default='last_write_wins')
    )

    # Add last_conflict_at column
    op.add_column(
        'sync_states',
        sa.Column('last_conflict_at', sa.DateTime(timezone=True), nullable=True)
    )

    # Create composite index on priority and status for offline_actions
    # This helps with prioritizing which actions to sync first
    op.create_index(
        'ix_offline_actions_priority_status',
        'offline_actions',
        ['priority', 'status'],
        unique=False
    )

    # Create index on user_id for faster user-specific queries
    op.create_index(
        'ix_offline_actions_user_pending',
        'offline_actions',
        ['user_id', 'status'],
        unique=False
    )

    # Create index on created_at for time-based queries
    op.create_index(
        'ix_offline_actions_created',
        'offline_actions',
        ['created_at'],
        unique=False
    )


def downgrade():
    """Remove conflict resolution fields from sync_states table."""

    # Drop indexes
    op.drop_index('ix_offline_actions_created', table_name='offline_actions')
    op.drop_index('ix_offline_actions_user_pending', table_name='offline_actions')
    op.drop_index('ix_offline_actions_priority_status', table_name='offline_actions')

    # Drop columns
    op.drop_column('sync_states', 'last_conflict_at')
    op.drop_column('sync_states', 'conflict_resolution')
