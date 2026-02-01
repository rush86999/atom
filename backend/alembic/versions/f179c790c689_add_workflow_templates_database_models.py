"""add workflow templates database models

Revision ID: f179c790c689
Revises: 69a4bf86ff15
Create Date: 2026-02-01 13:48:06.213550

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f179c790c689'
down_revision: Union[str, Sequence[str], None] = '69a4bf86ff15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create workflow_templates table
    op.create_table(
        'workflow_templates',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('template_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('complexity', sa.String(), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('author_id', sa.String(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_featured', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('template_json', sa.JSON(), nullable=False),
        sa.Column('inputs_schema', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('steps_schema', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('output_schema', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rating_sum', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rating_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('version', sa.String(), nullable=False, server_default='1.0.0'),
        sa.Column('parent_template_id', sa.String(), nullable=True),
        sa.Column('estimated_duration_seconds', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('prerequisites', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('dependencies', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('permissions', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('license', sa.String(), nullable=False, server_default='MIT'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['parent_template_id'], ['workflow_templates.template_id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('template_id')
    )
    op.create_index('ix_workflow_templates_template_id', 'workflow_templates', ['template_id'])
    op.create_index('ix_workflow_templates_author_id', 'workflow_templates', ['author_id'])
    op.create_index('ix_workflow_templates_is_public', 'workflow_templates', ['is_public'])
    op.create_index('ix_workflow_templates_is_featured', 'workflow_templates', ['is_featured'])
    op.create_index('ix_workflow_templates_created_at', 'workflow_templates', ['created_at'])
    op.create_index('ix_workflow_templates_category_complexity', 'workflow_templates', ['category', 'complexity'])
    op.create_index('ix_workflow_templates_public_featured', 'workflow_templates', ['is_public', 'is_featured'])
    op.create_index('ix_workflow_templates_author_public', 'workflow_templates', ['author_id', 'is_public'])

    # Create template_versions table
    op.create_table(
        'template_versions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('template_id', sa.String(), nullable=False),
        sa.Column('version', sa.String(), nullable=False),
        sa.Column('template_snapshot', sa.JSON(), nullable=False),
        sa.Column('change_description', sa.Text(), nullable=True),
        sa.Column('changed_by_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['changed_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['template_id'], ['workflow_templates.template_id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('template_id', 'version', name='uq_template_versions_template_version')
    )
    op.create_index('ix_template_versions_template_id', 'template_versions', ['template_id'])
    op.create_index('ix_template_versions_template_version', 'template_versions', ['template_id', 'version'], unique=True)

    # Create template_executions table
    op.create_table(
        'template_executions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('template_id', sa.String(), nullable=False),
        sa.Column('workflow_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('parameters_used', sa.JSON(), nullable=False),
        sa.Column('template_version', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['template_id'], ['workflow_templates.template_id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_template_executions_template_id', 'template_executions', ['template_id'])
    op.create_index('ix_template_executions_workflow_id', 'template_executions', ['workflow_id'])
    op.create_index('ix_template_executions_user_id', 'template_executions', ['user_id'])
    op.create_index('ix_template_executions_template_status', 'template_executions', ['template_id', 'status'])
    op.create_index('ix_template_executions_user_status', 'template_executions', ['user_id', 'status'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables in reverse order of creation
    op.drop_index('ix_template_executions_user_status', table_name='template_executions')
    op.drop_index('ix_template_executions_template_status', table_name='template_executions')
    op.drop_index('ix_template_executions_user_id', table_name='template_executions')
    op.drop_index('ix_template_executions_workflow_id', table_name='template_executions')
    op.drop_index('ix_template_executions_template_id', table_name='template_executions')
    op.drop_table('template_executions')

    op.drop_index('ix_template_versions_template_version', table_name='template_versions')
    op.drop_index('ix_template_versions_template_id', table_name='template_versions')
    op.drop_table('template_versions')

    op.drop_index('ix_workflow_templates_author_public', table_name='workflow_templates')
    op.drop_index('ix_workflow_templates_public_featured', table_name='workflow_templates')
    op.drop_index('ix_workflow_templates_category_complexity', table_name='workflow_templates')
    op.drop_index('ix_workflow_templates_created_at', table_name='workflow_templates')
    op.drop_index('ix_workflow_templates_is_featured', table_name='workflow_templates')
    op.drop_index('ix_workflow_templates_is_public', table_name='workflow_templates')
    op.drop_index('ix_workflow_templates_author_id', table_name='workflow_templates')
    op.drop_index('ix_workflow_templates_template_id', table_name='workflow_templates')
    op.drop_table('workflow_templates')
