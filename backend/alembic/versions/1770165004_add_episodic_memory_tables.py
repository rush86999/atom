"""add episodic memory tables

Revision ID: 1770165004
Revises: fa4f5aab967b
Create Date: 2026-02-03

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = '1770165004'
down_revision: Union[str, Sequence[str], None] = 'fa4f5aab967b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    
    # Create episodes table
    op.create_table(
        'episodes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('agent_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=True),
        sa.Column('execution_ids', sa.JSON(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), server_default='active', nullable=False),
        sa.Column('topics', sa.JSON(), nullable=False),
        sa.Column('entities', sa.JSON(), nullable=False),
        sa.Column('importance_score', sa.Float(), server_default='0.5', nullable=False),
        sa.Column('maturity_at_time', sa.String(), nullable=False),
        sa.Column('human_intervention_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('human_edits', sa.JSON(), nullable=False),
        sa.Column('constitutional_score', sa.Float(), nullable=True),
        sa.Column('world_model_state', sa.String(), nullable=True),
        sa.Column('decay_score', sa.Float(), server_default='1.0', nullable=False),
        sa.Column('access_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('consolidated_into', sa.String(), nullable=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_registry.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.ForeignKeyConstraint(['consolidated_into'], ['episodes.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_episodes_agent', 'episodes', ['agent_id'])
    op.create_index('ix_episodes_user', 'episodes', ['user_id'])
    op.create_index('ix_episodes_workspace', 'episodes', ['workspace_id'])
    op.create_index('ix_episodes_session', 'episodes', ['session_id'])
    op.create_index('ix_episodes_status', 'episodes', ['status'])
    op.create_index('ix_episodes_started_at', 'episodes', ['started_at'])
    op.create_index('ix_episodes_maturity', 'episodes', ['maturity_at_time'])
    op.create_index('ix_episodes_importance', 'episodes', ['importance_score'])

    # Create episode_segments table
    op.create_table(
        'episode_segments',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('episode_id', sa.String(), nullable=False),
        sa.Column('segment_type', sa.String(), nullable=False),
        sa.Column('sequence_order', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_summary', sa.Text(), nullable=True),
        sa.Column('source_type', sa.String(), nullable=False),
        sa.Column('source_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['episode_id'], ['episodes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_episode_segments_episode', 'episode_segments', ['episode_id'])
    op.create_index('ix_episode_segments_sequence', 'episode_segments', ['sequence_order'])

    # Create episode_access_logs table
    op.create_table(
        'episode_access_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('episode_id', sa.String(), nullable=False),
        sa.Column('accessed_by', sa.String(), nullable=True),
        sa.Column('accessed_by_agent', sa.String(), nullable=True),
        sa.Column('access_type', sa.String(), nullable=False),
        sa.Column('retrieval_query', sa.Text(), nullable=True),
        sa.Column('retrieval_mode', sa.String(), nullable=True),
        sa.Column('governance_check_passed', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('agent_maturity_at_access', sa.String(), nullable=True),
        sa.Column('results_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('access_duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['episode_id'], ['episodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['accessed_by'], ['users.id']),
        sa.ForeignKeyConstraint(['accessed_by_agent'], ['agent_registry.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_episode_access_logs_episode', 'episode_access_logs', ['episode_id'])
    op.create_index('ix_episode_access_logs_created_at', 'episode_access_logs', ['created_at'])
    op.create_index('ix_episode_access_logs_access_type', 'episode_access_logs', ['access_type'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop in reverse order of creation
    op.drop_table('episode_access_logs')
    op.drop_table('episode_segments')
    op.drop_table('episodes')
