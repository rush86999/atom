"""add_revoked_tokens_table

Revision ID: 2988f6733813
Revises: 827e2dc33702
Create Date: 2026-02-02 22:06:24.085355

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2988f6733813'
down_revision: Union[str, Sequence[str], None] = '827e2dc33702'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create revoked_tokens table
    op.create_table(
        'revoked_tokens',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('jti', sa.String(length=255), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('revocation_reason', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_revoked_tokens_user_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('jti', name='uq_revoked_tokens_jti')
    )

    # Create indexes for efficient lookups and cleanup
    op.create_index('ix_revoked_tokens_jti', 'revoked_tokens', ['jti'])
    op.create_index('ix_revoked_tokens_expires', 'revoked_tokens', ['expires_at'])
    op.create_index('ix_revoked_tokens_user', 'revoked_tokens', ['user_id', 'revoked_at'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('ix_revoked_tokens_user', table_name='revoked_tokens')
    op.drop_index('ix_revoked_tokens_expires', table_name='revoked_tokens')
    op.drop_index('ix_revoked_tokens_jti', table_name='revoked_tokens')

    # Drop table
    op.drop_table('revoked_tokens')
