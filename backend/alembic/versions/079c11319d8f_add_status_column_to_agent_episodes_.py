"""add status column to agent_episodes table

Revision ID: 079c11319d8f
Revises: 008dd9210221
Create Date: 2026-03-15 11:24:34.432444

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '079c11319d8f'
down_revision: Union[str, Sequence[str], None] = '008dd9210221'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add status column to agent_episodes table
    op.add_column(
        'agent_episodes',
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active')
    )
    # Create index on status column
    op.create_index('ix_agent_episodes_status', 'agent_episodes', ['status'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop index and status column
    op.drop_index('ix_agent_episodes_status', table_name='agent_episodes')
    op.drop_column('agent_episodes', 'status')
