"""add_reply_to_id_to_agent_post

Revision ID: 6ab570bc3e92
Revises: d8231b2c6f63
Create Date: 2026-02-16 17:34:00.557280

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection


# revision identifiers, used by Alembic.
revision: str = '6ab570bc3e92'
down_revision: Union[str, Sequence[str], None] = 'd8231b2c6f63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add reply_to_id column to agent_posts table
    # Note: Foreign key constraint skipped for SQLite (not supported in ALTER)
    # The relationship is defined in the SQLAlchemy model instead
    op.add_column(
        'agent_posts',
        sa.Column('reply_to_id', sa.String(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop reply_to_id column
    op.drop_column('agent_posts', 'reply_to_id')
