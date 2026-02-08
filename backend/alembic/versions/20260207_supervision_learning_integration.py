"""Supervision Learning Integration

Add supervision and proposal linkage columns to episodes table for
continuous learning from supervision experiences.

Revision ID: 20260207_supervision_learning
Revises: 20260207_multi_level_supervision
Create Date: 2026-02-07

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260207_supervision_learning'
down_revision = '20260207_multi_level_supervision'
branch_labels = None
depends_on = None


def upgrade():
    """Add supervision and proposal columns to episodes table."""

    # ========================================================================
    # Add Supervision Linkage Columns
    # ========================================================================

    # Supervisor linkage
    op.add_column('episodes', sa.Column('supervisor_id', sa.String(), nullable=True))
    op.add_column('episodes', sa.Column('supervisor_rating', sa.Integer(), nullable=True))
    op.add_column('episodes', sa.Column('supervision_feedback', sa.Text(), nullable=True))
    op.add_column('episodes', sa.Column('intervention_count', sa.Integer(), server_default='0'))
    op.add_column('episodes', sa.Column('intervention_types', sa.JSON(), nullable=True))

    # Proposal linkage
    op.add_column('episodes', sa.Column('proposal_id', sa.String(), nullable=True))
    op.add_column('episodes', sa.Column('proposal_outcome', sa.String(), nullable=True))
    op.add_column('episodes', sa.Column('rejection_reason', sa.Text(), nullable=True))

    # ========================================================================
    # Create Indexes for Performance
    # ========================================================================

    # Supervision indexes
    op.create_index('ix_episodes_supervisor_id', 'episodes', ['supervisor_id'])
    op.create_index('ix_episodes_supervisor_rating', 'episodes', ['supervisor_rating'])

    # Proposal index
    op.create_index('ix_episodes_proposal_id', 'episodes', ['proposal_id'])

    # Foreign key constraints
    op.create_foreign_key(
        'fk_episodes_supervisor_id_users',
        'episodes', 'users',
        ['supervisor_id'], ['id'],
        ondelete='SET NULL'
    )

    op.create_foreign_key(
        'fk_episodes_proposal_id_agent_proposals',
        'episodes', 'agent_proposals',
        ['proposal_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade():
    """Remove supervision and proposal columns from episodes table."""

    # Drop foreign keys
    op.drop_constraint('fk_episodes_proposal_id_agent_proposals', 'episodes', type_='foreignkey')
    op.drop_constraint('fk_episodes_supervisor_id_users', 'episodes', type_='foreignkey')

    # Drop indexes
    op.drop_index('ix_episodes_proposal_id', table_name='episodes')
    op.drop_index('ix_episodes_supervisor_rating', table_name='episodes')
    op.drop_index('ix_episodes_supervisor_id', table_name='episodes')

    # Drop columns
    op.drop_column('episodes', 'rejection_reason')
    op.drop_column('episodes', 'proposal_outcome')
    op.drop_column('episodes', 'proposal_id')
    op.drop_column('episodes', 'intervention_types')
    op.drop_column('episodes', 'intervention_count')
    op.drop_column('episodes', 'supervision_feedback')
    op.drop_column('episodes', 'supervisor_rating')
    op.drop_column('episodes', 'supervisor_id')
