"""add notion oauth token model

Revision ID: bcf9c8a7a85c
Revises:
Create Date: 2026-02-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = 'bcf9c8a7a85c'
down_revision = 'g1h2i3j4k5l6'  # Based on device capability models
branch_labels = None
depends_on = None


def upgrade():
    # Create notion_tokens table
    op.create_table(
        'notion_tokens',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=True),
        sa.Column('access_token', sa.String(), nullable=False),
        sa.Column('refresh_token', sa.String(), nullable=True),
        sa.Column('notion_user_id', sa.String(), nullable=True),
        sa.Column('workspace_name', sa.String(), nullable=True),
        sa.Column('workspace_icon', sa.String(), nullable=True),
        sa.Column('token_type', sa.String(), nullable=True),
        sa.Column('owner_type', sa.String(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scope', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('last_used', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index(op.f('ix_notion_tokens_id'), 'notion_tokens', ['id'], unique=False)
    op.create_index(op.f('ix_notion_tokens_user_id'), 'notion_tokens', ['user_id'], unique=False)
    op.create_index(op.f('ix_notion_tokens_workspace_id'), 'notion_tokens', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_notion_tokens_notion_user_id'), 'notion_tokens', ['notion_user_id'], unique=False)


def downgrade():
    # Drop indexes
    op.drop_index(op.f('ix_notion_tokens_notion_user_id'), table_name='notion_tokens')
    op.drop_index(op.f('ix_notion_tokens_workspace_id'), table_name='notion_tokens')
    op.drop_index(op.f('ix_notion_tokens_user_id'), table_name='notion_tokens')
    op.drop_index(op.f('ix_notion_tokens_id'), table_name='notion_tokens')

    # Drop table
    op.drop_table('notion_tokens')
