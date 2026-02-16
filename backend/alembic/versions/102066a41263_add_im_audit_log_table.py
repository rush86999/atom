"""add_im_audit_log_table

Revision ID: 102066a41263
Revises: 20260208_two_way_learning
Create Date: 2026-02-15 20:48:11.367654

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '102066a41263'
down_revision: Union[str, Sequence[str], None] = '20260208_two_way_learning'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create im_audit_logs table
    op.create_table(
        'im_audit_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('platform', sa.String(), nullable=False),
        sa.Column('sender_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('payload_hash', sa.String(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('rate_limited', sa.Boolean(), nullable=True),
        sa.Column('signature_valid', sa.Boolean(), nullable=True),
        sa.Column('governance_check_passed', sa.Boolean(), nullable=True),
        sa.Column('agent_maturity_level', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for efficient querying
    op.create_index('ix_im_audit_logs_platform', 'im_audit_logs', ['platform'])
    op.create_index('ix_im_audit_logs_sender_id', 'im_audit_logs', ['sender_id'])
    op.create_index('ix_im_audit_logs_timestamp', 'im_audit_logs', ['timestamp'])
    op.create_index('ix_im_audit_logs_platform_sender', 'im_audit_logs', ['platform', 'sender_id', 'timestamp'])
    op.create_index('ix_im_audit_logs_platform_time', 'im_audit_logs', ['platform', 'timestamp'])
    op.create_index('ix_im_audit_logs_sender_time', 'im_audit_logs', ['sender_id', 'timestamp'])
    op.create_index('ix_im_audit_logs_rate_limited', 'im_audit_logs', ['rate_limited', 'timestamp'])
    op.create_index('ix_im_audit_logs_success', 'im_audit_logs', ['success', 'timestamp'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('ix_im_audit_logs_success', 'im_audit_logs')
    op.drop_index('ix_im_audit_logs_rate_limited', 'im_audit_logs')
    op.drop_index('ix_im_audit_logs_sender_time', 'im_audit_logs')
    op.drop_index('ix_im_audit_logs_platform_time', 'im_audit_logs')
    op.drop_index('ix_im_audit_logs_platform_sender', 'im_audit_logs')
    op.drop_index('ix_im_audit_logs_timestamp', 'im_audit_logs')
    op.drop_index('ix_im_audit_logs_sender_id', 'im_audit_logs')
    op.drop_index('ix_im_audit_logs_platform', 'im_audit_logs')

    # Drop table
    op.drop_table('im_audit_logs')
