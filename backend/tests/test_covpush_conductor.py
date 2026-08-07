"""
Coverage-push tests for core/orchestration/conductor_agent.py.

Covers the 5 orchestration strategies, state-machine transitions, event
surfaces, and error/edge branches. Bug-hunt tests are written red-first.
"""
import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from core.orchestration.conductor_agent import (
    ConductorAgent,
    ConductorConfig,
    ExecutionStatus,
    ExecutionStrategy,
    OrchestrationResult,
    StepType,
    WorkflowExecutionContext,
    WorkflowStep,
    get_conductor_agent,
)


def make_steps(chain):
    """Build a list of WorkflowStep with next_steps links from (id, name) pairs."""
    steps = []
    for i, (sid, name) in enumerate(chain):
        nxt = chain[i + 1][0] if i + 1 < len(chain) else None
        steps.append(
            WorkflowStep(
                step_id=sid,
                name=name,
                next_steps=[nxt] if nxt else [],
            )
        )
    return steps


class TestWorkflowStepAndContext:
    """WorkflowStep.can_execute and WorkflowExecutionContext helpers."""

    def test_can_execute_requires_dependencies(self):
        step = WorkflowStep(step_id="s1", depends_on=["a", "b"])
        assert not step.can_execute({"a"})
        assert step.can_execute({"a", "b"})
        step.condition_met = False
        assert not step.can_execute({"a", "b"})

    def test_get_step_missing(self):
        ctx = WorkflowExecutionContext(steps=[WorkflowStep(step_id="s1")])
        assert ctx.get_step("nope") is None

    def test_get_next_steps_missing_and_linked(self):
        ctx = WorkflowExecutionContext(
            steps=[
                WorkflowStep(step_id="s1", next_steps=["s2", "ghost"]),
                WorkflowStep(step_id="s2"),
            ]
        )
        assert ctx.get_next_steps("s1")[0].step_id == "s2"
        assert ctx.get_next_steps("missing") == []
        assert ctx.get_next_steps("s2") == []

    def test_get_ready_steps_filters(self):
        ctx = WorkflowExecutionContext(
            steps=[
                WorkflowStep(step_id="s1", depends_on=["s0"]),
                WorkflowStep(step_id="s2"),
            ],
            completed_steps={"sX"},
        )
        ready = ctx.get_ready_steps()
        assert [s.step_id for s in ready] == ["s2"]
        ctx.steps[0].status = ExecutionStatus.RUNNING
        assert [s.step_id for s in ctx.get_ready_steps()] == ["s2"]

    def test_is_complete_terminal_states_and_all_done(self):
        ctx = WorkflowExecutionContext()
        ctx.status = ExecutionStatus.CANCELLED
        assert ctx.is_complete()
        ctx.status = ExecutionStatus.RUNNING
        ctx.steps = [
            WorkflowStep(step_id="a", status=ExecutionStatus.COMPLETED),
            WorkflowStep(step_id="b", status=ExecutionStatus.FAILED),
        ]
        assert ctx.is_complete()
        ctx.steps[1].status = ExecutionStatus.PENDING
        assert not ctx.is_complete()

    def test_get_progress(self):
        ctx = WorkflowExecutionContext()
        assert ctx.get_progress() == 0.0
        ctx.steps = [
            WorkflowStep(step_id="a", status=ExecutionStatus.COMPLETED),
            WorkflowStep(step_id="b", status=ExecutionStatus.PENDING),
            WorkflowStep(step_id="c", status=ExecutionStatus.PENDING),
        ]
        assert ctx.get_progress() == pytest.approx(1 / 3)

    def test_orchestration_result_was_successful(self):
        r = OrchestrationResult(status=ExecutionStatus.COMPLETED)
        assert r.was_successful()
        r.failed_steps = 1
        assert not r.was_successful()
        r.failed_steps = 0
        r.rolled_back = True
        assert not r.was_successful()


class TestSequentialStrategy:
    """SEQUENTIAL execution: success, failure, timeout, retry semantics."""

    @pytest.fixture
    def agent(self):
        return ConductorAgent()

    async def test_sequential_success(self, agent):
        steps = make_steps([("s1", "one"), ("s2", "two"), ("s3", "three")])
        result = await agent.execute_workflow(
            steps, "s1", strategy=ExecutionStrategy.SEQUENTIAL
        )
        assert result.status == ExecutionStatus.COMPLETED
        assert result.completed_steps == 3
        assert result.failed_steps == 0
        assert result.was_successful()
        assert result.duration_seconds >= 0
        status = agent.get_workflow_status(result.execution_id)
        assert status["status"] == "completed"

    async def test_sequential_step_failure_exhausts_retries(self, agent):
        agent._execute_step = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        steps = make_steps([("s1", "one"), ("s2", "two")])
        result = await agent.execute_workflow(
            steps, "s1", strategy=ExecutionStrategy.SEQUENTIAL
        )
        assert result.status == ExecutionStatus.FAILED
        assert result.failed_steps == 1
        assert "boom" in result.errors[0]
        assert steps[0].retry_count == steps[0].max_retries

    async def test_sequential_timeout_fails_step(self, agent):
        async def slow(step, ctx):
            await asyncio.sleep(5)
            return {"step_id": step.step_id}

        agent._execute_step = slow
        steps = make_steps([("s1", "one")])
        steps[0].timeout_seconds = 1
        result = await agent.execute_workflow(
            steps, "s1", strategy=ExecutionStrategy.SEQUENTIAL
        )
        assert result.status == ExecutionStatus.FAILED
        assert steps[0].error == "Timeout"
        assert result.failed_steps == 1

    async def test_retried_step_that_succeeds_is_not_failed(self, agent):
        """BUG-HUNT: a step that fails once then succeeds via retry must not
        leave failed_steps > 0 — otherwise the whole workflow is marked
        FAILED even though every step eventually completed."""
        calls = {"s1": 0}

        async def flaky(step, ctx):
            calls[step.step_id] = calls.get(step.step_id, 0) + 1
            if step.step_id == "s1" and calls["s1"] == 1:
                raise RuntimeError("transient hiccup")
            return {"step_id": step.step_id, "status": "completed"}

        agent._execute_step = flaky
        steps = make_steps([("s1", "one"), ("s2", "two")])
        steps[0].max_retries = 3
        result = await agent.execute_workflow(
            steps, "s1", strategy=ExecutionStrategy.SEQUENTIAL
        )
        assert calls["s1"] == 2
        assert result.failed_steps == 0
        assert result.status == ExecutionStatus.COMPLETED
        assert result.was_successful()

    async def test_unknown_step_breaks_loop(self, agent):
        steps = make_steps([("s1", "one")])
        steps[0].next_steps = ["ghost"]
        result = await agent.execute_workflow(
            steps, "s1", strategy=ExecutionStrategy.SEQUENTIAL
        )
        assert result.status == ExecutionStatus.COMPLETED


class TestParallelAndHybrid:
    """PARALLEL and HYBRID strategies."""

    async def test_parallel_runs_ready_steps(self):
        agent = ConductorAgent()
        steps = [
            WorkflowStep(step_id="s1"),
            WorkflowStep(step_id="s2", depends_on=["s1"]),
        ]
        result = await agent.execute_workflow(
            steps, "s1", strategy=ExecutionStrategy.PARALLEL
        )
        assert result.status == ExecutionStatus.COMPLETED
        assert result.completed_steps == 2

    async def test_parallel_failed_status_dict(self):
        agent = ConductorAgent()
        step = WorkflowStep(step_id="s1")
        agent._execute_step = AsyncMock(
            return_value={"step_id": "s1", "status": "failed", "error": "nope"}
        )
        result = await agent.execute_workflow(
            [step], "s1", strategy=ExecutionStrategy.PARALLEL
        )
        assert result.status == ExecutionStatus.FAILED
        assert step.status == ExecutionStatus.FAILED
        assert "nope" in result.errors[0]

    async def test_hybrid_single_and_parallel_blocks(self):
        agent = ConductorAgent()
        steps = [
            WorkflowStep(step_id="s1", is_parallel_root=True, parallel_group="g1"),
            WorkflowStep(step_id="s2", parallel_group="g1"),
            WorkflowStep(step_id="s3"),
        ]
        result = await agent.execute_workflow(
            steps, "s1", strategy=ExecutionStrategy.HYBRID
        )
        assert result.status == ExecutionStatus.COMPLETED
        assert result.completed_steps == 3

    def test_identify_parallel_blocks(self):
        agent = ConductorAgent()
        steps = [
            WorkflowStep(step_id="s1", is_parallel_root=True, parallel_group="g1"),
            WorkflowStep(step_id="s2", parallel_group="g1"),
            WorkflowStep(step_id="s3"),
        ]
        blocks = agent._identify_parallel_blocks(
            WorkflowExecutionContext(steps=steps)
        )
        assert len(blocks) == 2
        assert {s.step_id for s in blocks[0]} == {"s1", "s2"}
        assert blocks[1][0].step_id == "s3"

    async def test_execute_parallel_group(self):
        agent = ConductorAgent()
        steps = [
            WorkflowStep(step_id="s1", parallel_group="g1"),
            WorkflowStep(step_id="s2", parallel_group="g1"),
            WorkflowStep(step_id="s3", parallel_group="g2"),
        ]
        ctx = WorkflowExecutionContext(steps=steps)
        result = OrchestrationResult()
        await agent._execute_parallel_group(steps[0], ctx, result)
        assert result.completed_steps == 2
        assert ctx.completed_steps == {"s1", "s2"}

    def test_can_execute_parallel_group(self):
        agent = ConductorAgent()
        steps = [
            WorkflowStep(step_id="s1", parallel_group="g1", depends_on=["a"]),
            WorkflowStep(step_id="s2", parallel_group="g1", depends_on=["a"]),
        ]
        ctx = WorkflowExecutionContext(steps=steps)
        assert not agent._can_execute_parallel_group(steps[0], ctx)
        ctx.completed_steps.add("a")
        assert agent._can_execute_parallel_group(steps[0], ctx)


class TestAdaptiveStrategy:
    """ADAPTIVE strategy with condition skipping."""

    async def test_adaptive_skips_unmet_condition(self):
        agent = ConductorAgent()
        steps = [
            WorkflowStep(step_id="s1", condition="flag == 'off'", next_steps=["s2"]),
            WorkflowStep(step_id="s2"),
        ]
        ctx = WorkflowExecutionContext(
            steps=steps, start_step="s1", shared_context={"flag": "on"}
        )
        result = OrchestrationResult()
        await agent._execute_adaptive(ctx, result)
        assert steps[0].condition_met is False
        assert result.skipped_steps == 1
        assert result.completed_steps == 1

    async def test_adaptive_runs_met_condition(self):
        agent = ConductorAgent()
        steps = [
            WorkflowStep(step_id="s1", condition="flag == 'on'"),
        ]
        ctx = WorkflowExecutionContext(
            steps=steps, start_step="s1", shared_context={"flag": "on"}
        )
        result = OrchestrationResult()
        await agent._execute_adaptive(ctx, result)
        assert steps[0].status == ExecutionStatus.COMPLETED
        assert result.completed_steps == 1

    def test_evaluate_condition_true_false_and_errors(self):
        agent = ConductorAgent()
        ctx = WorkflowExecutionContext(shared_context={"x": 1})
        assert agent._evaluate_condition("x == 1", ctx) is True
        assert agent._evaluate_condition("x == 2", ctx) is False
        assert agent._evaluate_condition("__import__('os')", ctx) is False
        with patch("core.safe_evaluator.safe_eval", side_effect=RuntimeError("bad")):
            assert agent._evaluate_condition("x == 1", ctx) is False


class TestRollbackSafe:
    """ROLLBACK_SAFE strategy and compensation."""

    async def test_rollback_safe_success(self):
        agent = ConductorAgent()
        steps = make_steps([("s1", "one"), ("s2", "two")])
        steps[0].compensation_step_id = "c1"
        steps.append(WorkflowStep(step_id="c1"))
        result = await agent.execute_workflow(
            steps, "s1", strategy=ExecutionStrategy.ROLLBACK_SAFE
        )
        assert result.status == ExecutionStatus.COMPLETED
        assert result.rolled_back is False

    async def test_rollback_safe_triggers_rollback_on_failure(self):
        agent = ConductorAgent(config=ConductorConfig(rollback_on_failure=True))
        steps = make_steps([("s1", "one"), ("s2", "two")])
        steps[0].compensation_step_id = "c1"
        steps.append(WorkflowStep(step_id="c1"))
        agent._execute_step = AsyncMock(
            side_effect=[RuntimeError("fail")] + [
                {"step_id": s.step_id, "status": "completed"} for s in steps
            ]
        )
        result = await agent.execute_workflow(
            steps, "s1", strategy=ExecutionStrategy.ROLLBACK_SAFE
        )
        assert result.rolled_back is True
        assert result.rollback_reason == "Workflow execution failed"

    async def test_rollback_workflow_handles_missing_steps(self):
        agent = ConductorAgent()
        ctx = WorkflowExecutionContext(
            workflow_id="wf", rollback_stack=["s1", "ghost"]
        )
        ctx.steps = [
            WorkflowStep(step_id="s1", compensation_step_id="c1"),
            WorkflowStep(step_id="c1"),
        ]
        result = OrchestrationResult()
        await agent._rollback_workflow(ctx, result)
        assert result.rolled_back is True

    async def test_rollback_compensation_failure_recorded(self):
        agent = ConductorAgent()
        ctx = WorkflowExecutionContext(
            workflow_id="wf", rollback_stack=["s1"]
        )
        ctx.steps = [
            WorkflowStep(step_id="s1", compensation_step_id="c1"),
            WorkflowStep(step_id="c1"),
        ]
        agent._execute_step = AsyncMock(side_effect=RuntimeError("comp boom"))
        result = OrchestrationResult()
        await agent._rollback_workflow(ctx, result)
        assert any("Compensation failed" in e for e in result.errors)

    async def test_rollback_safe_blocked_when_can_not_execute(self):
        agent = ConductorAgent()
        steps = [WorkflowStep(step_id="s1", condition_met=False)]
        result = await agent.execute_workflow(
            steps, "s1", strategy=ExecutionStrategy.ROLLBACK_SAFE
        )
        # A workflow that makes zero progress must not dangle in RUNNING.
        assert result.status == ExecutionStatus.FAILED
        assert any("no progress" in e for e in result.errors)


class TestParallelConsensus:
    """PARALLEL_CONSENSUS with deterministic and stochastic executors."""

    async def test_consensus_deterministic_skips_fanout(self):
        agent = ConductorAgent()
        agent._execute_step = AsyncMock(
            return_value={"step_id": "s1", "output": "once"}
        )
        steps = [WorkflowStep(step_id="s1", step_type=StepType.AGENT)]
        result = await agent.execute_workflow(
            steps, "s1", strategy=ExecutionStrategy.PARALLEL_CONSENSUS
        )
        assert agent._execute_step.call_count == 1
        assert result.status == ExecutionStatus.COMPLETED

    async def test_consensus_stochastic_uses_orchestrator(self):
        agent = ConductorAgent()
        verifier = MagicMock()
        verifier.verify = AsyncMock(
            return_value=SimpleNamespace(winner={"step_id": "s1", "output": "win"})
        )
        agent.set_verification_orchestrator(verifier)
        agent._is_stochastic_executor = Mock(return_value=True)
        agent._execute_step = AsyncMock(
            return_value={"step_id": "s1", "output": "branch"}
        )
        steps = [WorkflowStep(step_id="s1", step_type=StepType.AGENT)]
        result = await agent.execute_workflow(
            steps, "s1", strategy=ExecutionStrategy.PARALLEL_CONSENSUS
        )
        assert result.status == ExecutionStatus.COMPLETED
        assert verifier.verify.called
        assert agent._execute_step.call_count == 3

    async def test_consensus_all_branches_fail(self):
        agent = ConductorAgent()
        agent._is_stochastic_executor = Mock(return_value=True)
        agent._execute_step = AsyncMock(side_effect=RuntimeError("dead"))
        steps = [WorkflowStep(step_id="s1", step_type=StepType.AGENT)]
        result = await agent.execute_workflow(
            steps, "s1", strategy=ExecutionStrategy.PARALLEL_CONSENSUS
        )
        assert result.status == ExecutionStatus.FAILED

    async def test_consensus_non_agent_steps_tracked(self):
        agent = ConductorAgent()
        steps = [
            WorkflowStep(step_id="s1", step_type=StepType.INTEGRATION),
        ]
        result = await agent.execute_workflow(
            steps, "s1", strategy=ExecutionStrategy.PARALLEL_CONSENSUS
        )
        assert result.status == ExecutionStatus.COMPLETED

    async def test_reconcile_branch_conflicts_delegates(self):
        agent = ConductorAgent()
        with patch(
            "core.orchestration.verification.voting.VotingVerifier"
        ) as VV:
            vv = VV.return_value
            vv.reconcile_only = AsyncMock(return_value={"merged": True})
            out = await agent._reconcile_branch_conflicts(
                "s1", [{"a": 1}, {"a": 2}]
            )
        assert out == {"merged": True}
        vv.reconcile_only.assert_awaited_once_with("s1", [{"a": 1}, {"a": 2}])

    def test_verification_orchestrator_lazy_construction(self):
        agent = ConductorAgent()
        with patch(
            "core.orchestration.verification.VerificationOrchestrator"
        ) as VO:
            inst = VO.return_value
            assert agent._get_or_create_verification_orchestrator() is inst
            assert agent._get_or_create_verification_orchestrator() is inst
        VO.assert_called_once()


class TestStepExecutor:
    """Injected step executor semantics."""

    @pytest.fixture
    def agent(self):
        return ConductorAgent()

    async def test_injected_executor_dict_result(self, agent):
        agent.set_step_executor(lambda step, ctx: {"step_id": step.step_id})
        steps = make_steps([("s1", "one")])
        result = await agent.execute_workflow(
            steps, "s1", strategy=ExecutionStrategy.SEQUENTIAL
        )
        assert result.status == ExecutionStatus.COMPLETED

    async def test_injected_executor_awaitable(self, agent):
        async def exec_step(step, ctx):
            return {"step_id": step.step_id}

        agent.set_step_executor(exec_step)
        steps = make_steps([("s1", "one")])
        result = await agent.execute_workflow(
            steps, "s1", strategy=ExecutionStrategy.SEQUENTIAL
        )
        assert result.status == ExecutionStatus.COMPLETED

    async def test_injected_executor_scalar_result_wrapped(self, agent):
        agent.set_step_executor(lambda step, ctx: "plain string")
        steps = make_steps([("s1", "one")])
        result = await agent.execute_workflow(
            steps, "s1", strategy=ExecutionStrategy.SEQUENTIAL
        )
        assert result.status == ExecutionStatus.COMPLETED

    async def test_injected_executor_exception_failed_status(self, agent):
        def boom(step, ctx):
            raise RuntimeError("injected boom")

        agent.set_step_executor(boom)
        steps = make_steps([("s1", "one")])
        result = await agent.execute_workflow(
            steps, "s1", strategy=ExecutionStrategy.SEQUENTIAL
        )
        assert result.status == ExecutionStatus.FAILED

    def test_is_stochastic_executor(self, agent):
        assert agent._is_stochastic_executor() is False
        agent.set_step_executor(lambda s, c: {})
        assert agent._is_stochastic_executor() is True


class TestWorkflowLifecycleControl:
    """pause/resume/cancel/status/statistics."""

    @pytest.fixture
    def agent(self):
        return ConductorAgent()

    def test_pause_and_resume(self, agent):
        ctx = WorkflowExecutionContext(execution_id="e1")
        agent._active_workflows["e1"] = ctx
        assert agent.pause_workflow("e1") is True
        assert ctx.status == ExecutionStatus.PAUSED
        assert agent.pause_workflow("nope") is False
        assert agent.resume_workflow("e1") is True
        assert ctx.status == ExecutionStatus.RUNNING
        assert agent.resume_workflow("nope") is False
        ctx.status = ExecutionStatus.RUNNING
        assert agent.resume_workflow("e1") is False

    def test_cancel_workflow(self, agent):
        ctx = WorkflowExecutionContext(execution_id="e1")
        agent._active_workflows["e1"] = ctx
        assert agent.cancel_workflow("e1") is True
        assert ctx.status == ExecutionStatus.CANCELLED
        assert agent.cancel_workflow("e1") is True
        assert agent.cancel_workflow("nope") is False

    def test_get_workflow_status_branches(self, agent):
        ctx = WorkflowExecutionContext(
            workflow_id="wf1", execution_id="e1",
            steps=[WorkflowStep(step_id="s1", status=ExecutionStatus.COMPLETED)],
        )
        agent._active_workflows["e1"] = ctx
        status = agent.get_workflow_status("e1")
        assert status["status"] == "pending"
        assert status["progress"] == 1.0
        assert status["total_steps"] == 1

        agent._active_workflows.pop("e1")
        agent._completed_workflows["e2"] = OrchestrationResult(
            workflow_id="wf2", execution_id="e2",
            status=ExecutionStatus.COMPLETED, failed_steps=1,
        )
        status = agent.get_workflow_status("e2")
        assert status["failed_steps"] == 1
        assert agent.get_workflow_status("missing") is None

    def test_get_statistics(self, agent):
        agent._active_workflows["e1"] = WorkflowExecutionContext(execution_id="e1")
        agent._event_subscriptions["evt"].append(lambda: None)
        stats = agent.get_statistics()
        assert stats["active_workflows"] == 1
        assert stats["event_subscriptions"] == 1
        assert stats["config"]["max_concurrent_steps"] == agent.config.max_concurrent_steps

    def test_factory_returns_singleton(self):
        with patch("core.orchestration.conductor_agent._conductor_instance", None):
            a1 = get_conductor_agent()
            a2 = get_conductor_agent()
            assert a1 is a2


class TestExecutionFailurePaths:
    """execute_workflow top-level exception handling."""

    async def test_unhandled_exception_marks_failed(self):
        agent = ConductorAgent()
        steps = make_steps([("s1", "one")])
        with patch.object(
            agent, "_execute_sequential",
            AsyncMock(side_effect=RuntimeError("catastrophic")),
        ):
            result = await agent.execute_workflow(
                steps, "s1", strategy=ExecutionStrategy.SEQUENTIAL
            )
        assert result.status == ExecutionStatus.FAILED
        assert any("catastrophic" in e for e in result.errors)

    async def test_failure_with_rollback_on_failure(self):
        agent = ConductorAgent(config=ConductorConfig(rollback_on_failure=True))
        steps = make_steps([("s1", "one")])
        steps[0].compensation_step_id = "c1"
        steps.append(WorkflowStep(step_id="c1"))
        with patch.object(
            agent, "_execute_sequential",
            AsyncMock(side_effect=RuntimeError("boom")),
        ):
            result = await agent.execute_workflow(
                steps, "s1", strategy=ExecutionStrategy.SEQUENTIAL
            )
        assert result.rolled_back is True

    async def test_context_is_reused(self):
        agent = ConductorAgent()
        ctx = WorkflowExecutionContext(
            workflow_id="wf", execution_id="e1",
            steps=make_steps([("s1", "one")]), start_step="s1",
        )
        result = await agent.execute_workflow(
            [], "s1", context=ctx, strategy=ExecutionStrategy.SEQUENTIAL
        )
        assert result.workflow_id == "wf"
        assert result.execution_id == "e1"
        assert ctx.status == ExecutionStatus.COMPLETED


from types import SimpleNamespace
