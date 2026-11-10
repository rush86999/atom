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

import hashlib
import json
import logging
import os
from typing import Any, Dict, List, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    ValidationError,
    field_validator,
    model_validator,
)

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


# ===========================================================================
# Scoped capability-qualification policy (owner-administered, strict)
# ===========================================================================

ASSESSMENT_POLICY_KEY = "ATOM_GRADUATION_ASSESSMENT_POLICY"
ASSESSMENT_POLICY_SCHEMA = "atom-graduation-assessment-policy-1"


class AssessmentPolicyError(Exception):
    """A present-but-invalid policy is configuration_required, never off."""

    def __init__(self, state: str, message: str):
        super().__init__(message)
        self.state = state
        self.message = message


class _ScopedException(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed: StrictBool = False
    agent_ids: List[StrictStr] = Field(default_factory=list)
    domains: List[StrictStr] = Field(default_factory=list)
    reason: Optional[StrictStr] = None

    @model_validator(mode="after")
    def _reason_required_when_allowed(self):
        if self.allowed:
            if not isinstance(self.reason, str) or not self.reason.strip():
                raise ValueError(
                    "an enabled owner exception requires a nonblank reason")
        return self


class _LegacyException(_ScopedException):
    state: Literal["legacy_unassessed"] = "legacy_unassessed"


class _ManualException(_ScopedException):
    state: Literal["manual_override"] = "manual_override"


class _SystemException(_ScopedException):
    state: Literal["system_exempt"] = "system_exempt"


class AssessmentExceptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legacy: _LegacyException = Field(default_factory=_LegacyException)
    manual: _ManualException = Field(default_factory=_ManualException)
    system: _SystemException = Field(default_factory=_SystemException)


class AssessmentTiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intern: StrictBool = True
    supervised: StrictBool = True
    autonomous: StrictBool = True


class RubricCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrictStr = Field(min_length=1, max_length=80)
    label: StrictStr = Field(min_length=1, max_length=200)

    @field_validator("id", "label")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("rubric criterion id/label must be nonblank")
        return value


DEFAULT_RUBRIC_CRITERIA = [
    {"id": "task_context",
     "label": "Task/context is inspectable and scoped to this agent and tier"},
    {"id": "actual_output",
     "label": "Actual durable output is present and reviewable"},
    {"id": "scope",
     "label": "Evidence matches the exact tenant/workspace/policy/source"},
    {"id": "safety",
     "label": "No unresolved safety or compliance violations"},
]


class AssessmentPolicy(BaseModel):
    """Strict owner policy for new upward graduation transitions.

    Absence of the setting returns this strict default: every new upward
    transition requires a passed scoped capability qualification. Exceptions
    are opt-in, agent/domain scoped, and never claim qualification.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[ASSESSMENT_POLICY_SCHEMA] = ASSESSMENT_POLICY_SCHEMA
    revision: StrictStr = Field(default="1", min_length=1, max_length=80)
    default_required: StrictBool = True
    tiers: AssessmentTiers = Field(default_factory=AssessmentTiers)
    exceptions: AssessmentExceptions = Field(default_factory=AssessmentExceptions)
    evaluator: Literal["human_review"] = "human_review"
    rubric_version: StrictStr = Field(default="heldout-v1", min_length=1, max_length=80)
    rubric_criteria: List[RubricCriterion] = Field(
        default_factory=lambda: [RubricCriterion(**item)
                                 for item in DEFAULT_RUBRIC_CRITERIA])
    source_revision: StrictStr = Field(
        default="agent-evidence-v1", min_length=1, max_length=120)

    @field_validator("revision", "rubric_version", "source_revision")
    @classmethod
    def _nonblank_identity(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("policy identity fields must be nonblank")
        return value

    def tier_required(self, target_level: str) -> bool:
        tier = str(target_level or "").strip().lower()
        if tier not in ("intern", "supervised", "autonomous"):
            # Unknown target must not silently become not-required.
            return True
        return bool(getattr(self.tiers, tier))

    def scoped_exception(self, kind: str, agent: Any) -> Optional[Any]:
        """Return an exception only for an explicit owner-listed agent id.

        ``agent.category``/name/model metadata are mutable and are NEVER
        consulted for an exemption. An empty agent_ids list means no
        exemption, not allow-all; the owner must name the exact agents.
        """
        exc = getattr(self.exceptions, kind, None)
        if exc is None or not exc.allowed:
            return None
        ids = {str(item) for item in exc.agent_ids}
        agent_id = str(getattr(agent, "id", "") or "")
        if not ids or not agent_id:
            return None
        return exc if agent_id in ids else None


DEFAULT_ASSESSMENT_POLICY: Dict[str, Any] = AssessmentPolicy().model_dump()


def get_assessment_policy(db: Any = None) -> Dict[str, Any]:
    """Resolve the strict owner policy through env > runtime_settings > default.

    A present-but-malformed env/DB value raises AssessmentPolicyError with
    state='configuration_required'. It never degrades to not-required.
    """
    from core.runtime_settings import StrictSettingError, resolve_setting_strict

    try:
        resolved = resolve_setting_strict(
            ASSESSMENT_POLICY_KEY, db=db, fresh=True)
    except StrictSettingError as exc:
        raise AssessmentPolicyError(
            "configuration_required",
            f"{ASSESSMENT_POLICY_KEY} is unreadable or invalid: {exc}",
        ) from exc
    raw = resolved.value
    try:
        policy = AssessmentPolicy.model_validate(raw)
    except ValidationError as exc:
        raise AssessmentPolicyError(
            "configuration_required",
            f"{ASSESSMENT_POLICY_KEY} failed strict validation: {exc}",
        ) from exc
    digest = hashlib.sha256(
        json.dumps(policy.model_dump(), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        "policy": policy,
        "revision": policy.revision,
        "digest": digest,
        "source": resolved.source,
        "row_updated_at": resolved.row_updated_at,
        "raw_value": resolved.value,
        "env_raw": (
            os.environ.get(ASSESSMENT_POLICY_KEY)
            if resolved.source == "env" else None),
        "schema_version": policy.schema_version,
    }
