"""add LLM OAuth credentials table

Revision ID: 20260426_llm_oauth
Revises: 20260220_cognitive_tier
Create Date: 2026-04-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260426_llm_oauth'
down_revision: Union[str, Sequence[str], None] = '20260220_cognitive_tier'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create llm_oauth_credentials table for OAuth token storage."""

    op.create_table(
        'llm_oauth_credentials',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('provider_id', sa.String(50), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_type', sa.String(20), nullable=True),
        sa.Column('scope', sa.String(500), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('refresh_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('account_email', sa.String(255), nullable=True),
        sa.Column('account_name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('last_validated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for performance
    op.create_index('idx_llm_oauth_user_provider', 'llm_oauth_credentials', ['user_id', 'provider_id'])
    op.create_index('idx_llm_oauth_tenant_provider', 'llm_oauth_credentials', ['tenant_id', 'provider_id'])
    op.create_index('idx_llm_oauth_is_active', 'llm_oauth_credentials', ['is_active'])
    op.create_index('idx_llm_oauth_credentials_user_id', 'llm_oauth_credentials', ['user_id'])
    op.create_index('idx_llm_oauth_credentials_tenant_id', 'llm_oauth_credentials', ['tenant_id'])
    op.create_index('idx_llm_oauth_credentials_provider_id', 'llm_oauth_credentials', ['provider_id'])


def downgrade() -> None:
    """Drop llm_oauth_credentials table and indexes."""

    op.drop_index('idx_llm_oauth_credentials_provider_id', table_name='llm_oauth_credentials')
    op.drop_index('idx_llm_oauth_credentials_tenant_id', table_name='llm_oauth_credentials')
    op.drop_index('idx_llm_oauth_credentials_user_id', table_name='llm_oauth_credentials')
    op.drop_index('idx_llm_oauth_is_active', table_name='llm_oauth_credentials')
    op.drop_index('idx_llm_oauth_tenant_provider', table_name='llm_oauth_credentials')
    op.drop_index('idx_llm_oauth_user_provider', table_name='llm_oauth_credentials')
    op.drop_table('llm_oauth_credentials')
