"""add nullable columns for agent_registry and hitlaction

This migration adds missing nullable columns to support new features:
- agent_registry: display_name, handle (for personalized agent names and @mentions)
- hitl_actions: chain_id (for delegation chain association)

All columns are added as nullable to ensure backward compatibility with existing data.
Existing records will have NULL values for these columns.

Revision ID: e186393951b0
Revises:
Create Date: 2026-04-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e186393951b0'
down_revision = None  # Standalone migration to avoid broken chain issues
branch_labels = None
depends_on = None


def upgrade():
    # Add display_name to agent_registry (for personalized agent names like "Alex", "Grace")
    with op.batch_alter_table('agent_registry', schema=None) as batch_op:
        batch_op.add_column(sa.Column('display_name', sa.String(), nullable=True))

    # Add handle to agent_registry (for @mentions like "@alex")
    with op.batch_alter_table('agent_registry', schema=None) as batch_op:
        batch_op.add_column(sa.Column('handle', sa.String(), nullable=True))

    # Create index on handle for faster @mention lookups
    with op.batch_alter_table('agent_registry', schema=None) as batch_op:
        batch_op.create_index('ix_agent_registry_handle', ['handle'], unique=False)

    # Add chain_id to hitl_actions (for delegation chain association)
    with op.batch_alter_table('hitl_actions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('chain_id', sa.String(), nullable=True))

    # Create index on chain_id for faster chain lookups
    with op.batch_alter_table('hitl_actions', schema=None) as batch_op:
        batch_op.create_index('ix_hitl_actions_chain_id', ['chain_id'], unique=False)


def downgrade():
    # Remove indexes first
    with op.batch_alter_table('hitl_actions', schema=None) as batch_op:
        batch_op.drop_index('ix_hitl_actions_chain_id')

    with op.batch_alter_table('agent_registry', schema=None) as batch_op:
        batch_op.drop_index('ix_agent_registry_handle')

    # Remove columns
    with op.batch_alter_table('hitl_actions', schema=None) as batch_op:
        batch_op.drop_column('chain_id')

    with op.batch_alter_table('agent_registry', schema=None) as batch_op:
        batch_op.drop_column('handle')

    with op.batch_alter_table('agent_registry', schema=None) as batch_op:
        batch_op.drop_column('display_name')
