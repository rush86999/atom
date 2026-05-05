"""stabilize_schema_discovery_pipeline

Revision ID: 0936cb8bc790
Revises: 20260505_add_discovered_entities
Create Date: 2026-05-05 18:09:02.349348

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0936cb8bc790'
down_revision: Union[str, Sequence[str], None] = '20260505_add_discovered_entities'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add entity_type_id to discovered_entities
    op.add_column('discovered_entities', sa.Column('entity_type_id', sa.String(), nullable=True))
    op.create_foreign_key('fk_discovered_entities_entity_type', 'discovered_entities', 'entity_type_definitions', ['entity_type_id'], ['id'])
    op.create_index('ix_discovered_entities_entity_type_id', 'discovered_entities', ['entity_type_id'])

    # Add metadata_json to entity_type_definitions
    op.add_column('entity_type_definitions', sa.Column('metadata_json', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove metadata_json from entity_type_definitions
    op.drop_column('entity_type_definitions', 'metadata_json')

    # Remove entity_type_id from discovered_entities
    op.drop_index('ix_discovered_entities_entity_type_id', table_name='discovered_entities')
    op.drop_constraint('fk_discovered_entities_entity_type', 'discovered_entities', type_='foreignkey')
    op.drop_column('discovered_entities', 'entity_type_id')
