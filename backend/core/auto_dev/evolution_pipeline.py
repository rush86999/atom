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
  3. Regression validation (regression_validator) — code mutations only
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

# Map pipeline ``source`` values to the capability strings that
# AutoDevCapabilityService.check_daily_limits() understands. Passing the raw
# source (e.g. "gea") made the gate always return True (fail-open no-op).
_CAPABILITY_BY_SOURCE: Dict[str, str] = {
    "alpha_evolver": "auto_dev.alpha_evolver",
    "harness_evolution": "auto_dev.alpha_evolver",
    "gea": "auto_dev.alpha_evolver",
    "memento": "auto_dev.memento_skills",
}


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

    def __init__(self, db: Any, sandbox: Any = None) -> None:
        self.db = db
        # Injectable sandbox for the regression stage (tests inject a mock;
        # production falls back to the Docker/subprocess ContainerSandbox).
        self.sandbox = sandbox

    async def submit_and_deploy(self, request: MutationRequest) -> PipelineResult:
        """Run the full mutation→validation→deployment pipeline.

        Stages (all must pass):
          1. Governance gate — validate_evolution_directive
          2. Daily limit check — capability_gate.check_daily_limits
          3. Regression validation — regression_validator (code mutations only)
          4. Rollback snapshot — mutation_rollback.snapshot
          5. Deploy (caller-specific)

        Every outcome (accepted or rejected at any gate) is appended to the
        skill-impact ledger (WikiSkill W1) so the evolvers never re-propose
        a rejected intervention.

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
                return self._record(request, PipelineResult(
                    mutation_id=mutation_id, passed=False,
                    stage="governance",
                    reason="Evolution directive rejected by governance gate",
                ))
        except Exception as e:
            logger.warning(f"Pipeline: governance check failed ({e}); blocking mutation")
            return self._record(request, PipelineResult(
                mutation_id=mutation_id, passed=False,
                stage="governance",
                reason=f"Governance check error: {e}",
            ))

        # 2. Daily limit check
        try:
            from core.auto_dev.capability_gate import AutoDevCapabilityService
            gate = AutoDevCapabilityService(self.db)
            if hasattr(gate, "check_daily_limits"):
                capability = _CAPABILITY_BY_SOURCE.get(
                    request.source, "auto_dev.alpha_evolver"
                )
                within_limit = gate.check_daily_limits(
                    request.agent_id, capability, self._get_workspace_settings(request.tenant_id)
                )
                if not within_limit:
                    return self._record(request, PipelineResult(
                        mutation_id=mutation_id, passed=False,
                        stage="daily_limit",
                        reason=f"Daily mutation limit exceeded for {request.source}",
                    ))
        except Exception as e:
            logger.warning(f"Pipeline: daily limit check failed ({e}); blocking (fail-closed)")
            return self._record(request, PipelineResult(
                mutation_id=mutation_id, passed=False,
                stage="daily_limit",
                reason=f"Daily limit check error: {e}",
            ))

        # 3. Regression validation — compare parent vs mutated code behavior on
        # the same test inputs in the sandbox. Skipped when no code pair is
        # supplied (config-only mutations can't regress behavior).
        if request.mutated_code is not None and request.parent_code is not None:
            try:
                from core.auto_dev.regression_validator import RegressionValidator
                sandbox = self.sandbox
                if sandbox is None:
                    from core.auto_dev.container_sandbox import ContainerSandbox
                    sandbox = ContainerSandbox()
                regression = await RegressionValidator().validate_regression(
                    parent_code=request.parent_code,
                    mutated_code=request.mutated_code,
                    test_inputs=request.test_inputs,
                    sandbox=sandbox,
                    tenant_id=request.tenant_id,
                )
                if not regression.passed:
                    return self._record(request, PipelineResult(
                        mutation_id=mutation_id, passed=False,
                        stage="regression",
                        reason=(
                            f"Behavioral regression detected on "
                            f"{len(regression.mismatches)}/{len(request.test_inputs)} test inputs"
                        ),
                    ))
            except Exception as e:
                logger.warning(
                    f"Pipeline: regression validation failed ({e}); blocking (fail-closed)"
                )
                return self._record(request, PipelineResult(
                    mutation_id=mutation_id, passed=False,
                    stage="regression",
                    reason=f"Regression validation error: {e}",
                ))

        # 4. Rollback snapshot
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

        return self._record(request, PipelineResult(
            mutation_id=mutation_id,
            passed=True,
            stage="validated",
            rollback_mutation_id=rollback_id,
        ))

    def _record(self, request: MutationRequest, result: PipelineResult) -> PipelineResult:
        """Append the outcome to the skill-impact ledger (best-effort — a
        ledger failure must never change pipeline behavior)."""
        try:
            from core.auto_dev.skill_impact_ledger import record_pipeline_outcome
            record_pipeline_outcome(self.db, request, result)
        except Exception as e:
            logger.debug(f"skill-impact ledger unavailable: {e}")
        return result

    async def rollback(
        self,
        mutation_id: str,
        agent_config: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Revert a deployed mutation. The skill rolls back; the ledger entry
        flips to rolled_back — the wiki itself is never rolled back (W1)."""
        try:
            from core.auto_dev.mutation_rollback import get_rollback_registry
            ok = get_rollback_registry().rollback(mutation_id, agent_config)
            if ok:
                try:
                    from core.auto_dev.skill_impact_ledger import record_rollback
                    record_rollback(self.db, mutation_id)
                except Exception:
                    pass
            return ok
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

    def _get_workspace_settings(self, tenant_id: str) -> Dict[str, Any]:
        """Retrieve workspace settings for a tenant (daily-limit config)."""
        try:
            from core.models import Workspace

            workspace = (
                self.db.query(Workspace)
                .filter(Workspace.tenant_id == tenant_id)
                .first()
            )
            if workspace and workspace.metadata_json:
                return workspace.metadata_json
        except Exception:
            pass
        return {}
