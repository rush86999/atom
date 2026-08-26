"""
Unified Canvas API Routes
Consolidates state management, context tracking, recording, and summarization.
"""

import logging
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from core.database import get_db
from core.auth import get_current_user
from core.models import User
from core.base_routes import BaseAPIRouter
from core.service_factory import ServiceFactory
from core.agent_governance_service import AgentGovernanceService

logger = logging.getLogger(__name__)

# Note: Using BaseAPIRouter for consistency with atom-upstream's enhanced JSON responses
router = BaseAPIRouter(prefix="/api/canvas", tags=["Canvas"])


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
    service = ServiceFactory.get_canvas_recording_service(db, tenant_id=current_user.tenant_id)

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
    service = ServiceFactory.get_canvas_recording_service(db, tenant_id=current_user.tenant_id)

    recording = await service.get_recording(recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")

    # Ownership check — recording["user_id"] must match current_user.id
    if str(recording.get("user_id", "")) != str(current_user.id):
        # Return 404 (not 403) to avoid leaking existence of other users' recordings
        raise HTTPException(status_code=404, detail="Recording not found")

    return router.success_response(data=recording)


# ============================================================================
# Canvas CRUD — Read, Update, Delete (Create happens via agent tools)
# ============================================================================

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


@router.put("/{canvas_id}")
async def update_canvas_content(
    canvas_id: str,
    content: Dict[str, Any],
    canvas_type: str = "generic",
    title: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Update the content of an existing canvas."""
    from tools.canvas_crud_tool import update_canvas_content as update_fn
    result = await update_fn(
        str(current_user.id), canvas_id, content, canvas_type, title
    )
    if not result.get("success"):
        # BUG FIX: not-found errors must return 404 (consistent with GET
        # /{canvas_id}), not 400 — a missing canvas is not a bad request.
        status = 404 if "not found" in str(result.get("error", "")).lower() else 400
        raise HTTPException(status_code=status, detail=result.get("error"))
    return result


@router.delete("/{canvas_id}")
async def delete_canvas(
    canvas_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete (close) a specific canvas by ID."""
    from tools.canvas_crud_tool import delete_canvas as delete_fn
    result = await delete_fn(str(current_user.id), canvas_id)
    if not result.get("success"):
        # BUG FIX: not-found errors must return 404 (consistent with GET
        # /{canvas_id}), not 400 — a missing canvas is not a bad request.
        status = 404 if "not found" in str(result.get("error", "")).lower() else 400
        raise HTTPException(status_code=status, detail=result.get("error"))
    return result


@router.post("/{canvas_id}/fork")
async def fork_canvas(
    canvas_id: str,
    current_user: User = Depends(get_current_user)
):
    """Fork a canvas into a new, independent canvas owned by the current user.

    P5 Blueprint Security: forking never leaks credentials or history. The copy
    gets a fresh id, ``share_token`` reset to None, ``status`` "active", and
    ``created_by`` set to the current user. No audit history is carried over
    (exactly one "fork" row is written), and no context/artifacts/recordings/
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
        new_canvas_type = src.canvas_type

        # 2. Independent copy: copied fields, all identity/state fields reset.
        new_canvas = Canvas(
            id=new_id,
            tenant_id=src.tenant_id,
            workspace_id=src.workspace_id,
            created_by=str(current_user.id),
            name=new_name,
            description=src.description,
            canvas_type=new_canvas_type,
            content=src.content,
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
        db.add(CanvasAudit(
            canvas_id=new_id,
            tenant_id=src.tenant_id,
            action_type="fork",
            user_id=str(current_user.id),
            canvas_type=new_canvas_type,
            details_json={"source_canvas_id": canvas_id},
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
async def list_user_canvases(
    canvas_type: Optional[str] = None,
    include_deleted: bool = False,
    current_user: User = Depends(get_current_user)
):
    """List all canvases for the current user."""
    from tools.canvas_crud_tool import list_canvases
    result = await list_canvases(
        str(current_user.id), canvas_type, include_deleted
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
    """
    Submit form data for a canvas.

    Validates authentication, required fields, and governance permissions.
    """
    # Governance check if agent_id provided
    if request.agent_id:
        governance = AgentGovernanceService(db)
        check = governance.can_perform_action(
            agent_id=request.agent_id,
            action_type="canvas_submit"
        )

        if not check.get("allowed", True):
            raise router.error_response(
                error_code="GOVERNANCE_DENIED",
                message=check.get("reason", "Permission denied"),
                status_code=403
            )

    # Persist the submission via the canvas audit trail.
    try:
        from core.database import get_db_session
        from core.models import CanvasAudit
        with get_db_session() as db:
            audit = CanvasAudit(
                canvas_id=request.canvas_id,
                tenant_id=getattr(current_user, "tenant_id", None) or "default",
                canvas_type="form",
                action_type="submit",
                user_id=str(current_user.id) if current_user else "system",
                agent_id=request.agent_id if hasattr(request, "agent_id") else None,
                details_json={
                    "form_data": request.form_data,
                    "agent_id": request.agent_id if hasattr(request, "agent_id") else None,
                    "submitted_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            db.add(audit)
            db.commit()
    except Exception as e:
        logger.warning(f"Canvas submit persistence failed (non-fatal): {e}")

    return router.success_response(
        data={
            "canvas_id": request.canvas_id,
            "submitted": True,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )


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
    service = ServiceFactory.get_canvas_recording_service(db, tenant_id=current_user.tenant_id)
    
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
        if canvas_id in self.active_connections:
            failed_connections = []
            for connection in self.active_connections[canvas_id]:
                try:
                    await connection.send_json({"type": "canvas:state_change", "state": state})
                except Exception as e:
                    logger.warning(f"Failed to send to WebSocket connection: {e}")
                    failed_connections.append(connection)

            # Clean up dead connections
            for conn in failed_connections:
                self.disconnect(canvas_id, conn)

manager = CanvasStateConnectionManager()

@router.websocket("/ws/{canvas_id}")
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
    """Load the canvas's stored server-side logic."""
    from core.canvas_logic_service import CanvasLogicService

    # R89: logic source is canvas content — same access rule as PUT.
    _require_canvas_access(db, canvas_id, current_user)

    logic = CanvasLogicService(db).load_logic(canvas_id)
    if logic is None:
        raise HTTPException(status_code=404, detail=f"No logic saved for canvas {canvas_id}")
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
