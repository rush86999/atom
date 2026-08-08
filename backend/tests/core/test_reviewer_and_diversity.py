"""
P4 — Diversity-aware sampling + ReviewerVerifier (W3).

Two concerns:
1. Diversity-aware init (P4a): ``diversity_overlays`` rotates perspectives per
   sample; disabled by default (kill-switch parity).
2. ReviewerVerifier (P4b): the Virtual Biotech's "Scientific Reviewer" —
   evaluates the winner on addresses/evidence/thoroughness, accepts or signals
   re-delegation. NOT debate (never multi-round; fail-opens to the winner).
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.llm.self_consistency_voter import SelfConsistencyVoter
from core.orchestration.conductor_agent import (
    ConductorAgent, ExecutionStrategy, WorkflowExecutionContext, WorkflowStep,
)
from core.orchestration.verification import (
    ReviewerVerifier, VerificationOrchestrator, VerificationStrategy,
)
from core.orchestration.verification.voting import VotingVerifier
from core.orchestration.workflow_state_machine import (
    WorkflowState, WorkflowStateMachine,
)


# ---------------------------------------------------------------------------
# P4a — diversity-aware sampling
# ---------------------------------------------------------------------------
def test_diversity_overlays_disabled_by_default():
    """Kill-switch parity: disabled → empty overlays (no behavior change)."""
    overlays = SelfConsistencyVoter.diversity_overlays(3, enabled=False)
    assert overlays == ["", "", ""], "disabled must produce empty overlays (parity)"


def test_diversity_overlays_enabled_rotates_perspectives():
    overlays = SelfConsistencyVoter.diversity_overlays(4, enabled=True)
    assert len(overlays) == 4
    assert len({o for o in overlays if o}) >= 2, "enabled must vary perspectives across samples"


@pytest.mark.asyncio
async def test_vote_wires_diversity_overlays_when_enabled(monkeypatch):
    """P4a wiring: flag on → each vote sample gets a distinct perspective overlay."""
    monkeypatch.setenv("ATOM_MOA_DIVERSITY_ENABLED", "true")

    class FakeHandler:
        def __init__(self):
            self.sys_instructions: list = []

        async def generate_structured_response(self, **kwargs):
            self.sys_instructions.append(kwargs.get("system_instruction", ""))
            return {"answer": "x"}

    handler = FakeHandler()
    voter = SelfConsistencyVoter(handler=handler)
    await voter.vote("task", dict, sample_count=3)

    assert len(handler.sys_instructions) == 3
    assert len({s for s in handler.sys_instructions if s}) >= 2, "samples must diverge"
    assert any("Approach this methodically" in s for s in handler.sys_instructions)


@pytest.mark.asyncio
async def test_vote_kill_switch_parity_no_overlay(monkeypatch):
    """P4a kill-switch parity: flag off → identical base instruction, no overlay."""
    monkeypatch.setenv("ATOM_MOA_DIVERSITY_ENABLED", "false")

    class FakeHandler:
        def __init__(self):
            self.sys_instructions: list = []

        async def generate_structured_response(self, **kwargs):
            self.sys_instructions.append(kwargs.get("system_instruction", ""))
            return {"answer": "x"}

    handler = FakeHandler()
    voter = SelfConsistencyVoter(handler=handler)
    await voter.vote("task", dict, sample_count=3, system_instruction="Base sys.")

    assert handler.sys_instructions == ["Base sys.", "Base sys.", "Base sys."]


def test_moa_aggregator_prompt_high_agreement_harmonizes():
    """P4a confidence-modulated update: high consensus → harmonize, no invention."""
    from core.llm.byok_handler import BYOKHandler
    prompt = BYOKHandler._build_moa_aggregator_prompt(
        "do the thing", ["a", "b"], agreement=0.9
    )
    assert "[CONSENSUS]" in prompt
    assert "WITHOUT introducing new claims" in prompt


def test_moa_aggregator_prompt_low_agreement_resolves():
    from core.llm.byok_handler import BYOKHandler
    prompt = BYOKHandler._build_moa_aggregator_prompt(
        "do the thing", ["a", "b"], agreement=0.33
    )
    assert "[CONSENSUS]" in prompt
    assert "resolve the contradictions" in prompt


def test_moa_aggregator_prompt_legacy_when_no_agreement():
    """No agreement info (legacy callers) → byte-identical legacy prompt shape."""
    from core.llm.byok_handler import BYOKHandler
    legacy = BYOKHandler._build_moa_aggregator_prompt("do the thing", ["a", "b"])
    assert "[CONSENSUS]" not in legacy
    assert "synthesize the single best final answer" in legacy


# ---------------------------------------------------------------------------
# P4b — ReviewerVerifier
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reviewer_accepts_on_positive_verdict():
    llm = AsyncMock()
    llm.generate_response = AsyncMock(return_value='{"accept": true, "score": 0.9, "feedback": ""}')
    rv = ReviewerVerifier(llm_service=llm)
    result = await rv.verify(["the answer"], step=MagicMock(description="do X"), context=MagicMock())
    assert result.winner == "the answer", "accepted → winner returned"
    assert result.details["reviewed"] is True
    assert result.details["accepted"] is True


@pytest.mark.asyncio
async def test_reviewer_signals_redelegation_on_reject():
    """Rejected → winner is None so the orchestrator can re-delegate (NOT pick another)."""
    llm = AsyncMock()
    llm.generate_response = AsyncMock(
        return_value='{"accept": false, "score": 0.2, "feedback": "missing edge case"}'
    )
    rv = ReviewerVerifier(llm_service=llm)
    result = await rv.verify(["weak answer"], step=MagicMock(description="do X"), context=MagicMock())
    assert result.winner is None, "rejected → winner None (signal re-delegation, not a swap)"
    assert result.details["accepted"] is False
    assert "missing edge case" in result.reason


@pytest.mark.asyncio
async def test_reviewer_failopens_without_llm():
    """No LLM → can't review → accept the winner (never block the swarm)."""
    rv = ReviewerVerifier(llm_service=None)
    result = await rv.verify(["ans"], step=None, context=MagicMock())
    assert result.winner == "ans"
    assert result.details["reviewed"] is False


@pytest.mark.asyncio
async def test_reviewer_failopens_on_timeout():
    llm = AsyncMock()

    async def _slow(_):
        await asyncio.sleep(100)
    llm.generate_response = _slow
    rv = ReviewerVerifier(llm_service=llm, timeout_seconds=0.05)
    result = await rv.verify(["ans"], step=None, context=MagicMock())
    assert result.winner == "ans", "timeout → accept (fail-open), never block"


@pytest.mark.asyncio
async def test_reviewer_registered_in_orchestrator():
    """The REVIEW strategy must be wired into the dispatcher's verifier registry."""
    orch = VerificationOrchestrator()
    assert VerificationStrategy.REVIEW in orch._verifiers
    assert isinstance(orch._verifiers[VerificationStrategy.REVIEW], ReviewerVerifier)


# ---------------------------------------------------------------------------
# P4c — reviewer re-delegation loop (conductor)
# ---------------------------------------------------------------------------


def _p4c_step() -> WorkflowStep:
    return WorkflowStep(
        step_id="s1",
        name="specialist step",
        description="analyze the edge case",
        parameters={"verification_strategy": "review"},  # force the REVIEW strategy
    )


def _p4c_review_llm(rejections_left: int, feedback: str = "missing edge case"):
    """An LLM double whose verdicts are: N rejections, then accept."""
    llm = MagicMock()

    def _generate_response(prompt: str) -> str:
        nonlocal rejections_left
        if rejections_left > 0:
            rejections_left -= 1
            return f'{{"accept": false, "score": 0.2, "feedback": "{feedback}"}}'
        return '{"accept": true, "score": 0.9, "feedback": ""}'

    llm.generate_response = _generate_response
    return llm


@pytest.mark.asyncio
async def test_reviewer_loop_redelegates_with_feedback(monkeypatch):
    """Flag ON: a REVIEW rejection re-delegates to the specialist with feedback."""
    monkeypatch.setenv("ATOM_REVIEWER_LOOP_ENABLED", "true")
    conductor = ConductorAgent()
    calls = []

    async def fake_executor(step, ctx):
        calls.append(dict(step_id=step.step_id, feedback=step.parameters.get("_review_feedback", "")))
        return {"step_id": step.step_id, "status": "completed", "output": f"draft {len(calls)}"}

    conductor.set_step_executor(fake_executor)
    orch = VerificationOrchestrator(llm_service=_p4c_review_llm(rejections_left=1))
    conductor.set_verification_orchestrator(orch)

    step = _p4c_step()
    context = WorkflowExecutionContext(
        workflow_id="wf_review_loop", execution_id="exec_review_loop", steps=[step],
        start_step="s1",
    )
    result = await conductor.execute_workflow(
        [step], "s1", context, strategy=ExecutionStrategy.PARALLEL_CONSENSUS
    )

    # 1 initial pass + 1 re-delegation (reject → accept), 3 branches each.
    assert len(calls) == 6, "initial 3 branches + 3 re-delegated branches"
    # The re-delegated branches carried the reviewer's feedback.
    assert any(c["feedback"] == "missing edge case" for c in calls[3:])
    assert step.retry_count == 1, "one re-delegation attached"
    assert result.completed_steps == 1
    assert result.failed_steps == 0
    assert step.result["output"] == "draft 4", "step completed with the accepted winner"


@pytest.mark.asyncio
async def test_reviewer_loop_flag_off_preserves_voting_fallback(monkeypatch):
    """Flag OFF (default): a REVIEW rejection folds into the voting safety net."""
    monkeypatch.delenv("ATOM_REVIEWER_LOOP_ENABLED", raising=False)
    conductor = ConductorAgent()
    calls = []

    async def fake_executor(step, ctx):
        calls.append(step.step_id)
        return {"step_id": step.step_id, "status": "completed", "output": "candidate"}

    conductor.set_step_executor(fake_executor)
    # Reviewer always rejects — but the loop is OFF, so the orchestrator's
    # universal fallback converts the rejection into a voting pass.
    orch = VerificationOrchestrator(llm_service=_p4c_review_llm(rejections_left=99))
    conductor.set_verification_orchestrator(orch)

    step = _p4c_step()
    context = WorkflowExecutionContext(
        workflow_id="wf_review_loop_off", execution_id="exec_review_loop_off",
        steps=[step], start_step="s1",
    )
    result = await conductor.execute_workflow(
        [step], "s1", context, strategy=ExecutionStrategy.PARALLEL_CONSENSUS
    )

    assert len(calls) == 3, "single pass — no re-delegation with the loop off"
    assert result.completed_steps == 1, "voting fallback still completes the step"
    assert step.result["output"] == "candidate", "fallback winner is the voted candidate"


@pytest.mark.asyncio
async def test_reviewer_loop_exhausts_rejections_to_failed(monkeypatch):
    """Flag ON + persistent rejection → fail loudly with feedback, never silent None."""
    monkeypatch.setenv("ATOM_REVIEWER_LOOP_ENABLED", "true")
    conductor = ConductorAgent()
    calls = []

    async def fake_executor(step, ctx):
        calls.append(step.step_id)
        return {"step_id": step.step_id, "status": "completed", "output": f"draft {len(calls)}"}

    conductor.set_step_executor(fake_executor)
    orch = VerificationOrchestrator(llm_service=_p4c_review_llm(rejections_left=99))
    conductor.set_verification_orchestrator(orch)

    step = _p4c_step()
    context = WorkflowExecutionContext(
        workflow_id="wf_review_loop_fail", execution_id="exec_review_loop_fail",
        steps=[step], start_step="s1",
    )
    result = await conductor.execute_workflow(
        [step], "s1", context, strategy=ExecutionStrategy.PARALLEL_CONSENSUS
    )

    # Initial pass + MAX_REVIEWER_REDELEGATIONS re-delegations, 3 branches each.
    from core.orchestration.reviewer_loop import MAX_REVIEWER_REDELEGATIONS
    assert len(calls) == 3 * (1 + MAX_REVIEWER_REDELEGATIONS)
    assert result.failed_steps == 1
    assert any("missing edge case" in e for e in result.errors), "feedback surfaced in error"


# ---------------------------------------------------------------------------
# P4c — state machine parking (RUNNING → WAITING while re-delegating)
# ---------------------------------------------------------------------------


def test_review_wait_state_machine_parking():
    """Review re-delegation parks the workflow in WAITING, then resumes RUNNING."""
    from core.orchestration.reviewer_loop import (
        enter_review_waiting, install_state_machine_hooks, resume_after_review,
    )

    machine = WorkflowStateMachine()
    install_state_machine_hooks(machine)
    machine.initialize_state("wf_park", "exec_park")

    # Drive to RUNNING.
    assert machine.transition("wf_park", "exec_park", WorkflowState.VALIDATED).value == "success"
    assert machine.transition("wf_park", "exec_park", WorkflowState.QUEUED).value == "success"
    assert machine.transition("wf_park", "exec_park", WorkflowState.RUNNING).value == "success"

    # Park for re-delegation.
    parked = enter_review_waiting(machine, "wf_park", "exec_park", "missing edge case")
    assert parked.value == "success"
    assert machine.get_state("wf_park") == WorkflowState.WAITING

    # A non-review RUNNING→WAITING is still allowed (guard default-allow).
    machine2 = WorkflowStateMachine()
    install_state_machine_hooks(machine2)
    machine2.initialize_state("wf_plain", "exec_plain")
    machine2.transition("wf_plain", "exec_plain", WorkflowState.VALIDATED)
    machine2.transition("wf_plain", "exec_plain", WorkflowState.QUEUED)
    assert machine2.transition("wf_plain", "exec_plain", WorkflowState.RUNNING).value == "success"
    plain_wait = machine2.transition("wf_plain", "exec_plain", WorkflowState.WAITING)
    assert plain_wait.value == "success"

    # Resume.
    resumed = resume_after_review(machine, "wf_park", "exec_park")
    assert resumed.value == "success"
    assert machine.get_state("wf_park") == WorkflowState.RUNNING
