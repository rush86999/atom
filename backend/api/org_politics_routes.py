"""Org-Politics Management API — automation control + approval queue.

Management surface for the consent-gated org-politics lifecycle automation
(``core/org_politics_automation.py``, AGENT_ORG_POLITICS_PLAN.md). Admins can:

- inspect flag states, the readiness verdicts, and the pending approvals
- trigger a certification pass on demand (telemetry + alignment sweep)
- approve / reject pending escalations for P2/P3/P5 flags
- change the automation mode / interval at runtime (env is the durable source)

All mutating endpoints require an admin role. Read-only health is available
at ``/health/org-politics``.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, cast

from fastapi import APIRouter, Depends, HTTPException

from core.auth import get_current_user
from core.database import get_db
from core.models import User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/org-politics", tags=["Org Politics"])

_ADMIN_ROLES = (
    UserRole.SUPER_ADMIN.value,
    UserRole.OWNER.value,
    UserRole.ADMIN.value,
    UserRole.WORKSPACE_ADMIN.value,
)


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Admin gate (super_admin/owner/admin/workspace_admin)."""
    role = getattr(current_user, "role", None)
    if role not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user


@router.get("/automation")
async def get_automation(
    _admin: User = Depends(_require_admin),
) -> Dict[str, Any]:
    """Automation config, per-flag states, last run, pending approvals."""
    try:
        from core.org_politics_automation import get_automation_status

        return cast(Dict[str, Any], get_automation_status())
    except Exception as e:
        logger.error(f"Org-politics status failed: {e}")
        raise HTTPException(status_code=500, detail="Status unavailable")


@router.post("/automation/config")
async def set_automation(
    payload: Dict[str, Any],
    _admin: User = Depends(_require_admin),
) -> Dict[str, Any]:
    """Change automation mode/interval at runtime.

    Payload: ``{"mode": "off|notify|approve|auto", "interval_min": 1440}``
    """
    try:
        from core.org_politics_automation import set_automation_config

        return cast(
            Dict[str, Any],
            set_automation_config(
                mode=payload.get("mode"),
                interval_min=payload.get("interval_min"),
            ),
        )
    except Exception as e:
        logger.error(f"Automation config failed: {e}")
        raise HTTPException(status_code=500, detail="Config update failed")


@router.post("/automation/run-now")
async def run_now(
    _admin: User = Depends(_require_admin),
) -> Dict[str, Any]:
    """Trigger an immediate certification pass (revocation included)."""
    try:
        from core.org_politics_automation import (
            ensure_automation_task,
            run_auto_certification,
        )

        result = cast(Dict[str, Any], run_auto_certification())
        ensure_automation_task()
        return result
    except Exception as e:
        logger.error(f"Org-politics run failed: {e}")
        raise HTTPException(status_code=500, detail="Run failed")


def _apply_decision(db: Any, payload: Dict[str, Any], approve: bool) -> Dict[str, Any]:
    flag_key = str(payload.get("flag_key") or "").strip()
    if not flag_key:
        raise HTTPException(status_code=422, detail="flag_key is required")
    try:
        from core.org_politics_automation import apply_pending_decision

        return cast(
            Dict[str, Any], apply_pending_decision(db, flag_key, approve=approve)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Decision failed: {e}")
        raise HTTPException(status_code=500, detail="Decision failed")


@router.post("/automation/approve")
async def approve(
    payload: Dict[str, Any],
    _admin: User = Depends(_require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Approve the pending escalation for one flag (flips it on)."""
    result = _apply_decision(db, payload, approve=True)
    if result.get("state") != "applied":
        raise HTTPException(
            status_code=404, detail=result.get("state", "not approved")
        )
    return result


@router.post("/automation/reject")
async def reject(
    payload: Dict[str, Any],
    _admin: User = Depends(_require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Reject the pending escalation for one flag (stays off)."""
    result = _apply_decision(db, payload, approve=False)
    if result.get("state") not in ("rejected", "not_found"):
        raise HTTPException(status_code=500, detail="Rejection failed")
    return result


@router.post("/revoke")
async def revoke_flag(
    payload: Dict[str, Any],
    _admin: User = Depends(_require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Manually revoke one flag (same fail-safe path automation uses)."""
    flag_key = str(payload.get("flag_key") or "").strip()
    if not flag_key:
        raise HTTPException(status_code=422, detail="flag_key is required")
    try:
        from core.org_politics_automation import _set_flag_state

        _set_flag_state(db, flag_key, "revoke", "revoked", {"reason": "manual"})
        return {"flag_key": flag_key, "state": "revoked"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manual revocation failed: {e}")
        raise HTTPException(status_code=500, detail="Revocation failed")
