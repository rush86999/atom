"""add token encryption to oauth_tokens

Revision ID: 1a3970744150
Revises: 23ebe84c54bd
Create Date: 2026-02-03 20:54:13.964703

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a3970744150'
down_revision: Union[str, Sequence[str], None] = '23ebe84c54bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add encrypted token columns to oauth_tokens table.

    The new columns will store Fernet-encrypted tokens.
    Existing tokens will be migrated on-the-fly when accessed via the
    hybrid property getters/setters.
    """
    # Add new encrypted columns (nullable initially for backwards compatibility)
    op.add_column('oauth_tokens', sa.Column('encrypted_access_token', sa.Text(), nullable=True))
    op.add_column('oauth_tokens', sa.Column('encrypted_refresh_token', sa.Text(), nullable=True))


def downgrade() -> None:
    """
    Remove encrypted token columns.

    WARNING: This will cause data loss if tokens have been encrypted.
    The old plaintext columns no longer exist.
    """
    op.drop_column('oauth_tokens', 'encrypted_refresh_token')
    op.drop_column('oauth_tokens', 'encrypted_access_token')
