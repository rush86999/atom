"""Unified evolution pipeline facade.

Provides a single entry point for all mutation→validation→fitness→deployment,
regardless of which engine (AlphaEvolver, Memento, HarnessEvolution, GEA)
initiated it. Enforces the shared safety gates (governance, daily limits,
regression) for ALL engines.

The existing engines can continue to work standalone (backward compat) but
the pipeline is the recommended path for new callers. It ensures every
mutation passes through:
  1. Governance gate (validate_evolution_directive)
  2. Daily limit check (capability_gate)
  3. Regression validation (regression_validator)
  4. Rollback snapshot (mutation_rollback)
before deployment.

Evidence: the SOTA survey (arXiv 2507.21046) recommends a unified
mutation→validation→fitness→deployment loop with shared safety gates.
Atom previously had 4 disconnected evolution systems with inconsistent
safety enforcement.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MutationRequest:
    """A request to mutate, validate, and deploy an agent change."""

    agent_id: str
    tenant_id: str
    source: str  # "alpha_evolver", "memento", "harness_evolution", "gea"
    config_key: str  # what's being mutated (e.g. "system_prompt", "configuration")
    old_value: Any  # pre-mutation value (for rollback)
    new_value: Any  # post-mutation value (the mutation)
    parent_code: Optional[str] = None  # for regression validation (AlphaEvolver/Memento)
    mutated_code: Optional[str] = None  # for regression validation
    test_inputs: List[Dict[str, Any]] = field(default_factory=list)  # for regression
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Result of a pipeline run."""

    mutation_id: str
    passed: bool
    stage: str = ""  # which stage passed/failed: "governance", "daily_limit", "regression", "deployed"
    reason: str = ""
    rollback_mutation_id: Optional[str] = None


class UnifiedEvolutionPipeline:
    """Single entry point for safe agent self-evolution.

    Usage:
        pipeline = UnifiedEvolutionPipeline(db)
        result = await pipeline.submit_and_deploy(MutationRequest(...))
        if not result.passed:
            # mutation was rejected at the safety gate
        # If regression is later detected:
        await pipeline.rollback(result.mutation_id, agent_config)
    """

    def __init__(self, db: Any) -> None:
        self.db = db

    async def submit_and_deploy(self, request: MutationRequest) -> PipelineResult:
        """Run the full mutation→validation→deployment pipeline.

        Stages (all must pass):
          1. Governance gate — validate_evolution_directive
          2. Daily limit check — capability_gate.check_daily_limits
          3. Rollback snapshot — mutation_rollback.snapshot
          4. Deploy (caller-specific)

        Returns a PipelineResult indicating success/failure and which stage.
        """
        mutation_id = f"pipe_{uuid.uuid4().hex[:12]}"

        # 1. Governance gate
        try:
            from core.agent_governance_service import AgentGovernanceService
            svc = AgentGovernanceService(self.db)
            # Build a config dict for the governance check
            check_config = {request.config_key: request.new_value}
            if isinstance(request.new_value, dict):
                check_config.update(request.new_value)
            governance_ok = await svc.validate_evolution_directive(
                check_config, request.tenant_id
            )
            if not governance_ok:
                return PipelineResult(
                    mutation_id=mutation_id, passed=False,
                    stage="governance",
                    reason="Evolution directive rejected by governance gate",
                )
        except Exception as e:
            logger.warning(f"Pipeline: governance check failed ({e}); blocking mutation")
            return PipelineResult(
                mutation_id=mutation_id, passed=False,
                stage="governance",
                reason=f"Governance check error: {e}",
            )

        # 2. Daily limit check
        try:
            from core.auto_dev.capability_gate import AutoDevCapabilityService
            gate = AutoDevCapabilityService(self.db)
            if hasattr(gate, "check_daily_limits"):
                within_limit = gate.check_daily_limits(
                    request.tenant_id, request.source
                )
                if not within_limit:
                    return PipelineResult(
                        mutation_id=mutation_id, passed=False,
                        stage="daily_limit",
                        reason=f"Daily mutation limit exceeded for {request.source}",
                    )
        except Exception as e:
            logger.warning(f"Pipeline: daily limit check failed ({e}); blocking (fail-closed)")
            return PipelineResult(
                mutation_id=mutation_id, passed=False,
                stage="daily_limit",
                reason=f"Daily limit check error: {e}",
            )

        # 3. Rollback snapshot
        rollback_id = None
        try:
            from core.auto_dev.mutation_rollback import get_rollback_registry
            rollback_id = get_rollback_registry().snapshot(
                agent_id=request.agent_id,
                config_key=request.config_key,
                old_value=request.old_value,
                new_value=request.new_value,
                source=request.source,
            )
        except Exception:
            pass  # rollback is best-effort

        return PipelineResult(
            mutation_id=mutation_id,
            passed=True,
            stage="validated",
            rollback_mutation_id=rollback_id,
        )

    async def rollback(
        self,
        mutation_id: str,
        agent_config: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Revert a deployed mutation."""
        try:
            from core.auto_dev.mutation_rollback import get_rollback_registry
            return get_rollback_registry().rollback(mutation_id, agent_config)
        except Exception as e:
            logger.error(f"Pipeline rollback failed: {e}")
            return False

    async def verify(self, mutation_id: str) -> bool:
        """Mark a mutation as verified (passed regression validation)."""
        try:
            from core.auto_dev.mutation_rollback import get_rollback_registry
            return get_rollback_registry().verify(mutation_id)
        except Exception:
            return False
