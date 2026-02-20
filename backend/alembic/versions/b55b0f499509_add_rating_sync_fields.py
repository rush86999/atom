"""add rating sync fields

Revision ID: b55b0f499509
Revises: d99e23d1bd3f
Create Date: 2026-02-19 19:00:38.590758

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b55b0f499509'
down_revision: Union[str, Sequence[str], None] = 'd99e23d1bd3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create skill_ratings table if it doesn't exist (Phase 60 Plan 01)
    if not sa.inspect(op.get_bind()).has_table('skill_ratings'):
        op.create_table(
            'skill_ratings',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('skill_id', sa.String(255), nullable=False),
            sa.Column('user_id', sa.String(255), nullable=False),
            sa.Column('rating', sa.Integer(), nullable=False),
            sa.Column('comment', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('synced_to_saas', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('remote_rating_id', sa.String(255), nullable=True)
        )
        op.create_index('idx_skill_rating_skill_user', 'skill_ratings', ['skill_id', 'user_id'], unique=True)
        op.create_index('idx_skill_rating_skill_id', 'skill_ratings', ['skill_id'])
        op.create_index('idx_skill_rating_user_id', 'skill_ratings', ['user_id'])
        op.create_index('idx_skill_rating_synced_to_saas', 'skill_ratings', ['synced_to_saas'])
    else:
        # Add rating sync tracking columns to existing table
        op.add_column('skill_ratings', sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True))
        op.add_column('skill_ratings', sa.Column('synced_to_saas', sa.Boolean(), nullable=False, server_default='false'))
        op.add_column('skill_ratings', sa.Column('remote_rating_id', sa.String(255), nullable=True))

        # Create index for efficient pending ratings query
        op.create_index('idx_skill_rating_synced_to_saas', 'skill_ratings', ['synced_to_saas'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the entire skill_ratings table (complete rollback)
    op.drop_index('idx_skill_rating_synced_to_saas', 'skill_ratings')
    op.drop_index('idx_skill_rating_user_id', 'skill_ratings')
    op.drop_index('idx_skill_rating_skill_id', 'skill_ratings')
    op.drop_index('idx_skill_rating_skill_user', 'skill_ratings')
    op.drop_table('skill_ratings')
