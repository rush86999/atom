"""add_custom_role_id_to_users

Revision ID: 1c42debcfabc
Revises: 20260220_smoke_test
Create Date: 2026-03-08 17:31:38.316256

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c42debcfabc'
down_revision: Union[str, Sequence[str], None] = '20260220_smoke_test'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add custom_role_id column to users table
    # First, check if custom_roles table exists (it may not in older databases)
    op.execute("""
        CREATE TABLE IF NOT EXISTS custom_roles (
            id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            description VARCHAR,
            permissions JSON,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Add custom_role_id as nullable to allow existing users to have NULL
    op.add_column('users', sa.Column('custom_role_id', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove custom_role_id from users table
    op.drop_column('users', 'custom_role_id')

    # Note: We don't drop custom_roles table in downgrade as it may have data
    # from other features. Commented out:
    # op.execute('DROP TABLE IF EXISTS custom_roles')
