"""Goal CRUD — the WHAT a role agent pursues (companion to
``api/goal_run_routes.py``, which is the WHO/HOW long-running execution).

Why this exists (2026-09-10 journey trace): ``GoalObjective`` rows were
creatable only by the agent action ``goals.create`` and readable only by
passing a known id into a run. The run-start journey therefore had its first
link severed — a supervisor could not see the goals a run can work, and had
no HTTP surface to create the goal a new run needs (``POST /api/goal-runs``
404s on an unknown goal). This is that surface.

RBAC mirrors ``playbook_routes`` / ``goal_run_routes``: listing and reading
is any-signed-in-user (employees may see what the team is working toward);
creating a goal — which the whole workspace's agents may then be pointed at —
is supervisor-grade (team_lead and up, the shared hierarchy).

Writes are verified, not just gated: ``core.goals.goal_write_service`` re-binds
the authoritative actor (id/status/active/role/workspace), the request-entry
workspace and the reviewed goal metadata in the same transaction as one
``AuditLog`` receipt. A demotion/deactivation/workspace move committed after the
role gate, or a peer metadata change, refuses with effect=none instead of
applying stale authority. Internal trusted lifecycle callers keep using
``GoalService`` directly — ordinary goal writes never become a human prompt.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth import get_current_user, User
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import User as UserModel, UserRole
from core.personal_scope import resolve_tenant_id, resolve_workspace_id
from core.security.rbac import user_meets_role

router = BaseAPIRouter(prefix="/api/goals", tags=["goals"])

_SUPERVISOR_MIN = UserRole.TEAM_LEAD
_RUNNER_MIN = UserRole.MEMBER


def _is_supervisor(db: Session, current_user: User) -> bool:
    user = db.query(UserModel).filter(UserModel.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user_meets_role(user, _SUPERVISOR_MIN)


def _require_runner(db: Session, current_user: User) -> None:
    """Creating the goal for a piece of work is a member act; viewers read."""
    user = db.query(UserModel).filter(UserModel.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user_meets_role(user, _RUNNER_MIN):
        raise HTTPException(
            status_code=403,
            detail="Creating a goal requires at least the member role",
        )


def _require_supervisor(db: Session, current_user: User) -> None:
    if not _is_supervisor(db, current_user):
        raise HTTPException(
            status_code=403,
            detail="This goal setting requires a supervisor "
                   "(team_lead or higher)",
        )


def _service(current_user: User, db: Session):
    """GoalService bound to THIS request's session (same pattern as
    goal_run_routes._service — one session per request, closed by get_db)."""

    @contextmanager
    def _session():
        yield db

    from core.goals.goal_service import GoalService
    return GoalService(
        workspace_id=resolve_workspace_id(current_user),
        tenant_id=resolve_tenant_id(current_user),
        session_factory=_session,
    )


def _raise_goal_write(result: dict) -> None:
    """Map the verified-write service result onto the public HTTP contract.

    A refused/conflicted/uncertain write is never reported as success; the
    caller gets the truthful effect state and can refresh instead of repeating
    an ambiguous operation.
    """
    status_value = str(result.get("status") or "")
    if status_value == "refused":
        raise HTTPException(
            status_code=int(result.get("http_status") or 403),
            detail={
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
                "error": {
                    "code": result.get("error_code")
                    or "GOAL_WRITE_TRANSACTION_ROLLED_BACK",
                    "message": result.get("error")
                    or "The goal write did not apply.",
                },
                "verification": result.get("verification"),
                "operation_id": result.get("operation_id"),
                "audit_id": result.get("audit_id"),
            },
        )
    if status_value in ("committed_unverified", "effect_unknown"):
        code = (
            "GOAL_WRITE_EFFECT_UNKNOWN"
            if status_value == "effect_unknown"
            else "GOAL_WRITE_COMMITTED_UNVERIFIED")
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": code,
                    "message": result.get("message")
                    or "The goal write outcome is uncertain.",
                },
                "verification": result.get("verification"),
                "operation_id": result.get("operation_id"),
                "audit_id": result.get("audit_id"),
                "target_id": result.get("target_id"),
            },
        )


class GoalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = ""
    criteria: Optional[List[dict]] = None
    key_results: Optional[List[dict]] = None
    target_date: Optional[str] = None
    utility_target: Optional[dict] = None


class UtilityTargetBody(BaseModel):
    metric: str
    direction: str
    source: str
    description: str = ""


@router.get("")
async def list_goals(
    status: Optional[str] = None,
    include_terminal: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = _service(current_user, db)
    return {"goals": svc.list_goals(status=status,
                                    include_terminal=include_terminal)}


@router.get("/{goal_id}")
async def get_goal(
    goal_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    goal = _service(current_user, db).get_goal(goal_id)
    if not goal:
        raise router.not_found_error("Goal", goal_id)
    return goal


@router.get("/{goal_id}/utility")
async def get_goal_utility(
    goal_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Durable utility target + deterministic ranking of completed runs.

    Read-only. Ranking is computed from persisted GoalRun evidence; it never
    changes the goal's status or progress.
    """
    svc = _service(current_user, db)
    goal = svc.get_goal(goal_id)
    if not goal:
        raise router.not_found_error("Goal", goal_id)
    ranking = svc.utility_ranking(goal_id)
    if ranking is None:
        return {"goal_id": goal_id, "target": None, "ranking": [],
                "winner": None, "eligible_count": 0}
    return {"goal_id": goal_id, **ranking}


@router.put("/{goal_id}/utility")
async def set_goal_utility(
    goal_id: str,
    payload: UtilityTargetBody,
    operation_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Attach an explicit utility target to an existing goal (supervisor).

    The role gate above reads the request-entry actor; the write service then
    re-binds the actor and the reviewed goal metadata in the same transaction
    as one receipt, so a concurrent demotion/deactivation/workspace move or a
    peer metadata change is refused instead of applied.
    """
    _require_supervisor(db, current_user)
    from core.goals import goal_write_service as writes
    result = writes.set_utility_target(
        db,
        actor=current_user,
        workspace_id=resolve_workspace_id(current_user),
        tenant_id=resolve_tenant_id(current_user),
        goal_id=goal_id,
        target=payload.model_dump(),
        operation_id=operation_id,
    )
    _raise_goal_write(result)
    data = result.get("data") or {}
    return {"success": True, "goal_id": goal_id,
            "utility_target": data.get("utility_target"),
            "verification": data.get("verification"),
            "operation_id": result.get("operation_id"),
            "audit_id": result.get("audit_id")}


@router.delete("/{goal_id}/utility")
async def clear_goal_utility(
    goal_id: str,
    operation_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_supervisor(db, current_user)
    from core.goals import goal_write_service as writes
    result = writes.clear_utility_target(
        db,
        actor=current_user,
        workspace_id=resolve_workspace_id(current_user),
        tenant_id=resolve_tenant_id(current_user),
        goal_id=goal_id,
        operation_id=operation_id,
    )
    _raise_goal_write(result)
    data = result.get("data") or {}
    return {"success": True, "goal_id": goal_id,
            "utility_target": data.get("utility_target"),
            "verification": data.get("verification"),
            "operation_id": result.get("operation_id"),
            "audit_id": result.get("audit_id")}


@router.post("")
async def create_goal(
    payload: GoalCreate,
    operation_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Role-based access (2026-09-10): goals are per-piece-of-work in ANY
    # business (a lead, a claim, a candidate, a purchase), so the people
    # doing that work may create one — but machine-checkable success
    # criteria and target dates shape how every agent terminates, so those
    # stay supervisor-grade.
    workspace_id = resolve_workspace_id(current_user)
    tenant_id = resolve_tenant_id(current_user)
    supervisor = _is_supervisor(db, current_user)
    if not supervisor:
        _require_runner(db, current_user)
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="goal title is required")
    if not supervisor and (payload.criteria or payload.key_results
                           or payload.target_date or payload.utility_target):
        raise HTTPException(
            status_code=403,
            detail="criteria, key_results, target_date and utility_target "
                   "require a supervisor (team_lead or higher) — create the "
                   "goal with a title and description, and a supervisor can "
                   "enrich it")
    target_dt = None
    if payload.target_date:
        try:
            target_dt = datetime.fromisoformat(
                str(payload.target_date).replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="target_date must be an ISO-8601 date/datetime")
    from core.goals import goal_write_service as writes
    result = writes.create_goal(
        db,
        actor=current_user,
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        title=title,
        description=payload.description or "",
        criteria=payload.criteria or [],
        key_results=payload.key_results or [],
        target_date=target_dt,
        utility_target=payload.utility_target,
        source="api",
        operation_id=operation_id,
    )
    _raise_goal_write(result)
    data = result.get("data") or {}
    return {"success": True, "goal": data,
            "verification": data.get("verification"),
            "operation_id": result.get("operation_id"),
            "audit_id": result.get("audit_id")}
