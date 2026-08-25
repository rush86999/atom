"""P5 — Allocator integrity controls (AGENT_ORG_POLITICS_PLAN.md Phase 5).

R6/R7/R12: agents reproduce human governance failures — allocator roles get
corrupted when they carry rewards, incumbents entrench in homogeneous pools,
and social contact (Agent Radio) can become deal-making. These helpers make
Atom's recruiter/coordinator roles incorruptible-by-construction:

- self-dealing block: an agent cannot recruit itself as a specialist
- rotation: teams may declare coordinator candidates with task/daily/fixed
  rotation so no single agent permanently holds the allocator role
- diversity floor: teams of ≥3 span ≥2 model families when families are
  declared (homogeneous pools never produce leadership turnover — R6)
- conflict-of-interest signal: prior radio contact between the coordinator
  and a candidate is recorded on the link (shadow-only; never blocks)

Pure functions here; wire-ins live in atom_meta_agent._recruit_fleet.
Flag: ATOM_ALLOCATOR_INTEGRITY_ENABLED (default false until calibrated).
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

COI_WINDOW_HOURS = 24 * 30


def allocator_integrity_enabled() -> bool:
    """Env kill-switch wins; else consent-gated automation state (TTL-cached)."""
    env_val = os.getenv("ATOM_ALLOCATOR_INTEGRITY_ENABLED", "")
    if env_val.strip().lower() in ("true", "false"):
        return env_val.strip().lower() == "true"
    try:
        from core.org_politics_automation import resolved_flag

        return resolved_flag("allocator_integrity")
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Self-recruitment guard
# ---------------------------------------------------------------------------


def self_recruitment_blocked(
    parent_agent_id: Optional[str], child_agent_id: Optional[str]
) -> bool:
    """True when an agent tries to recruit itself (case-insensitive)."""
    if not parent_agent_id or not child_agent_id:
        return False
    return str(parent_agent_id).strip().lower() == str(child_agent_id).strip().lower()


# ---------------------------------------------------------------------------
# Coordinator rotation (R6: term limits)
# ---------------------------------------------------------------------------


def resolve_coordinator(
    team_cfg: Optional[Dict[str, Any]],
    *,
    run_seq: int = 0,
    today: Optional[date] = None,
) -> Optional[str]:
    """Resolve the coordinator for one run from a team config.

    Config shape (config/lateral_teams/*.yaml):
        coordinator_rotation: fixed | task | daily   (default: fixed)
        coordinator_candidates: [agent_id, ...]

    - fixed  → always the first candidate (today's behavior)
    - task   → round-robin per run sequence number
    - daily  → rotates once per calendar day
    Returns None when no candidates are declared (callers keep incumbent).
    """
    if not isinstance(team_cfg, dict):
        return None
    candidates = [
        str(c)
        for c in (team_cfg.get("coordinator_candidates") or [])
        if c
    ]
    if not candidates:
        return None
    mode = str(team_cfg.get("coordinator_rotation", "fixed")).lower()
    if mode == "task":
        return candidates[run_seq % len(candidates)]
    if mode == "daily":
        day = today or datetime.now(timezone.utc).date()
        return candidates[day.toordinal() % len(candidates)]
    return candidates[0]


# ---------------------------------------------------------------------------
# Diversity floor (R6/R12)
# ---------------------------------------------------------------------------


def enforce_diversity_floor(
    members: List[str],
    family_of: Callable[[str], Optional[str]],
    *,
    min_team_size: int = 3,
    min_families: int = 2,
) -> Dict[str, Any]:
    """Check the model-family diversity floor for a recruited team.

    ``family_of`` resolves an agent id to its model family (or None when
    undeclared). Teams smaller than min_team_size are exempt. Unknown
    families don't count toward the floor — a fully-undeclared team cannot
    be judged homogeneous, so it passes (shadow posture).
    """
    detail: Dict[str, Any] = {
        "team_size": len(members),
        "families": {},
        "ok": True,
    }
    if len(members) < min_team_size:
        detail["reason"] = "team_below_min_size"
        return detail
    counts: Dict[str, int] = {}
    for m in members:
        fam = family_of(m)
        if fam:
            counts[fam] = counts.get(fam, 0) + 1
    detail["families"] = counts
    distinct = len(counts)
    detail["distinct_families"] = distinct
    if counts and distinct < min_families:
        detail["ok"] = False
        detail["reason"] = "single_family_team"
    else:
        detail["reason"] = "pass"
    return detail


# ---------------------------------------------------------------------------
# Conflict-of-interest signal (R6 deal-making surface)
# ---------------------------------------------------------------------------


def has_radio_contact(
    db: Any, agent_a: str, agent_b: str, *, window_hours: int = COI_WINDOW_HOURS
) -> bool:
    """True when A and B exchanged radio messages inside the window.

    Reads the P0 org telemetry (radio_message events, both directions).
    Never raises; missing table/data → False.
    """
    try:
        from core.org_telemetry_service import AgentOrgTelemetryService

        svc = AgentOrgTelemetryService(db)
        for ev in svc._events("radio_message", window_hours=window_hours):
            pair = {ev.actor_agent_id, ev.target_agent_id}
            if agent_a in pair and agent_b in pair:
                return True
        return False
    except Exception as e:  # noqa: BLE001 — signal only, never blocks
        logger.debug(f"has_radio_contact check failed: {e}")
        return False
