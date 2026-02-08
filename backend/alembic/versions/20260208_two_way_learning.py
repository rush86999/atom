"""Two-Way Learning System

Add models for supervisor performance tracking, feedback, and learning.

Revision ID: 20260208_two_way_learning
Revises: 20260207_supervision_learning
Create Date: 2026-02-08

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260208_two_way_learning'
down_revision = '20260207_supervision_learning'
branch_labels = None
depends_on = None


def upgrade():
    """Create tables for two-way learning system."""

    # ========================================================================
    # Supervisor Ratings Table
    # ========================================================================
    op.create_table(
        'supervisor_ratings',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('supervision_session_id', sa.String(), nullable=False),
        sa.Column('supervisor_id', sa.String(), nullable=False),
        sa.Column('rater_id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('rating_category', sa.String(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('was_helpful', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['supervision_session_id'], ['supervision_sessions.id'], name='fk_supervisor_ratings_session_supervision_sessions'),
        sa.ForeignKeyConstraint(['supervisor_id'], ['users.id'], name='fk_supervisor_ratings_supervisor_users'),
        sa.ForeignKeyConstraint(['rater_id'], ['users.id'], name='fk_supervisor_ratings_rater_users'),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_registry.id'], name='fk_supervisor_ratings_agent_agent_registry'),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for supervisor_ratings
    op.create_index('ix_supervisor_ratings_session', 'supervisor_ratings', ['supervision_session_id'])
    op.create_index('ix_supervisor_ratings_supervisor', 'supervisor_ratings', ['supervisor_id'])
    op.create_index('ix_supervisor_ratings_rater', 'supervisor_ratings', ['rater_id'])
    op.create_index('ix_supervisor_ratings_created', 'supervisor_ratings', ['created_at'])

    # ========================================================================
    # Supervisor Comments Table (Threaded)
    # ========================================================================
    op.create_table(
        'supervisor_comments',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('supervision_session_id', sa.String(), nullable=False),
        sa.Column('author_id', sa.String(), nullable=False),
        sa.Column('parent_comment_id', sa.String(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_type', sa.String(), server_default='text'),
        sa.Column('comment_type', sa.String(), nullable=True),
        sa.Column('intervention_reference', sa.JSON(), nullable=True),
        sa.Column('thread_path', sa.String(), nullable=True),
        sa.Column('depth', sa.Integer(), server_default='0'),
        sa.Column('reply_count', sa.Integer(), server_default='0'),
        sa.Column('upvote_count', sa.Integer(), server_default='0'),
        sa.Column('downvote_count', sa.Integer(), server_default='0'),
        sa.Column('is_edited', sa.Boolean(), server_default='0'),
        sa.Column('is_resolved', sa.Boolean(), server_default='0'),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['supervision_session_id'], ['supervision_sessions.id'], name='fk_supervisor_comments_session_supervision_sessions'),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], name='fk_supervisor_comments_author_users'),
        sa.ForeignKeyConstraint(['parent_comment_id'], ['supervisor_comments.id'], name='fk_supervisor_comments_parent_supervisor_comments'),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for supervisor_comments
    op.create_index('ix_supervisor_comments_session', 'supervisor_comments', ['supervision_session_id'])
    op.create_index('ix_supervisor_comments_author', 'supervisor_comments', ['author_id'])
    op.create_index('ix_supervisor_comments_parent', 'supervisor_comments', ['parent_comment_id'])
    op.create_index('ix_supervisor_comments_thread', 'supervisor_comments', ['thread_path'])
    op.create_index('ix_supervisor_comments_created', 'supervisor_comments', ['created_at'])

    # ========================================================================
    # Feedback Votes Table (Thumbs Up/Down)
    # ========================================================================
    op.create_table(
        'feedback_votes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('supervision_session_id', sa.String(), nullable=True),
        sa.Column('comment_id', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('vote_type', sa.String(), nullable=False),  # 'up', 'down'
        sa.Column('vote_reason', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['supervision_session_id'], ['supervision_sessions.id'], name='fk_feedback_votes_session_supervision_sessions'),
        sa.ForeignKeyConstraint(['comment_id'], ['supervisor_comments.id'], name='fk_feedback_votes_comment_supervisor_comments'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_feedback_votes_user_users'),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for feedback_votes
    op.create_index('ix_feedback_votes_session', 'feedback_votes', ['supervision_session_id'])
    op.create_index('ix_feedback_votes_comment', 'feedback_votes', ['comment_id'])
    op.create_index('ix_feedback_votes_user', 'feedback_votes', ['user_id'])
    op.create_index('ix_feedback_votes_created', 'feedback_votes', ['created_at'])

    # Unique constraints (one vote per user per target)
    op.create_index('ix_feedback_votes_unique_session', 'feedback_votes', ['supervision_session_id', 'user_id'], unique=True)
    op.create_index('ix_feedback_votes_unique_comment', 'feedback_votes', ['comment_id', 'user_id'], unique=True)

    # ========================================================================
    # Supervisor Performance Table
    # ========================================================================
    op.create_table(
        'supervisor_performance',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('supervisor_id', sa.String(), nullable=False),
        sa.Column('total_sessions_supervised', sa.Integer(), server_default='0'),
        sa.Column('total_interventions', sa.Integer(), server_default='0'),
        sa.Column('average_rating', sa.Float(), server_default='0.0'),
        sa.Column('total_ratings', sa.Integer(), server_default='0'),
        sa.Column('rating_1_count', sa.Integer(), server_default='0'),
        sa.Column('rating_2_count', sa.Integer(), server_default='0'),
        sa.Column('rating_3_count', sa.Integer(), server_default='0'),
        sa.Column('rating_4_count', sa.Integer(), server_default='0'),
        sa.Column('rating_5_count', sa.Integer(), server_default='0'),
        sa.Column('successful_interventions', sa.Integer(), server_default='0'),
        sa.Column('failed_interventions', sa.Integer(), server_default='0'),
        sa.Column('agents_promoted', sa.Integer(), server_default='0'),
        sa.Column('agent_confidence_boosted', sa.Float(), server_default='0.0'),
        sa.Column('total_comments_given', sa.Integer(), server_default='0'),
        sa.Column('total_upvotes_received', sa.Integer(), server_default='0'),
        sa.Column('total_downvotes_received', sa.Integer(), server_default='0'),
        sa.Column('confidence_score', sa.Float(), server_default='0.5'),
        sa.Column('competence_level', sa.String(), server_default='novice'),
        sa.Column('learning_rate', sa.Float(), server_default='0.0'),
        sa.Column('performance_trend', sa.String(), server_default='stable'),
        sa.Column('last_updated', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['supervisor_id'], ['users.id'], name='fk_supervisor_performance_supervisor_users'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('supervisor_id')
    )

    # Indexes for supervisor_performance
    op.create_index('ix_supervisor_performance_supervisor', 'supervisor_performance', ['supervisor_id'])
    op.create_index('ix_supervisor_performance_rating', 'supervisor_performance', ['average_rating'])
    op.create_index('ix_supervisor_performance_confidence', 'supervisor_performance', ['confidence_score'])

    # ========================================================================
    # Intervention Outcomes Table
    # ========================================================================
    op.create_table(
        'intervention_outcomes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('supervision_session_id', sa.String(), nullable=False),
        sa.Column('supervisor_id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=False),
        sa.Column('intervention_type', sa.String(), nullable=False),
        sa.Column('intervention_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('outcome', sa.String(), nullable=False),
        sa.Column('agent_behavior_change', sa.String(), nullable=True),
        sa.Column('task_completion', sa.String(), nullable=True),
        sa.Column('seconds_to_recovery', sa.Integer(), nullable=True),
        sa.Column('was_necessary', sa.Boolean(), server_default='0'),
        sa.Column('was_effective', sa.Boolean(), server_default='1'),
        sa.Column('would_recommend', sa.Boolean(), nullable=True),
        sa.Column('lesson_learned', sa.Text(), nullable=True),
        sa.Column('confidence_change', sa.Float(), server_default='0.0'),
        sa.Column('assessed_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['supervision_session_id'], ['supervision_sessions.id'], name='fk_intervention_outcomes_session_supervision_sessions'),
        sa.ForeignKeyConstraint(['supervisor_id'], ['users.id'], name='fk_intervention_outcomes_supervisor_users'),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_registry.id'], name='fk_intervention_outcomes_agent_agent_registry'),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for intervention_outcomes
    op.create_index('ix_intervention_outcomes_session', 'intervention_outcomes', ['supervision_session_id'])
    op.create_index('ix_intervention_outcomes_supervisor', 'intervention_outcomes', ['supervisor_id'])
    op.create_index('ix_intervention_outcomes_agent', 'intervention_outcomes', ['agent_id'])
    op.create_index('ix_intervention_outcomes_type', 'intervention_outcomes', ['intervention_type'])
    op.create_index('ix_intervention_outcomes_outcome', 'intervention_outcomes', ['outcome'])
    op.create_index('ix_intervention_outcomes_assessed', 'intervention_outcomes', ['assessed_at'])


def downgrade():
    """Drop two-way learning system tables."""

    # Drop tables in reverse order
    op.drop_table('intervention_outcomes')
    op.drop_table('supervisor_performance')
    op.drop_table('feedback_votes')
    op.drop_table('supervisor_comments')
    op.drop_table('supervisor_ratings')
