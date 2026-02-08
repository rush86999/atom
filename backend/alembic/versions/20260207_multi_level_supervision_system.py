"""Multi-Level Agent Supervision System

Add database models for user activity tracking, supervised execution queue,
and autonomous fallback supervision.

Revision ID: 20260207_multi_level_supervision
Revises: 20260207_complete_learning_analysis
Create Date: 2026-02-07

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260207_multi_level_supervision'
down_revision = '20260207_complete_learning_analysis'
branch_labels = None
depends_on = None


def upgrade():
    """Create supervision system tables."""

    # ========================================================================
    # UserState Enum (using CHECK constraint for SQLite compatibility)
    # ========================================================================

    # ========================================================================
    # User Activities Table
    # ========================================================================
    op.create_table(
        'user_activities',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('state', sa.Enum('online', 'away', 'offline', name='userstate'), nullable=False),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('manual_override', sa.Boolean(), default=False),
        sa.Column('manual_override_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_activities_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name=op.f('uq_user_activities_user_id'))
    )

    # Indexes for user_activities
    op.create_index('ix_user_activities_user_id', 'user_activities', ['user_id'])
    op.create_index('ix_user_activities_state', 'user_activities', ['state'])
    op.create_index('ix_user_activities_last_activity_at', 'user_activities', ['last_activity_at'])
    op.create_index('ix_user_activity_state_updated', 'user_activities', ['state', 'updated_at'])

    # ========================================================================
    # User Activity Sessions Table
    # ========================================================================
    op.create_table(
        'user_activity_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('activity_id', sa.String(), nullable=False),
        sa.Column('session_type', sa.String(), nullable=False),
        sa.Column('session_token', sa.String(), nullable=False),
        sa.Column('last_heartbeat', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('terminated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_activity_sessions_user_id_users'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['activity_id'], ['user_activities.id'], name=op.f('fk_user_activity_sessions_activity_id_user_activities'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_token', name=op.f('uq_user_activity_sessions_session_token'))
    )

    # Indexes for user_activity_sessions
    op.create_index('ix_user_activity_sessions_user_id', 'user_activity_sessions', ['user_id'])
    op.create_index('ix_user_activity_sessions_activity_id', 'user_activity_sessions', ['activity_id'])
    op.create_index('ix_user_activity_sessions_session_token', 'user_activity_sessions', ['session_token'])
    op.create_index('ix_user_activity_sessions_last_heartbeat', 'user_activity_sessions', ['last_heartbeat'])
    op.create_index('ix_user_activity_session_heartbeat', 'user_activity_sessions', ['last_heartbeat'])

    # ========================================================================
    # Supervised Execution Queue Table
    # ========================================================================
    op.create_table(
        'supervised_execution_queue',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('trigger_type', sa.String(), nullable=False),
        sa.Column('execution_context', sa.JSON(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'executing', 'completed', 'failed', 'cancelled', name='queuestatus'), nullable=False),
        sa.Column('supervisor_type', sa.String(), nullable=False),
        sa.Column('priority', sa.Integer(), default=0),
        sa.Column('max_attempts', sa.Integer(), default=3),
        sa.Column('attempt_count', sa.Integer(), default=0),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('execution_id', sa.String(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_registry.id'], name=op.f('fk_supervised_execution_queue_agent_id_agent_registry'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_supervised_execution_queue_user_id_users'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['execution_id'], ['agent_executions.id'], name=op.f('fk_supervised_execution_queue_execution_id_agent_executions'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for supervised_execution_queue
    op.create_index('ix_supervised_execution_queue_agent_id', 'supervised_execution_queue', ['agent_id'])
    op.create_index('ix_supervised_execution_queue_user_id', 'supervised_execution_queue', ['user_id'])
    op.create_index('ix_supervised_execution_queue_status', 'supervised_execution_queue', ['status'])
    op.create_index('ix_supervised_execution_queue_priority', 'supervised_execution_queue', ['priority'])
    op.create_index('ix_supervised_execution_queue_expires_at', 'supervised_execution_queue', ['expires_at'])
    op.create_index('ix_supervised_execution_queue_created_at', 'supervised_execution_queue', ['created_at'])
    op.create_index('ix_supervised_queue_user_status', 'supervised_execution_queue', ['user_id', 'status'])
    op.create_index('ix_supervised_queue_priority_created', 'supervised_execution_queue', ['priority', 'created_at'])
    op.create_index('ix_supervised_queue_expires', 'supervised_execution_queue', ['expires_at'])


def downgrade():
    """Drop supervision system tables."""

    # Drop tables in reverse order of creation
    # Drop indexes for supervised_execution_queue
    op.drop_index('ix_supervised_queue_expires', table_name='supervised_execution_queue')
    op.drop_index('ix_supervised_queue_priority_created', table_name='supervised_execution_queue')
    op.drop_index('ix_supervised_queue_user_status', table_name='supervised_execution_queue')
    op.drop_index('ix_supervised_execution_queue_created_at', table_name='supervised_execution_queue')
    op.drop_index('ix_supervised_execution_queue_expires_at', table_name='supervised_execution_queue')
    op.drop_index('ix_supervised_execution_queue_priority', table_name='supervised_execution_queue')
    op.drop_index('ix_supervised_execution_queue_status', table_name='supervised_execution_queue')
    op.drop_index('ix_supervised_execution_queue_user_id', table_name='supervised_execution_queue')
    op.drop_index('ix_supervised_execution_queue_agent_id', table_name='supervised_execution_queue')
    op.drop_table('supervised_execution_queue')

    # Drop indexes for user_activity_sessions
    op.drop_index('ix_user_activity_session_heartbeat', table_name='user_activity_sessions')
    op.drop_index('ix_user_activity_sessions_last_heartbeat', table_name='user_activity_sessions')
    op.drop_index('ix_user_activity_sessions_session_token', table_name='user_activity_sessions')
    op.drop_index('ix_user_activity_sessions_activity_id', table_name='user_activity_sessions')
    op.drop_index('ix_user_activity_sessions_user_id', table_name='user_activity_sessions')
    op.drop_table('user_activity_sessions')

    # Drop indexes for user_activities
    op.drop_index('ix_user_activity_state_updated', table_name='user_activities')
    op.drop_index('ix_user_activities_last_activity_at', table_name='user_activities')
    op.drop_index('ix_user_activities_state', table_name='user_activities')
    op.drop_index('ix_user_activities_user_id', table_name='user_activities')
    op.drop_table('user_activities')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS queuestatus')
    op.execute('DROP TYPE IF EXISTS userstate')
