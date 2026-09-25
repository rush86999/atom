"""Runtime consumption of ACTIVE lesson candidates (2026-09-24 loop close).

Closes the last disconnected link of the learning loop: an APPROVED
candidate is actually CONSUMED at runtime, its application is RECORDED,
and it is REVERSIBLE.

Mechanics (smallest intervention — configuration, not code):
- ``active_overrides()`` reads the skill-impact ledger's ACCEPTED lesson
  rows (source='lesson_promotion') and exposes their ``overrides`` dicts,
  newest-first, keyed by override key.
- The orchestrator consults ``get_override(key, default)`` at the one
  behavior point the pilot lesson governs (the resume-turn planner wait
  cap), so promotion genuinely changes runtime behavior through
  configuration.
- ``demote_lesson()`` appends a ``rolled_back`` ledger row; the override
  disappears from ``active_overrides()`` immediately (accepted row is
  superseded by the rollback), restoring baseline behavior.
- Every runtime consumption may be recorded on the turn's task outcome
  (``applied_lessons``) — observability without behavior coupling.

The PILOT lesson stays in shadow (the gate refused on sample count). The
override-mediated demo lesson (resume planner wait) exists to prove the
LOOP mechanics end-to-end; promoting it is a separate decision gated by
the frozen evaluation.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

_OVERRIDE_CACHE_TTL_S = 5.0
_cache: Dict[str, Any] = {"at": 0.0, "rows": []}


def _load_rows() -> list:
    import time as _time

    now = _time.time()
    if now - _cache["at"] < _OVERRIDE_CACHE_TTL_S:
        return _cache["rows"]
    rows: list = []
    try:
        from core.auto_dev.models import SkillImpactEntry
        from core.database import get_db_session

        with get_db_session() as db:
            for row in (
                db.query(SkillImpactEntry)
                .filter(
                    SkillImpactEntry.source == "lesson_promotion",
                    SkillImpactEntry.status.in_(("accepted", "rolled_back")),
                )
                .order_by(SkillImpactEntry.created_at.desc())
                .limit(100)
                .all()
            ):
                payload = row.payload
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload or "{}")
                    except Exception:  # noqa: BLE001
                        payload = {}
                if not isinstance(payload, dict):
                    payload = {}
                rows.append({
                    "target": row.target,
                    "status": row.status,
                    "overrides": payload.get("overrides") or {},
                })
    except Exception:  # noqa: BLE001 — runtime consumption is best-effort
        rows = []
    _cache["at"] = now
    _cache["rows"] = rows
    return rows


def active_overrides() -> Dict[str, Any]:
    """Active override dicts from ACCEPTED lessons whose newest row is
    not a rollback (newest-first: a rolled_back row supersedes)."""
    latest: Dict[str, str] = {}
    merged: Dict[str, Any] = {}
    for row in _load_rows():
        target = row["target"]
        if target in latest:
            continue  # a newer row already decided this target
        latest[target] = row["status"]
        if row["status"] == "accepted":
            for key, value in (row["overrides"] or {}).items():
                merged.setdefault(key, value)
    return merged


def get_override(key: str, default: Any = None) -> Any:
    return active_overrides().get(key, default)


def clear_cache() -> None:
    _cache["at"] = 0.0
    _cache["rows"] = []


def record_application(outcome: Dict[str, Any], applied: list) -> None:
    """Observability: which lessons the runtime consumed this turn."""
    if isinstance(outcome, dict) and applied:
        outcome["applied_lessons"] = applied[:8]
