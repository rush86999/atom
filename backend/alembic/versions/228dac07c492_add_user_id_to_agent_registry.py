"""Add user_id and configuration columns to agent_registry

Revision ID: 228dac07c492
Revises: 8b6243295b71
Create Date: 2026-02-01 10:20:37.502843

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = '228dac07c492'
down_revision: Union[str, Sequence[str], None] = '8b6243295b71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add user_id column to agent_registry
    op.add_column(
        'agent_registry',
        sa.Column('user_id', sa.String(), nullable=True, index=True)
    )

    # Add configuration column (JSON)
    op.add_column(
        'agent_registry',
        sa.Column('configuration', sa.JSON(), nullable=True, server_default='{}')
    )

    # Add schedule_config column (JSON)
    op.add_column(
        'agent_registry',
        sa.Column('schedule_config', sa.JSON(), nullable=True, server_default='{}')
    )

    # Create foreign key to users table
    try:
        op.create_foreign_key(
            'fk_agent_registry_user_id',
            'agent_registry', 'users',
            ['user_id'], ['id']
        )
    except Exception:
        # users table might not exist in all environments
        pass


def downgrade() -> None:
    """Downgrade schema."""
    # Drop foreign key
    try:
        op.drop_constraint('fk_agent_registry_user_id', 'agent_registry', type_='foreignkey')
    except Exception:
        pass

    # Drop user_id index and column
    try:
        op.drop_index('ix_agent_registry_user_id', table_name='agent_registry')
    except Exception:
        pass
    op.drop_column('agent_registry', 'user_id')

    # Drop configuration and schedule_config columns
    op.drop_column('agent_registry', 'schedule_config')
    op.drop_column('agent_registry', 'configuration')
