"""Gateway budget threshold alerts (Phase B3).

Tracks per-workspace daily gateway spend (in-memory, matching the repo's
personal-edition zero-dependency posture) and fires an in-app notification
once per threshold (50/80/90/100% of the personal budget limit) per
workspace-day. Gated by ``ATOM_GATEWAY_BUDGET_ALERTS`` (default off).

Notifications use the 3-arg ``NotificationService.send_notification(user_id,
type, data)`` contract and are best-effort — a glitch never raises.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import date
from typing import Dict, List, Optional, Set

from core.notification_service import NotificationService

logger = logging.getLogger(__name__)

GATEWAY_BUDGET_ALERTS_ENABLED = os.getenv("ATOM_GATEWAY_BUDGET_ALERTS", "false").lower() == "true"
THRESHOLDS = [50, 80, 90, 100]

# In-memory daily spend + fire-once state, keyed by workspace_id.
_daily_spend: Dict[str, float] = {}
_fired: Dict[str, Set[int]] = {}
_today: str = ""

# Serializes the read-modify-write on _daily_spend/_fired so concurrent
# gateway requests cannot lose updates or double-fire thresholds. A single
# global lock is sufficient — the critical section is tiny (dict ops + an
# await for notification, which releases the lock only after the atomic
# state mutation is complete).
_spend_lock = asyncio.Lock()


def reset_budget_alerts() -> None:
    """Clear in-memory alert state (used by tests)."""
    global _today
    _today = ""
    _daily_spend.clear()
    _fired.clear()


def _reset_if_new_day() -> None:
    global _today
    today = date.today().isoformat()
    if today != _today:
        _today = today
        # Mutate in place (never rebind): `_fired`/`_daily_spend` are read
        # under _spend_lock, and module consumers may hold references to the
        # dicts — rebinding would strand them on a stale (pre-reset) object.
        _daily_spend.clear()
        _fired.clear()


def resolve_budget_limit(_workspace_id: str) -> float:
    """Budget base for threshold math (personal budget limit, default $100)."""
    try:
        from core.personal_budget_service import personal_budget_service

        return personal_budget_service._get_budget_limit() or 100.0
    except Exception:
        return 100.0


def _resolve_recipient_id(prefer_user_id: Optional[str] = None) -> Optional[str]:
    """Resolve the alert recipient.

    Preference order:
      1. ``prefer_user_id`` (the gateway caller whose spend triggered the
         alert) — so the user whose budget is burning gets notified, not an
         arbitrary ``db.query(User).first()`` row.
      2. An admin user (workspace owner) — looked up by ``role``; the User
         model has no ``is_admin`` column (the previous attribute raised
         AttributeError, which was swallowed, silently disabling every
         fallback alert).
      3. None (alert skipped).

    The prior code fell back to ``db.query(User).first()`` (an arbitrary user)
    when no admin existed — a cross-user notification-leakage vector.
    """
    try:
        from core.database import SessionLocal
        from core.models import User, UserRole

        db = SessionLocal()
        try:
            if prefer_user_id:
                user = db.query(User).filter(User.id == prefer_user_id).first()
                if user:
                    return str(user.id)
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


async def record_gateway_spend(
    workspace_id: str,
    cost_usd: Optional[float],
    user_id: Optional[str] = None,
) -> List[int]:
    """Account gateway spend and return newly-crossed thresholds (fire-once).

    Fires in-app notifications for each threshold the cumulative daily spend
    just crossed. Returns the crossed thresholds (empty when disabled, no cost,
    no budget, or nothing newly crossed).

    ``user_id`` (the gateway caller) is passed to the notifier so the user
    whose spend crossed the threshold receives the alert, rather than an
    arbitrary fallback user.
    """
    if not GATEWAY_BUDGET_ALERTS_ENABLED or not cost_usd or cost_usd <= 0:
        return []
    _reset_if_new_day()

    # Serialize the read-modify-write so concurrent requests can't lose spend
    # updates or double-fire a threshold. The notification await happens
    # inside the lock but is best-effort and fast.
    async with _spend_lock:
        daily = _daily_spend.get(workspace_id, 0.0) + cost_usd
        _daily_spend[workspace_id] = daily

        limit = resolve_budget_limit(workspace_id)
        if limit <= 0:
            return []

        usage_percent = (daily / limit) * 100.0
        fired = _fired.setdefault(workspace_id, set())
        crossed = [t for t in THRESHOLDS if usage_percent >= t and t not in fired]
        if crossed:
            fired.update(crossed)
        # Release-relevant values captured; notification sent after the state
        # mutation is committed so the lock is held only for the atomic part.

    if crossed:
        await _notify_thresholds(workspace_id, crossed, daily, limit, user_id)
    return crossed


async def _notify_thresholds(
    workspace_id: str,
    thresholds: List[int],
    daily: float,
    limit: float,
    user_id: Optional[str] = None,
) -> None:
    try:
        recipient = _resolve_recipient_id(prefer_user_id=user_id)
        if not recipient:
            logger.debug("Gateway budget alert skipped: no recipient user")
            return
        notifier = NotificationService()
        usage_percent = (daily / limit) * 100.0
        for t in thresholds:
            await notifier.send_notification(
                str(recipient),
                "gateway_budget_alert",
                {
                    "title": f"Gateway budget {t}% used",
                    "message": (
                        f"Gateway spend reached {t}% of your budget. "
                        f"Daily spend ${daily:.2f} of ${limit:.2f}."
                    ),
                    "priority": "high",
                    "metadata": {
                        "alert_type": "gateway_budget_alert",
                        "workspace_id": workspace_id,
                        "threshold_percent": t,
                        "usage_percent": round(usage_percent, 2),
                        "current_spend": round(daily, 4),
                        "budget_limit": round(limit, 4),
                    },
                },
            )
    except Exception as exc:  # pragma: no cover - best-effort
        logger.debug(f"Gateway budget alert skipped: {exc}")


def run_budget_alert_sync(workspace_id: str, cost_usd: Optional[float]) -> List[int]:
    """Sync shim for callers without a running loop (test/utility use)."""
    return asyncio.run(record_gateway_spend(workspace_id, cost_usd))
