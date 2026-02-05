"""add_stripe_token_model

Revision ID: 1c3dd6f208e3
Revises: 2988f6733813
Create Date: 2026-02-03 08:05:23.239340

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '1c3dd6f208e3'
down_revision: Union[str, Sequence[str], None] = '2988f6733813'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add stripe_tokens table."""
    op.create_table(
        'stripe_tokens',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=True),
        sa.Column('access_token', sa.String(), nullable=False),
        sa.Column('refresh_token', sa.String(), nullable=True),
        sa.Column('stripe_user_id', sa.String(), nullable=False),
        sa.Column('livemode', sa.Boolean(), nullable=True),
        sa.Column('token_type', sa.String(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scope', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('last_used', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_stripe_tokens_user_id'), 'stripe_tokens', ['user_id'], unique=False)
    op.create_index(op.f('ix_stripe_tokens_stripe_user_id'), 'stripe_tokens', ['stripe_user_id'], unique=False)
    op.create_index(op.f('ix_stripe_tokens_workspace_id'), 'stripe_tokens', ['workspace_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema - Remove stripe_tokens table."""
    op.drop_index(op.f('ix_stripe_tokens_workspace_id'), table_name='stripe_tokens')
    op.drop_index(op.f('ix_stripe_tokens_stripe_user_id'), table_name='stripe_tokens')
    op.drop_index(op.f('ix_stripe_tokens_user_id'), table_name='stripe_tokens')
    op.drop_table('stripe_tokens')
