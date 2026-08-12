"""Automated per-workload stage-router certification — with consent + notification.

The stage router's shadow/calibration math (see ``core/llm/stage_router.py``
and ``scripts/calibrate_stage_router.py``) answers *when* a workload is ready
for enforcement. This module automates the flip — but keeps a human in the
loop for anything that changes live traffic:

Modes (``ATOM_STAGE_ROUTER_AUTO_ENFORCE``):
- ``off``      — automation disabled; manual operation only.
- ``notify``   — computes verdicts and notifies the admin; never writes config.
- ``approve``  — (default) queues an approval action + notifies; config flips
                only after the user approves via the management API.
- ``auto``     — applies immediately, then notifies.

Symmetric safety rule: **escalation requires consent, revocation does not**.
A workload whose capable arm starts regressing is automatically flipped back
to shadow (in every non-``off`` mode) and the admin is notified — fail-safe
by design. Every action is persisted in ``stage_router_automation_actions``
(verdict, mode, state, stats snapshot) so the management surface
(``api/stage_router_routes.py``) and ``GET /health/stage-router`` can show
what automation did and why.

Flags:
- ``ATOM_STAGE_ROUTER_AUTO_ENFORCE`` (default ``approve``): off|notify|approve|auto.
- ``ATOM_STAGE_ROUTER_AUTO_INTERVAL_MIN`` (default ``60``): certification cadence.
- ``ATOM_STAGE_ROUTER_AUTO_SUCCESS_GAP`` (default ``0.03``): capable-arm success
  advantage required to certify.
- ``ATOM_STAGE_ROUTER_AUTO_MAX_COST_RATIO`` (default ``8.0``): max
  capable/efficient cost ratio for certification.
- ``ATOM_STAGE_ROUTER_AUTO_REVOKE_GAP`` (default ``0.02``): capable-arm success
  deficit that triggers automatic revocation.

Never raises: any failure is logged and the loop continues.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.llm.stage_router import CAPABLE, EFFICIENT, MIN_OUTCOME_ROWS_PER_ARM

logger = logging.getLogger(__name__)

# ── Configuration (env defaults; runtime overrides via set_automation_config) ─
_MODE = os.getenv("ATOM_STAGE_ROUTER_AUTO_ENFORCE", "approve").lower()
if _MODE not in ("off", "notify", "approve", "auto"):
    logger.warning(f"Invalid ATOM_STAGE_ROUTER_AUTO_ENFORCE '{_MODE}', using 'approve'")
    _MODE = "approve"
_INTERVAL_MIN = float(os.getenv("ATOM_STAGE_ROUTER_AUTO_INTERVAL_MIN", "60"))
_SUCCESS_GAP = float(os.getenv("ATOM_STAGE_ROUTER_AUTO_SUCCESS_GAP", "0.03"))
_MAX_COST_RATIO = float(os.getenv("ATOM_STAGE_ROUTER_AUTO_MAX_COST_RATIO", "8.0"))
_REVOKE_GAP = float(os.getenv("ATOM_STAGE_ROUTER_AUTO_REVOKE_GAP", "0.02"))
_REVOKE_MIN_ROWS = 20
_NOTIFY_COOLDOWN_HOURS = float(
    os.getenv("ATOM_STAGE_ROUTER_AUTO_NOTIFY_COOLDOWN_HOURS", "24")
)

_last_run: Dict[str, Any] = {}
_automation_task: Optional[asyncio.Task] = None
# Per-agent last-notification timestamps (monotonic) — dedupes the ``notify``
# mode so a workload that stays "ready" doesn't ping the admin every pass.
_last_notified: Dict[str, float] = {}


def automation_mode() -> str:
    return _MODE


def automation_interval_min() -> float:
    return _INTERVAL_MIN


def set_automation_config(
    mode: Optional[str] = None, interval_min: Optional[float] = None
) -> Dict[str, Any]:
    """Runtime override of mode/interval (in-memory; env is the durable source).

    Returns the effective config. Used by the management API so operators can
    tune the automation without restarting.
    """
    global _MODE, _INTERVAL_MIN
    if mode is not None:
        lowered = mode.lower()
        if lowered in ("off", "notify", "approve", "auto"):
            _MODE = lowered
        else:
            logger.warning(f"Ignoring invalid mode '{mode}'")
    if interval_min is not None and interval_min > 0:
        _INTERVAL_MIN = float(interval_min)
    return {"mode": _MODE, "interval_min": _INTERVAL_MIN}


# ── Statistics + verdict ────────────────────────────────────────────────────


def _workload_stats(db: Any) -> Dict[str, Dict[str, Dict[str, float]]]:
    """Per-workload outcome-joined arm stats: {agent_id: {arm: {n, success_rate, avg_cost}}}."""
    from sqlalchemy import Integer, func

    from core.models import StageRouterAudit

    counts: Dict[str, Dict[str, Dict[str, float]]] = {}
    rows = (
        db.query(
            StageRouterAudit.agent_id,
            StageRouterAudit.applied_group,
            func.count(),
            func.sum(StageRouterAudit.success.cast(Integer)),
            func.avg(StageRouterAudit.actual_cost),
        )
        .filter(StageRouterAudit.success.isnot(None))
        .group_by(StageRouterAudit.agent_id, StageRouterAudit.applied_group)
        .all()
    )
    for agent_id, group, n, successes, avg_cost in rows:
        if group not in (EFFICIENT, CAPABLE) or agent_id is None:
            continue
        stats = counts.setdefault(agent_id, {EFFICIENT: {}, CAPABLE: {}})[group]
        stats["n"] = int(n)
        stats["success_rate"] = (float(successes) / int(n)) if n else 0.0
        stats["avg_cost"] = float(avg_cost) if avg_cost is not None else 0.0
    return counts


def _verdict(stats: Dict[str, Dict[str, float]]) -> str:
    """Classify one workload: certify | revoke | keep-shadow.

    Certify: both arms observed at the floor AND the capable arm's success
    advantage clears ``_SUCCESS_GAP`` at an acceptable cost ratio.
    Revoke: both arms observed at a smaller floor AND the capable arm is
    regressing by ``_REVOKE_GAP`` or more.
    """
    efficient = stats.get(EFFICIENT, {})
    capable = stats.get(CAPABLE, {})
    e_n = int(efficient.get("n", 0))
    c_n = int(capable.get("n", 0))
    if c_n < MIN_OUTCOME_ROWS_PER_ARM or e_n < MIN_OUTCOME_ROWS_PER_ARM:
        return "keep-shadow"
    gain = capable.get("success_rate", 0.0) - efficient.get("success_rate", 0.0)
    if gain >= _SUCCESS_GAP:
        e_cost = efficient.get("avg_cost", 0.0)
        c_cost = capable.get("avg_cost", 0.0)
        cost_ratio = (c_cost / e_cost) if e_cost > 0 else None
        if cost_ratio is None or cost_ratio <= _MAX_COST_RATIO:
            return "certify"
        logger.info(
            f"Workload certify blocked by cost ratio {cost_ratio:.1f} > "
            f"{_MAX_COST_RATIO} (capable +{gain:.1%})"
        )
        return "keep-shadow"
    if e_n >= _REVOKE_MIN_ROWS and c_n >= _REVOKE_MIN_ROWS and gain <= -_REVOKE_GAP:
        return "revoke"
    return "keep-shadow"


# ── Config + notification helpers ───────────────────────────────────────────


def _apply_enforce(
    agent: Any, enforce: bool, *, certified: bool = False, revoked: bool = False
) -> None:
    """Write ``configuration["stage_routing"]["enforce"]`` on an AgentRegistry row."""
    config = dict(agent.configuration or {})
    block = dict(config.get("stage_routing") or {})
    block["enforce"] = enforce
    now = datetime.now(timezone.utc).isoformat()
    if certified:
        block["auto_certified"] = True
        block["certified_at"] = now
        block.pop("auto_revoked", None)
        block.pop("revoked_at", None)
    if revoked:
        block["auto_revoked"] = True
        block["revoked_at"] = now
    config["stage_routing"] = block
    agent.configuration = config


def _admin_recipient() -> Optional[str]:
    """First admin user id (SUPER_ADMIN/OWNER/ADMIN/WORKSPACE_ADMIN), or None."""
    try:
        from core.database import SessionLocal
        from core.models import User, UserRole

        db = SessionLocal()
        try:
            admin_roles = (
                UserRole.SUPER_ADMIN.value,
                UserRole.OWNER.value,
                UserRole.ADMIN.value,
                UserRole.WORKSPACE_ADMIN.value,
            )
            user = db.query(User).filter(User.role.in_(admin_roles)).first()
            return str(user.id) if user else None
        finally:
            db.close()
    except Exception:
        return None


async def _notify(
    notification_type: str,
    title: str,
    message: str,
    action_url: str = "",
) -> None:
    """Persist an in-app notification for the admin (own session, email for
    high-priority types). Never raises — notification failure must not affect
    certification.
    """
    try:
        from core.notification_service import NotificationService

        user_id = _admin_recipient()
        if not user_id:
            logger.info(f"[stage-router] {title}: {message} (no admin recipient)")
            return
        data: Dict[str, Any] = {
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
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"Stage-router notification failed (non-fatal): {e}")


def _spawn_notification(
    notification_type: str,
    title: str,
    message: str,
    action_url: str = "",
) -> None:
    """Fire a notification without blocking the certification pass.

    In a running event loop (server) the notification runs as a background
    task; in a sync/CLI context it runs inline via a throwaway loop.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_notify(notification_type, title, message, action_url))
            return
    except Exception:
        pass
    try:
        asyncio.run(_notify(notification_type, title, message, action_url))
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"Stage-router notification failed (non-fatal): {e}")


def _record_action(db: Any, agent_id: str, verdict: str, state: str, stats: Dict[str, Any]) -> None:
    """Persist one automation action row (approval queue + audit trail)."""
    try:
        from core.models import StageRouterAutomationAction

        db.add(
            StageRouterAutomationAction(
                agent_id=agent_id,
                verdict=verdict,
                mode=_MODE,
                state=state,
                stats_json=stats,
                created_at=datetime.now(timezone.utc),
            )
        )
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"Stage-router action persist failed (non-fatal): {e}")


def _agent_query(db: Any, agent_id: str) -> Any:
    """AgentRegistry lookup helper (keeps the query chain single-sourced)."""
    from core.models import AgentRegistry

    return db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()


def _latest_action(db: Any, agent_id: str) -> Any:
    """Most recent automation action for an agent, or None."""
    try:
        from core.models import StageRouterAutomationAction

        return (
            db.query(StageRouterAutomationAction)
            .filter(StageRouterAutomationAction.agent_id == agent_id)
            .order_by(StageRouterAutomationAction.created_at.desc())
            .first()
        )
    except Exception:  # pragma: no cover - defensive
        return None


def _stats_signature(stats: Dict[str, Any]) -> str:
    """Deterministic snapshot hash of the arm stats — for change detection."""
    import hashlib
    import json as _json

    return hashlib.sha1(
        _json.dumps(stats, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]


def _notify_cooldown_active(agent_id: str) -> bool:
    """True when the admin was already notified for this agent recently."""
    import time as _time

    last = _last_notified.get(agent_id)
    if last is None:
        return False
    return (_time.monotonic() - last) < _NOTIFY_COOLDOWN_HOURS * 3600


def _mark_notified(agent_id: str) -> None:
    import time as _time

    _last_notified[agent_id] = _time.monotonic()


# ── Certification pass ──────────────────────────────────────────────────────


def _apply_certify(db: Any, agent: Any, stats: Dict[str, Any]) -> None:
    _apply_enforce(agent, True, certified=True)
    _record_action(db, agent.id, "certify", "applied", stats)
    _spawn_notification(
        "stage_router_certified",
        "Stage routing enabled for an agent",
        f"Agent '{agent.id}' passed calibration and stage routing is now live "
        "for it (per-agent, from its configuration).",
    )


def _queue_approval(db: Any, agent: Any, stats: Dict[str, Any]) -> None:
    _record_action(db, agent.id, "certify", "approval", stats)
    _spawn_notification(
        "approval_needed",
        "Stage routing calibration complete — approval needed",
        f"Agent '{agent.id}' now has enough outcome-joined turns in both arms "
        "and calibration recommends live enforcement. Approve or reject in "
        "the LLM routing settings.",
        action_url="/api/v1/llm/stage-router/automation",
    )


def _notify_ready(db: Any, agent: Any, stats: Dict[str, Any]) -> None:
    _spawn_notification(
        "stage_router_ready",
        "Agent ready for stage routing",
        f"Agent '{agent.id}' passed calibration (capable arm "
        f"+{stats[CAPABLE]['success_rate'] - stats[EFFICIENT]['success_rate']:.1%} "
        "success). Enable it via its configuration['stage_routing'] or "
        "ATOM_STAGE_ROUTER_AUTO_ENFORCE=approve.",
    )


def _apply_revoke(db: Any, agent: Any, stats: Dict[str, Any]) -> None:
    _apply_enforce(agent, False, revoked=True)
    _record_action(db, agent.id, "revoke", "revoked", stats)
    _spawn_notification(
        "stage_router_revoked",
        "Stage routing rolled back for an agent",
        f"Agent '{agent.id}' regressed under stage routing (capable arm "
        f"{stats[CAPABLE]['success_rate'] - stats[EFFICIENT]['success_rate']:.1%} "
        "vs efficient) — enforcement was automatically disabled.",
    )


def certify_workloads(db: Any) -> Dict[str, List[str]]:
    """Run one certification pass over every workload with outcome data.

    Behavior by mode:
      - off: no-op (caller guards, but kept safe here too).
      - notify: notifies the admin about certify/revoke verdicts; no writes.
      - approve: certify verdicts queue an approval row + notification; the
        config flips only when the user approves via the management API.
        revoke verdicts apply immediately (fail-safe).
      - auto: both certify and revoke apply immediately; notifications follow.
    """
    result: Dict[str, List[str]] = {
        "certified": [], "revoked": [], "queued": [], "notified": [], "kept": []
    }
    if _MODE == "off":
        return result
    for agent_id, stats in _workload_stats(db).items():
        verdict = _verdict(stats)
        agent = _agent_query(db, agent_id)
        if agent is None:
            result["kept"].append(agent_id)
            continue
        block = dict((agent.configuration or {}).get("stage_routing") or {})
        latest = _latest_action(db, agent_id)

        # ── Notification overload + intent-respect guards ───────────────────
        # Each verdict fires AT MOST ONCE per state transition:
        #   approve: a pending-approval row IS the dedupe (queued once, waits);
        #            a REJECTED row also suppresses re-queueing until the arm
        #            stats actually change (the user's no is respected)
        #   auto:    an "applied" certify action + live config is the dedupe;
        #            a manual "enforce": false is NEVER overwritten (opt-out)
        #   notify:  in-memory per-agent cooldown (default 24h)
        #   revoke:  an existing "revoked" action is the dedupe
        already_waiting = latest is not None and latest.verdict == "certify" and latest.state == "approval"
        already_applied = (
            latest is not None and latest.verdict == "certify" and latest.state == "applied"
        )
        already_revoked = latest is not None and latest.state == "revoked"
        rejected_unchanged = (
            latest is not None
            and latest.state == "rejected"
            and latest.stats_json is not None
            and _stats_signature(latest.stats_json) == _stats_signature(stats)
        )
        manual_opt_out = (
            block.get("enforce") is False and not block.get("auto_revoked")
        )

        if verdict == "certify":
            if _MODE == "auto":
                if manual_opt_out:
                    result["kept"].append(agent_id)  # user said no — never override
                elif already_applied and block.get("enforce"):
                    result["kept"].append(agent_id)  # already live; no re-notify
                else:
                    _apply_certify(db, agent, stats)
                    result["certified"].append(agent_id)
            elif _MODE == "approve":
                if already_waiting or rejected_unchanged:
                    result["kept"].append(agent_id)  # already queued / user said no
                else:
                    _queue_approval(db, agent, stats)
                    result["queued"].append(agent_id)
            else:  # notify
                if _notify_cooldown_active(agent_id):
                    result["kept"].append(agent_id)  # already pinged recently
                else:
                    _notify_ready(db, agent, stats)
                    _mark_notified(agent_id)
                    result["notified"].append(agent_id)
        elif verdict == "revoke":
            if already_revoked:
                result["kept"].append(agent_id)  # rollback already applied
            elif block.get("enforce"):
                _apply_revoke(db, agent, stats)
                result["revoked"].append(agent_id)
            else:
                # already shadowed → nothing to roll back; audit once only
                _record_action(db, agent_id, "revoke", "revoked", stats)
                result["kept"].append(agent_id)
        else:
            result["kept"].append(agent_id)
    return result


def run_auto_certification() -> Dict[str, Any]:
    """One full certification pass: open a session, run, commit, log, notify."""
    if _MODE == "off":
        return {"enabled": False, "mode": "off"}
    try:
        from core.database import get_db_session

        with get_db_session() as db:
            result = certify_workloads(db)
            db.commit()
        _last_run.update(
            {
                "last_run": datetime.now(timezone.utc).isoformat(),
                "mode": _MODE,
                "interval_min": _INTERVAL_MIN,
                **result,
            }
        )
        logger.info(
            f"[stage-router automation] {_MODE}: certified={result['certified']} "
            f"revoked={result['revoked']} queued={result['queued']} "
            f"notified={result['notified']}"
        )
        return {"enabled": True, "mode": _MODE, **result}
    except Exception as e:
        logger.warning(f"Stage-router automation pass failed: {e}")
        return {"enabled": True, "mode": _MODE, "error": "pass failed"}


# ── Approval management (management API) ────────────────────────────────────


def pending_approvals(db: Any) -> List[Dict[str, Any]]:
    """Latest pending-approval action per agent (state == 'approval')."""
    try:
        from core.models import StageRouterAutomationAction

        rows = (
            db.query(StageRouterAutomationAction)
            .filter(StageRouterAutomationAction.state == "approval")
            .order_by(StageRouterAutomationAction.created_at.desc())
            .all()
        )
        return [
            {
                "id": r.id,
                "agent_id": r.agent_id,
                "verdict": r.verdict,
                "mode": r.mode,
                "stats": r.stats_json,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"Pending approvals read failed: {e}")
        return []


def apply_pending_decision(db: Any, agent_id: str, approve: bool) -> Dict[str, Any]:
    """Apply or reject the latest pending certification for one agent.

    Approve: flips ``configuration["stage_routing"]["enforce"]=true`` (+
    calibration markers) and marks the action applied. Reject: marks it
    rejected; config untouched (a future pass may re-queue).
    """
    from core.models import StageRouterAutomationAction

    action = (
        db.query(StageRouterAutomationAction)
        .filter(
            StageRouterAutomationAction.agent_id == agent_id,
            StageRouterAutomationAction.state == "approval",
        )
        .order_by(StageRouterAutomationAction.created_at.desc())
        .first()
    )
    if action is None:
        return {"applied": False, "reason": "no pending approval for this agent"}
    agent = _agent_query(db, agent_id)
    if agent is None:
        return {"applied": False, "reason": "agent not found"}
    if approve:
        _apply_enforce(agent, True, certified=True)
        action.state = "applied"
        action.decided_at = datetime.now(timezone.utc)
        return {
            "applied": True,
            "agent_id": agent_id,
            "enforce": True,
            "state": "applied",
        }
    action.state = "rejected"
    action.decided_at = datetime.now(timezone.utc)
    return {"applied": False, "agent_id": agent_id, "state": "rejected"}


def get_automation_status() -> Dict[str, Any]:
    """Operator-facing automation state (mode, cadence, last run, queue)."""
    try:
        from core.database import get_db_session

        with get_db_session() as db:
            pending = pending_approvals(db)
    except Exception:  # pragma: no cover - defensive
        pending = []
    return {
        "enabled": _MODE != "off",
        "mode": _MODE,
        "interval_min": _INTERVAL_MIN,
        "pending_approvals": pending,
        "last_run": _last_run,
    }


# ── Background loop ─────────────────────────────────────────────────────────


async def stage_router_automation_loop() -> None:
    """Periodic certification pass. Failures are logged, never raised."""
    while True:
        try:
            await asyncio.sleep(max(_INTERVAL_MIN, 0.5) * 60)
            run_auto_certification()
        except asyncio.CancelledError:
            break
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"Stage-router automation loop iteration failed: {e}")


def ensure_automation_task() -> None:
    """Lazily start the background loop (mirrors GovernanceCache pattern)."""
    global _automation_task
    if _automation_task is not None or _MODE == "off":
        return
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            _automation_task = loop.create_task(stage_router_automation_loop())
    except Exception as e:
        logger.warning(f"Could not start stage-router automation loop: {e}")
