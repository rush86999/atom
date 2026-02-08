"""add canvas_type to canvas_audit

Revision ID: b1c2d3e4f5a6
Revises: a0ab43a0b96f
Create Date: 2026-02-02 12:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b1c2d3e4f5a6'
down_revision = 'a0ab43a0b96f'
branch_labels = None
depends_on = None


def upgrade():
    """Add canvas_type column to canvas_audit table."""
    # Add canvas_type column with default value 'generic'
    op.add_column(
        'canvas_audit',
        sa.Column('canvas_type', sa.String(), nullable=False, server_default='generic')
    )

    # Create index for canvas_type
    op.create_index(
        op.f('ix_canvas_audit_canvas_type'),
        'canvas_audit',
        ['canvas_type'],
        unique=False
    )


def downgrade():
    """Remove canvas_type column from canvas_audit table."""
    op.drop_index(op.f('ix_canvas_audit_canvas_type'), table_name='canvas_audit')
    op.drop_column('canvas_audit', 'canvas_type')
