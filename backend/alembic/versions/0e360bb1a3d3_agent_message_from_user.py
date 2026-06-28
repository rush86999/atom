"""agent_message_from_user

Revision ID: 0e360bb1a3d3
Revises: c68f8df11d55
Create Date: 2026-06-28 17:51:43.317745

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0e360bb1a3d3'
down_revision: Union[str, Sequence[str], None] = 'c68f8df11d55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("agent_messages", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "from_user_id",
                sa.String(36),
                sa.ForeignKey("users.id", name="fk_agent_messages_from_user_id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch_op.alter_column(
            "from_agent_id",
            existing_type=sa.String(255),
            nullable=True,
        )
        batch_op.alter_column(
            "to_agent_id",
            existing_type=sa.String(255),
            nullable=True,
        )
        batch_op.create_index("ix_agent_messages_from_user_id", ["from_user_id"])


def downgrade() -> None:
    with op.batch_alter_table("agent_messages", schema=None) as batch_op:
        batch_op.drop_index("ix_agent_messages_from_user_id")
        batch_op.alter_column(
            "to_agent_id",
            existing_type=sa.String(255),
            nullable=False,
        )
        batch_op.alter_column(
            "from_agent_id",
            existing_type=sa.String(255),
            nullable=False,
        )
        batch_op.drop_column("from_user_id")
