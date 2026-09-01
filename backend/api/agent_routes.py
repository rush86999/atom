
import asyncio
import datetime
from datetime import timezone
import logging
from typing import Any, Dict, List, Optional
import uuid
from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator
from fastapi import BackgroundTasks, Depends, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.auth import get_current_user, User
from core.agent_world_model import AgentExperience, WorldModelService
from core.base_routes import BaseAPIRouter
from core.database import SessionLocal, get_db, get_db_session
from core.enterprise_security import AuditEvent, EventType, SecurityLevel, enterprise_security
from core.models import (
    AgentFeedback,
    AgentJob,
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
    user: User = Depends(require_permission(Permission.AGENT_MANAGE)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an agent and every dependent row.

    FK enforcement is OFF on the SQLite connection, so a bare registry-row
    delete silently orphans episodes, audits, jobs and learning rows across
    the 25+ tables that carry an agent_id — those ghosts then resurface in
    journeys, governance metrics and listings. The cleanup discovers every
    table with an agent_id column dynamically (new tables are covered
    automatically) and removes the agent's rows in the same transaction.
    """
    # The main agent is load-bearing (mentor bootstrap, governance anchors)
    # — deleting it cripples the fleet rather than removing a test artifact.
    if agent_id == "atom_main":
        raise router.error_response(
            error_code="CANNOT_DELETE_MAIN_AGENT",
            message="The main agent (atom_main) cannot be deleted.",
            status_code=400,
        )

    agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
    if not agent:
        raise router.not_found_error("Agent", agent_id)

    # Check if agent has running tasks (BUG-050: was calling non-existent
    # get_active_tasks; now uses the real sync get_agent_tasks.)
    from core.agent_task_registry import agent_task_registry
    try:
        running_tasks = agent_task_registry.get_agent_tasks(agent_id)
    except Exception:
        running_tasks = []

    if running_tasks:
        raise router.error_response(
            error_code="AGENT_HAS_RUNNING_TASKS",
            message=f"Cannot delete agent with {len(running_tasks)} running task(s)",
            status_code=400
        )

    # Dependent cleanup: every table with an agent_id column. Raw SQL per
    # table — most of these tables have no ORM model, and the goal is
    # breadth (no orphan ghosts), not per-table semantics.
    from sqlalchemy import inspect as sa_inspect, text

    cleaned: dict[str, int] = {}
    try:
        inspector = sa_inspect(db.bind)
        for table in inspector.get_table_names():
            cols = {c["name"] for c in inspector.get_columns(table)}
            if "agent_id" not in cols or table == AgentRegistry.__tablename__:
                continue
            result = db.execute(
                text(f"DELETE FROM {table} WHERE agent_id = :aid"), {"aid": agent_id}
            )
            if result.rowcount:
                cleaned[table] = result.rowcount
    except Exception as e:
        db.rollback()
        raise router.error_response(
            error_code="AGENT_DELETE_CLEANUP_FAILED",
            message=f"Dependent-row cleanup failed, agent not deleted: {e}",
            status_code=500,
        )

    agent_name = agent.name
    # Honoring deletions: the onboarding demo agent is re-created by
    # ensure_demo_agent() at every bootstrap — a bare delete would make it
    # reappear on the next restart ("agents I delete keep coming back"). When
    # the deleted agent carries the demo_agent flag, write a tombstone in the
    # SAME transaction so the bootstrap skips re-creation from now on.
    from core.admin_bootstrap import DEMO_AGENT_TOMBSTONE_KEY
    from core.models import RuntimeSetting

    deleted_demo_agent = bool((agent.configuration or {}).get("demo_agent"))
    # Registry row also via raw SQL: db.delete(agent) makes the ORM null out
    # loaded child FKs (agent_episodes.agent_id is NOT NULL → IntegrityError)
    # for rows the cleanup above already removed from under its identity map.
    db.execute(
        text(f"DELETE FROM {AgentRegistry.__tablename__} WHERE id = :aid"),
        {"aid": agent_id},
    )
    if deleted_demo_agent:
        tombstone = db.get(RuntimeSetting, DEMO_AGENT_TOMBSTONE_KEY)
        if tombstone is not None:
            tombstone.value_json = {
                "deleted_at": datetime.datetime.now(timezone.utc).isoformat(),
                "agent_id": agent_id,
            }
            tombstone.updated_by = "system"
        else:
            db.add(
                RuntimeSetting(
                    key=DEMO_AGENT_TOMBSTONE_KEY,
                    value_json={
                        "deleted_at": datetime.datetime.now(timezone.utc).isoformat(),
                        "agent_id": agent_id,
                    },
                    updated_by="system",
                )
            )
    db.commit()

    return router.success_response(
        data={"agent_id": agent_id, "rows_cleaned": cleaned},
        message=f"Agent {agent_name} deleted successfully"
    )




@router.post("/{agent_id}/run")
async def run_agent(
    agent_id: str, 
    run_req: AgentRunRequest, 
    background_tasks: BackgroundTasks,
    user: User = Depends(require_permission(Permission.AGENT_RUN)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger an agent execution in the background.

    SECURITY: uses SELECT FOR UPDATE on the agent row to atomically
    transition to 'running' state. Prevents two concurrent run
    requests from both passing the status check.
    """
    agent = (
        db.query(AgentRegistry)
        .filter(AgentRegistry.id == agent_id)
        .with_for_update()
        .first()
    )
    if not agent:
        raise router.not_found_error("Agent", agent_id)

    # Check if agent is deprecated or paused
    if agent.status in [AgentStatus.DEPRECATED.value, AgentStatus.PAUSED.value]:
        raise router.error_response(
            error_code="AGENT_INVALID_STATE",
            message=f"Agent is {agent.status}",
            status_code=400
        )

    if agent.status == "running":
        raise router.conflict_error(
            message="Agent is already running",
            details={"agent_id": agent_id, "current_status": agent.status}
        )

    # Check if we should run synchronously (for testing)
    is_sync = run_req.parameters.get("sync", False)

    if is_sync:
        # Commit to RELEASE the SELECT ... FOR UPDATE row lock BEFORE running
        # the agent. Previously the lock (and the request's DB connection) was
        # held across the full `await execute_agent_task(...)` — serializing
        # concurrent runs of the same agent and pinning a pool slot for the
        # whole execution. execute_agent_task opens its own session, so the
        # lock serves no purpose during the run.
        db.commit()

        result = await execute_agent_task(agent_id, run_req.parameters)
        return router.success_response(
            data={"agent_id": agent_id, "result": result},
            message="Agent execution completed"
        )

    # Run in background
    # We pass agent_id only, task will re-fetch to ensure fresh state/object access
    background_tasks.add_task(execute_agent_task, agent_id, run_req.parameters)

    return router.success_response(
        data={"agent_id": agent_id},
        message="Agent execution started"
    )



@router.patch("/{agent_id}")
async def update_agent(
    agent_id: str,
    update_data: AgentUpdateRequest,
    user: User = Depends(require_permission(Permission.AGENT_MANAGE)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update agent details"""
    agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
    if not agent:
        raise router.not_found_error("Agent", agent_id)

    if update_data.name:
        agent.name = update_data.name
    if update_data.description is not None:
        agent.description = update_data.description
    # P2: per-agent capability binding (zero-trust tool scoping).
    if update_data.capabilities is not None:
        agent.capabilities = update_data.capabilities

    db.commit()
    db.refresh(agent)

    return router.success_response(
        data={
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "capabilities": agent.capabilities or [],
        },
        message="Agent updated successfully"
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
    user: User = Depends(require_permission(Permission.AGENT_MANAGE)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Promote agent to Autonomous mode.

    Manual promotion bypasses the graduation framework — use for agents
    that have demonstrated readiness outside the episodic memory system.
    """
    agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
    if not agent:
        raise router.not_found_error("Agent", agent_id)

    agent.status = AgentStatus.AUTONOMOUS.value
    db.commit()

    return router.success_response(
        data={"agent_status": agent.status, "agent_id": agent_id},
        message=f"Agent {agent_id} promoted to autonomous successfully"
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
    actions = db.query(HITLAction).filter(
        HITLAction.status == HITLActionStatus.PENDING.value
    ).order_by(HITLAction.created_at.desc()).limit(limit).all()
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
    action = (
        db.query(HITLAction)
        .filter(HITLAction.id == action_id)
        .with_for_update()
        .first()
    )
    if not action:
        raise router.not_found_error("HITLAction", action_id)

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
    
    # Broadcast update to UI via WebSocket
    await ws_manager.broadcast("workspace:default", {
        "type": "hitl_decision",
        "action_id": action_id,
        "decision": action.status
    })
    
    return router.success_response(
        data={"decision": action.status, "action_id": action_id},
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
    # 1. Create Agent
    registry_entry = AgentRegistry(
        name=req.name,
        description=req.description,
        category=req.category,
        configuration=req.configuration,
        schedule_config=req.schedule_config,
        module_path="core.generic_agent",
        class_name="GenericAgent",
        status=AgentStatus.STUDENT.value,
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
