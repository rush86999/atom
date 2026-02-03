"""add metadata_json to invoice table

Revision ID: 7a5c1de9f19f
Revises: 7d110440f4dc
Create Date: 2026-02-02 19:58:02.679729

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a5c1de9f19f'
down_revision: Union[str, Sequence[str], None] = '7d110440f4dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add metadata_json column to accounting_invoices table
    op.add_column('accounting_invoices', sa.Column('metadata_json', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove metadata_json column from accounting_invoices table
    op.drop_column('accounting_invoices', 'metadata_json')
