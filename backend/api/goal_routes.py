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


def _require_supervisor(db: Session, current_user: User) -> None:
    user = db.query(UserModel).filter(UserModel.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user_meets_role(user, _SUPERVISOR_MIN):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Required role: team_lead or higher",
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


class GoalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = ""
    criteria: Optional[List[dict]] = None
    key_results: Optional[List[dict]] = None
    target_date: Optional[str] = None


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


@router.post("")
async def create_goal(
    payload: GoalCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_supervisor(db, current_user)
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="goal title is required")
    target_dt = None
    if payload.target_date:
        try:
            target_dt = datetime.fromisoformat(
                str(payload.target_date).replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="target_date must be an ISO-8601 date/datetime")
    try:
        goal = _service(current_user, db).create_goal(
            title=title,
            description=payload.description or "",
            criteria=payload.criteria or [],
            key_results=payload.key_results or [],
            owner_id=str(current_user.id),
            target_date=target_dt,
            source="api",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"success": True, "goal": goal}
