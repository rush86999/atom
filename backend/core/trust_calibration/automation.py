"""Consent-gated automation loop for the trust calibration gateway (P3).

Mirrors core/fleet_orchestration/fleet_router_automation.py exactly:

  certify -> verdict(enable|revoke|collecting) -> consent mode dispatch
    off    : nothing recorded
    notify : record approval-state row + admin notification (cooldown)
    approve: queue approval-state row for the admin endpoints
    auto   : enable verdicts apply immediately; revocation is ALWAYS
             automatic when a previously-applied gate starts failing

The applied/revoked ledger drives resolved_trust_enforce() — the single
boolean future P3 consumers read. Nothing else in the app reads it yet, so
this scaffolding is dormant-safe: it automates the *decision bookkeeping*
without any consumer to relax.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_mode: Optional[str] = None
_interval_min: Optional[float] = None
_last_pass_monotonic: float = 0.0
_notified_keys: Dict[str, float] = {}


def _env_str(name: str, default: str) -> str:
    return os.getenv(name, default)


def automation_mode() -> str:
    global _mode
    if _mode is not None:
        return _mode
    raw = _env_str("ATOM_TRUST_CALIBRATION_AUTO_ENFORCE", "off").lower()
    return raw if raw in ("off", "notify", "approve", "auto") else "off"


def automation_interval_min() -> float:
    global _interval_min
    if _interval_min is not None:
        return _interval_min
    try:
        return float(_env_str("ATOM_TRUST_CALIBRATION_AUTO_INTERVAL_MIN", "60"))
    except ValueError:
        return 60.0


def set_automation_config(
    mode: Optional[str] = None, interval_min: Optional[float] = None
) -> Dict[str, Any]:
    global _mode, _interval_min
    if mode is not None:
        if mode not in ("off", "notify", "approve", "auto"):
            raise ValueError(f"invalid mode: {mode}")
        _mode = mode
    if interval_min is not None:
        _interval_min = max(float(interval_min), 1.0)
    return {"mode": automation_mode(), "interval_min": automation_interval_min()}


# ------------------------------------------------------------------ ledger


def _latest_action(db) -> Optional[Dict[str, Any]]:
    from core.models import TrustCalibrationAction

    row = (
        db.query(TrustCalibrationAction)
        .filter(TrustCalibrationAction.workload_key == "__global__")
        .order_by(TrustCalibrationAction.created_at.desc(), TrustCalibrationAction.id.desc())
        .first()
    )
    if not row:
        return None
    return {
        "id": row.id,
        "verdict": row.verdict,
        "state": row.state,
        "created_at": row.created_at,
    }


def resolved_trust_enforce(db=None) -> bool:
    """Single boolean future consumers read.

    Env hard-switch wins; otherwise the latest applied+enable action row
    authorizes relaxation. Failures degrade to False.
    """
    try:
        if _env_str("ATOM_TRUST_CALIBRATION_FORCE_ENFORCE", "false").lower() == "true":
            return True
        if db is None:
            return False
        latest = _latest_action(db)
        return bool(
            latest
            and latest["verdict"] == "enable"
            and latest["state"] == "applied"
        )
    except Exception as e:  # noqa: BLE001
        logger.debug(f"resolved_trust_enforce failed: {e}")
        return False


def _record_action(db, verdict: str, state: str, stats: Dict[str, Any]) -> str:
    from core.models import TrustCalibrationAction

    row = TrustCalibrationAction(
        workload_key="__global__",
        verdict=verdict,
        mode=automation_mode(),
        state=state,
        stats_json=stats,
    )
    db.add(row)
    db.commit()
    return row.id


def approve_action(db, action_id: str) -> bool:
    """Admin consents to a queued approval-row -> applied."""
    from core.models import TrustCalibrationAction

    row = db.query(TrustCalibrationAction).filter_by(id=action_id).first()
    if not row or row.state != "approval":
        return False
    row.state = "applied"
    db.commit()
    logger.info("Trust calibration action %s approved -> applied", action_id)
    return True


def reject_action(db, action_id: str) -> bool:
    from core.models import TrustCalibrationAction

    row = db.query(TrustCalibrationAction).filter_by(id=action_id).first()
    if not row or row.state != "approval":
        return False
    row.state = "rejected"
    db.commit()
    return True


# -------------------------------------------------------------- notifications


def _notify(title: str, message: str) -> None:
    try:
        import asyncio

        from core.notification_service import NotificationService

        svc = NotificationService(db_session=None)
        recipient = _admin_recipient()
        if not recipient:
            return
        coro = svc.send_notification(
            user_id=recipient, notification_type="trust_calibration_update",
            data={"title": title, "message": message},
        )
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            asyncio.run(coro)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"notify skipped: {e}")


def _admin_recipient() -> Optional[str]:
    try:
        from core.database import SessionLocal
        from core.models import User, UserRole

        with SessionLocal() as db:
            u = (
                db.query(User)
                .filter(User.role == UserRole.SUPER_ADMIN.value)
                .first()
            )
            return u.id if u else None
    except Exception:  # noqa: BLE001
        return None


def _notify_cooldown_active(key: str, hours: float = 24.0) -> bool:
    last = _notified_keys.get(key, 0.0)
    return (time.monotonic() - last) < hours * 3600


# ------------------------------------------------------------------ the pass


def run_automation_pass(db, force: bool = False) -> Dict[str, Any]:
    """One certification pass + consent-mode dispatch. Never raises."""
    global _last_pass_monotonic

    mode = automation_mode()
    interval = automation_interval_min()
    if (
        not force
        and mode != "auto"
        and (time.monotonic() - _last_pass_monotonic) < interval * 60
    ):
        return {"ran": False, "why": "interval"}

    _last_pass_monotonic = time.monotonic()

    if mode == "off":
        return {"ran": False, "why": "disabled"}

    from core.models import TrustCalibrationAction
    from core.trust_calibration.certify import ResolvedDecision, certify

    # Load resolved decisions (same join as /stats); missing tables
    # degrade to a clean not-ran result.
    try:
        from core.models import HITLAction, TrustCalibrationAssessment

        pairs = (
            db.query(TrustCalibrationAssessment, HITLAction.status)
            .join(HITLAction, TrustCalibrationAssessment.decision_ref == HITLAction.id)
            .filter(
                HITLAction.status.in_(["approved", "rejected"]),
                TrustCalibrationAssessment.decision_ref.isnot(None),
            )
            .order_by(TrustCalibrationAssessment.created_at.asc())
            .limit(2000)
            .all()
        )
        resolved = [
            ResolvedDecision(
                p_approve=float(a.p_approve),
                y=1 if status == "approved" else 0,
                decided_at=a.created_at,
                features_json=a.features_json
                or {"tool": [0.5, 0.5, 0.5], "ctx": [0.5]},
            )
            for a, status in pairs
        ]
    except Exception as e:
        return {"ran": False, "why": f"load failed: {type(e).__name__}"}

    cert = certify(resolved)
    stats = cert.to_dict()
    verdict = "enable" if cert.certified else "revoke"
    if cert.n_eval < 1 and "insufficient" in (cert.reasons[0] if cert.reasons else ""):
        verdict = "collecting"

    latest = _latest_action(db)
    previously_applied = bool(latest and latest["verdict"] == "enable"
                              and latest["state"] == "applied")

    if verdict == "collecting":
        if mode in ("notify", "approve") and not _notify_cooldown_active("collecting"):
            _notify(
                "Trust calibration collecting",
                f"{cert.n_train + cert.n_eval} decisions so far — certification "
                f"needs more resolved HITL history.",
            )
            _notified_keys["collecting"] = time.monotonic()
        return {"ran": True, "verdict": verdict, "stats": stats}

    if verdict == "enable":
        if previously_applied:
            return {"ran": True, "verdict": verdict, "stats": stats, "note": "already applied"}
        if mode == "auto":
            _record_action(db, "enable", "applied", stats)
            _notify("Trust gateway ENABLED (auto)",
                    "Certification passed — relaxation authorized automatically.")
            return {"ran": True, "verdict": verdict, "applied": True, "stats": stats}
        if mode == "approve":
            _record_action(db, "enable", "approval", stats)
            _notify("Trust gateway certified — approval queued",
                    "Approve via /api/v1/trust-calibration/approve/{action_id}.")
            return {"ran": True, "verdict": verdict, "queued": True, "stats": stats}
        # notify
        key = f"enable:{int(stats['brier_holdout'] * 1000)}"
        if not _notify_cooldown_active(key):
            _record_action(db, "enable", "approval", stats)
            _notify("Trust gateway certified",
                    "Certification passed — review and approve to relax Propose-Only.")
            _notified_keys[key] = time.monotonic()
        return {"ran": True, "verdict": verdict, "notified": True, "stats": stats}

    # verdict == revoke
    if previously_applied:
        _record_action(db, "revoke", "revoked", stats)
        _notify("Trust gateway REVOKED (automatic)",
                "Certification regressed — relaxation revoked automatically.")
        return {"ran": True, "verdict": "revoke", "revoked": True, "stats": stats}
    return {"ran": True, "verdict": "revoke", "stats": stats}
