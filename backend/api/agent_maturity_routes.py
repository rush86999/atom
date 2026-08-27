"""Agent Maturity Journey Routes

REST endpoints for the STUDENT→INTERN→SUPERVISED journey:
- Training proposals + sessions (STUDENT agents routed to training by
  TriggerInterceptor)
- Action proposal review/execute (INTERN agents, via ProposalService)

These endpoints were originally exposed by ``api/maturity_routes.py``, which
was removed in the July 2026 dead-code cleanup with zero replacements —
severing the training-approval and completion links that feed confidence
boosts and STUDENT→INTERN promotion (StudentTrainingService was fully
implemented and tested but unreachable). This module restores the surface
with current conventions: role-gated mutations (R65 supervisor gate), token
identity (no client-supplied user ids), and generic error responses.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth import get_current_user, User
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import (
    AgentProposal,
    ProposalStatus,
    ProposalType,
    TrainingSession,
    User as UserModel,
    UserRole,
)
from core.proposal_service import ProposalService
from core.student_training_service import StudentTrainingService, TrainingOutcome

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/maturity", tags=["Agent Maturity"])

# Mutations here change agent confidence/maturity or execute proposals —
# supervisor-grade roles only (same gate as supervision routes, R65).
_SUPERVISOR_ROLES = [
    UserRole.TEAM_LEAD.value,
    UserRole.WORKSPACE_ADMIN.value,
    UserRole.SUPER_ADMIN.value,
]


def _require_supervisor(db, current_user: User) -> None:
    """Require a supervisor-grade role (TEAM_LEAD+), 403 otherwise."""
    user = db.query(UserModel).filter(UserModel.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role not in _SUPERVISOR_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Required role: TEAM_LEAD or ADMIN",
        )


# ============================================================================
# Request Models
# ============================================================================


class ApproveTrainingRequest(BaseModel):
    """Request to approve (or reject) a training proposal."""

    approve: bool = Field(..., description="Whether to approve the training")
    duration_override: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional duration override (duration_override_hours, hours_per_day_limit)",
    )


class CompleteTrainingRequest(BaseModel):
    """Request to complete a training session (feeds the learning loop)."""

    performance_score: float = Field(..., ge=0.0, le=1.0)
    supervisor_feedback: str
    errors_count: int = Field(..., ge=0)
    tasks_completed: int = Field(..., ge=0)
    total_tasks: int = Field(..., gt=0)
    capabilities_developed: List[str] = Field(default_factory=list)
    capability_gaps_remaining: List[str] = Field(default_factory=list)


class ApproveActionProposalRequest(BaseModel):
    """Request to approve (and execute) an action proposal."""

    approve: bool
    modifications: Optional[Dict[str, Any]] = None


class RejectProposalRequest(BaseModel):
    reason: str


# ============================================================================
# Training Proposals (STUDENT journey)
# ============================================================================


@router.get("/training/proposals")
async def list_training_proposals(
    agent_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List training proposals for STUDENT agents."""
    query = db.query(AgentProposal).filter(
        AgentProposal.proposal_type == ProposalType.WORKFLOW.value
    )
    if agent_id:
        query = query.filter(AgentProposal.agent_id == agent_id)
    if status_filter:
        query = query.filter(AgentProposal.status == status_filter)
    proposals = query.order_by(AgentProposal.created_at.desc()).limit(limit).all()

    def _training_fields(p: AgentProposal) -> Dict[str, Any]:
        # Learning fields live inside the proposal_data JSON column (there are
        # no capability_gaps/learning_objectives columns on the model).
        data: Dict[str, Any] = p.proposal_data if isinstance(p.proposal_data, dict) else {}
        fields = {
            "capability_gaps": data.get("capability_gaps", []),
            "learning_objectives": data.get("learning_objectives", []),
            "estimated_duration_hours": data.get("estimated_duration_hours"),
        }
        # Active training session, when this proposal was approved — the
        # supervisor completes the session (score + feedback) from the UI.
        from core.models import TrainingSession as _TS

        active = (
            db.query(_TS)
            .filter(
                _TS.proposal_id == p.id,
                _TS.status.in_(["scheduled", "active", "in_progress", "pending"]),
            )
            .order_by(_TS.started_at.desc())
            .first()
        )
        if active:
            fields["active_session_id"] = active.id
            fields["session_status"] = active.status
        return fields

    return {
        "proposals": [
            {
                "id": p.id,
                "agent_id": p.agent_id,
                "agent_name": p.agent_name,
                "title": p.title,
                "description": p.description,
                "status": str(p.status) if p.status else None,
                **_training_fields(p),
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "approved_by": p.approved_by,
                "approved_at": p.approved_at.isoformat() if p.approved_at else None,
            }
            for p in proposals
        ]
    }


@router.get("/training/proposals/{proposal_id}")
async def get_training_proposal(
    proposal_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    proposal = (
        db.query(AgentProposal)
        .filter(
            AgentProposal.id == proposal_id,
            AgentProposal.proposal_type == ProposalType.WORKFLOW.value,
        )
        .first()
    )
    if not proposal:
        raise HTTPException(status_code=404, detail=f"Training proposal {proposal_id} not found")

    data: Dict[str, Any] = proposal.proposal_data if isinstance(proposal.proposal_data, dict) else {}
    return {
        "id": proposal.id,
        "agent_id": proposal.agent_id,
        "agent_name": proposal.agent_name,
        "title": proposal.title,
        "description": proposal.description,
        "proposal_type": str(proposal.proposal_type) if proposal.proposal_type else None,
        "capability_gaps": data.get("capability_gaps", []),
        "learning_objectives": data.get("learning_objectives", []),
        "estimated_duration_hours": data.get("estimated_duration_hours"),
        "duration_estimation_confidence": data.get("duration_estimation_confidence"),
        "duration_estimation_reasoning": data.get("duration_estimation_reasoning"),
        "training_scenario_template": data.get("training_scenario_template"),
        "status": str(proposal.status) if proposal.status else None,
        "approved_by": proposal.approved_by,
        "approved_at": proposal.approved_at.isoformat() if proposal.approved_at else None,
        "created_at": proposal.created_at.isoformat() if proposal.created_at else None,
    }


@router.post("/training/proposals/{proposal_id}/approve")
async def approve_training_proposal(
    proposal_id: str,
    request: ApproveTrainingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approve a training proposal (creates a TrainingSession) or reject it."""
    _require_supervisor(db, current_user)

    if not request.approve:
        proposal = db.query(AgentProposal).filter(AgentProposal.id == proposal_id).first()
        if not proposal:
            raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
        proposal.status = ProposalStatus.REJECTED.value
        db.commit()
        return {"message": "Training proposal rejected", "proposal_id": proposal_id}

    try:
        session = await StudentTrainingService(db).approve_training(
            proposal_id=proposal_id,
            user_id=str(current_user.id),
            modifications=request.duration_override,
        )
    except ValueError as e:
        # Controlled validation message from our own service layer.
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(
        "Training approved: proposal=%s session=%s approved_by=%s",
        proposal_id, session.id, current_user.id,
    )
    return {
        "message": "Training approved and session created",
        "session_id": session.id,
        "proposal_id": proposal_id,
    }


@router.post("/training/proposals/{proposal_id}/reject")
async def reject_training_proposal(
    proposal_id: str,
    request: RejectProposalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_supervisor(db, current_user)
    user_id: str = str(current_user.id)
    proposal = db.query(AgentProposal).filter(AgentProposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")

    proposal.status = ProposalStatus.REJECTED.value
    proposal.approver_id = user_id
    proposal.reviewed_at = datetime.now()
    # NOTE: AgentProposal has no free-form execution_result column; the reason
    # lives in approval_reason (writing an undeclared attribute would be
    # silently dropped by SQLAlchemy identity-map bookkeeping).
    proposal.approval_reason = request.reason
    db.commit()

    return {"message": "Training proposal rejected", "proposal_id": proposal_id}


@router.post("/training/sessions/{session_id}/complete")
async def complete_training_session(
    session_id: str,
    request: CompleteTrainingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Complete a training session — boosts agent confidence and may promote
    STUDENT → INTERN (the promotion link severed when the old routes died)."""
    _require_supervisor(db, current_user)

    outcome = TrainingOutcome(
        performance_score=request.performance_score,
        supervisor_feedback=request.supervisor_feedback,
        errors_count=request.errors_count,
        tasks_completed=request.tasks_completed,
        total_tasks=request.total_tasks,
        capabilities_developed=request.capabilities_developed,
        capability_gaps_remaining=request.capability_gaps_remaining,
    )
    try:
        result = await StudentTrainingService(db).complete_training_session(
            session_id=session_id, outcome=outcome
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logger.info("Training completed: session=%s result_keys=%s", session_id, sorted(result.keys()))
    return result


@router.get("/agents/{agent_id}/training-history")
async def get_agent_training_history(
    agent_id: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(TrainingSession)
        .filter(TrainingSession.agent_id == agent_id)
        .order_by(TrainingSession.started_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "agent_id": agent_id,
        "training_history": [
            {
                "id": s.id,
                "status": s.status,
                "supervisor_id": s.supervisor_id,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "total_tasks": getattr(s, "total_tasks", None),
                "tasks_completed": getattr(s, "tasks_completed", None),
            }
            for s in sessions
        ],
    }


# ============================================================================
# Action Proposals (INTERN journey)
# ============================================================================


@router.get("/proposals")
async def list_action_proposals(
    agent_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List action proposals from INTERN agents."""
    query = db.query(AgentProposal).filter(
        AgentProposal.proposal_type.in_([ProposalType.ACTION.value, ProposalType.ANALYSIS.value])
    )
    if agent_id:
        query = query.filter(AgentProposal.agent_id == agent_id)
    if status_filter:
        query = query.filter(AgentProposal.status == status_filter)
    proposals = query.order_by(AgentProposal.created_at.desc()).limit(limit).all()

    return {
        "proposals": [
            {
                "id": p.id,
                "tenant_id": p.tenant_id,
                "agent_id": p.agent_id,
                "agent_name": p.agent_name,
                "canvas_id": p.canvas_id,
                "session_id": p.session_id,
                "title": p.title,
                "description": p.description,
                "status": p.status,
                "proposed_action": p.proposed_action,
                "reasoning": p.reasoning,
                "reversible": p.reversible,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "approved_by": p.approved_by,
                "approved_at": p.approved_at.isoformat() if p.approved_at else None,
            }
            for p in proposals
        ]
    }


@router.post("/proposals/{proposal_id}/approve")
async def approve_action_proposal(
    proposal_id: str,
    request: ApproveActionProposalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approve an action proposal and execute it (INTERN HITL loop)."""
    _require_supervisor(db, current_user)
    user_id: str = str(current_user.id)
    service = ProposalService(db)
    try:
        if not request.approve:
            await service.reject_proposal(
                proposal_id=proposal_id,
                user_id=user_id,
                reason="User rejected the proposal",
            )
            return {"message": "Proposal rejected", "proposal_id": proposal_id}

        execution_result = await service.approve_proposal(
            proposal_id=proposal_id,
            user_id=user_id,
            modifications=request.modifications,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "message": "Proposal approved and executed",
        "proposal_id": proposal_id,
        "execution_result": execution_result,
    }


@router.post("/proposals/{proposal_id}/reject")
async def reject_action_proposal(
    proposal_id: str,
    request: RejectProposalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_supervisor(db, current_user)
    user_id: str = str(current_user.id)
    try:
        await ProposalService(db).reject_proposal(
            proposal_id=proposal_id,
            user_id=user_id,
            reason=request.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": "Proposal rejected", "proposal_id": proposal_id}


@router.get("/agents/{agent_id}/proposal-history")
async def get_agent_proposal_history(
    agent_id: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    history = await ProposalService(db).get_proposal_history(
        agent_id=agent_id, limit=limit
    )
    return {"agent_id": agent_id, "proposal_history": history}
