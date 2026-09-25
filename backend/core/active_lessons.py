"""Validated ACTIVE-lesson projection (2026-09-24 contract check 2).

The skill-impact ledger is APPEND-ONLY HISTORY for the evolvers
(WikiSkill W4: inference agents never read raw ledger rows). Runtime
consumption changes that contract, so this module is the single,
EXPLICIT bridge:

    ledger (history)  ->  active_lesson_projection()  ->  runtime use

A ledger row qualifies as an ACTIVE lesson override only when it passes
VALIDATION — the projection never trusts history alone:

- ``source == "lesson_promotion"`` and ``status == "accepted"``;
- the payload carries complete candidate metadata: candidate_id,
  version, scope (tenant), expiry (revalidate-after outcomes or wall
  clock), and a rollback state (a newer rolled_back row deactivates);
- every override value satisfies its OVERRIDE SPEC (registered bounds
  and type) — out-of-bounds or unknown-key overrides are dropped, not
  clamped silently;
- tenant scoping: a row is visible only to its tenant.

Unknown override keys are NOT silently ignored forever — they are
reported in ``projection_report()["rejected"]`` with reasons, so a
spec/lesson mismatch surfaces instead of half-applying.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

# OVERRIDE SPECS: type, inclusive bounds, and which execution limits the
# consumer must still enforce on its own (specs bound the LESSON, never
# the turn's own deadline/rate/permission/cost limits).
OVERRIDE_SPECS: Dict[str, Dict[str, Any]] = {
    "resume_planner_wait_max_seconds": {
        "type": float, "min": 25.0, "max": 75.0,
        "limits_note": (
            "consumer must still clamp to the turn's remaining deadline"),
    },
}

_CACHE_TTL_S = 5.0
_cache: Dict[str, Any] = {"at": 0.0, "projection": {}}


def _validate_row(row: Any) -> "tuple[Optional[Dict[str, Any]], Optional[str]]":
    """(validated-overrides, rejection-reason) for one ledger row."""
    payload = row.payload
    if isinstance(payload, str):
        try:
            import json

            payload = json.loads(payload or "{}")
        except Exception:  # noqa: BLE001
            payload = {}
    if not isinstance(payload, dict):
        return None, "payload_not_a_dict"
    candidate_id = payload.get("candidate_id")
    if not candidate_id:
        return None, "missing_candidate_id"
    if not payload.get("version"):
        return None, "missing_version"
    scope = payload.get("scope") or {}
    if not isinstance(scope, dict) or not scope.get("tenant_id"):
        return None, "missing_scope_tenant"
    expiry = payload.get("expiry") or {}
    expires_at = expiry.get("expires_at")
    if expires_at is not None and time.time() > float(expires_at):
        return None, "expired"
    overrides = payload.get("overrides") or {}
    if not isinstance(overrides, dict) or not overrides:
        return None, "no_overrides"
    validated: Dict[str, Any] = {}
    for key, value in overrides.items():
        spec = OVERRIDE_SPECS.get(key)
        if spec is None:
            return None, f"unknown_override_key:{key}"
        try:
            coerced = spec["type"](value)
        except (TypeError, ValueError):
            return None, f"override_type_mismatch:{key}"
        if coerced < spec["min"] or coerced > spec["max"]:
            return None, (
                f"override_out_of_bounds:{key}={coerced}"
                f" (allowed {spec['min']}..{spec['max']})")
        validated[key] = coerced
    return {
        "candidate_id": candidate_id,
        "version": payload.get("version"),
        "scope": scope,
        "overrides": validated,
        "accepted_at": str(row.created_at or ""),
    }, None


def active_lesson_projection(tenant_id: str = "default") -> Dict[str, Any]:
    """Validated, tenant-scoped ACTIVE overrides (newest row per target
    decides; a rolled_back newest row deactivates the target)."""
    now = time.time()
    if now - _cache["at"] < _CACHE_TTL_S:
        if tenant_id in _cache["projection"]:
            return _cache["projection"][tenant_id]
        # unseen tenant within the TTL window: compute it and merge into
        # the cached per-tenant dict (a cache miss must not return {}).
    per_target: Dict[str, Any] = {}
    report: Dict[str, list] = {"rejected": []}
    try:
        from core.auto_dev.models import SkillImpactEntry
        from core.database import get_db_session

        with get_db_session() as db:
            rows = (
                db.query(SkillImpactEntry)
                .filter(SkillImpactEntry.source == "lesson_promotion")
                .order_by(SkillImpactEntry.created_at.desc())
                .limit(200)
                .all()
            )
    except Exception:  # noqa: BLE001 — projection is best-effort
        rows = []
    for row in rows:
        target = str(row.target or "")
        if target in per_target:
            continue  # newer row already decided this target
        if row.status == "rolled_back":
            per_target[target] = None  # deactivated
            continue
        if row.status != "accepted":
            per_target[target] = None
            continue
        validated, reason = _validate_row(row)
        if validated is None:
            per_target[target] = None
            report["rejected"].append({"target": target, "reason": reason})
            continue
        if validated["scope"].get("tenant_id") not in (tenant_id, "*"):
            per_target[target] = None  # other tenant's lesson
            continue
        per_target[target] = validated
    merged: Dict[str, Any] = {}
    for entry in per_target.values():
        if not entry:
            continue
        for key, value in entry["overrides"].items():
            merged.setdefault(key, value)
    _cache["at"] = now
    _cache["projection"].setdefault(tenant_id, merged)
    _cache["projection"][tenant_id] = merged
    _cache["projection"]["_report"] = report
    return merged


def get_override(key: str, default: Any = None,
                 tenant_id: str = "default") -> Any:
    return active_lesson_projection(tenant_id).get(key, default)


def projection_report() -> Dict[str, Any]:
    active_lesson_projection()  # ensure fresh
    return _cache["projection"].get("_report", {"rejected": []})


def clear_cache() -> None:
    _cache["at"] = 0.0
    _cache["projection"] = {}
