"""Add agent config columns to registry

Revision ID: b78e9c2f1a3d
Revises: a13f747377c4
Create Date: 2025-12-26 21:00:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b78e9c2f1a3d'
down_revision: Union[str, Sequence[str], None] = 'a13f747377c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if columns exist (safe for both SQLite and Postgres in a migration script)
    # But standard Alembic upgrade usually just runs the command.
    # To be safe across engines, we can use batch_op for SQLite if needed, 
    # but since this is primarily for production Postgres parity:
    op.add_column('agent_registry', sa.Column('configuration', sa.JSON(), nullable=True, server_default='{}'))
    op.add_column('agent_registry', sa.Column('schedule_config', sa.JSON(), nullable=True, server_default='{}'))


def downgrade() -> None:
    op.drop_column('agent_registry', 'schedule_config')
    op.drop_column('agent_registry', 'configuration')
