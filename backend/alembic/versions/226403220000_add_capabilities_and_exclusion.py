"""add capabilities and exclusion columns

Revision ID: 226403220000
Revises: 226103220000
Create Date: 2026-03-22 23:55:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite


# revision identifiers, used by Alembic.
revision = '226403220000'
down_revision = '226103220000'
branch_labels = None
depends_on = None


def upgrade():
    # Check if columns exist (SQLite limitation handling)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('model_catalog')]

    # Add capabilities column if it doesn't exist
    if 'capabilities' not in columns:
        op.add_column(
            'model_catalog',
            sa.Column('capabilities', sa.JSON(), nullable=True)
        )

    # Add exclude_from_general_routing column if it doesn't exist
    if 'exclude_from_general_routing' not in columns:
        op.add_column(
            'model_catalog',
            sa.Column('exclude_from_general_routing', sa.Boolean(), nullable=True, server_default='0')
        )

    # Update existing records with default values
    op.execute("""
        UPDATE model_catalog
        SET capabilities = '["chat"]'
        WHERE capabilities IS NULL
    """)

    op.execute("""
        UPDATE model_catalog
        SET exclude_from_general_routing = 0
        WHERE exclude_from_general_routing IS NULL
    """)

    # Create index on exclude_from_general_routing for filtering performance
    try:
        op.create_index(
            'ix_model_catalog_exclude_from_general_routing',
            'model_catalog',
            ['exclude_from_general_routing']
        )
    except Exception:
        pass  # Index may already exist


def downgrade():
    op.drop_index('ix_model_catalog_exclude_from_general_routing', table_name='model_catalog')
    op.drop_column('model_catalog', 'exclude_from_general_routing')
    op.drop_column('model_catalog', 'capabilities')
