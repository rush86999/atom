"""Email Canvas API Routes"""
import logging
from typing import Any, Dict, List, Optional
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user, User
from core.base_routes import BaseAPIRouter
from core.canvas_email_service import EmailCanvasService
from core.database import get_db
from core.personal_scope import resolve_tenant_id

logger = logging.getLogger(__name__)
router = BaseAPIRouter(prefix="/api/canvas/email", tags=["canvas_email"])


def _get_owned_email_canvas_or_error(db, canvas_id: str, current_user) -> None:
    """Ownership gate for email canvases (R66).

    Email canvases hold drafts/messages; only the creator may read/write.
    """
    from sqlalchemy import asc

    from core.models import CanvasAudit

    first = db.query(CanvasAudit).filter(
        CanvasAudit.canvas_id == canvas_id,
        CanvasAudit.canvas_type == "email"
    ).order_by(asc(CanvasAudit.created_at)).first()
    if not first:
        raise router.not_found_error("Email Canvas", canvas_id)
    if first.user_id != current_user.id:
        raise router.permission_denied_error(
            action="access_email_canvas",
            resource="EmailCanvas",
        )


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


class SendEmailRequest(BaseModel):
    to: List[str]
    cc: Optional[List[str]] = None
    subject: str = ""
    body: str = ""
    canvas_id: Optional[str] = None
    agent_id: Optional[str] = None


class SetSignatureRequest(BaseModel):
    signature: str


@router.get("/signature")
async def get_email_signature(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The composer's default signature: a stored app override, else the
    connected integration's default (recovered from sent mail). signature
    is null when neither exists."""
    service = EmailCanvasService(db)
    return await service.get_signature(str(current_user.id))


@router.put("/signature")
async def set_email_signature(
    request: SetSignatureRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Store (or clear, on empty) the signature override. Emptying it falls
    the composer back to the integration-derived default."""
    service = EmailCanvasService(db)
    return service.set_signature(str(current_user.id), request.signature)


@router.get("/resolve-reply")
async def resolve_reply_recipients(
    subject: str = "",
    body: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Prefill To/Cc for a reply draft: locate the original thread by its
    prefix-stripped subject (the draft body's greeting is used as a
    secondary signal when the subject was agent-invented). Returns to=None
    (never errors) when no thread matches or no mailbox is connected."""
    service = EmailCanvasService(db)
    return await service.resolve_reply_recipients(
        str(current_user.id), subject, body_hint=(body or "")[:500]
    )


@router.get("/contacts")
async def search_email_contacts(
    q: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Recipient suggestions for the composer's To/Cc autocomplete.

    Backed by the connected mailbox's address book (the same account Send
    dispatches through). Returns an empty list — never an error — when no
    mailbox is connected, so the composer degrades to plain free-text.
    """
    service = EmailCanvasService(db)
    return await service.suggest_contacts(str(current_user.id), query=q)


@router.post("/send")
async def send_email_canvas(
    request: SendEmailRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send the composed email through the deterministic email policy.

    Human-initiated send: the user's click authorizes allow/approve decisions;
    BLOCK (restricted-sensitivity content) always refuses. Every attempt is
    stamped into CanvasAudit (action_type="email_send") and broadcast as a
    canvas:update so agents/users co-editing see it live.
    """
    service = EmailCanvasService(db)
    result = await service.send_email(
        canvas_id=request.canvas_id,
        user_id=current_user.id,
        to_emails=request.to,
        cc_emails=request.cc,
        subject=request.subject,
        body=request.body,
        agent_id=request.agent_id,
        tenant_id=resolve_tenant_id(current_user),
    )
    if not result.get("success"):
        raise router.error_response(
            error_code="EMAIL_SEND_FAILED",
            message=result.get("error", "Failed to send email"),
            status_code=400,
            details=result,
        )
    return result


@router.post("/create")
async def create_email_canvas(request: CreateEmailRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a new email canvas."""
    service = EmailCanvasService(db)
    result = service.create_email_canvas(
        user_id=current_user.id,
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
async def add_message(canvas_id: str, request: AddMessageRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Add a message to an email thread."""
    service = EmailCanvasService(db)
    result = service.add_message_to_thread(
        canvas_id=canvas_id,
        user_id=current_user.id,
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
async def save_draft(canvas_id: str, request: SaveDraftRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Save an email draft."""
    service = EmailCanvasService(db)
    result = service.save_draft(
        canvas_id=canvas_id,
        user_id=current_user.id,
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
async def categorize_email(canvas_id: str, request: CategorizeRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Categorize an email."""
    service = EmailCanvasService(db)
    result = service.categorize_email(
        canvas_id=canvas_id,
        user_id=current_user.id,
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
async def get_email_canvas(canvas_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get an email canvas by ID."""
    from sqlalchemy import desc

    from core.models import CanvasAudit

    # R66: only the canvas owner may read email canvas state.
    _get_owned_email_canvas_or_error(db, canvas_id, current_user)

    audit = db.query(CanvasAudit).filter(
        CanvasAudit.canvas_id == canvas_id,
        CanvasAudit.canvas_type == "email"
    ).order_by(desc(CanvasAudit.created_at)).first()

    if not audit:
        raise router.not_found_error("Email Canvas", canvas_id)

    return audit.details_json or {}
