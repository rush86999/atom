"""Coding Canvas API Routes"""
import logging
from typing import List, Optional
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.canvas_coding_service import CodingCanvasService
from core.database import get_db

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


@router.post("/create")
async def create_coding_canvas(request: CreateCodingRequest, db: Session = Depends(get_db)):
    """Create a new coding canvas."""
    service = CodingCanvasService(db)
    result = service.create_coding_canvas(
        user_id=request.user_id,
        repo=request.repo,
        branch=request.branch,
        canvas_id=request.canvas_id,
        agent_id=request.agent_id,
        layout=request.layout
    )
    if not result.get("success"):
        raise router.error_response(
            error_code="CODING_CANVAS_CREATE_FAILED",
            message=result.get("error", "Failed to create coding canvas"),
            status_code=400
        )

    return router.success_response(
        data=result,
        message="Coding canvas created successfully"
    )


@router.post("/{canvas_id}/file")
async def add_file(canvas_id: str, request: AddFileRequest, db: Session = Depends(get_db)):
    """Add a file to the coding workspace."""
    service = CodingCanvasService(db)
    result = service.add_file(
        canvas_id=canvas_id,
        user_id=request.user_id,
        path=request.path,
        content=request.content,
        language=request.language
    )
    if not result.get("success"):
        raise router.error_response(
            error_code="ADD_FILE_FAILED",
            message=result.get("error", "Failed to add file"),
            status_code=400
        )

    return router.success_response(
        data=result,
        message=f"File {request.path} added successfully"
    )


@router.post("/{canvas_id}/diff")
async def add_diff(canvas_id: str, request: AddDiffRequest, db: Session = Depends(get_db)):
    """Add a diff view."""
    service = CodingCanvasService(db)
    result = service.add_diff(
        canvas_id=canvas_id,
        user_id=request.user_id,
        file_path=request.file_path,
        old_content=request.old_content,
        new_content=request.new_content
    )
    if not result.get("success"):
        raise router.error_response(
            error_code="ADD_DIFF_FAILED",
            message=result.get("error", "Failed to add diff"),
            status_code=400
        )

    return router.success_response(
        data=result,
        message=f"Diff for {request.file_path} added successfully"
    )


@router.get("/{canvas_id}")
async def get_coding_canvas(canvas_id: str, db: Session = Depends(get_db)):
    """Get a coding canvas."""
    from sqlalchemy import desc

    from core.models import CanvasAudit

    audit = db.query(CanvasAudit).filter(
        CanvasAudit.canvas_id == canvas_id,
        CanvasAudit.canvas_type == "coding"
    ).order_by(desc(CanvasAudit.created_at)).first()

    if not audit:
        raise router.not_found_error(
            resource="CodingCanvas",
            resource_id=canvas_id
        )

    return router.success_response(
        data=audit.audit_metadata,
        message="Coding canvas retrieved successfully"
    )
