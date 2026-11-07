
import asyncio
import datetime
import json
from datetime import timezone
import logging
from typing import Any, Dict, List, Optional
import uuid
from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator
from fastapi import BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import update
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.agent_decision_write_service import (
    admit_agent_run as _admit_agent_run,
    delete_agent as _delete_agent_decision,
    promote_agent as _promote_agent_decision,
    replace_agent as _replace_agent_decision,
    stop_agent as _stop_agent_decision,
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
    AuditLog,
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

def _safe_decision_observation(
    result: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Project only established, public-safe outcome fields for error responses.

    Service envelopes may carry structured data for several operations. A 503
    must preserve the known stop observation without dumping raw job
    parameters, configuration, schedules, exception text or credentials.
    """
    data = result.get("data")
    if not isinstance(data, dict):
        return None
    safe: Dict[str, Any] = {}
    agent_id = data.get("agent_id")
    if isinstance(agent_id, str) and agent_id.strip():
        safe["agent_id"] = agent_id
    cancelled_tasks = data.get("cancelled_tasks")
    if type(cancelled_tasks) is int and cancelled_tasks >= 0:
        safe["cancelled_tasks"] = cancelled_tasks
    return safe or None


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
    if status_value == "state_unavailable":
        raise HTTPException(
            status_code=int(result.get("http_status") or 503),
            detail={
                "success": False,
                "error": {
                    "code": result.get("error_code")
                    or "AGENT_TASK_STATE_UNAVAILABLE",
                    "message": result.get("error")
                    or "The agent task state is unavailable.",
                },
                "verification": result.get("verification"),
                "operation_id": result.get("operation_id"),
                "target_id": result.get("target_id"),
            },
        )
    if status_value in ("committed_unverified", "effect_unknown"):
        code = (
            "AGENT_EFFECT_UNKNOWN"
            if status_value == "effect_unknown"
            else "AGENT_COMMITTED_UNVERIFIED")
        detail = {
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
        }
        observation = _safe_decision_observation(result)
        if observation is not None:
            detail["data"] = observation
        raise HTTPException(status_code=503, detail=detail)


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
        # A replay/continued read must expose the existing durable outcome
        # (including any peer-terminal state) and must not dispatch again.
        replay_job_id = data.get("job_id")
        if replay_job_id:
            durable = _job_outcome_projection(
                replay_job_id, db.get_bind())
            if durable is not None:
                data = dict(data)
                data.update({
                    "execution_id": durable.get("execution_id"),
                    "job_status": durable["job_status"],
                    "outcome": durable["outcome"],
                    "reason": durable["reason"],
                    "next_action": durable["next_action"],
                    "requires_reconciliation": durable[
                        "requires_reconciliation"],
                })
                if durable.get("wait_receipt") is not None:
                    data["wait_receipt"] = durable["wait_receipt"]
                if durable["job_status"] in _JOB_WAITING_STATUSES:
                    return JSONResponse(
                        status_code=202,
                        content=router.success_response(
                            data=data,
                            message=(
                                "Agent run is waiting for required "
                                "information"),
                        ),
                    )
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
            db.get_bind(), actor_id=current_user.id)
        if execution is None:
            # The durable claim refused a second dispatch (or the job is no
            # longer active). Never report a new execution as completed.
            raise HTTPException(
                status_code=409,
                detail={
                    "success": False,
                    "error": {
                        "code": "AGENT_RUN_NOT_DISPATCHED",
                        "message": (
                            "This run was already dispatched or is no longer "
                            "active; refresh the job state instead of "
                            "dispatching it again."),
                    },
                    "data": {
                        "agent_id": agent_id,
                        "job_id": job_id,
                    },
                },
            )
        job_outcome = _job_outcome_projection(job_id, db.get_bind())
        if job_outcome is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "success": False,
                    "error": {
                        "code": "AGENT_EXECUTION_UNCERTAIN",
                        "message": (
                            "The execution finished but its durable job "
                            "state could not be read back. Reconcile the "
                            "original operation; do not retry blindly."),
                    },
                    "data": {
                        "agent_id": agent_id,
                        "job_id": job_id,
                    },
                },
            )
        execution_data = {
            "agent_id": agent_id,
            "job_id": job_id,
            "execution_id": job_outcome.get("execution_id"),
            "job_status": job_outcome["job_status"],
            "outcome": job_outcome["outcome"],
            "reason": job_outcome["reason"],
            "next_action": job_outcome["next_action"],
            "requires_reconciliation": job_outcome[
                "requires_reconciliation"],
            "verification": data.get("verification"),
        }
        if job_outcome["job_status"] in _JOB_WAITING_STATUSES:
            # A durable wait is neither success nor failure. The same task
            # retains its question/receipt and resumes through the existing
            # continuation owner when authorized input arrives.
            execution_data["wait_receipt"] = job_outcome.get(
                "wait_receipt")
            return JSONResponse(
                status_code=202,
                content=router.success_response(
                    data=execution_data,
                    message=(
                        "Agent execution is waiting for required "
                        "information"),
                ),
            )
        if job_outcome["job_status"] == AgentJobStatus.SUCCESS.value:
            execution_data["result"] = _public_execution_result(execution)
            return router.success_response(
                data=execution_data,
                message="Agent execution completed",
            )
        detail = {
            "success": False,
            "error": {
                "code": (
                    "AGENT_EXECUTION_UNCERTAIN"
                    if job_outcome["requires_reconciliation"]
                    else "AGENT_EXECUTION_NOT_SUCCESSFUL"),
                "message": _public_outcome_message(job_outcome),
            },
            "data": execution_data,
        }
        return _execution_error_response(
            status_code=(
                503 if job_outcome["requires_reconciliation"] else 409),
            code=detail["error"]["code"],
            message=detail["error"]["message"],
            data=execution_data,
        )
    background_tasks.add_task(
        _dispatch_admitted_run, agent_id, run_req.parameters, job_id,
        prior_status, db.get_bind(), actor_id=current_user.id)
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

async def execute_agent_task(
    agent_id: str,
    params: Dict[str, Any],
    execution_context: Optional[Dict[str, Any]] = None,
):
    """Background task to run the agent logic.

    ``execution_context`` is the server-owned admission namespace. When it
    carries a durable ``job_id`` the wrapper is an admitted run: the actual
    workspace/tenant/actor/job/execution identity comes from the admission
    record and the ``AgentRegistry`` row, never from the request body. The
    business parameters remain available under their own keys.
    """
    trusted = dict(execution_context or {})
    admitted = bool(trusted.get("job_id"))
    # Use context manager for background task
    with get_db_session() as db:
        result = None
        agent = None
        try:
            agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
            if not agent:
                logger.error(f"Agent {agent_id} not found in background task")
                return

            logger.info(f"Starting agent {agent.name} (ID: {agent_id})...")

            namespace = _execution_namespace(agent, trusted)
            scoped_params = _scoped_agent_context(params, trusted, agent)
            workspace_id = namespace["workspace_id"]

            # 1. World Model Retrieval — scope to the agent's own workspace
            # (AgentRegistry carries workspace_id; the bare constructor
            # silently read the "default" workspace's memory).
            wm_service = WorldModelService(workspace_id)

            # Build a context string from params to query memory
            task_context = f"Execute {agent.name} with params: {str(scoped_params)}"
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

                runner = GenericAgent(
                    agent,
                    workspace_id=workspace_id,
                    managed_overrides=managed_overrides,
                )
                # GenericAgent persists the execution row with
                # getattr(self, "tenant_id") or "default". Carry the real
                # tenant instead of silently landing the run in "default".
                if namespace.get("tenant_id"):
                    runner.tenant_id = namespace["tenant_id"]

                # 3. Determine Input
                # ReAct loop needs a natural language instruction.
                task_input = scoped_params.get("task_input") or scoped_params.get("request")

                # If input is missing but we have params, we construct a prompt
                if not task_input:
                    if agent.id == "competitive_intel":
                        task_input = f"Track pricing for {scoped_params.get('product', 'configured products')} against {scoped_params.get('competitors', 'competitors')}."
                    elif agent.id == "inventory_reconcile":
                        task_input = f"Reconcile inventory for {scoped_params.get('skus', 'all SKUs')}."
                    elif agent.id == "payroll_guardian":
                        task_input = f"Reconcile payroll for period {scoped_params.get('period', 'current')}."
                    else:
                         task_input = f"Execute task with params: {scoped_params}"

                # 4. Execute ReAct Loop with step streaming
                logger.info(f"Executing Agent {agent.name} with ReAct Loop. Input: {task_input}")

                async def streaming_callback(step_record):
                    await _broadcast_agent_step(
                        agent_id, step_record, namespace)

                result_obj = await runner.execute(task_input, context=scoped_params, step_callback=streaming_callback)

                # 5. Process Result
                result = result_obj
                outcome = _execution_outcome(
                    result,
                    bind=db.get_bind(),
                    agent_id=agent_id,
                    namespace=namespace,
                    actor_id=trusted.get("actor_id"),
                )

                # --- [NEW] External Bridge Response Routing ---
                source_platform = scoped_params.get("source_platform")
                recipient_id = (
                    scoped_params.get("recipient_id")
                    or scoped_params.get("channel_id"))

                if source_platform and recipient_id:
                    try:
                        from core.agent_integration_gateway import (
                            ActionType,
                            agent_integration_gateway,
                        )
                        if outcome["job_status"] == AgentJobStatus.SUCCESS.value:
                            final_output = (
                                result.get("final_output")
                                or result.get("output")
                                if isinstance(result, dict)
                                else str(result))
                            content = (
                                f"✅ *{agent.name}* finished task:\n{final_output}"
                                if final_output else None)
                        else:
                            content = (
                                f"⚠️ *{agent.name}* did not complete the task. "
                                f"{_public_outcome_message(outcome)}")

                        if content:
                            logger.info(f"Routing async agent result back to {source_platform}")
                            routing_params = {
                                "recipient_id": recipient_id,
                                "channel": scoped_params.get("channel_id") or recipient_id,
                                "content": content,
                                "thread_ts": scoped_params.get("thread_ts")
                            }

                            # Phase 105: Include original sender for Agent-to-Agent loopback
                            if source_platform == "agent":
                                routing_params["sender_agent_id"] = scoped_params.get("agent_id") or scoped_params.get("sender_id")

                            await agent_integration_gateway.execute_action(
                                ActionType.SEND_MESSAGE,
                                source_platform,
                                routing_params
                            )
                    except Exception as route_err:
                        logger.error(f"Failed to route async agent result back to {source_platform}: {route_err}")

                # 6. Record Experience happens inside GenericAgent.execute() now.

                # Direct (non-admitted) callers have no dispatch wrapper to
                # emit the terminal event. Admitted runs leave the conditional
                # terminal job write + event to _dispatch_admitted_run so a
                # peer cancellation can never be followed by a stale success.
                if not admitted:
                    await _broadcast_agent_outcome(
                        agent_id, outcome, namespace, result)

            except Exception as e:
                logger.error(f"Agent {agent_id} logic failed: {e}")

                # Record Failure
                await wm_service.record_experience(AgentExperience(
                    id=str(uuid.uuid4()),
                    agent_id=agent.id,
                    task_type=agent.class_name,
                    input_summary=str(scoped_params),
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

            # Urgent Notification (Phase 34 requirement) — safe code only;
            # exception text stays in server logs.
            await notification_manager.send_urgent_notification(
                message="An agent execution failed. Review the agent run before retrying.",
                workspace_id=(
                    locals().get("namespace", {}).get("workspace_id")
                    or "default"),
                channel="slack"
            )

            if not admitted:
                await _broadcast_agent_outcome(
                    agent_id,
                    _execution_outcome({"status": "failed"}),
                    _execution_namespace(agent, trusted),
                )

        return result


_JOB_ACTIVE_STATUSES = (
    AgentJobStatus.PENDING.value,
    AgentJobStatus.RUNNING.value,
)

_RESULT_SUCCESS_STATUSES = frozenset(
    {"success", "objective_satisfied", "completed"})
_RESULT_CANCELLED_STATUSES = frozenset(
    {"cancelled", "canceled", "stopped"})
_RESULT_WAIT_STATUSES = frozenset({
    "waiting", "awaiting_information", "awaiting_input",
    "awaiting_approval", "paused", "pending",
})
_JOB_WAITING_STATUSES = frozenset({
    "waiting", "awaiting_information", "awaiting_input",
    "awaiting_approval",
})
_RESULT_RECONCILIATION_STATUSES = frozenset({"uncertain"})

# Namespace keys the admission owns. Business parameters keep every other
# key, but these can never be supplied (or overridden) by the request body.
_TRUSTED_CONTEXT_KEYS = (
    "workspace_id",
    "tenant_id",
    "user_id",
    "actor_id",
    "job_id",
    "execution_id",
    "run_id",
    "operation_id",
    "operation_slot",
    "intent_id",
    "authorization_id",
    # Execution relationship/provenance fields are also server-owned: a body
    # cannot attach this run to another chat session/proposal/goal or claim a
    # different trigger origin.
    "session_id",
    "proposal_id",
    "goal_id",
    "trigger",
)


def _safe_outcome_token(value: Any, default: str = "unknown") -> str:
    """Bound an outcome/status token to a safe public code."""
    token = str(value or "").strip().lower().replace(" ", "_")
    if not token or len(token) > 64:
        return default
    if not all(ch.isalnum() or ch in "_-" for ch in token):
        return default
    return token


def _verified_hitl_wait(
    result: Any,
    *,
    bind,
    agent_id: str,
    namespace: Dict[str, Any],
    actor_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Resolve a returned wait reference to an existing pending review row.

    A returned label/dict is not proof. Only an existing ``HITLAction`` in
    pending/pending_2fa state, bound to this agent and the frozen
    workspace/tenant (and to the actor when the row names one), is a durable
    wait. Invented/foreign/settled references resolve to ``None``.
    """
    if bind is None:
        return None
    candidates = []
    nested = result.get("wait_receipt")
    if isinstance(nested, dict):
        for key in ("hitl_action_id", "action_id", "id"):
            value = nested.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                candidates.append(str(value).strip())
    for key in (
        "hitl_action_id", "approval_action_id", "pending_action_id",
    ):
        value = result.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            candidates.append(str(value).strip())
    if not candidates:
        return None

    workspace = str(namespace.get("workspace_id") or "default")
    tenant = namespace.get("tenant_id")
    seen = set()
    for action_id in candidates:
        if action_id in seen:
            continue
        seen.add(action_id)
        row = _safe_get(bind, HITLAction, action_id)
        if row is None:
            continue
        if str(getattr(row, "status", "") or "") not in {
            HITLActionStatus.PENDING.value,
            HITLActionStatus.PENDING_2FA.value,
        }:
            continue
        if str(getattr(row, "agent_id", "") or "") != str(agent_id):
            continue
        row_workspace = getattr(row, "workspace_id", None)
        if row_workspace is None or str(row_workspace) != workspace:
            continue
        row_tenant = getattr(row, "tenant_id", None)
        if (None if row_tenant is None else str(row_tenant)) != tenant:
            continue
        row_user = getattr(row, "user_id", None)
        if actor_id is not None:
            if row_user is None or str(row_user) != str(actor_id):
                continue
        # A new admitted task needs the complete server-owned task/execution
        # binding; absence is unknown, not proof of ownership. Legacy rows
        # stay readable/listable but cannot certify this task's wait.
        material = {}
        for field in ("context_snapshot", "params"):
            value = getattr(row, field, None)
            if isinstance(value, dict):
                material.update(value)
        material_job = material.get("job_id")
        material_execution = (
            material.get("execution_id") or material.get("run_id"))
        expected_job = namespace.get("job_id")
        expected_execution = namespace.get("execution_id")
        if not material_job or not material_execution:
            continue
        if not expected_job or not expected_execution:
            continue
        if str(material_job) != str(expected_job):
            continue
        if str(material_execution) != str(expected_execution):
            continue
        return {
            "hitl_action_id": str(row.id),
            "kind": "hitl_review",
            "status": str(row.status),
            "action_type": _safe_outcome_token(
                getattr(row, "action_type", ""), default="review"),
            "required_role": _safe_outcome_token(
                getattr(row, "required_role", ""), default=""),
            "verified": True,
        }
    return None


def _execution_outcome(
    result: Any,
    *,
    bind=None,
    agent_id: Optional[str] = None,
    namespace: Optional[Dict[str, Any]] = None,
    actor_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Map an execution result to a truthful durable job outcome.

    Result-object presence is not business success. Only an explicit
    supported success status completes the job; uncertain, failed, blocked,
    cancelled, waiting, empty, invalid and contradictory outcomes are
    preserved as a failed aggregate with their exact reason and next action.
    """

    def failed(outcome, reason, next_action, *, requires=False):
        return {
            "job_status": AgentJobStatus.FAILED.value,
            "outcome": outcome,
            "reason": reason,
            "next_action": next_action,
            "requires_reconciliation": bool(requires),
        }

    if not isinstance(result, dict):
        return failed(
            "invalid_result", "execution_result_missing", "review_execution")

    raw = _safe_outcome_token(result.get("status"), default="")
    requires_reconciliation = bool(result.get("requires_reconciliation"))
    contradictory = bool(
        raw in _RESULT_SUCCESS_STATUSES
        and (
            result.get("success") is False
            or _safe_outcome_token(
                result.get("action_result"), default="") in {
                    "failed", "not_applied", "rejected"}))
    if requires_reconciliation or raw in _RESULT_RECONCILIATION_STATUSES:
        return failed(
            raw or "uncertain", "execution_uncertain",
            "reconcile_operation", requires=True)
    if contradictory:
        return failed(
            "contradictory", "execution_contradictory",
            "reconcile_operation", requires=True)
    if raw in _RESULT_SUCCESS_STATUSES:
        return {
            "job_status": AgentJobStatus.SUCCESS.value,
            "outcome": raw,
            "reason": "execution_succeeded",
            "next_action": "none",
            "requires_reconciliation": False,
        }
    if not raw:
        return failed(
            "unknown", "execution_result_missing", "review_execution")
    if raw in _RESULT_WAIT_STATUSES:
        receipt = _verified_hitl_wait(
            result,
            bind=bind,
            agent_id=str(agent_id or ""),
            namespace=dict(namespace or {}),
            actor_id=actor_id,
        )
        if receipt:
            waiting_for = result.get("waiting_for")
            if isinstance(waiting_for, str) and waiting_for.strip():
                receipt["waiting_for"] = waiting_for.strip()[:400]
            return {
                "job_status": "waiting",
                "outcome": raw,
                "reason": "execution_waiting",
                "next_action": "await_information",
                "requires_reconciliation": False,
                "wait_receipt": receipt,
            }
        # A bare model/body waiting string has no verified durable owner. Do
        # not invent a wait or trust an invented/foreign/settled reference.
        return failed(
            raw, "execution_waiting_unbacked", "review_execution")
    if raw in _RESULT_CANCELLED_STATUSES:
        return failed(raw, "execution_cancelled", "none")
    if raw == "blocked":
        return failed(raw, "execution_blocked", "resolve_blocker")
    if raw in {
        "failed", "timeout", "stuck", "max_steps_exceeded",
        "budget_exceeded", "error",
    }:
        return failed(raw, "execution_failed", "review_failure")
    return failed(raw, "execution_not_successful", "review_failure")


def _public_outcome_message(outcome: Dict[str, Any]) -> str:
    """Safe, original-action-preserving public explanation."""
    reason = str(outcome.get("reason") or "")
    if reason == "execution_uncertain":
        return (
            "The agent run outcome is uncertain. Reconcile the original "
            "operation before retrying; do not repeat it blindly.")
    if reason == "execution_contradictory":
        return (
            "The agent run returned contradictory success information. "
            "Reconcile the original operation before retrying.")
    if reason == "execution_cancelled":
        return "The agent run was cancelled. No retry was started."
    if reason == "execution_waiting":
        return (
            "The agent run is waiting for required information; the same "
            "task continues when the authorized input arrives.")
    if reason == "execution_waiting_unbacked":
        return (
            "The agent reported waiting without a durable wait record. "
            "Review the execution before retrying.")
    if reason == "execution_blocked":
        return (
            "The agent run is blocked by a missing prerequisite. Resolve "
            "it before retrying.")
    if reason == "execution_result_missing":
        return (
            "The agent run did not report a usable outcome. Review the "
            "execution before retrying.")
    return "The agent run failed. Review the execution before retrying."


def _execution_namespace(
    agent: Optional[AgentRegistry],
    trusted: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Resolve the server-owned namespace for a run.

    The admitted namespace wins; the agent row is the fallback for direct
    callers. Request-body values are never consulted here.
    """
    trusted = dict(trusted or {})
    agent_workspace = (
        None if agent is None else getattr(agent, "workspace_id", None))
    agent_tenant = (
        None if agent is None else getattr(agent, "tenant_id", None))
    workspace = trusted.get("workspace_id") or agent_workspace or "default"
    tenant = trusted.get("tenant_id")
    if tenant is None:
        tenant = agent_tenant
    namespace = dict(trusted)
    namespace["workspace_id"] = str(workspace)
    namespace["tenant_id"] = None if tenant is None else str(tenant)
    return namespace


def _scoped_agent_context(
    params: Optional[Dict[str, Any]],
    trusted: Optional[Dict[str, Any]],
    agent: Optional[AgentRegistry],
) -> Dict[str, Any]:
    """Business params plus the frozen server namespace.

    Without an admission context the legacy direct-call behavior is kept.
    With one, every namespace key is overwritten (including with ``None``),
    so a forged body value cannot become execution/authority scope.
    """
    context = dict(params or {})
    if not trusted:
        return context
    namespace = _execution_namespace(agent, trusted)
    for key in _TRUSTED_CONTEXT_KEYS:
        context[key] = namespace.get(key)
    return context


def _ws_channels(namespace: Dict[str, Any]) -> List[str]:
    """Channels for a run event.

    The real workspace channel carries the scoped event. The admitted
    actor's existing authenticated ``user:{id}`` channel is included so the
    ordinary UI still receives its own updates without spraying private
    output onto the shared ``workspace:default`` channel. Only an actually
    default/unscoped principal stays on the default workspace channel.
    """
    workspace = str(namespace.get("workspace_id") or "default")
    channels = [f"workspace:{workspace}"]
    actor = str(
        namespace.get("actor_id") or namespace.get("user_id") or "")
    if actor:
        channels.append(f"user:{actor}")
    return channels


def _safe_ws_payload(namespace: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for key in (
        "job_id", "execution_id", "workspace_id", "tenant_id",
    ):
        value = namespace.get(key)
        if value:
            payload[key] = str(value)
    return payload


async def _broadcast_agent_step(
    agent_id: str,
    step_record: Any,
    namespace: Dict[str, Any],
) -> None:
    payload = {
        "type": "agent_step_update",
        "agent_id": agent_id,
        "step": step_record,
    }
    payload.update(_safe_ws_payload(namespace))
    for channel in _ws_channels(namespace):
        try:
            await ws_manager.broadcast(channel, payload)
        except Exception as exc:  # noqa: BLE001 — UI delivery must not kill a run
            logger.warning(
                "Agent step broadcast failed: agent=%s channel=%s "
                "error_class=%s", agent_id, channel, type(exc).__name__)


async def _broadcast_agent_outcome(
    agent_id: str,
    outcome: Dict[str, Any],
    namespace: Dict[str, Any],
    result: Any = None,
) -> None:
    """Emit the truthful terminal event for a run (no raw internals)."""
    payload = {
        "type": "agent_status_change",
        "agent_id": agent_id,
        "status": outcome["job_status"],
        "job_status": outcome["job_status"],
        "outcome": outcome["outcome"],
        "reason": outcome["reason"],
        "next_action": outcome["next_action"],
        "requires_reconciliation": bool(
            outcome.get("requires_reconciliation")),
    }
    payload.update(_safe_ws_payload(namespace))
    if outcome["job_status"] == AgentJobStatus.SUCCESS.value:
        output = None
        if isinstance(result, dict):
            output = result.get("output")
            if output is None:
                output = result.get("final_output")
        if output is not None:
            payload["result"] = {
                "status": "success",
                "output": str(output)[:20000],
            }
    elif outcome["job_status"] in _JOB_WAITING_STATUSES:
        if outcome.get("wait_receipt"):
            payload["wait_receipt"] = outcome["wait_receipt"]
        payload["message"] = _public_outcome_message(outcome)
    else:
        payload["error"] = _public_outcome_message(outcome)

    for channel in _ws_channels(namespace):
        try:
            await ws_manager.broadcast(channel, payload)
        except Exception as exc:  # noqa: BLE001 — UI delivery must not kill a run
            logger.warning(
                "Agent outcome broadcast failed: agent=%s channel=%s "
                "error_class=%s", agent_id, channel, type(exc).__name__)


def _execution_error_response(
    status_code: int,
    *,
    code: str,
    message: str,
    data: Dict[str, Any],
) -> JSONResponse:
    """Truthful non-success execution envelope (top-level data preserved)."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {"code": code, "message": message},
            "data": data,
        },
    )


def _public_execution_result(result: Any) -> Any:
    """Whitelist the sync run result for public output.

    Internal scores, audit reports and raw uncertainty payloads stay on the
    server; the user-facing output, trace steps and reconciliation flag are
    preserved.
    """
    if not isinstance(result, dict):
        return result
    public: Dict[str, Any] = {}
    for key in (
        "output", "final_output", "status", "requires_reconciliation",
        "timestamp",
    ):
        if key in result:
            public[key] = result[key]
    if isinstance(result.get("steps"), list):
        public["steps"] = result["steps"]
    return public


def _safe_get(bind, model, primary_key):
    """Read one row without letting a missing/unreadable table kill dispatch."""
    session = Session(bind=bind)
    try:
        return session.get(model, primary_key)
    except Exception:  # noqa: BLE001 — lookup failure is handled by callers
        return None
    finally:
        session.close()


def _admission_receipt_metadata(
    bind,
    *,
    job_id: str,
    agent_id: str,
    actor_id: Optional[str],
    operation_id: str,
) -> Optional[Dict[str, Any]]:
    """Authenticate the original admission receipt for this job.

    The current AgentRegistry/actor arg alone is not authority for another
    admitted run: the durable audit receipt must name the same operation,
    agent, job and (when supplied) admission actor.
    """
    if not operation_id:
        # Legacy/probe jobs predate the receipt payload; the route always
        # supplies one. Admission authority is still enforced upstream.
        return {}
    receipt = _safe_get(bind, AuditLog, operation_id)
    if receipt is None or getattr(receipt, "success", None) is not True:
        return None
    try:
        metadata = json.loads(getattr(receipt, "metadata_json", "") or "{}")
    except (TypeError, ValueError):
        return None
    if not isinstance(metadata, dict):
        return None
    if str(metadata.get("action") or "") != "agent_run_admitted":
        return None
    if str(metadata.get("target_id") or "") != str(agent_id):
        return None
    extra = metadata.get("extra") or {}
    if not isinstance(extra, dict):
        return None
    if str(extra.get("job_id") or "") != str(job_id):
        return None
    receipt_actor = str(metadata.get("actor_id") or "")
    if str(getattr(receipt, "user_id", "") or "") != receipt_actor:
        return None
    if actor_id is not None and receipt_actor != str(actor_id):
        return None
    return metadata


def _admitted_parameters_match(
    bind,
    *,
    job_id: str,
    parameters: Dict[str, Any],
) -> bool:
    """The dispatch material must match the admitted parameters digest.

    The active job row alone is not authority for newly changed body
    parameters; compare against the digest frozen at admission.
    """
    job = _safe_get(bind, AgentJob, job_id)
    if job is None:
        return False
    try:
        payload = json.loads(job.result_summary or "{}")
    except (TypeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    expected = str(payload.get("parameters_digest") or "")
    if not expected:
        return True
    from core.agent_decision_write_service import (
        _canonical as _admission_canonical,
        _fingerprint as _admission_fingerprint,
    )

    actual = _admission_fingerprint(
        "agent-run-parameters", _admission_canonical(dict(parameters or {})))
    return actual == expected


def _trusted_execution_context(
    bind,
    *,
    agent_id: str,
    job_id: str,
    actor_id: Optional[str],
    execution_id: str,
) -> Optional[Dict[str, Any]]:
    """Build the frozen run namespace from durable server-owned rows."""
    job = _safe_get(bind, AgentJob, job_id)
    if job is None or str(job.agent_id or "") != str(agent_id):
        logger.debug(
            "trusted context refused: job missing/mismatch job=%s", job_id)
        return None
    agent = _safe_get(bind, AgentRegistry, agent_id)
    actor = _safe_get(bind, User, actor_id) if actor_id else None
    if actor_id and (
        actor is None
        or not bool(getattr(actor, "is_active", False))
        or str(getattr(actor, "status", "")) != "active"
    ):
        logger.debug(
            "trusted context refused: actor unavailable actor=%s", actor_id)
        return None

    operation_id = ""
    try:
        payload = json.loads(job.result_summary or "{}")
        if isinstance(payload, dict):
            operation_id = str(payload.get("operation_id") or "")
    except (TypeError, ValueError):
        operation_id = ""
    receipt = _admission_receipt_metadata(
        bind,
        job_id=job_id,
        agent_id=agent_id,
        actor_id=actor_id,
        operation_id=operation_id,
    )
    if receipt is None:
        logger.debug(
            "trusted context refused: admission receipt invalid job=%s "
            "operation=%s actor=%s", job_id, operation_id, actor_id)
        return None

    namespace = _execution_namespace(agent, {
        "job_id": job_id,
        "execution_id": execution_id,
        "run_id": execution_id,
        "actor_id": actor_id,
        "user_id": actor_id,
    })
    # Freeze the accepted admission scope; never let a moved agent or a
    # different current owner relabel this already-admitted run.
    resolved_workspace = None
    if receipt:
        receipt_workspace = receipt.get("target_workspace_id")
        if receipt_workspace is not None:
            resolved_workspace = str(receipt_workspace)
        receipt_tenant = (
            receipt.get("target_tenant_id")
            if receipt.get("target_tenant_id") is not None
            else receipt.get("tenant_id"))
        if receipt_tenant is not None:
            namespace["tenant_id"] = str(receipt_tenant)
        receipt_actor_tenant = (
            None if actor is None else getattr(actor, "tenant_id", None))
        if (
            receipt_actor_tenant is not None
            and receipt.get("tenant_id") is not None
            and str(receipt_actor_tenant) != str(receipt.get("tenant_id"))
        ):
            logger.debug(
                "trusted context refused: receipt actor tenant "
                "mismatch job=%s", job_id)
            return None
    if resolved_workspace is None and agent is not None:
        agent_workspace = getattr(agent, "workspace_id", None)
        if agent_workspace is not None:
            resolved_workspace = str(agent_workspace)
    if resolved_workspace is None and actor is not None:
        actor_workspace = getattr(actor, "workspace_id", None)
        if actor_workspace is not None:
            resolved_workspace = str(actor_workspace)
    namespace["workspace_id"] = resolved_workspace or "default"
    job_tenant = getattr(job, "tenant_id", None)
    if job_tenant is not None:
        if actor is not None and getattr(actor, "tenant_id", None) is not None:
            if str(actor.tenant_id) != str(job_tenant):
                logger.debug(
                    "trusted context refused: job actor tenant mismatch "
                    "job=%s", job_id)
                return None
        if namespace.get("tenant_id") is None:
            namespace["tenant_id"] = str(job_tenant)
    if namespace.get("tenant_id") is None and actor is not None:
        actor_tenant = getattr(actor, "tenant_id", None)
        namespace["tenant_id"] = (
            None if actor_tenant is None else str(actor_tenant))

    namespace["operation_id"] = operation_id or None
    namespace["trigger"] = "agent_run_route"
    return namespace


def _job_outcome_projection(job_id: str, bind) -> Optional[Dict[str, Any]]:
    """Read the durable job's truthful outcome in a fresh session."""
    session = Session(bind=bind)
    try:
        job = session.get(AgentJob, job_id)
        if job is None:
            return None
        status = str(job.status or "")
        try:
            payload = json.loads(job.result_summary or "{}")
        except (TypeError, ValueError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        if status in _JOB_WAITING_STATUSES:
            wait_receipt = payload.get("wait_receipt")
            if not (
                isinstance(wait_receipt, dict)
                and wait_receipt.get("verified") is True
            ):
                projection = _execution_outcome({"status": status})
                projection["job_status"] = AgentJobStatus.FAILED.value
                projection["reason"] = "execution_waiting_unbacked"
                projection["next_action"] = "review_execution"
                projection["requires_reconciliation"] = False
                execution_id = (
                    payload.get("execution_id")
                    or payload.get("dispatch_execution_id"))
                projection["execution_id"] = (
                    None if not execution_id else str(execution_id))
                return projection
            projection = {
                "job_status": status,
                "outcome": _safe_outcome_token(
                    payload.get("outcome"), default="waiting"),
                "reason": "execution_waiting",
                "next_action": "await_information",
                "requires_reconciliation": False,
                "wait_receipt": wait_receipt,
            }
            execution_id = (
                payload.get("execution_id")
                or payload.get("dispatch_execution_id"))
            projection["execution_id"] = (
                None if not execution_id else str(execution_id))
            return projection
        if status in _JOB_ACTIVE_STATUSES:
            # A continued/cold read must preserve the live state, not invent
            # a failed outcome for work that is still in flight.
            projection = {
                "job_status": status,
                "outcome": "in_progress",
                "reason": "execution_in_progress",
                "next_action": "await_completion",
                "requires_reconciliation": False,
            }
            execution_id = (
                payload.get("execution_id")
                or payload.get("dispatch_execution_id"))
            projection["execution_id"] = (
                None if not execution_id else str(execution_id))
            return projection
        projection = _execution_outcome({"status": status})
        projection["job_status"] = status or projection["job_status"]
        outcome = _safe_outcome_token(payload.get("outcome"), default="")
        if outcome:
            projection["outcome"] = outcome
        reason = _safe_outcome_token(payload.get("reason"), default="")
        if reason:
            projection["reason"] = reason
        next_action = _safe_outcome_token(
            payload.get("next_action"), default="")
        if next_action:
            projection["next_action"] = next_action
        if "requires_reconciliation" in payload:
            projection["requires_reconciliation"] = bool(
                payload.get("requires_reconciliation"))
        # Contradictory durable state: never let a status/detail mismatch
        # turn into a success claim. The exact mismatch is preserved.
        if (
            projection["job_status"] == AgentJobStatus.SUCCESS.value
            and outcome and outcome not in _RESULT_SUCCESS_STATUSES
        ):
            projection["job_status"] = AgentJobStatus.FAILED.value
            projection["reason"] = "execution_contradictory"
            projection["next_action"] = "reconcile_operation"
            projection["requires_reconciliation"] = True
        elif (
            projection["job_status"] != AgentJobStatus.SUCCESS.value
            and outcome in _RESULT_SUCCESS_STATUSES
            and not (
                projection["requires_reconciliation"]
                and reason in {
                    "execution_uncertain",
                    "execution_contradictory",
                }
            )
        ):
            projection["outcome"] = "contradictory"
            projection["reason"] = "execution_contradictory"
            projection["next_action"] = "reconcile_operation"
            projection["requires_reconciliation"] = True
        execution_id = (
            payload.get("execution_id")
            or payload.get("dispatch_execution_id"))
        projection["execution_id"] = (
            None if not execution_id else str(execution_id))
        return projection
    finally:
        session.close()


def _begin_job(
    job_id: str,
    bind,
    *,
    agent_id: str,
    execution_id: str,
) -> bool:
    """CAS the admitted job into its run slot.

    Returns ``True`` only for the dispatch that won the conditional write.
    A replay, a peer-terminal job, or a racing dispatcher returns ``False``
    and must not execute the agent a second time.
    """
    session = Session(bind=bind)
    try:
        job = session.get(AgentJob, job_id)
        if job is None or str(job.agent_id or "") != str(agent_id):
            return False
        if str(job.status or "") not in _JOB_ACTIVE_STATUSES:
            return False
        try:
            payload = json.loads(job.result_summary or "{}")
        except (TypeError, ValueError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        claimed_execution = str(
            payload.get("dispatch_execution_id") or "")
        if claimed_execution and claimed_execution != execution_id:
            return False
        current_summary = job.result_summary
        payload["dispatch_execution_id"] = execution_id
        payload["dispatch_started"] = True
        new_summary = json.dumps(payload, sort_keys=True)
        conditions = [
            AgentJob.id == job_id,
            AgentJob.agent_id == agent_id,
            AgentJob.status.in_(_JOB_ACTIVE_STATUSES),
        ]
        if current_summary is None:
            conditions.append(AgentJob.result_summary.is_(None))
        else:
            conditions.append(AgentJob.result_summary == current_summary)
        claimed = session.execute(
            update(AgentJob)
            .where(*conditions)
            .values(
                status=AgentJobStatus.RUNNING.value,
                result_summary=new_summary,
            ))
        session.commit()
        return claimed.rowcount == 1
    finally:
        session.close()


def _finish_job(
    job_id: str,
    outcome: Dict[str, Any],
    bind,
    *,
    execution_id: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> Optional[str]:
    """Conditionally finish an active job and return the durable status.

    The write is bound to the active expected status, the admitted agent and
    the exact dispatch execution id. A peer cancellation, a stale dispatcher
    or a changed material snapshot can never be overwritten by a late
    success.
    """
    session = Session(bind=bind)
    try:
        job = session.get(AgentJob, job_id)
        if job is None:
            return None
        if agent_id is not None and str(job.agent_id or "") != str(agent_id):
            return str(job.status or "") or None
        try:
            payload = json.loads(job.result_summary or "{}")
        except (TypeError, ValueError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        if execution_id:
            claimed_execution = str(
                payload.get("dispatch_execution_id") or "")
            if claimed_execution != str(execution_id):
                # Another dispatcher owns this run slot (or the claim was
                # replaced). Do not certify its work as this execution.
                return str(job.status or "") or None
        waiting = outcome["job_status"] in _JOB_WAITING_STATUSES
        payload["finished"] = not waiting
        payload["waiting"] = waiting
        payload["status"] = outcome["job_status"]
        payload["outcome"] = outcome["outcome"]
        payload["reason"] = outcome["reason"]
        payload["next_action"] = outcome["next_action"]
        payload["requires_reconciliation"] = bool(
            outcome.get("requires_reconciliation"))
        if outcome.get("wait_receipt"):
            payload["wait_receipt"] = outcome["wait_receipt"]
        if execution_id:
            payload["execution_id"] = execution_id
        new_summary = json.dumps(payload, sort_keys=True)
        conditions = [
            AgentJob.id == job_id,
            AgentJob.status.in_(_JOB_ACTIVE_STATUSES),
        ]
        if agent_id is not None:
            conditions.append(AgentJob.agent_id == agent_id)
        if job.result_summary is None:
            conditions.append(AgentJob.result_summary.is_(None))
        else:
            conditions.append(
                AgentJob.result_summary == job.result_summary)
        values: Dict[str, Any] = {
            "status": outcome["job_status"],
            "result_summary": new_summary,
        }
        if not waiting:
            values["end_time"] = datetime.datetime.now(timezone.utc)
        finished = session.execute(
            update(AgentJob)
            .where(*conditions)
            .values(**values))
        session.commit()
        if finished.rowcount == 1:
            return outcome["job_status"]
        current = session.get(AgentJob, job_id)
        return None if current is None else str(current.status or "")
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
    prior_status: Optional[str], bind, *, actor_id: Optional[str] = None,
):
    """Run an admitted job and keep its durable status truthful.

    The execution itself is the existing ``execute_agent_task``. Admission,
    the job row and the receipt already committed before this function runs.
    A second dispatcher is refused by the conditional run-slot claim.
    """
    execution_id = str(uuid.uuid4())
    if not _begin_job(
        job_id, bind, agent_id=agent_id, execution_id=execution_id,
    ):
        logger.warning(
            "Admitted agent run not dispatched (already claimed or "
            "terminal): agent=%s job=%s", agent_id, job_id)
        return None

    if not _admitted_parameters_match(
        bind, job_id=job_id, parameters=parameters,
    ):
        logger.warning(
            "Admitted agent run not dispatched (admitted parameters "
            "changed): agent=%s job=%s", agent_id, job_id)
        outcome = _execution_outcome({
            "status": "failed",
            "requires_reconciliation": True,
        })
        outcome["reason"] = "admission_material_changed"
        outcome["next_action"] = "refresh_required_state"
        _finish_job(
            job_id, outcome, bind,
            execution_id=execution_id, agent_id=agent_id)
        await _broadcast_agent_outcome(
            agent_id, outcome,
            _execution_namespace(
                _safe_get(bind, AgentRegistry, agent_id),
                {"job_id": job_id, "execution_id": execution_id,
                 "actor_id": actor_id, "user_id": actor_id}))
        _restore_agent_status(agent_id, prior_status, bind)
        return None

    trusted = _trusted_execution_context(
        bind,
        agent_id=agent_id,
        job_id=job_id,
        actor_id=actor_id,
        execution_id=execution_id,
    )
    if trusted is None:
        logger.warning(
            "Admitted agent run not dispatched (admission receipt or "
            "authority unavailable): agent=%s job=%s", agent_id, job_id)
        outcome = _execution_outcome({
            "status": "failed",
            "requires_reconciliation": True,
        })
        outcome["reason"] = "execution_authority_unavailable"
        outcome["next_action"] = "refresh_required_state"
        _finish_job(
            job_id, outcome, bind,
            execution_id=execution_id, agent_id=agent_id)
        await _broadcast_agent_outcome(
            agent_id, outcome,
            _execution_namespace(
                _safe_get(bind, AgentRegistry, agent_id),
                {"job_id": job_id, "execution_id": execution_id}))
        _restore_agent_status(agent_id, prior_status, bind)
        return None

    try:
        result = await execute_agent_task(
            agent_id, parameters, execution_context=trusted)
        outcome = _execution_outcome(
            result,
            bind=bind,
            agent_id=agent_id,
            namespace=trusted,
            actor_id=actor_id,
        )
        durable_status = _finish_job(
            job_id, outcome, bind,
            execution_id=execution_id, agent_id=agent_id)
        effective = outcome
        if durable_status is None:
            effective = _execution_outcome({
                "status": "failed",
                "requires_reconciliation": True,
            })
            effective["reason"] = "execution_durable_state_unavailable"
            effective["next_action"] = "refresh_required_state"
        elif durable_status != outcome["job_status"]:
            # A peer made the job terminal first. Report that truth, never
            # the late result the losing writer wanted to record.
            effective = _execution_outcome({"status": durable_status})
        await _broadcast_agent_outcome(
            agent_id, effective,
            _execution_namespace(None, trusted), result)
        return result
    except Exception as exc:  # noqa: BLE001 — job status records the failure
        outcome = _execution_outcome({"status": "failed"})
        outcome["reason"] = "execution_error"
        durable_status = _finish_job(
            job_id, outcome, bind,
            execution_id=execution_id, agent_id=agent_id)
        effective = outcome
        if durable_status is None:
            effective = _execution_outcome({
                "status": "failed",
                "requires_reconciliation": True,
            })
            effective["reason"] = "execution_durable_state_unavailable"
            effective["next_action"] = "refresh_required_state"
        elif durable_status != outcome["job_status"]:
            effective = _execution_outcome({"status": durable_status})
        await _broadcast_agent_outcome(
            agent_id, effective,
            _execution_namespace(None, trusted))
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
    operation_id: Optional[str] = None,
    user: User = Depends(require_permission(Permission.AGENT_MANAGE)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Replace an entire agent resource (RESTful PUT semantics).

    The verified decision binds current authority/scope and exact prior agent
    material, writes one AuditLog receipt, replays idempotently and refuses
    stale or foreign material. The scheduler is updated only after a verified
    commit and only once.
    """
    changes = {
        "name": req.name,
        "description": req.description,
        "category": req.category,
    }
    if req.configuration is not None:
        changes["configuration"] = req.configuration
    if req.schedule_config is not None:
        changes["schedule_config"] = req.schedule_config
    result = _replace_agent_decision(
        db,
        actor=current_user,
        agent_id=agent_id,
        changes=changes,
        operation_id=operation_id,
    )
    _raise_agent_decision(result)
    data = dict(result.get("data") or {})
    data.setdefault("agent_id", agent_id)
    if result.get("status") == "verified" and data.get("schedule_active"):
        try:
            from core.scheduler import AgentScheduler
            scheduler = AgentScheduler.get_instance()
            scheduler.schedule_agent(agent_id, req.schedule_config)
        except Exception as exc:  # noqa: BLE001 — DB replacement committed
            logger.error(
                "Agent replacement committed but scheduler update failed: "
                "agent=%s error_class=%s", agent_id, type(exc).__name__)
    return router.success_response(
        data=data,
        message=f"Agent {req.name} replaced successfully",
    )




@router.post("/{agent_id}/stop")
async def stop_agent(
    agent_id: str,
    operation_id: Optional[str] = None,
    user: User = Depends(require_permission(Permission.AGENT_RUN)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel an agent's active tasks in the caller's scope.

    The verified decision binds current authority, exact agent material and a
    durable AuditLog receipt. A replay does not cancel newly started tasks.
    """
    result = await _stop_agent_decision(
        db,
        actor=current_user,
        agent_id=agent_id,
        operation_id=operation_id,
    )
    _raise_agent_decision(result)
    data = result.get("data") or {}
    data.setdefault("agent_id", agent_id)
    return router.success_response(
        data=data,
        message=result.get("message") or "Agent stopped",
    )
