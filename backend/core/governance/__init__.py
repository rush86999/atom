"""
Dynamic Governance Module for Phase 5

Provides three-layer governance architecture:
- Operational Layer: Day-to-day agent permissions
- Tactical Layer: Policy-based decisions
- Strategic Layer: Long-term governance strategy

Based on 2025-2026 research:
- Governance-as-a-Service: Multi-Agent Framework (arXiv:2508.18765v1)
- From Anarchy to Assembly: Governance Survey
"""

from core.governance.dynamic_governance import (
    GovernanceLayer,
    GovernanceDecision,
    ThreeLayerGovernance,
    DynamicGovernanceManager,
    get_governance_manager,
)

from core.governance.policy_engine import (
    GovernancePolicy,
    PolicyRule,
    PolicyEvaluationResult,
    PolicyEngine,
    get_policy_engine,
)

from core.governance.governance_service import (
    GovernanceServiceRequest,
    GovernanceServiceResponse,
    GovernanceAsAService,
    get_governance_service,
)

__all__ = [
    # Dynamic Governance
    "GovernanceLayer",
    "GovernanceDecision",
    "ThreeLayerGovernance",
    "DynamicGovernanceManager",
    "get_governance_manager",

    # Policy Engine
    "GovernancePolicy",
    "PolicyRule",
    "PolicyEvaluationResult",
    "PolicyEngine",
    "get_policy_engine",

    # Governance Service
    "GovernanceServiceRequest",
    "GovernanceServiceResponse",
    "GovernanceAsAService",
    "get_governance_service",
]
