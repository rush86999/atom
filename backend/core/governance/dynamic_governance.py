"""
Three-layer governance for graduation decisions.

Layers (mapped from the graduation doc's contract):
- OPERATIONAL — routine graduation checks (student→intern), automated.
- TACTICAL — graduation with policy review (intern→supervised), adaptive.
- STRATEGIC — critical promotions (supervised→autonomous),
  human-in-the-loop: even when every policy passes, the decision requires
  human approval; automated callers must withhold the promotion and a
  supervisor completes it (AgentGraduationService.promote_agent /
  GraduationExamService.promote_agent_manually).

``DynamicGovernanceManager.decide`` evaluates the policy engine at the
requested layer and flags ``requires_human`` for STRATEGIC approvals.
This is the reintroduced (2026-08-30) graduation-scoped version — wired
into GraduationExamService.conduct_exam and
AgentGraduationService.promote_agent, unlike the general-purpose version
deleted 2026-08-20 for having no live wiring.
"""

from enum import Enum
from typing import Any, Dict, Optional

from core.governance.policy_engine import PolicyEngine


class GovernanceLayer(str, Enum):
    OPERATIONAL = "operational"
    TACTICAL = "tactical"
    STRATEGIC = "strategic"


_LAYER_FOR_ACTION = {
    "graduate_to_intern": GovernanceLayer.OPERATIONAL,
    "graduate_to_supervised": GovernanceLayer.TACTICAL,
    "graduate_to_autonomous": GovernanceLayer.STRATEGIC,
}


def layer_for_action(action: str) -> GovernanceLayer:
    """Canonical layer for a graduation action.

    Unknown graduation actions default to TACTICAL (policy review) — never
    silently OPERATIONAL, which would bypass review for typos/new tiers.
    """
    return _LAYER_FOR_ACTION.get(action, GovernanceLayer.TACTICAL)


class GovernanceDecision:
    """Outcome of one governance decision request."""

    def __init__(
        self,
        agent_id: str,
        action: str,
        layer: GovernanceLayer,
        allowed: bool,
        requires_human: bool,
        reasons,
        policy_results,
    ):
        self.agent_id = agent_id
        self.action = action
        self.layer = layer
        self.allowed = allowed
        self.requires_human = requires_human
        self.reasons = list(reasons)
        self.policy_results = policy_results

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "action": self.action,
            "layer": self.layer.value,
            "allowed": self.allowed,
            "requires_human": self.requires_human,
            "reasons": self.reasons,
            "policy_results": self.policy_results,
        }


class DynamicGovernanceManager:
    """Routes a graduation request through the policy engine per layer."""

    def __init__(self, engine: Optional[PolicyEngine] = None):
        self.engine = engine or PolicyEngine()

    def decide(
        self,
        agent_id: str,
        action: str,
        layer: Optional[GovernanceLayer] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> GovernanceDecision:
        """Decide a graduation action at a governance layer.

        - Policies denied → ``allowed=False`` with per-rule reasons.
        - Policies passed at STRATEGIC → ``allowed=True`` AND
          ``requires_human=True`` — the human approval IS the gate.
        - Policies passed at OPERATIONAL/TACTICAL → automated allow.
        """
        resolved_layer = layer if isinstance(layer, GovernanceLayer) else (
            GovernanceLayer(str(layer).lower()) if layer else layer_for_action(action)
        )
        result = self.engine.evaluate(
            agent_id=agent_id,
            action=action,
            layer=resolved_layer.value,
            context=context,
        )
        allowed = result.allowed
        requires_human = allowed and resolved_layer is GovernanceLayer.STRATEGIC
        return GovernanceDecision(
            agent_id=agent_id,
            action=action,
            layer=resolved_layer,
            allowed=allowed,
            requires_human=requires_human,
            reasons=result.reasons,
            policy_results=result.policies_evaluated,
        )
