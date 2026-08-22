"""Trust Calibration routes (P0 spike) — admin-gated, shadow-only.

GET /api/v1/trust-calibration/assess?action_type=&platform=&agent_id=
GET /api/v1/trust-calibration/stats

Both are read-only inference over already-recorded human decisions. When
ATOM_TRUST_CALIBRATION_ENABLED is false (default) the surface answers 503 —
the gateway never mutates any decision path in P0.
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



def _calibration_metrics(db: Session, limit: int = 500) -> Dict[str, Any]:
    """P1 outcome join: assessments x HITLAction.status -> live shadow quality.

    Brier over resolved decisions, 10-bin ECE, and a recommendation-x-outcome
    matrix. Expired HITL actions are excluded (no ground truth).
    """
    from core.models import HITLAction, TrustCalibrationAssessment

    rows = (
        db.query(TrustCalibrationAssessment)
        .order_by(TrustCalibrationAssessment.created_at.desc())
        .limit(limit)
        .all()
    )
    refs = [r.decision_ref for r in rows if r.decision_ref]
    status_by_ref: Dict[str, str] = {}
    if refs:
        try:
            hrows = db.query(HITLAction).filter(HITLAction.id.in_(refs)).all()
            status_by_ref = {h.id: h.status for h in hrows}
        except Exception as e:  # noqa: BLE001
            logger.debug(f"outcome join failed: {e}")

    brier_sum = 0.0
    resolved = 0
    bins = [[] for _ in range(10)]
    matrix: Dict[str, Dict[str, int]] = {}
    pending = 0
    for r in rows:
        st = status_by_ref.get(r.decision_ref) if r.decision_ref else None
        if st is None:
            continue
        y = {"approved": 1.0, "rejected": 0.0}.get((st or "").lower())
        if y is None:
            continue  # expired / pending / unknown
        y01 = int(y)
        brier_sum += (float(r.p_approve) - y01) ** 2
        resolved += 1
        b = min(int(float(r.p_approve) * 10), 9)
        bins[b].append(y01)
        rec = r.recommendation or "unknown"
        matrix.setdefault(rec, {"approved": 0, "rejected": 0})
        matrix[rec]["approved" if y01 else "rejected"] += 1

    ece = 0.0
    for b in bins:
        if b:
            conf = sum(b) / len(b)
            ece += len(b) / max(sum(len(x) for x in bins), 1) * abs(conf - (sum(b) / len(b)))
    # NOTE: bin confidence == observed rate for binary labels; keep the
    # standard |mean_p - freq| form using mean p per bin instead:
    p_sums = [0.0] * 10
    counts = [0] * 10
    for r in rows:
        st = status_by_ref.get(r.decision_ref) if r.decision_ref else None
        if st not in ("approved", "rejected"):
            continue
        idx = min(int(float(r.p_approve) * 10), 9)
        counts[idx] += 1
        p_sums[idx] += float(r.p_approve)
    ece = 0.0
    total_resolved = sum(counts)
    for i in range(10):
        if counts[i]:
            mean_p = p_sums[i] / counts[i]
            freq = sum(bins[i]) / counts[i]
            ece += (counts[i] / total_resolved) * abs(mean_p - freq)

    return {
        "assessments_total": len(rows),
        "resolved": resolved,
        "pending": len(rows) - resolved,
        "brier": round(brier_sum / resolved, 6) if resolved else None,
        "ece_10bin": round(ece, 6) if resolved else None,
        "recommendation_outcome_matrix": matrix,
    }


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
        calibration = _calibration_metrics(db)

        return {
            "enabled": True,
            "shadow_only": True,
            "observations": {
                "total": len(obs),
                "by_source": by_source,
                "approved": approved,
                "rejected": rejected,
            },
            "calibration": calibration,
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


# ============================================================================
# P3 consent-gated automation (mirrors fleet/stage router management)
# ============================================================================


@router.get("/automation")
async def get_automation(
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    if not _flag_on():
        raise HTTPException(status_code=503, detail="Trust calibration disabled")
    from core.trust_calibration import automation

    latest = automation._latest_action(db)
    return {
        "mode": automation.automation_mode(),
        "interval_min": automation.automation_interval_min(),
        "resolved_enforce": automation.resolved_trust_enforce(db),
        "latest_action": (
            {k: str(v) for k, v in latest.items()} if latest else None
        ),
    }


@router.post("/automation")
async def set_automation(
    mode: Optional[str] = Query(None),
    interval_min: Optional[float] = Query(None),
    _admin: User = Depends(_require_admin),
):
    if not _flag_on():
        raise HTTPException(status_code=503, detail="Trust calibration disabled")
    from core.trust_calibration import automation

    try:
        cfg = automation.set_automation_config(mode=mode, interval_min=interval_min)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return cfg


@router.post("/run-now")
async def run_now(
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    if not _flag_on():
        raise HTTPException(status_code=503, detail="Trust calibration disabled")
    from core.trust_calibration import automation

    return automation.run_automation_pass(db, force=True)


@router.post("/approve/{action_id}")
async def approve_queued(
    action_id: str,
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    if not _flag_on():
        raise HTTPException(status_code=503, detail="Trust calibration disabled")
    from core.trust_calibration import automation

    if automation.approve_action(db, action_id):
        return {"approved": True, "action_id": action_id}
    raise HTTPException(status_code=404, detail="Queued approval not found")


@router.post("/reject/{action_id}")
async def reject_queued(
    action_id: str,
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    if not _flag_on():
        raise HTTPException(status_code=503, detail="Trust calibration disabled")
    from core.trust_calibration import automation

    if automation.reject_action(db, action_id):
        return {"rejected": True, "action_id": action_id}
    raise HTTPException(status_code=404, detail="Queued approval not found")
