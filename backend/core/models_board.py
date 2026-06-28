from __future__ import annotations

"""
Board / Kanban task models.

Single-Tenant version for Upstream. All tenant_id columns and RLS have been stripped.
"""

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base
from core.models import JSONBColumn, UUID


def _pk_uuid() -> Column:
    """UUID primary key with uuid4 default — matches the rest of core.models."""
    return Column(UUID, primary_key=True, default=lambda: str(uuid.uuid4()))


class Board(Base):
    """A Kanban board. Contains columns + tasks."""

    __tablename__ = "boards"

    id = _pk_uuid()
    name = Column(String(255), nullable=False)
    slug = Column(String(120), nullable=True, index=True)
    description = Column(Text, nullable=True)
    owner_user_id = Column(
        UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    archived_at = Column(DateTime(timezone=True), nullable=True)

    # Optimistic locking
    version_id = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version_id}

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    owner = relationship("User", foreign_keys=[owner_user_id], backref="owned_boards")
    columns = relationship(
        "BoardColumn",
        back_populates="board",
        cascade="all, delete-orphan",
        order_by="BoardColumn.position",
    )
    tasks = relationship(
        "BoardTask",
        back_populates="board",
        cascade="all, delete-orphan",
        primaryjoin="Board.id == foreign(BoardTask.board_id)",
    )


class BoardColumn(Base):
    """A column (a.k.a. swimlane / status bucket) on a board."""

    __tablename__ = "board_columns"

    id = _pk_uuid()
    board_id = Column(
        UUID,
        ForeignKey("boards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(String(120), nullable=False)
    position = Column(Integer, nullable=False, default=0)
    wip_limit = Column(Integer, nullable=True)  # Work-in-progress cap; nullable = unlimited

    # Optimistic locking
    version_id = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version_id}

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    board = relationship("Board", back_populates="columns")
    tasks = relationship(
        "BoardTask", back_populates="column", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_board_columns_board_position", "board_id", "position"),
    )


class BoardTask(Base):
    """A task on a board. Optionally owns a Canvas workspace."""

    __tablename__ = "board_tasks"

    id = _pk_uuid()
    board_id = Column(
        UUID,
        ForeignKey("boards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    column_id = Column(
        UUID,
        ForeignKey("board_columns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Task definition
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="backlog")
    priority = Column(String(16), default="normal")  # low, normal, high, urgent

    # Assignment (human and/or agent). Nullable to allow unassigned backlog items.
    assignee_user_id = Column(
        UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assignee_agent_id = Column(UUID, nullable=True, index=True)

    # Hierarchy (self-reference). parent_task_id is self-reference.
    parent_task_id = Column(
        UUID, ForeignKey("board_tasks.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    root_task_id = Column(UUID, nullable=True, index=True)

    # Sort order within a column. Float for fractional indexing (Figma-style).
    sort_order = Column(Float, nullable=False, default=0.0)

    due_at = Column(DateTime(timezone=True), nullable=True)
    labels = Column(JSONBColumn, default=list)
    metadata_json = Column(JSONBColumn, default=dict)

    created_by_user_id = Column(
        UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Task workspace (Canvas). Nullable.
    canvas_id = Column(
        UUID,
        ForeignKey("canvases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Optimistic locking
    version_id = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version_id}

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    board = relationship(
        "Board", back_populates="tasks", foreign_keys=[board_id]
    )
    column = relationship("BoardColumn", back_populates="tasks", foreign_keys=[column_id])
    parent_task = relationship(
        "BoardTask",
        remote_side="BoardTask.id",
        foreign_keys=[parent_task_id],
        backref="subtasks",
    )
    canvas = relationship("Canvas", foreign_keys=[canvas_id])

    __table_args__ = (
        # Primary access pattern: render a column in sort order.
        Index(
            "ix_board_tasks_board_column_sort",
            "board_id",
            "column_id",
            "sort_order",
        ),
        # "My tasks" / assignee query.
        Index(
            "ix_board_tasks_assignee_status",
            "assignee_user_id",
            "status",
        ),
    )
