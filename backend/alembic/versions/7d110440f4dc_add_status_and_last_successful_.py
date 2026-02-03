"""Add status and last_successful_connection to integration_catalog

Revision ID: 7d110440f4dc
Revises: 5d659ec66766
Create Date: 2026-02-02 19:24:29.832458

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d110440f4dc'
down_revision: Union[str, Sequence[str], None] = '5d659ec66766'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add status column to integration_catalog
    op.add_column('integration_catalog', sa.Column('status', sa.String(), nullable=True, server_default='active'))
    op.add_column('integration_catalog', sa.Column('last_successful_connection', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('integration_catalog', 'last_successful_connection')
    op.drop_column('integration_catalog', 'status')
