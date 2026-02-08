"""add session_id to canvas_audit for session isolation

Revision ID: 3552e6844c1d
Revises: g1h2i3j4k5l6
Create Date: 2026-02-01 09:01:51.814422

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '3552e6844c1d'
down_revision: Union[str, Sequence[str], None] = 'g1h2i3j4k5l6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add session_id column to canvas_audit for session isolation
    op.add_column(
        'canvas_audit',
        sa.Column('session_id', sa.String(), nullable=True, index=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove session_id column from canvas_audit
    op.drop_column('canvas_audit', 'session_id')
