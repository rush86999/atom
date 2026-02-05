"""merge heads for token encryption

Revision ID: 23ebe84c54bd
Revises: 1770165004, d1e2f3g4h5i6
Create Date: 2026-02-03 20:53:54.123944

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '23ebe84c54bd'
down_revision: Union[str, Sequence[str], None] = ('1770165004', 'd1e2f3g4h5i6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
