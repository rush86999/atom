"""Add deep_link_audit table

Revision ID: 158137b9c8b6
Revises: 3552e6844c1d
Create Date: 2026-02-01 09:42:45.515800

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '158137b9c8b6'
down_revision: Union[str, Sequence[str], None] = '3552e6844c1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create deep_link_audit table
    op.create_table(
        'deep_link_audit',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=True),
        sa.Column('agent_id', sa.String(), nullable=True),
        sa.Column('agent_execution_id', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=False),
        sa.Column('resource_id', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('deeplink_url', sa.Text(), nullable=False),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('governance_check_passed', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_registry.id'], ),
        sa.ForeignKeyConstraint(['agent_execution_id'], ['agent_executions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for common queries
    op.create_index(op.f('ix_deep_link_audit_agent_id'), 'deep_link_audit', ['agent_id'], unique=False)
    op.create_index(op.f('ix_deep_link_audit_agent_execution_id'), 'deep_link_audit', ['agent_execution_id'], unique=False)
    op.create_index(op.f('ix_deep_link_audit_user_id'), 'deep_link_audit', ['user_id'], unique=False)
    op.create_index(op.f('ix_deep_link_audit_created_at'), 'deep_link_audit', ['created_at'], unique=False)
    op.create_index(op.f('ix_deep_link_audit_workspace_id'), 'deep_link_audit', ['workspace_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index(op.f('ix_deep_link_audit_workspace_id'), table_name='deep_link_audit')
    op.drop_index(op.f('ix_deep_link_audit_created_at'), table_name='deep_link_audit')
    op.drop_index(op.f('ix_deep_link_audit_user_id'), table_name='deep_link_audit')
    op.drop_index(op.f('ix_deep_link_audit_agent_execution_id'), table_name='deep_link_audit')
    op.drop_index(op.f('ix_deep_link_audit_agent_id'), table_name='deep_link_audit')

    # Drop table
    op.drop_table('deep_link_audit')
