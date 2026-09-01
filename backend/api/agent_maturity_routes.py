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

from fastapi import Depends, HTTPException, Query, Request
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
from core.student_training_service import (
    InsufficientTrainingEvidenceError,
    StudentTrainingService,
    TrainingOutcome,
)
from core.personal_scope import resolve_tenant_id
from core import role_template_registry

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/maturity", tags=["Agent Maturity"])

# Mutations here change agent confidence/maturity or execute proposals —
# supervisor-grade roles only (same gate as supervision routes, R65).
_SUPERVISOR_ROLES = [
    UserRole.TEAM_LEAD.value,
    UserRole.WORKSPACE_ADMIN.value,
    UserRole.SUPER_ADMIN.value,
]

# Statuses under which a training session can still be worked (and completed
# by the supervisor). Historical values kept for rows created before the
# status vocabulary settled.
_ACTIVE_SESSION_STATUSES = ["scheduled", "active", "in_progress", "pending"]


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
    """Request to complete a training session.

    The recorded outcome is derived from the session's linked episode
    evidence; ``performance_score`` is an optional supervisor claim that the
    backend caps by that evidence, and the task counts here are ignored in
    favor of the ledger.
    """

    performance_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    supervisor_feedback: str
    errors_count: int = Field(0, ge=0)
    tasks_completed: Optional[int] = Field(None, ge=0)
    total_tasks: Optional[int] = Field(None, gt=0)
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
                _TS.status.in_(_ACTIVE_SESSION_STATUSES),
            )
            .order_by(_TS.started_at.desc())
            .first()
        )
        if active:
            fields["active_session_id"] = active.id
            fields["session_status"] = active.status
            guidance = active.supervisor_guidance if isinstance(active.supervisor_guidance, dict) else {}
            fields["lesson_plan"] = guidance.get("lesson_plan") or guidance
            if guidance.get("canvas_id"):
                fields["canvas_id"] = guidance["canvas_id"]
                fields["canvas_url"] = f"/canvas/{guidance['canvas_id']}"
        # Student identity + trust state — the supervisor must know WHO is
        # being trained and where they stand before scoring.
        from core.models import AgentRegistry as _AR

        agent_row = db.query(_AR).filter(_AR.id == p.agent_id).first()
        fields["agent_tier"] = agent_row.status if agent_row else None
        fields["agent_confidence"] = agent_row.confidence_score if agent_row else None
        fields["agent_domain"] = ((agent_row.category if agent_row else None) or "").lower()
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
        "lesson_plan": (
            (
                session_row.supervisor_guidance or {}
            ).get("lesson_plan")
            if (
                (session_row := db.query(TrainingSession).filter(TrainingSession.proposal_id == proposal.id).order_by(TrainingSession.started_at.desc()).first())
                and isinstance(session_row.supervisor_guidance, dict)
            ) else None
        ),
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
    except InsufficientTrainingEvidenceError as e:
        # 422 with the live counts so the panel can render "1/3 recorded
        # runs" instead of a generic failure.
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INSUFFICIENT_TRAINING_EVIDENCE",
                "message": str(e),
                "evidence": e.evidence,
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logger.info("Training completed: session=%s result_keys=%s", session_id, sorted(result.keys()))
    return result


@router.get("/training/sessions/{session_id}/evidence")
async def get_training_session_evidence(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Live linked-evidence counts for a training session.

    Powers the supervisor panel: work runs the agent recorded since the
    session was approved, its success ratio, and the completion floor.
    """
    _require_supervisor(db, current_user)
    session = db.query(TrainingSession).filter(TrainingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    service = StudentTrainingService(db)
    evidence = service.get_session_evidence(session)
    return {"session_id": session_id, **evidence}




@router.patch("/training/sessions/{session_id}/guidance")
async def update_training_guidance(
    session_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Supervisor edits the mentor-proposed lesson plan for the session.

    The lesson arrives as the mentor's concrete proposal (tasks anchored in
    the hire's real ingested data); the supervisor may modify or replace any
    part before running the supervised pass.
    """
    _require_supervisor(db, current_user)
    session = db.query(TrainingSession).filter(TrainingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body must be JSON")

    guidance = session.supervisor_guidance if isinstance(session.supervisor_guidance, dict) else {}
    lesson = body.get("lesson_plan")
    if lesson is not None:
        if not isinstance(lesson, dict):
            raise HTTPException(status_code=400, detail="lesson_plan must be an object")
        guidance["lesson_plan"] = lesson
    if "supervisor_note" in body and isinstance(body["supervisor_note"], str):
        guidance["supervisor_note"] = body["supervisor_note"]
    session.supervisor_guidance = guidance
    db.commit()
    return {"success": True, "lesson_plan": guidance.get("lesson_plan")}


@router.get("/training/sessions/{session_id}/canvases")
def get_training_session_canvases(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Role canvases spawned for a training session (visual cards on /approvals).

    Phase 2 role-template registry: approving a training proposal spawns the
    role's typed-canvas set (ChatSession + Canvas + CanvasAudit rows stamped
    with the session id). This surface lets the supervisor review the trainee's
    work as cards instead of chat text.
    """
    _require_supervisor(db, current_user)
    session = (
        db.query(TrainingSession)
        .filter(TrainingSession.id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=404, detail=f"Training session {session_id} not found"
        )
    # Ownership gate (IDOR): the approving supervisor always sees their own
    # session; otherwise the caller must share the session's tenant. A
    # cross-tenant foreign UUID 404s (no existence leak). Tenant strings may
    # legitimately diverge (e.g. sessions created before proposal-tenant
    # inheritance stored "default"), so supervisor_id is authoritative.
    tenant_id = resolve_tenant_id(current_user)
    if (
        str(session.supervisor_id or "") != str(current_user.id)
        and session.tenant_id != tenant_id
    ):
        raise HTTPException(
            status_code=404, detail=f"Training session {session_id} not found"
        )
    # Audit rows are read under the SESSION's tenant (where spawn wrote
    # them), not the caller's — the two may differ for legacy sessions.
    canvases = role_template_registry.get_session_canvases(
        db, session_id, tenant_id=session.tenant_id
    )
    return {"session_id": session_id, "canvases": canvases}


@router.get("/training/context")
async def get_canvas_training_context(
    canvas_id: str = Query(..., description="Canvas the training panel is opened on"),
    agent_id: Optional[str] = Query(
        None, description="Optional agent hint (chat-expanded canvases carry ?agent_id=)"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Training context for a canvas — powers the training panel on /canvas/{id}.

    The canvas IS a training surface (the supervisor edits the hire's draft
    ON the canvas; the edit-diff is the learning signal), so the panel needs
    to know WHO is being trained here and which session this canvas belongs
    to. Read-only: every mutation flows through the existing session
    endpoints above — this only resolves identity and linkage.

    Resolution order:
    - agent: client hint -> CanvasAudit.agent_id (canvas provenance) ->
      training-canvas content.student.id -> linked session's agent.
    - session: an audit session_id that keys a TrainingSession row (the
      training_session_started stamp / role-canvas spawn) -> a session whose
      mini-canvas IS this canvas (supervisor_guidance.canvas_id) -> the
      agent's most recent ACTIVE session (draft canvases still train).
    """
    from core.models import AgentRegistry, Canvas, CanvasAudit

    # Role flag, not a gate: employees legitimately open this panel (teach +
    # progress only); the UI hides supervisor controls when False.
    viewer_is_supervisor = True
    try:
        _require_supervisor(db, current_user)
    except HTTPException:
        viewer_is_supervisor = False

    tenant_id = resolve_tenant_id(current_user)
    canvas = db.query(Canvas).filter(Canvas.id == canvas_id).first()
    # IDOR: a foreign-tenant canvas must 404 with no existence leak (same
    # guard as get_training_session_canvases).
    if not canvas or (canvas.tenant_id or "default") != tenant_id:
        raise HTTPException(status_code=404, detail=f"Canvas {canvas_id} not found")

    content = canvas.content if isinstance(canvas.content, dict) else {}
    audit_rows = (
        db.query(CanvasAudit)
        .filter(CanvasAudit.canvas_id == canvas_id)
        .order_by(CanvasAudit.created_at.desc())
        .all()
    )

    # Linkage 1: audit rows on THIS canvas that reference a training session
    # (the mini-canvas stamp or a role-canvas spawn wrote them).
    linked: Optional[TrainingSession] = None
    seen_session_ids = set()
    for row in audit_rows:
        if row.session_id and row.session_id not in seen_session_ids:
            seen_session_ids.add(row.session_id)
            candidate = (
                db.query(TrainingSession)
                .filter(TrainingSession.id == row.session_id)
                .first()
            )
            if candidate:
                linked = candidate
                break

    # Linkage 2: the session whose mini-canvas IS this canvas.
    if linked is None:
        candidates = (
            db.query(TrainingSession)
            .filter(TrainingSession.tenant_id == (canvas.tenant_id or "default"))
            .order_by(TrainingSession.started_at.desc())
            .limit(50)
            .all()
        )
        for candidate in candidates:
            guidance = (
                candidate.supervisor_guidance
                if isinstance(candidate.supervisor_guidance, dict)
                else {}
            )
            if guidance.get("canvas_id") == canvas_id:
                linked = candidate
                break

    # Agent identity — canvas provenance (audit rows) after the client hint;
    # the training-canvas content and the linked session carry it too.
    agent: Optional[AgentRegistry] = None
    candidate_agent_ids = [agent_id] + [row.agent_id for row in audit_rows if row.agent_id]
    if content.get("type") == "training_session":
        student = content.get("student") if isinstance(content.get("student"), dict) else {}
        if student.get("id"):
            candidate_agent_ids.append(student["id"])
    if linked is not None:
        candidate_agent_ids.append(linked.agent_id)
    for candidate_id in candidate_agent_ids:
        if not candidate_id:
            continue
        row = db.query(AgentRegistry).filter(AgentRegistry.id == candidate_id).first()
        if row is not None and (row.tenant_id or "default") == tenant_id:
            agent = row
            break

    # Draft/role canvases carry no session stamp, and a canvas linked to a
    # COMPLETED round may coexist with a newer active one — the panel shows
    # the session currently being trained, falling back to the linked one.
    # The linked session is only valid for the RESOLVED agent: falling back
    # to another agent's session (hint/audit resolved hire A, linkage found
    # hire B's session) would let the supervisor edit and complete B's
    # session under A's name — shown data must match the shown agent.
    session = linked
    if session is not None and agent is not None and session.agent_id != agent.id:
        session = None
    if session is None or (session.status or "").lower() not in _ACTIVE_SESSION_STATUSES:
        active = None
        if agent is not None:
            active = (
                db.query(TrainingSession)
                .filter(
                    TrainingSession.agent_id == agent.id,
                    TrainingSession.status.in_(_ACTIVE_SESSION_STATUSES),
                )
                .order_by(TrainingSession.started_at.desc())
                .first()
            )
        session = active or (
            linked
            if linked is not None and (agent is None or linked.agent_id == agent.id)
            else None
        )

    pending_proposal = None
    if agent is not None:
        pending_proposal = (
            db.query(AgentProposal)
            .filter(
                AgentProposal.agent_id == agent.id,
                AgentProposal.proposal_type == ProposalType.WORKFLOW.value,
                AgentProposal.status == ProposalStatus.PENDING_APPROVAL.value,
            )
            .order_by(AgentProposal.created_at.desc())
            .first()
        )

    def _session_payload(s: TrainingSession) -> Dict[str, Any]:
        guidance = s.supervisor_guidance if isinstance(s.supervisor_guidance, dict) else {}
        return {
            "id": s.id,
            "agent_id": s.agent_id,
            "status": s.status,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            "lesson_plan": guidance.get("lesson_plan") or None,
            "supervisor_note": guidance.get("supervisor_note"),
            "canvas_id": guidance.get("canvas_id"),
            "promoted_to_intern": bool(s.promoted_to_intern),
            "performance_score": s.performance_score,
            "evidence": StudentTrainingService(db).get_session_evidence(s),
        }

    def _proposal_payload(p: AgentProposal) -> Dict[str, Any]:
        data: Dict[str, Any] = p.proposal_data if isinstance(p.proposal_data, dict) else {}
        return {
            "id": p.id,
            "agent_id": p.agent_id,
            "agent_name": p.agent_name,
            "title": p.title,
            "description": p.description,
            "status": str(p.status) if p.status else None,
            "capability_gaps": data.get("capability_gaps", []),
            "learning_objectives": data.get("learning_objectives", []),
            "estimated_duration_hours": data.get("estimated_duration_hours"),
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }

    def _teaching_points(a: AgentRegistry) -> List[Dict[str, Any]]:
        """The agent's learning journal — every teaching point it was given
        (mentor lessons + absorbed observations), newest first. This is the
        read side of POST /api/agents/{id}/teach, which previously had no
        surface: the Training tab could teach but never show what was taught.
        """
        config = a.configuration if isinstance(a.configuration, dict) else {}
        learning = config.get("learning") if isinstance(config.get("learning"), dict) else {}
        log = learning.get("log") if isinstance(learning, dict) else None
        if not isinstance(log, list):
            return []
        points: List[Dict[str, Any]] = []
        for entry in log:
            if not isinstance(entry, dict):
                continue
            source = str(entry.get("source") or "teacher")
            if source == "observation":
                points.append(
                    {
                        "source": "observation",
                        "topic": str(entry.get("observation_type") or "general"),
                        "text": str(entry.get("summary") or ""),
                        "learned_at": entry.get("learned_at"),
                    }
                )
            else:
                points.append(
                    {
                        "source": "teacher",
                        "topic": str(entry.get("topic") or "general"),
                        "text": str(entry.get("lesson") or ""),
                        "learned_at": entry.get("learned_at"),
                        "teacher_agent_id": entry.get("teacher_agent_id"),
                    }
                )
        points.sort(key=lambda p: p.get("learned_at") or "", reverse=True)
        return points[:50]

    return {
        "canvas_id": canvas_id,
        "agent": (
            {
                "id": agent.id,
                "name": agent.name,
                # Normalized lowercase: the stored status may be uppercase
                # (API clients write "STUDENT"); tier drives tier badges and
                # next-tier lookups on the panel and the header hire badge.
                "tier": (agent.status or "student").lower(),
                "confidence": agent.confidence_score,
                "domain": (agent.category or "").lower(),
            }
            if agent is not None
            else None
        ),
        "linked_session": _session_payload(session) if session is not None else None,
        "pending_proposal": _proposal_payload(pending_proposal) if pending_proposal else None,
        "viewer_is_supervisor": viewer_is_supervisor,
        "teaching_points": _teaching_points(agent) if agent is not None else [],
    }


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
