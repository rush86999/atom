"""add provider registry

Revision ID: 226103220000
Revises: 079c11319d8f
Create Date: 2026-03-22 21:52:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite


# revision identifiers, used by Alembic.
revision = '226103220000'
down_revision = '079c11319d8f'
branch_labels = None
depends_on = None


def upgrade():
    # Create provider_registry table
    op.create_table(
        'provider_registry',
        sa.Column('provider_id', sa.String(50), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500)),
        sa.Column('litellm_provider', sa.String(50)),
        sa.Column('base_url', sa.String(500)),
        sa.Column('supports_vision', sa.Boolean(), default=False, nullable=False),
        sa.Column('supports_tools', sa.Boolean(), default=False, nullable=False),
        sa.Column('supports_cache', sa.Boolean(), default=False, nullable=False),
        sa.Column('supports_structured_output', sa.Boolean(), default=False, nullable=False),
        sa.Column('reasoning_level', sa.Integer()),
        sa.Column('quality_score', sa.Float()),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('discovered_at', sa.DateTime()),
        sa.Column('last_updated', sa.DateTime()),
        sa.Column('provider_metadata', sa.JSON()),
    )
    op.create_index('ix_provider_registry_is_active', 'provider_registry', ['is_active'])

    # Create model_catalog table
    op.create_table(
        'model_catalog',
        sa.Column('model_id', sa.String(100), primary_key=True),
        sa.Column('provider_id', sa.String(50), sa.ForeignKey('provider_registry.provider_id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(200)),
        sa.Column('description', sa.String(500)),
        sa.Column('input_cost_per_token', sa.Float()),
        sa.Column('output_cost_per_token', sa.Float()),
        sa.Column('max_tokens', sa.Integer()),
        sa.Column('max_input_tokens', sa.Integer()),
        sa.Column('context_window', sa.Integer()),
        sa.Column('mode', sa.String(50)),
        sa.Column('source', sa.String(50)),
        sa.Column('discovered_at', sa.DateTime()),
        sa.Column('last_updated', sa.DateTime()),
        sa.Column('model_metadata', sa.JSON()),
    )
    op.create_index('ix_model_catalog_provider_id', 'model_catalog', ['provider_id'])


def downgrade():
    op.drop_index('ix_model_catalog_provider_id', table_name='model_catalog')
    op.drop_table('model_catalog')
    op.drop_index('ix_provider_registry_is_active', table_name='provider_registry')
    op.drop_table('provider_registry')
