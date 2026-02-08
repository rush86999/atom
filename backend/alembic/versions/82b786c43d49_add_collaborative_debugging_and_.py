"""add_collaborative_debugging_and_performance_profiling

Revision ID: 82b786c43d49
Revises: a25c563b8198
Create Date: 2026-02-01 15:30:41.625524

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '82b786c43d49'
down_revision: Union[str, Sequence[str], None] = 'a25c563b8198'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add collaborative debugging and performance profiling columns
    op.add_column('workflow_debug_sessions',
        sa.Column('collaborators', sa.JSON(), nullable=True)
    )
    op.add_column('workflow_debug_sessions',
        sa.Column('performance_metrics', sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove collaborative debugging and performance profiling columns
    op.drop_column('workflow_debug_sessions', 'performance_metrics')
    op.drop_column('workflow_debug_sessions', 'collaborators')
