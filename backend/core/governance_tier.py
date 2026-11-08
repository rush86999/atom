"""Canonical governance-tier vocabulary and run-time narrowing.

``AgentRegistry.status`` carries two different concepts in this codebase:

* a *governance maturity tier* — ``student`` / ``intern`` / ``supervised`` /
  ``autonomous``;
* a *runtime execution state* — most visibly ``running`` while an admitted
  run is in flight (and legacy/idle-style labels written by older surfaces).

Only the first group may become ``tier_at_issuance``. The sandbox issuer
correctly treats an unknown value as ``student``, but a live ``running`` row
must not erase the maturity the admission actually accepted. This module is
the single canonical conversion used by admission, dispatch and the agent
runners; it deliberately does **not** map execution states to a higher tier.

Narrowing rule: an issued tier is an upper bound, not a promotion. If the
agent's current row is a lower canonical tier (a real demotion), the lower
tier wins. If the row is revoked/disabled or an unrecognisable non-running
state, the result fails closed to ``student`` and the caller gets a truthful
source code.
"""
from __future__ import annotations

from typing import Optional, Tuple

CANONICAL_GOVERNANCE_TIERS: Tuple[str, ...] = (
    "student",
    "intern",
    "supervised",
    "autonomous",
)

_GOVERNANCE_TIER_RANK = {
    tier: rank for rank, tier in enumerate(CANONICAL_GOVERNANCE_TIERS)
}

# Execution/transport states that are not maturity. ``running`` is handled
# explicitly because admission legitimately holds the row there while an
# admitted job executes; all other non-tier values fail closed when no issued
# tier can prove the maturity.
_EXECUTION_STATES = frozenset({
    "running",
    "idle",
    "success",
    "completed",
    "failed",
    "error",
    "pending",
    "queued",
    "waiting",
    "active",
    "inactive",
    "paused",
    "stopped",
    "deprecated",
    "deleted",
})


def canonical_governance_tier(value: object) -> Optional[str]:
    """Return a canonical maturity tier, or ``None`` for any other value.

    Whitespace/case are normalised (the stored vocabulary has historically
    appeared in both cases); nothing else is coerced.
    """
    text = str(value or "").strip().lower()
    return text if text in _GOVERNANCE_TIER_RANK else None


def governance_tier_rank(value: object) -> Optional[int]:
    """Return the ordering rank of a canonical tier, or ``None``."""
    tier = canonical_governance_tier(value)
    return _GOVERNANCE_TIER_RANK[tier] if tier is not None else None


def is_execution_state(value: object) -> bool:
    """True for a known non-maturity runtime state label."""
    return str(value or "").strip().lower() in _EXECUTION_STATES


def effective_governance_tier(
    issued_tier: object,
    current_status: object,
    *,
    current_enabled: bool = True,
) -> Tuple[str, str]:
    """Resolve the tier a run may actually use, never widening past issuance.

    Returns ``(tier, source)`` where ``source`` is one of:

    ``admission``
        The issued canonical tier is still the effective (or the current row
        is the transient ``running`` execution state for this same run).
    ``demoted``
        The current row holds a lower canonical tier; the lower tier wins.
    ``current``
        No issued tier was available; the current canonical row supplied it.
    ``revoked``
        The current row is disabled; fail closed to ``student``.
    ``unverified`` / ``current_unverified``
        No canonical maturity could be proven; fail closed to ``student``.
    """
    issued = canonical_governance_tier(issued_tier)
    current = canonical_governance_tier(current_status)
    current_text = str(current_status or "").strip().lower()

    if not current_enabled:
        return "student", "revoked"

    if issued is None:
        if current is None:
            return "student", "unverified"
        return current, "current"

    if current is None:
        if current_text == "running":
            # The admitted run legitimately holds this row in ``running``;
            # that is execution state, not a maturity downgrade.
            return issued, "admission"
        return "student", "current_unverified"

    if _GOVERNANCE_TIER_RANK[current] < _GOVERNANCE_TIER_RANK[issued]:
        return current, "demoted"
    return issued, "admission"
