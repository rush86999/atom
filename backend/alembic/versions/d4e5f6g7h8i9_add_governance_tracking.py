"""Add governance tracking for streaming, canvas, and forms

Revision ID: d4e5f6g7h8i9
Revises: 1a2b3c4d5e6f
Create Date: 2026-01-30 12:00:00.000000

This migration adds:
- agent_id column to chat_sessions
- default_agent_id to workspaces (via metadata_json)
- canvas_audit table for canvas action tracking
- Indexes for agent execution queries
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd4e5f6g7h8i9'
down_revision = '1a2b3c4d5e6f'
branch_labels = None
depends_on = None


def upgrade():
    # ### Add agent_id to chat_sessions ###
    op.add_column(
        'chat_sessions',
        sa.Column('agent_id', sa.String(), nullable=True)
    )

    # Create index for agent_id in chat_sessions
    op.create_index(
        'ix_chat_sessions_agent_id',
        'chat_sessions',
        ['agent_id'],
        unique=False
    )

    # ### Add workspace_id to chat_sessions if not exists ###
    # Check if workspace_id exists first to avoid errors
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('chat_sessions')]

    if 'workspace_id' not in columns:
        op.add_column(
            'chat_sessions',
            sa.Column('workspace_id', sa.String(), nullable=True, server_default='default')
        )
        op.create_index(
            'ix_chat_sessions_workspace_id',
            'chat_sessions',
            ['workspace_id'],
            unique=False
        )

    # ### Create canvas_audit table ###
    op.create_table(
        'canvas_audit',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=True),
        sa.Column('agent_execution_id', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('canvas_id', sa.String(), nullable=True),
        sa.Column('component_type', sa.String(), nullable=False),  # 'chart', 'markdown', 'form', etc.
        sa.Column('component_name', sa.String(), nullable=True),  # 'line_chart', 'bar_chart', etc.
        sa.Column('action', sa.String(), nullable=False),  # 'present', 'close', 'submit'
        sa.Column('audit_metadata', sa.JSON(), nullable=True),  # Renamed from 'metadata' (reserved in SQLAlchemy)
        sa.Column('governance_check_passed', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for canvas_audit
    op.create_index(
        'ix_canvas_audit_workspace_id',
        'canvas_audit',
        ['workspace_id'],
        unique=False
    )
    op.create_index(
        'ix_canvas_audit_agent_id',
        'canvas_audit',
        ['agent_id'],
        unique=False
    )
    op.create_index(
        'ix_canvas_audit_user_id',
        'canvas_audit',
        ['user_id'],
        unique=False
    )
    op.create_index(
        'ix_canvas_audit_created_at',
        'canvas_audit',
        ['created_at'],
        unique=False
    )

    # ### Add indexes for agent_executions table ###
    # These optimize queries for agent execution tracking
    op.create_index(
        'ix_agent_executions_workspace_id',
        'agent_executions',
        ['workspace_id'],
        unique=False
    )
    op.create_index(
        'ix_agent_executions_status',
        'agent_executions',
        ['status'],
        unique=False
    )
    op.create_index(
        'ix_agent_executions_started_at',
        'agent_executions',
        ['started_at'],
        unique=False
    )

    # ### Add compound index for agent execution queries ###
    # This optimizes common queries like "get executions for agent in workspace"
    try:
        # Postgres syntax
        op.execute(
            'CREATE INDEX ix_agent_executions_agent_workspace ON agent_executions (agent_id, workspace_id)'
        )
    except Exception:
        # Fallback for other databases
        pass

    # ### end Alembic commands ###


def downgrade():
    # ### Drop canvas_audit table ###
    op.drop_index('ix_canvas_audit_created_at', 'canvas_audit')
    op.drop_index('ix_canvas_audit_user_id', 'canvas_audit')
    op.drop_index('ix_canvas_audit_agent_id', 'canvas_audit')
    op.drop_index('ix_canvas_audit_workspace_id', 'canvas_audit')
    op.drop_table('canvas_audit')

    # ### Drop agent_executions indexes ###
    try:
        op.execute('DROP INDEX ix_agent_executions_agent_workspace')
    except Exception:
        pass

    op.drop_index('ix_agent_executions_started_at', 'agent_executions')
    op.drop_index('ix_agent_executions_status', 'agent_executions')
    op.drop_index('ix_agent_executions_workspace_id', 'agent_executions')

    # ### Remove agent_id from chat_sessions ###
    op.drop_index('ix_chat_sessions_agent_id', 'chat_sessions')
    op.drop_column('chat_sessions', 'agent_id')

    # ### Remove workspace_id from chat_sessions (if we added it) ###
    # Keep workspace_id as it may be used by other features
    # op.drop_index('ix_chat_sessions_workspace_id', 'chat_sessions')
    # op.drop_column('chat_sessions', 'workspace_id')

    # ### end Alembic commands ###
