"""Learning-router management API — self-activation status + the numbers behind it.

The learning router (``core/llm/learning_router_registry.py``,
``core/learning_llm_router.py``) is self-activating by default:
``ATOM_LEARNING_ROUTER=auto`` keeps static BPC ordering until the verdict
history is thick enough to re-rank, then flips itself on — and falls back if
that evidence ages out. That is a DATA question, and it needs to be answerable
from the UI: on a fresh install the setting reads ``auto`` while doing nothing,
and the only trace of the flip was a log line.

- ``GET /status`` — mode, whether re-ranking is live, and the counters
  (observations in the window, models with enough observations) measured against
  the thresholds, plus a human-readable reason. Read-only, admin-gated.

Self-activation needs no consent click (it is the default and fail-safe: the
fallback is plain BPC ordering). Manual overrides remain authoritative — setting
the mode to ``true``/``false`` is respected and never re-flipped by automation.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from core.auth import get_current_user
from core.models import User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/llm/learning-router", tags=["LLM Routing"])

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


@router.get("/status")
async def learning_router_status(
    _admin: User = Depends(_require_admin),
) -> Dict[str, Any]:
    """Learning-router mode + self-activation readiness (read-only).

    Never raises on a metrics failure: the report degrades to a reason string,
    because a diagnostics endpoint must not become a new failure mode.
    """
    try:
        from core.llm.learning_router_registry import readiness_report

        report = readiness_report()
    except Exception as e:  # noqa: BLE001
        logger.error(f"Learning-router status unavailable: {e}")
        raise HTTPException(status_code=500, detail="Learning-router status unavailable")

    try:
        from core.llm.learning_router_registry import ema_router_enabled

        report["ema_term_enabled"] = ema_router_enabled()
    except Exception:  # noqa: BLE001
        report["ema_term_enabled"] = None

    return {"success": True, "data": report}
