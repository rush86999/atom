"""Email Canvas API Routes"""
import logging
import uuid
from typing import Any, Dict, List, Optional
from fastapi import Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user, User
from core.deployment_audience import require_pilot_user
from core.base_routes import BaseAPIRouter
from core.canvas_email_service import EmailCanvasService
from core.database import get_db
from core.personal_scope import resolve_tenant_id

logger = logging.getLogger(__name__)
router = BaseAPIRouter(prefix="/api/canvas/email", tags=["canvas_email"], dependencies=[Depends(require_pilot_user)])


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


def _require_email_actor(db, current_user, canvas_id: Optional[str] = None):
    """Resolve the current authoritative actor and exact canvas scope.

    Reuses the shared Canvas authority adapter: inactive API/status, moved
    actor scope, foreign/moved target and missing tenant all refuse before any
    create/save/read effect.
    """
    from core.canvas_authority import (
        CanvasAuthorityError, require_active_actor, require_canvas_read,
    )

    try:
        actor = require_active_actor(db, str(current_user.id))
        if canvas_id:
            require_canvas_read(db, canvas_id, actor)
    except CanvasAuthorityError as exc:
        raise HTTPException(status_code=exc.status_code, detail={
            "error": exc.code,
            "message": str(exc),
        }) from exc
    return actor


def _split_recipients(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value or "").split(",")
            if item.strip()]


def _native_email_content(material: Dict[str, Any], request) -> Dict[str, Any]:
    """Compose the native email dict while preserving thread/attachment data."""
    content = material.get("content")
    base = dict(content) if isinstance(content, dict) else {}
    details = material.get("details") if isinstance(
        material.get("details"), dict) else {}
    prior_draft = details.get("draft") if isinstance(
        details.get("draft"), dict) else {}
    if "attachments" in base:
        attachments = base.get("attachments") or []
    elif "attachments" in prior_draft:
        attachments = prior_draft.get("attachments") or []
    elif "attachments" in details:
        attachments = details.get("attachments") or []
    else:
        attachments = []
    draft_id = (
        str(prior_draft.get("draft_id") or base.get("draft_id") or "")
        or str(uuid.uuid4())
    )
    to_emails = list(request.to_emails or [])
    cc_emails = list(request.cc_emails or [])
    subject = str(request.subject or "")
    body = str(request.body or "")
    native = dict(base)
    native.update({
        "to": ", ".join(to_emails),
        "cc": ", ".join(cc_emails),
        "subject": subject,
        "body": body,
        "attachments": attachments,
        "draft": {
            "draft_id": draft_id,
            "to_emails": to_emails,
            "cc_emails": cc_emails,
            "subject": subject,
            "body": body,
            "attachments": attachments,
        },
    })
    for key in (
        "thread_id", "in_reply_to", "references", "source_message_id",
        "source_identity", "imported_from", "imported_to", "imported_cc",
        "imported_subject", "imported_sent_at", "template",
    ):
        if key in native:
            continue
        value = details.get(key)
        if value in (None, "", [], {}):
            value = prior_draft.get(key)
        if value not in (None, "", [], {}):
            native[key] = value
    return native


def _email_canvas_view(material: Dict[str, Any]) -> Dict[str, Any]:
    """Project visible canvas content into the native email read shape.

    Canonical top-level ``content`` fields win by KEY PRESENCE (an explicit
    empty string/list is a value, not a reason to fall back). Nested/legacy
    ``draft`` metadata is only used when the corresponding key is absent.
    Thread and attachment identity come from the same visible material; no
    implicit reattachment, send or second store.
    """
    details = material.get("details") if isinstance(
        material.get("details"), dict) else {}
    content = material.get("content")
    if not isinstance(content, dict):
        return dict(details)
    draft = content.get("draft") if isinstance(
        content.get("draft"), dict) else {}
    prior_draft = details.get("draft") if isinstance(
        details.get("draft"), dict) else {}

    if "to" in content:
        to_emails = _split_recipients(content.get("to"))
    elif "to_emails" in draft:
        to_emails = list(draft.get("to_emails") or [])
    elif "to_emails" in prior_draft:
        to_emails = list(prior_draft.get("to_emails") or [])
    else:
        to_emails = []

    if "cc" in content:
        cc_emails = _split_recipients(content.get("cc"))
    elif "cc_emails" in draft:
        cc_emails = list(draft.get("cc_emails") or [])
    elif "cc_emails" in prior_draft:
        cc_emails = list(prior_draft.get("cc_emails") or [])
    else:
        cc_emails = []

    if "subject" in content:
        subject = str(content.get("subject") or "")
    elif "subject" in draft:
        subject = str(draft.get("subject") or "")
    else:
        subject = str(prior_draft.get("subject") or "")

    if "body" in content:
        body = str(content.get("body") or "")
    elif "body" in draft:
        body = str(draft.get("body") or "")
    else:
        body = str(prior_draft.get("body") or "")

    if "attachments" in content:
        attachments = list(content.get("attachments") or [])
    elif "attachments" in draft:
        attachments = list(draft.get("attachments") or [])
    elif "attachments" in prior_draft:
        attachments = list(prior_draft.get("attachments") or [])
    elif "attachments" in details:
        attachments = list(details.get("attachments") or [])
    else:
        attachments = []

    draft_id = str(
        draft.get("draft_id")
        or prior_draft.get("draft_id")
        or content.get("draft_id")
        or ""
    )
    if "messages" in content:
        messages = list(content.get("messages") or [])
    elif "messages" in details:
        messages = list(details.get("messages") or [])
    else:
        messages = []

    view = dict(details)
    view.update({
        "canvas_type": "email",
        "component_type": details.get("component_type") or "compose_form",
        "subject": subject,
        "draft": {
            "draft_id": draft_id,
            "to_emails": to_emails,
            "cc_emails": cc_emails,
            "subject": subject,
            "body": body,
            "attachments": attachments,
        },
        "attachments": attachments,
        "messages": messages,
    })
    if "thread_id" in content:
        view["thread_id"] = content.get("thread_id")
    else:
        thread_id = (
            draft.get("thread_id")
            or prior_draft.get("thread_id")
            or details.get("thread_id")
        )
        if thread_id:
            view["thread_id"] = thread_id
    for key in (
        "in_reply_to", "references", "source_message_id", "source_identity",
        "imported_from", "imported_to", "imported_cc", "imported_subject",
        "imported_sent_at", "template", "content",
    ):
        if key in content:
            value = content.get(key)
        else:
            value = details.get(key)
        if value not in (None, "", [], {}):
            view[key] = value
    return view


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
    # Required for public draft edits: the audit row the client planned
    # against. A missing token is a typed 409; a stale token is a 409
    # conflict from the shared canvas write service.
    expected_prior_audit_id: Optional[str] = None
    # Optional stable identity for an idempotent retry of the same edit.
    operation_id: Optional[str] = None


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
    attachment_ids: Optional[List[str]] = None
    # Grounded-send gate (Phase 4): supervisor override for an enforce-mode
    # block — recorded on the send audit row, never silent.
    override_grounding: bool = False
    # Mixed-thread leak guard override: send even though the body quotes
    # internal-only discussion from the thread. Supervisor decision.
    override_internal_quote: bool = False
    # Threaded reply: the composer's resolve-reply prefills this (Outlook
    # conversationId) so the send lands in the original thread. The visible
    # To/Cc/Subject still apply via the Graph reply message override.
    thread_id: Optional[str] = None
    reply_all: bool = False


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
    if request.canvas_id:
        _get_owned_email_canvas_or_error(db, request.canvas_id, current_user)
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
        attachment_ids=request.attachment_ids,
        override_grounding=request.override_grounding,
        override_internal_quote=request.override_internal_quote,
        thread_id=request.thread_id,
        reply_all=request.reply_all,
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
    """Create a new email canvas in the current actor's authoritative scope."""
    actor = _require_email_actor(db, current_user)
    service = EmailCanvasService(db)
    result = service.create_email_canvas(
        user_id=current_user.id,
        subject=request.subject,
        recipients=request.recipients,
        canvas_id=request.canvas_id,
        agent_id=request.agent_id,
        layout=request.layout,
        template=request.template,
        tenant_id=str(actor.get("tenant_id") or ""),
        workspace_id=str(actor.get("workspace_id") or ""),
    )
    if not result.get("success"):
        raise router.error_response(
            error_code="EMAIL_CANVAS_CREATE_FAILED",
            message=result.get("error", "Failed to create email canvas"),
            status_code=400
        )
    return result


@router.post("/{canvas_id}/import-eml")
async def import_eml_canvas(
    canvas_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Import an EML into this canvas as a received message + reply draft.

    Import never sends. Attachment records are stored as source evidence and
    marked non-sendable, so a later reply cannot silently return them.
    """
    _get_owned_email_canvas_or_error(db, canvas_id, current_user)
    content = await file.read()
    max_bytes = int(__import__("os").getenv("MAX_UPLOAD_BYTES", "52428800"))
    if len(content) > max_bytes:
        raise router.validation_error(field="file", message="File too large")
    result = EmailCanvasService(db).import_eml(
        canvas_id=canvas_id,
        user_id=str(current_user.id),
        content=content,
        filename=file.filename or "message.eml",
    )
    if not result.get("success"):
        raise router.error_response(
            error_code="EMAIL_EML_IMPORT_FAILED",
            message=result.get("error", "Failed to import EML"),
            status_code=400,
        )
    return result


@router.post("/{canvas_id}/message")
async def add_message(canvas_id: str, request: AddMessageRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Add a message to an email thread."""
    _get_owned_email_canvas_or_error(db, canvas_id, current_user)
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
    """Save an email draft through the shared verified canvas writer.

    Public edits require ``expected_prior_audit_id``. The existing
    ``canvas_write_service.update_canvas_verified`` owns the transactional
    authority claim, optimistic concurrency, append/readback and uncertainty
    envelope; this route only composes the native email payload.
    """
    from core.canvas_write_service import update_canvas_verified
    from tools.canvas_crud_tool import visible_canvas_material

    actor = _require_email_actor(db, current_user, canvas_id)
    material = visible_canvas_material(db, canvas_id)
    if not material.get("success"):
        raise HTTPException(status_code=404, detail="Email canvas not found")
    prior = str(material.get("revision_audit_id") or "")
    expected = str(request.expected_prior_audit_id or "").strip()
    if not expected:
        raise HTTPException(status_code=409, detail={
            "error": "expected_prior_audit_id_required",
            "message": (
                "Saving an email draft requires the audit id the edit was "
                "planned against."),
            "current_audit_id": prior,
        })
    content = _native_email_content(material, request)
    result = await update_canvas_verified(
        user_id=str(current_user.id),
        canvas_id=canvas_id,
        content=content,
        canvas_type="email",
        operation_id=request.operation_id,
        expected_prior_audit_id=expected,
        tenant_id=str(actor.get("tenant_id") or ""),
        workspace_id=str(actor.get("workspace_id") or ""),
    )
    if result.get("status") == "refused":
        status = int(result.get("http_status") or (
            409 if result.get("conflict") else 400))
        raise HTTPException(status_code=status, detail={
            "error": "email_draft_save_refused",
            "message": str(
                result.get("error") or "The draft save was refused."),
            "current_audit_id": prior,
        })
    result.setdefault("draft_id", content["draft"]["draft_id"])
    return result


@router.post("/{canvas_id}/categorize")
async def categorize_email(canvas_id: str, request: CategorizeRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Categorize an email."""
    _get_owned_email_canvas_or_error(db, canvas_id, current_user)
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
    """Read the exact visible email draft under the shared Canvas authority."""
    from tools.canvas_crud_tool import visible_canvas_material

    _require_email_actor(db, current_user, canvas_id)
    material = visible_canvas_material(db, canvas_id)
    if not material.get("success"):
        raise HTTPException(status_code=404, detail="Email canvas not found")
    return _email_canvas_view(material)


# ─── Attachment CRUD (docs/canvas/EMAIL_ATTACHMENT_CRUD_PLAN.md §5) ────────


@router.get("/{canvas_id}/attachments")
async def list_email_attachments(
    canvas_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Attachment records on the canvas (metadata only — bytes stream on download)."""
    _get_owned_email_canvas_or_error(db, canvas_id, current_user)
    result = EmailCanvasService(db).list_attachments(canvas_id, str(current_user.id))
    if not result.get("success"):
        raise router.error_response(
            error_code="EMAIL_ATTACHMENT_LIST_FAILED",
            message=result.get("error", "Failed to list attachments"),
            status_code=400,
        )
    return result


@router.post("/{canvas_id}/attachments")
async def upload_email_attachments(
    canvas_id: str,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stage uploads onto a draft canvas. Files live in the staged store
    until send (which uploads them to the mailbox) or removal."""
    _get_owned_email_canvas_or_error(db, canvas_id, current_user)
    payloads = []
    for f in files or []:
        content = await f.read()
        payloads.append(
            {
                "filename": f.filename or "",
                "content_bytes": content,
                "content_type": f.content_type or "",
            }
        )
    result = EmailCanvasService(db).stage_attachments(
        canvas_id, str(current_user.id), payloads
    )
    if not result.get("success"):
        raise router.error_response(
            error_code="EMAIL_ATTACHMENT_UPLOAD_FAILED",
            message=result.get("error", "Failed to stage attachments"),
            status_code=400,
        )
    return result


@router.get("/{canvas_id}/attachments/{attachment_id}/download")
async def download_email_attachment(
    canvas_id: str,
    attachment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stream attachment bytes to the owner. Received attachments proxy from
    the mailbox (never persisted server-side); staged ones read from disk."""
    _get_owned_email_canvas_or_error(db, canvas_id, current_user)
    resolved = await EmailCanvasService(db).get_attachment_bytes(
        canvas_id, str(current_user.id), attachment_id
    )
    if not resolved or resolved.get("bytes") is None:
        raise router.not_found_error("Email Attachment", attachment_id)
    record = resolved["record"]
    return StreamingResponse(
        iter([resolved["bytes"]]),
        media_type=record.get("content_type") or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{record.get("filename", "attachment")}"',
            "Content-Length": str(len(resolved["bytes"])),
        },
    )


@router.get("/{canvas_id}/attachments/{attachment_id}/preview")
async def preview_email_attachment(
    canvas_id: str,
    attachment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Extracted-text excerpt for the canvas preview pane (Docling-backed;
    returns null preview when the format has no text layer)."""
    _get_owned_email_canvas_or_error(db, canvas_id, current_user)
    resolved = await EmailCanvasService(db).get_attachment_bytes(
        canvas_id, str(current_user.id), attachment_id
    )
    if not resolved or resolved.get("bytes") is None:
        raise router.not_found_error("Email Attachment", attachment_id)
    record = resolved["record"]
    filename = record.get("filename") or "attachment"
    excerpt = None
    try:
        from core.auto_document_ingestion import DocumentParser

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        text = await DocumentParser().parse_document(resolved["bytes"], ext, filename)
        if text:
            excerpt = text[:4000]
    except Exception as e:
        logger.warning(f"Attachment preview failed for {attachment_id}: {e}")
    return {
        "success": True,
        "attachment_id": attachment_id,
        "filename": filename,
        "preview": excerpt,
    }


@router.delete("/{canvas_id}/attachments/{attachment_id}")
async def delete_email_attachment(
    canvas_id: str,
    attachment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove an attachment: staged files are deleted, received ones are
    detached from the canvas view (mailbox copy untouched)."""
    _get_owned_email_canvas_or_error(db, canvas_id, current_user)
    result = EmailCanvasService(db).remove_attachment(
        canvas_id, str(current_user.id), attachment_id
    )
    if not result.get("success"):
        raise router.error_response(
            error_code="EMAIL_ATTACHMENT_DELETE_FAILED",
            message=result.get("error", "Failed to remove attachment"),
            status_code=400,
        )
    return result


@router.post("/{canvas_id}/attachments/{attachment_id}/ingest")
async def ingest_email_attachment(
    canvas_id: str,
    attachment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Index one attachment's text into the documents memory index
    ("Add to memory"); status lands on the attachment record via canvas:update."""
    _get_owned_email_canvas_or_error(db, canvas_id, current_user)
    result = await EmailCanvasService(db).ingest_attachment(
        canvas_id, str(current_user.id), attachment_id
    )
    if not result.get("success"):
        raise router.error_response(
            error_code="EMAIL_ATTACHMENT_INGEST_FAILED",
            message=str(result.get("ingestion", {}).get("reason") or result.get("error") or "Failed to ingest attachment"),
            status_code=400,
            details=result,
        )
    return result
