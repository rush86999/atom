"""add_workflow_debugging_models

Revision ID: a25c563b8198
Revises: 1da492286fd4
Create Date: 2026-02-01 14:34:16.892757

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a25c563b8198'
down_revision: Union[str, Sequence[str], None] = '1da492286fd4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Create workflow_debug_sessions table
    op.create_table(
        'workflow_debug_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workflow_id', sa.String(), nullable=False),
        sa.Column('execution_id', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('session_name', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True, server_default='active'),
        sa.Column('current_step', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('current_node_id', sa.String(), nullable=True),
        sa.Column('breakpoints', sa.JSON(), nullable=True),
        sa.Column('variables', sa.JSON(), nullable=True),
        sa.Column('call_stack', sa.JSON(), nullable=True),
        sa.Column('stop_on_entry', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('stop_on_exceptions', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('stop_on_error', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('conditional_breakpoints', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['execution_id'], ['workflow_executions.execution_id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_debug_sessions_workflow', 'workflow_debug_sessions', ['workflow_id'])
    op.create_index('ix_debug_sessions_user', 'workflow_debug_sessions', ['user_id', 'created_at'])
    op.create_index('ix_debug_sessions_status', 'workflow_debug_sessions', ['status'])

    # Create workflow_breakpoints table
    op.create_table(
        'workflow_breakpoints',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workflow_id', sa.String(), nullable=False),
        sa.Column('debug_session_id', sa.String(), nullable=True),
        sa.Column('node_id', sa.String(), nullable=False),
        sa.Column('edge_id', sa.String(), nullable=True),
        sa.Column('breakpoint_type', sa.String(), nullable=True, server_default='node'),
        sa.Column('condition', sa.Text(), nullable=True),
        sa.Column('hit_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('hit_limit', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('is_disabled', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('log_message', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['debug_session_id'], ['workflow_debug_sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_breakpoints_workflow', 'workflow_breakpoints', ['workflow_id', 'is_active'])
    op.create_index('ix_breakpoints_session', 'workflow_breakpoints', ['debug_session_id'])
    op.create_index('ix_breakpoints_node', 'workflow_breakpoints', ['node_id'])

    # Create execution_traces table
    op.create_table(
        'execution_traces',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workflow_id', sa.String(), nullable=False),
        sa.Column('execution_id', sa.String(), nullable=False),
        sa.Column('debug_session_id', sa.String(), nullable=True),
        sa.Column('step_number', sa.Integer(), nullable=False),
        sa.Column('node_id', sa.String(), nullable=False),
        sa.Column('node_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('input_data', sa.JSON(), nullable=True),
        sa.Column('output_data', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('variables_before', sa.JSON(), nullable=True),
        sa.Column('variables_after', sa.JSON(), nullable=True),
        sa.Column('variable_changes', sa.JSON(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('parent_step_id', sa.String(), nullable=True),
        sa.Column('thread_id', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['debug_session_id'], ['workflow_debug_sessions.id'], ),
        sa.ForeignKeyConstraint(['execution_id'], ['workflow_executions.execution_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_traces_execution', 'execution_traces', ['execution_id', 'step_number'])
    op.create_index('ix_traces_workflow', 'execution_traces', ['workflow_id'])
    op.create_index('ix_traces_debug_session', 'execution_traces', ['debug_session_id'])
    op.create_index('ix_traces_node', 'execution_traces', ['node_id'])

    # Create debug_variables table
    op.create_table(
        'debug_variables',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('trace_id', sa.String(), nullable=False),
        sa.Column('debug_session_id', sa.String(), nullable=True),
        sa.Column('variable_name', sa.String(), nullable=False),
        sa.Column('variable_path', sa.String(), nullable=False),
        sa.Column('variable_type', sa.String(), nullable=False),
        sa.Column('value', sa.JSON(), nullable=True),
        sa.Column('value_preview', sa.Text(), nullable=True),
        sa.Column('is_mutable', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('scope', sa.String(), nullable=True, server_default='local'),
        sa.Column('is_changed', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('previous_value', sa.JSON(), nullable=True),
        sa.Column('is_watch', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('watch_expression', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['debug_session_id'], ['workflow_debug_sessions.id'], ),
        sa.ForeignKeyConstraint(['trace_id'], ['execution_traces.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_debug_variables_trace', 'debug_variables', ['trace_id'])
    op.create_index('ix_debug_variables_session', 'debug_variables', ['debug_session_id'])
    op.create_index('ix_debug_variables_name', 'debug_variables', ['variable_name'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_debug_variables_name', table_name='debug_variables')
    op.drop_index('ix_debug_variables_session', table_name='debug_variables')
    op.drop_index('ix_debug_variables_trace', table_name='debug_variables')
    op.drop_table('debug_variables')

    op.drop_index('ix_traces_node', table_name='execution_traces')
    op.drop_index('ix_traces_debug_session', table_name='execution_traces')
    op.drop_index('ix_traces_workflow', table_name='execution_traces')
    op.drop_index('ix_traces_execution', table_name='execution_traces')
    op.drop_table('execution_traces')

    op.drop_index('ix_breakpoints_node', table_name='workflow_breakpoints')
    op.drop_index('ix_breakpoints_session', table_name='workflow_breakpoints')
    op.drop_index('ix_breakpoints_workflow', table_name='workflow_breakpoints')
    op.drop_table('workflow_breakpoints')

    op.drop_index('ix_debug_sessions_status', table_name='workflow_debug_sessions')
    op.drop_index('ix_debug_sessions_user', table_name='workflow_debug_sessions')
    op.drop_index('ix_debug_sessions_workflow', table_name='workflow_debug_sessions')
    op.drop_table('workflow_debug_sessions')
