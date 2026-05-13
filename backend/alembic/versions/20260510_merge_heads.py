"""merge divergent heads

Revision ID: atom_merge_20260510
Revises: 0936cb8bc790, 20260218_add_canvas, a3f2d1e0b9c8, 20260219_python_package, 20260425_add_template_component_tables, 3a1b2c3d4e5f, b5370fc53623
Create Date: 2026-05-10 13:13:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'atom_merge_20260510'
down_revision: Union[str, Sequence[str], None] = ('0936cb8bc790', '20260218_add_canvas', 'a3f2d1e0b9c8', '20260219_python_package', '20260425_add_template_component_tables', '3a1b2c3d4e5f', 'b5370fc53623')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
