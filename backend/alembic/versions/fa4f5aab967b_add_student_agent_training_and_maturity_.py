"""add student agent training and maturity routing models

Revision ID: fa4f5aab967b
Revises: 7164fda50c4b
Create Date: 2026-02-02 18:13:23.236165

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'fa4f5aab967b'
down_revision: Union[str, Sequence[str], None] = '7164fda50c4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create BlockedTriggerContext table
    op.create_table(
        'blocked_triggers',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=False),
        sa.Column('agent_name', sa.String(), nullable=False),
        sa.Column('agent_maturity_at_block', sa.String(), nullable=False),
        sa.Column('confidence_score_at_block', sa.Float(), nullable=False),
        sa.Column('trigger_source', sa.String(), nullable=False),
        sa.Column('trigger_type', sa.String(), nullable=False),
        sa.Column('trigger_context', sa.JSON(), nullable=False),
        sa.Column('routing_decision', sa.String(), nullable=False),
        sa.Column('block_reason', sa.String(), nullable=False),
        sa.Column('proposal_id', sa.String(), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_outcome', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_registry.id']),
        sa.ForeignKeyConstraint(['proposal_id'], ['agent_proposals.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_blocked_triggers_agent', 'blocked_triggers', ['agent_id'])
    op.create_index('ix_blocked_triggers_created', 'blocked_triggers', ['created_at'])
    op.create_index('ix_blocked_triggers_maturity', 'blocked_triggers', ['agent_maturity_at_block'])
    op.create_index('ix_blocked_triggers_resolved', 'blocked_triggers', ['resolved'])
    op.create_index('ix_blocked_triggers_source', 'blocked_triggers', ['trigger_source'])

    # Create AgentProposal table
    op.create_table(
        'agent_proposals',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=False),
        sa.Column('agent_name', sa.String(), nullable=False),
        sa.Column('proposal_type', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('proposed_action', sa.JSON(), nullable=True),
        sa.Column('reasoning', sa.String(), nullable=True),
        sa.Column('learning_objectives', sa.JSON(), nullable=True),
        sa.Column('capability_gaps', sa.JSON(), nullable=True),
        sa.Column('training_scenario_template', sa.String(), nullable=True),
        sa.Column('estimated_duration_hours', sa.Float(), nullable=True),
        sa.Column('duration_estimation_confidence', sa.Float(), nullable=True),
        sa.Column('duration_estimation_reasoning', sa.String(), nullable=True),
        sa.Column('user_override_duration_hours', sa.Float(), nullable=True),
        sa.Column('hours_per_day_limit', sa.Float(), nullable=True),
        sa.Column('training_start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('training_end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(), server_default='proposed', nullable=False),
        sa.Column('proposed_by', sa.String(), nullable=False),
        sa.Column('approved_by', sa.String(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('modifications', sa.JSON(), nullable=True),
        sa.Column('execution_result', sa.JSON(), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_registry.id']),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_agent_proposals_agent', 'agent_proposals', ['agent_id'])
    op.create_index('ix_agent_proposals_approved_by', 'agent_proposals', ['approved_by'])
    op.create_index('ix_agent_proposals_created', 'agent_proposals', ['created_at'])
    op.create_index('ix_agent_proposals_proposed_by', 'agent_proposals', ['proposed_by'])
    op.create_index('ix_agent_proposals_status', 'agent_proposals', ['status'])
    op.create_index('ix_agent_proposals_type', 'agent_proposals', ['proposal_type'])

    # Create SupervisionSession table
    op.create_table(
        'supervision_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=False),
        sa.Column('agent_name', sa.String(), nullable=False),
        sa.Column('trigger_id', sa.String(), nullable=True),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('trigger_context', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(), server_default='running', nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('supervisor_id', sa.String(), nullable=False),
        sa.Column('intervention_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('interventions', sa.JSON(), server_default='[]', nullable=False),
        sa.Column('agent_actions', sa.JSON(), server_default='[]', nullable=False),
        sa.Column('outcomes', sa.JSON(), nullable=True),
        sa.Column('supervisor_rating', sa.Integer(), nullable=True),
        sa.Column('supervisor_feedback', sa.String(), nullable=True),
        sa.Column('confidence_boost', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_registry.id']),
        sa.ForeignKeyConstraint(['trigger_id'], ['blocked_triggers.id']),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.ForeignKeyConstraint(['supervisor_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_supervision_sessions_agent', 'supervision_sessions', ['agent_id'])
    op.create_index('ix_supervision_sessions_started', 'supervision_sessions', ['started_at'])
    op.create_index('ix_supervision_sessions_status', 'supervision_sessions', ['status'])
    op.create_index('ix_supervision_sessions_supervisor', 'supervision_sessions', ['supervisor_id'])
    op.create_index('ix_supervision_sessions_workspace', 'supervision_sessions', ['workspace_id'])

    # Create TrainingSession table
    op.create_table(
        'training_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('proposal_id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=False),
        sa.Column('agent_name', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('supervisor_id', sa.String(), nullable=False),
        sa.Column('supervisor_guidance', sa.JSON(), nullable=True),
        sa.Column('tasks_completed', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_tasks', sa.Integer(), nullable=True),
        sa.Column('outcomes', sa.JSON(), nullable=True),
        sa.Column('performance_score', sa.Float(), nullable=True),
        sa.Column('errors_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('supervisor_feedback', sa.String(), nullable=True),
        sa.Column('confidence_boost', sa.Float(), nullable=True),
        sa.Column('promoted_to_intern', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('capabilities_developed', sa.JSON(), nullable=True),
        sa.Column('capability_gaps_remaining', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['proposal_id'], ['agent_proposals.id']),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_registry.id']),
        sa.ForeignKeyConstraint(['supervisor_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_training_sessions_agent', 'training_sessions', ['agent_id'])
    op.create_index('ix_training_sessions_created', 'training_sessions', ['created_at'])
    op.create_index('ix_training_sessions_proposal', 'training_sessions', ['proposal_id'])
    op.create_index('ix_training_sessions_status', 'training_sessions', ['status'])
    op.create_index('ix_training_sessions_supervisor', 'training_sessions', ['supervisor_id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop in reverse order of creation
    op.drop_table('training_sessions')
    op.drop_table('supervision_sessions')
    op.drop_table('agent_proposals')
    op.drop_table('blocked_triggers')
