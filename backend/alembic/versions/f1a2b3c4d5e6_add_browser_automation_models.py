"""Add browser automation models

Revision ID: f1a2b3c4d5e6
Revises: e1f2g3h4i5j6
Create Date: 2026-01-31 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = 'e1f2g3h4i5j6'
branch_labels = None
depends_on = None


def upgrade():
    """Create browser_sessions and browser_audit tables."""

    # Create browser_sessions table
    op.create_table(
        'browser_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=True),
        sa.Column('agent_id', sa.String(), nullable=True),
        sa.Column('agent_execution_id', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('browser_type', sa.String(), server_default='chromium', nullable=True),
        sa.Column('headless', sa.Boolean(), server_default='1', nullable=True),
        sa.Column('status', sa.String(), server_default='active', nullable=True),
        sa.Column('current_url', sa.Text(), nullable=True),
        sa.Column('page_title', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('governance_check_passed', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_registry.id'], ),
        sa.ForeignKeyConstraint(['agent_execution_id'], ['agent_executions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_browser_sessions_agent_id'), 'browser_sessions', ['agent_id'], unique=False)
    op.create_index(op.f('ix_browser_sessions_agent_execution_id'), 'browser_sessions', ['agent_execution_id'], unique=False)
    op.create_index(op.f('ix_browser_sessions_session_id'), 'browser_sessions', ['session_id'], unique=True)
    op.create_index(op.f('ix_browser_sessions_user_id'), 'browser_sessions', ['user_id'], unique=False)
    op.create_index(op.f('ix_browser_sessions_workspace_id'), 'browser_sessions', ['workspace_id'], unique=False)

    # Create browser_audit table
    op.create_table(
        'browser_audit',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=True),
        sa.Column('agent_id', sa.String(), nullable=True),
        sa.Column('agent_execution_id', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('action_type', sa.String(), nullable=False),
        sa.Column('action_target', sa.Text(), nullable=True),
        sa.Column('action_params', sa.JSON(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('result_summary', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('result_data', sa.JSON(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('governance_check_passed', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['browser_sessions.session_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_browser_audit_action_type'), 'browser_audit', ['action_type'], unique=False)
    op.create_index(op.f('ix_browser_audit_agent_execution_id'), 'browser_audit', ['agent_execution_id'], unique=False)
    op.create_index(op.f('ix_browser_audit_agent_id'), 'browser_audit', ['agent_id'], unique=False)
    op.create_index(op.f('ix_browser_audit_session_id'), 'browser_audit', ['session_id'], unique=False)
    op.create_index(op.f('ix_browser_audit_user_id'), 'browser_audit', ['user_id'], unique=False)
    op.create_index(op.f('ix_browser_audit_workspace_id'), 'browser_audit', ['workspace_id'], unique=False)


def downgrade():
    """Drop browser_sessions and browser_audit tables."""

    # Drop browser_audit table
    op.drop_index(op.f('ix_browser_audit_workspace_id'), table_name='browser_audit')
    op.drop_index(op.f('ix_browser_audit_user_id'), table_name='browser_audit')
    op.drop_index(op.f('ix_browser_audit_session_id'), table_name='browser_audit')
    op.drop_index(op.f('ix_browser_audit_agent_id'), table_name='browser_audit')
    op.drop_index(op.f('ix_browser_audit_agent_execution_id'), table_name='browser_audit')
    op.drop_index(op.f('ix_browser_audit_action_type'), table_name='browser_audit')
    op.drop_table('browser_audit')

    # Drop browser_sessions table
    op.drop_index(op.f('ix_browser_sessions_workspace_id'), table_name='browser_sessions')
    op.drop_index(op.f('ix_browser_sessions_user_id'), table_name='browser_sessions')
    op.drop_index(op.f('ix_browser_sessions_session_id'), table_name='browser_sessions')
    op.drop_index(op.f('ix_browser_sessions_agent_execution_id'), table_name='browser_sessions')
    op.drop_index(op.f('ix_browser_sessions_agent_id'), table_name='browser_sessions')
    op.drop_table('browser_sessions')
