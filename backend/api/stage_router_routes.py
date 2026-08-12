"""Stage Router Management API — automation control + approval queue.

Management surface for the consent-gated stage-router automation
(``core/llm/stage_router_automation.py``). Admins can:

- inspect the automation (mode, cadence, last run, pending approvals)
- trigger a certification pass on demand
- approve / reject pending per-workload certifications
- change the automation mode / interval at runtime (env is the durable source)

All mutating endpoints require an admin role. Read-only status is also
available publicly at ``/health/stage-router``.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, cast

from fastapi import APIRouter, Depends, HTTPException

from core.auth import get_current_user
from core.database import get_db
from core.models import User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/llm/stage-router", tags=["LLM Routing"])

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
async def stage_router_status() -> Dict[str, Any]:
    """Full stage-router status (phases + automation block). Read-only."""
    try:
        from core.llm.stage_router import stage_router_status as _status

        return cast(Dict[str, Any], _status())
    except Exception as e:
        logger.error(f"Stage router status failed: {e}")
        return {"phase": "error", "error": "internal"}


@router.get("/automation")
async def get_automation(
    _admin: User = Depends(_require_admin),
) -> Dict[str, Any]:
    """Automation config, last run, and the pending approval queue."""
    try:
        from core.llm.stage_router_automation import get_automation_status

        return cast(Dict[str, Any], get_automation_status())
    except Exception as e:
        logger.error(f"Automation status failed: {e}")
        raise HTTPException(status_code=500, detail="Automation status unavailable")


@router.post("/automation/config")
async def set_automation(
    payload: Dict[str, Any],
    _admin: User = Depends(_require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Change automation mode/interval at runtime (in-memory; env is durable).

    Payload: ``{"mode": "off|notify|approve|auto", "interval_min": 60}``
    """
    try:
        from core.llm.stage_router_automation import set_automation_config

        return cast(
            Dict[str, Any],
            set_automation_config(
                mode=payload.get("mode"), interval_min=payload.get("interval_min")
            ),
        )
    except Exception as e:
        logger.error(f"Automation config failed: {e}")
        raise HTTPException(status_code=500, detail="Automation config update failed")


@router.post("/automation/run-now")
async def run_automation_now(
    _admin: User = Depends(_require_admin),
) -> Dict[str, Any]:
    """Trigger an immediate certification pass."""
    try:
        from core.llm.stage_router_automation import run_auto_certification

        return cast(Dict[str, Any], run_auto_certification())
    except Exception as e:
        logger.error(f"Automation run failed: {e}")
        raise HTTPException(status_code=500, detail="Automation run failed")


@router.post("/automation/approve")
async def approve_certification(
    payload: Dict[str, Any],
    _admin: User = Depends(_require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Approve the pending certification for one agent (flips enforce on)."""
    agent_id = str(payload.get("agent_id") or "").strip()
    if not agent_id:
        raise HTTPException(status_code=422, detail="agent_id is required")
    try:
        from core.llm.stage_router_automation import apply_pending_decision

        result: Dict[str, Any] = apply_pending_decision(db, agent_id, approve=True)
        db.commit()
    except Exception as e:
        logger.error(f"Approval failed: {e}")
        raise HTTPException(status_code=500, detail="Approval failed")
    if not result.get("applied"):
        raise HTTPException(status_code=404, detail=result.get("reason", "not approved"))
    return result


@router.post("/automation/reject")
async def reject_certification(
    payload: Dict[str, Any],
    _admin: User = Depends(_require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Reject the pending certification for one agent (config untouched)."""
    agent_id = str(payload.get("agent_id") or "").strip()
    if not agent_id:
        raise HTTPException(status_code=422, detail="agent_id is required")
    try:
        from core.llm.stage_router_automation import apply_pending_decision

        result: Dict[str, Any] = apply_pending_decision(db, agent_id, approve=False)
        db.commit()
    except Exception as e:
        logger.error(f"Rejection failed: {e}")
        raise HTTPException(status_code=500, detail="Rejection failed")
    if result.get("applied"):
        raise HTTPException(status_code=409, detail="No pending approval to reject")
    return result
