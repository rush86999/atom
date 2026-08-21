"""merge heads

Revision ID: c1e2a454c6e9
Revises: 20260808_documents_fts, 20260810_supervisor_comments_learning, 20260816_org_ingestion_sharing
Create Date: 2026-08-20 18:20:09.486214

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1e2a454c6e9'
down_revision: Union[str, Sequence[str], None] = ('20260808_documents_fts', '20260810_supervisor_comments_learning', '20260816_org_ingestion_sharing')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
