"""Playbook CRUD + approval (Installation Adaptation Plan Phase 3) —
company processes as procedural memory. Drafts (taught/learned) NEVER enter
prompts until a supervisor approves them here; approve/retire are the HITL
gate. Tenant-scoped by the caller's account.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth import get_current_user, User
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import User as UserModel, UserRole
from core.personal_scope import resolve_tenant_id

router = BaseAPIRouter(prefix="/api/playbooks", tags=["playbooks"])

# Draft promotion/retirement changes what EVERY agent in the tenant is
# advised by — supervisor-grade only (same gate as the other supervision
# surfaces: agent_maturity/audit/episode/supervision routes). Listing stays
# any-signed-in-user: employees may see the queue; only supervisors act.
_SUPERVISOR_ROLES = [
    UserRole.TEAM_LEAD.value,
    UserRole.WORKSPACE_ADMIN.value,
    UserRole.SUPER_ADMIN.value,
]


def _require_supervisor(db: Session, current_user: User) -> None:
    user = db.query(UserModel).filter(UserModel.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role not in _SUPERVISOR_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Required role: TEAM_LEAD or ADMIN",
        )


class PlaybookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    trigger_canvas_type: Optional[str] = None
    trigger_keywords: List[str] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=list)
    template_questions: List[str] = Field(default_factory=list)
    examples: List[dict] = Field(default_factory=list)
    # authored drafts start approved when the supervisor authors them
    # directly; taught/learned drafts start in `draft`.
    approval_state: str = "approved"


@router.get("")
async def list_playbooks(
    include_drafts: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.playbook_service import PlaybookService

    svc = PlaybookService(db, tenant_id=resolve_tenant_id(current_user))
    rows = svc.list(include_drafts=include_drafts)
    return {
        "playbooks": [
            {
                "id": r.id, "name": r.name, "description": r.description,
                "trigger_canvas_type": r.trigger_canvas_type,
                "trigger_keywords": r.trigger_keywords or [],
                "steps": r.steps or [],
                "template_questions": r.template_questions or [],
                "source": r.source,
                "approval_state": r.approval_state,
                "version": r.version,
            }
            for r in rows
        ]
    }


@router.post("")
async def create_playbook(
    payload: PlaybookCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.playbook_service import PlaybookService

    if payload.approval_state not in ("approved", "draft"):
        return {"success": False,
                "error": "approval_state must be approved or draft"}
    svc = PlaybookService(db, tenant_id=resolve_tenant_id(current_user))
    row = svc.create(
        payload.name,
        description=payload.description,
        trigger_canvas_type=payload.trigger_canvas_type,
        trigger_keywords=payload.trigger_keywords,
        steps=payload.steps,
        template_questions=payload.template_questions,
        examples=payload.examples,
        source="authored",
        approval_state=payload.approval_state,
        created_by=str(current_user.id),
    )
    return {"success": True, "id": row.id, "approval_state": row.approval_state}


@router.post("/{playbook_id}/approve")
async def approve_playbook(
    playbook_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """THE HITL gate: a draft (taught or sleep-time-learned) only enters
    prompts after this. Approval is attributed to the supervisor.

    WikiSkill W5: when the draft originated from incident evals, the evals
    are replayed first — ATOM_PLAYBOOK_EVAL_GATE=enforce blocks promotion
    while any of them fails; shadow (default) records the replay outcome on
    the playbook and approves."""
    from fastapi import HTTPException

    from core.playbook_service import PlaybookService

    svc = PlaybookService(db, tenant_id=resolve_tenant_id(current_user))
    _require_supervisor(db, current_user)
    result = await svc.approve(playbook_id, actor=str(current_user.id))
    if result is None:
        raise router.not_found_error("Playbook", playbook_id)
    if not result["approved"]:
        raise HTTPException(
            status_code=409,
            detail={
                "success": False,
                "error": "Blocked by the incident-eval gate "
                         "(ATOM_PLAYBOOK_EVAL_GATE=enforce)",
                "eval_gate": {
                    k: v for k, v in (result["eval_gate"] or {}).items()
                    if k != "results"
                },
            },
        )
    row = result["playbook"]
    return {"success": True, "id": row.id, "approval_state": row.approval_state,
            "eval_gate": {
                k: v for k, v in (result["eval_gate"] or {}).items()
                if k != "results"
            }}


@router.post("/{playbook_id}/retire")
async def retire_playbook(
    playbook_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.playbook_service import PlaybookService

    svc = PlaybookService(db, tenant_id=resolve_tenant_id(current_user))
    _require_supervisor(db, current_user)
    row = svc.set_state(playbook_id, "retired", actor=str(current_user.id))
    if row is None:
        raise router.not_found_error("Playbook", playbook_id)
    return {"success": True, "id": row.id, "approval_state": row.approval_state}


class PlaybookUpdate(BaseModel):
    """Draft edits before approval (Playbook Journey P1 — "Edit steps
    first"). Approved playbooks are versioned objects; editing those goes
    through retire + re-draft, not in-place mutation."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    trigger_canvas_type: Optional[str] = None
    trigger_keywords: Optional[List[str]] = None
    steps: Optional[List[str]] = None
    template_questions: Optional[List[str]] = None


@router.put("/{playbook_id}")
async def update_playbook(
    playbook_id: str,
    payload: PlaybookUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.playbook_service import PlaybookService

    svc = PlaybookService(db, tenant_id=resolve_tenant_id(current_user))
    _require_supervisor(db, current_user)
    row = svc.update(
        playbook_id,
        name=payload.name,
        description=payload.description,
        trigger_canvas_type=payload.trigger_canvas_type,
        trigger_keywords=payload.trigger_keywords,
        steps=payload.steps,
        template_questions=payload.template_questions,
    )
    if row is None:
        existing = svc.get(playbook_id)
        if existing is None:
            raise router.not_found_error("Playbook", playbook_id)
        raise HTTPException(
            status_code=409,
            detail={"success": False,
                    "error": "Only DRAFT playbooks can be edited in place — "
                             "retire the approved playbook and re-draft instead"},
        )
    return {"success": True, "id": row.id, "approval_state": row.approval_state}
