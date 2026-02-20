"""create smoke test user

Revision ID: 20260220_smoke_test
Revises: ffc5eb832d0d
Create Date: 2026-02-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from passlib.context import CryptContext

# revision identifiers, used by Alembic.
revision = '20260220_smoke_test'
down_revision = 'ffc5eb832d0d'
branch_labels = None
depends_on = None

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def upgrade() -> None:
    # Create smoke_test user with known credentials
    users_table = table('users',
        column('id', sa.String()),
        column('username', sa.String()),
        column('email', sa.String()),
        column('hashed_password', sa.String()),
        column('is_active', sa.Boolean()),
        column('is_smoke_test_user', sa.Boolean())
    )

    # Hash the password
    password = "smoke_test_password_change_in_prod"
    hashed_password = pwd_context.hash(password)

    op.execute(
        users_table.insert().values(
            id='smoke-test-user-uuid',
            username='smoke_test',
            email='smoke-test@example.com',
            hashed_password=hashed_password,
            is_active=True,
            is_smoke_test_user=True
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM users WHERE username = 'smoke_test'")
    )
