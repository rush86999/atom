"""
Supervision Routes

API endpoints for agent supervision monitoring and intervention.
Includes SSE endpoint for real-time log streaming.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import AgentExecution, SupervisionSession
from core.supervision_service import SupervisionService, SupervisionEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/supervision", tags=["supervision"])


# ============================================================================
# Request/Response Models
# ============================================================================

class InterventionRequest(BaseModel):
    """Request to intervene in agent execution"""
    intervention_type: str  # "pause", "correct", "terminate"
    guidance: str


class InterventionResponse(BaseModel):
    """Response to intervention request"""
    success: bool
    message: str
    session_state: str


class SupervisionSessionResponse(BaseModel):
    """Supervision session info"""
    session_id: str
    agent_id: str
    agent_name: str
    supervisor_id: str
    supervisor_type: str
    status: str
    started_at: str
    completed_at: Optional[str]
    duration_seconds: Optional[int]
    intervention_count: int


class LogEntry(BaseModel):
    """Log entry from execution"""
    timestamp: str
    level: str  # "info", "warning", "error"
    message: str
    data: Optional[dict]


# ============================================================================
# SSE Endpoint for Live Monitoring
# ============================================================================

@router.get("/{execution_id}/stream")
async def stream_supervision_logs(
    execution_id: str,
    db: Session = Depends(get_db)
):
    """
    Server-Sent Events stream for real-time supervision monitoring.

    Streams execution logs, progress updates, and events in real-time.
    Client should use EventSource to connect and listen for events.
    """
    # Verify execution exists
    execution = db.query(AgentExecution).filter(
        AgentExecution.id == execution_id
    ).first()

    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution not found: {execution_id}"
        )

    # Get supervision session
    session = db.query(SupervisionSession).filter(
        SupervisionSession.agent_id == execution.agent_id
    ).order_by(SupervisionSession.started_at.desc()).first()

    async def event_stream() -> AsyncGenerator[str, None]:
        """Generate SSE events for client."""
        try:
            supervision_service = SupervisionService(db)

            # Send initial connection event
            yield _format_sse("connected", {
                "execution_id": execution_id,
                "agent_id": execution.agent_id,
                "agent_name": execution.agent_name,
                "timestamp": datetime.now().isoformat()
            })

            # Stream supervision events
            async for event in supervision_service.monitor_agent_execution(
                session=session,
                db=db
            ):
                # Format event for SSE
                event_data = {
                    "event_type": event.event_type,
                    "timestamp": event.timestamp.isoformat(),
                    "data": event.data
                }

                yield _format_sse("supervision_event", event_data)

                # Check if execution is complete
                if event.event_type in ["execution_completed", "execution_failed", "error"]:
                    yield _format_sse("done", {
                        "execution_id": execution_id,
                        "timestamp": datetime.now().isoformat()
                    })
                    break

        except Exception as e:
            logger.error(f"Error in SSE stream: {e}", exc_info=True)
            yield _format_sse("error", {
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            })

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


def _format_sse(event: str, data: dict) -> str:
    """Format data as Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ============================================================================
# Intervention Endpoints
# ============================================================================

@router.post("/sessions/{session_id}/intervene", response_model=InterventionResponse)
async def intervene_in_session(
    session_id: str,
    request: InterventionRequest,
    db: Session = Depends(get_db)
):
    """
    Intervene in agent execution.

    Allows supervisor to pause, correct, or terminate execution.
    """
    supervision_service = SupervisionService(db)

    try:
        result = await supervision_service.intervene(
            session_id=session_id,
            intervention_type=request.intervention_type,
            guidance=request.guidance
        )

        return InterventionResponse(
            success=result.success,
            message=result.message,
            session_state=result.session_state
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to intervene: {str(e)}"
        )


@router.post("/sessions/{session_id}/complete")
async def complete_supervision_session(
    session_id: str,
    supervisor_rating: int = Query(..., ge=1, le=5, description="Rating 1-5"),
    feedback: str = Query(..., description="Feedback text"),
    db: Session = Depends(get_db)
):
    """
    Complete supervision session and record outcomes.

    Updates agent confidence based on session performance.
    """
    supervision_service = SupervisionService(db)

    try:
        outcome = await supervision_service.complete_supervision(
            session_id=session_id,
            supervisor_rating=supervisor_rating,
            feedback=feedback
        )

        return {
            "success": True,
            "session_id": outcome.session_id,
            "duration_seconds": outcome.duration_seconds,
            "intervention_count": outcome.intervention_count,
            "confidence_boost": outcome.confidence_boost
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete session: {str(e)}"
        )


# ============================================================================
# Session Query Endpoints
# ============================================================================

@router.get("/sessions/active", response_model=List[SupervisionSessionResponse])
async def get_active_sessions(
    workspace_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get currently active supervision sessions."""
    supervision_service = SupervisionService(db)

    try:
        sessions = await supervision_service.get_active_sessions(
            workspace_id=workspace_id,
            limit=limit
        )

        return [
            SupervisionSessionResponse(
                session_id=s.id,
                agent_id=s.agent_id,
                agent_name=s.agent_name,
                supervisor_id=s.supervisor_id,
                supervisor_type="user",  # Could be determined from session
                status=s.status,
                started_at=s.started_at.isoformat(),
                completed_at=s.completed_at.isoformat() if s.completed_at else None,
                duration_seconds=s.duration_seconds,
                intervention_count=s.intervention_count
            )
            for s in sessions
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active sessions: {str(e)}"
        )


@router.get("/agents/{agent_id}/sessions", response_model=List[SupervisionSessionResponse])
async def get_agent_supervision_history(
    agent_id: str,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get agent's supervision history."""
    supervision_service = SupervisionService(db)

    try:
        history = await supervision_service.get_supervision_history(
            agent_id=agent_id,
            limit=limit
        )

        return [
            SupervisionSessionResponse(
                session_id=h["session_id"],
                agent_id=agent_id,
                agent_name="",  # Not included in history
                supervisor_id="",  # Not included in history
                supervisor_type="user",
                status=h["status"],
                started_at=h["started_at"],
                completed_at=h.get("completed_at"),
                duration_seconds=h.get("duration_seconds"),
                intervention_count=h.get("intervention_count", 0)
            )
            for h in history
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get supervision history: {str(e)}"
        )


@router.get("/sessions/{session_id}", response_model=SupervisionSessionResponse)
async def get_supervision_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get details of a specific supervision session."""
    session = db.query(SupervisionSession).filter(
        SupervisionSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supervision session not found: {session_id}"
        )

    return SupervisionSessionResponse(
        session_id=session.id,
        agent_id=session.agent_id,
        agent_name=session.agent_name,
        supervisor_id=session.supervisor_id,
        supervisor_type="user",  # Could be determined from session
        status=session.status,
        started_at=session.started_at.isoformat(),
        completed_at=session.completed_at.isoformat() if session.completed_at else None,
        duration_seconds=session.duration_seconds,
        intervention_count=session.intervention_count
    )


# ============================================================================
# Autonomous Approval Endpoint
# ============================================================================

@router.post("/proposals/{proposal_id}/autonomous-approve")
async def autonomous_approve_proposal(
    proposal_id: str,
    db: Session = Depends(get_db)
):
    """
    Attempt autonomous approval/rejection of proposal.

    When human supervisor is unavailable, tries to find autonomous agent
    to review and approve/reject proposal.
    """
    from core.proposal_service import ProposalService

    proposal_service = ProposalService(db)

    try:
        result = await proposal_service.autonomous_approve_or_reject(
            proposal_id=proposal_id
        )

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process autonomous approval: {str(e)}"
        )
