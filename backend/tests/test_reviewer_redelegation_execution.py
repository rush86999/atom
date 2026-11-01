"""Reviewer rejection must actually re-delegate the same step with feedback."""
import pytest

from core.orchestration.conductor_agent import (
    ConductorAgent,
    ExecutionStatus,
    ExecutionStrategy,
    OrchestrationResult,
    StepType,
    WorkflowExecutionContext,
    WorkflowStep,
)
from core.orchestration.reviewer_loop import (
    get_review_feedback,
    get_review_loop_state_machine,
)
from core.orchestration.verification.base import (
    VerificationResult,
    VerificationStrategy,
)
from core.orchestration.workflow_state_machine import WorkflowState


@pytest.mark.asyncio
async def test_review_rejection_redelegates_same_step_with_feedback(monkeypatch):
    monkeypatch.setenv("ATOM_REVIEWER_LOOP_ENABLED", "true")
    agent = ConductorAgent()
    attempts = []

    async def fake_executor(step, context):
        attempts.append(get_review_feedback(step))
        return {
            "step_id": step.step_id,
            "status": "completed",
            "output": "revised answer" if get_review_feedback(step) else "first answer",
        }

    class FakeVerification:
        def __init__(self):
            self.calls = 0

        async def verify(self, candidates, step, context):
            self.calls += 1
            if self.calls == 1:
                return VerificationResult(
                    winner=None,
                    strategy=VerificationStrategy.REVIEW,
                    domain="test",
                    confidence=0.3,
                    details={"accepted": False, "feedback": "add the missing evidence"},
                    reason="review rejected",
                )
            return VerificationResult(
                winner=candidates[0],
                strategy=VerificationStrategy.REVIEW,
                domain="test",
                confidence=0.9,
                details={"accepted": True, "feedback": ""},
                reason="review accepted",
            )

    verification = FakeVerification()
    agent.set_step_executor(fake_executor)
    agent.set_verification_orchestrator(verification)

    workflow_id = "reviewer-loop-acceptance"
    execution_id = "exec-reviewer-loop"
    step = WorkflowStep(
        step_id="s1",
        step_type=StepType.AGENT,
        name="draft the answer",
        description="reviewer re-delegation acceptance",
        parameters={},
    )
    context = WorkflowExecutionContext(
        workflow_id=workflow_id,
        execution_id=execution_id,
        steps=[step],
        start_step="s1",
        strategy=ExecutionStrategy.PARALLEL_CONSENSUS,
    )
    get_review_loop_state_machine().initialize_state(
        workflow_id, execution_id, WorkflowState.RUNNING
    )
    result = OrchestrationResult(
        workflow_id=workflow_id, execution_id=execution_id, total_steps=1
    )

    await agent._execute_parallel_consensus(context, result)

    assert verification.calls == 2, "reviewer must be consulted again after re-delegation"
    assert len(attempts) == 6, f"expected 3 branches x 2 attempts, got {attempts}"
    assert attempts[:3] == ["", "", ""]
    assert attempts[3:] == ["add the missing evidence"] * 3
    assert result.completed_steps == 1
    assert step.status == ExecutionStatus.COMPLETED
    assert step.result["output"] == "revised answer"
