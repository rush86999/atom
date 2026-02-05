"""Add device capability models

Revision ID: g1h2i3j4k5l6
Revises: f1a2b3c4d5e6
Create Date: 2026-02-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = 'g1h2i3j4k5l6'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    """Create device_nodes table and create device_sessions and device_audit tables."""

    # Create device_nodes table if it doesn't exist
    # Check if table exists first using batch operations for SQLite
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)

    if 'device_nodes' not in inspector.get_table_names():
        op.create_table(
            'device_nodes',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('workspace_id', sa.String(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('device_id', sa.String(), nullable=False),
            sa.Column('node_type', sa.String(), nullable=False),
            sa.Column('status', sa.String(), server_default='offline', nullable=True),
            sa.Column('last_seen', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
            sa.Column('capabilities', sa.JSON(), nullable=True),
            sa.Column('capabilities_detailed', sa.JSON(), nullable=True),
            sa.Column('platform', sa.String(), nullable=True),
            sa.Column('platform_version', sa.String(), nullable=True),
            sa.Column('architecture', sa.String(), nullable=True),
            sa.Column('tauri_version', sa.String(), nullable=True),
            sa.Column('app_version', sa.String(), nullable=True),
            sa.Column('version', sa.String(), nullable=True),
            sa.Column('hardware_info', sa.JSON(), nullable=True),
            sa.Column('metadata_json', sa.JSON(), nullable=True),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_device_nodes_workspace_id'), 'device_nodes', ['workspace_id'], unique=False)
        op.create_index(op.f('ix_device_nodes_device_id'), 'device_nodes', ['device_id'], unique=False)
        op.create_index(op.f('ix_device_nodes_user_id'), 'device_nodes', ['user_id'], unique=False)
    else:
        # Extend existing device_nodes table with new columns
        op.add_column('device_nodes', sa.Column('capabilities_detailed', sa.JSON(), nullable=True))
        op.add_column('device_nodes', sa.Column('platform', sa.String(), nullable=True))
        op.add_column('device_nodes', sa.Column('platform_version', sa.String(), nullable=True))
        op.add_column('device_nodes', sa.Column('architecture', sa.String(), nullable=True))
        op.add_column('device_nodes', sa.Column('tauri_version', sa.String(), nullable=True))
        op.add_column('device_nodes', sa.Column('app_version', sa.String(), nullable=True))
        op.add_column('device_nodes', sa.Column('hardware_info', sa.JSON(), nullable=True))

    # Create device_sessions table
    op.create_table(
        'device_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=True),
        sa.Column('device_node_id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=True),
        sa.Column('agent_execution_id', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),

        # Session details
        sa.Column('session_type', sa.String(), nullable=False),  # 'camera', 'screen_record', 'command', etc.
        sa.Column('status', sa.String(), server_default='active', nullable=True),  # active, closed, error
        sa.Column('configuration', sa.JSON(), nullable=True),  # Session-specific config

        # Metadata
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('governance_check_passed', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),

        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_device_sessions_agent_id'), 'device_sessions', ['agent_id'], unique=False)
    op.create_index(op.f('ix_device_sessions_agent_execution_id'), 'device_sessions', ['agent_execution_id'], unique=False)
    op.create_index(op.f('ix_device_sessions_session_id'), 'device_sessions', ['session_id'], unique=True)
    op.create_index(op.f('ix_device_sessions_user_id'), 'device_sessions', ['user_id'], unique=False)
    op.create_index(op.f('ix_device_sessions_device_node_id'), 'device_sessions', ['device_node_id'], unique=False)
    op.create_index(op.f('ix_device_sessions_workspace_id'), 'device_sessions', ['workspace_id'], unique=False)

    # Create device_audit table
    op.create_table(
        'device_audit',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=True),
        sa.Column('agent_id', sa.String(), nullable=True),
        sa.Column('agent_execution_id', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('device_node_id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=True),

        # Action details
        sa.Column('action_type', sa.String(), nullable=False),  # camera_snap, screen_record_start, location, etc.
        sa.Column('action_params', sa.JSON(), nullable=True),  # Full parameters for reproducibility

        # Results
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('result_summary', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('result_data', sa.JSON(), nullable=True),  # Structured result data
        sa.Column('file_path', sa.Text(), nullable=True),  # For camera/screen recordings

        # Metadata
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('governance_check_passed', sa.Boolean(), nullable=True),

        # Timing
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),

        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_device_audit_action_type'), 'device_audit', ['action_type'], unique=False)
    op.create_index(op.f('ix_device_audit_agent_execution_id'), 'device_audit', ['agent_execution_id'], unique=False)
    op.create_index(op.f('ix_device_audit_agent_id'), 'device_audit', ['agent_id'], unique=False)
    op.create_index(op.f('ix_device_audit_session_id'), 'device_audit', ['session_id'], unique=False)
    op.create_index(op.f('ix_device_audit_user_id'), 'device_audit', ['user_id'], unique=False)
    op.create_index(op.f('ix_device_audit_device_node_id'), 'device_audit', ['device_node_id'], unique=False)
    op.create_index(op.f('ix_device_audit_workspace_id'), 'device_audit', ['workspace_id'], unique=False)


def downgrade():
    """Drop device_sessions, device_audit, and device_nodes tables."""

    # Drop device_audit table
    op.drop_index(op.f('ix_device_audit_workspace_id'), table_name='device_audit')
    op.drop_index(op.f('ix_device_audit_device_node_id'), table_name='device_audit')
    op.drop_index(op.f('ix_device_audit_user_id'), table_name='device_audit')
    op.drop_index(op.f('ix_device_audit_session_id'), table_name='device_audit')
    op.drop_index(op.f('ix_device_audit_agent_id'), table_name='device_audit')
    op.drop_index(op.f('ix_device_audit_agent_execution_id'), table_name='device_audit')
    op.drop_index(op.f('ix_device_audit_action_type'), table_name='device_audit')
    op.drop_table('device_audit')

    # Drop device_sessions table
    op.drop_index(op.f('ix_device_sessions_workspace_id'), table_name='device_sessions')
    op.drop_index(op.f('ix_device_sessions_device_node_id'), table_name='device_sessions')
    op.drop_index(op.f('ix_device_sessions_user_id'), table_name='device_sessions')
    op.drop_index(op.f('ix_device_sessions_session_id'), table_name='device_sessions')
    op.drop_index(op.f('ix_device_sessions_agent_execution_id'), table_name='device_sessions')
    op.drop_index(op.f('ix_device_sessions_agent_id'), table_name='device_sessions')
    op.drop_table('device_sessions')

    # Drop device_nodes table
    op.drop_index(op.f('ix_device_nodes_user_id'), table_name='device_nodes')
    op.drop_index(op.f('ix_device_nodes_device_id'), table_name='device_nodes')
    op.drop_index(op.f('ix_device_nodes_workspace_id'), table_name='device_nodes')
    op.drop_table('device_nodes')
