"""GoalRun CRUD + lifecycle API (docs/architecture/GOAL_RUN_ORCHESTRATION.md
§5, §7 slice 5). RBAC mirrors playbook_routes: listing/reading is any-
signed-in-user; acts that spend resources, direct agents, or change
supervision are supervisor-grade (team_lead and up — the shared hierarchy,
not a hand-maintained allowlist).
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth import get_current_user, User
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import HITLAction, HITLActionStatus, User as UserModel, UserRole
from core.security.rbac import user_meets_role
from core.personal_scope import resolve_tenant_id, resolve_workspace_id

router = BaseAPIRouter(prefix="/api/goal-runs", tags=["goal-runs"])

logger = logging.getLogger(__name__)

_SUPERVISOR_MIN = UserRole.TEAM_LEAD

# Terminal statuses accept no further loop turns. Kept beside the guarded
# transition table in goal_run_service so a reader can see both.
_TERMINAL_STATUSES = ("achieved", "failed", "cancelled")

# Role-based runs are everyday work: anyone who talks to people outside the
# org (a rep quoting a lead) must be able to start and work their own run.
# team_lead+ keeps the broader powers (arbitrary plans/goals, autonomous mode,
# mode changes, distillation, the workspace-wide event inbox). Viewers and
# guests read only.
MEMBER_MODES = ("training", "shadow")
_RUNNER_MIN = UserRole.MEMBER
# Governance knobs a run's worker must not tune for themselves.
_GOVERNANCE_PARAM_KEYS = ("replan_budget", "wait_ceiling_days")


def _is_supervisor(db: Session, current_user: User) -> bool:
    user = db.query(UserModel).filter(UserModel.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user_meets_role(user, _SUPERVISOR_MIN)


def _require_runner(db: Session, current_user: User) -> None:
    """A viewer/guest may read runs but not start or drive one."""
    user = db.query(UserModel).filter(UserModel.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user_meets_role(user, _RUNNER_MIN):
        raise HTTPException(
            status_code=403,
            detail="Starting or working a goal run requires at least the "
                   "member role",
        )


def _require_supervisor(db: Session, current_user: User) -> None:
    if not _is_supervisor(db, current_user):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Required role: team_lead or higher",
        )


def _require_run_access(db: Session, current_user: User, run: dict) -> None:
    """A run is worked by its OWNER (the person who started it) or any
    supervisor — not by every member. A member must not be able to drive,
    approve or cancel somebody else's run."""
    if _is_supervisor(db, current_user):
        return
    if str(run.get("created_by") or "") == str(current_user.id):
        return
    raise HTTPException(
        status_code=403,
        detail="Only the run's owner or a supervisor (team_lead or higher) "
               "can act on this run",
    )


def _service(current_user: User, db: Session):
    """GoalRunService bound to THIS request's session (each service call
    opens a `with` on the same session; get_db closes it at request end)."""

    @contextmanager
    def _session():
        yield db

    from core.goals.goal_run_service import GoalRunService
    return GoalRunService(
        # resolve_workspace_id inspects ATTRIBUTES on the sources it is
        # given. Passing the raw workspace string here made getattr() miss
        # and silently fall back to "default" — goals and runs could land in
        # different workspaces. Pass the user (2026-09-10).
        workspace_id=resolve_workspace_id(current_user),
        tenant_id=resolve_tenant_id(current_user),
        session_factory=_session,
    )


# ---------------------------------------------------------------- schemas

class GoalRunCreate(BaseModel):
    goal_id: str = Field(min_length=1)
    agent_id: Optional[str] = None
    role: Optional[str] = None
    supervision_mode: str = "shadow"
    plan: Optional[List[dict]] = None   # omitted → seed from role playbooks
    parameters: Optional[dict] = None
    # Kick off the first loop turn on create (2026-09-10 journey fix): a
    # started run must actually start working — otherwise it sits `active`
    # with a cursor and does nothing until a human finds the Advance button.
    # False stages a dormant run for callers that want to schedule it.
    start: bool = True


class ResumeBody(BaseModel):
    approved: bool
    guidance: Optional[str] = None
    # Scope of the guidance when it becomes a lesson: "global" (default —
    # applies to all of this agent's work) or "goal" (true only for THIS run's
    # goal). See core/student_learning_service lesson scope.
    guidance_scope: Optional[str] = None


class ModeBody(BaseModel):
    supervision_mode: str


class CheckpointBody(BaseModel):
    approved: bool
    guidance: Optional[str] = None


class EventBody(BaseModel):
    event: str = Field(min_length=1)
    from_email: Optional[str] = Field(default=None, alias="from")
    subject: Optional[str] = None
    summary: Optional[str] = None
    source: Optional[str] = None
    thread_id: Optional[str] = None
    payload: Optional[dict] = None


# ------------------------------------------------------------------ reads

@router.get("")
async def list_goal_runs(
    goal_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    include_terminal: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = _service(current_user, db)
    runs = svc.list_runs(goal_id=goal_id, agent_id=agent_id, role=role,
                         status=status, include_terminal=include_terminal)
    return {"runs": runs}


@router.get("/{run_id}")
async def get_goal_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = _service(current_user, db)
    run = svc.get_run(run_id)
    if not run:
        raise router.not_found_error("GoalRun", run_id)
    return run


@router.get("/{run_id}/decisions")
async def get_goal_run_decisions(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = _service(current_user, db)
    if not svc.get_run(run_id):
        raise router.not_found_error("GoalRun", run_id)
    return {"decisions": svc.get_decisions(run_id)}


@router.get("/{run_id}/canvases")
async def get_goal_run_canvases(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The run's touch-point canvases (goal-grouped gallery / timeline)."""
    svc = _service(current_user, db)
    if not svc.get_run(run_id):
        raise router.not_found_error("GoalRun", run_id)
    return {"canvases": svc.list_canvases(run_id)}


# ------------------------------------------------------------------ writes

@router.post("")
async def create_goal_run(
    payload: GoalRunCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.models import GoalObjective
    from core.goals.goal_run_learning import seed_plan_for_run

    supervisor = _is_supervisor(db, current_user)
    if not supervisor:
        _require_runner(db, current_user)
    svc = _service(current_user, db)
    goal = db.query(GoalObjective).filter(
        GoalObjective.id == payload.goal_id).first()
    if not goal:
        raise router.not_found_error("Goal", payload.goal_id)

    # Role-based access (2026-09-10, generalized to ANY business): a member
    # who works with people outside the org starts their OWN role-based run.
    # The role is the business function, derived from the business's OWN data
    # (the selected agent's specialty/category) when not given — never a
    # hardcoded industry. Members get: role from the agent, a plan seeded
    # from that role's approved playbooks (never hand-authored), no
    # self-promotion to `autonomous`, and no tuning the governance knobs.
    # team_lead+ keeps the broader powers.
    role = (payload.role or "").strip() or None
    if not role and payload.agent_id:
        from core.models import AgentRegistry
        agent = db.query(AgentRegistry).filter(
            AgentRegistry.id == payload.agent_id).first()
        if agent:
            role = (getattr(agent, "specialty", None)
                    or getattr(agent, "category", None) or "").strip() or None
    mode = payload.supervision_mode
    parameters = payload.parameters
    if not supervisor:
        if not role:
            raise HTTPException(
                status_code=422,
                detail="role is required to start a role-based run — bind a "
                       "role agent (its specialty defines the role) or pass "
                       "an explicit role")
        if payload.plan:
            raise HTTPException(
                status_code=403,
                detail="A custom plan requires a supervisor (team_lead or "
                       "higher) — role-based runs are seeded from the role's "
                       "approved playbooks")
        if mode not in MEMBER_MODES:
            raise HTTPException(
                status_code=403,
                detail=f"supervision_mode '{mode}' requires a supervisor; "
                       f"members may use {list(MEMBER_MODES)}")
        parameters = {k: v for k, v in (parameters or {}).items()
                      if k not in _GOVERNANCE_PARAM_KEYS}

    plan = payload.plan
    seed_source = None
    if not plan:
        seeded = seed_plan_for_run(
            goal.title, role=role, agent_id=payload.agent_id,
            tenant_id=resolve_tenant_id(current_user))
        plan = seeded["plan"]
        seed_source = seeded["source"]
    try:
        run = svc.create_run(payload.goal_id, agent_id=payload.agent_id,
                             role=role,
                             supervision_mode=mode,
                             plan=plan, parameters=parameters,
                             created_by=str(current_user.id))
        svc.transition(run["id"], "active")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Kick off the first loop turn so "start" means started. Fault-isolated:
    # a router/executor hiccup still returns the created run (the supervisor
    # can Advance it), and an exception here must never lose the run row.
    started = None
    if payload.start:
        try:
            started = await svc.advance(run["id"])
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(f"goal run {run['id']}: kickoff advance failed: {exc}")
            started = {"advanced": False, "error": "kickoff failed"}
    return {"success": True, "id": run["id"], "seed_source": seed_source,
            "started": started, "run": svc.get_run(run["id"])}


@router.post("/{run_id}/advance")
async def advance_goal_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manual loop turn (owner or supervisor nudge)."""
    svc = _service(current_user, db)
    run = svc.get_run(run_id)
    if not run:
        raise router.not_found_error("GoalRun", run_id)
    _require_run_access(db, current_user, run)
    if run["status"] in _TERMINAL_STATUSES:
        # Was a 200 no-op the UI reported as success ("Advanced one decision
        # cycle" while nothing moved). Terminal is terminal.
        raise HTTPException(
            status_code=409,
            detail=f"run is {run['status']} — a finished goal run takes no "
                   f"further loop turns")
    result = await svc.advance(run_id)
    if not result.get("advanced") and result.get("reason") == "run not found":
        raise router.not_found_error("GoalRun", run_id)
    return result


@router.post("/{run_id}/resume")
async def resume_goal_run(
    run_id: str,
    payload: ResumeBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resolve a held decision: approve → execute; reject → the guidance is
    a correction (instant lesson for the agent). Owner or supervisor."""
    svc = _service(current_user, db)
    run = svc.get_run(run_id)
    if not run:
        raise router.not_found_error("GoalRun", run_id)
    _require_run_access(db, current_user, run)
    try:
        return await svc.resume(run_id, approved=payload.approved,
                                reviewer=str(current_user.id),
                                guidance=payload.guidance,
                                guidance_scope=payload.guidance_scope)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/{run_id}/checkpoints/{hitl_id}/resolve")
async def resolve_checkpoint(
    run_id: str,
    hitl_id: str,
    payload: CheckpointBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resolve a PROCESS-INTRINSIC checkpoint (a human sign-off step the
    role's process defines): the HITL row closes and the wake drives the next
    loop turn. Owner or supervisor."""
    svc = _service(current_user, db)
    run = svc.get_run(run_id)
    if not run:
        raise router.not_found_error("GoalRun", run_id)
    _require_run_access(db, current_user, run)
    hitl = db.query(HITLAction).filter(HITLAction.id == hitl_id).first()
    if not hitl or (hitl.params or {}).get("run_id") != run_id:
        raise router.not_found_error("Checkpoint", hitl_id)
    if hitl.status != HITLActionStatus.PENDING.value:
        raise HTTPException(status_code=409,
                            detail=f"checkpoint already {hitl.status}")
    hitl.status = (HITLActionStatus.APPROVED.value if payload.approved
                   else HITLActionStatus.REJECTED.value)
    hitl.reviewed_by = str(current_user.id)
    hitl.user_feedback = payload.guidance
    db.commit()
    wake = svc.consume_wake(run_id, {"event": "human_checkpoint",
                                     "hitl_id": hitl_id,
                                     "approved": payload.approved})
    if not wake.get("consumed"):
        return {"success": True, "resumed": False,
                "reason": wake.get("reason", "run not waiting")}
    if payload.approved:
        svc.complete_checkpoint(run_id,
                                step_id=(hitl.params or {}).get("step_id"))
    else:
        # Rejection: the cursor returns to the guarded work step so the
        # router's next decision can revise REAL work instead of
        # re-requesting the same approval.
        svc.rewind_to_work_before(run_id,
                                  step_id=(hitl.params or {}).get("step_id"))
    result = await svc.advance(
        run_id, event={"event": "human_checkpoint",
                       "approved": payload.approved,
                       "guidance": payload.guidance,
                       "summary": payload.guidance or
                                  ("checkpoint approved" if payload.approved
                                   else "checkpoint rejected")})
    return {"success": True, "resumed": True, "loop": result}


@router.post("/{run_id}/distill")
async def distill_goal_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Distill a completed run's decision log into a playbook DRAFT
    (source=learned) in the existing approval queue (§3.6). 409 when the
    run is too thin or a draft for this process already exists (fingerprint
    dedup)."""
    _require_supervisor(db, current_user)
    svc = _service(current_user, db)
    run = svc.get_run(run_id)
    if not run:
        raise router.not_found_error("GoalRun", run_id)
    if run["status"] not in ("achieved", "failed", "cancelled"):
        raise HTTPException(
            status_code=409,
            detail={"success": False,
                    "error": "Only a finished run can be distilled — "
                            "this one is still "
                            f"{run['status']}"})
    from core.models import GoalObjective
    from core.goals.goal_run_learning import distill_run_to_playbook_draft
    goal = db.query(GoalObjective).filter(
        GoalObjective.id == run["goal_id"]).first()
    draft = distill_run_to_playbook_draft(
        run, tenant_id=resolve_tenant_id(current_user),
        workspace_id=resolve_workspace_id(current_user),
        goal_title=goal.title if goal else "")
    if draft is None:
        raise HTTPException(
            status_code=409,
            detail={"success": False,
                    "error": "Nothing new to distill — the run's decision "
                             "log is too thin, or a draft for this process "
                             "already exists in the approval queue"})
    return {"success": True, "draft": draft}


@router.post("/{run_id}/mode")
async def set_supervision_mode(
    run_id: str,
    payload: ModeBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_supervisor(db, current_user)
    svc = _service(current_user, db)
    try:
        run = svc.set_supervision_mode(run_id, payload.supervision_mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"success": True, "run": run}


@router.post("/{run_id}/cancel")
async def cancel_goal_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = _service(current_user, db)
    existing = svc.get_run(run_id)
    if not existing:
        raise router.not_found_error("GoalRun", run_id)
    _require_run_access(db, current_user, existing)
    try:
        run = svc.cancel(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"success": True, "run": run}


# ----------------------------------------------------------------- events

@router.post("/events")
async def ingest_goal_run_event(
    payload: EventBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Integration inbox for waiting runs (inbound email replies, webhook
    events, human input). Matching runs wake and advance one loop turn.

    Supervisor-gated: an event wakes a run and drives the router (and, in
    shadow/autonomous, the executors) — a member must not be able to inject
    one. Consistent with every other run-mutating route here.
    """
    _require_supervisor(db, current_user)
    event = {"event": payload.event,
             "from": payload.from_email, "subject": payload.subject,
             "summary": payload.summary, "source": payload.source,
             "thread_id": payload.thread_id, **(payload.payload or {})}
    from core.goals.goal_run_events import ingest_event

    @contextmanager
    def _session():
        yield db

    out = await ingest_event(event,
                             workspace_id=resolve_workspace_id(current_user),
                             tenant_id=resolve_tenant_id(current_user),
                             session_factory=_session)
    return {"success": True, **out}


@router.get("/promotion/{agent_id}")
async def promotion_evidence(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Advisory training→shadow→autonomous promotion evidence (§3.7B)."""
    _require_supervisor(db, current_user)
    from core.goals.goal_run_learning import evaluate_mode_promotion

    @contextmanager
    def _session():
        yield db

    return evaluate_mode_promotion(
        agent_id,
        workspace_id=resolve_workspace_id(current_user),
        tenant_id=resolve_tenant_id(current_user),
        session_factory=_session)
