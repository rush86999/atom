"""merge heads for social media, financial, menubar audit tables

Revision ID: da88b7d00bf2
Revises: 20260204_messaging_perf, 20260205_add_job_id, 20260205_menubar_integration
Create Date: 2026-02-06 17:15:41.924332

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'da88b7d00bf2'
down_revision: Union[str, Sequence[str], None] = ('20260204_messaging_perf', '20260205_add_job_id', '20260205_menubar_integration')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
