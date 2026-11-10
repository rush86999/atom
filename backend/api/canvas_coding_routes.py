"""Coding Canvas API Routes"""
import logging
from typing import List, Optional
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user, User
from core.base_routes import BaseAPIRouter
from core.canvas_coding_service import CodingCanvasService
from core.database import get_db
from core.models import User

logger = logging.getLogger(__name__)
router = BaseAPIRouter(prefix="/api/canvas/coding", tags=["canvas_coding"])


class CreateCodingRequest(BaseModel):
    user_id: str
    repo: str
    branch: str
    canvas_id: Optional[str] = None
    agent_id: Optional[str] = None
    layout: str = "repo_view"


class AddFileRequest(BaseModel):
    user_id: str
    path: str
    content: str
    language: str = "text"


class AddDiffRequest(BaseModel):
    user_id: str
    file_path: str
    old_content: str
    new_content: str


def _raise_service_error(result: dict, default_code: str, default_message: str) -> None:
    """Map a typed service refusal to its real HTTP status."""
    raise router.error_response(
        error_code=result.get("error_code") or default_code,
        message=result.get("error") or default_message,
        status_code=int(result.get("http_status") or 400),
    )


@router.post("/create")
async def create_coding_canvas(
    request: CreateCodingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new coding canvas for the authenticated actor."""
    service = CodingCanvasService(db)
    result = service.create_coding_canvas(
        user_id=str(current_user.id),  # Override body-supplied user_id for security
        repo=request.repo,
        branch=request.branch,
        canvas_id=request.canvas_id,
        agent_id=request.agent_id,
        layout=request.layout
    )
    if not result.get("success"):
        _raise_service_error(
            result,
            "CODING_CANVAS_CREATE_FAILED",
            "Failed to create coding canvas",
        )

    return router.success_response(
        data=result,
        message="Coding canvas created successfully"
    )


@router.post("/{canvas_id}/file")
async def add_file(
    canvas_id: str,
    request: AddFileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a file to the coding workspace."""
    service = CodingCanvasService(db)
    result = service.add_file(
        canvas_id=canvas_id,
        user_id=str(current_user.id),  # Override body-supplied user_id
        path=request.path,
        content=request.content,
        language=request.language
    )
    if not result.get("success"):
        _raise_service_error(
            result, "ADD_FILE_FAILED", "Failed to add file")

    return router.success_response(
        data=result,
        message=f"File {request.path} added successfully"
    )


@router.post("/{canvas_id}/diff")
async def add_diff(
    canvas_id: str,
    request: AddDiffRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a diff view."""
    service = CodingCanvasService(db)
    result = service.add_diff(
        canvas_id=canvas_id,
        user_id=str(current_user.id),  # Override body-supplied user_id
        file_path=request.file_path,
        old_content=request.old_content,
        new_content=request.new_content
    )
    if not result.get("success"):
        _raise_service_error(
            result, "ADD_DIFF_FAILED", "Failed to add diff")

    return router.success_response(
        data=result,
        message=f"Diff for {request.file_path} added successfully"
    )


@router.get("/{canvas_id}")
async def get_coding_canvas(
    canvas_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a coding canvas for the current authorized actor."""
    service = CodingCanvasService(db)
    result = service.get_coding_canvas(canvas_id, current_user.id)
    if not result.get("success"):
        _raise_service_error(
            result, "CODING_CANVAS_READ_FAILED", "Coding canvas could not be read")
    return router.success_response(
        data=result.get("data") or {},
        message="Coding canvas retrieved successfully"
    )
