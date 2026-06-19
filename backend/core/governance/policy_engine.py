"""
Policy Engine for Governance Decisions

Based on 2025-2026 research:
- Governance-as-a-Service: Multi-Agent Framework (arXiv:2508.18765v1)

Implements:
- Policy rule definition and evaluation
- Context-based policy matching
- Policy composition and priority
- Policy versioning
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import re

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Configuration
# ============================================================================

class PolicyOperator(Enum):
    """Operators for policy rules"""
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    GREATER_EQUAL = "gte"
    LESS_EQUAL = "lte"
    IN = "in"
    NOT_IN = "nin"
    CONTAINS = "contains"
    MATCHES = "matches"  # Regex match
    EXISTS = "exists"


class PolicyPriority(Enum):
    """Priority levels for policies"""
    CRITICAL = 0  # Highest priority
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    ADVISORY = 4  # Lowest priority


@dataclass
class PolicyEngineConfig:
    """Configuration for policy engine"""
    # Evaluation
    short_circuit: bool = True  # Stop at first matching policy
    allow_overrides: bool = True  # Lower priority can override higher

    # Caching
    enable_cache: bool = True
    cache_ttl_seconds: int = 300
    max_cache_size: int = 1000

    # Monitoring
    log_evaluations: bool = True
    log_denials: bool = True


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class PolicyRule:
    """A rule within a policy"""
    rule_id: str = ""
    field: str = ""  # Field to check in context
    operator: PolicyOperator = PolicyOperator.EQUALS
    value: Any = None
    description: str = ""

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate rule against context"""
        field_value = context.get(self.field)

        try:
            if self.operator == PolicyOperator.EQUALS:
                return field_value == self.value
            elif self.operator == PolicyOperator.NOT_EQUALS:
                return field_value != self.value
            elif self.operator == PolicyOperator.GREATER_THAN:
                return isinstance(field_value, (int, float)) and field_value > self.value
            elif self.operator == PolicyOperator.LESS_THAN:
                return isinstance(field_value, (int, float)) and field_value < self.value
            elif self.operator == PolicyOperator.GREATER_EQUAL:
                return isinstance(field_value, (int, float)) and field_value >= self.value
            elif self.operator == PolicyOperator.LESS_EQUAL:
                return isinstance(field_value, (int, float)) and field_value <= self.value
            elif self.operator == PolicyOperator.IN:
                return field_value in self.value if isinstance(self.value, (list, tuple, set)) else False
            elif self.operator == PolicyOperator.NOT_IN:
                return field_value not in self.value if isinstance(self.value, (list, tuple, set)) else False
            elif self.operator == PolicyOperator.CONTAINS:
                return isinstance(field_value, str) and self.value in field_value
            elif self.operator == PolicyOperator.MATCHES:
                return isinstance(field_value, str) and bool(re.match(self.value, field_value))
            elif self.operator == PolicyOperator.EXISTS:
                return self.field in context
            else:
                logger.warning(f"Unknown operator: {self.operator}")
                return False

        except Exception as e:
            logger.warning(f"Rule evaluation failed: {e}")
            return False


@dataclass
class PolicyEvaluationResult:
    """Result of policy evaluation"""
    policy_id: str = ""
    matched: bool = False
    outcome: str = "allow"  # allow, deny, condition
    confidence: float = 1.0
    conditions: List[str] = field(default_factory=list)
    reasoning: str = ""

    # Evaluation metadata
    evaluated_at: datetime = None
    evaluation_time_ms: float = 0.0
    rules_evaluated: int = 0
    rules_matched: int = 0


@dataclass
class GovernancePolicy:
    """A governance policy"""
    policy_id: str = ""
    name: str = ""
    description: str = ""
    version: int = 1

    # Priority
    priority: PolicyPriority = PolicyPriority.MEDIUM

    # Rules
    rules: List[PolicyRule] = field(default_factory=list)
    match_all_rules: bool = True  # True: AND, False: OR

    # Scope
    agent_filter: Optional[Dict[str, Any]] = None  # Filter by agent properties
    action_filter: Optional[List[str]] = None  # Filter by actions
    layer_filter: Optional[List[str]] = None  # Filter by governance layers

    # Outcome
    outcome: str = "allow"  # allow, deny, condition
    conditions: List[str] = field(default_factory=list)
    confidence: float = 1.0

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    created_by: str = "system"
    active: bool = True
    tags: List[str] = field(default_factory=list)

    def matches_scope(self, agent_id: str, action: str, layer: str, context: Dict[str, Any]) -> bool:
        """Check if policy matches the scope"""
        # Check action filter
        if self.action_filter and action not in self.action_filter:
            return False

        # Check layer filter
        if self.layer_filter and layer not in self.layer_filter:
            return False

        # Check agent filter
        if self.agent_filter:
            for key, value in self.agent_filter.items():
                if context.get(key) != value:
                    return False

        return True

    def evaluate_rules(self, context: Dict[str, Any]) -> Tuple[bool, int]:
        """Evaluate policy rules"""
        if not self.rules:
            return True, 0

        matched_count = 0

        for rule in self.rules:
            if rule.evaluate(context):
                matched_count += 1
                if not self.match_all_rules:
                    # OR logic: one match is enough
                    return True, matched_count

        if self.match_all_rules:
            # AND logic: all must match
            return matched_count == len(self.rules), matched_count

        return False, matched_count


# ============================================================================
# Policy Engine
# ============================================================================

class PolicyEngine:
    """
    Engine for evaluating governance policies.

    Features:
    - Policy registration and management
    - Context-based policy evaluation
    - Priority-based resolution
    - Policy caching
    """

    def __init__(self, config: Optional[PolicyEngineConfig] = None):
        self.config = config or PolicyEngineConfig()

        # Policy storage
        self._policies: Dict[str, GovernancePolicy] = {}
        self._policy_cache: Dict[str, PolicyEvaluationResult] = {}

        # Indexes
        self._priority_index: Dict[PolicyPriority, List[str]] = {
            priority: [] for priority in PolicyPriority
        }
        self._tag_index: Dict[str, List[str]] = defaultdict(list)

    def register_policy(self, policy: GovernancePolicy) -> None:
        """Register a governance policy"""
        self._policies[policy.policy_id] = policy

        # Update indexes
        self._priority_index[policy.priority].append(policy.policy_id)
        for tag in policy.tags:
            self._tag_index[tag].append(policy.policy_id)

        logger.info(f"Registered policy: {policy.policy_id} (priority: {policy.priority.name})")

    def unregister_policy(self, policy_id: str) -> bool:
        """Unregister a policy"""
        if policy_id not in self._policies:
            return False

        policy = self._policies[policy_id]

        # Remove from indexes
        self._priority_index[policy.priority].remove(policy_id)
        for tag in policy.tags:
            if policy_id in self._tag_index[tag]:
                self._tag_index[tag].remove(policy_id)

        del self._policies[policy_id]

        # Clear cache
        self._clear_cache_for_policy(policy_id)

        logger.info(f"Unregistered policy: {policy_id}")
        return True

    def evaluate(
        self,
        agent_id: str,
        action: str,
        layer: str,
        context: Dict[str, Any],
        priority_limit: Optional[PolicyPriority] = None
    ) -> PolicyEvaluationResult:
        """
        Evaluate policies against context.

        Args:
            agent_id: Agent identifier
            action: Action being performed
            layer: Governance layer
            context: Execution context
            priority_limit: Only evaluate policies up to this priority

        Returns:
            Evaluation result
        """
        start_time = datetime.now()

        # Check cache
        cache_key = self._get_cache_key(agent_id, action, layer, context)
        if self.config.enable_cache and cache_key in self._policy_cache:
            cached = self._policy_cache[cache_key]
            # Check if cache is still valid
            if (datetime.now() - cached.evaluated_at).total_seconds() < self.config.cache_ttl_seconds:
                return cached

        # Sort policies by priority
        policies_to_eval = self._get_policies_by_priority(priority_limit)

        # Evaluate each policy
        for policy in policies_to_eval:
            if not policy.active:
                continue

            # Check scope
            if not policy.matches_scope(agent_id, action, layer, context):
                continue

            # Evaluate rules
            matched, rules_matched = policy.evaluate_rules(context)

            if matched:
                result = PolicyEvaluationResult(
                    policy_id=policy.policy_id,
                    matched=True,
                    outcome=policy.outcome,
                    confidence=policy.confidence,
                    conditions=policy.conditions,
                    reasoning=f"Policy {policy.name} matched with {rules_matched} rules",
                    evaluated_at=start_time,
                    evaluation_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                    rules_evaluated=len(policy.rules),
                    rules_matched=rules_matched
                )

                # Cache result
                if self.config.enable_cache:
                    self._policy_cache[cache_key] = result

                if self.config.short_circuit:
                    return result

        # No policies matched
        return PolicyEvaluationResult(
            matched=False,
            outcome="allow",  # Default allow
            reasoning="No applicable policies matched",
            evaluated_at=start_time,
            evaluation_time_ms=(datetime.now() - start_time).total_seconds() * 1000
        )

    def _get_policies_by_priority(self, priority_limit: Optional[PolicyPriority]) -> List[GovernancePolicy]:
        """Get policies sorted by priority"""
        policies = []

        priorities = [p for p in PolicyPriority if priority_limit is None or p.value <= priority_limit.value]

        for priority in priorities:
            for policy_id in self._priority_index[priority]:
                if policy_id in self._policies:
                    policies.append(self._policies[policy_id])

        return policies

    def _get_cache_key(self, agent_id: str, action: str, layer: str, context: Dict[str, Any]) -> str:
        """Generate cache key"""
        # Create hash from key context
        import hashlib
        key_data = f"{agent_id}:{action}:{layer}"
        for k, v in sorted(context.items()):
            key_data += f":{k}={v}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]

    def _clear_cache_for_policy(self, policy_id: str) -> None:
        """Clear cache entries for a policy"""
        keys_to_remove = [
            key for key, result in self._policy_cache.items()
            if result.policy_id == policy_id
        ]
        for key in keys_to_remove:
            del self._policy_cache[key]

    def get_policies_by_tag(self, tag: str) -> List[GovernancePolicy]:
        """Get policies with a specific tag"""
        policy_ids = self._tag_index.get(tag, [])
        return [self._policies[pid] for pid in policy_ids if pid in self._policies]

    def get_statistics(self) -> Dict[str, Any]:
        """Get policy engine statistics"""
        active_policies = sum(1 for p in self._policies.values() if p.active)
        total_rules = sum(len(p.rules) for p in self._policies.values())

        return {
            "total_policies": len(self._policies),
            "active_policies": active_policies,
            "total_rules": total_rules,
            "cache_size": len(self._policy_cache),
            "priority_distribution": {
                priority.name: len(self._priority_index[priority])
                for priority in PolicyPriority
            },
            "tag_index_size": len(self._tag_index)
        }


# ============================================================================
# Factory
# ============================================================================

_policy_engine_instance: Optional[PolicyEngine] = None


def get_policy_engine(config: Optional[PolicyEngineConfig] = None) -> PolicyEngine:
    """Get or create policy engine instance"""
    global _policy_engine_instance
    if _policy_engine_instance is None:
        _policy_engine_instance = PolicyEngine(config)
    return _policy_engine_instance
