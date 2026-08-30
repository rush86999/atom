"""
Policy-based graduation gating.

A GovernancePolicy declares evidence floors (``rules``) for a graduation
action; the engine DENIES when any rule is violated by the supplied
context. Rules are matched against context keys 1:1 by name (see
``_RULE_KEYS``); a rule whose context key is absent counts as violated —
an evidence gate must not pass on missing evidence.

Default policies (registered by ``PolicyEngine(include_defaults=True)``)
are DERIVED from ``ReadinessThresholds`` and the per-level minimum episode
counts in ``EpisodeService``, so the policy layer cannot drift from the
exam's own gates. This module was reintroduced 2026-08-30 scoped to
graduation decisions and wired into ``GraduationExamService.conduct_exam``
and ``AgentGraduationService.promote_agent`` — the version deleted
2026-08-20 was removed because it was never wired into any live path.
"""

import re
from enum import Enum
from typing import Any, Dict, List, Optional

from core.episode_service import ReadinessThresholds


class PolicyPriority(str, Enum):
    """Policy precedence when multiple policies match one action."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_PRIORITY_ORDER = {
    PolicyPriority.LOW: 0,
    PolicyPriority.MEDIUM: 1,
    PolicyPriority.HIGH: 2,
    PolicyPriority.CRITICAL: 3,
}

# condition strings support exactly `action == '<name>'` (optionally double
# quoted). Anything else is treated as a literal action-name match.
_ACTION_CONDITION_RE = re.compile(r"^action\s*==\s*['\"]([^'\"]+)['\"]$")

# rule name -> context key the caller supplies. min_episodes counts
# episodes and intervention rates are named without the min/max prefix at
# call sites (matching the documented PolicyEngine usage); everything
# else maps 1:1 by name.
_RULE_TO_CONTEXT_KEY = {
    "min_episodes": "episode_count",
    "max_intervention_rate": "intervention_rate",
    "min_constitutional_score": "constitutional_score",
    "min_readiness_score": "readiness_score",
    "min_success_rate": "success_rate",
    "min_confidence_score": "confidence_score",
}


class GovernancePolicy:
    """One declarative gate over a graduation action's evidence."""

    def __init__(
        self,
        policy_id: str,
        priority: PolicyPriority = PolicyPriority.MEDIUM,
        condition: str = "",
        effect: str = "DENY",
        layer: str = "strategic",
        rules: Optional[Dict[str, float]] = None,
        description: str = "",
    ):
        self.policy_id = policy_id
        self.priority = priority if isinstance(priority, PolicyPriority) else PolicyPriority(priority)
        self.condition = condition
        self.effect = effect.upper()
        self.layer = layer.lower()
        self.rules = dict(rules or {})
        self.description = description

    def matches(self, action: str, layer: str) -> bool:
        """Whether this policy applies to (action, layer)."""
        match = _ACTION_CONDITION_RE.match((self.condition or "").strip())
        if match:
            action_ok = match.group(1) == action
        else:
            action_ok = not self.condition or self.condition == action
        return action_ok and self.layer == (layer or "").lower()

    def violated_rules(self, context: Dict[str, Any]) -> List[str]:
        """Human-readable reasons for every rule the context fails."""
        reasons: List[str] = []
        for rule, floor in sorted(self.rules.items()):
            key = _RULE_TO_CONTEXT_KEY.get(rule, rule)
            value = context.get(key)
            if value is None:
                reasons.append(f"{key} not provided (required: {rule} {floor})")
            elif rule.startswith("max_") and float(value) > float(floor):
                reasons.append(f"{key} {float(value):.4g} exceeds {rule} {floor}")
            elif rule.startswith("min_") and float(value) < float(floor):
                reasons.append(f"{key} {float(value):.4g} below {rule} {floor}")
        return reasons

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "priority": self.priority.value,
            "condition": self.condition,
            "effect": self.effect,
            "layer": self.layer,
            "rules": self.rules,
            "description": self.description,
        }


class PolicyEvaluationResult:
    """Outcome of evaluating every policy matching one request."""

    def __init__(
        self,
        decision: str,
        reasons: List[str],
        policies_evaluated: List[Dict[str, Any]],
    ):
        self.decision = decision  # "allow" | "deny"
        self.reasons = reasons
        self.policies_evaluated = policies_evaluated

    @property
    def allowed(self) -> bool:
        return self.decision == "allow"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "reasons": self.reasons,
            "policies_evaluated": self.policies_evaluated,
        }


def default_graduation_policies() -> List[GovernancePolicy]:
    """Graduation policies mirroring the exam's own gates.

    Derived from ReadinessThresholds (overall + per-component floors) and
    EpisodeService's per-level minimum episode counts — single source, no
    drift. max_intervention_rate is the complement of the
    zero_intervention_ratio threshold.
    """
    def _min_episodes(target: str) -> int:
        return {
            "intern": 10,
            "supervised": 25,
            "autonomous": 50,
        }.get(target, 10)

    specs = (
        # (action suffix, layer, threshold dict, description)
        (
            "intern",
            "operational",
            ReadinessThresholds.STUDENT_TO_INTERN,
            "Routine student→intern gate — automated",
        ),
        (
            "supervised",
            "tactical",
            ReadinessThresholds.INTERN_TO_SUPERVISED,
            "Intern→supervised gate — adaptive policy review",
        ),
        (
            "autonomous",
            "strategic",
            ReadinessThresholds.SUPERVISED_TO_AUTONOMOUS,
            "Critical supervised→autonomous gate — human-in-the-loop",
        ),
    )
    policies = []
    for suffix, layer, thresholds, description in specs:
        rules = {
            "min_readiness_score": thresholds["overall"],
            "min_episodes": _min_episodes(suffix),
            "min_success_rate": thresholds["success_rate"],
            "min_constitutional_score": thresholds["constitutional_score"],
            "max_intervention_rate": round(1.0 - thresholds["zero_intervention_ratio"], 4),
            "min_confidence_score": thresholds["confidence_score"],
        }
        policies.append(GovernancePolicy(
            policy_id=f"graduation_policy_{suffix}",
            priority=PolicyPriority.HIGH if layer != "strategic" else PolicyPriority.CRITICAL,
            condition=f"action == 'graduate_to_{suffix}'",
            effect="DENY",
            layer=layer,
            rules=rules,
            description=description,
        ))
    return policies


class PolicyEngine:
    """Registers and evaluates governance policies.

    ``include_defaults=True`` seeds the graduation policies above; pass
    ``False`` for a clean engine (tests, custom rule sets). Unregulated
    actions (no matching policy) are ALLOWED — the engine gates known
    graduation transitions, it does not deny by default.
    """

    def __init__(self, include_defaults: bool = True):
        self._policies: List[GovernancePolicy] = []
        if include_defaults:
            for policy in default_graduation_policies():
                self.register_policy(policy)

    def register_policy(self, policy: GovernancePolicy) -> None:
        existing = [p for p in self._policies if p.policy_id == policy.policy_id]
        if existing:
            raise ValueError(f"Policy '{policy.policy_id}' is already registered")
        self._policies.append(policy)
        self._policies.sort(key=lambda p: _PRIORITY_ORDER[p.priority], reverse=True)

    def unregister_policy(self, policy_id: str) -> bool:
        before = len(self._policies)
        self._policies = [p for p in self._policies if p.policy_id != policy_id]
        return len(self._policies) < before

    def evaluate(
        self,
        agent_id: str,
        action: str,
        layer: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> PolicyEvaluationResult:
        """Evaluate every policy matching (action, layer).

        DENY wins: if ANY matching DENY policy has a violated rule the
        request is denied, with the violated reasons aggregated across all
        matching DENY policies (highest priority first). Matching policies
        whose rules all hold, ALLOW policies, and actions with no matching
        policy all result in "allow".
        """
        ctx = dict(context or {})
        matching = [p for p in self._policies if p.matches(action, layer)]

        if not matching:
            return PolicyEvaluationResult(
                decision="allow",
                reasons=[f"no policy regulates action '{action}' at layer '{layer}'"],
                policies_evaluated=[],
            )

        evaluated: List[Dict[str, Any]] = []
        denied_reasons: List[str] = []
        for policy in matching:
            reasons = policy.violated_rules(ctx)
            evaluated.append({
                "policy_id": policy.policy_id,
                "effect": policy.effect,
                "violated": bool(reasons),
                "reasons": reasons,
            })
            if policy.effect == "DENY" and reasons:
                denied_reasons.extend(reasons)

        if denied_reasons:
            return PolicyEvaluationResult(
                decision="deny",
                reasons=list(dict.fromkeys(denied_reasons)),  # dedupe, keep order
                policies_evaluated=evaluated,
            )

        return PolicyEvaluationResult(
            decision="allow",
            reasons=[],
            policies_evaluated=evaluated,
        )
