"""
Unified Canvas API Routes
Consolidates state management, context tracking, recording, and summarization.
"""

import hashlib
import io
import json
import logging
import os
import re
import tempfile
from pathlib import Path
from fastapi import APIRouter, Body, Depends, File, WebSocket, WebSocketDisconnect, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from core.database import get_db
from core.auth import get_current_user
from core.deployment_audience import require_pilot_user
from core.models import User
from core.base_routes import BaseAPIRouter
from core.service_factory import ServiceFactory
from core.agent_governance_service import AgentGovernanceService

logger = logging.getLogger(__name__)

# Note: Using BaseAPIRouter for consistency with atom-upstream's enhanced JSON responses
router = BaseAPIRouter(prefix="/api/canvas", tags=["Canvas"], dependencies=[Depends(require_pilot_user)])
# WebSocket routes cannot use the HTTP-only pilot dependency (it resolves a
# Request and OAuth2PasswordBearer rejects the WS scope). The canvas WS
# handler authenticates its own ?token= and checks canvas ownership, so it
# lives on a dependency-free sibling router.
ws_router = APIRouter(prefix="/api/canvas", tags=["Canvas"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateContextRequest(BaseModel):
    canvas_type: str = Field(..., description="Type of canvas (terminal, docs, etc.)")
    agent_id: Optional[str] = Field(None, description="Optional agent ID for context attribution")
    initial_state: Optional[dict] = Field(None, description="Initial state to set")


class UpdateStateRequest(BaseModel):
    state_update: Dict[str, Any] = Field(..., description="Key-value pairs to update in current state")
    canvas_type: Optional[str] = Field(None, description="Canvas type for schema validation")


class RecordCorrectionRequest(BaseModel):
    original_action: dict = Field(..., description="Action proposed by agent")
    corrected_action: dict = Field(..., description="Action modified by user")
    context_info: Optional[str] = Field(None, description="Additional context about correction")


class AddActionRequest(BaseModel):
    action: dict = Field(..., description="Action taken in the canvas session")


class StartRecordingRequest(BaseModel):
    canvas_id: str
    canvas_type: str
    session_name: Optional[str] = None
    agent_id: str
    autonomous: bool = False


class CanvasSubmitRequest(BaseModel):
    """Request model for canvas form submission."""
    canvas_id: str = Field(..., description="Unique identifier for the canvas")
    form_data: Dict[str, Any] = Field(..., description="Form field data to submit")
    agent_id: Optional[str] = Field(None, description="Optional agent ID for governance checks")
    agent_execution_id: Optional[str] = Field(None, description="Optional agent execution ID")
    operation_id: Optional[str] = Field(
        None,
        description=(
            "Optional stable identity for this logical submission. A retry "
            "with the same id/material replays the original receipt."
        ),
    )


# ============================================================================
# State & Type Discovery
# ============================================================================

@router.get("/types")
async def list_canvas_types(
    agent_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """List all available canvas types and their state schemas.

    Note: Canvas types are metadata descriptors and are universally accessible.
    Governance is checked to ensure the agent has basic read permissions, but
    canvas types are not filtered by maturity - all agents can see what types exist.
    Actual canvas creation and interaction are governed separately.
    """
    # Governance check - ensures agent has basic read_canvas permission
    governance = AgentGovernanceService(db)
    check = governance.can_perform_action(
        agent_id=agent_id,
        action_type="read_canvas"
    )

    if not check.get("allowed", True):
        raise router.error_response(
            error_code="GOVERNANCE_DENIED",
            message=check.get("reason"),
            status_code=403
        )

    # Simplified representation of canvas types for the API
    # These are metadata descriptors, not filtered by agent maturity
    canvas_types = {
        "generic": {"description": "Generic UI components"},
        "docs": {"description": "Markdown documentation"},
        "email": {"description": "Email composer"},
        "sheets": {"description": "Spreadsheet grids"},
        "orchestration": {"description": "Workflow boards"},
        "terminal": {"description": "Shell/Console"},
        "coding": {"description": "Code editor"}
    }

    return router.success_response(data={"canvas_types": canvas_types})


# ============================================================================
# Recordings (list + detail)
#
# IMPORTANT: these static-path GET routes MUST be registered BEFORE the
# parameterized GET /{canvas_id} route below. FastAPI matches routes in
# registration order, so /{canvas_id} would otherwise shadow /recordings
# (resolving canvas_id="recordings") and /recordings/{recording_id}. This
# is the classic FastAPI route-shadowing bug.
# ============================================================================
@router.get("/recordings")
async def list_recordings(
    canvas_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List canvas recordings."""
    service = ServiceFactory.get_canvas_recording_service(
        db, tenant_id=current_user.tenant_id,
        workspace_id=getattr(current_user, "workspace_id", None) or "default",
    )

    recordings = await service.list_recordings(
        user_id=str(current_user.id),
        agent_id=agent_id,
        limit=limit
    )

    return router.success_response(data=recordings)


@router.get("/recordings/{recording_id}")
async def get_recording(
    recording_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get recording details and timeline.

    SECURITY: Verifies the recording belongs to the authenticated user
    before returning data (prevents IDOR).
    """
    service = ServiceFactory.get_canvas_recording_service(
        db, tenant_id=current_user.tenant_id,
        workspace_id=getattr(current_user, "workspace_id", None) or "default",
    )

    recording = await service.get_recording(recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")

    # Ownership check — recording["user_id"] must match current_user.id
    if str(recording.get("user_id", "")) != str(current_user.id):
        # Return 404 (not 403) to avoid leaking existence of other users' recordings
        raise HTTPException(status_code=404, detail="Recording not found")

    return router.success_response(data=recording)


# ============================================================================
# Canvas CRUD — Create (blank), Read, Update, Delete
#
# Create used to happen only via agent tools; the gallery's "New blank
# canvas" journey (create → attach a hire → load data) needs a direct
# human path. The canvas is deliberately created WITHOUT an agent: the
# attach step below is what unlocks data loading (see the gate in
# POST /{canvas_id}/data/upload).
# ============================================================================

class CreateBlankCanvasRequest(BaseModel):
    title: Optional[str] = Field(None, description="Display title; defaults to 'Untitled canvas'")
    description: Optional[str] = Field(None, description="Optional canvas description")
    canvas_type: str = Field(
        "document",
        description="Canvas app type (document, markdown, code, sheet, status_panel, ...)",
    )


# Same app vocabulary the chat to-canvas path accepts, minus "email" (an
# email canvas without a draft body is not a starting state) and the
# office_* kinds (they need a real materialized file to bind).
BLANK_CANVAS_TYPES = {
    "document", "markdown", "code", "sheet", "status_panel",
    "form", "line_chart", "bar_chart", "pie_chart", "terminal",
    "orchestration",
}


@router.post("")
async def create_blank_canvas(
    request: CreateBlankCanvasRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create an empty canvas owned by the current user.

    Row conventions mirror the chat to-canvas creation: ``status`` active,
    content in BOTH the Canvas row and the CanvasAudit trail (readers treat
    the audit trail as the source of truth), and a "create" audit row.
    """
    import uuid

    from core.models import Canvas, CanvasAudit
    from core.personal_scope import resolve_tenant_id

    canvas_type = (request.canvas_type or "document").strip().lower()
    if canvas_type not in BLANK_CANVAS_TYPES:
        raise router.error_response(
            error_code="UNSUPPORTED_CANVAS_TYPE",
            message=f"Unsupported canvas_type: {request.canvas_type}",
            status_code=400,
        )

    tenant_id = resolve_tenant_id(current_user)
    canvas_id = str(uuid.uuid4())
    title = (request.title or "").strip() or "Untitled canvas"
    content: Any = {"content": ""}

    db.add(Canvas(
        id=canvas_id,
        tenant_id=tenant_id,
        workspace_id=(
            current_user.workspaces[0].id
            if getattr(current_user, "workspaces", None) else "default"
        ),
        created_by=str(current_user.id),
        name=title,
        description=request.description,
        canvas_type=canvas_type,
        content=content,
        status="active",
        last_edited_by=str(current_user.id),
        last_edited_at=datetime.now(timezone.utc),
    ))
    db.add(CanvasAudit(
        canvas_id=canvas_id,
        tenant_id=tenant_id,
        canvas_type=canvas_type,
        action_type="create",
        user_id=str(current_user.id),
        details_json={"source": "blank_canvas", "title": title, "content": content},
    ))
    db.commit()
    return {"success": True, "canvas_id": canvas_id, "url": f"/canvas/{canvas_id}"}


# ============================================================================
# Agent attachment — the canvas's hires
#
# A canvas works through its hire: the explicit AgentCanvasPresence rows
# written here are the authoritative "who is attached", the gate for data
# loading, and the first resolution candidate for the training panel.
# ============================================================================

class AttachCanvasAgentRequest(BaseModel):
    agent_id: str = Field(..., description="AgentRegistry id of the hire to attach")
    role: str = Field("collaborator", description="Presence role (collaborator, reviewer, approver)")


def _get_owned_canvas(db: Session, canvas_id: str, current_user: User):
    """Ownership-guarded Canvas row (404 without an existence leak)."""
    from core.models import Canvas
    from tools.canvas_crud_tool import _verify_canvas_owner

    if not _verify_canvas_owner(db, canvas_id, str(current_user.id)):
        raise router.not_found_error("Canvas", canvas_id)
    canvas = db.query(Canvas).filter(Canvas.id == canvas_id).first()
    if canvas is None:
        raise router.not_found_error("Canvas", canvas_id)
    return canvas


@router.get("/{canvas_id}/agents")
async def list_canvas_agents(
    canvas_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The hires currently attached to this canvas (newest first)."""
    from core.agent_coordination import active_canvas_agents

    _get_owned_canvas(db, canvas_id, current_user)
    return {"success": True, "canvas_id": canvas_id, "agents": active_canvas_agents(db, canvas_id)}


@router.post("/{canvas_id}/agents")
async def attach_canvas_agent(
    canvas_id: str,
    request: AttachCanvasAgentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Attach a hire to this canvas (idempotent).

    Writes AgentCanvasPresence (with the coordination service's WS join
    broadcast), stamps CanvasContext.agent_id so training-context resolution
    and the correction loop see the hire, and appends an audit row.
    """
    from core.models import AgentRegistry
    from core.personal_scope import resolve_tenant_id
    from core.service_factory import ServiceFactory
    from core.agent_coordination import MultiAgentCanvasService, active_canvas_agents

    canvas = _get_owned_canvas(db, canvas_id, current_user)
    tenant_id = resolve_tenant_id(current_user)

    agent = db.query(AgentRegistry).filter(AgentRegistry.id == request.agent_id).first()
    if agent is None or (agent.tenant_id or "default") not in (tenant_id, canvas.tenant_id or "default"):
        raise router.not_found_error("Agent", request.agent_id)

    try:
        join_result = await MultiAgentCanvasService(db).add_agent_to_canvas(
            agent_id=request.agent_id,
            canvas_id=canvas_id,
            tenant_id=canvas.tenant_id or tenant_id,
            role=request.role,
        )
    except ValueError as exc:
        raise router.error_response(
            error_code="AGENT_ATTACH_FAILED", message=str(exc), status_code=400,
        )

    # get_or_create only sets agent_id at CREATION (the chat-binding has the
    # same stamp) — a canvas bound before it had a hire would keep None forever.
    try:
        context_service = ServiceFactory.get_canvas_context_service(
            db, tenant_id=tenant_id
        )
        context = context_service.get_or_create_context(
            canvas_id=canvas_id,
            canvas_type=canvas.canvas_type or "generic",
            user_id=str(current_user.id),
            agent_id=request.agent_id,
        )
        if context.agent_id != request.agent_id:
            context.agent_id = request.agent_id
            db.commit()
    except Exception as stamp_err:
        logger.warning(f"canvas context agent stamp skipped: {stamp_err}")

    db.add(_agent_attachment_audit(
        canvas_id, canvas.tenant_id or tenant_id, str(current_user.id),
        canvas.canvas_type, "agent_attached", request.agent_id,
    ))
    db.commit()

    return {
        "success": True,
        "canvas_id": canvas_id,
        "agent_id": request.agent_id,
        "join_status": join_result.get("status"),
        "agents": active_canvas_agents(db, canvas_id),
    }


def _agent_attachment_audit(
    canvas_id: str,
    tenant_id: str,
    user_id: str,
    canvas_type: Optional[str],
    action_type: str,
    agent_id: str,
):
    from core.models import CanvasAudit

    return CanvasAudit(
        canvas_id=canvas_id,
        tenant_id=tenant_id,
        canvas_type=canvas_type,
        action_type=action_type,
        user_id=user_id,
        agent_id=agent_id,
        details_json={"agent_id": agent_id, "source": "canvas_agent_attach"},
    )


@router.delete("/{canvas_id}/agents/{agent_id}")
async def detach_canvas_agent(
    canvas_id: str,
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Detach a hire from this canvas (presence becomes "left"; audit row)."""
    from core.personal_scope import resolve_tenant_id
    from core.agent_coordination import MultiAgentCanvasService, active_canvas_agents

    canvas = _get_owned_canvas(db, canvas_id, current_user)
    result = await MultiAgentCanvasService(db).remove_agent_from_canvas(
        agent_id=agent_id,
        canvas_id=canvas_id,
        tenant_id=canvas.tenant_id or resolve_tenant_id(current_user),
    )
    if result.get("status") == "not_present":
        raise router.not_found_error("Attached agent", agent_id)

    db.add(_agent_attachment_audit(
        canvas_id, canvas.tenant_id or "default", str(current_user.id),
        canvas.canvas_type, "agent_detached", agent_id,
    ))
    db.commit()
    return {
        "success": True,
        "canvas_id": canvas_id,
        "agent_id": agent_id,
        "agents": active_canvas_agents(db, canvas_id),
    }


# ============================================================================
# Canvas data loading — gated on the attached hire
#
# A canvas loads data ONLY through its hire: every canvas-scoped load path
# refuses with 409 NO_AGENT_ON_CANVAS until a hire is attached (same gate in
# the UI). Ingested content lands in the workspace memory role-tagged to the
# hire's category, so its recall surfaces it first.
# ============================================================================

# Same upload guardrails as /api/document-ingestion/upload — one standard,
# not a second opinion per surface.
CANVAS_UPLOAD_ALLOWED_EXTENSIONS = {
    "txt", "pdf", "docx", "doc", "xlsx", "xls", "pptx", "ppt",
    "csv", "json", "md", "html", "htm", "rtf", "odt", "eml", "png", "jpg",
    "jpeg", "gif", "bmp", "tiff", "mp3", "wav", "mp4", "avi", "mov",
}


@router.post("/{canvas_id}/data/upload")
async def upload_canvas_data(
    canvas_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Load a file into the canvas's world: parse + ingest into workspace
    memory, role-tagged to the attached hire.

    409 NO_AGENT_ON_CANVAS when no hire is attached — attach an agent first
    (POST /{canvas_id}/agents). The audit row makes every load visible on
    the canvas's journey timeline.
    """
    from core.agent_coordination import active_canvas_agents, canvas_load_role

    from core.models import CanvasAudit

    canvas = _get_owned_canvas(db, canvas_id, current_user)

    agents = active_canvas_agents(db, canvas_id)
    if not agents:
        raise router.error_response(
            error_code="NO_AGENT_ON_CANVAS",
            message="This canvas has no agent attached — add an agent before loading data.",
            status_code=409,
        )
    role = canvas_load_role(db, canvas_id)
    hire_id = agents[0]["agent_id"]

    max_bytes = int(os.getenv("MAX_UPLOAD_BYTES", "52428800"))
    content = await file.read()
    if len(content) > max_bytes:
        raise router.validation_error(
            field="file",
            message=f"File exceeds maximum size of {max_bytes // (1024 * 1024)} MiB",
        )
    file_name = file.filename or "upload"
    file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if file_ext not in CANVAS_UPLOAD_ALLOWED_EXTENSIONS:
        raise router.validation_error(
            field="file",
            message=f"File type '{file_ext or 'unknown'}' is not supported",
        )

    from core.auto_document_ingestion import AutoDocumentIngestionService

    result = await AutoDocumentIngestionService().process_file_bytes(
        content,
        file_name=file_name,
        source="canvas_upload",
        user_id=str(current_user.id),
        role=role,
        extra_metadata={"canvas_id": canvas_id, "agent_id": hire_id},
    )
    ingested = result.get("status") == "ingested"

    # ── File → authoritative canvas binding ─────────────────────────────
    # Ingestion alone makes the file recallable in chat, but the workbook/
    # document/deck canvas needs the REAL file on disk. Similarly an EML must
    # become a structured email canvas (envelope/body/attachments), not a
    # flat text memory row. Both bindings are workspace-owned through the
    # canvas row and are returned so the UI can reload the opened artifact.
    office_canvas = None
    email_canvas = None
    if file_ext in ("xlsx", "xlsm", "docx", "pptx"):
        from core.office_sync_service import OfficeSyncService

        bound = OfficeSyncService(db).materialize_upload(
            canvas_id=canvas_id,
            file_name=file_name,
            content=content,
            user_id=str(current_user.id),
            title=file_name,
        )
        if bound.get("success"):
            office_canvas = {
                "canvas_id": bound["id"],
                "canvas_type": bound["canvas_type"],
                "component": bound["component"],
                "file_path": bound["file_path"],
                "content": bound["content"],
            }
    elif file_ext == "eml":
        from core.canvas_email_service import EmailCanvasService

        imported = EmailCanvasService(db).import_eml(
            canvas_id=canvas_id,
            user_id=str(current_user.id),
            content=content,
            filename=file_name,
            agent_id=hire_id,
        )
        if imported.get("success"):
            from core.models import Canvas as _Canvas

            _row = db.query(_Canvas).filter(_Canvas.id == canvas_id).first()
            email_canvas = {
                "canvas_id": imported["canvas_id"],
                "subject": imported.get("subject"),
                "draft_subject": imported.get("draft_subject"),
                "attachments": imported.get("attachments") or [],
                "source_identity": imported.get("source_identity") or {},
                "content": dict(_row.content or {}) if _row is not None else {},
            }

    # The data-loaded audit row is the read surface. Pin the canvas type to
    # the artifact that was actually bound (email / sheets / docs /
    # presentation), otherwise the page renders the pre-upload document shell.
    if email_canvas:
        canvas.canvas_type = "email"
    elif office_canvas:
        canvas.canvas_type = office_canvas["canvas_type"]
    db.add(CanvasAudit(
        canvas_id=canvas_id,
        tenant_id=canvas.tenant_id or "default",
        canvas_type=canvas.canvas_type,
        action_type="data_loaded",
        user_id=str(current_user.id),
        agent_id=hire_id,
        details_json={
            "file_name": file_name,
            "source": "canvas_upload",
            "role": role,
            "ingested": ingested,
            "doc_id": result.get("doc_id"),
            # The latest audit row is what /api/canvas/{id} serves. Without
            # the bound snapshot here, a file upload read back as the canvas's
            # pre-upload blank document snapshot.
            **(office_canvas["content"] if office_canvas else {}),
            **({"content": office_canvas["content"]} if office_canvas else {}),
            **({"content": email_canvas["content"]} if email_canvas else {}),
        },
    ))
    db.commit()

    return {
        "success": True,
        "canvas_id": canvas_id,
        "agent_id": hire_id,
        "role": role,
        "file_name": file_name,
        "ingestion": result,
        "office_canvas": office_canvas,
        "email_canvas": email_canvas,
    }


@router.get("/{canvas_id}")
async def read_canvas_content(
    canvas_id: str,
    current_user: User = Depends(get_current_user)
):
    """Read the current content of a canvas by ID (from the audit trail)."""
    from tools.canvas_crud_tool import read_canvas
    result = await read_canvas(str(current_user.id), canvas_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error"))
    return result


def _maybe_record_canvas_correction(
    user_id: str, tenant_id: Optional[str], canvas_id: str, corrected_content: Any
) -> None:
    """Learning loop for the canvas: when the version being replaced was the
    hire's DRAFT (an agent-attributed audit row), this human edit IS the
    correction. Feeds record_user_correction → AgentFeedback (RLHF) → the
    maturity/graduation cycle — an immature hire isn't refused edits, it's
    corrected on the canvas and learns. Fault-isolated: never blocks a save.
    """
    try:
        from core.database import get_db_session
        from core.models import CanvasAudit
        from core.service_factory import ServiceFactory
        from sqlalchemy import desc

        with get_db_session() as db:
            rows = (
                db.query(CanvasAudit)
                .filter(CanvasAudit.canvas_id == canvas_id)
                .order_by(desc(CanvasAudit.created_at))
                .limit(5)
                .all()
            )
            if not rows or rows[0].action_type == "delete":
                return
            # rows[0] is the save this PUT just appended; the draft being
            # corrected is the nearest AGENT-authored row beneath it (scan,
            # don't index — same-commit timestamps tie-order ambiguously).
            draft_row = next(
                (r for r in rows[1:] if r.agent_id and r.action_type != "delete"),
                None,
            )
            if draft_row is None:
                return
            prior = (draft_row.details_json or {}).get("content")
            if prior == corrected_content:
                return  # no diff — nothing to learn

            # CanvasContext rows are tenant-scoped under the ACTING USER's
            # tenant (that's how the chat binding writes them — fresh users
            # get UUID tenants, not "default"; the canvas's own audit rows
            # can carry a different tenant than the user's context row).
            service = ServiceFactory.get_canvas_context_service(
                db, tenant_id=tenant_id or "default"
            )
            context = service.get_context(canvas_id, user_id)
            if context is None or not context.agent_id:
                return  # canvas has no hire — nothing to teach

            service.record_user_correction(
                canvas_id=canvas_id,
                user_id=user_id,
                original_action={
                    "type": "canvas_edit",
                    "content": prior,
                    "author": "agent",
                    "agent_id": draft_row.agent_id,
                },
                corrected_action={
                    "type": "canvas_edit",
                    "content": corrected_content,
                    "author": "supervisor",
                },
                context_info=f"canvas_id={canvas_id}; supervisor corrected the hire's draft",
            )
            logger.info(
                f"canvas correction recorded for agent {draft_row.agent_id} "
                f"on {canvas_id} (learning signal)"
            )
    except Exception as e:
        logger.debug(f"canvas correction capture skipped: {e}")


@router.put("/{canvas_id}")
async def update_canvas_content(
    canvas_id: str,
    content: Any = Body(...),
    canvas_type: str = "generic",
    title: Optional[str] = None,
    retype: bool = False,
    operation_id: Optional[str] = None,
    expected_prior_audit_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Update the content of an existing canvas.

    ``content`` is stored verbatim in the audit trail and may be ANY JSON
    shape the canvas type owns natively — dict for email drafts
    ({to, cc, subject, body}), list-of-rows for sheets, plain string for
    markdown/code/document bodies. (Dict-only validation forced every other
    host to keep persisting edits to the legacy artifacts store, where the
    co-editor — and the /canvas/{id} page — could never see them.)

    ``retype=true`` marks the update as a MANUAL type switch (the UI's escape
    hatch when the agent-chat classifier created the wrong canvas type): the
    new ``canvas_type`` is pinned on the audit row and read-time email
    coercion can no longer override it.

    ``operation_id`` is the optional stable identity of the LOGICAL edit; a
    retry of the same operation reuses the existing audit row. Without it,
    byte-identical edits remain deliberate distinct edits, preserving the
    normal manual-edit contract. ``expected_prior_audit_id`` is the optional
    optimistic-concurrency token.

    The direct route now uses the shared postcondition oracle: a 200 success
    carries an explicit ``verification`` status. A committed-but-unverified
    write keeps its ``audit_id``/``operation_id`` and says
    ``replay: do_not_repeat``; an effect with unknown outcome is reported as
    ``effect_unknown`` rather than as a clean refusal.
    """
    from core.canvas_write_service import update_canvas_verified
    result = await update_canvas_verified(
        user_id=str(current_user.id),
        canvas_id=canvas_id,
        content=content,
        canvas_type=canvas_type,
        title=title,
        manual_retype=retype,
        operation_id=operation_id,
        expected_prior_audit_id=expected_prior_audit_id,
        tenant_id=getattr(current_user, "tenant_id", None),
        workspace_id=getattr(current_user, "workspace_id", None),
    )
    if result.get("status") == "refused":
        # BUG FIX: not-found errors must return 404 (consistent with GET
        # /{canvas_id}), not 400 — a missing canvas is not a bad request.
        # A stale revision is a 409; a foreign tenant/workspace is 403 and
        # never reaches the append.
        error = str(result.get("error", ""))
        status = int(result.get("http_status") or (
            409 if result.get("conflict") else (
                404 if "not found" in error.lower() else 400)))
        raise HTTPException(status_code=status, detail=error)
    # The save itself must never be blocked by the learning capture. Only a
    # verified new edit feeds learning; a no-change/already-applied or
    # committed-but-unverified result is not a clean new user edit.
    verification_status = (result.get("verification") or {}).get("status")
    if (result.get("success") and verification_status == "verified"
            and not result.get("no_change")
            and not result.get("already_applied")):
        _maybe_record_canvas_correction(
            str(current_user.id),
            getattr(current_user, "tenant_id", None),
            canvas_id,
            content,
        )
    return result


def _canvas_export_text(content: Any) -> Optional[str]:
    """The exact saved text body for generated document/markdown canvases."""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        for key in ("content", "text", "markdown", "body"):
            value = content.get(key)
            if isinstance(value, str):
                return value
    return None


def _canvas_export_slug(value: Any, fallback: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value or "")).strip("-")
    return (slug[:60] or fallback)


def _normalize_office_zip(body: bytes) -> bytes:
    """Make Office OPC packages byte-stable across processes.

    python-docx/python-pptx write ZIP entries with the current local timestamp.
    The document content is deterministic, but that ZIP metadata is not. This
    rewrites the same entries and compression with a fixed 1980 DOS timestamp;
    it does not alter any XML/business content. The result is a real Office
    package and the same saved source now yields the same bytes/hash.
    """
    import zipfile

    source = zipfile.ZipFile(io.BytesIO(body))
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            data = source.read(info.filename)
            normalized = zipfile.ZipInfo(
                info.filename, date_time=(1980, 1, 1, 0, 0, 0))
            normalized.compress_type = info.compress_type
            normalized.external_attr = info.external_attr
            normalized.internal_attr = info.internal_attr
            normalized.create_system = 0
            normalized.comment = b""
            normalized.extra = b""
            target.writestr(normalized, data)
    return output.getvalue()


def _validate_docx_package(body: bytes, source_text: str,
                           title: Optional[str] = None) -> None:
    """Compare the DOCX body, in XML order, to the canonical renderer blocks.

    Group-presence checks are not enough: a document whose sections were
    reordered, whose heading depth was changed, or whose table moved keeps the
    same groups/labels and would still look "valid". This rebuilds the exact
    ordered block sequence the existing ``_markdown_blocks`` compiler emits and
    compares it to the body sequence of the actual package.
    """
    from docx import Document
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    from core.office_service import _markdown_blocks

    document = Document(io.BytesIO(body))
    actual = []
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            paragraph = Paragraph(child, document)
            text = paragraph.text
            style = (paragraph.style.name or "").strip()
            lowered = style.lower()
            heading = re.fullmatch(r"heading ([1-9])", lowered)
            if lowered == "title":
                actual.append(("title", text))
            elif heading:
                actual.append(("heading", int(heading.group(1)), text))
            elif "list bullet" in lowered:
                actual.append(("bullet", text))
            else:
                actual.append(("paragraph", text))
        elif child.tag == qn("w:tbl"):
            table = Table(child, document)
            actual.append((
                "table",
                tuple(
                    tuple(cell.text for cell in row.cells)
                    for row in table.rows
                ),
            ))

    blocks = list(_markdown_blocks(source_text))
    first_heading = next(
        (payload[1] for kind, payload in blocks
         if kind == "heading" and payload[1]),
        "",
    )
    expected = []
    if title and str(title).strip().lower() != str(first_heading).strip().lower():
        expected.append(("title", str(title)))
    for kind, payload in blocks:
        if kind == "heading":
            level, text = payload
            if text:
                expected.append(("heading", int(level), text))
        elif kind == "bullets":
            for item in payload:
                expected.append(("bullet", item))
        elif kind == "table":
            rows = payload
            width = max(len(row) for row in rows)
            expected.append((
                "table",
                tuple(
                    tuple(row[index] if index < len(row) else ""
                          for index in range(width))
                    for row in rows
                ),
            ))
        else:
            text = str(payload or "").strip()
            if text:
                expected.append(("paragraph", text))

    if actual != expected:
        raise ValueError(
            "rendered DOCX body does not match the exact ordered blocks of "
            "the saved source")


def _validate_pptx_package(body: bytes, source_text: str) -> None:
    from pptx import Presentation

    from core.chat_draft_classifier import extract_slide_outline
    from core.office_service import _parse_markdown_table

    expected = extract_slide_outline(source_text)
    if not expected:
        raise ValueError("presentation source has no Slide N: outline")
    presentation = Presentation(io.BytesIO(body))
    if len(presentation.slides) != len(expected):
        raise ValueError("rendered PPTX slide count does not match the source")

    for slide, expected_slide in zip(presentation.slides, expected):
        title = str(expected_slide.get("title") or "").strip()
        title_shape = slide.shapes.title
        rendered_title = (
            title_shape.text.strip() if title_shape is not None else "")
        if rendered_title != title:
            raise ValueError("rendered PPTX slide title does not match")

        content_lines = str(expected_slide.get("content") or "").splitlines()
        expected_notes = []
        body_lines = []
        expected_tables = []
        table_lines = set()
        for idx, line in enumerate(content_lines):
            stripped = line.strip()
            lowered = stripped.lower()
            if lowered.startswith(("notes:", "speaker notes:")):
                expected_notes.append(stripped.split(":", 1)[1].strip())
                continue
            if lowered.startswith(("source:", "sources:", "reference:",
                                   "references:")):
                expected_notes.append(stripped)
                continue
            rows, nxt = _parse_markdown_table(content_lines, idx)
            if rows:
                expected_tables.append(rows)
                table_lines.update(range(idx, nxt))
                continue
            if idx not in table_lines and stripped:
                body_lines.append(stripped)

        actual_body = []
        actual_tables = []
        for shape in slide.shapes:
            if title_shape is not None and shape == title_shape:
                continue
            if getattr(shape, "has_table", False):
                actual_tables.append([
                    [cell.text.strip() for cell in row.cells]
                    for row in shape.table.rows
                ])
            elif getattr(shape, "has_text_frame", False):
                actual_body.append(shape.text_frame.text.strip())
        actual_body_text = "\n".join(part for part in actual_body if part)
        for line in body_lines:
            if line not in actual_body_text:
                raise ValueError(
                    "rendered PPTX slide body does not match the saved source")
        if body_lines and not actual_body_text.strip():
            raise ValueError("rendered PPTX slide body is empty")
        if actual_tables != expected_tables:
            raise ValueError(
                "rendered PPTX tables do not match the saved source")
        if expected_notes:
            notes_shape = slide.notes_slide
            actual_notes = notes_shape.notes_text_frame.text.strip()
            for note in expected_notes:
                if note and note not in actual_notes:
                    raise ValueError(
                        "rendered PPTX speaker notes do not match the source")


def _normalized_export_requirements(raw: Any) -> list:
    """Validate exactly one claimed requirement set, or refuse."""
    if not isinstance(raw, list):
        raise HTTPException(status_code=409, detail={
            "error": "canvas_export_business_requirements_malformed",
            "message": "business requirements must be a list of bindings",
        })
    if not raw:
        return []
    malformed = [
        index for index, item in enumerate(raw)
        if not isinstance(item, dict) or not item
    ]
    if malformed:
        raise HTTPException(status_code=409, detail={
            "error": "canvas_export_business_requirements_malformed",
            "message": "a business requirement has no valid binding",
            "indices": malformed,
        })
    try:
        from core.employee_business_outcomes import (
            normalize_business_requirements,
        )
        return normalize_business_requirements(raw)
    except Exception as exc:  # noqa: BLE001 — fail closed, no internals
        logger.warning(
            "Canvas export business requirement unreadable (class=%s)",
            type(exc).__name__)
        raise HTTPException(status_code=409, detail={
            "error": "canvas_export_business_requirements_unreadable",
            "message": "a business requirement binding is unsupported or "
                       "malformed",
        }) from exc


def _claimed_export_requirements(material: Dict[str, Any]) -> Optional[list]:
    """Read CanvasAudit-carried requirement claims for fail-closed checks.

    A claim is never proof: the route resolves the canonical persisted
    assignment separately. A claim that disagrees with that assignment
    refuses instead of adding or removing a requirement.
    """
    details = material.get("details") if isinstance(
        material.get("details"), dict) else {}
    assignment = details.get("assignment") if isinstance(
        details.get("assignment"), dict) else {}
    top_present = "business_requirements" in details
    nested_present = "business_requirements" in assignment
    if not (top_present or nested_present):
        return None
    top = (
        _normalized_export_requirements(details.get("business_requirements"))
        if top_present else None)
    nested = (
        _normalized_export_requirements(
            assignment.get("business_requirements"))
        if nested_present else None)
    if top is not None and nested is not None:
        key = lambda items: sorted(  # noqa: E731 - local comparison key
            items, key=lambda item: item["requirement_id"])
        if key(top) != key(nested):
            raise HTTPException(status_code=409, detail={
                "error": "canvas_export_business_requirements_contradictory",
                "message": "top-level and assignment business requirements "
                           "disagree; the export is refused rather than "
                           "weakening either set",
            })
    return top if top is not None else nested


def _resolve_export_job(db: Session, canvas_id: str, actor: Dict[str, Any]):
    """Resolve the authoritative persisted job bound to this canvas.

    Resolution is server-owned: ``Canvas.goal_run_id`` (the existing goal-run
    back-link) or the run's exact ``provenance.canvas_id``. A truthy
    ``run_id`` copied into CanvasAudit metadata is never used, and there is no
    first-available-job fallback. The GoalRunService is workspace-scoped.
    """
    from sqlalchemy.orm import sessionmaker

    from core.goals.goal_run_service import GoalRunService
    from core.models import Canvas
    from core.task_lifecycle import TaskLifecycle

    canvas = db.query(Canvas).filter(Canvas.id == canvas_id).first()
    if canvas is None:
        return {"canvas": None, "record": None, "binding": None,
                "error": "canvas_missing"}
    factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    runs = GoalRunService(
        workspace_id=str(actor["effective_workspace_id"]),
        tenant_id=str(actor["effective_tenant_id"]),
        session_factory=factory)
    lifecycle = TaskLifecycle(runs)
    goal_run_id = str(getattr(canvas, "goal_run_id", "") or "").strip()
    if goal_run_id:
        record = lifecycle.get_task(goal_run_id)
        if record is None:
            return {"canvas": canvas, "record": None,
                    "binding": "canvas_goal_run_id",
                    "error": "job_binding_unresolved"}
        return {"canvas": canvas, "record": record,
                "binding": "canvas_goal_run_id", "error": None}
    record = lifecycle.find_active_task_for_canvas(canvas_id)
    if record is not None:
        return {"canvas": canvas, "record": record,
                "binding": "canvas_provenance_active", "error": None}
    record = lifecycle.find_canvas_evidence_task(canvas_id)
    if record is not None:
        return {"canvas": canvas, "record": record,
                "binding": "canvas_provenance_evidence", "error": None}
    return {"canvas": canvas, "record": None, "binding": None, "error": None}


def _authoritative_export_steps(
    record: Dict[str, Any], assignment: Dict[str, Any],
) -> list:
    """Steps whose applied result comes from a durable applied operation.

    A persisted assignment step flag/result alone is not proof: it is mapped
    from the run's operation record here, and an ``applied`` claim without a
    matching applied operation is downgraded to unverified. Embedded/copied
    CanvasAudit steps never enter this path.
    """
    operations = {
        str(operation.get("operation_id") or ""): operation
        for operation in (record.get("operations") or [])
        if isinstance(operation, dict)
    }
    steps = []
    for raw in assignment.get("steps") or []:
        if not isinstance(raw, dict):
            continue
        step = dict(raw)
        operation = operations.get(str(step.get("operation_id") or ""))
        execution = (
            operation.get("execution")
            if operation is not None
            and str(operation.get("status") or "") == "applied"
            and isinstance(operation.get("execution"), dict)
            and operation.get("execution")
            else None
        )
        if execution is None:
            step["status"] = "unverified"
            step["result"] = None
        else:
            step["status"] = "applied"
            step["result"] = execution
        steps.append(step)
    return steps


def _stale_export_source(reason: str) -> HTTPException:
    return HTTPException(status_code=409, detail={
        "error": "canvas_export_source_changed",
        "message": "the verified job receipt is not bound to the current "
                   "saved canvas source; refresh and re-verify",
        "reason": reason,
    })


def _check_export_job_binding(
    canvas: Any, record: Dict[str, Any], assignment: Dict[str, Any],
    *, revision_id: str, source_digest: str,
) -> None:
    """Compare recorded job/source/revision bindings to the current canvas."""
    from core.canvas_assignment import _canvas_state

    try:
        state = _canvas_state(canvas)
    except Exception as exc:  # noqa: BLE001 — unreadable is a refusal
        logger.warning(
            "Canvas export job state unreadable (class=%s)",
            type(exc).__name__)
        raise _stale_export_source("job_state_unreadable") from exc

    provenance = {}
    candidates = [
        (record.get("task_revision") or {}).get("provenance"),
        assignment.get("provenance"),
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            for key, value in candidate.items():
                if value not in (None, "", [], {}):
                    provenance.setdefault(key, value)
    source_entries = [
        entry for entry in (assignment.get("sources") or [])
        if isinstance(entry, dict)
        and (
            not entry.get("canvas_id")
            or str(entry.get("canvas_id")) == str(canvas.id)
        )
    ]

    def _compare(binding: Dict[str, Any]) -> None:
        revision = binding.get("state_revision")
        if revision not in (None, ""):
            try:
                expected_revision = int(revision)
            except (TypeError, ValueError) as exc:
                raise _stale_export_source("job_revision_unreadable") from exc
            if state["revision"] != expected_revision:
                raise _stale_export_source("canvas_revision_changed")
        manifest = binding.get("manifest_revision")
        if manifest not in (None, "") and str(manifest) != str(
                state["manifest_revision"] or ""):
            raise _stale_export_source("canvas_manifest_changed")
        source = binding.get("source") if isinstance(
            binding.get("source"), dict) else binding
        for field, actual in (
            ("source_version", state["source_version"]),
            ("sha256", (state["source"] or {}).get("sha256")),
            ("resource_id", (state["source"] or {}).get("resource_id")),
        ):
            wanted = source.get(field)
            if wanted not in (None, "") and str(wanted) != str(actual or ""):
                raise _stale_export_source(f"canvas_{field}_changed")

    _compare(provenance)
    for entry in source_entries:
        _compare(entry)

    recorded_audit = (
        provenance.get("canvas_audit_id")
        or provenance.get("source_audit_id"))
    if recorded_audit not in (None, "") and str(
            recorded_audit) != str(revision_id):
        raise _stale_export_source("canvas_audit_changed")
    recorded_body = (
        provenance.get("canvas_content_sha256")
        or provenance.get("canvas_sha256"))
    if recorded_body not in (None, "") and str(
            recorded_body) != str(source_digest):
        raise _stale_export_source("canvas_body_changed")
    return provenance


def _artifact_bound_to_export(
    record: Dict[str, Any], assignment: Dict[str, Any],
    source_text: str, format: str,
) -> Optional[bool]:
    """Whether the job's verified artifact for this format is this body.

    ``None`` means the job has no artifact step for the format, so the
    business-result receipts (not document composition) are the claim.
    """
    adapter = (
        "artifact.document" if format == "docx" else "artifact.presentation")
    steps = [
        step for step in _authoritative_export_steps(record, assignment)
        if str(step.get("adapter") or "") == adapter
    ]
    if not steps:
        return None
    body_sha = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    for step in steps:
        if str(step.get("status") or "") != "applied":
            continue
        result = step.get("result") if isinstance(
            step.get("result"), dict) else {}
        artifact = result.get("artifact") if isinstance(
            result.get("artifact"), dict) else {}
        if not (artifact.get("sha256") and artifact.get("revision")):
            continue
        if str(result.get("content_sha256") or "") == body_sha:
            return True
    return False


def _resolve_export_business_claim(
    db: Session, canvas_id: str, actor: Dict[str, Any],
    material: Dict[str, Any], *, revision_id: str, source_digest: str,
    source_text: str, format: str,
) -> tuple:
    """Authoritative artifact scope and verified business result for export."""
    from core.employee_business_outcomes import (
        business_requirement_views, normalize_business_requirements,
    )

    claimed = _claimed_export_requirements(material)
    resolution = _resolve_export_job(db, canvas_id, actor)
    record = resolution.get("record")
    assignment = (
        record.get("assignment") if isinstance(record, dict)
        and isinstance(record.get("assignment"), dict) else None)
    if resolution.get("error") == "job_binding_unresolved":
        raise HTTPException(status_code=409, detail={
            "error": "canvas_export_job_binding_required",
            "message": "the canvas job binding can no longer be resolved; "
                       "the copied result claim is not authoritative",
        })
    if record is None:
        if claimed:
            raise HTTPException(status_code=409, detail={
                "error": "canvas_export_job_binding_required",
                "message": "business requirements are claimed but no "
                           "authoritative persisted job is bound to this "
                           "canvas",
            })
        return "unscoped_canvas_draft", "not_claimed"
    if str(record.get("run_status") or "") in ("failed", "cancelled"):
        raise HTTPException(status_code=409, detail={
            "error": "canvas_export_job_not_active",
            "message": "the bound job is not in an exportable state",
            "run_status": record.get("run_status"),
        })
    if assignment is None:
        if claimed:
            raise HTTPException(status_code=409, detail={
                "error": "canvas_export_job_binding_required",
                "message": "the bound job has no persisted assignment plan",
            })
        return "assignment_bound", "no_required_results"

    try:
        requirements = normalize_business_requirements(
            assignment.get("business_requirements") or [])
    except Exception as exc:  # noqa: BLE001 — fail closed, no internals
        logger.warning(
            "Canvas export canonical requirements unreadable (class=%s)",
            type(exc).__name__)
        raise HTTPException(status_code=409, detail={
            "error": "canvas_export_business_requirements_unreadable",
            "message": "the persisted job requirements are unsupported or "
                       "malformed",
        }) from exc
    if claimed is not None and claimed and requirements:
        key = lambda items: sorted(  # noqa: E731 - local comparison key
            items, key=lambda item: item["requirement_id"])
        if key(claimed) != key(requirements):
            raise HTTPException(status_code=409, detail={
                "error": "canvas_export_business_requirements_contradictory",
                "message": "the canvas result claim disagrees with the "
                           "persisted job requirements",
            })
    if claimed and not requirements:
        raise HTTPException(status_code=409, detail={
            "error": "canvas_export_business_requirements_contradictory",
            "message": "the canvas claims requirements that its persisted "
                       "job does not carry",
        })
    if not requirements:
        return "assignment_bound", "no_required_results"

    provenance = _check_export_job_binding(
        resolution["canvas"], record, assignment,
        revision_id=revision_id, source_digest=source_digest)

    authoritative = {
        **assignment,
        "steps": _authoritative_export_steps(record, assignment),
    }
    views = business_requirement_views(authoritative)
    if len(views) != len(requirements):
        raise HTTPException(status_code=409, detail={
            "error": "canvas_export_business_requirements_unreadable",
            "message": "the persisted job receipts could not be evaluated "
                       "exactly",
        })
    unresolved = [
        view for view in views
        if str(view.get("status") or "") != "satisfied"
    ]
    if unresolved:
        raise HTTPException(status_code=409, detail={
            "error": "canvas_export_business_result_required",
            "message": "the requested output cannot be published before its "
                       "required scoped business result is verified",
            "unresolved": [
                {"label": item.get("label"),
                 "next_action": item.get("next_action")}
                for item in unresolved
            ],
        })
    artifact_bound = _artifact_bound_to_export(
        record, assignment, source_text, format)
    if artifact_bound is False:
        raise HTTPException(status_code=409, detail={
            "error": "canvas_export_artifact_binding_mismatch",
            "message": "the saved canvas body is not the verified job "
                       "artifact for this format; a manual edit cannot "
                       "inherit the old business result",
        })
    if artifact_bound is None:
        # No artifact step for this format: a byte-exact body digest recorded
        # by the producer is still an exact output binding. Without one, a
        # calculation job alone cannot certify an arbitrary document body.
        recorded_body = (
            provenance.get("canvas_content_sha256")
            or provenance.get("canvas_sha256"))
        body_sha = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        if not recorded_body or str(recorded_body) != body_sha:
            raise HTTPException(status_code=409, detail={
                "error": "canvas_export_output_binding_required",
                "message": "the bound job has business results but no exact "
                           "output/body binding to the current saved canvas; "
                           "the document cannot be certified from an old "
                           "receipt",
            })

    return "assignment_bound", "required_results_verified"


@router.get("/{canvas_id}/export/office")
async def export_generated_canvas_office(
    canvas_id: str,
    format: str = Query(..., pattern="^(docx|pptx)$"),
    expected_audit_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download the exact saved generated Canvas document/presentation.

    Read-only: reads the authoritative audit material, renders with the
    existing office_service Word/PowerPoint create_from_markdown renderers,
    verifies the actual package, and returns bytes with source/output digests.
    It never executes an agent/model and never exposes a filesystem path.
    """
    from core.canvas_authority import (
        CanvasAuthorityError, require_active_actor, require_canvas_read,
    )
    from core.canvas_write_service import canvas_content_digest
    from core.office_service import OfficeService
    from tools.canvas_crud_tool import visible_canvas_material

    try:
        actor = require_active_actor(db, str(current_user.id))
        require_canvas_read(db, canvas_id, actor)
    except CanvasAuthorityError as exc:
        raise HTTPException(status_code=exc.status_code, detail={
            "error": exc.code, "message": str(exc)}) from exc
    material = visible_canvas_material(db, canvas_id)
    if not material.get("success"):
        raise HTTPException(status_code=404, detail="Canvas not found")
    latest = material.get("latest")
    if latest is not None and str(latest.action_type or "") == "delete":
        raise HTTPException(status_code=404, detail="Canvas not found")
    revision_id = str(material.get("revision_audit_id") or "")
    if not revision_id:
        raise HTTPException(status_code=409, detail={
            "error": "canvas_source_unavailable",
            "message": "the canvas has no saved source revision",
        })
    if expected_audit_id and str(expected_audit_id) != revision_id:
        raise HTTPException(status_code=409, detail={
            "error": "canvas_source_changed",
            "message": "the saved canvas changed before export; save again and retry",
        })
    review_status = str(material.get("review_status") or "unknown").lower()
    if review_status in {"pending_review", "rejected", "withheld"}:
        raise HTTPException(status_code=409, detail={
            "error": "canvas_export_withheld",
            "message": "the canvas result is not accepted for final publication",
            "review_status": review_status,
        })
    text = _canvas_export_text(material.get("content"))
    if text is None or not text.strip():
        raise HTTPException(status_code=409, detail={
            "error": "canvas_export_empty",
            "message": "the saved canvas has no document text to export",
        })
    canvas_type = str(material.get("canvas_type") or "").lower()
    if format == "pptx" and canvas_type not in (
            "presentation", "markdown", "generic"):
        raise HTTPException(status_code=409, detail={
            "error": "canvas_export_format_unsupported",
            "message": "this canvas type is not a presentation source",
        })
    if format == "docx" and canvas_type not in (
            "docs", "document", "markdown", "generic"):
        raise HTTPException(status_code=409, detail={
            "error": "canvas_export_format_unsupported",
            "message": "this canvas type is not a document source",
        })

    source_digest = canvas_content_digest(material.get("content"))
    artifact_scope, business_result = _resolve_export_business_claim(
        db, canvas_id, actor, material,
        revision_id=revision_id,
        source_digest=source_digest,
        source_text=text,
        format=format,
    )
    source_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    title = str(material.get("title") or "").strip() or None
    from core.local_paths import resolve_local_path
    office_dir = resolve_local_path(
        os.getenv("ATOM_OFFICE_DIR") or os.path.join("data", "office"))
    office_dir.mkdir(parents=True, exist_ok=True)
    suffix = "." + format
    fd, temp_path = tempfile.mkstemp(
        prefix=f"canvas-{_canvas_export_slug(canvas_id, 'canvas')}-",
        suffix=suffix, dir=str(office_dir))
    os.close(fd)
    os.unlink(temp_path)
    service = OfficeService()
    try:
        if format == "docx":
            result = service.word.create_from_markdown(
                temp_path, text, title=title)
        else:
            result = service.pptx.create_from_markdown(
                temp_path, text, title=title)
        if not result.get("success"):
            logger.warning(
                "Canvas office export renderer refused (stage=render)")
            raise HTTPException(status_code=422, detail={
                "error": "canvas_export_render_failed",
                "message": "the renderer refused the saved canvas content",
                "stage": "render",
            })
        body = _normalize_office_zip(Path(temp_path).read_bytes())
        if format == "docx":
            _validate_docx_package(body, text, title)
        else:
            _validate_pptx_package(body, text)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(
            "Canvas office export failed (stage=render_or_validate, class=%s)",
            type(exc).__name__)
        raise HTTPException(status_code=422, detail={
            "error": "canvas_export_render_failed",
            "message": "the renderer did not produce a valid Office package",
            "stage": "render_or_validate",
        }) from exc
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass

    # Recheck actor/scope/source immediately before delivery. A concurrent
    # save or authority change must not return bytes for the earlier revision.
    # Independent scoped session on the SAME engine: never trust the cached
    # request ORM identity, and never expire/rollback unrelated caller work.
    from sqlalchemy.orm import Session as SqlSession
    fresh_db = SqlSession(bind=db.get_bind())
    try:
        try:
            actor = require_active_actor(fresh_db, str(current_user.id))
            require_canvas_read(fresh_db, canvas_id, actor)
        except CanvasAuthorityError as exc:
            raise HTTPException(status_code=exc.status_code, detail={
                "error": exc.code, "message": str(exc)}) from exc
        latest_material = visible_canvas_material(fresh_db, canvas_id)
        if (not latest_material.get("success")
                or str(latest_material.get("revision_audit_id") or "")
                != revision_id):
            raise HTTPException(status_code=409, detail={
                "error": "canvas_source_changed",
                "message": "the saved canvas changed while the file was "
                           "rendered; retry",
            })
        latest_digest = canvas_content_digest(
            latest_material.get("content"))
        if latest_digest != source_digest:
            raise HTTPException(status_code=409, detail={
                "error": "canvas_source_changed",
                "message": "the saved canvas changed while the file was "
                           "rendered; retry",
            })
        latest_text = _canvas_export_text(latest_material.get("content"))
        latest_scope, latest_result = _resolve_export_business_claim(
            fresh_db, canvas_id, actor, latest_material,
            revision_id=str(latest_material.get("revision_audit_id") or ""),
            source_digest=latest_digest,
            source_text=latest_text or "",
            format=format,
        )
        if (latest_scope != artifact_scope
                or latest_result != business_result):
            raise HTTPException(status_code=409, detail={
                "error": "canvas_export_job_changed",
                "message": "the job/receipt state changed while the file was "
                           "rendered; retry",
            })
    finally:
        fresh_db.close()

    output_sha = hashlib.sha256(body).hexdigest()
    filename = (
        "canvas-"
        + _canvas_export_slug(title or canvas_id, "canvas")
        + "-"
        + _canvas_export_slug(revision_id, "revision")[:8]
        + suffix
    )
    return Response(
        content=body,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            + ("wordprocessingml.document" if format == "docx"
               else "presentationml.presentation")),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(body)),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "ETag": f'"sha256:{output_sha}"',
            "X-Atom-Canvas-Id": canvas_id,
            "X-Atom-Source-Audit-Id": revision_id,
            "X-Atom-Source-SHA256": source_sha,
            "X-Atom-Output-SHA256": output_sha,
            "X-Atom-Artifact-Scope": artifact_scope,
            "X-Atom-Business-Result": business_result,
        },
    )


@router.post("/{canvas_id}/restore")
async def restore_canvas_version(
    canvas_id: str,
    body: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Restore an earlier version from the audit trail.

    Body: {"audit_id": "<canvas_audit.id>"}. The restore is APPENDED as a new
    version (append-only trail — nothing is rewritten), and broadcasts the
    same WS update as an ordinary edit, so open canvases converge live.

    The direct route now uses the shared postcondition oracle. A successful
    restore carries an explicit ``verification`` status; a committed-but-
    unverified restore keeps its ``audit_id``/``restored_from`` identity and
    says ``replay: do_not_repeat``. An effect with unknown outcome is reported
    as ``effect_unknown`` rather than as a clean refusal.
    """
    from core.canvas_write_service import restore_canvas_verified

    audit_id = (body or {}).get("audit_id")
    if not audit_id:
        raise HTTPException(status_code=400, detail="audit_id is required")
    result = await restore_canvas_verified(
        user_id=str(current_user.id),
        canvas_id=canvas_id,
        audit_id=str(audit_id),
        tenant_id=getattr(current_user, "tenant_id", None),
        workspace_id=getattr(current_user, "workspace_id", None),
    )
    if result.get("status") == "refused":
        error = str(result.get("error", ""))
        status = int(result.get("http_status") or (
            409 if result.get("conflict") else (
                404 if "not found" in error.lower() else 400)))
        raise HTTPException(status_code=status, detail=error)
    return result


@router.delete("/{canvas_id}")
async def delete_canvas(
    canvas_id: str,
    operation_id: Optional[str] = None,
    expected_prior_audit_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Delete (close) a specific canvas by ID.

    The append-only tombstone is written by the shared verified lifecycle
    service: the acting user's CURRENT tenant/workspace is authorized in the
    same transaction as the append, the logical operation is idempotent, and
    a 200 carries an explicit verification status. A committed-but-unverified
    delete keeps its ``audit_id``/``operation_id`` and says
    ``replay: do_not_repeat``; an unknown commit outcome is never reported as
    "nothing changed".
    """
    from core.canvas_write_service import delete_canvas_verified
    result = await delete_canvas_verified(
        user_id=str(current_user.id),
        canvas_id=canvas_id,
        operation_id=operation_id,
        expected_prior_audit_id=expected_prior_audit_id,
        tenant_id=getattr(current_user, "tenant_id", None),
        workspace_id=getattr(current_user, "workspace_id", None),
    )
    if result.get("status") == "refused":
        error = str(result.get("error", ""))
        status = int(result.get("http_status") or (
            409 if result.get("conflict") else (
                404 if "not found" in error.lower() else 400)))
        raise HTTPException(status_code=status, detail=error)
    return result


@router.post("/{canvas_id}/undelete")
async def undelete_canvas(
    canvas_id: str,
    body: Optional[Dict[str, Any]] = Body(default=None),
    operation_id: Optional[str] = None,
    tombstone_audit_id: Optional[str] = None,
    source_audit_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Un-delete a tombstoned canvas (append a restore row; append-only).

    Distinct from POST /{canvas_id}/restore above, which restores an earlier
    VERSION of a live canvas — this one revives a canvas whose latest audit
    row is a delete tombstone.

    The receiver copies the newest CONTENT-bearing non-delete row (not a
    contentless event stamp) and records the exact tombstone id, source row
    id and content digest. The acting user's CURRENT tenant/workspace is
    authorized in the same transaction as the append, so a historical
    co-editor whose scope moved is refused before effect.
    """
    from core.canvas_write_service import restore_deleted_canvas_verified

    payload = body or {}
    resolved_operation_id = (
        payload.get("operation_id") or operation_id)
    resolved_tombstone_id = (
        payload.get("tombstone_audit_id")
        or payload.get("expected_tombstone_audit_id")
        or tombstone_audit_id)
    resolved_source_id = (
        payload.get("source_audit_id")
        or payload.get("expected_source_audit_id")
        or source_audit_id)

    result = await restore_deleted_canvas_verified(
        user_id=str(current_user.id),
        canvas_id=canvas_id,
        operation_id=resolved_operation_id,
        tombstone_audit_id=resolved_tombstone_id,
        source_audit_id=resolved_source_id,
        tenant_id=getattr(current_user, "tenant_id", None),
        workspace_id=getattr(current_user, "workspace_id", None),
    )
    if result.get("status") == "refused":
        error = str(result.get("error", ""))
        status = int(result.get("http_status") or (
            409 if result.get("conflict") else (
                404 if "not found" in error.lower() else 400)))
        raise HTTPException(status_code=status, detail=error)
    return result


@router.post("/{canvas_id}/fork")
async def fork_canvas(
    canvas_id: str,
    current_user: User = Depends(get_current_user)
):
    """Fork a canvas into a new, independent canvas owned by the current user.

    P5 Blueprint Security: forking never leaks credentials or history. The copy
    gets a fresh id, ``share_token`` reset to None, ``status`` "active", and
    ``created_by`` set to the current user. The copy's body is the audit-trail
    content (what the user sees), recorded on the single "fork" row — no audit
    HISTORY is carried over, and no context/artifacts/recordings/
    presence/handoffs are copied. Component installation configs are run
    through ``strip_credentials`` before they are re-created on the copy. The
    source canvas is never modified.
    """
    import uuid
    from datetime import datetime, timezone

    from core.blueprint_sanitizer import strip_credentials
    from core.database import get_db_session
    from core.models import Canvas, CanvasAudit, ComponentInstallation
    from tools.canvas_crud_tool import read_canvas

    # 1. Audit-trail source of truth: verifies the canvas exists and the
    #    current user owns it (IDOR guard).
    source_read = await read_canvas(str(current_user.id), canvas_id)
    if not source_read.get("success"):
        raise HTTPException(status_code=404, detail=source_read.get("error"))

    with get_db_session() as db:
        src = db.query(Canvas).filter(Canvas.id == canvas_id).first()
        if src is None:
            raise HTTPException(status_code=404, detail=f"Canvas {canvas_id} not found")

        new_id = str(uuid.uuid4())
        new_name = f"{src.name} (copy)"
        # The audit trail is the read source-of-truth (see read_canvas): every
        # agent/UI edit appends a CanvasAudit row and never rewrites the
        # Canvas.content column, so copying src.content forked the creation-era
        # snapshot instead of the draft the user sees. Copy the resolved read.
        new_canvas_type = source_read.get("canvas_type") or src.canvas_type
        from core.canvas_capability_service import sanitize_capability_copy

        # Capability copies keep the data shape but drop private teaching,
        # source identity and approval bindings (independent instance).
        forked_content = sanitize_capability_copy(source_read["content"], new_id)

        # 2. Independent copy: copied fields, all identity/state fields reset.
        new_canvas = Canvas(
            id=new_id,
            tenant_id=src.tenant_id,
            workspace_id=src.workspace_id,
            created_by=str(current_user.id),
            name=new_name,
            description=src.description,
            canvas_type=new_canvas_type,
            content=forked_content,
            style=src.style,
            is_collaborative=src.is_collaborative,
            share_token=None,          # never inherit a share token
            status="active",           # fresh status
            last_edited_by=str(current_user.id),
            last_edited_at=datetime.now(timezone.utc),
        )
        db.add(new_canvas)
        db.flush()

        # 3. Re-create component installations with credentials stripped.
        for inst in db.query(ComponentInstallation).filter(
            ComponentInstallation.canvas_id == canvas_id
        ).all():
            db.add(ComponentInstallation(
                tenant_id=inst.tenant_id,
                canvas_id=new_id,
                component_id=inst.component_id,
                config=strip_credentials(inst.config) if inst.config else inst.config,
                position=inst.position,
                z_index=inst.z_index,
            ))

        # 4. Exactly one audit row for the copy — history is NOT carried over.
        #    The body rides on this row (it is the copy's current content, not
        #    carried history) so the audit-first read path serves the fork
        #    without depending on the Canvas.content fallback.
        db.add(CanvasAudit(
            canvas_id=new_id,
            tenant_id=src.tenant_id,
            action_type="fork",
            user_id=str(current_user.id),
            canvas_type=new_canvas_type,
            details_json={
                "source_canvas_id": canvas_id,
                "title": new_name,
                "content": forked_content,
            },
        ))

        db.commit()

    return {
        "success": True,
        "message": f"Canvas forked to {new_id}",
        "canvas": {
            "id": new_id,
            "name": new_name,
            "canvas_type": new_canvas_type,
            "created_by": str(current_user.id),
            "share_token": None,
            "status": "active",
        },
    }


@router.get("/{canvas_id}/journey")
async def get_canvas_journey(
    canvas_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Full change journey for a canvas: every edit/action with actor
    attribution (which hire vs. which human), supervisor corrections with
    original→corrected previews, and HITL action proposals with their
    approval states — the traceable "who did what, when" timeline.
    """
    from core.models import (
        AgentProposal,
        AgentRegistry,
        CanvasAudit,
        CanvasContext,
    )

    # Ownership: same guard as read_canvas_content (audit-trail ownership).
    from tools.canvas_crud_tool import read_canvas

    owned = await read_canvas(str(current_user.id), canvas_id)
    if not owned.get("success"):
        raise HTTPException(status_code=404, detail=owned.get("error"))

    agent_names: dict = {}
    events: list = []

    audits = (
        db.query(CanvasAudit)
        .filter(CanvasAudit.canvas_id == canvas_id)
        .order_by(CanvasAudit.created_at.desc())
        .limit(limit)
        .all()
    )
    for row in audits:
        if row.agent_id and row.agent_id not in agent_names:
            agent = db.query(AgentRegistry).filter(AgentRegistry.id == row.agent_id).first()
            agent_names[row.agent_id] = agent.name if agent else "Agent"
        detail = row.details_json or {}
        _content = detail.get("content", detail.get("data", detail.get("form_data")))
        events.append({
            "kind": "audit",
            "action": row.action_type,
            "actor_type": "agent" if row.agent_id else ("assistant" if row.session_id else "user"),
            # agent rows: the hire's name; chat-driven rows without a hire
            # (session_id stamped by the chat context): the platform
            # assistant; no session at all: a direct human edit/save.
            "actor": (
                agent_names.get(row.agent_id, "Agent") if row.agent_id
                else ("Assistant" if row.session_id else "You")
            ),
            "agent_id": row.agent_id,
            "at": row.created_at.isoformat() if row.created_at else None,
            "canvas_type": row.canvas_type,
            "summary": _audit_summary(row, detail),
            # The ACTUAL content at this version (capped) — a journey line
            # item that hides what was written is an audit in name only.
            "content_preview": _content_preview(_content, 140),
            "content": _content_text(_content, 2000),
            "title": detail.get("title"),
        })

    ctx = (
        db.query(CanvasContext)
        .filter(CanvasContext.canvas_id == canvas_id, CanvasContext.user_id == str(current_user.id))
        .first()
    )
    if ctx is not None:
        for corr in (ctx.user_corrections or [])[-limit:]:
            events.append({
                "kind": "correction",
                "action": "supervisor_correction",
                "actor_type": "supervisor",
                "actor": "You (supervisor)",
                "at": corr.get("timestamp"),
                "original": _content_preview((corr.get("original") or {}).get("content")),
                "corrected": _content_preview((corr.get("corrected") or {}).get("content")),
                "summary": "Supervisor corrected the hire's draft (learning signal recorded)",
            })
        for act in (ctx.session_history or [])[-limit:]:
            if not isinstance(act, dict) or act.get("type") != "canvas_edit_proposal":
                continue
            events.append({
                "kind": "learning_proposal",
                "action": "draft_proposal",
                "actor_type": "agent",
                "actor": agent_names.get(act.get("agent_id"), "Hire"),
                "at": act.get("timestamp"),
                "summary": f"Immature hire proposed an edit: {str(act.get('instruction', ''))[:80]}",
            })

    proposals = (
        db.query(AgentProposal)
        .filter(AgentProposal.canvas_id == canvas_id)
        .order_by(AgentProposal.created_at.desc())
        .limit(limit)
        .all()
    )
    for p in proposals:
        action = (p.proposal_data or {}).get("action_type", "action")
        _pdata = p.proposal_data or {}
        events.append({
            "kind": "proposal",
            "action": action,
            "actor_type": "agent",
            "actor": p.agent_name or "Agent",
            "agent_id": p.agent_id,
            "at": p.created_at.isoformat() if p.created_at else None,
            "status": p.status,
            "proposal_id": p.id,
            "title": p.title,
            "to": _pdata.get("to", ""),
            "subject": _pdata.get("subject", ""),
            # The actual draft the agent proposed to send.
            "content_preview": _content_preview(_pdata.get("body"), 140),
            "content": _content_text(_pdata.get("body"), 2000),
            "summary": f"{action} proposed — status: {str(p.status).replace('_', ' ')}",
        })

    events.sort(key=lambda e: e.get("at") or "", reverse=True)
    return {
        "success": True,
        "canvas_id": canvas_id,
        "events": events[:limit],
        "pending_proposals": [e for e in events if e.get("status") == "pending_approval"],
    }


def _content_preview(content: Any, cap: int = 160) -> str:
    if isinstance(content, dict):
        content = content.get("content", content)
    text = str(content or "")
    return text if len(text) <= cap else text[:cap] + "…"


def _content_text(content: Any, cap: int) -> Optional[str]:
    """Full-ish content for the expanded journey row (None when absent)."""
    if content is None:
        return None
    if isinstance(content, dict):
        content = content.get("content", content)
        if isinstance(content, dict):
            import json as _json
            try:
                content = _json.dumps(content, indent=2, default=str)
            except Exception:
                content = str(content)
    text = str(content or "").strip()
    if not text:
        return None
    return text if len(text) <= cap else text[:cap] + "…"


def _audit_summary(row, detail: Optional[dict] = None) -> str:
    action = row.action_type or "action"
    detail = detail or {}
    if action in ("email_send", "email_send_attempt"):
        _to = detail.get("to") or detail.get("recipients")
        if isinstance(_to, (list, tuple)):
            _to = ", ".join(str(x) for x in _to[:3])
        return f"Email send attempted{f' → {_to}' if _to else ''}"
    if action == "update":
        return "Canvas content updated"
    if action == "present":
        return "Canvas created/presented"
    if action == "delete":
        return "Canvas deleted"
    if action == "submit":
        return "Form submitted"
    return f"Canvas {action}"


@router.get("/{canvas_id}/history")
async def get_canvas_history(
    canvas_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get the version history (audit trail) for a canvas."""
    from core.database import get_db_session
    from core.models import CanvasAudit
    from sqlalchemy import desc

    try:
        with get_db_session() as db:
            # BUG-071: Verify ownership before returning audit history.
            # Previously any authenticated user could read another user's
            # canvas edit history by supplying the canvas_id. Uses the
            # audit-aware owner check so agent-created canvases (audit-trail
            # only, no Canvas row) resolve their owner from CanvasAudit.
            from tools.canvas_crud_tool import _verify_canvas_owner
            if not _verify_canvas_owner(db, canvas_id, str(current_user.id)):
                raise HTTPException(status_code=404, detail="Canvas not found")

            audits = db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
            ).order_by(desc(CanvasAudit.created_at)).limit(50).all()

            history = [
                {
                    "audit_id": a.id,
                    "canvas_id": a.canvas_id,
                    "canvas_type": a.canvas_type,
                    "action_type": a.action_type,
                    "user_id": a.user_id,
                    "details": a.details_json,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in audits
            ]
        return {"success": True, "canvas_id": canvas_id, "history": history, "count": len(history)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Canvas audit history failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve audit history")


@router.get("/")
@router.get("", include_in_schema=False)
async def list_user_canvases(
    canvas_type: Optional[str] = None,
    include_deleted: bool = False,
    q: Optional[str] = Query(None, max_length=200, description="Search across title, content, type, and canvas id"),
    limit: int = Query(60, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
    session_id: Optional[str] = Query(None, max_length=255, description="Scope to canvases touched in one chat session"),
    current_user: User = Depends(get_current_user)
):
    """List the current user's canvases — searchable, paginated, recency-first.

    The discovery surface for finding a canvas as the count grows: ``q``
    matches derived titles, canvas bodies (so untitled canvases are findable
    by content), type, and id; every item carries ``display_title`` (never a
    raw UUID) and a ``snippet`` windowed around the match. ``session_id``
    scopes the list to one chat session (the agent-chat Artifacts panel).
    """
    from tools.canvas_crud_tool import list_canvases
    result = await list_canvases(
        str(current_user.id), canvas_type, include_deleted,
        q=q, limit=limit, offset=offset,
        session_id=session_id,
    )
    return result


# ============================================================================
# Context Management (Memory & Learning)
# ============================================================================

@router.post("/{canvas_id}/context")
async def create_context(
    canvas_id: str,
    request: CreateContextRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create or get canvas context for agent memory."""
    service = ServiceFactory.get_canvas_context_service(db, tenant_id=current_user.tenant_id)
    
    context = service.get_or_create_context(
        canvas_id=canvas_id,
        canvas_type=request.canvas_type,
        user_id=current_user.id,
        agent_id=request.agent_id
    )
    
    if request.initial_state:
        service.update_state(
            canvas_id=canvas_id,
            user_id=current_user.id,
            state_update=request.initial_state
        )
    
    return router.success_response(
        data={"context_id": context.id, "canvas_id": canvas_id},
        message="Canvas context initialized"
    )


@router.get("/{canvas_id}/context")
async def get_context(
    canvas_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get canvas context snapshot for agent memory."""
    service = ServiceFactory.get_canvas_context_service(db, tenant_id=current_user.tenant_id)
    
    snapshot = service.get_context_snapshot(
        canvas_id=canvas_id,
        user_id=current_user.id
    )
    
    if not snapshot:
        raise HTTPException(status_code=404, detail="Canvas context not found")
    
    return router.success_response(data=snapshot)


@router.put("/{canvas_id}/context/state")
async def update_context_state(
    canvas_id: str,
    request: UpdateStateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update persistsed canvas state."""
    service = ServiceFactory.get_canvas_context_service(db, tenant_id=current_user.tenant_id)

    # Basic validation: ensure state_update is not empty
    if not request.state_update:
        raise HTTPException(status_code=400, detail="State update cannot be empty")

    # TODO: Add canvas-specific schema validation if canvas_type is provided
    # This would involve calling get_canvas_schema(request.canvas_type) and
    # validating the state_update against that schema

    success = service.update_state(
        canvas_id=canvas_id,
        user_id=current_user.id,
        state_update=request.state_update
    )

    if not success:
        raise HTTPException(status_code=404, detail="Canvas context not found")

    return router.success_response(message="State updated")


@router.post("/{canvas_id}/context/correction")
async def record_correction(
    canvas_id: str,
    request: RecordCorrectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Record user correction for agent learning."""
    service = ServiceFactory.get_canvas_context_service(db, tenant_id=current_user.tenant_id)
    
    success = service.record_user_correction(
        canvas_id=canvas_id,
        user_id=current_user.id,
        original_action=request.original_action,
        corrected_action=request.corrected_action,
        context_info=request.context_info
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Canvas context not found")

    return router.success_response(message="Correction recorded for learning")


# ============================================================================
# Canvas Submission
# ============================================================================

@router.post("/submit")
async def submit_canvas(
    request: CanvasSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Submit one scoped event with a durable, independently verified receipt."""
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from core.canvas_write_service import submit_canvas_verified

    result = await submit_canvas_verified(
        user_id=str(current_user.id),
        canvas_id=request.canvas_id,
        form_data=request.form_data,
        operation_id=request.operation_id,
        agent_id=request.agent_id,
        agent_execution_id=request.agent_execution_id,
    )
    status = int(result.get("http_status") or 503)
    verified = bool(result.get("success") and (result.get("verification") or {}).get("status") == "verified")
    body = {
        **result,
        "success": verified,
        "data": {
            "canvas_id": request.canvas_id,
            "submitted": verified,
            "timestamp": result.get("submitted_at"),
        },
    }
    body.pop("http_status", None)
    if result.get("error_code") == "GOVERNANCE_DENIED":
        refusal = router.error_response(
            error_code="GOVERNANCE_DENIED",
            message=result.get("error"), status_code=status)
        body["detail"] = refusal.detail
    return JSONResponse(status_code=status, content=jsonable_encoder(body))


# ============================================================================
# Recording & Audit
# ============================================================================

@router.post("/recordings/start")
async def start_recording(
    request: StartRecordingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Start recording a canvas session."""
    service = ServiceFactory.get_canvas_recording_service(
        db, tenant_id=current_user.tenant_id,
        workspace_id=getattr(current_user, "workspace_id", None) or "default",
    )
    
    recording_id = await service.start_recording(
        user_id=str(current_user.id),
        agent_id=request.agent_id,
        canvas_id=request.canvas_id,
        reason=f"manual_{request.canvas_type}",
        tags=[request.canvas_type] if request.canvas_type else None,
    )

    return router.success_response(
        data={"recording_id": recording_id},
        message="Recording started"
    )


# NOTE: GET /recordings and GET /recordings/{recording_id} are registered
# earlier in this module (before GET /{canvas_id}) to avoid route shadowing.
# See the "Recordings (list + detail)" section above.


# ============================================================================
# Summarization
# ============================================================================

@router.get("/{canvas_id}/summary")
async def get_canvas_summary(
    canvas_id: str,
    force_refresh: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate LLM-powered summary of canvas state.

    Flow:
    1. Fetch canvas context (canvas_type + state) via CanvasContextService.
    2. Pass to CanvasSummaryService.generate_summary with correct signature.
    """
    from core.llm.canvas_summary_service import CanvasSummaryService

    try:
        # 1. Fetch the canvas context (ownership-checked via user_id)
        ctx_service = ServiceFactory.get_canvas_context_service(
            db, tenant_id=current_user.tenant_id
        )
        snapshot = ctx_service.get_context_snapshot(
            canvas_id=canvas_id,
            user_id=current_user.id
        )
        if not snapshot:
            raise HTTPException(status_code=404, detail="Canvas context not found")

        canvas_type = snapshot.get("canvas_type", "unknown")
        canvas_state = snapshot.get("state", snapshot)

        # 2. Generate summary with correct signature
        summary_service = CanvasSummaryService(db)
        summary = await summary_service.generate_summary(
            canvas_type=canvas_type,
            canvas_state=canvas_state,
        )
    except HTTPException:
        raise
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Summary generation timed out")
    except Exception as e:
        logger.error(f"Failed to generate summary for canvas {canvas_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate summary")

    if not summary:
        raise HTTPException(status_code=500, detail="Failed to generate summary")

    return router.success_response(data={"summary": summary})


# ============================================================================
# WebSockets (Real-Time State)
# ============================================================================

class CanvasStateConnectionManager:
    """Manages WebSocket connections for canvas state streaming"""
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, canvas_id: str, websocket: WebSocket):
        await websocket.accept()
        if canvas_id not in self.active_connections:
            self.active_connections[canvas_id] = []
        self.active_connections[canvas_id].append(websocket)

    def disconnect(self, canvas_id: str, websocket: WebSocket):
        if canvas_id in self.active_connections:
            if websocket in self.active_connections[canvas_id]:
                self.active_connections[canvas_id].remove(websocket)

    async def broadcast_state(self, canvas_id: str, state: Dict[str, Any]):
        await self.broadcast_message(
            canvas_id, {"type": "canvas:state_change", "state": state})

    async def broadcast_message(self, canvas_id: str, message: Dict[str, Any]):
        """Send an already-shaped canvas event to this canvas's subscribers."""
        if canvas_id in self.active_connections:
            failed_connections = []
            for connection in self.active_connections[canvas_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.warning(f"Failed to send to WebSocket connection: {e}")
                    failed_connections.append(connection)

            # Clean up dead connections
            for conn in failed_connections:
                self.disconnect(canvas_id, conn)

manager = CanvasStateConnectionManager()

@ws_router.websocket("/ws/{canvas_id}")
async def canvas_state_websocket(canvas_id: str, websocket: WebSocket):
    """WebSocket for real-time canvas state sync.

    SECURITY: Requires JWT authentication via the ``token`` query parameter.
    Without this, any attacker who knows a canvas ID could inject state
    changes into other users' sessions via ``canvas:state_update`` messages.
    """
    from core.auth import get_current_user_ws
    from core.database import SessionLocal

    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Missing authentication token")
        return

    db = SessionLocal()
    try:
        user = await get_current_user_ws(token, db)
    finally:
        db.close()

    if user is None:
        await websocket.close(code=1008, reason="Invalid or expired token")
        return

    # C2 fix: verify the user owns (or can access) this canvas before
    # allowing WS state injection. Previously any authenticated user who
    # knew a canvas_id could broadcast state_update to its viewers.
    # Fail-closed: a NONEXISTENT canvas_id is also rejected (the original
    # `if canvas and ...` guard short-circuited on None and accepted unknown
    # ids, letting a user hold an authorized WS for an id that doesn't exist).
    from tools.canvas_crud_tool import _verify_canvas_owner
    db = SessionLocal()
    try:
        # Audit-aware owner check: agent-created canvases (present_* tools)
        # have no Canvas row — their owner lives on CanvasAudit. Still
        # fail-closed for unknown ids and non-owners.
        if not _verify_canvas_owner(db, canvas_id, str(user.id)):
            await websocket.close(code=1008, reason="Not authorized for this canvas")
            return
    finally:
        db.close()

    await manager.connect(canvas_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "canvas:state_update":
                state = data.get("state", {})
                await manager.broadcast_state(canvas_id, state)
                # BUG-099: Previously WS edits were broadcast but never
                # persisted — lost on reopen. Now persist via the canvas
                # CRUD tool (append-only audit trail).
                try:
                    from tools.canvas_crud_tool import update_canvas_content
                    await update_canvas_content(str(user.id), canvas_id, state, "generic")
                except Exception as persist_err:
                    logger.warning(f"Canvas WS state not persisted: {persist_err}")
    except WebSocketDisconnect:
        manager.disconnect(canvas_id, websocket)
    except Exception:
        manager.disconnect(canvas_id, websocket)


# ============================================================================
# P7 — Per-canvas server runtime (logic endpoints).
# Saving/running canvas logic requires AUTONOMOUS maturity (governance gate
# mirrors custom_components_service._check_governance_for_js).
# ============================================================================


def _require_canvas_access(db: Session, canvas_id: str, current_user: User) -> None:
    """Owner on private canvases, anyone on collaborative ones; fail-closed.

    R89: shared by PUT (already had it inline), GET (leaked logic source) and
    POST run (executed other users' logic with attacker-chosen inputs).
    """
    from core.models import Canvas

    canvas = db.query(Canvas).filter(Canvas.id == canvas_id).first()
    if canvas is None:
        raise HTTPException(status_code=404, detail=f"Canvas {canvas_id} not found")
    if not canvas.is_collaborative and str(canvas.created_by) != str(current_user.id):
        raise HTTPException(status_code=403, detail="You do not have permission to edit this canvas")


def _enforce_logic_governance(svc, agent_id: Optional[str]) -> None:
    """R89: the AUTONOMOUS gate is mandatory. The previous `if body.agent_id:`
    wiring let a caller bypass the maturity check entirely by omitting the
    field — check_governance(None) already raises PermissionError."""
    try:
        svc.check_governance(agent_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


class CanvasLogicRequest(BaseModel):
    source: str = Field("", description="Python source to save")
    language: str = Field("python")
    agent_id: Optional[str] = Field(None, description="Agent saving the logic (AUTONOMOUS required)")


class CanvasLogicRunRequest(BaseModel):
    inputs: Dict[str, Any] = Field(default_factory=dict)
    agent_id: Optional[str] = Field(None, description="Agent running the logic (AUTONOMOUS required)")


@router.put("/{canvas_id}/logic")
async def put_canvas_logic(
    canvas_id: str,
    body: CanvasLogicRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save per-canvas server-side Python logic."""
    from core.canvas_logic_service import CanvasLogicService
    from core.models import Canvas

    # Access gate: writing logic mutates the canvas's controller. Allow the
    # owner on private canvases and any collaborator on collaborative canvases
    # (mini-app blueprint/instance canvases are created collaborative). A
    # stranger must never overwrite a private canvas's logic.
    _require_canvas_access(db, canvas_id, current_user)

    svc = CanvasLogicService(db)
    _enforce_logic_governance(svc, body.agent_id)
    saved = svc.save_logic(
        canvas_id=canvas_id,
        source=body.source,
        language=body.language,
        created_by=str(current_user.id),
    )
    return {"success": True, "data": saved, "message": "Canvas logic saved"}


@router.get("/{canvas_id}/logic")
async def get_canvas_logic(
    canvas_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Load the canvas's stored server-side logic.

    A canvas with NO logic yet returns an empty default (200) rather than a
    404: the Logic tab read-fires on every open, and an error response made
    the tab look broken on every fresh canvas (observed live — the only
    right-panel route 404ing). The empty payload matches save_logic's shape
    so the panel's editor just starts empty.
    """
    from core.canvas_logic_service import CanvasLogicService

    # R89: logic source is canvas content — same access rule as PUT.
    _require_canvas_access(db, canvas_id, current_user)

    logic = CanvasLogicService(db).load_logic(canvas_id)
    if logic is None:
        logic = {
            "id": None,
            "canvas_id": canvas_id,
            "language": "python",
            "source": "",
            "created_by": None,
        }
    return {"success": True, "data": logic}


@router.post("/{canvas_id}/logic/run")
async def run_canvas_logic(
    canvas_id: str,
    body: CanvasLogicRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run the canvas's stored logic in the isolated sandbox runtime."""
    from core.canvas_logic_service import CanvasLogicService

    # R89: ownership first, then the (now non-bypassable) AUTONOMOUS gate.
    _require_canvas_access(db, canvas_id, current_user)
    svc = CanvasLogicService(db)
    _enforce_logic_governance(svc, body.agent_id)
    result = await svc.run(canvas_id, inputs=body.inputs, agent_id=body.agent_id)
    return {"success": result.get("success", True), "data": result}


class ClearChatFeedbackRequest(BaseModel):
    input_summary: str


@router.post("/{canvas_id}/chat-feedback/clear")
async def clear_canvas_chat_feedback(
    canvas_id: str,
    request: ClearChatFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Clear the persisted thumbs choice for one assistant message (the
    panel's "click the same thumb again to clear" gesture). Sets the map
    entry to None — a merge, so other messages' feedback is preserved.
    """
    from core.models import CanvasContext
    from core.service_factory import ServiceFactory

    service = ServiceFactory.get_canvas_context_service(
        db, tenant_id=getattr(current_user, "tenant_id", None) or "default"
    )
    ctx = service.get_context(canvas_id, str(current_user.id))
    if ctx is None:
        row = db.query(CanvasContext).filter(CanvasContext.canvas_id == canvas_id).first()
        ctx = row
    if ctx is None:
        return {"success": True, "cleared": False}  # nothing persisted yet
    state = dict(ctx.current_state or {})
    fb_map = dict(state.get("chat_feedback") or {})
    fb_map[str(request.input_summary or "")[:200]] = None
    state["chat_feedback"] = fb_map
    ctx.current_state = state
    db.commit()
    return {"success": True, "cleared": True}
