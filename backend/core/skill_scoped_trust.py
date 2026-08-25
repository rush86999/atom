"""Skill-scoped reputation (AGENT_ORG_POLITICS_PLAN.md Phase 3).

R8 ("Skill-Conditional Reputation", arXiv 2606.14200): a single global trust
score is the wrong object for skill-specialized agents; trust should be
per-skill with empirical-Bayes borrowing across correlated skills — but the
same pooling channel that buys data efficiency launders reputation, so a
structural zero-evidence gate must bound it.

R9: updates are asymmetric — slow to gain, fast to lose.
R12: homogeneous pools entrench incumbents → cold-start agents get a small
deterministic exploration boost so they can enter rotation.

Data source: ``AgentRegistry.configuration.capability_stats`` as written by
``CapabilityGraduationService.record_usage`` (verified-gated tri-state;
unverified successes never inflate trust). Correlation borrows via
``SpecialistMatcher.DOMAIN_ALIASES``: an agent's record on
finance-adjacent capability names (invoice, reconciliation, …) informs its
finance trust — capped by TRUST_FLOOR_CAP when the target skill itself has
no direct evidence.

Flag: ATOM_SKILL_SCOPED_TRUST_ENABLED (default OFF — shadow-first; when off,
the matcher's global-confidence term behaves exactly as before).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Pooling strength toward correlated-skill evidence (the paper's safe knee).
BETA = 0.1
# Laundering guard: with zero direct evidence on the target skill, borrowed
# trust can never exceed this cap no matter how perfect the farm record.
TRUST_FLOOR_CAP = 0.6
# R9 asymmetry: verified failures subtract fast (success accrues only via
# the verified ratio itself, i.e. slowly).
FAIL_PENALTY_PER = 0.05
FAIL_PENALTY_CAP = 0.25
# Cold-start visibility: deterministic epsilon so unevidenced-but-capable
# agents can enter rotation without randomness in scoring.
EXPLORATION_BOOST = 0.02


def skill_scoped_trust_enabled() -> bool:
    """Env kill-switch wins; else consent-gated automation state (TTL-cached)."""
    env_val = os.getenv("ATOM_SKILL_SCOPED_TRUST_ENABLED", "")
    if env_val.strip().lower() in ("true", "false"):
        return env_val.strip().lower() == "true"
    try:
        from core.org_politics_automation import resolved_flag

        return resolved_flag("skill_trust")
    except Exception:
        return False


def _ratio(stats: Optional[Dict[str, Any]]) -> Optional[float]:
    """Verified success ratio for one stats dict (None when no evidence)."""
    if not isinstance(stats, dict):
        return None
    total = stats.get("total", 0)
    if not total:
        return None
    verified = stats.get("verified_success", 0)
    try:
        return max(0.0, min(1.0, verified / total))
    except (TypeError, ZeroDivisionError):
        return None


def _penalty(stats: Optional[Dict[str, Any]]) -> float:
    if not isinstance(stats, dict):
        return 0.0
    failures = stats.get("failures_verified", 0) or 0
    try:
        return min(FAIL_PENALTY_CAP, float(failures) * FAIL_PENALTY_PER)
    except (TypeError, ValueError):
        return 0.0


def collect_stats(
    configuration: Any, domain: str
) -> Tuple[Dict[str, Any], List[Tuple[str, Dict[str, Any]]]]:
    """Split an agent's capability_stats into (direct, correlated) for domain.

    Direct = exact stats key match on the canonical domain name. Correlated =
    other keys whose name matches any DOMAIN_ALIASES keyword of the domain
    (substring match both ways, case-insensitive). Missing config yields
    ({}, []) → neutral trust.
    """
    if not isinstance(configuration, dict):
        return {}, []
    all_stats = configuration.get("capability_stats")
    if not isinstance(all_stats, dict):
        return {}, []
    try:
        from core.specialist_matcher import DOMAIN_ALIASES

        aliases = [k.lower() for k in DOMAIN_ALIASES.get((domain or "").lower(), [])]
    except Exception:
        aliases = []
    direct: Dict[str, Any] = {}
    correlated: List[Tuple[str, Dict[str, Any]]] = []
    for key, stats in all_stats.items():
        if not isinstance(stats, dict):
            continue
        key_l = str(key).lower()
        if key_l == (domain or "").lower():
            direct = stats
            continue
        if any(a and (a in key_l or key_l in a) for a in aliases):
            correlated.append((str(key), stats))
    # Prefer an alias-matched entry over {} only when there is no exact key.
    if not direct:
        for key, stats in correlated:
            if key.lower() == (domain or "").lower():
                direct = stats
                break
    return direct, correlated


def pooled_ratio(correlated: List[Any]) -> Optional[float]:
    """Total-weighted verified-success ratio across correlated skills.

    Accepts either ``[(name, stats), …]`` tuples or bare stats dicts.
    """
    num = 0.0
    den = 0
    for entry in correlated:
        if isinstance(entry, dict):
            stats = entry
        elif isinstance(entry, tuple) and len(entry) == 2:
            stats = entry[1]
        else:
            continue
        if not isinstance(stats, dict):
            continue
        total = stats.get("total", 0) or 0
        if not total:
            continue
        num += (stats.get("verified_success", 0) or 0) * (
            stats.get("total", 0) / max(total, 1)
        )
        den += total
    if not den:
        return None
    return max(0.0, min(1.0, num / den))


def trust_score(
    direct: Optional[Dict[str, Any]],
    correlated: List[Any],
) -> float:
    """Trust in [0, 1] for one (agent × domain), default-deny neutral 0.5.

    - No evidence anywhere → 0.5 (neutral; neither rewards nor punishes).
    - No DIRECT evidence but correlated exists → min(pooled, TRUST_FLOOR_CAP)
      (R8 laundering guard: farmed records cannot lift unevidenced skills).
    - Direct evidence present → shrinkage blend of direct ratio toward the
      pooled ratio, minus the fast-fail penalty. Unverified successes never
      enter the numerator (graduation policy parity).
    """
    direct_ratio = _ratio(direct)
    pool = pooled_ratio(correlated)

    if direct_ratio is None:
        base = TRUST_FLOOR_CAP if pool is not None else 0.5
        score = min(pool, TRUST_FLOOR_CAP) if pool is not None else base
    else:
        if pool is not None:
            blended = (direct_ratio + BETA * pool) / (1 + BETA)
        else:
            blended = direct_ratio
        score = blended

    score -= _penalty(direct)
    return round(max(0.0, min(1.0, score)), 4)


def exploration_eligible(direct: Optional[Dict[str, Any]]) -> bool:
    """True when the agent has zero direct evidence on this domain (cold start)."""
    return not (isinstance(direct, dict) and (direct.get("total", 0) or 0))


def agent_domain_trust(agent_row: Any, domain: str) -> Tuple[float, bool]:
    """Convenience wrapper: (trust, cold_start) for an AgentRegistry row."""
    config = getattr(agent_row, "configuration", None)
    direct, correlated = collect_stats(config, domain)
    score = trust_score(direct, correlated)
    if exploration_eligible(direct):
        score = round(min(1.0, score + EXPLORATION_BOOST), 4)
    return score, exploration_eligible(direct)


def confidence_term(agent_row: Any, domain: str) -> float:
    """Drop-in replacement for the matcher's global-confidence term.

    Returns the same value shape the ``_W_CONFIDENCE`` weight expects.
    """
    trust, _ = agent_domain_trust(agent_row, domain)
    return trust
