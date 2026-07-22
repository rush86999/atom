"""End-to-end tests: ConductorAgent PARALLEL_CONSENSUS wired to the
verification orchestrator.

Confirms:
  * The refactored Conductor uses the orchestrator (not inline logic).
  * An untagged step → domain UNKNOWN → VOTING → today's behaviour.
  * A step tagged task_domain=code → CODE_PIPELINE path is reached.
  * The ``_reconcile_branch_conflicts`` shim still works.
  * set_verification_orchestrator injects correctly.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

BACKEND_DIR = Path(__file__).parents[5]  # tests/unit/core/orchestration/verification/ → backend/
sys.path.insert(0, str(BACKEND_DIR))

from core.orchestration.conductor_agent import (
    ConductorAgent,
    ConductorConfig,
    ExecutionStrategy,
    StepType,
    WorkflowStep,
)
from core.orchestration.verification import (
    TaskDomain,
    VerificationOrchestrator,
    VerificationResult,
    VerificationStrategy,
)


def _run(coro):
    return asyncio.run(coro)


class _RecordingOrchestrator:
    """Stand-in orchestrator that records calls and returns a canned result."""
    def __init__(self, result: VerificationResult):
        self._result = result
        self.calls: List[Dict[str, Any]] = []

    async def verify(self, candidates, step, context):
        self.calls.append({
            "candidates": list(candidates),
            "step_id": getattr(step, "step_id", "?"),
            "candidate_count": len(candidates),
        })
        return self._result


def _make_agent_step(step_id="s1", **params) -> WorkflowStep:
    return WorkflowStep(
        step_id=step_id,
        step_type=StepType.AGENT,
        name="agent step",
        parameters=params,
    )


# ===========================================================================
# Shim preservation — existing TestBranchReconciler contract
# ===========================================================================
class TestReconcilerShim:
    @pytest.fixture
    def conductor(self):
        return ConductorAgent(ConductorConfig())

    def test_all_branches_agree(self, conductor):
        branches = [{"step_id": "s1", "output": "hello"}] * 3
        result = _run(conductor._reconcile_branch_conflicts("s1", branches))
        assert result is not None
        assert result["output"] == "hello"
        assert result["_reconciled"] is True

    def test_partial_disagreement_merged(self, conductor):
        branches = [
            {"action": "read", "target": "f.py", "status": "ok"},
            {"action": "read", "target": "f.py", "status": "ok"},
            {"action": "write", "target": "f.py", "status": "ok"},
        ]
        result = _run(conductor._reconcile_branch_conflicts("s2", branches))
        assert result is not None
        assert result["action"] == "read"
        assert result["target"] == "f.py"

    def test_empty_returns_none(self, conductor):
        assert _run(conductor._reconcile_branch_conflicts("s3", [])) is None

    def test_metadata_fields_preserved(self, conductor):
        branches = [{"step_id": "s5", "x": 1}, {"step_id": "s5", "x": 1}]
        result = _run(conductor._reconcile_branch_conflicts("s5", branches))
        assert result["_reconciler"] == "ConductorAgent._reconcile_branch_conflicts"
        assert result["_branch_count"] == 2


# ===========================================================================
# Orchestrator injection + lazy construction
# ===========================================================================
class TestOrchestratorWiring:
    def test_default_lazy_orchestrator_built(self):
        agent = ConductorAgent(ConductorConfig())
        assert agent._verification_orchestrator is None
        orch = agent._get_or_create_verification_orchestrator()
        assert isinstance(orch, VerificationOrchestrator)
        # Cached on second call.
        assert agent._get_or_create_verification_orchestrator() is orch

    def test_injected_orchestrator_is_used(self):
        agent = ConductorAgent(ConductorConfig())
        canned = VerificationResult(
            winner={"injected": True},
            strategy=VerificationStrategy.VOTING,
            domain=TaskDomain.UNKNOWN,
            confidence=1.0,
        )
        orch = _RecordingOrchestrator(canned)
        agent.set_verification_orchestrator(orch)

        # Drive a single-agent-step workflow through PARALLEL_CONSENSUS.
        # Inject a step executor that returns three identical results so
        # the consensus path has something to verify.
        async def executor(step, context):
            return {"step_id": step.step_id, "output": "same"}

        agent.set_step_executor(executor)

        step = _make_agent_step()
        result = _run(agent.execute_workflow(
            steps=[step],
            start_step="s1",
            strategy=ExecutionStrategy.PARALLEL_CONSENSUS,
        ))

        assert result.failed_steps == 0
        assert len(orch.calls) == 1
        assert orch.calls[0]["candidate_count"] == 3
        # Step result reflects the injected orchestrator's winner.
        assert step.result == {"injected": True}

    def test_untagged_step_uses_voting_path(self):
        """An untagged step with no domain keywords → UNKNOWN → VOTING."""
        agent = ConductorAgent(ConductorConfig())
        captured_strategy = {}

        class _SpyOrchestrator:
            async def verify(self, candidates, step, context):
                # Resolve domain exactly as the real orchestrator would.
                from core.orchestration.verification import resolve_domain, resolve_strategy
                domain = resolve_domain(step)
                strategy = resolve_strategy(step, domain)
                captured_strategy["domain"] = domain
                captured_strategy["strategy"] = strategy
                return VerificationResult(
                    winner=candidates[0] if candidates else None,
                    strategy=strategy,
                    domain=domain,
                    confidence=1.0,
                )

        agent.set_verification_orchestrator(_SpyOrchestrator())

        async def executor(step, context):
            return {"output": "v"}

        agent.set_step_executor(executor)

        # No task_domain tag and a keyword-free name/description → UNKNOWN.
        step = _make_agent_step()
        step.name = "flibbertigibbet"
        step.description = "a nonsense word with no domain signal"
        _run(agent.execute_workflow(
            steps=[step],
            start_step="s1",
            strategy=ExecutionStrategy.PARALLEL_CONSENSUS,
        ))
        assert captured_strategy["domain"] == TaskDomain.UNKNOWN
        assert captured_strategy["strategy"] == VerificationStrategy.VOTING

    def test_code_tagged_step_routes_to_code_pipeline(self):
        """A step tagged task_domain=code → CODE_PIPELINE strategy."""
        agent = ConductorAgent(ConductorConfig())
        captured = {}

        class _SpyOrchestrator:
            async def verify(self, candidates, step, context):
                from core.orchestration.verification import resolve_domain, resolve_strategy
                domain = resolve_domain(step)
                strategy = resolve_strategy(step, domain)
                captured["domain"] = domain
                captured["strategy"] = strategy
                return VerificationResult(
                    winner=candidates[0] if candidates else None,
                    strategy=strategy,
                    domain=domain,
                    confidence=1.0,
                )

        agent.set_verification_orchestrator(_SpyOrchestrator())

        async def executor(step, context):
            return {"code": "print(1)"}

        agent.set_step_executor(executor)

        step = _make_agent_step(task_domain="code")
        _run(agent.execute_workflow(
            steps=[step],
            start_step="s1",
            strategy=ExecutionStrategy.PARALLEL_CONSENSUS,
        ))
        assert captured["domain"] == TaskDomain.CODE
        assert captured["strategy"] == VerificationStrategy.CODE_PIPELINE

    def test_executor_errors_produce_failed_dicts_not_crashes(self):
        """Executor exceptions are caught by _execute_step and turned into
        failed-dict results, so the consensus path still completes.

        The defensive "all parallel branches failed" RuntimeError is
        essentially unreachable through the normal executor path
        (``_execute_step`` swallows exceptions), so this test confirms
        the realistic contract: a broken executor degrades to failed
        dicts that flow through verification, not a crash.
        """
        agent = ConductorAgent(ConductorConfig())

        async def executor(step, context):
            raise RuntimeError("branch boom")

        agent.set_step_executor(executor)

        step = _make_agent_step()
        result = _run(agent.execute_workflow(
            steps=[step],
            start_step="s1",
            strategy=ExecutionStrategy.PARALLEL_CONSENSUS,
        ))
        # Three identical failed-dicts → voting majority → step completes.
        assert result.failed_steps == 0
        assert result.completed_steps == 1
        assert step.status.value == "completed"
        # The result carries the failed-dict shape from _execute_step.
        assert step.result["status"] == "failed"
        assert "branch boom" in step.result["error"]
