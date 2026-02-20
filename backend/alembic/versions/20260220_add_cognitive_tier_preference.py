"""add cognitive tier preference table

Revision ID: 20260220_cognitive_tier
Revises: 29b7aa4918a3
Create Date: 2026-02-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260220_cognitive_tier'
down_revision: Union[str, Sequence[str], None] = '29b7aa4918a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create cognitive_tier_preferences table for per-workspace tier routing."""

    op.create_table(
        'cognitive_tier_preferences',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('default_tier', sa.String(), nullable=False),
        sa.Column('min_tier', sa.String(), nullable=True),
        sa.Column('max_tier', sa.String(), nullable=True),
        sa.Column('monthly_budget_cents', sa.Integer(), nullable=True),
        sa.Column('max_cost_per_request_cents', sa.Integer(), nullable=True),
        sa.Column('enable_cache_aware_routing', sa.Boolean(), nullable=True),
        sa.Column('enable_auto_escalation', sa.Boolean(), nullable=True),
        sa.Column('enable_minimax_fallback', sa.Boolean(), nullable=True),
        sa.Column('preferred_providers', sa.JSON(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id')
    )
    op.create_index('ix_cognitive_tier_preferences_workspace_id', 'cognitive_tier_preferences', ['workspace_id'], unique=True)


def downgrade() -> None:
    """Drop cognitive_tier_preferences table."""

    op.drop_index('ix_cognitive_tier_preferences_workspace_id', table_name='cognitive_tier_preferences')
    op.drop_table('cognitive_tier_preferences')
