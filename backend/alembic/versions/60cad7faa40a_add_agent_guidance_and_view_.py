"""add agent guidance and view orchestration models

Revision ID: 60cad7faa40a
Revises: 4ea149ecf75f
Create Date: 2026-02-02 11:07:51.372139

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '60cad7faa40a'
down_revision: Union[str, Sequence[str], None] = '4ea149ecf75f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Create agent_operation_tracker table
    op.create_table(
        'agent_operation_tracker',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('operation_type', sa.String(), nullable=False),
        sa.Column('operation_id', sa.String(), nullable=False),
        sa.Column('current_step', sa.String(), nullable=True),
        sa.Column('total_steps', sa.Integer(), nullable=True),
        sa.Column('current_step_index', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('status', sa.String(), nullable=True, server_default='running'),
        sa.Column('progress', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('what_explanation', sa.Text(), nullable=True),
        sa.Column('why_explanation', sa.Text(), nullable=True),
        sa.Column('next_steps', sa.Text(), nullable=True),
        sa.Column('operation_metadata', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('logs', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_registry.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('operation_id')
    )
    op.create_index(op.f('ix_agent_operation_tracker_agent_id'), 'agent_operation_tracker', ['agent_id'], unique=False)
    op.create_index(op.f('ix_agent_operation_tracker_operation_id'), 'agent_operation_tracker', ['operation_id'], unique=True)
    op.create_index(op.f('ix_agent_operation_tracker_operation_type'), 'agent_operation_tracker', ['operation_type'], unique=False)
    op.create_index(op.f('ix_agent_operation_tracker_status'), 'agent_operation_tracker', ['status'], unique=False)
    op.create_index(op.f('ix_agent_operation_tracker_user_id'), 'agent_operation_tracker', ['user_id'], unique=False)

    # Create agent_request_log table
    op.create_table(
        'agent_request_log',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('request_id', sa.String(), nullable=False),
        sa.Column('request_type', sa.String(), nullable=False),
        sa.Column('request_data', sa.JSON(), nullable=False),
        sa.Column('user_response', sa.JSON(), nullable=True),
        sa.Column('response_time_seconds', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked', sa.Boolean(), nullable=True, server_default='False'),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_registry.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('request_id')
    )
    op.create_index(op.f('ix_agent_request_log_agent_id'), 'agent_request_log', ['agent_id'], unique=False)
    op.create_index(op.f('ix_agent_request_log_request_id'), 'agent_request_log', ['request_id'], unique=True)
    op.create_index(op.f('ix_agent_request_log_request_type'), 'agent_request_log', ['request_type'], unique=False)
    op.create_index(op.f('ix_agent_request_log_user_id'), 'agent_request_log', ['user_id'], unique=False)

    # Create view_orchestration_state table
    op.create_table(
        'view_orchestration_state',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('active_views', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('layout', sa.String(), nullable=True, server_default='canvas'),
        sa.Column('controlling_agent', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['controlling_agent'], ['agent_registry.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id')
    )
    op.create_index(op.f('ix_view_orchestration_state_session_id'), 'view_orchestration_state', ['session_id'], unique=True)
    op.create_index(op.f('ix_view_orchestration_state_user_id'), 'view_orchestration_state', ['user_id'], unique=False)

    # Create operation_error_resolutions table
    op.create_table(
        'operation_error_resolutions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('error_type', sa.String(), nullable=False),
        sa.Column('error_code', sa.String(), nullable=True),
        sa.Column('resolution_attempted', sa.String(), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('user_feedback', sa.Text(), nullable=True),
        sa.Column('agent_suggested', sa.Boolean(), nullable=True, server_default='True'),
        sa.Column('alternative_used', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_operation_error_resolutions_error_code'), 'operation_error_resolutions', ['error_code'], unique=False)
    op.create_index(op.f('ix_operation_error_resolutions_error_type'), 'operation_error_resolutions', ['error_type'], unique=False)
    op.create_index(op.f('ix_operation_error_resolutions_success'), 'operation_error_resolutions', ['success'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(op.f('ix_operation_error_resolutions_success'), table_name='operation_error_resolutions')
    op.drop_index(op.f('ix_operation_error_resolutions_error_type'), table_name='operation_error_resolutions')
    op.drop_index(op.f('ix_operation_error_resolutions_error_code'), table_name='operation_error_resolutions')
    op.drop_table('operation_error_resolutions')

    op.drop_index(op.f('ix_view_orchestration_state_user_id'), table_name='view_orchestration_state')
    op.drop_index(op.f('ix_view_orchestration_state_session_id'), table_name='view_orchestration_state')
    op.drop_table('view_orchestration_state')

    op.drop_index(op.f('ix_agent_request_log_user_id'), table_name='agent_request_log')
    op.drop_index(op.f('ix_agent_request_log_request_type'), table_name='agent_request_log')
    op.drop_index(op.f('ix_agent_request_log_request_id'), table_name='agent_request_log')
    op.drop_index(op.f('ix_agent_request_log_agent_id'), table_name='agent_request_log')
    op.drop_table('agent_request_log')

    op.drop_index(op.f('ix_agent_operation_tracker_user_id'), table_name='agent_operation_tracker')
    op.drop_index(op.f('ix_agent_operation_tracker_status'), table_name='agent_operation_tracker')
    op.drop_index(op.f('ix_agent_operation_tracker_operation_type'), table_name='agent_operation_tracker')
    op.drop_index(op.f('ix_agent_operation_tracker_operation_id'), table_name='agent_operation_tracker')
    op.drop_index(op.f('ix_agent_operation_tracker_agent_id'), table_name='agent_operation_tracker')
    op.drop_table('agent_operation_tracker')
