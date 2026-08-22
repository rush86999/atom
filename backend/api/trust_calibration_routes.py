"""Trust Calibration routes (P0 spike) — admin-gated, shadow-only.

GET /api/v1/trust-calibration/assess?action_type=&platform=&agent_id=
GET /api/v1/trust-calibration/stats

Both are read-only inference over already-recorded human decisions. When
ATOM_TRUST_CALIBRATION_ENABLED is false (default) the surface answers 503 —
the gateway never mutates any decision path in P0.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.auth import User, get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import UserRole

logger = logging.getLogger(__name__)

router = BaseAPIRouter(
    prefix="/api/v1/trust-calibration", tags=["Trust Calibration"]
)

_ADMIN_ROLES = [
    UserRole.WORKSPACE_ADMIN.value,
    UserRole.SUPER_ADMIN.value,
]


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user


def _flag_on() -> bool:
    import os

    return os.getenv("ATOM_TRUST_CALIBRATION_ENABLED", "false").lower() == "true"


def _gateway(db: Session):
    from core.trust_calibration.gateway import TrustCalibrationGateway

    return TrustCalibrationGateway(db=db)


@router.get("/assess")
async def assess(
    action_type: str = Query(..., description="Action/tool name to assess"),
    platform: str = Query("internal"),
    agent_id: Optional[str] = Query(None),
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Three-tier recommendation (allow/ask/block) for a proposed action."""
    if not _flag_on():
        raise HTTPException(status_code=503, detail="Trust calibration disabled")
    try:
        gw = _gateway(db)
        return gw.assess(
            action_type=action_type, platform=platform, agent_id=agent_id
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"trust calibration assess failed: {e}")
        raise HTTPException(status_code=500, detail="Assessment failed")


@router.get("/stats")
async def stats(
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Posterior health: observation counts by source/outcome + knobs."""
    if not _flag_on():
        raise HTTPException(status_code=503, detail="Trust calibration disabled")
    try:
        from core.trust_calibration.service import load_decisions

        gw = _gateway(db)
        obs = load_decisions(db, limit=gw.max_obs)
        by_source = {"hitl": 0, "proposal": 0}
        approved = rejected = 0
        for o in obs:
            by_source[o.source] = by_source.get(o.source, 0) + 1
            if o.y == 1:
                approved += 1
            else:
                rejected += 1
        return {
            "enabled": True,
            "shadow_only": True,
            "observations": {
                "total": len(obs),
                "by_source": by_source,
                "approved": approved,
                "rejected": rejected,
            },
            "kernel": {
                "half_life_days": gw.half_life_days,
                "max_obs": gw.max_obs,
            },
            "thresholds": {
                "tau_low": gw.tau_low,
                "tau_uncertain": gw.tau_uncertain,
                "min_observations": gw.min_observations,
            },
        }
    except Exception as e:  # noqa: BLE001
        logger.error(f"trust calibration stats failed: {e}")
        raise HTTPException(status_code=500, detail="Stats failed")
