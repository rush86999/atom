"""add conflict log model

Revision ID: 29b7aa4918a3
Revises: 2e5851064fe7
Create Date: 2026-02-19 19:21:57.750394

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '29b7aa4918a3'
down_revision: Union[str, Sequence[str], None] = '2e5851064fe7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create conflict_log table
    op.create_table(
        'conflict_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('skill_id', sa.String(length=255), nullable=False),
        sa.Column('conflict_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('local_data', sa.JSON(), nullable=False),
        sa.Column('remote_data', sa.JSON(), nullable=False),
        sa.Column('resolution_strategy', sa.String(length=50), nullable=True),
        sa.Column('resolved_data', sa.JSON(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('idx_conflict_log_skill_id', 'conflict_log', ['skill_id'])
    op.create_index('idx_conflict_log_type', 'conflict_log', ['conflict_type'])
    op.create_index('idx_conflict_log_severity', 'conflict_log', ['severity'])
    op.create_index('idx_conflict_log_resolved_at', 'conflict_log', ['resolved_at'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('idx_conflict_log_resolved_at', table_name='conflict_log')
    op.drop_index('idx_conflict_log_severity', table_name='conflict_log')
    op.drop_index('idx_conflict_log_type', table_name='conflict_log')
    op.drop_index('idx_conflict_log_skill_id', table_name='conflict_log')

    # Drop table
    op.drop_table('conflict_log')
