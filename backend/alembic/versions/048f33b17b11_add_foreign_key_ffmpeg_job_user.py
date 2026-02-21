"""add_foreign_key_ffmpeg_job_user

Revision ID: 048f33b17b11
Revises: 20260221_autonomous_coding
Create Date: 2026-02-21 07:57:03.657552

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '048f33b17b11'
down_revision: Union[str, Sequence[str], None] = '20260221_autonomous_coding'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Add foreign key constraint to FFmpegJob.user_id to fix relationship error.
    """
    # SQLite requires batch mode for schema changes that affect foreign keys
    with op.batch_alter_table('ffmpeg_job', recreate='auto') as batch_op:
        batch_op.create_foreign_key(
            'fk_ffmpeg_job_user_id',
            'users',
            ['user_id'],
            ['id']
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('ffmpeg_job', recreate='auto') as batch_op:
        batch_op.drop_constraint('fk_ffmpeg_job_user_id', type_='foreignkey')
