"""Add marketplace cache and rating models

Revision ID: d99e23d1bd3f
Revises: 20260219_python_package
Create Date: 2026-02-19 16:09:31.057412

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd99e23d1bd3f'
down_revision: Union[str, Sequence[str], None] = '20260219_python_package'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
