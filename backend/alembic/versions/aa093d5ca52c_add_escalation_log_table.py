"""add escalation log table

Revision ID: aa093d5ca52c
Revises: 20260220_cognitive_tier
Create Date: 2026-02-20 12:39:53.426754

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa093d5ca52c'
down_revision: Union[str, Sequence[str], None] = '20260220_cognitive_tier'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create escalation_log table."""
    op.create_table(
        'escalation_log',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('request_id', sa.String(), nullable=False),
        sa.Column('from_tier', sa.String(), nullable=False),
        sa.Column('to_tier', sa.String(), nullable=False),
        sa.Column('reason', sa.String(), nullable=False),
        sa.Column('trigger_value', sa.Float(), nullable=True),
        sa.Column('provider_id', sa.String(), nullable=True),
        sa.Column('model', sa.String(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('prompt_length', sa.Integer(), nullable=True),
        sa.Column('estimated_tokens', sa.Integer(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_escalation_log_workspace_id', 'escalation_log', ['workspace_id'])
    op.create_index('ix_escalation_log_request_id', 'escalation_log', ['request_id'])


def downgrade() -> None:
    """Downgrade schema - drop escalation_log table."""
    op.drop_index('ix_escalation_log_request_id', table_name='escalation_log')
    op.drop_index('ix_escalation_log_workspace_id', table_name='escalation_log')
    op.drop_table('escalation_log')
