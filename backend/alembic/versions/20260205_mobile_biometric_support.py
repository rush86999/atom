"""Mobile biometric support

Add biometric authentication fields to MobileDevice model.

Revision ID: 20260205_mobile_biometric
Revises: 20260204_canvas_feedback_episode_integration
Create Date: 2026-02-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260205_mobile_biometric'
down_revision = 'canvas_feedback_ep_integration'
branch_labels = None
depends_on = None


def upgrade():
    """Add biometric fields to mobile_devices table."""

    # Add biometric_public_key column
    op.add_column(
        'mobile_devices',
        sa.Column('biometric_public_key', sa.Text(), nullable=True)
    )

    # Add last_biometric_auth column
    op.add_column(
        'mobile_devices',
        sa.Column('last_biometric_auth', sa.DateTime(timezone=True), nullable=True)
    )

    # Add biometric_enabled column
    op.add_column(
        'mobile_devices',
        sa.Column('biometric_enabled', sa.Boolean(), nullable=True, server_default='false')
    )

    # Create composite index on user_id and status for faster lookups
    op.create_index(
        'ix_mobile_devices_user_status',
        'mobile_devices',
        ['user_id', 'status'],
        unique=False
    )

    # Create index on biometric_enabled for filtering
    op.create_index(
        'ix_mobile_devices_biometric_enabled',
        'mobile_devices',
        ['biometric_enabled'],
        unique=False
    )


def downgrade():
    """Remove biometric fields from mobile_devices table."""

    # Drop indexes
    op.drop_index('ix_mobile_devices_biometric_enabled', table_name='mobile_devices')
    op.drop_index('ix_mobile_devices_user_status', table_name='mobile_devices')

    # Drop columns
    op.drop_column('mobile_devices', 'biometric_enabled')
    op.drop_column('mobile_devices', 'last_biometric_auth')
    op.drop_column('mobile_devices', 'biometric_public_key')
