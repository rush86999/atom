"""Agent org-dynamics telemetry (AGENT_ORG_POLITICS_PLAN.md Phase 0).

Append-only event capture for org "office politics" signals — recruitment
incumbency, radio social contact, reviewer accept/reject rates — plus pure
compute helpers that turn events into the baseline report. Telemetry is
write-only from the runtime's perspective: nothing here feeds a routing or
gating decision, and emission NEVER raises (best-effort, like monitoring).

Flag: ATOM_ORG_TELEMETRY_ENABLED (default ON).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

EVENT_FLEET_RECRUIT = "fleet_recruit"
EVENT_RADIO_THREAD_ATTACH = "radio_thread_attach"
EVENT_RADIO_MESSAGE = "radio_message"
EVENT_REVIEW_VERDICT = "review_verdict"


def telemetry_enabled() -> bool:
    return os.getenv("ATOM_ORG_TELEMETRY_ENABLED", "true").lower() == "true"


class AgentOrgTelemetryService:
    """Best-effort writer + reporter over ``agent_org_events``."""

    def __init__(self, db: Session):
        self.db = db

    # -- write path ---------------------------------------------------------

    def emit(
        self,
        event_type: str,
        *,
        actor_agent_id: Optional[str] = None,
        target_agent_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        chain_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        commit: bool = True,
    ) -> Optional[Any]:
        """Write one event row. Returns the row, or None when disabled/error.

        ``commit=False`` rides the caller's transaction (wire-ins that must
        not disturb the ambient session's commit contract); the row is only
        flushed and persists when the caller next commits.
        """
        if not telemetry_enabled():
            return None
        try:
            from core.models import AgentOrgEvent

            row = AgentOrgEvent(
                event_type=event_type,
                actor_agent_id=actor_agent_id,
                target_agent_id=target_agent_id,
                execution_id=execution_id,
                chain_id=chain_id,
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                payload_json=dict(payload or {}),
            )
            self.db.add(row)
            if commit:
                self.db.commit()
            else:
                self.db.flush()
            return row
        except Exception as e:  # noqa: BLE001 — telemetry must never raise
            logger.debug(f"org telemetry emit failed: {e}")
            return None

    def emit_fleet_recruit(
        self,
        *,
        coordinator_agent_id: str,
        members: List[Dict[str, Any]],
        chain_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> List[Any]:
        """One recruit event per coordinator→specialist pair (incumbency data)."""
        rows: List[Any] = []
        for member in members:
            target = (
                member.get("agent_id")
                if isinstance(member, dict)
                else getattr(member, "agent_id", None)
            )
            if not target:
                continue
            row = self.emit(
                EVENT_FLEET_RECRUIT,
                actor_agent_id=coordinator_agent_id,
                target_agent_id=str(target),
                chain_id=chain_id,
                execution_id=execution_id,
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                payload={
                    "domain": (
                        member.get("domain") if isinstance(member, dict) else None
                    )
                },
            )
            if row is not None:
                rows.append(row)
        return rows

    # -- report math (pure reads; also used by scripts/org_dynamics_report.py)

    def _events(self, event_type: str, window_hours: Optional[int] = None) -> List[Any]:
        try:
            from core.models import AgentOrgEvent

            q = self.db.query(AgentOrgEvent).filter(
                AgentOrgEvent.event_type == event_type
            )
            if window_hours is not None:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
                q = q.filter(AgentOrgEvent.created_at >= cutoff)
            return q.all()
        except Exception as e:  # noqa: BLE001
            logger.debug(f"org telemetry read failed: {e}")
            return []

    def compute_incumbency(self, window_hours: Optional[int] = None) -> Dict[str, Any]:
        """How often does the same coordinator recruit the same specialist?

        R6 ("Politician/Liar/Obedient Worker"): homogeneous pools entrench
        incumbents. High repeat-pair ratios are the signal to watch before any
        allocator autonomy expands.
        """
        counts: Dict[tuple, int] = {}
        for ev in self._events(EVENT_FLEET_RECRUIT, window_hours):
            if ev.actor_agent_id and ev.target_agent_id:
                key = (ev.actor_agent_id, ev.target_agent_id)
                counts[key] = counts.get(key, 0) + 1
        total = sum(counts.values())
        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        repeat_pairs = sum(1 for _, n in ranked if n > 1)
        distinct_targets = len({t for (_, t) in counts})
        return {
            "total_recruits": total,
            "distinct_pairs": len(ranked),
            "repeat_pairs": repeat_pairs,
            "distinct_targets": distinct_targets,
            "repeat_pair_ratio": (
                round(repeat_pairs / len(ranked), 4) if ranked else 0.0
            ),
            "top_pairs": [
                {"actor": a, "target": t, "count": n}
                for (a, t), n in ranked[:10]
            ],
        }

    def compute_review_rates(
        self, window_hours: Optional[int] = None
    ) -> Dict[str, Any]:
        """Reviewer accept/reject counts per reviewed specialist."""
        by_target: Dict[str, Dict[str, int]] = {}
        for ev in self._events(EVENT_REVIEW_VERDICT, window_hours):
            target = ev.target_agent_id or "(unknown)"
            slot = by_target.setdefault(target, {"accepted": 0, "rejected": 0})
            accepted = bool((ev.payload_json or {}).get("accepted", True))
            slot["accepted" if accepted else "rejected"] += 1
        return {
            "by_target": by_target,
            "total_reviews": sum(s["accepted"] + s["rejected"] for s in by_target.values()),
        }

    def compute_coi_pairs(
        self,
        window_hours: int = 24 * 30,
    ) -> List[Dict[str, Any]]:
        """Conflict-of-interest signal: A messaged B on radio, then B recruited A.

        Shadow-only (R6): informs the Phase 5 integrity controls; never blocks.
        """
        recruits = [
            (ev.actor_agent_id, ev.target_agent_id, ev.created_at)
            for ev in self._events(EVENT_FLEET_RECRUIT, window_hours)
            if ev.actor_agent_id and ev.target_agent_id
        ]
        messages = [
            (ev.actor_agent_id, ev.target_agent_id, ev.created_at)
            for ev in self._events(EVENT_RADIO_MESSAGE, window_hours)
            if ev.actor_agent_id and ev.target_agent_id
        ]
        message_pairs = {(a, t) for (a, t, _) in messages} | {
            (t, a) for (a, t, _) in messages
        }
        flagged: List[Dict[str, Any]] = []
        seen = set()
        for actor, target, when in recruits:
            if (actor, target) in message_pairs and (actor, target) not in seen:
                seen.add((actor, target))
                flagged.append({
                    "actor": actor,
                    "target": target,
                    "last_recruit_at": when.isoformat() if when else None,
                })
        return flagged


def emit_org_event(
    db: Optional[Session], event_type: str, **kwargs: Any
) -> None:
    """Module-level one-liner for wire-in points (swallows everything).

    ``db=None`` opens a short-lived session — for call sites (e.g. the
    reviewer loop) that hold no session of their own. Pass ``commit=False``
    in kwargs to ride the caller's transaction.
    """
    try:
        if db is None:
            from core.database import get_db_session

            with get_db_session() as owned_db:
                AgentOrgTelemetryService(owned_db).emit(event_type, **kwargs)
            return
        AgentOrgTelemetryService(db).emit(event_type, **kwargs)
    except Exception as e:  # noqa: BLE001 — never propagate
        logger.debug(f"emit_org_event failed: {e}")
