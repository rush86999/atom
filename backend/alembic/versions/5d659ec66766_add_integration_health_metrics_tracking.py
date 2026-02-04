"""Add integration health metrics tracking

Revision ID: 5d659ec66766
Revises: fa4f5aab967b
Create Date: 2026-02-02 19:22:21.923310

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5d659ec66766'
down_revision: Union[str, Sequence[str], None] = 'fa4f5aab967b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create integration_health_metrics table
    op.create_table(
        'integration_health_metrics',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('integration_id', sa.String(), nullable=False),
        sa.Column('connection_id', sa.String(), nullable=False),
        sa.Column('latency_ms', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('success_rate', sa.Float(), nullable=True, server_default='1.0'),
        sa.Column('error_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('request_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('health_trend', sa.String(), nullable=True, server_default='stable'),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_failure_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['connection_id'], ['user_connections.id'], ),
        sa.ForeignKeyConstraint(['integration_id'], ['integration_catalog.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_integration_health_metrics_connection_id'), 'integration_health_metrics', ['connection_id'], unique=False)
    op.create_index(op.f('ix_integration_health_metrics_integration_id'), 'integration_health_metrics', ['integration_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_integration_health_metrics_connection_id'), table_name='integration_health_metrics')
    op.drop_index(op.f('ix_integration_health_metrics_integration_id'), table_name='integration_health_metrics')
    op.drop_table('integration_health_metrics')
