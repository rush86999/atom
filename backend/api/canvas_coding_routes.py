"""Coding Canvas API Routes"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.canvas_coding_service import CodingCanvasService
from core.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/canvas/coding", tags=["canvas_coding"])


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
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


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
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


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
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


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
        raise HTTPException(status_code=404, detail="Coding canvas not found")

    return audit.audit_metadata
