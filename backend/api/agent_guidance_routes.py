"""
Agent Guidance API Routes

REST endpoints for agent guidance operations including:
- Operation tracking
- View orchestration
- Error guidance
- Agent requests
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.agent_guidance_canvas_tool import get_agent_guidance_system
from core.agent_request_manager import get_agent_request_manager
from core.database import get_db
from core.error_guidance_engine import get_error_guidance_engine
from core.models import AgentOperationTracker, AgentRequestLog, User
from core.security_dependencies import get_current_user
from core.view_coordinator import get_view_coordinator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent-guidance", tags=["agent-guidance"])


# Request/Response Models
class OperationStartRequest(BaseModel):
    agent_id: str
    operation_type: str
    context: Dict[str, Any]
    total_steps: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class OperationUpdateRequest(BaseModel):
    step: Optional[str] = None
    progress: Optional[int] = None
    add_log: Optional[Dict[str, Any]] = None
    what: Optional[str] = None
    why: Optional[str] = None
    next_steps: Optional[str] = None


class OperationCompleteRequest(BaseModel):
    status: str = "completed"  # completed or failed
    final_message: Optional[str] = None


class ViewSwitchRequest(BaseModel):
    agent_id: str
    view_type: str  # browser, terminal, canvas
    url: Optional[str] = None  # For browser view
    command: Optional[str] = None  # For terminal view
    guidance: str
    session_id: Optional[str] = None


class ViewLayoutRequest(BaseModel):
    layout: str  # canvas, split_horizontal, split_vertical, tabs, grid
    session_id: Optional[str] = None


class ErrorPresentRequest(BaseModel):
    operation_id: str
    error: Dict[str, Any]
    agent_id: Optional[str] = None


class ResolutionTrackRequest(BaseModel):
    error_type: str
    error_code: Optional[str] = None
    resolution_attempted: str
    success: bool
    user_feedback: Optional[str] = None
    agent_suggested: bool = True


class PermissionRequestRequest(BaseModel):
    agent_id: str
    title: str
    permission: str
    context: Dict[str, Any]
    urgency: str = "medium"
    expires_in: Optional[int] = None


class DecisionRequestRequest(BaseModel):
    agent_id: str
    title: str
    explanation: str
    options: list
    context: Dict[str, Any]
    urgency: str = "low"
    suggested_option: int = 0
    expires_in: Optional[int] = None


class RequestRespondRequest(BaseModel):
    request_id: str
    response: Dict[str, Any]


# Operation Tracking Endpoints
@router.post("/operation/start")
async def start_operation(
    request: OperationStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start a new agent operation and broadcast to canvas.

    Creates an operation tracker and broadcasts to user's canvas for
    real-time visibility.
    """
    try:
        guidance_system = get_agent_guidance_system(db)

        operation_id = await guidance_system.start_operation(
            user_id=current_user.id,
            agent_id=request.agent_id,
            operation_type=request.operation_type,
            context=request.context,
            total_steps=request.total_steps,
            metadata=request.metadata
        )

        return {
            "success": True,
            "operation_id": operation_id,
            "message": "Operation started"
        }

    except Exception as e:
        logger.error(f"Failed to start operation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/operation/{operation_id}/update")
async def update_operation(
    operation_id: str,
    request: OperationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update operation progress and context.

    Updates step, progress, context, or adds log entries to operation.
    """
    try:
        guidance_system = get_agent_guidance_system(db)

        # Update step and progress
        if request.step or request.progress or request.add_log:
            await guidance_system.update_step(
                user_id=current_user.id,
                operation_id=operation_id,
                step=request.step,
                progress=request.progress,
                add_log=request.add_log
            )

        # Update context
        if request.what or request.why or request.next_steps:
            await guidance_system.update_context(
                user_id=current_user.id,
                operation_id=operation_id,
                what=request.what,
                why=request.why,
                next_steps=request.next_steps
            )

        return {
            "success": True,
            "message": "Operation updated"
        }

    except Exception as e:
        logger.error(f"Failed to update operation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/operation/{operation_id}/complete")
async def complete_operation(
    operation_id: str,
    request: OperationCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark operation as completed or failed.

    Finalizes operation status and broadcasts completion to canvas.
    """
    try:
        guidance_system = get_agent_guidance_system(db)

        await guidance_system.complete_operation(
            user_id=current_user.id,
            operation_id=operation_id,
            status=request.status,
            final_message=request.final_message
        )

        return {
            "success": True,
            "message": f"Operation {request.status}"
        }

    except Exception as e:
        logger.error(f"Failed to complete operation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/operation/{operation_id}")
async def get_operation(
    operation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get operation details by ID.

    Returns current state of tracked operation.
    """
    try:
        operation = db.query(AgentOperationTracker).filter(
            AgentOperationTracker.operation_id == operation_id,
            AgentOperationTracker.user_id == current_user.id
        ).first()

        if not operation:
            raise HTTPException(status_code=404, detail="Operation not found")

        return {
            "success": True,
            "operation": {
                "operation_id": operation.operation_id,
                "agent_id": operation.agent_id,
                "operation_type": operation.operation_type,
                "status": operation.status,
                "current_step": operation.current_step,
                "total_steps": operation.total_steps,
                "current_step_index": operation.current_step_index,
                "progress": operation.progress,
                "context": {
                    "what": operation.what_explanation,
                    "why": operation.why_explanation,
                    "next": operation.next_steps
                },
                "logs": operation.logs,
                "metadata": operation.metadata,
                "started_at": operation.started_at.isoformat() if operation.started_at else None,
                "completed_at": operation.completed_at.isoformat() if operation.completed_at else None
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get operation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# View Orchestration Endpoints
@router.post("/view/switch")
async def switch_view(
    request: ViewSwitchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Switch to a different view (browser, terminal, canvas).

    Activates specified view with agent guidance via canvas.
    """
    try:
        view_coordinator = get_view_coordinator(db)

        if request.view_type == "browser":
            if not request.url:
                raise HTTPException(status_code=400, detail="URL required for browser view")

            await view_coordinator.switch_to_browser_view(
                user_id=current_user.id,
                agent_id=request.agent_id,
                url=request.url,
                guidance=request.guidance,
                session_id=request.session_id
            )

        elif request.view_type == "terminal":
            if not request.command:
                raise HTTPException(status_code=400, detail="Command required for terminal view")

            await view_coordinator.switch_to_terminal_view(
                user_id=current_user.id,
                agent_id=request.agent_id,
                command=request.command,
                guidance=request.guidance,
                session_id=request.session_id
            )

        else:
            raise HTTPException(status_code=400, detail=f"Unknown view type: {request.view_type}")

        return {
            "success": True,
            "message": f"Switched to {request.view_type} view"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to switch view: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/view/layout")
async def set_layout(
    request: ViewLayoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Set multi-view layout.

    Configures layout for canvas/browser/terminal views.
    """
    try:
        view_coordinator = get_view_coordinator(db)

        await view_coordinator.set_layout(
            user_id=current_user.id,
            layout=request.layout,
            session_id=request.session_id
        )

        return {
            "success": True,
            "message": f"Layout set to {request.layout}"
        }

    except Exception as e:
        logger.error(f"Failed to set layout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Error Guidance Endpoints
@router.post("/error/present")
async def present_error(
    request: ErrorPresentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Present error with resolution suggestions to user.

    Broadcasts error with actionable resolutions to canvas.
    """
    try:
        error_engine = get_error_guidance_engine(db)

        await error_engine.present_error(
            user_id=current_user.id,
            operation_id=request.operation_id,
            error=request.error,
            agent_id=request.agent_id
        )

        return {
            "success": True,
            "message": "Error presented with guidance"
        }

    except Exception as e:
        logger.error(f"Failed to present error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/error/track-resolution")
async def track_resolution(
    request: ResolutionTrackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Track error resolution outcome for learning.

    Records which resolutions work for which errors to improve suggestions.
    """
    try:
        error_engine = get_error_guidance_engine(db)

        await error_engine.track_resolution(
            error_type=request.error_type,
            error_code=request.error_code,
            resolution_attempted=request.resolution_attempted,
            success=request.success,
            user_feedback=request.user_feedback,
            agent_suggested=request.agent_suggested
        )

        return {
            "success": True,
            "message": "Resolution tracked"
        }

    except Exception as e:
        logger.error(f"Failed to track resolution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Agent Request Endpoints
@router.post("/request/permission")
async def create_permission_request(
    request: PermissionRequestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a permission request from agent to user.

    Agent requests specific permission from user with context.
    """
    try:
        request_manager = get_agent_request_manager(db)

        request_id = await request_manager.create_permission_request(
            user_id=current_user.id,
            agent_id=request.agent_id,
            title=request.title,
            permission=request.permission,
            context=request.context,
            urgency=request.urgency,
            expires_in=request.expires_in
        )

        return {
            "success": True,
            "request_id": request_id,
            "message": "Permission request created"
        }

    except Exception as e:
        logger.error(f"Failed to create permission request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/request/decision")
async def create_decision_request(
    request: DecisionRequestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a decision request from agent to user.

    Agent asks user to make a decision with multiple options.
    """
    try:
        request_manager = get_agent_request_manager(db)

        request_id = await request_manager.create_decision_request(
            user_id=current_user.id,
            agent_id=request.agent_id,
            title=request.title,
            explanation=request.explanation,
            options=request.options,
            context=request.context,
            urgency=request.urgency,
            suggested_option=request.suggested_option,
            expires_in=request.expires_in
        )

        return {
            "success": True,
            "request_id": request_id,
            "message": "Decision request created"
        }

    except Exception as e:
        logger.error(f"Failed to create decision request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/request/{request_id}/respond")
async def respond_to_request(
    request_id: str,
    request: RequestRespondRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Respond to an agent request.

    User provides their response to a pending agent request.
    """
    try:
        request_manager = get_agent_request_manager(db)

        await request_manager.handle_response(
            user_id=current_user.id,
            request_id=request_id,
            response=request.response
        )

        return {
            "success": True,
            "message": "Response recorded"
        }

    except Exception as e:
        logger.error(f"Failed to respond to request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/request/{request_id}")
async def get_request(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get request details by ID.

    Returns current state of agent request.
    """
    try:
        request_log = db.query(AgentRequestLog).filter(
            AgentRequestLog.request_id == request_id,
            AgentRequestLog.user_id == current_user.id
        ).first()

        if not request_log:
            raise HTTPException(status_code=404, detail="Request not found")

        return {
            "success": True,
            "request": {
                "request_id": request_log.request_id,
                "agent_id": request_log.agent_id,
                "request_type": request_log.request_type,
                "request_data": request_log.request_data,
                "user_response": request_log.user_response,
                "created_at": request_log.created_at.isoformat(),
                "responded_at": request_log.responded_at.isoformat() if request_log.responded_at else None,
                "expires_at": request_log.expires_at.isoformat() if request_log.expires_at else None,
                "revoked": request_log.revoked
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get request: {e}")
        raise HTTPException(status_code=500, detail=str(e))
