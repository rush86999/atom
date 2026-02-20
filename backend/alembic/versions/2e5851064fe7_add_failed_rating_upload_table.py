"""add failed rating upload table

Revision ID: 2e5851064fe7
Revises: 235237d9a71e
Create Date: 2026-02-19 19:09:00.450689

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2e5851064fe7'
down_revision: Union[str, Sequence[str], None] = '235237d9a71e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'failed_rating_uploads',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('rating_id', sa.String(36), sa.ForeignKey('skill_ratings.id'), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=False),
        sa.Column('failed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_retry_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('idx_failed_rating_uploads_rating_id', 'failed_rating_uploads', ['rating_id'])
    op.create_index('idx_failed_rating_uploads_failed_at', 'failed_rating_uploads', ['failed_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_failed_rating_uploads_failed_at', 'failed_rating_uploads')
    op.drop_index('idx_failed_rating_uploads_rating_id', 'failed_rating_uploads')
    op.drop_table('failed_rating_uploads')
