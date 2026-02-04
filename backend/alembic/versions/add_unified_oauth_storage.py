"""add unified oauth storage

This migration adds unified OAuth state and token storage for all OAuth providers.
Replaces provider-specific token tables with a single, extensible model.

Revision ID: c1d2e3f4g5h6
Revises: bcf9c8a7a85c
Create Date: 2026-02-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = 'c1d2e3f4g5h6'
down_revision = '2988f6733813'  # Merge with revoked tokens table
branch_labels = None
depends_on = None


def upgrade():
    # Create oauth_states table for CSRF protection
    op.create_table(
        'oauth_states',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('state', sa.String(), nullable=False),
        sa.Column('scopes', sa.JSON(), nullable=True),
        sa.Column('redirect_uri', sa.String(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('used', sa.Boolean(), nullable=True, server_default='0'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for oauth_states
    op.create_index(op.f('ix_oauth_states_id'), 'oauth_states', ['id'], unique=False)
    op.create_index(op.f('ix_oauth_states_user_id'), 'oauth_states', ['user_id'], unique=False)
    op.create_index(op.f('ix_oauth_states_provider'), 'oauth_states', ['provider'], unique=False)
    op.create_index(op.f('ix_oauth_states_state'), 'oauth_states', ['state'], unique=True)
    op.create_index(op.f('ix_oauth_states_used'), 'oauth_states', ['used'], unique=False)

    # Create oauth_tokens table for unified token storage
    op.create_table(
        'oauth_tokens',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_type', sa.String(), nullable=True, server_default='Bearer'),
        sa.Column('scopes', sa.JSON(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(), nullable=True, server_default='active'),
        sa.Column('last_used', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for oauth_tokens
    op.create_index(op.f('ix_oauth_tokens_id'), 'oauth_tokens', ['id'], unique=False)
    op.create_index(op.f('ix_oauth_tokens_user_id'), 'oauth_tokens', ['user_id'], unique=False)
    op.create_index(op.f('ix_oauth_tokens_provider'), 'oauth_tokens', ['provider'], unique=False)
    op.create_index(op.f('ix_oauth_tokens_status'), 'oauth_tokens', ['status'], unique=False)


def downgrade():
    # Drop oauth_tokens indexes and table
    op.drop_index(op.f('ix_oauth_tokens_status'), table_name='oauth_tokens')
    op.drop_index(op.f('ix_oauth_tokens_provider'), table_name='oauth_tokens')
    op.drop_index(op.f('ix_oauth_tokens_user_id'), table_name='oauth_tokens')
    op.drop_index(op.f('ix_oauth_tokens_id'), table_name='oauth_tokens')
    op.drop_table('oauth_tokens')

    # Drop oauth_states indexes and table
    op.drop_index(op.f('ix_oauth_states_used'), table_name='oauth_states')
    op.drop_index(op.f('ix_oauth_states_state'), table_name='oauth_states')
    op.drop_index(op.f('ix_oauth_states_provider'), table_name='oauth_states')
    op.drop_index(op.f('ix_oauth_states_user_id'), table_name='oauth_states')
    op.drop_index(op.f('ix_oauth_states_id'), table_name='oauth_states')
    op.drop_table('oauth_states')
