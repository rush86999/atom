
import asyncio
import datetime
import json
from datetime import timezone
import logging
from typing import Any, Dict, List, Optional
import uuid
from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator
from fastapi import BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import update
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.agent_decision_write_service import (
    admit_agent_run as _admit_agent_run,
    delete_agent as _delete_agent_decision,
    promote_agent as _promote_agent_decision,
    update_agent as _update_agent_decision,
)
from core.auth import get_current_user, User
from core.agent_world_model import AgentExperience, WorldModelService
from core.base_routes import BaseAPIRouter
from core.database import SessionLocal, get_db, get_db_session
from core.enterprise_security import AuditEvent, EventType, SecurityLevel, enterprise_security
from core.models import (
    AgentFeedback,
    AgentJob,
    AgentJobStatus,
    AgentRegistry,
    AgentStatus,
    HITLAction,
    HITLActionStatus,
    NEW_AGENT_CONFIDENCE,
    User,
)
from core.notification_manager import notification_manager
from core.rbac_service import Permission
from core.security_dependencies import require_permission
from core.websockets import manager as ws_manager

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/agents", tags=["Agents"])

# --- Data Models ---
class AgentRunRequest(BaseModel):
    agent_id: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)

class AgentUpdateRequest(BaseModel):
    agent_id: Optional[str] = None
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Agent name")
    description: Optional[str] = None
    # P2: per-agent zero-trust tool scoping. Empty/['*'] = unrestricted (default).
    capabilities: Optional[List[str]] = None
    # USER-TUNABLE PROMOTION FLOOR (2026-09-23): minimum episodes before the
    # next promotion is considered. Null = use the per-level default.
    promotion_episode_floor: Optional[int] = Field(None, ge=1, description="Minimum episodes before next promotion (null = per-level default)")

    @field_validator('name')
    @classmethod
    def validate_name_not_whitespace(cls, v: Optional[str]) -> Optional[str]:
        """Reject whitespace-only names (mirrors the line-841 AgentUpdateRequest)."""
        if v is not None:
            if not v or not v.strip():
                raise ValueError('cannot be empty or whitespace-only')
            return v.strip()
        return v

class AgentInfo(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: str # idle, running, failed, success
    last_run: Optional[str] = None
    category: Optional[str] = None

# --- Registry (Mock for MVP, real app would scan or register classes) ---
class AgentFeedbackRequest(BaseModel):
    user_correction: str
    input_context: Optional[str] = None
    original_output: str

class HITLApprovalRequest(BaseModel):
    decision: str # approved | rejected
    feedback: Optional[str] = None
    # Supervisor MODIFIES the action before approving: the agent resumes with
    # these params instead of its original ones (e.g. rewrite the draft
    # email, retarget the recipient). Applied only on approve.
    modified_params: Optional[Dict[str, Any]] = None

# --- Endpoints ---

def _raise_agent_decision(result: Dict[str, Any]) -> None:
    """Map the verified agent-decision envelope to a safe HTTP error."""
    status_value = str(result.get("status") or "")
    if status_value == "refused":
        raise HTTPException(
            status_code=int(result.get("http_status") or 403),
            detail={
                "success": False,
                "error": {
                    "code": result.get("error_code") or "AUTHORITY_REQUIRED",
                    "message": result.get("error") or "Request refused",
                },
                "field": result.get("field"),
                "verification": result.get("verification"),
            },
        )
    if status_value == "conflict":
        raise HTTPException(
            status_code=409,
            detail={
                "success": False,
                "error": {
                    "code": result.get("error_code") or "STALE_TARGET",
                    "message": result.get("error") or "Conflict",
                },
                "verification": result.get("verification"),
            },
        )
    if status_value == "not_applied":
        raise HTTPException(
            status_code=int(result.get("http_status") or 409),
            detail={
                "success": False,
                "error": {
                    "code": result.get("error_code")
                    or "AGENT_TRANSACTION_ROLLED_BACK",
                    "message": result.get("error")
                    or "The agent decision did not apply.",
                },
                "verification": result.get("verification"),
                "operation_id": result.get("operation_id"),
                "audit_id": result.get("audit_id"),
            },
        )
    if status_value in ("committed_unverified", "effect_unknown"):
        code = (
            "AGENT_EFFECT_UNKNOWN"
            if status_value == "effect_unknown"
            else "AGENT_COMMITTED_UNVERIFIED")
        raise HTTPException(
            status_code=503,
            detail={
                "success": False,
                "error": {
                    "code": code,
                    "message": result.get("message")
                    or "The agent decision outcome is uncertain.",
                },
                "verification": result.get("verification"),
                "operation_id": result.get("operation_id"),
                "audit_id": result.get("audit_id"),
                "target_id": result.get("target_id"),
            },
        )


@router.get("/history")
async def get_agent_execution_history(
    limit: int = Query(50, ge=1, le=100, description="Max results (capped at 100)"),
    user: User = Depends(require_permission(Permission.AGENT_VIEW)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get recent agent execution history (for the Agents page history panel)."""
    from core.models import AgentExecution, ExecutionStatus
    try:
        executions = db.query(AgentExecution).order_by(
            AgentExecution.started_at.desc()
        ).limit(limit).all()
        return [
            {
                "id": str(e.id),
                "agent_id": e.agent_id,
                "status": e.status,
                "started_at": e.started_at.isoformat() if e.started_at else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                "duration_seconds": e.duration_seconds,
                "result_summary": (e.result_summary or "")[:200],
                "error_message": (e.error_message or "")[:200],
                "triggered_by": e.triggered_by,
            }
            for e in executions
        ]
    except Exception as e:
        logger.error(f"Failed to fetch agent history: {e}")
        return []


@router.get("/")
async def list_agents(
    category: Optional[str] = None,
    user: User = Depends(require_permission(Permission.AGENT_VIEW)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all available Computer Use Agents from Registry"""
    # W45 (Agent Control Center crash): the endpoint previously had NO error
    # handling — any DB hiccup (schema drift, missing table, permission-layer
    # failure) surfaced as a raw 500 with an empty body, which the frontend
    # rendered as the useless "Failed to load agents: Internal Server Error".
    # Catch, log the real cause server-side, and return a structured error so
    # the page can show what actually went wrong.
    try:
        governance_service = AgentGovernanceService(db)
        agents_db = governance_service.list_agents(category)

        # Get last run times
        from sqlalchemy import func
        latest_jobs = db.query(AgentJob.agent_id, func.max(AgentJob.start_time).label('last_run'))\
            .group_by(AgentJob.agent_id)\
            .all()
        last_run_map = {job.agent_id: job.last_run.isoformat() for job in latest_jobs if job.last_run}

        agents_list = [
            AgentInfo(
                id=a.id,
                name=a.name,
                description=a.description,
                status=a.status,
                last_run=last_run_map.get(a.id),
                category=a.category
            ) for a in agents_db
        ]

        return router.success_response(
            data=agents_list,
            message=f"Retrieved {len(agents_list)} agents"
        )
    except Exception as e:
        logger.error(f"Failed to list agents: {e}", exc_info=True)
        raise router.error_response(
            error_code="AGENT_LIST_FAILED",
            message=f"Failed to load agents: {e}",
            status_code=500,
        ) from e

# --- Endpoints ---


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    user: User = Depends(require_permission(Permission.AGENT_VIEW)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific agent by ID"""
    agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
    if not agent:
        raise router.not_found_error("Agent", agent_id)

    # Get last run time
    from sqlalchemy import func
    latest_job = db.query(func.max(AgentJob.start_time))\
        .filter(AgentJob.agent_id == agent_id)\
        .scalar()

    return router.success_response(
        data={
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "category": agent.category,
            "status": agent.status,
            "confidence_score": agent.confidence_score,
            "module_path": agent.module_path,
            "class_name": agent.class_name,
            "configuration": _safe_configuration_view(agent),
            "schedule_config": agent.schedule_config,
            "version": agent.version,
            "last_run": latest_job.isoformat() if latest_job else None
        },
        message="Agent retrieved successfully"
    )


def _safe_configuration_view(agent: AgentRegistry) -> dict:
    """
    Buyer-safe configuration view. Marketplace-managed agents store only a
    reference (template_id/version/capabilities/tunables) — never publisher
    prompts or memory.
    """
    config = agent.configuration or {}
    if config.get("marketplace_managed"):
        return {
            "marketplace_managed": True,
            "template_id": config.get("template_id"),
            "managed_version": config.get("managed_version"),
            "capabilities": config.get("capabilities", []),
            "tunables": config.get("tunables", {}),
        }
    return config


@router.get("/{agent_id}/status")
async def get_agent_status(
    agent_id: str,
    user: User = Depends(require_permission(Permission.AGENT_VIEW)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the current status of an agent"""
    agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
    if not agent:
        raise router.not_found_error("Agent", agent_id)

    # Check for running tasks (BUG-050: get_active_tasks never existed; the
    # real sync method is get_agent_tasks. The old call raised AttributeError
    # which was silently swallowed, defeating the running-task guard.)
    from core.agent_task_registry import agent_task_registry
    try:
        running_tasks = agent_task_registry.get_agent_tasks(agent_id)
    except Exception:
        running_tasks = []

    return router.success_response(
        data={
            "agent_id": agent.id,
            "name": agent.name,
            "status": agent.status,
            "confidence_score": agent.confidence_score,
            "is_running": len(running_tasks) > 0,
            "active_tasks": len(running_tasks)
        },
        message="Agent status retrieved successfully"
    )


# P3.1 — graduation progress surface. Drives the tier badge + progress bar on
# AgentCard and the dashboard. Returns the agent's current tier, raw episode
# count, intervention count, and the next-tier threshold so the UI can render
# "8/10 episodes to INTERN" without re-implementing the criteria.
@router.get("/{agent_id}/graduation-progress")
async def get_agent_graduation_progress(
    agent_id: str,
    user: User = Depends(require_permission(Permission.AGENT_VIEW)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get tier + episode progress for an agent."""
    agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
    if not agent:
        raise router.not_found_error("Agent", agent_id)

    # Pull the canonical thresholds. Importing locally keeps the route file
    # import-cost low and avoids potential circular-import pitfalls.
    try:
        from core.agent_graduation_service import AgentGraduationService
        criteria = AgentGraduationService.CRITERIA
    except Exception:
        criteria = {}

    # Order of tiers from lowest to highest. The criteria dict only contains
    # INTERN/SUPERVISED/AUTONOMOUS (STUDENT has no minimum because it's the
    # starting tier); we synthesize the STUDENT entry.
    tier_order = ["student", "intern", "supervised", "autonomous"]
    current_tier = (agent.status or "student").lower()
    if current_tier not in tier_order:
        current_tier = "student"
    current_idx = tier_order.index(current_tier)

    next_tier = tier_order[current_idx + 1] if current_idx < len(tier_order) - 1 else None
    next_tier_upper = next_tier.upper() if next_tier else None
    episodes_to_next = None
    next_threshold = None
    # Real episode count (R82): count successful episodes so the UI progress
    # bar reflects actual progress, not the bare threshold. The old
    # placeholder claimed "X episodes to next tier" regardless of progress —
    # the AgentCard badge and dashboard bar both render this live.
    episode_count = 0
    try:
        from core.models import AgentEpisode
        raw_count = (
            db.query(AgentEpisode)
            .filter(
                AgentEpisode.agent_id == agent_id,
                AgentEpisode.outcome == "success",
            )
            .count()
        )
        if isinstance(raw_count, int) and raw_count >= 0:
            episode_count = raw_count
    except Exception:
        episode_count = 0

    if next_tier_upper and next_tier_upper in criteria:
        next_threshold = criteria[next_tier_upper].get("min_episodes")
        if isinstance(next_threshold, int):
            episodes_to_next = max(0, next_threshold - episode_count)

    return router.success_response(
        data={
            "agent_id": agent.id,
            "current_tier": current_tier,
            "next_tier": next_tier,
            "next_threshold_episodes": next_threshold,
            "episodes_to_next": episodes_to_next,
            "episode_count": episode_count,
            "criteria": criteria,
        },
        message="Graduation progress retrieved successfully"
    )


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    operation_id: Optional[str] = None,
    user: User = Depends(require_permission(Permission.AGENT_MANAGE)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an agent and every dependent row in the caller's scope.

    The verified decision binds current authority and exact prior material,
    performs the existing dynamic dependent-row cleanup and demo tombstone in
    one transaction, and writes one AuditLog receipt. A foreign tenant or
    workspace target resolves as not found; stale material refuses without
    deleting anything.
    """
    result = _delete_agent_decision(
        db,
        actor=current_user,
        agent_id=agent_id,
        operation_id=operation_id,
    )
    _raise_agent_decision(result)
    data = result.get("data") or {}
    if result.get("status") in ("verified", "already_applied"):
        message = (
            f"Agent {data.get('agent_name') or agent_id} "
            "deleted successfully")
    else:
        message = result.get("message") or "Agent deleted successfully"
    return router.success_response(data=data, message=message)




@router.post("/{agent_id}/run")
async def run_agent(
    agent_id: str,
    run_req: AgentRunRequest,
    background_tasks: BackgroundTasks,
    operation_id: Optional[str] = None,
    user: User = Depends(require_permission(Permission.AGENT_RUN)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Admit and dispatch one agent execution in the caller's scope.

    The verified admission binds current authority, exact agent material and a
    durable AgentJob/receipt before dispatch. The existing execution task is
    dispatched only after that transaction commits; tests stub the execution.
    """
    result = _admit_agent_run(
        db,
        actor=current_user,
        agent_id=agent_id,
        parameters=run_req.parameters,
        operation_id=operation_id,
    )
    _raise_agent_decision(result)
    data = result.get("data") or {}
    if result.get("status") == "already_applied":
        return router.success_response(
            data=data, message="Agent run already admitted")
    job_id = data.get("job_id")
    if not job_id:
        raise HTTPException(
            status_code=503,
            detail={
                "success": False,
                "error": {
                    "code": "AGENT_RUN_JOB_MISSING",
                    "message": "The run was admitted without a job identity.",
                },
                "verification": data.get("verification"),
            },
        )
    prior_status = data.get("prior_status")
    if run_req.parameters.get("sync", False):
        execution = await _dispatch_admitted_run(
            agent_id, run_req.parameters, job_id, prior_status,
            db.get_bind())
        return router.success_response(
            data={
                "agent_id": agent_id,
                "job_id": job_id,
                "result": execution,
                "verification": data.get("verification"),
            },
            message="Agent execution completed",
        )
    background_tasks.add_task(
        _dispatch_admitted_run, agent_id, run_req.parameters, job_id,
        prior_status, db.get_bind())
    return router.success_response(
        data={
            "agent_id": agent_id,
            "job_id": job_id,
            "verification": data.get("verification"),
        },
        message="Agent execution started",
    )




@router.patch("/{agent_id}")
async def update_agent(
    agent_id: str,
    update_data: AgentUpdateRequest,
    operation_id: Optional[str] = None,
    user: User = Depends(require_permission(Permission.AGENT_MANAGE)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update agent details in the caller's tenant/workspace scope."""
    result = _update_agent_decision(
        db,
        actor=current_user,
        agent_id=agent_id,
        changes=update_data.model_dump(exclude_none=True),
        operation_id=operation_id,
    )
    _raise_agent_decision(result)
    return router.success_response(
        data=result.get("data"),
        message=(
            result.get("message")
            if result.get("status") == "no_change"
            else "Agent updated successfully"),
    )

@router.post("/{agent_id}/feedback")
async def submit_agent_feedback(
    agent_id: str,
    feedback: AgentFeedbackRequest,
    user: User = Depends(require_permission(Permission.AGENT_RUN)), # Members can submit feedback
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit feedback/corrections for an agent"""
    service = AgentGovernanceService(db)
    result = await service.submit_feedback(
        agent_id=agent_id,
        user_id=user.id,
        original_output=feedback.original_output,
        user_correction=feedback.user_correction,
        input_context=feedback.input_context
    )
    return router.success_response(
        data={
            "feedback_id": result.id,
            "adjudication": result.status,
            "reasoning": result.ai_reasoning
        },
        message="Feedback submitted successfully"
    )

@router.post("/{agent_id}/promote")
async def promote_agent(
    agent_id: str,
    operation_id: Optional[str] = None,
    user: User = Depends(require_permission(Permission.AGENT_MANAGE)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Promote agent to Autonomous mode in the caller's tenant/workspace scope.

    Manual promotion bypasses the graduation framework — use for agents
    that have demonstrated readiness outside the episodic memory system.
    """
    result = _promote_agent_decision(
        db,
        actor=current_user,
        agent_id=agent_id,
        operation_id=operation_id,
    )
    _raise_agent_decision(result)
    data = result.get("data") or {}
    return router.success_response(
        data=data,
        message=(
            result.get("message")
            if result.get("status") == "no_change"
            else f"Agent {agent_id} promoted to autonomous successfully"),
    )

@router.get("/approvals/pending", response_model=List[Dict[str, Any]])
async def list_pending_approvals(
    limit: int = 100,
    user: User = Depends(require_permission(Permission.AGENT_MANAGE)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List actions waiting for human approval.

    SECURITY: capped at 1000 rows to prevent DoS via pending-action
    flooding. Caller can paginate with limit + offset if needed.
    """
    # Clamp limit server-side regardless of caller input
    if limit < 1 or limit > 1000:
        limit = 100
    actions_query = db.query(HITLAction).filter(
        HITLAction.status == HITLActionStatus.PENDING.value)
    if current_user.workspace_id:
        actions_query = actions_query.filter(
            HITLAction.workspace_id == current_user.workspace_id)
    if current_user.tenant_id:
        actions_query = actions_query.filter(
            HITLAction.tenant_id == current_user.tenant_id)
    actions = actions_query.order_by(
        HITLAction.created_at.desc()).limit(limit).all()
    return [{
        "id": a.id,
        "agent_id": a.agent_id,
        "action_type": a.action_type,
        "params": a.params,
        "reason": a.reason,
        "created_at": a.created_at.isoformat() if a.created_at else None
    } for a in actions]

@router.post("/approvals/{action_id}")
async def decide_hitl_action(
    action_id: str,
    req: HITLApprovalRequest,
    user: User = Depends(require_permission(Permission.AGENT_MANAGE)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Approve or Reject a paused agent action.

    SECURITY: uses SELECT ... FOR UPDATE to prevent race condition
    where two concurrent approvals both succeed (double-spend).
    SQLite ignores with_for_update() so this is a no-op there;
    PostgreSQL acquires a row lock for the duration of the transaction.
    """
    # SELECT FOR UPDATE — concurrent approvals block until this commits
    action_query = db.query(HITLAction).filter(HITLAction.id == action_id)
    if current_user.workspace_id:
        action_query = action_query.filter(
            HITLAction.workspace_id == current_user.workspace_id)
    if current_user.tenant_id:
        action_query = action_query.filter(
            HITLAction.tenant_id == current_user.tenant_id)
    action = action_query.with_for_update().first()
    if not action:
        raise router.not_found_error("HITLAction", action_id)
    from api.approvals_routes import _validate_assignment_approval_payload

    _validate_assignment_approval_payload(action, req.modified_params)

    # Idempotent: already-resolved actions return current state, don't double-apply
    already_resolved = action.status in (
        HITLActionStatus.APPROVED.value,
        HITLActionStatus.REJECTED.value,
    )
    if already_resolved:
        return router.success_response(
            data={"decision": action.status, "action_id": action_id, "already_resolved": True},
            message=f"Action {action_id} already resolved as {action.status}"
        )

    # Validate the exact reviewed goal decision BEFORE this route mutates the
    # HITL row. A stale approval must not mark a newer decision's row (or its
    # own row) approved without executing the reviewed material.
    from core.hitl_resume import preflight_hitl_decision

    preflight = preflight_hitl_decision(
        action_id, req.modified_params, action=action, db=db)
    if not preflight.get("valid", True):
        reason = preflight.get("reason") or "stale_decision_review"
        raise router.error_response(
            "DECISION_REVIEW_REQUIRED" if reason == "decision_review_required"
            else "STALE_DECISION_REVIEW",
            preflight.get("message") or (
                "Refresh the run and review the current pending decision "
                "before approving it."),
            details={
                "reason": reason,
                "current_decision_id": preflight.get("current_decision_id"),
            },
            status_code=409,
        )

    if req.decision.lower() == "approved":
        action.status = HITLActionStatus.APPROVED.value
        # Supervisor modification: the resumed action runs with these params
        # instead of the agent's originals (real-world training loop: edit,
        # approve, and the agent learns from the diff via user_feedback).
        if req.modified_params:
            try:
                merged = dict(action.params or {})
                merged.update(req.modified_params)
                action.params = merged
            except Exception as params_err:
                logger.warning(f"HITL modified_params merge failed, keeping originals: {params_err}")
    else:
        action.status = HITLActionStatus.REJECTED.value

    action.user_feedback = req.feedback
    action.reviewed_at = datetime.datetime.now()
    action.reviewed_by = user.id

    db.commit()

    # A decision is not the end of the journey: goal runs and workflows are
    # waiting on this row. Resume the durable work before answering the UI so
    # "approved" cannot mean "marked approved, still stuck".
    resume: Dict[str, Any] = {"handled": False}
    try:
        from core.hitl_resume import resume_after_hitl_decision

        resume = await resume_after_hitl_decision(
            action_id,
            approved=req.decision.lower() == "approved",
            reviewer_id=str(user.id),
            guidance=req.feedback,
        )
    except Exception as resume_err:  # noqa: BLE001 — decision already committed
        logger.exception("HITL %s decided but resume bridge failed: %s", action_id, resume_err)
        resume = {"handled": True, "resumed": False, "error": str(resume_err)}

    # Broadcast update to UI via WebSocket
    await ws_manager.broadcast("workspace:default", {
        "type": "hitl_decision",
        "action_id": action_id,
        "decision": action.status,
        "resume": resume,
    })
    
    return router.success_response(
        data={"decision": action.status, "action_id": action_id, "resume": resume},
        message=f"Action {action_id} {action.status} successfully"
    )

async def execute_agent_task(agent_id: str, params: Dict[str, Any]):
    """Background task to run the agent logic"""
    # Use context manager for background task
    with get_db_session() as db:
        result = None
        try:
            agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
            if not agent:
                logger.error(f"Agent {agent_id} not found in background task")
                return

            logger.info(f"Starting agent {agent.name} (ID: {agent_id})...")

            # 1. World Model Retrieval — scope to the agent's own workspace
            # (AgentRegistry carries workspace_id; the bare constructor
            # silently read the "default" workspace's memory).
            wm_service = WorldModelService(
                getattr(agent, "workspace_id", None) or "default"
            )

            # Build a context string from params to query memory
            task_context = f"Execute {agent.name} with params: {str(params)}"
            relevant_memories = await wm_service.recall_experiences(agent, task_context)

            if isinstance(relevant_memories, dict):
                 # Extract the actual experiences list from the dictionary response
                 experiences = relevant_memories.get("experiences", [])

                 if experiences:
                    logger.info(f"Agents {agent.name} found {len(experiences)} relevant past experiences.")
                    for mem in experiences:
                        # Defensive check if mem is object or dict (mock vs real)
                        if hasattr(mem, "input_summary"):
                             logger.info(f"  [Memory] {mem.input_summary} -> {mem.learnings} ({mem.outcome})")
                        else:
                             logger.info(f"  [Memory] {str(mem)}")
            elif isinstance(relevant_memories, list):
                 # Legacy/Fallback support if it returns a list directly
                 logger.info(f"Agents {agent.name} found {len(relevant_memories)} relevant past experiences.")
                 for mem in relevant_memories:
                     if hasattr(mem, "input_summary"):
                        logger.info(f"  [Memory] {mem.input_summary} -> {mem.learnings} ({mem.outcome})")
                     else:
                        logger.info(f"  [Memory] {str(mem)}")

            # Dynamic Import
            # Unified Execution Logic using GenericAgent ReAct Loop
            from core.generic_agent import GenericAgent

            result = None
            try:
                # 1. Determine Tools based on Agent ID/Type (Migration compatibility)
                # If the agent is legacy and doesn't have tools configured, we inject them here.
                override_config = {}
                if agent.id == "competitive_intel":
                     override_config["tools"] = ["track_competitor_pricing"]
                     override_config["system_prompt"] = "You are a Competitive Intelligence Agent. Use the 'track_competitor_pricing' tool to gather market data."
                elif agent.id == "inventory_reconcile":
                     override_config["tools"] = ["reconcile_inventory"]
                     override_config["system_prompt"] = "You are an Inventory Manager. Use 'reconcile_inventory' to check for variance."
                elif agent.id == "payroll_guardian":
                     override_config["tools"] = ["reconcile_payroll"]
                     override_config["system_prompt"] = "You are a Payroll Guardian. Use 'reconcile_payroll' to verify accuracy."

                # 2. Instantiate Runtime
                if override_config:
                    if not agent.configuration:
                        agent.configuration = {}
                    # Merge defaults if not present
                    for k, v in override_config.items():
                        if k not in agent.configuration:
                            agent.configuration[k] = v

                # Marketplace managed agents: resolve prompts/tools/guidance
                # from the template manifest (raises if a kill switch tripped).
                from core.marketplace_runtime import (
                    ManagedAgentBlockedError,
                    resolve_managed_agent,
                )

                try:
                    managed_overrides = resolve_managed_agent(db, agent)
                except ManagedAgentBlockedError as blocked:
                    return router.error_response(
                        message=f"This marketplace agent is unavailable: {blocked.reason}",
                        status_code=403,
                    )

                runner = GenericAgent(agent, managed_overrides=managed_overrides)

                # 3. Determine Input
                # ReAct loop needs a natural language instruction.
                task_input = params.get("task_input") or params.get("request")

                # If input is missing but we have params, we construct a prompt
                if not task_input:
                    if agent.id == "competitive_intel":
                        task_input = f"Track pricing for {params.get('product', 'configured products')} against {params.get('competitors', 'competitors')}."
                    elif agent.id == "inventory_reconcile":
                        task_input = f"Reconcile inventory for {params.get('skus', 'all SKUs')}."
                    elif agent.id == "payroll_guardian":
                        task_input = f"Reconcile payroll for period {params.get('period', 'current')}."
                    else:
                         task_input = f"Execute task with params: {params}"

                # 4. Execute ReAct Loop with step streaming
                logger.info(f"Executing Agent {agent.name} with ReAct Loop. Input: {task_input}")

                async def streaming_callback(step_record):
                    await ws_manager.broadcast("workspace:default", {
                        "type": "agent_step_update",
                        "agent_id": agent_id,
                        "step": step_record
                    })

                result_obj = await runner.execute(task_input, context=params, step_callback=streaming_callback)

                # 5. Process Result
                result = result_obj

                # Success Notification
                await ws_manager.broadcast("workspace:default", {
                    "type": "agent_status_change",
                    "agent_id": agent_id,
                    "status": "success",
                    "result": result
                })

                # --- [NEW] External Bridge Response Routing ---
                source_platform = params.get("source_platform")
                recipient_id = params.get("recipient_id") or params.get("channel_id")

                if source_platform and recipient_id:
                    try:
                        from core.agent_integration_gateway import (
                            ActionType,
                            agent_integration_gateway,
                        )
                        final_output = result.get("final_output") if isinstance(result, dict) else str(result)

                        if final_output:
                            logger.info(f"Routing async agent result back to {source_platform}")
                            routing_params = {
                                "recipient_id": recipient_id,
                                "channel": params.get("channel_id") or recipient_id,
                                "content": f"✅ *{agent.name}* finished task:\n{final_output}",
                                "thread_ts": params.get("thread_ts")
                            }

                            # Phase 105: Include original sender for Agent-to-Agent loopback
                            if source_platform == "agent":
                                routing_params["sender_agent_id"] = params.get("agent_id") or params.get("sender_id")

                            await agent_integration_gateway.execute_action(
                                ActionType.SEND_MESSAGE,
                                source_platform,
                                routing_params
                            )
                    except Exception as route_err:
                        logger.error(f"Failed to route async agent result back to {source_platform}: {route_err}")

                # 6. Record Experience happens inside GenericAgent.execute() now.


            except Exception as e:
                logger.error(f"Agent {agent_id} logic failed: {e}")

                # Record Failure
                await wm_service.record_experience(AgentExperience(
                    id=str(uuid.uuid4()),
                    agent_id=agent.id,
                    task_type=agent.class_name,
                    input_summary=str(params),
                    outcome="Failure",
                    learnings=f"Failed with error: {str(e)}",
                    agent_role=agent.category,
                    specialty=None,
                    timestamp=datetime.datetime.now(timezone.utc)
                ))
                raise e

        except Exception as e:
            import sys
            import traceback
            error_msg = f"Agent execution FAILED: {str(e)}\n{traceback.format_exc()}"
            logger.critical(f"!!! CRITICAL AGENT ERROR !!!\n{error_msg}")
            logger.error(f"Agent {agent_id} execution wrapper failed: {e}")

            # Urgent Notification (Phase 34 requirement)
            await notification_manager.send_urgent_notification(
                message=f"Agent execution FAILED: {str(e)}",
                workspace_id="default_workspace",
                channel="slack"
            )

            # Notify UI Status
            await ws_manager.broadcast("workspace:default", {
                "type": "agent_status_change",
                "agent_id": agent_id,
                "status": "failed",
                "error": str(e),
                "traceback": traceback.format_exc()
            })

        return result


def _begin_job(job_id: str, bind) -> None:
    session = Session(bind=bind)
    try:
        job = session.get(AgentJob, job_id)
        if job is not None:
            job.status = AgentJobStatus.RUNNING.value
            session.commit()
    finally:
        session.close()


def _finish_job(job_id: str, status: str, bind) -> None:
    session = Session(bind=bind)
    try:
        job = session.get(AgentJob, job_id)
        if job is None:
            return
        job.status = status
        job.end_time = datetime.datetime.now(timezone.utc)
        try:
            payload = json.loads(job.result_summary or "{}")
        except (TypeError, ValueError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload["finished"] = True
        payload["status"] = status
        job.result_summary = json.dumps(payload, sort_keys=True)
        session.commit()
    finally:
        session.close()


def _restore_agent_status(
    agent_id: str, prior_status: Optional[str], bind,
) -> None:
    if not prior_status:
        return
    session = Session(bind=bind)
    try:
        session.execute(
            update(AgentRegistry)
            .where(
                AgentRegistry.id == agent_id,
                AgentRegistry.status == "running",
            )
            .values(status=prior_status))
        session.commit()
    finally:
        session.close()


async def _dispatch_admitted_run(
    agent_id: str, parameters: Dict[str, Any], job_id: str,
    prior_status: Optional[str], bind,
):
    """Run an admitted job and keep its durable status truthful.

    The execution itself is the existing ``execute_agent_task``. Admission,
    the job row and the receipt already committed before this function runs.
    """
    _begin_job(job_id, bind)
    try:
        result = await execute_agent_task(agent_id, parameters)
        _finish_job(
            job_id,
            AgentJobStatus.SUCCESS.value if result is not None
            else AgentJobStatus.FAILED.value, bind)
        return result
    except Exception as exc:  # noqa: BLE001 — job status records the failure
        _finish_job(job_id, AgentJobStatus.FAILED.value, bind)
        logger.error(
            "Admitted agent run failed: agent=%s job=%s error_class=%s",
            agent_id, job_id, type(exc).__name__)
        raise
    finally:
        _restore_agent_status(agent_id, prior_status, bind)


# ==================== ATOM META-AGENT ENDPOINTS ====================

class AtomExecuteRequest(BaseModel):
    request: str
    context: Optional[Dict[str, Any]] = None

class AtomSpawnRequest(BaseModel):
    template: str  # e.g., "finance_analyst", "sales_assistant", "custom"
    custom_params: Optional[Dict[str, Any]] = None
    persist: bool = False

class AtomTriggerRequest(BaseModel):
    event_type: str
    data: Dict[str, Any]

@router.post("/atom/execute")
async def execute_atom(
    req: AtomExecuteRequest,
    user: User = Depends(require_permission(Permission.AGENT_RUN)),
):
    """
    Execute the Atom Meta-Agent with a natural language request.
    Atom will analyze the request and spawn specialty agents as needed.
    """
    from core.atom_meta_agent import handle_manual_trigger

    # Determine workspace from user context
    workspace_id = "default"

    result = await handle_manual_trigger(
        request=req.request,
        user=user,
        workspace_id=workspace_id
    )

    return router.success_response(
        data=result,
        message="Atom meta-agent executed successfully"
    )


@router.post("/spawn")
async def spawn_agent(
    req: AtomSpawnRequest,
    user: User = Depends(require_permission(Permission.AGENT_MANAGE)),
):
    """
    Spawn a specialty agent on-demand from a template.
    """
    from core.atom_meta_agent import get_atom_agent
    
    atom = get_atom_agent()
    agent = await atom.spawn_agent(
        template_name=req.template,
        custom_params=req.custom_params,
        persist=req.persist
    )
    
    return router.success_response(
        data={
            "agent_id": agent.id,
            "agent_name": agent.name,
            "category": agent.category,
            "persisted": req.persist
        },
        message=f"Agent {agent.name} spawned successfully"
    )


@router.post("/atom/trigger")
async def trigger_atom_with_data(
    req: AtomTriggerRequest,
    # This endpoint may not require user auth if called by webhooks/internal systems
    # For now, require basic auth
    user: User = Depends(require_permission(Permission.AGENT_RUN)),
):
    """
    Trigger Atom with new data (event-driven execution).
    Used for webhooks, ingestion events, integration callbacks.
    """
    from core.atom_meta_agent import handle_data_event_trigger
    
    result = await handle_data_event_trigger(
        event_type=req.event_type,
        data=req.data,
        workspace_id="default"
    )
    
    return router.success_response(
        data=result,
        message="Atom triggered with data event successfully"
    )

class CustomAgentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100, description="Agent name (1-100 characters)")
    description: Optional[str] = "Custom Agent"
    category: str = Field(min_length=1, max_length=50, description="Agent category (1-50 characters)")
    configuration: Optional[Dict[str, Any]] = None
    schedule_config: Optional[Dict[str, Any]] = None

    @field_validator('name', 'category')
    @classmethod
    def validate_not_whitespace(cls, v: str) -> str:
        """Validate that name and category are not empty or whitespace-only."""
        if not v or not v.strip():
            raise ValueError('cannot be empty or whitespace-only')
        return v.strip()


class AgentUpdateRequest(BaseModel):
    """Request model for partial agent updates (Bug #4 fix)."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Agent name")
    description: Optional[str] = None
    category: Optional[str] = Field(None, min_length=1, max_length=50, description="Agent category")
    configuration: Optional[Dict[str, Any]] = None
    schedule_config: Optional[Dict[str, Any]] = None
    # P2: per-agent zero-trust tool scoping. Empty/['*'] = unrestricted (default).
    capabilities: Optional[List[str]] = None

    @field_validator('name', 'category')
    @classmethod
    def validate_not_whitespace(cls, v: Optional[str]) -> Optional[str]:
        """Validate that name and category are not empty or whitespace-only."""
        if v is not None:
            if not v or not v.strip():
                raise ValueError('cannot be empty or whitespace-only')
            return v.strip()
        return v


class AgentReplaceRequest(BaseModel):
    """Request model for PUT /api/agents/{id} - full agent replacement.

    Per RFC 9110 Section 4.3.4 (PUT), this endpoint validates all required fields
    and performs a full replacement of the agent resource. For partial updates,
    use PATCH /api/agents/{id} instead.

    Required fields:
        name: Agent name (1-100 characters, not whitespace-only)
        category: Agent category (1-50 characters, not whitespace-only)

    Optional fields:
        description: Agent description
        configuration: Agent configuration dictionary
        schedule_config: Agent schedule configuration dictionary

    See: docs/testing/PUT_SEMANTICS_DECISION.md
    """
    name: str = Field(min_length=1, max_length=100, description="Agent name (required)")
    description: Optional[str] = None
    category: str = Field(min_length=1, max_length=50, description="Agent category (required)")
    configuration: Optional[Dict[str, Any]] = None
    schedule_config: Optional[Dict[str, Any]] = None

    @field_validator('name', 'category')
    @classmethod
    def validate_not_whitespace(cls, v: str) -> str:
        """Validate that name and category are not empty or whitespace-only."""
        if not v or not v.strip():
            raise ValueError('cannot be empty or whitespace-only')
        return v.strip()

@router.post("/custom", status_code=201)
async def create_custom_agent(
    req: CustomAgentRequest,
    user: User = Depends(require_permission(Permission.AGENT_MANAGE)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a fully custom agent with configuration and schedule.

    Returns 201 Created on success (HTTP standard for resource creation).
    """
    # 1. Create Agent. The employee's scope is the authenticated user's
    # effective scope, not NULL: assignment start resolves an agent by
    # workspace + tenant, so an unscoped hire was visible in the list but
    # could not be given work on a fresh install.
    workspace_id = getattr(current_user, "workspace_id", None) or "default"
    tenant_id = getattr(current_user, "tenant_id", None) or "default"
    registry_entry = AgentRegistry(
        name=req.name,
        description=req.description,
        category=req.category,
        configuration=req.configuration,
        schedule_config=req.schedule_config,
        module_path="core.generic_agent",
        class_name="GenericAgent",
        status=AgentStatus.STUDENT.value,
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        # Round 86: start hires below the INTERN band floor (0.5). The old
        # 0.5 default put every new employee one graded rehearsal away from
        # promotion — confidence should reflect demonstrated work, and the
        # evidence gate (student_training_service) now requires it anyway.
        confidence_score=NEW_AGENT_CONFIDENCE,
    )
    db.add(registry_entry)
    db.commit()
    db.refresh(registry_entry)
    
    # 2. Schedule if needed
    if req.schedule_config and req.schedule_config.get("active"):
        from core.scheduler import AgentScheduler
        scheduler = AgentScheduler.get_instance()
        scheduler.schedule_agent(registry_entry.id, req.schedule_config)
        
    return router.success_response(
        data={"agent_id": registry_entry.id},
        message=f"Custom agent {req.name} created successfully"
    )

@router.put("/{agent_id}")
async def replace_agent(
    agent_id: str,
    req: AgentReplaceRequest,
    user: User = Depends(require_permission(Permission.AGENT_MANAGE)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Replace an entire agent resource (RESTful PUT semantics per RFC 9110).

    This endpoint performs a full replacement of the agent resource. All required
    fields (name, category) must be provided. For partial updates, use PATCH instead.

    Returns 422 if required fields are missing.

    See: docs/testing/PUT_SEMANTICS_DECISION.md
    """
    agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
    if not agent:
        raise router.not_found_error("Agent", agent_id)

    # Full replacement: update all fields
    agent.name = req.name
    agent.description = req.description
    agent.category = req.category
    if req.configuration is not None:
        agent.configuration = req.configuration
    if req.schedule_config is not None:
        agent.schedule_config = req.schedule_config

    db.commit()

    # Update Scheduler if schedule_config changed
    if req.schedule_config and req.schedule_config.get("active"):
        from core.scheduler import AgentScheduler
        scheduler = AgentScheduler.get_instance()
        scheduler.schedule_agent(agent.id, req.schedule_config)

    return router.success_response(
        data={"agent_id": agent.id},
        message=f"Agent {agent.name} replaced successfully"
    )

@router.post("/{agent_id}/stop")
async def stop_agent(
    agent_id: str,
    user: User = Depends(require_permission(Permission.AGENT_RUN)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Stop a running agent by cancelling its active tasks.
    Uses the AgentTaskRegistry to cancel all running tasks for the agent.
    """
    from core.agent_task_registry import agent_task_registry

    logger.info(f"Stop request received for agent {agent_id} by user {user.id}")

    # Try to cancel tasks via registry
    cancelled_count = await agent_task_registry.cancel_agent_tasks(agent_id)

    if cancelled_count > 0:
        # Successfully cancelled tasks
        return router.success_response(
            data={
                "agent_id": agent_id,
                "cancelled_tasks": cancelled_count
            },
            message=f"Successfully stopped {cancelled_count} running task(s)"
        )
    else:
        # No tasks in registry - agent might not be running or already stopped
        # Check if agent exists
        agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if not agent:
            raise router.not_found_error("Agent", agent_id)

        return router.success_response(
            data={"agent_id": agent_id, "cancelled_tasks": 0},
            message="No running tasks found for this agent"
        )
