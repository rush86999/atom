"""Email Canvas API Routes"""
import logging
from typing import Any, Dict, List, Optional
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.canvas_email_service import EmailCanvasService
from core.database import get_db

logger = logging.getLogger(__name__)
router = BaseAPIRouter(prefix="/api/canvas/email", tags=["canvas_email"])


class CreateEmailRequest(BaseModel):
    user_id: str
    subject: str
    recipients: List[str]
    canvas_id: Optional[str] = None
    agent_id: Optional[str] = None
    layout: str = "conversation"
    template: Optional[str] = None


class AddMessageRequest(BaseModel):
    user_id: str
    from_email: str
    to_emails: List[str]
    subject: str
    body: str
    attachments: Optional[List[Dict]] = None


class SaveDraftRequest(BaseModel):
    user_id: str
    to_emails: List[str]
    cc_emails: Optional[List[str]] = None
    subject: str = ""
    body: str = ""


class CategorizeRequest(BaseModel):
    user_id: str
    category: str
    color: Optional[str] = None


@router.post("/create")
async def create_email_canvas(request: CreateEmailRequest, db: Session = Depends(get_db)):
    """Create a new email canvas."""
    service = EmailCanvasService(db)
    result = service.create_email_canvas(
        user_id=request.user_id,
        subject=request.subject,
        recipients=request.recipients,
        canvas_id=request.canvas_id,
        agent_id=request.agent_id,
        layout=request.layout,
        template=request.template
    )
    if not result.get("success"):
        raise router.error_response(
            error_code="EMAIL_CANVAS_CREATE_FAILED",
            message=result.get("error", "Failed to create email canvas"),
            status_code=400
        )
    return result


@router.post("/{canvas_id}/message")
async def add_message(canvas_id: str, request: AddMessageRequest, db: Session = Depends(get_db)):
    """Add a message to an email thread."""
    service = EmailCanvasService(db)
    result = service.add_message_to_thread(
        canvas_id=canvas_id,
        user_id=request.user_id,
        from_email=request.from_email,
        to_emails=request.to_emails,
        subject=request.subject,
        body=request.body,
        attachments=request.attachments
    )
    if not result.get("success"):
        raise router.error_response(
            error_code="EMAIL_MESSAGE_ADD_FAILED",
            message=result.get("error", "Failed to add message to email thread"),
            status_code=400
        )
    return result


@router.post("/{canvas_id}/draft")
async def save_draft(canvas_id: str, request: SaveDraftRequest, db: Session = Depends(get_db)):
    """Save an email draft."""
    service = EmailCanvasService(db)
    result = service.save_draft(
        canvas_id=canvas_id,
        user_id=request.user_id,
        to_emails=request.to_emails,
        cc_emails=request.cc_emails,
        subject=request.subject,
        body=request.body
    )
    if not result.get("success"):
        raise router.error_response(
            error_code="EMAIL_DRAFT_SAVE_FAILED",
            message=result.get("error", "Failed to save email draft"),
            status_code=400
        )
    return result


@router.post("/{canvas_id}/categorize")
async def categorize_email(canvas_id: str, request: CategorizeRequest, db: Session = Depends(get_db)):
    """Categorize an email."""
    service = EmailCanvasService(db)
    result = service.categorize_email(
        canvas_id=canvas_id,
        user_id=request.user_id,
        category=request.category,
        color=request.color
    )
    if not result.get("success"):
        raise router.error_response(
            error_code="EMAIL_CATEGORIZE_FAILED",
            message=result.get("error", "Failed to categorize email"),
            status_code=400
        )
    return result


@router.get("/{canvas_id}")
async def get_email_canvas(canvas_id: str, db: Session = Depends(get_db)):
    """Get an email canvas by ID."""
    from sqlalchemy import desc

    from core.models import CanvasAudit

    audit = db.query(CanvasAudit).filter(
        CanvasAudit.canvas_id == canvas_id,
        CanvasAudit.canvas_type == "email"
    ).order_by(desc(CanvasAudit.created_at)).first()

    if not audit:
        raise router.not_found_error("Email Canvas", canvas_id)

    return audit.audit_metadata
