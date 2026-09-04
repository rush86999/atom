"""PDF Canvas API Routes.

Same ownership + error conventions as canvas_email_routes.py: the service
does the owner check and the route maps the error shape onto 4xx (404
missing / 403 not-owner / 409 version conflict or immutable / 400 policy).
All state reads/writes go through PdfCanvasService; bytes stream through
these routes but never persist anywhere but the content-addressed blob
store.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user, User
from core.base_routes import BaseAPIRouter
from core.pdf_canvas_service import PdfCanvasService
from core.database import get_db
from core.personal_scope import resolve_tenant_id

logger = logging.getLogger(__name__)
router = BaseAPIRouter(prefix="/api/canvas/pdf", tags=["canvas_pdf"])


class CreateBlankRequest(BaseModel):
    title: Optional[str] = None
    filename: Optional[str] = None


class PageOpsRequest(BaseModel):
    """Full page map: [{"src_index": 0, "rotation": 0}, ...] — reorder by
    order, delete by omission, rotate by absolute degrees."""
    pages: List[dict]
    base_hash: Optional[str] = None
    agent_id: Optional[str] = None


class MergeCanvasRequest(BaseModel):
    from_canvas_id: str
    agent_id: Optional[str] = None


class AttachToEmailRequest(BaseModel):
    email_canvas_id: Optional[str] = None
    agent_id: Optional[str] = None
    flatten: bool = False


class LifecycleRequest(BaseModel):
    agent_id: Optional[str] = None


class FormValuesRequest(BaseModel):
    values: Dict[str, Any]
    base_hash: Optional[str] = None
    agent_id: Optional[str] = None


class AnnotateRequest(BaseModel):
    items: List[Dict[str, Any]]
    agent_id: Optional[str] = None


class RedactRequest(BaseModel):
    items: List[Dict[str, Any]]  # [{page, text}] — exact-match content removal
    agent_id: Optional[str] = None


class SignRequest(BaseModel):
    page: int = 0
    signature_lines: List[str]
    rect: List[float] = [72, 600, 272, 650]
    label: str = ""
    agent_id: Optional[str] = None


class GenerateRequest(BaseModel):
    template: str  # quote | invoice | letter
    doc: Dict[str, Any]
    title: Optional[str] = None
    agent_id: Optional[str] = None


class ArchiveRequest(BaseModel):
    folder_path: str = ""
    agent_id: Optional[str] = None


class SendToDocuSignRequest(BaseModel):
    signer_email: str
    signer_name: str
    agent_id: Optional[str] = None


def _map_service_error(result: dict, fallback_code: str, fallback_message: str):
    error = str(result.get("error", fallback_message))
    if result.get("conflict") or result.get("immutable"):
        raise router.error_response(
            error_code="PDF_VERSION_CONFLICT" if result.get("conflict") else "PDF_IMMUTABLE",
            message=error,
            status_code=409,
            details=result,
        )
    if "not found" in error.lower() and "content stream" not in error.lower():
        # precise 404: only the canvas-missing phrase — a redaction miss also
        # says "not found" but is a 400 policy refusal, not a missing resource
        raise router.not_found_error("PDF Canvas", error)
    if "owner" in error.lower():
        raise router.permission_denied_error(action="access_pdf_canvas", resource="PdfCanvas")
    raise router.error_response(
        error_code=fallback_code,
        message=error,
        status_code=400,
        details=result,
    )


@router.post("/create")
async def create_blank_pdf_canvas(
    request: CreateBlankRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a PDF canvas from a blank single-page document."""
    result = PdfCanvasService(db).create_pdf_canvas(
        user_id=str(current_user.id),
        tenant_id=resolve_tenant_id(current_user),
        title=request.title,
        filename=request.filename,
    )
    if not result.get("success"):
        _map_service_error(result, "PDF_CANVAS_CREATE_FAILED", "Failed to create PDF canvas")
    return result


@router.post("/create/upload")
async def create_pdf_canvas_from_upload(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a PDF canvas from an uploaded .pdf (corrupt/encrypted files are
    rejected here, at the boundary — never mid-lifecycle)."""
    content = await file.read()
    result = PdfCanvasService(db).create_pdf_canvas(
        user_id=str(current_user.id),
        tenant_id=resolve_tenant_id(current_user),
        title=title,
        filename=file.filename,
        content_bytes=content,
    )
    if not result.get("success"):
        _map_service_error(result, "PDF_CANVAS_UPLOAD_FAILED", "Failed to create PDF canvas from upload")
    return result


@router.get("/{canvas_id}/file")
async def download_pdf_canvas_file(
    canvas_id: str,
    hash: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stream the current version's bytes (or a named version's, by hash) —
    this is what the in-browser viewer renders."""
    resolved = PdfCanvasService(db).get_bytes(canvas_id, str(current_user.id), hash)
    if not resolved:
        raise router.not_found_error("PDF Canvas or version", canvas_id)
    filename = (resolved["state"].get("file") or {}).get("filename") or "document.pdf"
    return StreamingResponse(
        iter([resolved["bytes"]]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Content-Length": str(len(resolved["bytes"])),
            "X-Pdf-Version-Hash": resolved["hash"],
        },
    )


@router.post("/{canvas_id}/pages")
async def apply_pdf_page_ops(
    canvas_id: str,
    request: PageOpsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Commit the page map (reorder/delete/rotate) as a new audited version."""
    result = PdfCanvasService(db).apply_page_ops(
        canvas_id=canvas_id,
        user_id=str(current_user.id),
        pages=request.pages,
        base_hash=request.base_hash,
        agent_id=request.agent_id,
    )
    if not result.get("success"):
        _map_service_error(result, "PDF_PAGE_OPS_FAILED", "Failed to apply page operations")
    return result


@router.post("/{canvas_id}/merge/upload")
async def merge_pdf_upload(
    canvas_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Append every page of an uploaded PDF after the canvas's pages."""
    content = await file.read()
    result = PdfCanvasService(db).merge_upload(
        canvas_id=canvas_id,
        user_id=str(current_user.id),
        filename=file.filename or "merged.pdf",
        content_bytes=content,
    )
    if not result.get("success"):
        _map_service_error(result, "PDF_MERGE_FAILED", "Failed to merge PDF")
    return result


@router.post("/{canvas_id}/merge/canvas")
async def merge_pdf_from_canvas(
    canvas_id: str,
    request: MergeCanvasRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Append every page of another PDF canvas owned by the same user."""
    result = PdfCanvasService(db).merge_from_canvas(
        canvas_id=canvas_id,
        user_id=str(current_user.id),
        from_canvas_id=request.from_canvas_id,
        agent_id=request.agent_id,
    )
    if not result.get("success"):
        _map_service_error(result, "PDF_MERGE_FAILED", "Failed to merge PDF canvas")
    return result


@router.post("/{canvas_id}/extract-text")
async def extract_pdf_text(
    canvas_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Per-page text of the current version (reading pane; agent read-back
    rides the same path in P2)."""
    result = PdfCanvasService(db).extract_text(canvas_id, str(current_user.id))
    if not result.get("success"):
        _map_service_error(result, "PDF_EXTRACT_FAILED", "Failed to extract text")
    return result


@router.post("/{canvas_id}/lifecycle/{transition}")
async def pdf_lifecycle_transition(
    canvas_id: str,
    transition: str,
    request: LifecycleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Human lifecycle moves: submit-review, approve (content becomes
    immutable), reopen, archive. The state machine is enforced in the
    service; agent callers go through the maturity-gated tools instead —
    a human click here is the authority the proposals route back to."""
    result = PdfCanvasService(db).transition(
        canvas_id, str(current_user.id), transition, agent_id=request.agent_id,
    )
    if not result.get("success"):
        _map_service_error(result, "PDF_LIFECYCLE_FAILED", f"Failed to {transition}")
    return result


@router.post("/{canvas_id}/attach-to-email")
async def attach_pdf_to_email(
    canvas_id: str,
    request: AttachToEmailRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stage the current version onto an email canvas (a fresh draft when
    none is named) through the existing staged-attachment path. The email
    canvas opens with the attachment already in its strip; Send runs the
    normal email policy."""
    result = PdfCanvasService(db).attach_to_email(
        canvas_id=canvas_id,
        user_id=str(current_user.id),
        email_canvas_id=request.email_canvas_id,
        agent_id=request.agent_id,
        flatten=request.flatten,
    )
    if not result.get("success"):
        _map_service_error(result, "PDF_ATTACH_FAILED", "Failed to attach PDF to email")
    return result


# ── P3: trust operations ─────────────────────────────────────────────────


@router.post("/create/generate")
async def generate_pdf_canvas(
    request: GenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a PDF canvas from structured business data (quote/invoice/
    letter templates) — deterministic rendering, audited like any create."""
    result = PdfCanvasService(db).generate(
        user_id=str(current_user.id),
        tenant_id=resolve_tenant_id(current_user),
        template=request.template,
        doc=request.doc,
        title=request.title,
        agent_id=request.agent_id,
    )
    if not result.get("success"):
        _map_service_error(result, "PDF_GENERATE_FAILED", "Failed to generate PDF")
    return result


@router.get("/{canvas_id}/form-fields")
async def get_pdf_form_fields(
    canvas_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """AcroForm field inventory of the current version."""
    result = PdfCanvasService(db).get_form_fields(canvas_id, str(current_user.id))
    if not result.get("success"):
        _map_service_error(result, "PDF_FORM_READ_FAILED", "Failed to read form fields")
    return result


@router.post("/{canvas_id}/form")
async def set_pdf_form_fields(
    canvas_id: str,
    request: FormValuesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fill AcroForm values as a new version (fields stay interactive)."""
    result = PdfCanvasService(db).set_form_fields(
        canvas_id, str(current_user.id), request.values,
        base_hash=request.base_hash, agent_id=request.agent_id,
    )
    if not result.get("success"):
        _map_service_error(result, "PDF_FORM_FILL_FAILED", "Failed to fill form")
    return result


@router.post("/{canvas_id}/flatten")
async def flatten_pdf_form(
    canvas_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Burn form values into the content and strip the interactive layer."""
    result = PdfCanvasService(db).flatten_form(canvas_id, str(current_user.id))
    if not result.get("success"):
        _map_service_error(result, "PDF_FLATTEN_FAILED", "Failed to flatten form")
    return result


@router.post("/{canvas_id}/annotate")
async def annotate_pdf(
    canvas_id: str,
    request: AnnotateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add real PDF annotations (note/freetext/rect) as a new version."""
    result = PdfCanvasService(db).annotate(
        canvas_id, str(current_user.id), request.items, agent_id=request.agent_id,
    )
    if not result.get("success"):
        _map_service_error(result, "PDF_ANNOTATE_FAILED", "Failed to annotate")
    return result


@router.post("/{canvas_id}/redact")
async def redact_pdf(
    canvas_id: str,
    request: RedactRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """TRUE redaction: content-stream text removal + verification. Refuses
    the whole op when any target can't be removed — no partial redactions."""
    result = PdfCanvasService(db).redact(
        canvas_id, str(current_user.id), request.items, agent_id=request.agent_id,
    )
    if not result.get("success"):
        _map_service_error(result, "PDF_REDACT_FAILED", "Failed to redact")
    return result


@router.post("/{canvas_id}/sign")
async def sign_pdf(
    canvas_id: str,
    request: SignRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Internal signing stamp (signature text + attribution). External
    cryptographic signing runs through the DocuSign envelope path."""
    result = PdfCanvasService(db).stamp_signature(
        canvas_id, str(current_user.id), request.page,
        request.signature_lines, request.rect, request.label,
        agent_id=request.agent_id,
    )
    if not result.get("success"):
        _map_service_error(result, "PDF_SIGN_FAILED", "Failed to stamp signature")
    return result


@router.post("/{canvas_id}/extract-text")
async def extract_pdf_text(
    canvas_id: str,
    ocr: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Per-page text of the current version. ocr=true routes text-less
    (scanned) pages through the Docling parser instead of returning empty."""
    service = PdfCanvasService(db)
    if ocr:
        result = await service.extract_text_ocr(canvas_id, str(current_user.id))
    else:
        result = service.extract_text(canvas_id, str(current_user.id))
    if not result.get("success"):
        _map_service_error(result, "PDF_EXTRACT_FAILED", "Failed to extract text")
    return result


# ── P4: sign & archive ───────────────────────────────────────────────────


@router.post("/{canvas_id}/archive/onedrive")
async def archive_pdf_to_onedrive(
    canvas_id: str,
    request: ArchiveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Archive the current version to the owner's OneDrive (Microsoft
    umbrella grant). The reference is stamped on the canvas audit trail."""
    result = await PdfCanvasService(db).archive_to_onedrive(
        canvas_id, str(current_user.id),
        folder_path=request.folder_path, agent_id=request.agent_id,
    )
    if not result.get("success"):
        _map_service_error(result, "PDF_ARCHIVE_FAILED", "Failed to archive to OneDrive")
    return result


@router.get("/{canvas_id}/export-archive")
async def export_pdf_archive(
    canvas_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download a sanitized archival copy (rebuilt, metadata scrubbed,
    attachments/JS dropped). NOT certified PDF/A — see the plan doc."""
    from core import pdf_engine

    resolved = PdfCanvasService(db).get_bytes(canvas_id, str(current_user.id))
    if not resolved:
        raise router.not_found_error("PDF Canvas", canvas_id)
    try:
        clean = pdf_engine.sanitize(resolved["bytes"])
    except pdf_engine.PdfEngineError as e:
        raise router.error_response(
            error_code="PDF_ARCHIVE_EXPORT_FAILED", message=str(e), status_code=400,
        )
    filename = (resolved["state"].get("file") or {}).get("filename") or "document.pdf"
    return StreamingResponse(
        iter([clean]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="archive-{filename}"',
            "Content-Length": str(len(clean)),
        },
    )


@router.post("/{canvas_id}/docusign")
async def send_pdf_to_docusign(
    canvas_id: str,
    request: SendToDocuSignRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send the current version out for external signing via the DocuSign
    envelope API (env-configured; returns a clean 400 when not configured)."""
    result = PdfCanvasService(db).send_to_docusign(
        canvas_id, str(current_user.id),
        signer_email=request.signer_email, signer_name=request.signer_name,
        agent_id=request.agent_id,
    )
    if not result.get("success"):
        _map_service_error(result, "PDF_DOCUSIGN_FAILED", "Failed to send to DocuSign")
    return result


class CreateFromAttachmentRequest(BaseModel):
    email_canvas_id: str
    attachment_id: str
    agent_id: Optional[str] = None


@router.post("/create/from-email-attachment")
async def create_pdf_from_email_attachment(
    request: CreateFromAttachmentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Open an email attachment as a PDF canvas (pdf attachments only;
    received attachments stream through from the mailbox)."""
    result = await PdfCanvasService(db).create_from_email_attachment(
        user_id=str(current_user.id),
        tenant_id=resolve_tenant_id(current_user),
        email_canvas_id=request.email_canvas_id,
        attachment_id=request.attachment_id,
        agent_id=request.agent_id,
    )
    if not result.get("success"):
        _map_service_error(result, "PDF_CREATE_FROM_ATTACHMENT_FAILED",
                           "Failed to create PDF canvas from attachment")
    return result
