"""Enhance AgentFeedback with ratings and execution linking

Revision ID: 8b6243295b71
Revises: 158137b9c8b6
Create Date: 2026-02-01 09:51:28.820120

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '8b6243295b71'
down_revision: Union[str, Sequence[str], None] = '158137b9c8b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new columns to agent_feedback table
    op.add_column('agent_feedback', sa.Column('thumbs_up_down', sa.Boolean(), nullable=True))
    op.add_column('agent_feedback', sa.Column('agent_execution_id', sa.String(), nullable=True))
    op.add_column('agent_feedback', sa.Column('rating', sa.Integer(), nullable=True))
    op.add_column('agent_feedback', sa.Column('feedback_type', sa.String(), nullable=True))

    # Create index for agent_execution_id
    op.create_index(op.f('ix_agent_feedback_agent_execution_id'), 'agent_feedback', ['agent_execution_id'], unique=False)
    op.create_index(op.f('ix_agent_feedback_rating'), 'agent_feedback', ['rating'], unique=False)
    op.create_index(op.f('ix_agent_feedback_feedback_type'), 'agent_feedback', ['feedback_type'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index(op.f('ix_agent_feedback_feedback_type'), table_name='agent_feedback')
    op.drop_index(op.f('ix_agent_feedback_rating'), table_name='agent_feedback')
    op.drop_index(op.f('ix_agent_feedback_agent_execution_id'), table_name='agent_feedback')

    # Drop columns
    op.drop_column('agent_feedback', 'feedback_type')
    op.drop_column('agent_feedback', 'rating')
    op.drop_column('agent_feedback', 'agent_execution_id')
    op.drop_column('agent_feedback', 'thumbs_up_down')
