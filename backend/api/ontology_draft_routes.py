"""Ontology Draft automation routes — admin-gated, consent-gated.

Management surface for the ontology draft promotion automation
(``core/ontology/ontology_draft_automation.py``):

GET  /api/v1/ontology-drafts/status      draft census + automation state
GET  /api/v1/ontology-drafts/automation  current mode/interval/latest decisions
POST /api/v1/ontology-drafts/automation  set mode (off|notify|approve|auto) /
                                         interval_min
POST /api/v1/ontology-drafts/run-now     force one evidence+consent pass
GET  /api/v1/ontology-drafts/pending     queued approvals awaiting consent
POST /api/v1/ontology-drafts/approve/{action_id}   apply a queued promotion
POST /api/v1/ontology-drafts/reject/{action_id}    reject a queued promotion

All endpoints require WORKSPACE_ADMIN/SUPER_ADMIN. The pass only activates
types whose evidence cleared the documented thresholds; revocation is
always automatic; manual decisions are never overridden.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.auth import User, get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import UserRole

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/v1/ontology-drafts", tags=["Ontology Drafts"])

_ADMIN_ROLES = [
    UserRole.WORKSPACE_ADMIN.value,
    UserRole.SUPER_ADMIN.value,
]


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user


def _automation():
    import core.ontology.ontology_draft_automation as _auto

    return _auto


@router.get("/status")
async def get_status(
    tenant_id: Optional[str] = Query(None, description="Scope to one tenant"),
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Read-only census: how many drafts exist, how many are eligible, and
    the ledger state — never mutates anything."""
    from core.ontology.ontology_draft_automation import census

    return census(db, tenant_id=tenant_id)


@router.get("/automation")
async def get_automation(
    tenant_id: Optional[str] = Query(None),
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    auto = _automation()
    pending = auto.list_pending(db, tenant_id=tenant_id)
    return {
        "mode": auto.automation_mode(),
        "interval_min": auto.automation_interval_min(),
        "thresholds": auto.thresholds(),
        "pending_approvals": len(pending),
    }


@router.post("/automation")
async def set_automation(
    mode: Optional[str] = Query(None),
    interval_min: Optional[float] = Query(None),
    _admin: User = Depends(_require_admin),
):
    auto = _automation()
    try:
        cfg = auto.set_automation_config(mode=mode, interval_min=interval_min)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return cfg


@router.post("/run-now")
async def run_now(
    tenant_id: Optional[str] = Query(None),
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Force one pass (skips the interval cooldown)."""
    auto = _automation()
    return auto.run_automation_pass(db, tenant_id=tenant_id, force=True)


@router.get("/pending")
async def list_pending(
    tenant_id: Optional[str] = Query(None),
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    auto = _automation()
    return {"pending": auto.list_pending(db, tenant_id=tenant_id)}


@router.post("/approve/{action_id}")
async def approve_queued(
    action_id: int,
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Admin consent: apply a queued promotion (activates the draft)."""
    auto = _automation()
    if auto.approve_action(db, action_id):
        return {"approved": True, "action_id": action_id}
    raise HTTPException(status_code=404, detail="Queued approval not found")


@router.post("/reject/{action_id}")
async def reject_queued(
    action_id: int,
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    auto = _automation()
    if auto.reject_action(db, action_id):
        return {"rejected": True, "action_id": action_id}
    raise HTTPException(status_code=404, detail="Queued approval not found")
