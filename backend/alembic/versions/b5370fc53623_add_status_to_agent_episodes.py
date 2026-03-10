"""add status field to agent_episodes

Revision ID: b5370fc53623
Revises:
Create Date: 2026-03-10 11:25:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b5370fc53623'
down_revision = 'add_audit_immutable_trigger'
branch_labels = None
depends_on = None


def upgrade():
    """Add status column to agent_episodes table"""
    # Add status column with default value
    op.add_column('agent_episodes',
                  sa.Column('status', sa.String(20), nullable=False, server_default='active'))
    # Create index on status
    op.create_index('ix_agent_episodes_status', 'agent_episodes', ['status'])


def downgrade():
    """Remove status column from agent_episodes table"""
    op.drop_index('ix_agent_episodes_status', 'agent_episodes')
    op.drop_column('agent_episodes', 'status')
