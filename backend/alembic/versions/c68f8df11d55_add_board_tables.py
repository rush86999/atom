"""add_board_tables

Revision ID: c68f8df11d55
Revises: 20260624_reasoning_fts
Create Date: 2026-06-28 17:47:41.079633

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c68f8df11d55'
down_revision: Union[str, Sequence[str], None] = '20260624_reasoning_fts'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # boards
    # ------------------------------------------------------------------ #
    op.create_table(
        "boards",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "owner_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_boards_slug", "boards", ["slug"])
    op.create_index("ix_boards_owner_user_id", "boards", ["owner_user_id"])

    # ------------------------------------------------------------------ #
    # board_columns
    # ------------------------------------------------------------------ #
    op.create_table(
        "board_columns",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "board_id",
            sa.String(36),
            sa.ForeignKey("boards.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wip_limit", sa.Integer(), nullable=True),
        sa.Column("version_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_board_columns_board_id", "board_columns", ["board_id"])
    op.create_index(
        "ix_board_columns_board_position", "board_columns", ["board_id", "position"]
    )

    # ------------------------------------------------------------------ #
    # board_tasks
    # ------------------------------------------------------------------ #
    op.create_table(
        "board_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "board_id",
            sa.String(36),
            sa.ForeignKey("boards.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "column_id",
            sa.String(36),
            sa.ForeignKey("board_columns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="backlog"),
        sa.Column("priority", sa.String(length=16), server_default="normal"),
        sa.Column(
            "assignee_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("assignee_agent_id", sa.String(36), nullable=True),
        sa.Column("parent_task_id", sa.String(36), nullable=True),
        sa.Column("root_task_id", sa.String(36), nullable=True),
        sa.Column("sort_order", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("labels", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "canvas_id",
            sa.String(36),
            sa.ForeignKey("canvases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("version_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["parent_task_id"],
            ["board_tasks.id"],
            name="fk_board_tasks_parent_task_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_board_tasks_board_id", "board_tasks", ["board_id"])
    op.create_index("ix_board_tasks_column_id", "board_tasks", ["column_id"])
    op.create_index("ix_board_tasks_parent_task_id", "board_tasks", ["parent_task_id"])
    op.create_index("ix_board_tasks_root_task_id", "board_tasks", ["root_task_id"])
    op.create_index(
        "ix_board_tasks_assignee_user_id", "board_tasks", ["assignee_user_id"]
    )
    op.create_index(
        "ix_board_tasks_assignee_agent_id", "board_tasks", ["assignee_agent_id"]
    )
    op.create_index("ix_board_tasks_canvas_id", "board_tasks", ["canvas_id"])
    op.create_index(
        "ix_board_tasks_board_column_sort",
        "board_tasks",
        ["board_id", "column_id", "sort_order"],
    )
    op.create_index(
        "ix_board_tasks_assignee_status",
        "board_tasks",
        ["assignee_user_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_board_tasks_assignee_status", table_name="board_tasks")
    op.drop_index("ix_board_tasks_board_column_sort", table_name="board_tasks")
    op.drop_index("ix_board_tasks_canvas_id", table_name="board_tasks")
    op.drop_index("ix_board_tasks_assignee_agent_id", table_name="board_tasks")
    op.drop_index("ix_board_tasks_assignee_user_id", table_name="board_tasks")
    op.drop_index("ix_board_tasks_root_task_id", table_name="board_tasks")
    op.drop_index("ix_board_tasks_parent_task_id", table_name="board_tasks")
    op.drop_index("ix_board_tasks_column_id", table_name="board_tasks")
    op.drop_index("ix_board_tasks_board_id", table_name="board_tasks")
    op.drop_table("board_tasks")

    op.drop_index("ix_board_columns_board_position", table_name="board_columns")
    op.drop_index("ix_board_columns_board_id", table_name="board_columns")
    op.drop_table("board_columns")

    op.drop_index("ix_boards_owner_user_id", table_name="boards")
    op.drop_index("ix_boards_slug", table_name="boards")
    op.drop_table("boards")
