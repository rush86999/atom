"""Dynamic promotion policy: seeded thresholds, auto-tuned by domain history.

Promotion gates (training sessions, work episodes, success ratio) start from
env seeds and adapt to observed post-promotion performance of the domain.

Design (research-aligned — "earned autonomy" with asymmetric adjustment):
- SEED: env defaults (3 sessions / 10 episodes / 0.7 ratio) until evidence exists.
- STATISTICAL FLOOR: no tuning until the domain has >= ATOM_POLICY_MIN_PROMOTED
  promoted agents (default 3) each with >= 5 episodes — thresholds never move
  on noise.
- ASYMMETRY: underperforming domains tighten quickly (+1 session, +5 episodes,
  +0.05 ratio); strong domains ease slowly (−1 session, ×0.8 episodes, −0.05
  ratio). Trust is earned slowly and forfeited fast.
- HARD BOUNDS: sessions [1,6], episodes [3,20], ratio [0.5,0.9] — a tuned
  policy can never drop below defensible floors.
- KILL-SWITCH: ATOM_PROMOTION_DYNAMIC_TUNING=false pins the seeds.

Deterministic on demand (recomputed from history, no stored state to drift),
so the policy is auditable: every response carries the thresholds plus the
basis numbers that produced them.
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Hard bounds — tuned values clamp into these.
_SESSIONS_MIN, _SESSIONS_MAX = 1, 6
_EPISODES_MIN, _EPISODES_MAX = 3, 20
_RATIO_MIN, _RATIO_MAX = 0.5, 0.9

# Evidence floor before tuning engages (per domain).
_MIN_PROMOTED_SAMPLE = int(os.getenv("ATOM_POLICY_MIN_PROMOTED", "3"))
_MIN_EPISODES_PER_AGENT = 5

_STRONG_DOMAIN_RATIO = 0.85   # seed + 0.15: reliably strong post-promotion
_TUNE_EASE = "ease"
_TUNE_TIGHTEN = "tighten"


def _dynamic_tuning_enabled() -> bool:
    return os.getenv("ATOM_PROMOTION_DYNAMIC_TUNING", "true").lower() in ("1", "true", "yes")


def seeded_policy() -> Dict[str, Any]:
    """The env-seeded policy — also the cold-start and kill-switch answer."""
    return {
        "min_sessions": int(os.getenv("ATOM_PROMOTION_MIN_TRAINING_SESSIONS", "3")),
        "min_episodes": int(os.getenv("ATOM_PROMOTION_MIN_EPISODES", "10")),
        "min_success_ratio": float(os.getenv("ATOM_PROMOTION_MIN_SUCCESS_RATIO", "0.7")),
        "source": "seeded",
        "basis": {"reason": "no tuning evidence yet" if _dynamic_tuning_enabled() else "dynamic tuning disabled"},
    }


def _clamp(sessions: int, episodes: int, ratio: float) -> Dict[str, Any]:
    return {
        "min_sessions": max(_SESSIONS_MIN, min(_SESSIONS_MAX, int(sessions))),
        "min_episodes": max(_EPISODES_MIN, min(_EPISODES_MAX, int(episodes))),
        "min_success_ratio": round(max(_RATIO_MIN, min(_RATIO_MAX, float(ratio))), 2),
    }


def get_promotion_policy(db, domain: Optional[str]) -> Dict[str, Any]:
    """Tuned STUDENT→INTERN promotion policy for a domain.

    Deterministic from history: seeds until the domain has enough promoted
    agents, then eases/tightens asymmetrically from their post-promotion
    episode record. Never raises.
    """
    policy = seeded_policy()
    domain = (domain or "").lower().strip()
    if not domain or not _dynamic_tuning_enabled() or db is None:
        return policy

    try:
        from core.models import AgentEpisode, AgentRegistry, AgentStatus

        # Promoted agents in this domain (INTERN and above).
        promoted = (
            db.query(AgentRegistry)
            .filter(
                func_lower_category(db, domain),
                AgentRegistry.status.in_([
                    AgentStatus.INTERN.value,
                    AgentStatus.SUPERVISED.value,
                    AgentStatus.AUTONOMOUS.value,
                ]),
            )
            .all()
        )
        # Enough post-promotion evidence per agent before it counts.
        sample: List[Dict[str, Any]] = []
        for agent in promoted:
            episodes = (
                db.query(AgentEpisode)
                .filter(AgentEpisode.agent_id == agent.id)
                .count()
            )
            if episodes < _MIN_EPISODES_PER_AGENT:
                continue
            successes = (
                db.query(AgentEpisode)
                .filter(
                    AgentEpisode.agent_id == agent.id,
                    AgentEpisode.outcome == "success",
                )
                .count()
            )
            sample.append({
                "agent_id": agent.id,
                "episodes": episodes,
                "success_ratio": successes / episodes if episodes else 0.0,
            })

        if len(sample) < _MIN_PROMOTED_SAMPLE:
            policy["basis"] = {
                "reason": (
                    f"seeded — {len(sample)}/{_MIN_PROMOTED_SAMPLE} promoted "
                    f"{domain} agents with >= {_MIN_EPISODES_PER_AGENT} episodes"
                ),
                "sample_size": len(sample),
            }
            return policy

        domain_ratio = sum(s["success_ratio"] for s in sample) / len(sample)
        seed_ratio = policy["min_success_ratio"]

        if domain_ratio < seed_ratio:
            # Domain graduates underperforming the bar → tighten (fast).
            tuned = _clamp(
                policy["min_sessions"] + 1,
                policy["min_episodes"] + 5,
                seed_ratio + 0.05,
            )
            mode = _TUNE_TIGHTEN
        elif domain_ratio >= _STRONG_DOMAIN_RATIO:
            # Domain graduates reliably strong → ease (slowly).
            tuned = _clamp(
                policy["min_sessions"] - 1,
                policy["min_episodes"] * 0.8,
                seed_ratio - 0.05,
            )
            mode = _TUNE_EASE
        else:
            tuned = _clamp(policy["min_sessions"], policy["min_episodes"], seed_ratio)
            mode = "hold"

        policy.update(tuned)
        policy["source"] = f"tuned:{mode}"
        policy["basis"] = {
            "domain": domain,
            "promoted_agents_sampled": len(sample),
            "domain_post_promotion_success_ratio": round(domain_ratio, 3),
        }
        return policy
    except Exception as e:
        logger.debug(f"promotion policy tuning fell back to seed: {e}")
        policy["basis"] = {"reason": f"tuning error, seeded: {e}"}
        return policy


def func_lower_category(db, domain: str):
    """SQL filter: lower(agent_registry.category) == domain."""
    from sqlalchemy import func

    from core.models import AgentRegistry

    return func.lower(AgentRegistry.category) == domain
