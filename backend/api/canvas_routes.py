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
    state_update: dict = Field(..., description="Key-value pairs to update in current state")


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
    """List all available canvas types and their state schemas."""
    # Governance check
    governance = AgentGovernanceService(db)
    check = governance.can_perform_action(
        agent_id=agent_id,
        action_type="read_canvas"
    )

    if not check.get("allowed", True):
        return router.error_response(
            error_code="GOVERNANCE_DENIED",
            message=check.get("reason"),
            status_code=403
        )

    # Simplified representation of canvas types for the API
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
    service_factory = ServiceFactory(db)
    service = service_factory.get_canvas_context_service(tenant_id=current_user.tenant_id)
    
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
    service_factory = ServiceFactory(db)
    service = service_factory.get_canvas_context_service(tenant_id=current_user.tenant_id)
    
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
    service_factory = ServiceFactory(db)
    service = service_factory.get_canvas_context_service(tenant_id=current_user.tenant_id)
    
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
    service_factory = ServiceFactory(db)
    service = service_factory.get_canvas_context_service(tenant_id=current_user.tenant_id)
    
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
            return router.error_response(
                error_code="GOVERNANCE_DENIED",
                message=check.get("reason", "Permission denied"),
                status_code=403
            )

    # TODO: Process form submission, save to database, etc.
    # For now, return success
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
    service_factory = ServiceFactory(db)
    service = service_factory.get_canvas_recording_service(tenant_id=current_user.tenant_id)
    
    recording = service.start_recording(
        canvas_id=request.canvas_id,
        canvas_type=request.canvas_type,
        user_id=current_user.id,
        agent_id=request.agent_id,
        session_name=request.session_name,
        autonomous=request.autonomous
    )
    
    return router.success_response(
        data={"recording_id": recording.recording_id},
        message="Recording started"
    )


@router.get("/recordings")
async def list_recordings(
    canvas_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List canvas recordings."""
    service_factory = ServiceFactory(db)
    service = service_factory.get_canvas_recording_service(tenant_id=current_user.tenant_id)
    
    recordings = service.list_recordings(
        user_id=current_user.id,
        canvas_id=canvas_id,
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
    """Get recording details and timeline."""
    service_factory = ServiceFactory(db)
    service = service_factory.get_canvas_recording_service(tenant_id=current_user.tenant_id)
    
    playback = service.get_playback_data(recording_id)
    if not playback:
        raise HTTPException(status_code=404, detail="Recording not found")
        
    return router.success_response(data=playback)


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
    """Generate LLM-powered summary of canvas state."""
    service_factory = ServiceFactory(db)
    service = service_factory.get_canvas_summary_service(tenant_id=current_user.tenant_id)
    
    summary = await service.generate_summary(
        canvas_id=canvas_id,
        user_id=current_user.id,
        force_refresh=force_refresh
    )
    
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
            for connection in self.active_connections[canvas_id]:
                try:
                    await connection.send_json({"type": "canvas:state_change", "state": state})
                except Exception: pass

manager = CanvasStateConnectionManager()

@router.websocket("/ws/{canvas_id}")
async def canvas_state_websocket(canvas_id: str, websocket: WebSocket):
    """WebSocket for real-time state sync."""
    await manager.connect(canvas_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "canvas:state_update":
                await manager.broadcast_state(canvas_id, data.get("state", {}))
    except WebSocketDisconnect:
        manager.disconnect(canvas_id, websocket)
