"""add social post job id

Revision ID: 20260205_add_job_id
Revises:
Create Date: 2026-02-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260205_add_job_id'
down_revision = None  # Set to the latest migration ID
branch_labels = None
depends_on = None


def upgrade():
    """Add job_id column and update status enum for SocialPostHistory"""
    # Add job_id column
    op.add_column(
        'social_post_history',
        sa.Column('job_id', sa.String(), nullable=True, index=True)
    )

    # Update status column to include new statuses
    # Note: SQLite doesn't support ALTER TYPE, so we use a workaround
    # For PostgreSQL, you could use: ALTER TABLE social_post_history ALTER COLUMN status TYPE VARCHAR(20)

    # Create index for job_id
    op.create_index(
        'ix_social_post_history_job_id',
        'social_post_history',
        ['job_id']
    )


def downgrade():
    """Remove job_id column from SocialPostHistory"""
    # Remove index
    op.drop_index(
        'ix_social_post_history_job_id',
        table_name='social_post_history'
    )

    # Remove column
    op.drop_column(
        'social_post_history',
        'job_id'
    )
