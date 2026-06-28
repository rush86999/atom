from __future__ import annotations

import logging
from typing import Any, Union

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.schemas.board_decompose_schemas import (
    DecomposeCommitRequest,
    DecomposeCommitResult,
    DecomposePreview,
    DecomposeRequest,
)
from core.board_decomposer import MAX_ROOT_DEPTH, BoardDecomposer
from core.board_events import BoardEventEmitter
from core.database import get_db
from core.models import User
from core.models_board import BoardTask
from core.security_dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/boards", tags=["board_decompose"])

_emitter = BoardEventEmitter()


def _build_handler(request: Request, db: Session, model_hint: Union[str, None]):
    try:
        from core.llm.byok_handler import BYOKHandler
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": "byok_unavailable", "message": "BYOK subsystem unavailable."},
        ) from e

    return BYOKHandler(
        db_session=db,
    )


# --------------------------------------------------------------------------- #
# Propose
# --------------------------------------------------------------------------- #
@router.post(
    "/{board_id}/tasks/{task_id}/decompose",
    response_model=DecomposePreview,
)
async def propose_decomposition(
    board_id: str,
    task_id: str,
    payload: DecomposeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    handler = _build_handler(request, db, payload.model_hint)
    decomposer = BoardDecomposer(db)

    result = await decomposer.propose(
        board_id=board_id,
        task_id=task_id,
        handler=handler,
    )

    task = db.query(BoardTask).filter(
        BoardTask.id == task_id,
    ).first()
    depth = BoardDecomposer._root_depth(task) if task else 1

    return DecomposePreview(
        parent_task_id=task_id,
        rationale=result.rationale,
        subtasks=result.subtasks,
        depth=depth,
        max_depth=MAX_ROOT_DEPTH,
    )


# --------------------------------------------------------------------------- #
# Commit
# --------------------------------------------------------------------------- #
@router.post(
    "/{board_id}/tasks/{task_id}/decompose/commit",
    response_model=DecomposeCommitResult,
    status_code=201,
)
async def commit_decomposition(
    board_id: str,
    task_id: str,
    payload: DecomposeCommitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    decomposer = BoardDecomposer(db)
    children = decomposer.commit(
        board_id=board_id,
        parent_task_id=task_id,
        proposals=payload.proposals,
        created_by_user_id=str(current_user.id),
        spawn_workspaces=payload.spawn_workspaces,
    )

    for c in children:
        await _emitter.emit_task_created(c)

    return DecomposeCommitResult(
        parent_task_id=task_id,
        created_task_ids=[str(c.id) for c in children],
        spawned_workspaces=payload.spawn_workspaces,
    )
