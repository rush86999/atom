"""
Dynamic Governance Adjustment with Three-Layer Architecture

Based on 2025-2026 research:
- Governance-as-a-Service: Multi-Agent Framework (arXiv:2508.18765v1)
- From Anarchy to Assembly: Governance Survey

Implements:
- Three-layer governance (Operational, Tactical, Strategic)
- Dynamic governance adjustment based on performance
- Policy-based decision making
- Adaptive governance thresholds
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Configuration
# ============================================================================

class GovernanceLayer(Enum):
    """Layers of the three-tier governance architecture"""
    OPERATIONAL = "operational"  # Day-to-day permissions (STUDENT/INTERN/SUPERVISED/AUTONOMOUS)
    TACTICAL = "tactical"  # Policy-based decisions (feature access, resource limits)
    STRATEGIC = "strategic"  # Long-term strategy (agent creation, governance policies)


class DecisionType(Enum):
    """Types of governance decisions"""
    PERMISSION = "permission"  # Can agent perform action?
    LIMIT = "limit"  # Resource limit adjustment
    ESCALATION = "escalation"  # Maturity level change
    POLICY = "policy"  # Governance policy change
    CREATION = "creation"  # Agent/skill creation approval


class DecisionOutcome(Enum):
    """Possible outcomes of governance decision"""
    ALLOW = "allow"
    DENY = "deny"
    ALLOW_WITH_CONDITIONS = "allow_with_conditions"
    ESCALATE = "escalate"
    DEFER = "defer"


@dataclass
class GovernanceConfig:
    """Configuration for dynamic governance"""
    # Operational layer
    maturity_based: bool = True
    action_complexity_gating: bool = True
    real_time_monitoring: bool = True

    # Tactical layer
    policy_based_decisions: bool = True
    resource_limits: bool = True
    feature_flags: bool = True

    # Strategic layer
    auto_graduation: bool = True
    policy_evolution: bool = True
    learning_from_feedback: bool = True

    # Adaptation
    adaptation_interval_hours: int = 24
    min_confidence_for_auto_decision: float = 0.8
    human_intervention_threshold: float = 0.5

    # Feedback
    feedback_integration: bool = True
    feedback_weight: float = 0.3


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class GovernanceDecision:
    """A governance decision"""
    decision_id: str = ""
    layer: GovernanceLayer = GovernanceLayer.OPERATIONAL
    decision_type: DecisionType = DecisionType.PERMISSION

    # Request
    agent_id: str = ""
    action: str = ""
    resource: str = ""
    context: Dict[str, Any] = field(default_factory=dict)

    # Outcome
    outcome: DecisionOutcome = DecisionOutcome.ALLOW
    confidence: float = 1.0
    reasoning: str = ""

    # Conditions
    conditions: List[str] = field(default_factory=list)
    required_approvals: List[str] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = "system"  # system, human, or specific service
    expires_at: Optional[datetime] = None

    def is_allowed(self) -> bool:
        """Check if decision allows action"""
        return self.outcome in [DecisionOutcome.ALLOW, DecisionOutcome.ALLOW_WITH_CONDITIONS]

    def requires_approval(self) -> bool:
        """Check if decision requires human approval"""
        return len(self.required_approvals) > 0 or self.confidence < 0.8


@dataclass
class LayerMetrics:
    """Metrics for a governance layer"""
    layer: GovernanceLayer = GovernanceLayer.OPERATIONAL

    # Decisions
    total_decisions: int = 0
    allowed_decisions: int = 0
    denied_decisions: int = 0
    escalated_decisions: int = 0

    # Performance
    avg_decision_time_ms: float = 0.0
    avg_confidence: float = 0.0

    # Adaptation
    adaptations_made: int = 0
    last_adaptation_at: Optional[datetime] = None


@dataclass
class GovernancePolicy:
    """A governance policy"""
    policy_id: str = ""
    name: str = ""
    layer: GovernanceLayer = GovernanceLayer.TACTICAL
    description: str = ""

    # Rules
    rules: List[str] = field(default_factory=list)

    # Conditions
    applies_to: Dict[str, Any] = field(default_factory=dict)  # Agent filters
    applies_to_actions: List[str] = field(default_factory=list)
    applies_to_layers: List[str] = field(default_factory=list)

    # Outcome
    default_outcome: DecisionOutcome = DecisionOutcome.ALLOW
    conditions: List[str] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    version: int = 1
    active: bool = True


# ============================================================================
# Three-Layer Governance
# ============================================================================

class ThreeLayerGovernance:
    """
    Three-layer governance architecture.

    Layers:
    1. Operational: Real-time permission decisions based on maturity
    2. Tactical: Policy-based decisions for resource management
    3. Strategic: Long-term governance and auto-graduation
    """

    def __init__(self):
        self.layers: Dict[GovernanceLayer, Any] = {}
        self.layer_metrics: Dict[GovernanceLayer, LayerMetrics] = {}
        self.policies: Dict[str, GovernancePolicy] = {}

        # Initialize layer metrics
        for layer in GovernanceLayer:
            self.layer_metrics[layer] = LayerMetrics(layer=layer)

    def decide(
        self,
        layer: GovernanceLayer,
        agent_id: str,
        action: str,
        context: Dict[str, Any]
    ) -> GovernanceDecision:
        """Make a governance decision at specified layer"""
        decision = GovernanceDecision(
            decision_id=f"dec_{uuid.uuid4().hex[:16]}",
            layer=layer,
            agent_id=agent_id,
            action=action,
            context=context,
            created_at=datetime.now()
        )

        # Route to appropriate decision logic
        if layer == GovernanceLayer.OPERATIONAL:
            self._operational_decision(decision)
        elif layer == GovernanceLayer.TACTICAL:
            self._tactical_decision(decision)
        elif layer == GovernanceLayer.STRATEGIC:
            self._strategic_decision(decision)
        else:
            decision.outcome = DecisionOutcome.DENY
            decision.reasoning = "Unknown governance layer"

        # Update metrics
        metrics = self.layer_metrics[layer]
        metrics.total_decisions += 1
        if decision.outcome == DecisionOutcome.ALLOW:
            metrics.allowed_decisions += 1
        elif decision.outcome == DecisionOutcome.DENY:
            metrics.denied_decisions += 1
        elif decision.outcome == DecisionOutcome.ESCALATE:
            metrics.escalated_decisions += 1

        return decision

    def _operational_decision(self, decision: GovernanceDecision) -> None:
        """Make operational (maturity-based) decision"""
        maturity = decision.context.get("maturity", "STUDENT")
        complexity = decision.context.get("complexity", 1)

        # Action complexity gating
        complexity_map = {
            "STUDENT": 1,
            "INTERN": 2,
            "SUPERVISED": 3,
            "AUTONOMOUS": 4
        }

        max_complexity = complexity_map.get(maturity, 1)

        if complexity <= max_complexity:
            decision.outcome = DecisionOutcome.ALLOW
            decision.confidence = 0.9
            decision.reasoning = f"Maturity {maturity} allows complexity {complexity}"
        else:
            decision.outcome = DecisionOutcome.ESCALATE
            decision.confidence = 0.95
            decision.reasoning = f"Maturity {maturity} insufficient for complexity {complexity}"

    def _tactical_decision(self, decision: GovernanceDecision) -> None:
        """Make tactical (policy-based) decision"""
        # Check applicable policies
        for policy in self.policies.values():
            if not policy.active:
                continue
            if policy.layer != GovernanceLayer.TACTICAL:
                continue

            # Check if policy applies
            if self._policy_applies(policy, decision):
                decision.outcome = policy.default_outcome
                decision.conditions = policy.conditions
                decision.reasoning = f"Policy {policy.name} applied"
                return

        # Default: allow if no policy blocks
        decision.outcome = DecisionOutcome.ALLOW
        decision.confidence = 0.7
        decision.reasoning = "No applicable tactical policies"

    def _strategic_decision(self, decision: GovernanceDecision) -> None:
        """Make strategic (long-term) decision"""
        decision_type = decision.decision_type

        if decision_type == DecisionType.ESCALATION:
            # Maturity escalation
            current_maturity = decision.context.get("current_maturity", "STUDENT")
            performance = decision.context.get("performance_score", 0.5)

            maturity_order = ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]
            try:
                current_idx = maturity_order.index(current_maturity)
            except ValueError:
                current_idx = 0

            if performance > 0.9 and current_idx < len(maturity_order) - 1:
                decision.outcome = DecisionOutcome.ALLOW
                decision.conditions = [
                    f"Escalate to {maturity_order[current_idx + 1]}",
                    "Update governance records"
                ]
            else:
                decision.outcome = DecisionOutcome.DENY
                decision.reasoning = "Insufficient performance for escalation"

        elif decision_type == DecisionType.POLICY:
            # Policy creation or modification
            decision.outcome = DecisionOutcome.ALLOW_WITH_CONDITIONS
            decision.conditions = [
                "Policy review required",
                "Stakeholder approval"
            ]
            decision.confidence = 0.6

        else:
            decision.outcome = DecisionOutcome.ALLOW
            decision.confidence = 0.5
            decision.reasoning = "Strategic decision type not specified"

    def _policy_applies(self, policy: GovernancePolicy, decision: GovernanceDecision) -> bool:
        """Check if policy applies to decision"""
        # Check action filter
        if policy.applies_to_actions and decision.action not in policy.applies_to_actions:
            return False

        # Check agent filters
        if policy.applies_to:
            for key, value in policy.applies_to.items():
                if decision.context.get(key) != value:
                    return False

        return True

    def add_policy(self, policy: GovernancePolicy) -> None:
        """Add a governance policy"""
        self.policies[policy.policy_id] = policy
        logger.info(f"Added governance policy: {policy.policy_id}")

    def remove_policy(self, policy_id: str) -> bool:
        """Remove a governance policy"""
        if policy_id in self.policies:
            del self.policies[policy_id]
            logger.info(f"Removed governance policy: {policy_id}")
            return True
        return False

    def get_layer_metrics(self, layer: GovernanceLayer) -> LayerMetrics:
        """Get metrics for a governance layer"""
        return self.layer_metrics.get(layer, LayerMetrics(layer=layer))


# ============================================================================
# Dynamic Governance Manager
# ============================================================================

class DynamicGovernanceManager:
    """
    Manages dynamic governance adjustment.

    Features:
    - Three-layer governance coordination
    - Performance-based adaptation
    - Policy evolution
    - Human-in-the-loop decisions
    """

    def __init__(self, config: Optional[GovernanceConfig] = None):
        self.config = config or GovernanceConfig()
        self.governance = ThreeLayerGovernance()

        # Performance tracking
        self._performance_history: Dict[str, List[float]] = defaultdict(list)
        self._feedback_history: Dict[str, List[float]] = defaultdict(list)

        # Adaptation tracking
        self._adaptations: List[Dict[str, Any]] = []

        # Human intervention queue
        self._intervention_queue: List[GovernanceDecision] = []
        self._intervention_results: Dict[str, DecisionOutcome] = {}

        # Thread safety
        self._lock = threading.RLock()

    def decide(
        self,
        agent_id: str,
        action: str,
        context: Dict[str, Any],
        layer: Optional[GovernanceLayer] = None
    ) -> GovernanceDecision:
        """Make a governance decision"""
        with self._lock:
            # Determine layer
            if not layer:
                layer = self._determine_layer(context)

            # Get decision from governance
            decision = self.governance.decide(layer, agent_id, action, context)

            # Check confidence for human intervention
            if decision.confidence < self.config.human_intervention_threshold:
                decision.required_approvals.append("human_review")
                self._intervention_queue.append(decision)

            # Log decision for learning
            self._record_decision(decision)

            return decision

    def _determine_layer(self, context: Dict[str, Any]) -> GovernanceLayer:
        """Determine appropriate governance layer"""
        decision_type = context.get("decision_type", DecisionType.PERMISSION)

        if decision_type in [DecisionType.ESCALATION, DecisionType.CREATION, DecisionType.POLICY]:
            return GovernanceLayer.STRATEGIC
        elif decision_type in [DecisionType.LIMIT, DecisionType.POLICY]:
            return GovernanceLayer.TACTICAL
        else:
            return GovernanceLayer.OPERATIONAL

    def record_performance(self, agent_id: str, score: float) -> None:
        """Record performance score for agent"""
        self._performance_history[agent_id].append(score)

        # Trigger adaptation if enough data
        if len(self._performance_history[agent_id]) >= 100:
            self._consider_adaptation(agent_id)

    def record_feedback(self, agent_id: str, feedback_score: float) -> None:
        """Record feedback for agent"""
        self._feedback_history[agent_id].append(feedback_score)

    def _consider_adaptation(self, agent_id: str) -> None:
        """Consider governance adaptation based on performance"""
        scores = self._performance_history[agent_id]
        if not scores:
            return

        avg_score = sum(scores[-100:]) / min(len(scores), 100)

        # High performance - consider escalation
        if avg_score > 0.95:
            self._suggest_adaptation(
                agent_id=agent_id,
                adaptation_type="escalation",
                reason=f"High performance score: {avg_score:.2f}"
            )

        # Low performance - consider intervention
        elif avg_score < 0.6:
            self._suggest_adaptation(
                agent_id=agent_id,
                adaptation_type="intervention",
                reason=f"Low performance score: {avg_score:.2f}"
            )

    def _suggest_adaptation(
        self,
        agent_id: str,
        adaptation_type: str,
        reason: str
    ) -> None:
        """Suggest governance adaptation"""
        adaptation = {
            "agent_id": agent_id,
            "adaptation_type": adaptation_type,
            "reason": reason,
            "created_at": datetime.now().isoformat(),
            "status": "pending"
        }
        self._adaptations.append(adaptation)
        logger.info(f"Suggested adaptation: {adaptation_type} for {agent_id} - {reason}")

    def get_intervention_queue(self) -> List[GovernanceDecision]:
        """Get pending human intervention decisions"""
        return self._intervention_queue.copy()

    def resolve_intervention(
        self,
        decision_id: str,
        outcome: DecisionOutcome
    ) -> bool:
        """Resolve a human intervention"""
        # Find decision
        for i, decision in enumerate(self._intervention_queue):
            if decision.decision_id == decision_id:
                self._intervention_results[decision_id] = outcome
                self._intervention_queue.pop(i)
                logger.info(f"Resolved intervention: {decision_id} -> {outcome.value}")
                return True
        return False

    def _record_decision(self, decision: GovernanceDecision) -> None:
        """Record decision for learning"""
        # In production, persist to database
        pass

    def get_statistics(self) -> Dict[str, Any]:
        """Get governance statistics"""
        with self._lock:
            return {
                "total_interventions": len(self._intervention_queue) + len(self._intervention_results),
                "pending_interventions": len(self._intervention_queue),
                "resolved_interventions": len(self._intervention_results),
                "adaptations_suggested": len(self._adaptations),
                "performance_tracked": len(self._performance_history),
                "feedback_tracked": len(self._feedback_history),
                "layer_metrics": {
                    layer.value: {
                        "total_decisions": metrics.total_decisions,
                        "allowed": metrics.allowed_decisions,
                        "denied": metrics.denied_decisions,
                        "escalated": metrics.escalated_decisions
                    }
                    for layer, metrics in self.governance.layer_metrics.items()
                }
            }


# ============================================================================
# Factory
# ============================================================================

_governance_manager_instance: Optional[DynamicGovernanceManager] = None


def get_governance_manager(config: Optional[GovernanceConfig] = None) -> DynamicGovernanceManager:
    """Get or create governance manager instance"""
    global _governance_manager_instance
    if _governance_manager_instance is None:
        _governance_manager_instance = DynamicGovernanceManager(config)
    return _governance_manager_instance


# Import uuid for unique IDs
import uuid
