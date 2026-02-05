"""add recording review model for governance and learning

Revision ID: b677f9cd6ac5
Revises: a0ab43a0b96f
Create Date: 2026-02-02 12:12:03.702736

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b677f9cd6ac5'
down_revision: Union[str, Sequence[str], None] = 'a0ab43a0b96f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create canvas_recording_reviews table
    op.create_table(
        'canvas_recording_reviews',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('recording_id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('review_status', sa.String(), nullable=False),
        sa.Column('overall_rating', sa.Integer(), nullable=True),
        sa.Column('performance_rating', sa.Integer(), nullable=True),
        sa.Column('safety_rating', sa.Integer(), nullable=True),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('identified_issues', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('positive_patterns', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('lessons_learned', sa.Text(), nullable=True),
        sa.Column('confidence_delta', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('promoted', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('demoted', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('governance_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_by', sa.String(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('auto_reviewed', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('auto_review_confidence', sa.Float(), nullable=True),
        sa.Column('used_for_training', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('training_value', sa.String(), nullable=True),
        sa.Column('world_model_updated', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_registry.id'], ),
        sa.ForeignKeyConstraint(['recording_id'], ['canvas_recordings.recording_id'], ),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_recording_reviews_recording', 'canvas_recording_reviews', ['recording_id'], unique=False)
    op.create_index('ix_recording_reviews_agent', 'canvas_recording_reviews', ['agent_id'], unique=False)
    op.create_index('ix_recording_reviews_status', 'canvas_recording_reviews', ['review_status'], unique=False)
    op.create_index('ix_recording_reviews_reviewed', 'canvas_recording_reviews', ['reviewed_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('ix_recording_reviews_reviewed', table_name='canvas_recording_reviews')
    op.drop_index('ix_recording_reviews_status', table_name='canvas_recording_reviews')
    op.drop_index('ix_recording_reviews_agent', table_name='canvas_recording_reviews')
    op.drop_index('ix_recording_reviews_recording', table_name='canvas_recording_reviews')

    # Drop table
    op.drop_table('canvas_recording_reviews')
