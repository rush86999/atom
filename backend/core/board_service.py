from __future__ import annotations

"""
BoardService — business logic for Board / BoardColumn / BoardTask (Phase 1).

Single-Tenant version for Upstream. All tenant_id columns and RLS have been stripped
from Board, BoardColumn, and BoardTask tables, but Canvas creation still receives
tenant_id as a parameter to satisfy external model constraints.
"""

import logging
import uuid
from typing import Any, Union

from fastapi import HTTPException
from sqlalchemy import desc, func as sql_func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from api.schemas.board_schemas import (
    BoardCreate,
    ColumnCreate,
    TaskCreate,
    TaskPatch,
)
from core.board_events import BoardEventEmitter
from core.board_state_machine import (
    BoardStatus,
    IllegalBoardTransition,
    assert_transition,
)
from core.models import Canvas, CanvasAudit, User, Workspace
from core.models_board import Board, BoardColumn, BoardTask

logger = logging.getLogger(__name__)

# Standard 6-column Kanban layout.
DEFAULT_COLUMNS: tuple[tuple[str, int], ...] = (
    ("Backlog", 0),
    ("To Do", 1),
    ("In Progress", 2),
    ("In Review", 3),
    ("Blocked", 4),
    ("Done", 5),
)


class BoardService:
    """Stateless-ish service: takes a ``db`` Session per request."""

    def __init__(self, db: Session, emitter: Union[BoardEventEmitter, None] = None):
        self.db = db
        # Optional emitter for testing
        self.emitter = emitter

    # ------------------------------------------------------------------- #
    # Helpers
    # ------------------------------------------------------------------- #
    def _get_board_scoped(self, board_id: str) -> Board:
        board = (
            self.db.query(Board)
            .filter(Board.id == board_id)
            .first()
        )
        if not board:
            raise HTTPException(status_code=404, detail="Board not found")
        return board

    def _get_column_scoped(
        self, column_id: str, board_id: str
    ) -> BoardColumn:
        column = (
            self.db.query(BoardColumn)
            .filter(
                BoardColumn.id == column_id,
                BoardColumn.board_id == board_id,
            )
            .first()
        )
        if not column:
            raise HTTPException(status_code=404, detail="Column not found")
        return column

    def _get_task_scoped(
        self, task_id: str, board_id: str
    ) -> BoardTask:
        task = (
            self.db.query(BoardTask)
            .filter(
                BoardTask.id == task_id,
                BoardTask.board_id == board_id,
            )
            .first()
        )
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    # ------------------------------------------------------------------- #
    # Board CRUD
    # ------------------------------------------------------------------- #
    def create_board(
        self,
        owner_user_id: Union[str, None],
        payload: BoardCreate,
        tenant_id: Union[str, None] = None,  # kept for signature compatibility/defaulting
    ) -> Board:
        board = Board(
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            owner_user_id=owner_user_id,
        )
        self.db.add(board)
        self.db.flush()

        if payload.seed_default_columns:
            for name, position in DEFAULT_COLUMNS:
                self.db.add(
                    BoardColumn(
                        board_id=board.id,
                        name=name,
                        position=position,
                    )
                )

        self.db.flush()
        self.db.commit()
        self.db.refresh(board)
        return board

    def list_boards(self, include_archived: bool = False) -> list[Board]:
        q = self.db.query(Board)
        if not include_archived:
            q = q.filter(Board.archived_at.is_(None))
        return q.order_by(Board.created_at.desc()).all()

    def get_board(self, board_id: str) -> Board:
        return self._get_board_scoped(board_id)

    # ------------------------------------------------------------------- #
    # Column CRUD
    # ------------------------------------------------------------------- #
    def create_column(
        self,
        board_id: str,
        payload: ColumnCreate,
    ) -> BoardColumn:
        self._get_board_scoped(board_id)
        column = BoardColumn(
            board_id=board_id,
            name=payload.name,
            position=payload.position,
            wip_limit=payload.wip_limit,
        )
        self.db.add(column)
        self.db.commit()
        self.db.refresh(column)
        return column

    def list_columns(self, board_id: str) -> list[BoardColumn]:
        return (
            self.db.query(BoardColumn)
            .filter(BoardColumn.board_id == board_id)
            .order_by(BoardColumn.position.asc())
            .all()
        )

    # ------------------------------------------------------------------- #
    # Task CRUD
    # ------------------------------------------------------------------- #
    def create_task(
        self,
        board_id: str,
        created_by_user_id: Union[str, None],
        payload: TaskCreate,
        tenant_id: Union[str, None] = None,  # Required to seed task workspace (Canvas)
    ) -> BoardTask:
        """Create a task. If ``payload.workspace`` is True, also create a Canvas."""
        self._get_board_scoped(board_id)
        column = self._get_column_scoped(payload.column_id, board_id)

        if payload.status not in BoardStatus.ALL:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown status {payload.status!r}. Allowed: {list(BoardStatus.ALL)}",
            )

        # Sort order: append to end of the destination column by default.
        sort_order = self._next_sort_order(column.id)

        task = BoardTask(
            board_id=board_id,
            column_id=column.id,
            title=payload.title,
            description=payload.description,
            status=payload.status,
            priority=payload.priority,
            assignee_user_id=payload.assignee_user_id,
            assignee_agent_id=payload.assignee_agent_id,
            parent_task_id=payload.parent_task_id,
            root_task_id=payload.parent_task_id,
            sort_order=sort_order,
            due_at=payload.due_at,
            labels=payload.labels or [],
            metadata_json=payload.metadata_json or {},
            created_by_user_id=created_by_user_id,
        )

        # Resolve root_task_id from parent if the caller passed a parent.
        if payload.parent_task_id:
            parent = self._get_task_scoped(payload.parent_task_id, board_id)
            task.root_task_id = parent.root_task_id or parent.id

        self.db.add(task)
        self.db.flush()

        if payload.workspace:
            if not tenant_id:
                raise HTTPException(
                    status_code=400,
                    detail="tenant_id is required to create a workspace for the task"
                )
            self.create_task_workspace(task, tenant_id=tenant_id)

        self.db.commit()
        self.db.refresh(task)
        return task

    def patch_task(
        self,
        board_id: str,
        task_id: str,
        payload: TaskPatch,
        tenant_id: Union[str, None] = None,  # Required if payload.workspace is True
    ) -> tuple[BoardTask, dict[str, Any]]:
        """Apply a partial update with optimistic locking + state-machine checks."""
        task = self._get_task_scoped(task_id, board_id)

        if payload.expected_version != task.version_id:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "stale_version",
                    "expected_version": payload.expected_version,
                    "actual_version": task.version_id,
                    "message": "Another client edited this task. Refresh and retry.",
                },
            )

        # Capture BEFORE state
        before_column_id = str(task.column_id)
        before_status = task.status
        changed_fields: set[str] = set()

        # Validate column move
        target_column: Union[BoardColumn, None] = None
        if payload.column_id is not None and payload.column_id != str(task.column_id):
            target_column = self._get_column_scoped(payload.column_id, board_id)

        # Validate transition
        if payload.status is not None and payload.status != task.status:
            try:
                assert_transition(task.status, payload.status)
            except IllegalBoardTransition as e:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "illegal_transition",
                        "current": e.current,
                        "requested": e.requested,
                        "allowed_next": sorted(e.allowed_next),
                    },
                ) from e

        # Apply scalar mutations
        if payload.title is not None:
            task.title = payload.title[:500]
            changed_fields.add("title")
        if payload.description is not None:
            task.description = payload.description
            changed_fields.add("description")
        if payload.priority is not None:
            task.priority = payload.priority
            changed_fields.add("priority")
        if payload.assignee_user_id is not None:
            task.assignee_user_id = payload.assignee_user_id
            changed_fields.add("assignee_user_id")
        if payload.assignee_agent_id is not None:
            task.assignee_agent_id = payload.assignee_agent_id
            changed_fields.add("assignee_agent_id")
        if payload.due_at is not None:
            task.due_at = payload.due_at
            changed_fields.add("due_at")
        if payload.labels is not None:
            task.labels = payload.labels
            changed_fields.add("labels")
        if payload.metadata_json is not None:
            task.metadata_json = payload.metadata_json
            changed_fields.add("metadata_json")

        # Apply transition
        if payload.status is not None and payload.status != task.status:
            task.status = payload.status
            if payload.status == BoardStatus.DONE and task.canvas_id is not None:
                self._archive_task_canvas(task)

        if target_column is not None:
            if payload.sort_order is None:
                new_sort = self._next_sort_order(target_column.id)
            else:
                new_sort = payload.sort_order
            task.column_id = target_column.id
            task.sort_order = new_sort
        elif payload.sort_order is not None:
            task.sort_order = payload.sort_order
            changed_fields.add("sort_order")

        # Create workspace if requested
        if payload.workspace is True and task.canvas_id is None:
            if not tenant_id:
                raise HTTPException(
                    status_code=400,
                    detail="tenant_id is required to create a workspace for the task"
                )
            self.create_task_workspace(task, tenant_id=tenant_id)
            changed_fields.add("canvas_id")

        try:
            self.db.flush()
            self.db.commit()
        except (StaleDataError, IntegrityError) as e:
            self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "stale_version",
                    "message": "Task was modified concurrently. Refresh and retry.",
                },
            ) from e

        self.db.refresh(task)

        change_meta = {
            "from_column_id": before_column_id if target_column is not None else None,
            "to_column_id": str(task.column_id) if target_column is not None else None,
            "from_status": before_status if task.status != before_status else None,
            "to_status": task.status if task.status != before_status else None,
            "fields": changed_fields,
        }
        return task, change_meta

    def delete_task(self, board_id: str, task_id: str) -> dict[str, Any]:
        """Delete a task. Returns a snapshot for event emission."""
        task = self._get_task_scoped(task_id, board_id)
        snapshot = {
            "id": str(task.id),
            "board_id": str(task.board_id),
            "column_id": str(task.column_id),
            "title": task.title,
            "status": task.status,
            "sort_order": float(task.sort_order),
            "version_id": task.version_id,
            "canvas_id": str(task.canvas_id) if task.canvas_id else None,
        }
        self.db.delete(task)
        self.db.commit()
        return snapshot

    def list_tasks(
        self,
        board_id: str,
        column_id: Union[str, None] = None,
    ) -> list[BoardTask]:
        q = self.db.query(BoardTask).filter(BoardTask.board_id == board_id)
        if column_id:
            q = q.filter(BoardTask.column_id == column_id)
        return q.order_by(BoardTask.sort_order.asc()).all()

    # ------------------------------------------------------------------- #
    # Sort helpers
    # ------------------------------------------------------------------- #
    def _next_sort_order(self, column_id: str) -> float:
        max_so = (
            self.db.query(sql_func.max(BoardTask.sort_order))
            .filter(BoardTask.column_id == column_id)
            .scalar()
        )
        return float(max_so) + 1.0 if max_so is not None else 0.0

    def rebalance_column(
        self, board_id: str, column_id: Union[str, None]
    ) -> int:
        """Rewrite ``sort_order`` as 0.0, 1.0, 2.0, ... for each task in a column."""
        self._get_board_scoped(board_id)

        column_ids: list[str]
        if column_id is None:
            column_ids = [c.id for c in self.list_columns(board_id)]
        else:
            column_ids = [self._get_column_scoped(column_id, board_id).id]

        moved = 0
        for cid in column_ids:
            tasks = (
                self.db.query(BoardTask)
                .filter(BoardTask.column_id == cid)
                .order_by(BoardTask.sort_order.asc())
                .all()
            )
            for i, t in enumerate(tasks):
                if t.sort_order != float(i):
                    t.sort_order = float(i)
                    moved += 1
        self.db.commit()
        return moved

    # ------------------------------------------------------------------- #
    # Canvas workspace lifecycle
    # ------------------------------------------------------------------- #
    def create_task_workspace(
        self,
        task: BoardTask,
        tenant_id: str,
    ) -> Canvas:
        """Create a Canvas of ``canvas_type="kanban"`` and link it to ``task``."""
        if task.canvas_id is not None:
            existing = (
                self.db.query(Canvas).filter(Canvas.id == str(task.canvas_id)).first()
            )
            if existing is not None:
                return existing

        workspace_id = self._lookup_workspace_id(tenant_id)

        canvas = Canvas(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            created_by=str(task.created_by_user_id) if task.created_by_user_id else "system",
            name=f"Task: {task.title}"[:255],
            description=task.description,
            canvas_type="kanban",
            is_collaborative=True,
        )
        self.db.add(canvas)
        self.db.flush()

        task.canvas_id = canvas.id

        audit = CanvasAudit(
            canvas_id=canvas.id,
            tenant_id=tenant_id,
            action_type="create_task_workspace",
            user_id=str(task.created_by_user_id) if task.created_by_user_id else None,
            details_json={"task_id": str(task.id)},
        )
        self.db.add(audit)
        return canvas

    def _lookup_workspace_id(self, tenant_id: str) -> Union[str, None]:
        ws = (
            self.db.query(Workspace)
            .filter(Workspace.tenant_id == tenant_id)
            .order_by(Workspace.created_at.asc())
            .first()
        )
        return str(ws.id) if ws else None

    def _archive_task_canvas(self, task: BoardTask) -> None:
        if task.canvas_id is None:
            return
        canvas = self.db.query(Canvas).filter(Canvas.id == str(task.canvas_id)).first()
        if canvas is not None and canvas.status != "archived":
            canvas.status = "archived"
