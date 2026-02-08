"""Add dashboard and dashboard widget models

Revision ID: 827e2dc33702
Revises: 7a5c1de9f19f
Create Date: 2026-02-02 20:36:48.133560

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '827e2dc33702'
down_revision: Union[str, Sequence[str], None] = '7a5c1de9f19f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create dashboards table
    op.create_table(
        'dashboards',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('owner_id', sa.String(), nullable=False),
        sa.Column('configuration', sa.JSON(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_dashboards_active', 'dashboards', ['is_active'])
    op.create_index('ix_dashboards_owner', 'dashboards', ['owner_id'])
    op.create_index('ix_dashboards_public', 'dashboards', ['is_public'])

    # Create dashboard_widgets table
    op.create_table(
        'dashboard_widgets',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('dashboard_id', sa.String(), nullable=False),
        sa.Column('widget_type', sa.String(length=50), nullable=False),
        sa.Column('widget_name', sa.String(length=255), nullable=False),
        sa.Column('data_source', sa.JSON(), nullable=True),
        sa.Column('position', sa.JSON(), nullable=True),
        sa.Column('display_config', sa.JSON(), nullable=True),
        sa.Column('refresh_interval_seconds', sa.Integer(), nullable=True, server_default='300'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['dashboard_id'], ['dashboards.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_dashboard_widgets_dashboard', 'dashboard_widgets', ['dashboard_id'])
    op.create_index('ix_dashboard_widgets_type', 'dashboard_widgets', ['widget_type'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_dashboard_widgets_type', table_name='dashboard_widgets')
    op.drop_index('ix_dashboard_widgets_dashboard', table_name='dashboard_widgets')
    op.drop_table('dashboard_widgets')

    op.drop_index('ix_dashboards_public', table_name='dashboards')
    op.drop_index('ix_dashboards_owner', table_name='dashboards')
    op.drop_index('ix_dashboards_active', table_name='dashboards')
    op.drop_table('dashboards')
