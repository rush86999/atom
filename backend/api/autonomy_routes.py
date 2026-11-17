"""Autonomy policy API — the owner decides which agent-action topics always
require a human in the loop and which the agent may handle autonomously once
mature. Backs the Autonomy panel on the canvas page (reusable anywhere).

The additive ``/never-rules`` endpoints persist the OPT IN "never autonomous"
task baskets. They reuse the same policy module and enforcement gate; this is
not a parallel policy system.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.autonomy_policy import (
    NeverRuleConflict,
    NeverRuleNotFound,
    NeverRuleValidationError,
    create_never_rule,
    delete_never_rule,
    list_never_rules,
    list_topics,
    set_mode,
    update_never_rule,
)
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import AgentRegistry, Canvas, User
from core.task_classification import (
    CATEGORY_VALUES,
    DIFFICULTY_VALUES,
    DOMAIN_SUGGESTIONS,
)

router = BaseAPIRouter(prefix="/api/autonomy", tags=["Autonomy"])
logger = logging.getLogger(__name__)


class AutonomyModeRequest(BaseModel):
    mode: str  # human_always | auto_if_mature


class NeverRuleBody(BaseModel):
    """Public create/update body. Dimension validation lives in the policy
    module so direct service callers and HTTP get identical semantics."""

    name: str
    enabled: bool = True
    match: Dict[str, Any]
    expected_revision: Optional[int] = None


def _canvas_type_for_user(db: Session, user_id: str, canvas_id: str) -> Optional[str]:
    """The canvas's type when it belongs to the caller (shared/public canvases
    deliberately yield no canvas context — the panel degrades to the general
    set rather than leaking another user's canvas metadata)."""
    try:
        canvas = (
            db.query(Canvas)
            .filter(Canvas.id == canvas_id, Canvas.created_by == user_id)
            .first()
        )
        if canvas is not None:
            return canvas.canvas_type
    except Exception as e:
        logger.debug(f"autonomy canvas lookup skipped: {e}")
    return None


def _accessible_agent_id(db: Session, user_id: str, agent_id: Optional[str]) -> Optional[str]:
    """The agent_id only when it resolves to the caller's hire (or a legacy
    owner-less row) — trust/maturity stats must not leak across users."""
    if not agent_id:
        return None
    try:
        row = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if row is None:
            return None
        if row.user_id and str(row.user_id) != user_id:
            return None
        return agent_id
    except Exception as e:
        logger.debug(f"autonomy agent lookup skipped: {e}")
        return None


@router.get("/topics")
async def get_autonomy_topics(
    canvas_id: Optional[str] = None,
    canvas_type: Optional[str] = None,
    agent_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """All action topics with the caller's effective mode.

    ``canvas_id`` (or a plain ``canvas_type`` fallback) groups the topics:
    those primary for the canvas's type come back flagged
    ``canvas_relevant`` so the Autonomy tab can lead with them. ``agent_id``
    attaches the hire's live trust×maturity gate per topic."""
    user_id = str(current_user.id)
    resolved_canvas_type = (
        _canvas_type_for_user(db, user_id, canvas_id) if canvas_id else None
    ) or canvas_type
    resolved_agent_id = _accessible_agent_id(db, user_id, agent_id)
    return {
        "topics": list_topics(
            user_id,
            db,
            canvas_type=resolved_canvas_type,
            agent_id=resolved_agent_id,
        ),
        "canvas_type": resolved_canvas_type,
    }


@router.put("/topics/{topic}")
async def set_autonomy_mode(
    topic: str,
    request: AutonomyModeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set the caller's mode for a topic."""
    if not set_mode(db, str(current_user.id), topic, request.mode):
        raise HTTPException(status_code=400, detail=f"Unknown topic or mode: {topic}/{request.mode}")
    return {"success": True, "topic": topic, "mode": request.mode}


def _effective_write_scope(current_user: User) -> Dict[str, Optional[str]]:
    """Owner always wins; workspace/tenant are optional narrowing scopes.

    Personal deployments commonly have neither set, so ``None`` is persisted
    and means default scope. This mirrors the existing per-user
    ``action_autonomy_policies`` behavior rather than inventing a new tenant
    requirement.
    """
    return {
        "user_id": str(current_user.id),
        "workspace_id": (
            str(current_user.workspace_id)
            if getattr(current_user, "workspace_id", None) else None),
        "tenant_id": (
            str(current_user.tenant_id)
            if getattr(current_user, "tenant_id", None) else None),
    }


@router.get("/never-rules")
async def get_never_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the caller's never-autonomous task baskets.

    Disabled rules are returned too so the UI can re-enable/edit them; only
    enabled rules participate in runtime enforcement.
    """
    scope = _effective_write_scope(current_user)
    rules = list_never_rules(db, scope["user_id"])
    return {
        "rules": rules,
        "count": len(rules),
        "dimensions": {
            "difficulty": list(DIFFICULTY_VALUES),
            "category": list(CATEGORY_VALUES),
            "domain": list(DOMAIN_SUGGESTIONS),
        },
        "scope": scope,
    }


@router.post("/never-rules", status_code=201)
async def post_never_rule(
    request: NeverRuleBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create one opt-in rule. The list is empty until this is called."""
    scope = _effective_write_scope(current_user)
    try:
        rule = create_never_rule(
            db,
            scope["user_id"],
            name=request.name,
            match=request.match,
            enabled=request.enabled,
            tenant_id=scope["tenant_id"],
            workspace_id=scope["workspace_id"],
        )
    except NeverRuleValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "rule": rule}


@router.put("/never-rules/{rule_id}")
async def put_never_rule(
    rule_id: str,
    request: NeverRuleBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Replace one rule owned by the caller."""
    scope = _effective_write_scope(current_user)
    try:
        rule = update_never_rule(
            db,
            scope["user_id"],
            rule_id,
            name=request.name,
            match=request.match,
            enabled=request.enabled,
            expected_revision=request.expected_revision,
        )
    except NeverRuleNotFound as exc:
        raise HTTPException(status_code=404, detail="rule_not_found") from exc
    except NeverRuleConflict as exc:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=409,
            content={
                "detail": "rule_revision_conflict",
                "current_revision": exc.current_revision,
            },
        )
    except NeverRuleValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "rule": rule}


@router.delete("/never-rules/{rule_id}")
async def remove_never_rule(
    rule_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete one rule owned by the caller (cross-user ids are not found)."""
    try:
        delete_never_rule(db, str(current_user.id), rule_id)
    except NeverRuleNotFound as exc:
        raise HTTPException(status_code=404, detail="rule_not_found") from exc
    return {"success": True, "id": rule_id, "deleted": True}
