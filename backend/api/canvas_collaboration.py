"""
Multi-Agent Canvas Collaboration API Endpoints

REST API for managing multi-agent collaboration on shared canvases with:
- Session creation and management
- Agent role-based permissions
- Conflict detection and resolution
- Activity tracking

Endpoints:
- POST /api/canvas-collab/session/create - Create collaboration session
- POST /api/canvas-collab/session/{session_id}/add-agent - Add agent to session
- DELETE /api/canvas-collab/session/{session_id}/remove-agent - Remove agent
- GET /api/canvas-collab/session/{session_id}/status - Get session status
- POST /api/canvas-collab/session/{session_id}/check-conflict - Check for conflicts
- POST /api/canvas-collab/session/{session_id}/resolve-conflict - Resolve conflict
- POST /api/canvas-collab/session/{session_id}/complete - Complete session
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.canvas_collaboration_service import CanvasCollaborationService

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateSessionRequest(BaseModel):
    """Request to create a collaboration session."""
    canvas_id: str = Field(..., description="Canvas identifier")
    session_id: str = Field(..., description="Canvas session identifier")
    user_id: str = Field(..., description="Owner user ID")
    collaboration_mode: str = Field(default="sequential", description="Mode: sequential, parallel, locked")
    max_agents: int = Field(default=5, ge=1, le=10, description="Maximum agents in session")
    initial_agent_id: Optional[str] = Field(None, description="Optional first agent to add")


class AddAgentRequest(BaseModel):
    """Request to add agent to session."""
    agent_id: str = Field(..., description="Agent to add")
    user_id: str = Field(..., description="User initiating the agent")
    role: str = Field(default="contributor", description="Agent role")
    permissions: Optional[Dict[str, Any]] = Field(None, description="Specific permissions")


class RemoveAgentRequest(BaseModel):
    """Request to remove agent from session."""
    agent_id: str = Field(..., description="Agent to remove")


class CheckConflictRequest(BaseModel):
    """Request to check for conflicts."""
    agent_id: str = Field(..., description="Agent performing action")
    component_id: Optional[str] = Field(None, description="Component being modified")
    action: Dict[str, Any] = Field(..., description="Action details")


class ResolveConflictRequest(BaseModel):
    """Request to resolve a conflict."""
    agent_a_id: str = Field(..., description="First agent")
    agent_b_id: str = Field(..., description="Second agent")
    component_id: str = Field(..., description="Contested component")
    agent_a_action: Dict[str, Any] = Field(..., description="First agent's action")
    agent_b_action: Dict[str, Any] = Field(..., description="Second agent's action")
    resolution_strategy: str = Field(default="first_come_first_served", description="Resolution strategy")


class RecordActionRequest(BaseModel):
    """Request to record agent action."""
    agent_id: str = Field(..., description="Agent performing action")
    action: str = Field(..., description="Action performed")
    component_id: Optional[str] = Field(None, description="Component ID")


class ReleaseLockRequest(BaseModel):
    """Request to release component lock."""
    agent_id: str = Field(..., description="Agent holding lock")
    component_id: str = Field(..., description="Component to unlock")


# ============================================================================
# Session Management Endpoints
# ============================================================================

@router.post("/session/create")
async def create_collaboration_session(
    request: CreateSessionRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new multi-agent collaboration session.

    Enables multiple agents to work together on a shared canvas
    with configurable collaboration modes and permissions.

    Request Body:
        - canvas_id: Canvas identifier
        - session_id: Canvas session identifier
        - user_id: Owner user ID
        - collaboration_mode: sequential, parallel, or locked (default: sequential)
        - max_agents: Maximum agents (default: 5)
        - initial_agent_id: Optional first agent

    Response:
        Created session data
    """
    service = CanvasCollaborationService(db)
    result = service.create_collaboration_session(
        canvas_id=request.canvas_id,
        session_id=request.session_id,
        user_id=request.user_id,
        collaboration_mode=request.collaboration_mode,
        max_agents=request.max_agents,
        initial_agent_id=request.initial_agent_id
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/session/{session_id}/add-agent")
async def add_agent_to_session(
    session_id: str,
    request: AddAgentRequest,
    db: Session = Depends(get_db)
):
    """
    Add an agent to a collaboration session.

    Request Body:
        - agent_id: Agent to add
        - user_id: User initiating the agent
        - role: owner, contributor, reviewer, viewer (default: contributor)
        - permissions: Optional specific permissions

    Response:
        Participant data with role and permissions
    """
    service = CanvasCollaborationService(db)
    result = service.add_agent_to_session(
        collaboration_session_id=session_id,
        agent_id=request.agent_id,
        user_id=request.user_id,
        role=request.role,
        permissions=request.permissions
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.delete("/session/{session_id}/remove-agent")
async def remove_agent_from_session(
    session_id: str,
    request: RemoveAgentRequest,
    db: Session = Depends(get_db)
):
    """
    Remove an agent from a collaboration session.

    Request Body:
        - agent_id: Agent to remove

    Response:
        Removal confirmation
    """
    service = CanvasCollaborationService(db)
    result = service.remove_agent_from_session(
        collaboration_session_id=session_id,
        agent_id=request.agent_id
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/session/{session_id}/status")
async def get_session_status(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get current status of a collaboration session.

    Returns session details including:
    - Active participants
    - Their roles and permissions
    - Activity levels
    - Held locks

    Response:
        Session status with participant details
    """
    service = CanvasCollaborationService(db)
    result = service.get_session_status(session_id)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.post("/session/{session_id}/complete")
async def complete_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Complete a collaboration session.

    Marks all active participants as completed and
    provides summary statistics.

    Response:
        Completion summary with:
        - Total participants
        - Total actions performed
        - Total conflicts resolved
    """
    service = CanvasCollaborationService(db)
    result = service.complete_session(session_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


# ============================================================================
# Permission and Conflict Endpoints
# ============================================================================

@router.post("/session/{session_id}/check-permission")
async def check_agent_permission(
    session_id: str,
    agent_id: str = Query(..., description="Agent to check"),
    action: str = Query(..., description="Action to check"),
    component_id: Optional[str] = Query(None, description="Optional component"),
    db: Session = Depends(get_db)
):
    """
    Check if an agent has permission to perform an action.

    Query Parameters:
        - session_id: Collaboration session ID
        - agent_id: Agent to check
        - action: Action (read, write, delete, lock)
        - component_id: Optional component

    Response:
        Permission check result with allowed boolean and reason
    """
    service = CanvasCollaborationService(db)
    result = service.check_agent_permission(
        collaboration_session_id=session_id,
        agent_id=agent_id,
        action=action,
        component_id=component_id
    )

    return result


@router.post("/session/{session_id}/check-conflict")
async def check_for_conflicts(
    session_id: str,
    request: CheckConflictRequest,
    db: Session = Depends(get_db)
):
    """
    Check if an action conflicts with other agents' work.

    Analyzes potential conflicts based on:
    - Sequential mode: Recent agent activity
    - Parallel mode: Held locks
    - Locked mode: Existing component locks

    Request Body:
        - agent_id: Agent performing action
        - component_id: Component being modified
        - action: Action details

    Response:
        Conflict check result
    """
    service = CanvasCollaborationService(db)
    result = service.check_for_conflicts(
        collaboration_session_id=session_id,
        agent_id=request.agent_id,
        component_id=request.component_id,
        action=request.action
    )

    return result


@router.post("/session/{session_id}/resolve-conflict")
async def resolve_conflict(
    session_id: str,
    request: ResolveConflictRequest,
    db: Session = Depends(get_db)
):
    """
    Resolve a conflict between two agents.

    Uses the specified resolution strategy to determine
    which agent's action should proceed and logs the conflict.

    Request Body:
        - agent_a_id: First agent
        - agent_b_id: Second agent
        - component_id: Contested component
        - agent_a_action: First agent's action
        - agent_b_action: Second agent's action
        - resolution_strategy: first_come_first_served, priority, merge

    Response:
        Resolution result with conflict ID and final action
    """
    service = CanvasCollaborationService(db)
    result = service.resolve_conflict(
        collaboration_session_id=session_id,
        agent_a_id=request.agent_a_id,
        agent_b_id=request.agent_b_id,
        component_id=request.component_id,
        agent_a_action=request.agent_a_action,
        agent_b_action=request.agent_b_action,
        resolution_strategy=request.resolution_strategy
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


# ============================================================================
# Activity Tracking Endpoints
# ============================================================================

@router.post("/session/{session_id}/record-action")
async def record_agent_action(
    session_id: str,
    request: RecordActionRequest,
    db: Session = Depends(get_db)
):
    """
    Record an agent's action in the collaboration session.

    Updates activity tracking and manages locks for parallel mode.

    Request Body:
        - agent_id: Agent performing action
        - action: Action performed
        - component_id: Optional component ID

    Response:
        Recorded action data
    """
    service = CanvasCollaborationService(db)
    result = service.record_agent_action(
        collaboration_session_id=session_id,
        agent_id=request.agent_id,
        action=request.action,
        component_id=request.component_id
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/session/{session_id}/release-lock")
async def release_agent_lock(
    session_id: str,
    request: ReleaseLockRequest,
    db: Session = Depends(get_db)
):
    """
    Release a lock held by an agent on a component.

    Used in parallel collaboration mode when an agent is done
    working on a component.

    Request Body:
        - agent_id: Agent holding lock
        - component_id: Component to unlock

    Response:
        Lock release result
    """
    service = CanvasCollaborationService(db)
    result = service.release_agent_lock(
        collaboration_session_id=session_id,
        agent_id=request.agent_id,
        component_id=request.component_id
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


# ============================================================================
# Query Endpoints
# ============================================================================

@router.get("/sessions")
async def list_collaboration_sessions(
    canvas_id: Optional[str] = Query(None, description="Filter by canvas ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Max results"),
    db: Session = Depends(get_db)
):
    """
    List collaboration sessions with optional filtering.

    Query Parameters:
        - canvas_id: Optional canvas filter
        - status: Optional status filter (active, paused, completed)
        - limit: Maximum results

    Response:
        List of collaboration sessions
    """
    from core.models import CanvasCollaborationSession

    query = db.query(CanvasCollaborationSession)

    if canvas_id:
        query = query.filter(CanvasCollaborationSession.canvas_id == canvas_id)

    if status:
        query = query.filter(CanvasCollaborationSession.status == status)

    sessions = query.order_by(CanvasCollaborationSession.created_at.desc()).limit(limit).all()

    return {
        "total": len(sessions),
        "sessions": [
            {
                "session_id": s.id,
                "canvas_id": s.canvas_id,
                "status": s.status,
                "collaboration_mode": s.collaboration_mode,
                "max_agents": s.max_agents,
                "created_at": s.created_at.isoformat()
            }
            for s in sessions
        ]
    }
