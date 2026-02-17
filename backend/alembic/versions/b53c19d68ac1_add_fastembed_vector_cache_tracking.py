"""add fastembed vector cache tracking

Revision ID: b53c19d68ac1
Revises: 6ab570bc3e92
Create Date: 2026-02-17 11:51:57.935713

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b53c19d68ac1'
down_revision: Union[str, Sequence[str], None] = '6ab570bc3e92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add FastEmbed cache tracking columns to episodes table
    op.add_column(
        'episodes',
        sa.Column('fastembed_cached', sa.Boolean(), nullable=False, server_default='false')
    )
    op.add_column(
        'episodes',
        sa.Column('fastembed_cached_at', sa.DateTime(timezone=True), nullable=True)
    )

    # Add ST embedding cache tracking columns to episodes table (for completeness)
    op.add_column(
        'episodes',
        sa.Column('embedding_cached', sa.Boolean(), nullable=False, server_default='false')
    )
    op.add_column(
        'episodes',
        sa.Column('embedding_cached_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove columns in reverse order
    op.drop_column('episodes', 'embedding_cached_at')
    op.drop_column('episodes', 'embedding_cached')
    op.drop_column('episodes', 'fastembed_cached_at')
    op.drop_column('episodes', 'fastembed_cached')
