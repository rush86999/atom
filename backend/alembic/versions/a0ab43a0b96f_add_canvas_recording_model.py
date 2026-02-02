"""add canvas recording model

Revision ID: a0ab43a0b96f
Revises: 60cad7faa40a
Create Date: 2026-02-02 11:54:11.518438

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a0ab43a0b96f'
down_revision: Union[str, Sequence[str], None] = '60cad7faa40a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create canvas_recordings table
    op.create_table(
        'canvas_recordings',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('recording_id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('canvas_id', sa.String(), nullable=True),
        sa.Column('session_id', sa.String(), nullable=True),
        sa.Column('reason', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=True, server_default='recording'),
        sa.Column('tags', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('events', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('stopped_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('event_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('recording_metadata', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('flagged_for_review', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('flag_reason', sa.Text(), nullable=True),
        sa.Column('flagged_by', sa.String(), nullable=True),
        sa.Column('flagged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('storage_url', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_registry.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_canvas_recordings_recording_id', 'canvas_recordings', ['recording_id'], unique=True)
    op.create_index('ix_canvas_recordings_user_id', 'canvas_recordings', ['user_id'], unique=False)
    op.create_index('ix_canvas_recordings_session_id', 'canvas_recordings', ['session_id'], unique=False)
    op.create_index('ix_canvas_recordings_agent_user', 'canvas_recordings', ['agent_id', 'user_id'], unique=False)
    op.create_index('ix_canvas_recordings_session_status', 'canvas_recordings', ['session_id', 'status'], unique=False)
    op.create_index('ix_canvas_recordings_started_at', 'canvas_recordings', ['started_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('ix_canvas_recordings_started_at', table_name='canvas_recordings')
    op.drop_index('ix_canvas_recordings_session_status', table_name='canvas_recordings')
    op.drop_index('ix_canvas_recordings_agent_user', table_name='canvas_recordings')
    op.drop_index('ix_canvas_recordings_session_id', table_name='canvas_recordings')
    op.drop_index('ix_canvas_recordings_user_id', table_name='canvas_recordings')
    op.drop_index('ix_canvas_recordings_recording_id', table_name='canvas_recordings')

    # Drop table
    op.drop_table('canvas_recordings')
