"""Add multi-agent canvas collaboration tables

Revision ID: bcfaa9f4c376
Revises: 6e792c493b60
Create Date: 2026-02-01 11:00:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'bcfaa9f4c376'
down_revision: Union[str, Sequence[str], None] = '6e792c493b60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create canvas_collaboration_sessions table
    op.create_table(
        'canvas_collaboration_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('canvas_id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=True, server_default='active'),
        sa.Column('collaboration_mode', sa.String(), nullable=True, server_default='sequential'),
        sa.Column('max_agents', sa.Integer(), nullable=True, server_default='5'),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id', name='pk_canvas_collaboration_sessions')
    )

    # Create indexes for canvas_collaboration_sessions
    op.create_index('ix_canvas_collaboration_sessions_canvas_id', 'canvas_collaboration_sessions', ['canvas_id'], unique=False)
    op.create_index('ix_canvas_collaboration_sessions_session_id', 'canvas_collaboration_sessions', ['session_id'], unique=False)
    op.create_index('ix_canvas_collaboration_sessions_user_id', 'canvas_collaboration_sessions', ['user_id'], unique=False)
    op.create_index('ix_canvas_collaboration_sessions_status', 'canvas_collaboration_sessions', ['status'], unique=False)

    # Create canvas_agent_participants table
    op.create_table(
        'canvas_agent_participants',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('collaboration_session_id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=True, server_default='contributor'),
        sa.Column('permissions', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('status', sa.String(), nullable=True, server_default='active'),
        sa.Column('last_activity_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('actions_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('held_locks', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('joined_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('left_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['collaboration_session_id'], ['canvas_collaboration_sessions.id'], name='fk_canvas_agent_participants_collaboration_session_id'),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_registry.id'], name='fk_canvas_agent_participants_agent_id'),
        sa.PrimaryKeyConstraint('id', name='pk_canvas_agent_participants')
    )

    # Create indexes for canvas_agent_participants
    op.create_index('ix_canvas_agent_participants_collaboration_session_id', 'canvas_agent_participants', ['collaboration_session_id'], unique=False)
    op.create_index('ix_canvas_agent_participants_agent_id', 'canvas_agent_participants', ['agent_id'], unique=False)
    op.create_index('ix_canvas_agent_participants_user_id', 'canvas_agent_participants', ['user_id'], unique=False)
    op.create_index('ix_canvas_agent_participants_session_agent', 'canvas_agent_participants', ['collaboration_session_id', 'agent_id'], unique=False)
    op.create_index('ix_canvas_agent_participants_session_status', 'canvas_agent_participants', ['collaboration_session_id', 'status'], unique=False)

    # Create canvas_conflicts table
    op.create_table(
        'canvas_conflicts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('collaboration_session_id', sa.String(), nullable=False),
        sa.Column('canvas_id', sa.String(), nullable=False),
        sa.Column('component_id', sa.String(), nullable=False),
        sa.Column('agent_a_id', sa.String(), nullable=False),
        sa.Column('agent_b_id', sa.String(), nullable=False),
        sa.Column('agent_a_action', sa.JSON(), nullable=True),
        sa.Column('agent_b_action', sa.JSON(), nullable=True),
        sa.Column('resolution', sa.String(), nullable=False),
        sa.Column('resolved_by', sa.String(), nullable=True),
        sa.Column('resolved_action', sa.JSON(), nullable=True),
        sa.Column('conflict_time', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['collaboration_session_id'], ['canvas_collaboration_sessions.id'], name='fk_canvas_conflicts_collaboration_session_id'),
        sa.ForeignKeyConstraint(['agent_a_id'], ['agent_registry.id'], name='fk_canvas_conflicts_agent_a_id'),
        sa.ForeignKeyConstraint(['agent_b_id'], ['agent_registry.id'], name='fk_canvas_conflicts_agent_b_id'),
        sa.PrimaryKeyConstraint('id', name='pk_canvas_conflicts')
    )

    # Create indexes for canvas_conflicts
    op.create_index('ix_canvas_conflicts_collaboration_session_id', 'canvas_conflicts', ['collaboration_session_id'], unique=False)
    op.create_index('ix_canvas_conflicts_canvas_id', 'canvas_conflicts', ['canvas_id'], unique=False)
    op.create_index('ix_canvas_conflicts_component_id', 'canvas_conflicts', ['component_id'], unique=False)
    op.create_index('ix_canvas_conflicts_agent_a_id', 'canvas_conflicts', ['agent_a_id'], unique=False)
    op.create_index('ix_canvas_conflicts_agent_b_id', 'canvas_conflicts', ['agent_b_id'], unique=False)
    op.create_index('ix_canvas_conflicts_conflict_time', 'canvas_conflicts', ['conflict_time'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop canvas_conflicts table and indexes
    try:
        op.drop_index('ix_canvas_conflicts_conflict_time', table_name='canvas_conflicts')
    except Exception:
        pass

    try:
        op.drop_index('ix_canvas_conflicts_agent_b_id', table_name='canvas_conflicts')
    except Exception:
        pass

    try:
        op.drop_index('ix_canvas_conflicts_agent_a_id', table_name='canvas_conflicts')
    except Exception:
        pass

    try:
        op.drop_index('ix_canvas_conflicts_component_id', table_name='canvas_conflicts')
    except Exception:
        pass

    try:
        op.drop_index('ix_canvas_conflicts_canvas_id', table_name='canvas_conflicts')
    except Exception:
        pass

    try:
        op.drop_index('ix_canvas_conflicts_collaboration_session_id', table_name='canvas_conflicts')
    except Exception:
        pass

    op.drop_table('canvas_conflicts')

    # Drop canvas_agent_participants table and indexes
    try:
        op.drop_index('ix_canvas_agent_participants_session_status', table_name='canvas_agent_participants')
    except Exception:
        pass

    try:
        op.drop_index('ix_canvas_agent_participants_session_agent', table_name='canvas_agent_participants')
    except Exception:
        pass

    try:
        op.drop_index('ix_canvas_agent_participants_user_id', table_name='canvas_agent_participants')
    except Exception:
        pass

    try:
        op.drop_index('ix_canvas_agent_participants_agent_id', table_name='canvas_agent_participants')
    except Exception:
        pass

    try:
        op.drop_index('ix_canvas_agent_participants_collaboration_session_id', table_name='canvas_agent_participants')
    except Exception:
        pass

    op.drop_table('canvas_agent_participants')

    # Drop canvas_collaboration_sessions table and indexes
    try:
        op.drop_index('ix_canvas_collaboration_sessions_status', table_name='canvas_collaboration_sessions')
    except Exception:
        pass

    try:
        op.drop_index('ix_canvas_collaboration_sessions_user_id', table_name='canvas_collaboration_sessions')
    except Exception:
        pass

    try:
        op.drop_index('ix_canvas_collaboration_sessions_session_id', table_name='canvas_collaboration_sessions')
    except Exception:
        pass

    try:
        op.drop_index('ix_canvas_collaboration_sessions_canvas_id', table_name='canvas_collaboration_sessions')
    except Exception:
        pass

    op.drop_table('canvas_collaboration_sessions')
