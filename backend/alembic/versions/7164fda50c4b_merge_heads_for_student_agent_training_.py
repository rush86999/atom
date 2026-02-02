"""merge heads for student agent training migration

Revision ID: 7164fda50c4b
Revises: b1c2d3e4f5a6, b677f9cd6ac5
Create Date: 2026-02-02 18:13:17.739670

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7164fda50c4b'
down_revision: Union[str, Sequence[str], None] = ('b1c2d3e4f5a6', 'b677f9cd6ac5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
