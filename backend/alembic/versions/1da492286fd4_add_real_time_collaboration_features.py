"""add real-time collaboration features

Revision ID: 1da492286fd4
Revises: f179c790c689
Create Date: 2026-02-01 14:30:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '1da492286fd4'
down_revision: Union[str, Sequence[str], None] = 'f179c790c689'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Create workflow_collaboration_sessions table
    op.create_table(
        'workflow_collaboration_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('workflow_id', sa.String(), nullable=False),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('active_users', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('last_activity', sa.DateTime(), nullable=True),
        sa.Column('collaboration_mode', sa.String(), nullable=False, server_default='parallel'),
        sa.Column('max_users', sa.Integer(), nullable=False, server_default='10'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id')
    )
    op.create_index('ix_workflow_collaboration_sessions_workflow', 'workflow_collaboration_sessions', ['workflow_id'])
    op.create_index('ix_workflow_collaboration_sessions_created_by', 'workflow_collaboration_sessions', ['created_by'])
    op.create_index('ix_workflow_collaboration_sessions_active', 'workflow_collaboration_sessions', ['last_activity'])

    # Create collaboration_session_participants table
    op.create_table(
        'collaboration_session_participants',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('joined_at', sa.DateTime(), nullable=True),
        sa.Column('last_heartbeat', sa.DateTime(), nullable=True),
        sa.Column('cursor_position', sa.JSON(), nullable=True),
        sa.Column('selected_node', sa.String(), nullable=True),
        sa.Column('user_name', sa.String(), nullable=True),
        sa.Column('user_color', sa.String(), nullable=False, server_default='#2196F3'),
        sa.Column('role', sa.String(), nullable=False, server_default='editor'),
        sa.Column('can_edit', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['session_id'], ['workflow_collaboration_sessions.session_id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', 'user_id', name='uq_collaboration_participants_session_user')
    )
    op.create_index('ix_collaboration_participants_session_user', 'collaboration_session_participants', ['session_id', 'user_id'], unique=True)
    op.create_index('ix_collaboration_participants_heartbeat', 'collaboration_session_participants', ['last_heartbeat'])

    # Create edit_locks table
    op.create_table(
        'edit_locks',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('workflow_id', sa.String(), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=False),
        sa.Column('resource_id', sa.String(), nullable=False),
        sa.Column('locked_by', sa.String(), nullable=False),
        sa.Column('locked_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('lock_reason', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['session_id'], ['workflow_collaboration_sessions.session_id'], ),
        sa.ForeignKeyConstraint(['locked_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_edit_locks_workflow', 'edit_locks', ['workflow_id', 'is_active'])
    op.create_index('ix_edit_locks_resource', 'edit_locks', ['resource_type', 'resource_id', 'is_active'])
    op.create_index('ix_edit_locks_expiry', 'edit_locks', ['expires_at', 'is_active'])

    # Create workflow_shares table
    op.create_table(
        'workflow_shares',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('share_id', sa.String(), nullable=False),
        sa.Column('workflow_id', sa.String(), nullable=False),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('share_link', sa.String(), nullable=False),
        sa.Column('share_type', sa.String(), nullable=False, server_default='link'),
        sa.Column('permissions', sa.JSON(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('max_uses', sa.Integer(), nullable=True),
        sa.Column('use_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_accessed', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['revoked_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('share_id'),
        sa.UniqueConstraint('share_link')
    )
    op.create_index('ix_workflow_shares_workflow', 'workflow_shares', ['workflow_id', 'is_active'])
    op.create_index('ix_workflow_shares_expires', 'workflow_shares', ['expires_at', 'is_active'])

    # Create collaboration_comments table
    op.create_table(
        'collaboration_comments',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workflow_id', sa.String(), nullable=False),
        sa.Column('author_id', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('parent_comment_id', sa.String(), nullable=True),
        sa.Column('context_type', sa.String(), nullable=True),
        sa.Column('context_id', sa.String(), nullable=True),
        sa.Column('is_resolved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('resolved_by', sa.String(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['parent_comment_id'], ['collaboration_comments.id'], ),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_collaboration_comments_workflow', 'collaboration_comments', ['workflow_id'])
    op.create_index('ix_collaboration_comments_context', 'collaboration_comments', ['context_type', 'context_id'])
    op.create_index('ix_collaboration_comments_thread', 'collaboration_comments', ['parent_comment_id'])
    op.create_index('ix_collaboration_comments_resolved', 'collaboration_comments', ['is_resolved'])

    # Create collaboration_audit table
    op.create_table(
        'collaboration_audit',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workflow_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('action_type', sa.String(), nullable=False),
        sa.Column('action_details', sa.JSON(), nullable=True),
        sa.Column('resource_type', sa.String(), nullable=True),
        sa.Column('resource_id', sa.String(), nullable=True),
        sa.Column('session_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['workflow_collaboration_sessions.session_id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_collaboration_audit_workflow', 'collaboration_audit', ['workflow_id'])
    op.create_index('ix_collaboration_audit_user', 'collaboration_audit', ['user_id', 'created_at'])
    op.create_index('ix_collaboration_audit_action', 'collaboration_audit', ['action_type', 'created_at'])


def downgrade() -> None:
    """Downgrade schema."""

    # Drop tables in reverse order of creation
    op.drop_index('ix_collaboration_audit_action', table_name='collaboration_audit')
    op.drop_index('ix_collaboration_audit_user', table_name='collaboration_audit')
    op.drop_index('ix_collaboration_audit_workflow', table_name='collaboration_audit')
    op.drop_table('collaboration_audit')

    op.drop_index('ix_collaboration_comments_resolved', table_name='collaboration_comments')
    op.drop_index('ix_collaboration_comments_thread', table_name='collaboration_comments')
    op.drop_index('ix_collaboration_comments_context', table_name='collaboration_comments')
    op.drop_index('ix_collaboration_comments_workflow', table_name='collaboration_comments')
    op.drop_table('collaboration_comments')

    op.drop_index('ix_workflow_shares_expires', table_name='workflow_shares')
    op.drop_index('ix_workflow_shares_workflow', table_name='workflow_shares')
    op.drop_table('workflow_shares')

    op.drop_index('ix_edit_locks_expiry', table_name='edit_locks')
    op.drop_index('ix_edit_locks_resource', table_name='edit_locks')
    op.drop_index('ix_edit_locks_workflow', table_name='edit_locks')
    op.drop_table('edit_locks')

    op.drop_index('ix_collaboration_participants_heartbeat', table_name='collaboration_session_participants')
    op.drop_index('ix_collaboration_participants_session_user', table_name='collaboration_session_participants')
    op.drop_table('collaboration_session_participants')

    op.drop_index('ix_workflow_collaboration_sessions_active', table_name='workflow_collaboration_sessions')
    op.drop_index('ix_workflow_collaboration_sessions_created_by', table_name='workflow_collaboration_sessions')
    op.drop_index('ix_workflow_collaboration_sessions_workflow', table_name='workflow_collaboration_sessions')
    op.drop_table('workflow_collaboration_sessions')
