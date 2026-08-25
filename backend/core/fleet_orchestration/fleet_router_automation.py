"""Fleet router automation — consent-gated pilot certification.

2026-08-21: fleet routing is ON in shadow mode. This module makes the leap
from shadow to force-enforce (pilot) *data-driven and consent-gated*, mirroring
``core/llm/stage_router_automation.py``:

- Calibration pass reads outcome-joined fleet audit rows (the incumbent
  Queen->ReAct baseline on fleet-eligible tasks) + recruitment health.
- Verdicts are single-arm and honest: ``enable`` = "baseline healthy +
  recruitment works" -> recommend the pilot switch; ``blocked`` when the
  recruitment machinery fails. ``revoke`` = the baseline regressed or
  recruitment collapsed -> revocation is ALWAYS automatic (fail-safe), in all
  non-off modes.
- Escalation requires consent: ``approve`` mode queues an approval action
  row; ``auto`` applies immediately; ``notify`` only pings admins.
- Enforcement override: the latest applied/revoked action row drives
  ``resolved_fleet_enforce()``; the env kill-switch
  ``ATOM_FLEET_ROUTING_FORCE_ENFORCE=true`` always wins over the override,
  and ``false`` env + no override = shadow.

Env knobs (all optional):
    ATOM_FLEET_ROUTER_AUTO_ENFORCE      off|notify|approve|auto  (default approve)
    ATOM_FLEET_ROUTER_AUTO_INTERVAL_MIN float minutes            (default 60)
    ATOM_FLEET_ROUTER_AUTO_MIN_ROWS     int                      (default 30)
    ATOM_FLEET_ROUTER_AUTO_SUCCESS_GAP  float baseline floor      (default 0.70)
    ATOM_FLEET_ROUTER_AUTO_NOTIFY_COOLDOWN_HOURS float           (default 24)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# --- Config (env-driven; in-memory runtime override via the admin API) -------

_VALID_MODES = ("off", "notify", "approve", "auto")


def _mode_default() -> str:
    mode = os.getenv("ATOM_FLEET_ROUTER_AUTO_ENFORCE", "approve").strip().lower()
    if mode not in _VALID_MODES:
        logger.warning("Invalid ATOM_FLEET_ROUTER_AUTO_ENFORCE=%r, falling back to approve", mode)
        return "approve"
    return mode


_mode: str = _mode_default()
_interval_min: float = _env_float("ATOM_FLEET_ROUTER_AUTO_INTERVAL_MIN", 60.0)

_last_run: Dict[str, Any] = {}
_last_notified: Dict[str, float] = {}
_automation_task: Optional[asyncio.Task] = None


def automation_mode() -> str:
    return _mode


def automation_interval_min() -> float:
    return _interval_min


def set_automation_config(mode: Optional[str] = None, interval_min: Optional[float] = None) -> Dict[str, Any]:
    """In-memory runtime override (env remains the durable source)."""
    global _mode, _interval_min
    if mode is not None:
        mode = str(mode).strip().lower()
        if mode not in _VALID_MODES:
            raise ValueError(f"mode must be one of {_VALID_MODES}")
        _mode = mode
    if interval_min is not None:
        interval_min = float(interval_min)
        if interval_min < 0.5:
            raise ValueError("interval_min must be >= 0.5")
        _interval_min = interval_min
    return {"mode": _mode, "interval_min": _interval_min}


# --- Stats access (imports are local to keep module import cheap) ------------

def _load_stats(db) -> Dict[str, Any]:
    from core.fleet_orchestration.fleet_routing_stats import (
        _aggregate_recruitment_health,
        _workload_stats,
    )

    return {
        "workloads": _workload_stats(db),
        "recruitment": _aggregate_recruitment_health(db),
    }


def _latest_action(db, workload_key: str = "__global__") -> Optional[Dict[str, Any]]:
    from core.models import FleetRouterAutomationAction

    row = (
        db.query(FleetRouterAutomationAction)
        .filter(FleetRouterAutomationAction.workload_key == workload_key)
        .order_by(FleetRouterAutomationAction.created_at.desc())
        .first()
    )
    if not row:
        return None
    return {
        "id": row.id,
        "workload_key": row.workload_key,
        "verdict": row.verdict,
        "mode": row.mode,
        "state": row.state,
        "stats_json": row.stats_json,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
    }


def resolved_fleet_enforce(db=None) -> bool:
    """Effective enforce state: env kill-switch always wins, else automation override.

    Called from the hot path once per fleet-eligible decision. The env
    ``ATOM_FLEET_ROUTING_FORCE_ENFORCE=true`` forces enforcement; a latest
    action row with ``state=applied, verdict=enable`` also enables it; a
    ``revoked``/``rejected``/``approval`` row does not. Failures degrade to
    shadow (fail-safe), never enforce.
    """
    ensure_automation_task()
    try:
        from core.fleet_routing_config import fleet_routing_force_enforce

        if fleet_routing_force_enforce():
            return True
    except Exception:
        return False

    try:
        from core.database import get_db_session

        owns = db is None
        session = db if not owns else None
        if owns:
            from core.database import SessionLocal

            session = SessionLocal()
        try:
            latest = _latest_action(session)
            if latest and latest["verdict"] == "enable" and latest["state"] == "applied":
                return True
        finally:
            if owns:
                try:
                    session.close()
                except Exception:
                    pass
    except Exception:
        pass
    return False


# --- Notification helpers ----------------------------------------------------

def _admin_recipient() -> Optional[str]:
    try:
        from core.database import SessionLocal
        from core.models import User

        with SessionLocal() as db:
            user = (
                db.query(User)
                # R82: UserRole enum VALUES are lowercase — the previous
                # uppercase literals matched nothing, so notifications were
                # silently dropped.
                .filter(User.role.in_(["super_admin", "owner", "admin", "workspace_admin"]))
                .order_by(User.created_at.asc())
                .first()
            )
            return user.id if user else None
    except Exception:
        return None


async def _notify(notification_type: str, title: str, message: str, action_url: str = "") -> None:
    try:
        from core.notification_service import NotificationService

        user_id = _admin_recipient()
        if not user_id:
            return
        data = {
            "title": title,
            "message": message,
            "workspace_id": "default",
            "tenant_id": "default",
        }
        if action_url:
            data["action_url"] = action_url
            data["action_label"] = "Manage in settings"
        await NotificationService().send_notification(
            user_id=user_id,
            notification_type=notification_type,
            data=data,
        )
    except Exception as e:
        logger.warning("Fleet router notification failed: %s", e)


def _spawn_notification(notification_type: str, title: str, message: str, action_url: str = "") -> None:
    async def _run() -> None:
        await _notify(notification_type, title, message, action_url)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_run())
        else:
            asyncio.run(_run())
    except Exception:
        try:
            asyncio.run(_run())
        except Exception:
            pass


def _notify_cooldown_active(key: str) -> bool:
    cooldown = _env_float("ATOM_FLEET_ROUTER_AUTO_NOTIFY_COOLDOWN_HOURS", 24.0) * 3600.0
    last = _last_notified.get(key)
    if last is None:
        return False
    return (time.monotonic() - last) < cooldown


def _mark_notified(key: str) -> None:
    _last_notified[key] = time.monotonic()


def _stats_signature(stats: Dict[str, Any]) -> str:
    return hashlib.sha1(
        json.dumps(stats, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]


def _record_action(db, verdict: str, state: str, stats: Dict[str, Any]) -> str:
    from core.models import FleetRouterAutomationAction

    row = FleetRouterAutomationAction(
        workload_key="__global__",
        verdict=verdict,
        mode=_mode,
        state=state,
        stats_json=stats,
    )
    db.add(row)
    db.flush()
    return row.id


# --- Verdict computation -----------------------------------------------------

def _certify_verdict(db) -> Dict[str, Any]:
    """Single-arm calibration verdict for the global fleet workload.

    Returns:
        {"verdict": "blocked"|"collecting"|"enable"|"revoke", "stats": {...},
         "why": str}
    """
    from core.fleet_orchestration.fleet_routing_stats import (
        BASELINE_SUCCESS_FLOOR,
        MIN_OUTCOME_ROWS,
        MIN_RECRUIT_ATTEMPTS,
        MIN_RECRUIT_SUCCESS_RATE,
        REVOKE_MIN_ROWS,
        REVOKE_SUCCESS_CEILING,
    )

    stats = _load_stats(db)
    workloads = stats["workloads"]
    recruit = stats["recruitment"]

    # Global aggregation: all outcome-joined rows across workloads (single-arm).
    n = sum(w["n"] for w in workloads.values())
    successes = sum(round(w["success_rate"] * w["n"]) for w in workloads.values())
    success_rate = round(successes / n, 3) if n else None

    recruit_rate = recruit["recruit_success_rate"]
    recruit_attempts = recruit["recruit_attempts"]

    agg = {
        "n": n,
        "success_rate": success_rate,
        "recruit_attempts": recruit_attempts,
        "recruit_success_rate": recruit_rate,
    }

    if recruit_attempts >= MIN_RECRUIT_ATTEMPTS and recruit_rate is not None and recruit_rate < MIN_RECRUIT_SUCCESS_RATE:
        return {
            "verdict": "blocked",
            "stats": agg,
            "why": (
                f"recruitment failure rate too high ({recruit_rate} success over "
                f"{recruit_attempts} attempts)"
            ),
        }

    if n >= REVOKE_MIN_ROWS and success_rate is not None and success_rate < REVOKE_SUCCESS_CEILING:
        return {
            "verdict": "revoke",
            "stats": agg,
            "why": f"baseline regression: incumbent success {success_rate} < {REVOKE_SUCCESS_CEILING} over {n} rows",
        }

    if n < MIN_OUTCOME_ROWS:
        return {
            "verdict": "collecting",
            "stats": agg,
            "why": f"{n} of {MIN_OUTCOME_ROWS} outcome-joined rows needed",
        }

    if success_rate is not None and success_rate < BASELINE_SUCCESS_FLOOR:
        return {
            "verdict": "collecting",
            "stats": agg,
            "why": f"baseline success {success_rate} below {BASELINE_SUCCESS_FLOOR}; collect more before piloting",
        }

    return {
        "verdict": "enable",
        "stats": agg,
        "why": (
            f"baseline healthy (success {success_rate} over {n} rows) + recruitment "
            f"healthy ({recruit_rate} over {recruit_attempts} attempts)"
        ),
    }


def _apply_enforce(db, certified: bool) -> None:
    from core.models import FleetRouterAutomationAction

    existing = (
        db.query(FleetRouterAutomationAction)
        .filter(
            FleetRouterAutomationAction.workload_key == "__global__",
            FleetRouterAutomationAction.state == "applied",
            FleetRouterAutomationAction.verdict == "enable",
        )
        .first()
    )
    if existing:
        return  # already applied and live
    row = FleetRouterAutomationAction(
        workload_key="__global__",
        verdict="enable",
        mode=_mode,
        state="applied",
        stats_json={},
    )
    row.decided_at = datetime.now(timezone.utc)
    db.add(row)


def _apply_revoke(db, stats: Dict[str, Any]) -> str:
    from core.models import FleetRouterAutomationAction

    latest = _latest_action(db)
    if latest and latest["verdict"] == "revoke" and latest["state"] == "revoked":
        return latest["id"]
    row = FleetRouterAutomationAction(
        workload_key="__global__",
        verdict="revoke",
        mode=_mode,
        state="revoked",
        stats_json=stats,
    )
    row.decided_at = datetime.now(timezone.utc)
    db.add(row)
    return row.id


def _pending_row(db) -> Optional[Dict[str, Any]]:
    from core.models import FleetRouterAutomationAction

    row = (
        db.query(FleetRouterAutomationAction)
        .filter(
            FleetRouterAutomationAction.workload_key == "__global__",
            FleetRouterAutomationAction.state == "approval",
        )
        .order_by(FleetRouterAutomationAction.created_at.desc())
        .first()
    )
    if not row:
        return None
    return {
        "id": row.id,
        "verdict": row.verdict,
        "mode": row.mode,
        "state": row.state,
        "stats": row.stats_json,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _rejected_unchanged(db, stats: Dict[str, Any]) -> bool:
    """Honor a user's 'no': if stats are unchanged since the last rejection, stay put."""
    from core.models import FleetRouterAutomationAction

    rejected = (
        db.query(FleetRouterAutomationAction)
        .filter(
            FleetRouterAutomationAction.workload_key == "__global__",
            FleetRouterAutomationAction.state == "rejected",
        )
        .order_by(FleetRouterAutomationAction.created_at.desc())
        .first()
    )
    if not rejected or not rejected.stats_json:
        return False
    return _stats_signature(rejected.stats_json) == _stats_signature(stats)


# --- Public API --------------------------------------------------------------

def certify_fleet(db) -> Dict[str, List[str]]:
    """One full calibration pass. Returns outcome buckets (ids)."""
    result: Dict[str, List[str]] = {
        "certified": [],
        "revoked": [],
        "queued": [],
        "notified": [],
        "kept": [],
        "blocked": [],
    }
    if _mode == "off":
        return result

    verdict = _certify_verdict(db)

    if verdict["verdict"] == "blocked":
        _record_action(db, "revoke", "revoked", verdict["stats"])
        result["revoked"].append("__global__")
        _spawn_notification(
            "fleet_router_revoked",
            "Fleet routing blocked: recruitment unhealthy",
            f"Fleet routing blocked: {verdict['why']}",
            "/api/v1/fleet/automation",
        )
        return result

    if verdict["verdict"] == "revoke":
        _record_action(db, "revoke", "revoked", verdict["stats"])
        result["revoked"].append("__global__")
        _spawn_notification(
            "fleet_router_revoked",
            "Fleet routing pilot revoked",
            f"Fleet routing pilot revoked automatically: {verdict['why']}",
            "/api/v1/fleet/automation",
        )
        return result

    if verdict["verdict"] == "collecting":
        result["kept"].append("__global__")
        return result

    # enable verdict
    if _mode == "auto":
        if _pending_row(db):
            result["kept"].append("__global__")
            return result
        _apply_enforce(db, certified=True)
        action_id = _record_action(db, "enable", "applied", verdict["stats"])
        result["certified"].append("__global__")
        _spawn_notification(
            "fleet_router_certified",
            "Fleet routing pilot enabled (auto)",
            f"Fleet routing force-enforce pilot enabled: {verdict['why']}",
            "/api/v1/fleet/automation",
        )
        return result

    if _mode == "approve":
        if _pending_row(db) or _rejected_unchanged(db, verdict["stats"]):
            result["kept"].append("__global__")
            return result
        _record_action(db, "enable", "approval", verdict["stats"])
        result["queued"].append("__global__")
        _spawn_notification(
            "approval_needed",
            "Fleet routing pilot awaiting approval",
            f"Fleet routing is ready to pilot force-enforce: {verdict['why']}",
            "/api/v1/fleet/automation",
        )
        return result

    # notify mode
    if not _notify_cooldown_active("ready"):
        _mark_notified("ready")
        _record_action(db, "enable", "approval", verdict["stats"])
        result["notified"].append("__global__")
        _spawn_notification(
            "fleet_router_ready",
            "Fleet routing ready to pilot",
            f"Fleet routing is ready to pilot force-enforce: {verdict['why']}",
            "/api/v1/fleet/automation",
        )
    else:
        result["kept"].append("__global__")
    return result


def run_auto_certification() -> Dict[str, Any]:
    """One automation pass with its own session; commits. Never raises."""
    if _mode == "off":
        _last_run.update({"enabled": False, "mode": "off"})
        return {"enabled": False, "mode": "off"}
    try:
        from core.database import get_db_session

        with get_db_session() as db:
            result = certify_fleet(db)
        _last_run.update(
            {
                "enabled": True,
                "mode": _mode,
                "ts": datetime.now(timezone.utc).isoformat(),
                **result,
            }
        )
        return {"enabled": True, "mode": _mode, **result}
    except Exception as e:
        logger.warning("Fleet router automation pass failed: %s", e)
        _last_run.update({"enabled": True, "mode": _mode, "error": "pass failed"})
        return {"enabled": True, "mode": _mode, "error": "pass failed"}


def pending_approvals(db) -> List[Dict[str, Any]]:
    pending = _pending_row(db)
    return [pending] if pending else []


def apply_pending_decision(db, approve: bool) -> Dict[str, Any]:
    """Approve/reject the queued pilot recommendation. Returns the action dict."""
    from core.models import FleetRouterAutomationAction

    pending = (
        db.query(FleetRouterAutomationAction)
        .filter(
            FleetRouterAutomationAction.workload_key == "__global__",
            FleetRouterAutomationAction.state == "approval",
        )
        .order_by(FleetRouterAutomationAction.created_at.desc())
        .first()
    )
    if not pending:
        return {"applied": False, "reason": "no pending approval"}

    if approve:
        pending.state = "applied"
        pending.decided_at = datetime.now(timezone.utc)
        db.commit()
        return {"applied": True, "action_id": pending.id, "verdict": "enable", "state": "applied"}
    pending.state = "rejected"
    pending.decided_at = datetime.now(timezone.utc)
    db.commit()
    return {"applied": False, "action_id": pending.id, "state": "rejected"}


def get_automation_status() -> Dict[str, Any]:
    """Operator-facing status: mode, interval, pending approvals, last run."""
    try:
        from core.database import get_db_session

        with get_db_session() as db:
            pending = pending_approvals(db)
        return {
            "enabled": _mode != "off",
            "mode": _mode,
            "interval_min": _interval_min,
            "pending_approvals": pending,
            "last_run": _last_run,
        }
    except Exception:
        return {
            "enabled": _mode != "off",
            "mode": _mode,
            "interval_min": _interval_min,
            "pending_approvals": [],
            "last_run": _last_run,
        }


async def fleet_router_automation_loop() -> None:
    while True:
        await asyncio.sleep(max(_interval_min, 0.5) * 60)
        try:
            run_auto_certification()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("Fleet router automation loop iteration failed: %s", e)


def ensure_automation_task() -> None:
    """Lazy-start the automation loop from the hot path (mirrors stage router)."""
    global _automation_task
    if _automation_task is not None or _mode == "off":
        return
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            _automation_task = loop.create_task(fleet_router_automation_loop())
    except Exception:
        pass
