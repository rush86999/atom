"""Remove workspace multi-tenancy

Revision ID: e1f2g3h4i5j6
Revises: d4e5f6g7h8i9
Create Date: 2026-01-30 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e1f2g3h4i5j6'
down_revision = 'd4e5f6g7h8i9'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Drop workspace_id from chat_sessions
    try:
        op.drop_index('ix_chat_sessions_workspace_id', table_name='chat_sessions')
    except Exception:
        pass
    
    try:
        op.drop_column('chat_sessions', 'workspace_id')
    except Exception:
        pass

    # 2. Drop workspace_id indices from execution and audit tables (keep columns for audit trail)
    # agent_executions
    try:
        op.drop_index('ix_agent_executions_workspace_id', table_name='agent_executions')
    except Exception:
        pass
    
    try:
        # Also drop the compound index if it exists
        op.execute('DROP INDEX IF EXISTS ix_agent_executions_agent_workspace')
    except Exception:
        pass

    # canvas_audit
    try:
        op.drop_index('ix_canvas_audit_workspace_id', table_name='canvas_audit')
    except Exception:
        pass

    # chat_messages
    try:
        op.drop_index('ix_chat_messages_workspace_id', table_name='chat_messages')
    except Exception:
        pass

    # skill_executions
    try:
        op.drop_index('ix_skill_executions_workspace_id', table_name='skill_executions')
    except Exception:
        pass

    # ingested_documents
    try:
        op.drop_index('ix_ingested_documents_workspace_id', table_name='ingested_documents')
    except Exception:
        pass

    # ingestion_settings
    try:
        op.drop_index('ix_ingestion_settings_workspace_id', table_name='ingestion_settings')
    except Exception:
        pass

    # graph_nodes
    try:
        op.drop_index('ix_graph_nodes_workspace_id', table_name='graph_nodes')
    except Exception:
        pass

    # graph_edges
    try:
        op.drop_index('ix_graph_edges_workspace_id', table_name='graph_edges')
    except Exception:
        pass

    # graph_communities
    try:
        op.drop_index('ix_graph_communities_workspace_id', table_name='graph_communities')
    except Exception:
        pass

    # 3. Make workspace_id nullable for tables where it was mandatory but we're keeping it
    try:
        op.alter_column('agent_executions', 'workspace_id', existing_type=sa.String(), nullable=True)
        op.alter_column('canvas_audit', 'workspace_id', existing_type=sa.String(), nullable=True)
        op.alter_column('chat_messages', 'workspace_id', existing_type=sa.String(), nullable=True)
        op.alter_column('skill_executions', 'workspace_id', existing_type=sa.String(), nullable=True)
    except Exception:
        pass


def downgrade():
    # Restore workspace_id to chat_sessions
    try:
        op.add_column('chat_sessions', sa.Column('workspace_id', sa.String(), nullable=True, server_default='default'))
        op.create_index('ix_chat_sessions_workspace_id', 'chat_sessions', ['workspace_id'], unique=False)
    except Exception:
        pass

    # Restore indices
    try:
        op.create_index('ix_agent_executions_workspace_id', 'agent_executions', ['workspace_id'], unique=False)
        op.create_index('ix_canvas_audit_workspace_id', 'canvas_audit', ['workspace_id'], unique=False)
        op.create_index('ix_chat_messages_workspace_id', 'chat_messages', ['workspace_id'], unique=False)
        op.create_index('ix_skill_executions_workspace_id', 'skill_executions', ['workspace_id'], unique=False)
    except Exception:
        pass
