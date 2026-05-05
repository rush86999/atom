"""Add DiscoveredEntity table for multi-entity extraction

Revision ID: 20260505_add_discovered_entities
Revises: 20260426_llm_oauth
Create Date: 2026-05-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = '20260505_add_discovered_entities'
down_revision = '20260426_llm_oauth'
branch_labels = None
depends_on = None


def upgrade():
    # Create DiscoveredEntity table
    op.create_table(
        'discovered_entities',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('_discovered_type', sa.String(100), nullable=False, comment='LLM-discovered entity type'),
        sa.Column('properties', sa.JSON(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False, default=0.0),
        sa.Column('source_record_id', sa.String(), nullable=False),
        sa.Column('source_record_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('linked_to_graph_node_id', sa.String(), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('extraction_metadata', sa.JSON(), nullable=False, default={}),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['linked_to_graph_node_id'], ['graph_nodes.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for performance
    op.create_index('ix_discovered_entities_tenant_workspace', 'discovered_entities', ['tenant_id', 'workspace_id'])
    op.create_index('ix_discovered_entities_discovered_type', 'discovered_entities', ['_discovered_type'])
    op.create_index('ix_discovered_entities_source', 'discovered_entities', ['source_record_id', 'source_record_type'])
    op.create_index('ix_discovered_entities_status', 'discovered_entities', ['status'])
    op.create_index('ix_discovered_entities_confidence', 'discovered_entities', ['confidence_score'])

    # Note: Full-text search index is PostgreSQL-specific and would be added separately
    # CREATE INDEX ix_discovered_entities_properties_fts ON discovered_entities USING GIN(to_tsvector('english', properties::text))


def downgrade():
    # Drop indexes first
    op.drop_index('ix_discovered_entities_confidence', table_name='discovered_entities')
    op.drop_index('ix_discovered_entities_status', table_name='discovered_entities')
    op.drop_index('ix_discovered_entities_source', table_name='discovered_entities')
    op.drop_index('ix_discovered_entities_discovered_type', table_name='discovered_entities')
    op.drop_index('ix_discovered_entities_tenant_workspace', table_name='discovered_entities')

    # Drop table
    op.drop_table('discovered_entities')
