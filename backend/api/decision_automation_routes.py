"""Decision Plane Management API — automation control + approval queue.

Management surface for the consent-gated decision-plane automation
(``core/decision_automation.py``). Admins can:

- inspect the automation (mode + pending approvals + latest action per surface)
- trigger a certification pass on demand
- approve / reject pending certifications (action_id)

All mutating endpoints require an admin role. Read-only status is also
available publicly at ``/health/decision-router``. Nothing here enforces:
approval only flips the ledger; enforcement resolves off until certified.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, cast

from fastapi import APIRouter, Depends, HTTPException

from core.auth import get_current_user
from core.database import get_db
from core.models import User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/decision-automation", tags=["Decision Plane"])

_ADMIN_ROLES = (
    UserRole.SUPER_ADMIN.value,
    UserRole.OWNER.value,
    UserRole.ADMIN.value,
    UserRole.WORKSPACE_ADMIN.value,
)


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Admin gate for management endpoints (super_admin/owner/admin/workspace_admin)."""
    role = getattr(current_user, "role", None)
    if role not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user


@router.get("/status")
async def decision_automation_status(db=Depends(get_db)) -> Dict[str, Any]:
    """Full decision-plane status (phases + automation block). Read-only."""
    try:
        from core.decision_automation import decision_status

        return cast(Dict[str, Any], decision_status(db))
    except Exception as e:
        logger.error(f"Decision automation status failed: {e}")
        return {"phase": "error", "error": "internal"}


@router.get("/automation")
async def get_automation(
    _admin: User = Depends(_require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Automation mode, pending approval queue, latest action per surface."""
    try:
        from core.decision_automation import get_automation_status

        return cast(Dict[str, Any], get_automation_status(db))
    except Exception as e:
        logger.error(f"Automation status failed: {e}")
        raise HTTPException(status_code=500, detail="Automation status unavailable")


@router.post("/automation/run-now")
async def run_automation_now(
    _admin: User = Depends(_require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Trigger an immediate certification pass (writes certify/revoke actions)."""
    try:
        from core import decision_automation as da

        actions = da.run_automation_pass(db)
        return {"actions": actions}
    except Exception as e:
        logger.error(f"Automation run failed: {e}")
        raise HTTPException(status_code=500, detail="Automation run failed")


@router.post("/automation/approve")
async def approve_certification(
    payload: Dict[str, Any],
    _admin: User = Depends(_require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Approve a pending certification action (flips resolve on)."""
    try:
        action_id = int(payload.get("action_id") or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="action_id is required")
    if not action_id:
        raise HTTPException(status_code=422, detail="action_id is required")
    try:
        from core import decision_automation as da

        ok = da.approve_action(db, action_id)
        db.commit()
    except Exception as e:
        logger.error(f"Approval failed: {e}")
        raise HTTPException(status_code=500, detail="Approval failed")
    if not ok:
        raise HTTPException(status_code=404, detail="No pending approval with that id")
    return {"applied": True, "action_id": action_id}


@router.post("/automation/reject")
async def reject_certification(
    payload: Dict[str, Any],
    _admin: User = Depends(_require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Reject a pending certification action (config untouched)."""
    try:
        action_id = int(payload.get("action_id") or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="action_id is required")
    if not action_id:
        raise HTTPException(status_code=422, detail="action_id is required")
    try:
        from core import decision_automation as da

        ok = da.reject_action(db, action_id)
        db.commit()
    except Exception as e:
        logger.error(f"Rejection failed: {e}")
        raise HTTPException(status_code=500, detail="Rejection failed")
    if not ok:
        raise HTTPException(status_code=404, detail="No pending approval with that id")
    return {"applied": False, "action_id": action_id}
