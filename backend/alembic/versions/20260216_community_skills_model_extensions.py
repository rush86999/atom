"""community_skills_model_extensions

Revision ID: 20260216_community_skills
Revises: 102066a41263
Create Date: 2026-02-16

This migration adds community skill tracking columns to skill_executions table.
Phase 14: Community Skills Integration - Hazard Sandbox execution

New columns:
- skill_source: Track if skill is 'cloud' (Atom cloud) or 'community' (OpenClaw/ClawHub)
- security_scan_result: Store LLM security scan results (risk level, findings)
- sandbox_enabled: Flag to enable/disable Docker sandbox for execution
- container_id: Track Docker container ID for debugging/audit

Indexes:
- ix_skill_executions_skill_source: Filter by skill source
- ix_skill_executions_sandbox_enabled: Filter sandboxed skills
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260216_community_skills'
down_revision: Union[str, Sequence[str], None] = '102066a41263'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add community skill columns."""

    # Add new columns to skill_executions table
    op.add_column(
        'skill_executions',
        sa.Column('skill_source', sa.String(), default='cloud', nullable=True)
    )

    op.add_column(
        'skill_executions',
        sa.Column('security_scan_result', sa.JSON(), nullable=True)
    )

    op.add_column(
        'skill_executions',
        sa.Column('sandbox_enabled', sa.Boolean(), default=False, nullable=True)
    )

    op.add_column(
        'skill_executions',
        sa.Column('container_id', sa.String(), nullable=True)
    )

    # Create indexes for efficient querying
    op.create_index(
        'ix_skill_executions_skill_source',
        'skill_executions',
        ['skill_source']
    )

    op.create_index(
        'ix_skill_executions_sandbox_enabled',
        'skill_executions',
        ['sandbox_enabled']
    )

    # Update existing records: set skill_source='cloud' for NULL values
    op.execute(
        "UPDATE skill_executions SET skill_source = 'cloud' WHERE skill_source IS NULL"
    )


def downgrade() -> None:
    """Downgrade schema - remove community skill columns."""

    # Drop indexes
    op.drop_index('ix_skill_executions_sandbox_enabled', 'skill_executions')
    op.drop_index('ix_skill_executions_skill_source', 'skill_executions')

    # Drop columns (in reverse order)
    op.drop_column('skill_executions', 'container_id')
    op.drop_column('skill_executions', 'sandbox_enabled')
    op.drop_column('skill_executions', 'security_scan_result')
    op.drop_column('skill_executions', 'skill_source')
