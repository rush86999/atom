"""Complete Learning and Analysis Implementations

Add database models for learning plans, competitor analysis, project health history,
and risk predictions. This completes the incomplete implementations in the codebase.

Revision ID: 20260207_complete_learning_analysis
Revises: 20260206_add_debug_system
Create Date: 2026-02-07

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260207_complete_learning_analysis'
down_revision = '20260206_add_debug_system'
branch_labels = None
depends_on = None


def upgrade():
    """Create all learning and analysis tables."""

    # ========================================================================
    # Learning Plans Table
    # ========================================================================
    op.create_table(
        'learning_plans',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('topic', sa.String(), nullable=False),
        sa.Column('current_skill_level', sa.String(), nullable=False),
        sa.Column('target_skill_level', sa.String(), nullable=False),
        sa.Column('duration_weeks', sa.Integer(), nullable=False),
        sa.Column('modules', sa.JSON(), nullable=False),
        sa.Column('milestones', sa.JSON(), nullable=False),
        sa.Column('assessment_criteria', sa.JSON(), nullable=False),
        sa.Column('progress', sa.JSON(), nullable=True),
        sa.Column('notion_database_id', sa.String(), nullable=True),
        sa.Column('notion_page_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_learning_plans_user_id_users')),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for learning_plans
    op.create_index('ix_learning_plans_user_id', 'learning_plans', ['user_id'])
    op.create_index('ix_learning_plans_created_at', 'learning_plans', ['created_at'])
    op.create_index('ix_learning_plans_user_created', 'learning_plans', ['user_id', 'created_at'])

    # ========================================================================
    # Competitor Analyses Table
    # ========================================================================
    op.create_table(
        'competitor_analyses',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('competitors', sa.JSON(), nullable=False),
        sa.Column('analysis_depth', sa.String(), nullable=False),
        sa.Column('focus_areas', sa.JSON(), nullable=False),
        sa.Column('insights', sa.JSON(), nullable=False),
        sa.Column('comparison_matrix', sa.JSON(), nullable=False),
        sa.Column('recommendations', sa.JSON(), nullable=False),
        sa.Column('notion_database_id', sa.String(), nullable=True),
        sa.Column('notion_page_id', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('cache_expiry', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_competitor_analyses_user_id_users')),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for competitor_analyses
    op.create_index('ix_competitor_analyses_user_id', 'competitor_analyses', ['user_id'])
    op.create_index('ix_competitor_analyses_created_at', 'competitor_analyses', ['created_at'])
    op.create_index('ix_competitor_analyses_cache_expiry', 'competitor_analyses', ['cache_expiry'])
    op.create_index('ix_competitor_analyses_user_created', 'competitor_analyses', ['user_id', 'created_at'])

    # ========================================================================
    # Project Health History Table
    # ========================================================================
    op.create_table(
        'project_health_history',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('check_id', sa.String(), nullable=False),
        sa.Column('overall_score', sa.Float(), nullable=False),
        sa.Column('overall_status', sa.String(), nullable=False),
        sa.Column('metrics', sa.JSON(), nullable=False),
        sa.Column('time_range_days', sa.Integer(), nullable=False),
        sa.Column('checked_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_project_health_history_user_id_users')),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for project_health_history
    op.create_index('ix_project_health_history_user_id', 'project_health_history', ['user_id'])
    op.create_index('ix_project_health_history_checked_at', 'project_health_history', ['checked_at'])
    op.create_index('ix_project_health_history_check_id', 'project_health_history', ['check_id'])
    op.create_index('ix_project_health_history_user_checked', 'project_health_history', ['user_id', 'checked_at'])

    # ========================================================================
    # Customer Churn Predictions Table
    # ========================================================================
    op.create_table(
        'customer_churn_predictions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('customer_id', sa.String(), nullable=False),
        sa.Column('customer_name', sa.String(), nullable=False),
        sa.Column('churn_probability', sa.Float(), nullable=False),
        sa.Column('risk_factors', sa.JSON(), nullable=False),
        sa.Column('mrr_at_risk', sa.Float(), nullable=False),
        sa.Column('recommended_action', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for customer_churn_predictions
    op.create_index('ix_customer_churn_predictions_workspace_id', 'customer_churn_predictions', ['workspace_id'])
    op.create_index('ix_customer_churn_predictions_created_at', 'customer_churn_predictions', ['created_at'])
    op.create_index('ix_customer_churn_predictions_churn_probability', 'customer_churn_predictions', ['churn_probability'])
    op.create_index('ix_churn_predictions_workspace_created', 'customer_churn_predictions', ['workspace_id', 'created_at'])

    # ========================================================================
    # AR Delay Predictions Table
    # ========================================================================
    op.create_table(
        'ar_delay_predictions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('invoice_id', sa.String(), nullable=False),
        sa.Column('client_name', sa.String(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('due_date', sa.DateTime(), nullable=False),
        sa.Column('likelihood_late', sa.Float(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for ar_delay_predictions
    op.create_index('ix_ar_delay_predictions_workspace_id', 'ar_delay_predictions', ['workspace_id'])
    op.create_index('ix_ar_delay_predictions_created_at', 'ar_delay_predictions', ['created_at'])
    op.create_index('ix_ar_delay_predictions_due_date', 'ar_delay_predictions', ['due_date'])
    op.create_index('ix_ar_predictions_workspace_created', 'ar_delay_predictions', ['workspace_id', 'created_at'])


def downgrade():
    """Drop all learning and analysis tables."""

    # Drop tables in reverse order of creation
    op.drop_index('ix_ar_predictions_workspace_created', table_name='ar_delay_predictions')
    op.drop_index('ix_ar_delay_predictions_due_date', table_name='ar_delay_predictions')
    op.drop_index('ix_ar_delay_predictions_created_at', table_name='ar_delay_predictions')
    op.drop_index('ix_ar_delay_predictions_workspace_id', table_name='ar_delay_predictions')
    op.drop_table('ar_delay_predictions')

    op.drop_index('ix_churn_predictions_workspace_created', table_name='customer_churn_predictions')
    op.drop_index('ix_customer_churn_predictions_churn_probability', table_name='customer_churn_predictions')
    op.drop_index('ix_customer_churn_predictions_created_at', table_name='customer_churn_predictions')
    op.drop_index('ix_customer_churn_predictions_workspace_id', table_name='customer_churn_predictions')
    op.drop_table('customer_churn_predictions')

    op.drop_index('ix_project_health_history_user_checked', table_name='project_health_history')
    op.drop_index('ix_project_health_history_check_id', table_name='project_health_history')
    op.drop_index('ix_project_health_history_checked_at', table_name='project_health_history')
    op.drop_index('ix_project_health_history_user_id', table_name='project_health_history')
    op.drop_table('project_health_history')

    op.drop_index('ix_competitor_analyses_user_created', table_name='competitor_analyses')
    op.drop_index('ix_competitor_analyses_cache_expiry', table_name='competitor_analyses')
    op.drop_index('ix_competitor_analyses_created_at', table_name='competitor_analyses')
    op.drop_index('ix_competitor_analyses_user_id', table_name='competitor_analyses')
    op.drop_table('competitor_analyses')

    op.drop_index('ix_learning_plans_user_created', table_name='learning_plans')
    op.drop_index('ix_learning_plans_created_at', table_name='learning_plans')
    op.drop_index('ix_learning_plans_user_id', table_name='learning_plans')
    op.drop_table('learning_plans')
