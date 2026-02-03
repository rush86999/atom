"""merge oauth heads

This migration merges multiple head revisions from OAuth-related migrations.

Revision ID: d1e2f3g4h5i6
Revises: 1c3dd6f208e3, bcf9c8a7a85c, c1d2e3f4g5h6
Create Date: 2026-02-03

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1e2f3g4h5i6'
down_revision = ('1c3dd6f208e3', 'bcf9c8a7a85c', 'c1d2e3f4g5h6')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
