from __future__ import annotations

"""
Kanban Board API routes (Phase 1).

Single-Tenant version for Upstream. All tenant_id columns and arguments are stripped
except when delegating to services that need tenant_id (e.g. creating task Canvas).
"""

import logging
from typing import Any, Union

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from api.schemas.board_schemas import (
    BoardCreate,
    BoardDetail,
    BoardRead,
    ColumnCreate,
    ColumnRead,
    RebalanceRequest,
    RebalanceResult,
    TaskCreate,
    TaskPatch,
    TaskRead,
)
from core.board_events import BoardEventEmitter
from core.board_service import BoardService
from core.database import get_db
from core.models import Canvas, User
from core.models_board import Board, BoardColumn, BoardTask
from core.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/boards", tags=["boards"])

_emitter = BoardEventEmitter()


# --------------------------------------------------------------------------- #
# Serialisation helpers
# --------------------------------------------------------------------------- #
def _canvas_summary(db: Session, task: BoardTask) -> Union[dict[str, Any], None]:
    if task.canvas_id is None:
        return None
    canvas = db.query(Canvas).filter(Canvas.id == task.canvas_id).first()
    if canvas is None:
        return None

    # In upstream models: AgentCanvasPresence and Artifact
    from core.models import AgentCanvasPresence, Artifact

    artifact_count = (
        db.query(Artifact).filter(Artifact.canvas_id == canvas.id).count()
    )
    presence_count = (
        db.query(AgentCanvasPresence)
        .filter(
            AgentCanvasPresence.canvas_id == canvas.id,
            AgentCanvasPresence.status == "active",
        )
        .count()
    )
    return {
        "canvas_id": str(canvas.id),
        "name": canvas.name,
        "status": canvas.status,
        "artifact_count": artifact_count,
        "presence_count": presence_count,
    }


def _serialize_task(db: Session, task: BoardTask) -> TaskRead:
    data = {
        "id": str(task.id),
        "board_id": str(task.board_id),
        "column_id": str(task.column_id),
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "assignee_user_id": str(task.assignee_user_id) if task.assignee_user_id else None,
        "assignee_agent_id": str(task.assignee_agent_id) if task.assignee_agent_id else None,
        "parent_task_id": str(task.parent_task_id) if task.parent_task_id else None,
        "root_task_id": str(task.root_task_id) if task.root_task_id else None,
        "sort_order": float(task.sort_order),
        "due_at": task.due_at,
        "labels": task.labels or [],
        "metadata_json": task.metadata_json or {},
        "created_by_user_id": (
            str(task.created_by_user_id) if task.created_by_user_id else None
        ),
        "canvas_id": str(task.canvas_id) if task.canvas_id else None,
        "version_id": task.version_id,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "canvas": _canvas_summary(db, task),
    }
    return TaskRead.model_validate(data)


def _serialize_board(board: Board) -> BoardRead:
    data = {
        "id": str(board.id),
        "name": board.name,
        "slug": board.slug,
        "description": board.description,
        "owner_user_id": str(board.owner_user_id) if board.owner_user_id else None,
        "archived_at": board.archived_at,
        "version_id": board.version_id,
        "created_at": board.created_at,
        "updated_at": board.updated_at,
    }
    return BoardRead.model_validate(data)


def _serialize_column(column: BoardColumn, task_count: int = 0) -> ColumnRead:
    return ColumnRead(
        id=str(column.id),
        board_id=str(column.board_id),
        name=column.name,
        position=column.position,
        wip_limit=column.wip_limit,
        version_id=column.version_id,
        task_count=task_count,
    )


# --------------------------------------------------------------------------- #
# Board CRUD
# --------------------------------------------------------------------------- #
@router.post("", response_model=BoardRead, status_code=201)
async def create_board(
    payload: BoardCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = BoardService(db)
    board = service.create_board(
        owner_user_id=str(current_user.id),
        payload=payload,
        tenant_id=current_user.tenant_id,
    )
    return _serialize_board(board)


@router.get("", response_model=list[BoardRead])
async def list_boards(
    include_archived: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = BoardService(db)
    return [_serialize_board(b) for b in service.list_boards(
        include_archived=include_archived,
    )]


@router.get("/{board_id}", response_model=BoardDetail)
async def get_board(
    board_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = BoardService(db)
    board = service.get_board(board_id)
    columns = service.list_columns(board_id)

    counts: dict[str, int] = {}
    for t in service.list_tasks(board_id):
        counts[str(t.column_id)] = counts.get(str(t.column_id), 0) + 1

    return BoardDetail(
        **_serialize_board(board).model_dump(),
        columns=[_serialize_column(c, counts.get(str(c.id), 0)) for c in columns],
    )


# --------------------------------------------------------------------------- #
# Column CRUD
# --------------------------------------------------------------------------- #
@router.post("/{board_id}/columns", response_model=ColumnRead, status_code=201)
async def create_column(
    board_id: str,
    payload: ColumnCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = BoardService(db)
    column = service.create_column(
        board_id=board_id,
        payload=payload,
    )
    return _serialize_column(column)


# --------------------------------------------------------------------------- #
# Task CRUD
# --------------------------------------------------------------------------- #
@router.post("/{board_id}/tasks", response_model=TaskRead, status_code=201)
async def create_task(
    board_id: str,
    payload: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = BoardService(db)
    task = service.create_task(
        board_id=board_id,
        created_by_user_id=str(current_user.id),
        payload=payload,
        tenant_id=current_user.tenant_id,
    )
    await _emitter.emit_task_created(task)
    return _serialize_task(db, task)


@router.patch("/{board_id}/tasks/{task_id}", response_model=TaskRead)
async def patch_task(
    board_id: str,
    task_id: str,
    payload: TaskPatch,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = BoardService(db)
    task, change_meta = service.patch_task(
        board_id=board_id,
        task_id=task_id,
        payload=payload,
        tenant_id=current_user.tenant_id,
    )

    if change_meta["from_column_id"] is not None:
        await _emitter.emit_task_moved(
            task,
            from_column_id=change_meta["from_column_id"],
            to_column_id=change_meta["to_column_id"],
        )
    if change_meta["from_status"] is not None:
        await _emitter.emit_task_transitioned(
            task,
            from_status=change_meta["from_status"],
            to_status=change_meta["to_status"],
        )
    other_fields = change_meta["fields"] - {"sort_order"}
    if other_fields and change_meta["from_status"] is None and change_meta["from_column_id"] is None:
        await _emitter.emit_task_updated(task)

    return _serialize_task(db, task)


@router.delete("/{board_id}/tasks/{task_id}", status_code=204)
async def delete_task(
    board_id: str,
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = BoardService(db)
    snapshot = service.delete_task(
        board_id, task_id
    )
    await _emitter.emit_task_deleted(snapshot)
    return None


@router.get("/{board_id}/tasks", response_model=list[TaskRead])
async def list_tasks(
    board_id: str,
    column_id: Union[str, None] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = BoardService(db)
    tasks = service.list_tasks(
        board_id=board_id,
        column_id=column_id,
    )
    return [_serialize_task(db, t) for t in tasks]


# --------------------------------------------------------------------------- #
# Workspace / rebalance helpers
# --------------------------------------------------------------------------- #
@router.get("/{board_id}/tasks/{task_id}/canvas")
async def get_task_canvas(
    board_id: str,
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = (
        db.query(BoardTask)
        .filter(
            BoardTask.id == task_id,
            BoardTask.board_id == board_id,
        )
        .first()
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.canvas_id is None:
        raise HTTPException(status_code=404, detail="Task has no workspace Canvas")
    return RedirectResponse(url=f"/canvas/{task.canvas_id}")


@router.post("/{board_id}/rebalance", response_model=RebalanceResult)
async def rebalance_board(
    board_id: str,
    payload: RebalanceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = BoardService(db)
    moved = service.rebalance_column(
        board_id=board_id,
        column_id=payload.column_id,
    )

    if payload.column_id is None:
        columns_touched = [
            str(c.id)
            for c in service.list_columns(board_id)
        ]
    else:
        columns_touched = [payload.column_id]

    return RebalanceResult(rebalanced_columns=columns_touched, moved_tasks=moved)
