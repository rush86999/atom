"""Terminal Canvas API Routes"""
import logging
from typing import Any, Dict, Optional
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.canvas_terminal_service import TerminalCanvasService
from core.database import get_db

logger = logging.getLogger(__name__)
router = BaseAPIRouter(prefix="/api/canvas/terminal", tags=["canvas_terminal"])


class CreateTerminalRequest(BaseModel):
    user_id: str
    command: str
    canvas_id: Optional[str] = None
    agent_id: Optional[str] = None
    working_dir: str = "."


class AddOutputRequest(BaseModel):
    user_id: str
    command: str
    output: str
    exit_code: int = 0


@router.post("/create")
async def create_terminal_canvas(request: CreateTerminalRequest, db: Session = Depends(get_db)):
    """Create a new terminal canvas."""
    service = TerminalCanvasService(db)
    result = service.create_terminal_canvas(
        user_id=request.user_id,
        command=request.command,
        canvas_id=request.canvas_id,
        agent_id=request.agent_id,
        working_dir=request.working_dir
    )
    if not result.get("success"):
        raise router.error_response(
            error_code="TERMINAL_CANVAS_CREATE_FAILED",
            message=result.get("error", "Failed to create terminal canvas"),
            status_code=400
        )

    return router.success_response(
        data=result,
        message="Terminal canvas created successfully"
    )


@router.post("/{canvas_id}/output")
async def add_output(canvas_id: str, request: AddOutputRequest, db: Session = Depends(get_db)):
    """Add command output to the terminal."""
    service = TerminalCanvasService(db)
    result = service.add_output(
        canvas_id=canvas_id,
        user_id=request.user_id,
        command=request.command,
        output=request.output,
        exit_code=request.exit_code
    )
    if not result.get("success"):
        raise router.error_response(
            error_code="ADD_OUTPUT_FAILED",
            message=result.get("error", "Failed to add output"),
            status_code=400
        )

    return router.success_response(
        data=result,
        message="Command output added successfully"
    )


@router.get("/{canvas_id}")
async def get_terminal_canvas(canvas_id: str, db: Session = Depends(get_db)):
    """Get a terminal canvas."""
    from sqlalchemy import desc

    from core.models import CanvasAudit

    audit = db.query(CanvasAudit).filter(
        CanvasAudit.canvas_id == canvas_id,
        CanvasAudit.canvas_type == "terminal"
    ).order_by(desc(CanvasAudit.created_at)).first()

    if not audit:
        raise router.not_found_error(
            resource="TerminalCanvas",
            resource_id=canvas_id
        )

    return router.success_response(
        data=audit.audit_metadata,
        message="Terminal canvas retrieved successfully"
    )
