"""add_auto_generated_to_agent_post

Revision ID: d8231b2c6f63
Revises: 20260216_community_skills
Create Date: 2026-02-16 17:14:47.936420

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8231b2c6f63'
down_revision: Union[str, Sequence[str], None] = '20260216_community_skills'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add auto_generated column to agent_posts table
    op.add_column(
        'agent_posts',
        sa.Column('auto_generated', sa.Boolean(), nullable=True, default=False)
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove auto_generated column from agent_posts table
    op.drop_column('agent_posts', 'auto_generated')
