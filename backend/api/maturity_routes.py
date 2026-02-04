"""
Maturity API Routes

REST endpoints for training proposals, action proposals, and supervision sessions.
Supports all maturity levels: STUDENT (training), INTERN (proposals), SUPERVISED (monitoring).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import (
    AgentProposal,
    AgentRegistry,
    BlockedTriggerContext,
    ProposalStatus,
    ProposalType,
    SupervisionSession,
    SupervisionStatus,
    TrainingSession,
)
from core.proposal_service import ProposalService
from core.student_training_service import StudentTrainingService, TrainingOutcome
from core.supervision_service import SupervisionOutcome, SupervisionService
from core.training_websocket_events import TrainingWebSocketEvents

router = APIRouter(prefix="/api/maturity", tags=["Agent Maturity"])


# ============================================================================
# Pydantic Models for Request/Response
# ============================================================================

class ApproveTrainingRequest(BaseModel):
    """Request to approve training proposal"""
    approve: bool = Field(..., description="Whether to approve the training")
    duration_override: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional duration override (user_specified_hours, reason, hours_per_day, deadline)"
    )


class CompleteTrainingRequest(BaseModel):
    """Request to complete training session"""
    performance_score: float = Field(..., ge=0.0, le=1.0, description="Performance score (0.0-1.0)")
    supervisor_feedback: str = Field(..., description="Supervisor's feedback")
    errors_count: int = Field(..., ge=0, description="Number of errors during training")
    tasks_completed: int = Field(..., ge=0, description="Number of tasks completed")
    total_tasks: int = Field(..., gt=0, description="Total number of training tasks")
    capabilities_developed: List[str] = Field(default_factory=list, description="Capabilities developed")
    capability_gaps_remaining: List[str] = Field(default_factory=list, description="Remaining capability gaps")


class ActionProposalRequest(BaseModel):
    """Request to create action proposal (INTERN agent)"""
    intern_agent_id: str = Field(..., description="INTERN agent creating proposal")
    trigger_context: Dict[str, Any] = Field(..., description="Trigger context")
    proposed_action: Dict[str, Any] = Field(..., description="Proposed action details")
    reasoning: str = Field(..., description="Reasoning for the proposal")


class ApproveActionProposalRequest(BaseModel):
    """Request to approve action proposal"""
    approve: bool = Field(..., description="Whether to approve the proposal")
    modifications: Optional[Dict[str, Any]] = Field(None, description="Optional modifications to proposed action")


class RejectProposalRequest(BaseModel):
    """Request to reject proposal"""
    reason: str = Field(..., description="Reason for rejection")


class SupervisionInterventionRequest(BaseModel):
    """Request to intervene in supervision session"""
    intervention_type: str = Field(..., description="Type: pause, correct, terminate")
    guidance: str = Field(..., description="Supervisor's guidance")


class CompleteSupervisionRequest(BaseModel):
    """Request to complete supervision session"""
    supervisor_rating: int = Field(..., ge=1, le=5, description="Rating (1-5 stars)")
    feedback: str = Field(..., description="Supervisor's feedback")


# ============================================================================
# Training Proposals (STUDENT agents)
# ============================================================================

@router.get("/training/proposals")
async def list_training_proposals(
    agent_id: Optional[str] = Query(None, description="Filter by agent"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List training proposals for STUDENT agents"""
    query = db.query(AgentProposal).filter(
        AgentProposal.proposal_type == ProposalType.TRAINING.value
    )

    if agent_id:
        query = query.filter(AgentProposal.agent_id == agent_id)

    if status_filter:
        query = query.filter(AgentProposal.status == status_filter)

    proposals = query.order_by(
        AgentProposal.created_at.desc()
    ).limit(limit).all()

    return {
        "proposals": [
            {
                "id": p.id,
                "agent_id": p.agent_id,
                "agent_name": p.agent_name,
                "title": p.title,
                "description": p.description,
                "status": p.status,
                "capability_gaps": p.capability_gaps,
                "learning_objectives": p.learning_objectives,
                "estimated_duration_hours": p.estimated_duration_hours,
                "created_at": p.created_at.isoformat(),
                "approved_by": p.approved_by,
                "approved_at": p.approved_at.isoformat() if p.approved_at else None
            }
            for p in proposals
        ]
    }


@router.get("/training/proposals/{proposal_id}")
async def get_training_proposal(
    proposal_id: str,
    db: Session = Depends(get_db)
):
    """Get training proposal details"""
    proposal = db.query(AgentProposal).filter(
        AgentProposal.id == proposal_id,
        AgentProposal.proposal_type == ProposalType.TRAINING.value
    ).first()

    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training proposal {proposal_id} not found"
        )

    return {
        "id": proposal.id,
        "agent_id": proposal.agent_id,
        "agent_name": proposal.agent_name,
        "title": proposal.title,
        "description": proposal.description,
        "proposal_type": proposal.proposal_type,
        "capability_gaps": proposal.capability_gaps,
        "learning_objectives": proposal.learning_objectives,
        "estimated_duration_hours": proposal.estimated_duration_hours,
        "duration_estimation_confidence": proposal.duration_estimation_confidence,
        "duration_estimation_reasoning": proposal.duration_estimation_reasoning,
        "training_scenario_template": proposal.training_scenario_template,
        "status": proposal.status,
        "proposed_by": proposal.proposed_by,
        "approved_by": proposal.approved_by,
        "approved_at": proposal.approved_at.isoformat() if proposal.approved_at else None,
        "modifications": proposal.modifications,
        "training_start_date": proposal.training_start_date.isoformat() if proposal.training_start_date else None,
        "training_end_date": proposal.training_end_date.isoformat() if proposal.training_end_date else None,
        "created_at": proposal.created_at.isoformat()
    }


@router.post("/training/proposals/{proposal_id}/approve")
async def approve_training_proposal(
    proposal_id: str,
    request: ApproveTrainingRequest,
    user_id: str = Query(..., description="User approving the training"),
    db: Session = Depends(get_db)
):
    """Approve training proposal and create training session"""
    if not request.approve:
        # Reject proposal
        proposal = db.query(AgentProposal).filter(
            AgentProposal.id == proposal_id
        ).first()

        if not proposal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Proposal {proposal_id} not found"
            )

        proposal.status = ProposalStatus.REJECTED.value
        db.commit()

        return {"message": "Training proposal rejected", "proposal_id": proposal_id}

    # Approve and create session
    training_service = StudentTrainingService(db)

    try:
        session = await training_service.approve_training(
            proposal_id=proposal_id,
            user_id=user_id,
            modifications=request.duration_override
        )

        # Notify via WebSocket
        ws_events = TrainingWebSocketEvents(db)
        await ws_events.notify_training_approved(
            proposal_id=proposal_id,
            session_id=session.id,
            approved_by=user_id
        )

        return {
            "message": "Training approved and session created",
            "session_id": session.id,
            "proposal_id": proposal_id,
            "training_start_date": session.started_at.isoformat() if session.started_at else None
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/training/proposals/{proposal_id}/reject")
async def reject_training_proposal(
    proposal_id: str,
    request: RejectProposalRequest,
    user_id: str = Query(..., description="User rejecting the proposal"),
    db: Session = Depends(get_db)
):
    """Reject training proposal"""
    proposal = db.query(AgentProposal).filter(
        AgentProposal.id == proposal_id
    ).first()

    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal {proposal_id} not found"
        )

    proposal.status = ProposalStatus.REJECTED.value
    proposal.approved_by = user_id
    proposal.approved_at = datetime.now()

    # Store rejection reason
    if not proposal.execution_result:
        proposal.execution_result = {}
    proposal.execution_result["rejected"] = True
    proposal.execution_result["rejected_by"] = user_id
    proposal.execution_result["rejected_at"] = datetime.now().isoformat()
    proposal.execution_result["reason"] = request.reason

    db.commit()

    return {"message": "Training proposal rejected", "proposal_id": proposal_id}


@router.post("/training/sessions/{session_id}/complete")
async def complete_training_session(
    session_id: str,
    request: CompleteTrainingRequest,
    db: Session = Depends(get_db)
):
    """Complete training session and update agent maturity"""
    training_service = StudentTrainingService(db)

    try:
        outcome = TrainingOutcome(
            performance_score=request.performance_score,
            supervisor_feedback=request.supervisor_feedback,
            errors_count=request.errors_count,
            tasks_completed=request.tasks_completed,
            total_tasks=request.total_tasks,
            capabilities_developed=request.capabilities_developed,
            capability_gaps_remaining=request.capability_gaps_remaining
        )

        result = await training_service.complete_training_session(
            session_id=session_id,
            outcome=outcome
        )

        # Notify via WebSocket
        ws_events = TrainingWebSocketEvents(db)
        await ws_events.notify_training_completed(
            session_id=session_id,
            maturity_update=result
        )

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/agents/{agent_id}/training-history")
async def get_agent_training_history(
    agent_id: str,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get agent's training history"""
    training_service = StudentTrainingService(db)

    try:
        history = await training_service.get_training_history(
            agent_id=agent_id,
            limit=limit
        )

        return {"agent_id": agent_id, "training_history": history}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# Action Proposals (INTERN agents)
# ============================================================================

@router.get("/proposals")
async def list_action_proposals(
    agent_id: Optional[str] = Query(None, description="Filter by agent"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List action proposals from INTERN agents"""
    query = db.query(AgentProposal).filter(
        AgentProposal.proposal_type == ProposalType.ACTION.value
    )

    if agent_id:
        query = query.filter(AgentProposal.agent_id == agent_id)

    if status_filter:
        query = query.filter(AgentProposal.status == status_filter)

    proposals = query.order_by(
        AgentProposal.created_at.desc()
    ).limit(limit).all()

    return {
        "proposals": [
            {
                "id": p.id,
                "agent_id": p.agent_id,
                "agent_name": p.agent_name,
                "title": p.title,
                "description": p.description,
                "status": p.status,
                "proposed_action": p.proposed_action,
                "reasoning": p.reasoning,
                "created_at": p.created_at.isoformat(),
                "approved_by": p.approved_by,
                "approved_at": p.approved_at.isoformat() if p.approved_at else None
            }
            for p in proposals
        ]
    }


@router.get("/proposals/{proposal_id}")
async def get_action_proposal(
    proposal_id: str,
    db: Session = Depends(get_db)
):
    """Get action proposal details"""
    proposal = db.query(AgentProposal).filter(
        AgentProposal.id == proposal_id,
        AgentProposal.proposal_type.in_([ProposalType.ACTION.value, ProposalType.ANALYSIS.value])
    ).first()

    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal {proposal_id} not found"
        )

    return {
        "id": proposal.id,
        "agent_id": proposal.agent_id,
        "agent_name": proposal.agent_name,
        "title": proposal.title,
        "description": proposal.description,
        "proposal_type": proposal.proposal_type,
        "proposed_action": proposal.proposed_action,
        "reasoning": proposal.reasoning,
        "status": proposal.status,
        "proposed_by": proposal.proposed_by,
        "approved_by": proposal.approved_by,
        "approved_at": proposal.approved_at.isoformat() if proposal.approved_at else None,
        "modifications": proposal.modifications,
        "execution_result": proposal.execution_result,
        "created_at": proposal.created_at.isoformat()
    }


@router.post("/proposals/{proposal_id}/approve")
async def approve_action_proposal(
    proposal_id: str,
    request: ApproveActionProposalRequest,
    user_id: str = Query(..., description="User approving the proposal"),
    db: Session = Depends(get_db)
):
    """Approve action proposal and execute"""
    proposal_service = ProposalService(db)

    try:
        if not request.approve:
            # Reject
            await proposal_service.reject_proposal(
                proposal_id=proposal_id,
                user_id=user_id,
                reason="User rejected the proposal"
            )

            # Notify
            ws_events = TrainingWebSocketEvents(db)
            await ws_events.notify_proposal_rejected(
                proposal_id=proposal_id,
                rejected_by=user_id,
                reason="User rejected the proposal"
            )

            return {"message": "Proposal rejected", "proposal_id": proposal_id}

        # Approve and execute
        result = await proposal_service.approve_proposal(
            proposal_id=proposal_id,
            user_id=user_id,
            modifications=request.modifications
        )

        # Notify
        ws_events = TrainingWebSocketEvents(db)
        await ws_events.notify_proposal_approved(
            proposal_id=proposal_id,
            execution_result=result
        )

        return {
            "message": "Proposal approved and executed",
            "proposal_id": proposal_id,
            "execution_result": result
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/proposals/{proposal_id}/reject")
async def reject_action_proposal(
    proposal_id: str,
    request: RejectProposalRequest,
    user_id: str = Query(..., description="User rejecting the proposal"),
    db: Session = Depends(get_db)
):
    """Reject action proposal"""
    proposal_service = ProposalService(db)

    try:
        await proposal_service.reject_proposal(
            proposal_id=proposal_id,
            user_id=user_id,
            reason=request.reason
        )

        # Notify
        ws_events = TrainingWebSocketEvents(db)
        await ws_events.notify_proposal_rejected(
            proposal_id=proposal_id,
            rejected_by=user_id,
            reason=request.reason
        )

        return {"message": "Proposal rejected", "proposal_id": proposal_id}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/agents/{agent_id}/proposal-history")
async def get_agent_proposal_history(
    agent_id: str,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get agent's proposal history"""
    proposal_service = ProposalService(db)

    try:
        history = await proposal_service.get_proposal_history(
            agent_id=agent_id,
            limit=limit
        )

        return {"agent_id": agent_id, "proposal_history": history}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# Supervision Sessions (SUPERVISED agents)
# ============================================================================

@router.get("/supervision/sessions")
async def list_supervision_sessions(
    agent_id: Optional[str] = Query(None, description="Filter by agent"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List supervision sessions for SUPERVISED agents"""
    query = db.query(SupervisionSession)

    if agent_id:
        query = query.filter(SupervisionSession.agent_id == agent_id)

    if status_filter:
        query = query.filter(SupervisionSession.status == status_filter)

    sessions = query.order_by(
        SupervisionSession.started_at.desc()
    ).limit(limit).all()

    return {
        "sessions": [
            {
                "id": s.id,
                "agent_id": s.agent_id,
                "agent_name": s.agent_name,
                "workspace_id": s.workspace_id,
                "status": s.status,
                "supervisor_id": s.supervisor_id,
                "started_at": s.started_at.isoformat(),
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "duration_seconds": s.duration_seconds,
                "intervention_count": s.intervention_count,
                "supervisor_rating": s.supervisor_rating
            }
            for s in sessions
        ]
    }


@router.get("/supervision/sessions/{session_id}")
async def get_supervision_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get supervision session details"""
    session = db.query(SupervisionSession).filter(
        SupervisionSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supervision session {session_id} not found"
        )

    return {
        "id": session.id,
        "agent_id": session.agent_id,
        "agent_name": session.agent_name,
        "workspace_id": session.workspace_id,
        "status": session.status,
        "supervisor_id": session.supervisor_id,
        "started_at": session.started_at.isoformat(),
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "duration_seconds": session.duration_seconds,
        "intervention_count": session.intervention_count,
        "interventions": session.interventions,
        "agent_actions": session.agent_actions,
        "outcomes": session.outcomes,
        "supervisor_rating": session.supervisor_rating,
        "supervisor_feedback": session.supervisor_feedback,
        "confidence_boost": session.confidence_boost
    }


@router.post("/supervision/sessions/{session_id}/intervene")
async def intervene_in_session(
    session_id: str,
    request: SupervisionInterventionRequest,
    db: Session = Depends(get_db)
):
    """Intervene in supervision session"""
    supervision_service = SupervisionService(db)

    try:
        result = await supervision_service.intervene(
            session_id=session_id,
            intervention_type=request.intervention_type,
            guidance=request.guidance
        )

        # Notify
        ws_events = TrainingWebSocketEvents(db)
        await ws_events.notify_supervision_intervention(
            session_id=session_id,
            intervention_type=request.intervention_type,
            guidance=request.guidance
        )

        return {
            "message": result.message,
            "session_state": result.session_state
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/supervision/sessions/{session_id}/complete")
async def complete_supervision(
    session_id: str,
    request: CompleteSupervisionRequest,
    db: Session = Depends(get_db)
):
    """Complete supervision session and record outcomes"""
    supervision_service = SupervisionService(db)

    try:
        outcome = await supervision_service.complete_supervision(
            session_id=session_id,
            supervisor_rating=request.supervisor_rating,
            feedback=request.feedback
        )

        # Notify
        ws_events = TrainingWebSocketEvents(db)
        await ws_events.notify_supervision_completed(
            session_id=session_id,
            outcome={
                "success": outcome.success,
                "duration_seconds": outcome.duration_seconds,
                "intervention_count": outcome.intervention_count,
                "supervisor_rating": outcome.supervisor_rating,
                "feedback": outcome.feedback,
                "confidence_boost": outcome.confidence_boost
            }
        )

        return {
            "message": "Supervision session completed",
            "session_id": outcome.session_id,
            "success": outcome.success,
            "confidence_boost": outcome.confidence_boost
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ============================================================================
# WebSocket Endpoint for Real-Time Supervision Events
# ============================================================================

@router.websocket("/supervision/{session_id}/ws")
async def supervision_websocket(
    websocket: WebSocket,
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Real-time supervision events stream.

    Connect to receive live supervision events including:
    - Agent actions
    - Intermediate results
    - Potential issues
    - Intervention notifications
    """
    await websocket.accept()

    try:
        # Verify session exists
        session = db.query(SupervisionSession).filter(
            SupervisionSession.id == session_id
        ).first()

        if not session:
            await websocket.send_json({
                "error": "Supervision session not found"
            })
            await websocket.close()
            return

        # Send initial session state
        await websocket.send_json({
            "type": "session_connected",
            "session_id": session_id,
            "agent_id": session.agent_id,
            "status": session.status
        })

        # In production, this would subscribe to supervision events
        # and stream them as they occur
        # For now, keep connection alive

        while True:
            # Keep connection alive (heartbeat)
            await websocket.send_json({"type": "heartbeat", "timestamp": datetime.now().isoformat()})

            # Wait for client messages
            data = await websocket.receive_json()

            # Handle client requests if needed
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except Exception as e:
        logger.error(f"Supervision WebSocket error: {e}")
    finally:
        await websocket.close()
