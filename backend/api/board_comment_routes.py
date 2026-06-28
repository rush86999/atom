from __future__ import annotations

import logging
from typing import Any, Union

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.schemas.board_comment_schemas import (
    ArtifactCommentRead,
    CommentCreate,
    CommentPatch,
    CommentRead,
)
from core.board_comment_service import BoardCommentService
from core.board_events import BoardEventEmitter
from core.database import get_db
from core.models import User
from core.security_dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["board_comments"])

_emitter = BoardEventEmitter()


def _serialize_comment(service: BoardCommentService, msg) -> dict[str, Any]:
    return service._serialize(msg)


# --------------------------------------------------------------------------- #
# Task-level comments
# --------------------------------------------------------------------------- #
@router.post(
    "/boards/{board_id}/tasks/{task_id}/comments",
    response_model=CommentRead,
    status_code=201,
)
async def create_task_comment(
    board_id: str,
    task_id: str,
    payload: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = BoardCommentService(db)
    msg = service.create_comment(
        board_id=board_id,
        task_id=task_id,
        author_user_id=str(current_user.id),
        content=payload.content,
        parent_message_id=payload.parent_message_id,
    )
    serialized = _serialize_comment(service, msg)
    from core.models_board import BoardTask

    task = db.query(BoardTask).filter(BoardTask.id == task_id).first()
    if task is not None:
        await _emitter.emit_comment_posted(task, comment_id=str(msg.id), comment_payload=serialized)
    return CommentRead(**serialized, replies=[])


@router.get(
    "/boards/{board_id}/tasks/{task_id}/comments",
    response_model=list[CommentRead],
)
async def list_task_comments(
    board_id: str,
    task_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    before_id: Union[str, None] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = BoardCommentService(db)
    flat = service.list_comments(
        board_id=board_id,
        task_id=task_id,
        limit=limit,
        before_id=before_id,
    )
    tree = service.build_thread_tree(flat)
    return [CommentRead(**node) for node in tree]


@router.patch("/comments/{comment_id}", response_model=CommentRead)
async def patch_comment(
    comment_id: str,
    payload: CommentPatch,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = BoardCommentService(db)
    msg = service.patch_comment(
        comment_id=comment_id,
        author_user_id=str(current_user.id),
        new_content=payload.content,
    )
    return CommentRead(**_serialize_comment(service, msg), replies=[])


@router.delete("/comments/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = BoardCommentService(db)
    service.delete_comment(
        comment_id=comment_id,
        author_user_id=str(current_user.id),
    )
    return None


# --------------------------------------------------------------------------- #
# Artifact-level comments (aggregated from the task's Canvas)
# --------------------------------------------------------------------------- #
@router.get(
    "/boards/{board_id}/tasks/{task_id}/artifact-comments",
    response_model=list[ArtifactCommentRead],
)
async def list_artifact_comments(
    board_id: str,
    task_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = BoardCommentService(db)
    rows = service.list_artifact_comments_for_task(
        board_id=board_id,
        task_id=task_id,
        limit=limit,
    )
    return [ArtifactCommentRead(**row) for row in rows]
