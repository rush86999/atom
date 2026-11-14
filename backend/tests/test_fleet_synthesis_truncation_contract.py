"""Fleet final synthesis: completion honesty when output is cut off.

The live Goal 13 replay (2026-11-14) produced a user-visible answer that stopped
mid-action ("... on the specialist's reasoning that slipped deals are more
likely") while the fleet reported ``status=success``. The specialist's own
durable output contained all three corrective actions.

Root cause had two independent legs:

  * INPUT: the synthesis prompt capped each contribution at 2,000 characters,
    cutting the specialist's 3-action list after item 1;
  * OUTPUT: the provider's stop reason was not propagated by
    ``LLMService.generate_completion``, so a completion cut at the output-token
    cap could not be distinguished from a natural ``stop``.

These tests lock the replacement contract:

  * a complete synthesis (finish_reason=stop) is used and grounds every
    requested action plus the conditional $6,000 residual;
  * a truncated synthesis (finish_reason=length / max_tokens) is never shown as
    the business deliverable -- the existing durable raw-contribution fallback
    delivers the complete attributed specialist evidence;
  * a gateway that omits finish_reason is caught by the conservative text-shape
    backstop (the live answer ended on a continuation word);
  * input ``evidence_truncated`` stays a separate flag from output truncation;
  * provider failure uses the same one-call, no-retry fallback;
  * the durable result and a cached readback preserve the complete answer and
    the truncation disclosure without a second synthesis or specialist rerun;
  * a legacy cached ``used=True + evidence_truncated=True`` result is repaired
    from its own durable specialist results with zero provider calls.

No provider, network, live DB, or credential is used.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.fleet_admiral import FleetAdmiral
from core.models import (
    AgentRegistry,
    ChainLink,
    DelegationChain,
    TaskOperationRecord,
)

TENANT = "tenant-truncation"
WORKSPACE = "workspace-truncation"
TASK = (
    "Diagnose the quarterly revenue shortfall for the executive review and "
    "list the highest-impact corrective actions. Supplied figures: target "
    "240000 USD, closed 198000 USD, churn 21000 USD, slipped deals 15000 USD."
)
ROSTER = [{
    "agent_id": "spec-sales",
    "agent_name": "Sales Analyst",
    "domain": "sales",
    "capability_score": 0.9,
}]

ACTIONS = (
    "Recover slipped deals first",
    "Launch churn containment and win-back",
    "Reconcile the unexplained $6,000",
)

SPECIALIST_OUTPUT = (
    "**Sales-domain diagnosis**\n\n"
    "Under the supplied figures, quarterly revenue is **$198,000 vs. a "
    "$240,000 target**, a **$42,000 shortfall**. Churn is **$21,000** and "
    "slipped deals **$15,000**, leaving **$6,000 unexplained**.\n\n"
    "**Highest-impact corrective actions (proposals - not completed work)**\n\n"
    "1. **Recover slipped deals first ($15,000).** Run a deal-level recovery "
    "review and measure dollars recovered.\n\n"
    "2. **Launch churn containment and win-back ($21,000).** Segment churned "
    "revenue by reason and assign owners.\n\n"
    "3. **Reconcile the unexplained $6,000 and tighten forecast discipline.** "
    "Reconcile CRM to finance and review weekly.\n\n"
    "**Missing evidence / blockers**\n"
    "The figures are not independently validated against CRM or finance."
)

COMPLETE_SYNTHESIS = (
    "## DIRECT ANSWER:\n"
    "Quarterly revenue closed at $198,000 against a $240,000 target - a "
    "$42,000 shortfall. Churn ($21,000) and slipped deals ($15,000) explain "
    "$36,000, leaving $6,000 unexplained.\n\n"
    "## CONFLICTS RECONCILED:\n"
    "Only one specialist evidence set was supplied; no figure-level conflict "
    "exists. The additive attribution remains conditional on the supplied "
    "figures.\n\n"
    "## QUANTITATIVE RECONCILIATION:\n"
    "240,000 - 198,000 = 42,000 USD; 21,000 + 15,000 = 36,000 USD; "
    "42,000 - 36,000 = 6,000 USD unexplained.\n\n"
    "## REQUESTED DELIVERABLES:\n"
    "1. Diagnosis - supplied by the Sales Analyst.\n"
    "2. Corrective actions - provided as proposals (not executed).\n\n"
    "## PROPOSED NEXT STEPS (NOT EXECUTED):\n"
    "1. Recover slipped deals first, with an owner and a measurable recovery "
    "target.\n"
    "2. Launch churn containment and win-back by churn reason.\n"
    "3. Reconcile the unexplained $6,000 and tighten forecast discipline."
)

TRUNCATED_SYNTHESIS = (
    "## DIRECT ANSWER:\n"
    "Quarterly revenue closed at $198,000 against a $240,000 target - a "
    "$42,000 shortfall.\n\n"
    "## PROPOSED NEXT STEPS (NOT EXECUTED):\n"
    "1. **Prioritize slipped-deal recovery** - address the $15,000 first, on "
    "the specialist's reasoning that slipped deals are more likely"
)

# Same live symptom, but with an unambiguous structural cut: the sentence
# ends on an auxiliary verb. Used only to exercise the provider-omitted
# ``finish_reason`` backstop; the live evaluative ending above is weak
# evidence on its own and must not be relabelled as truncation.
STRONG_CUT_SYNTHESIS = (
    "## DIRECT ANSWER:\n"
    "Quarterly revenue closed at $198,000 against a $240,000 target - a "
    "$42,000 shortfall.\n\n"
    "## PROPOSED NEXT STEPS (NOT EXECUTED):\n"
    "1. **Prioritize slipped-deal recovery** - address the $15,000 first "
    "because the specialist's reasoning is"
)


class FakeSpecialist:
    """Records dispatch and returns the controlled specialist finding."""

    calls = []
    output = SPECIALIST_OUTPUT

    def __init__(self, agent_model, workspace_id="default", **kwargs):
        self.agent = agent_model
        self.workspace_id = workspace_id

    async def execute(self, task_input, context=None, step_callback=None):
        FakeSpecialist.calls.append({
            "agent_id": self.agent.id,
            "task_input": task_input,
            "context": context or {},
        })
        return {
            "success": True,
            "final_output": FakeSpecialist.output,
            "steps": [],
        }


class FakeLLM:
    """Controlled synthesis service; records every synthesis request."""

    def __init__(self, content=COMPLETE_SYNTHESIS, finish_reason="stop",
                 error=None):
        self.calls = []
        self.content = content
        self.finish_reason = finish_reason
        self.error = error

    async def generate_completion(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return {
            "success": True,
            "content": self.content,
            "finish_reason": self.finish_reason,
            "model": "synthesis-model",
            "provider": "synthesis-provider",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                      "total_tokens": 15},
        }


@pytest.fixture()
def world(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'synthesis-truncation.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    for model in (AgentRegistry, DelegationChain, ChainLink,
                  TaskOperationRecord):
        model.__table__.create(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    FakeSpecialist.calls = []
    FakeSpecialist.output = SPECIALIST_OUTPUT
    monkeypatch.setattr("core.generic_agent.GenericAgent", FakeSpecialist)
    try:
        yield Session
    finally:
        engine.dispose()


def _seed_chain(Session):
    db = Session()
    try:
        db.add(AgentRegistry(
            id="spec-sales", name="Sales Analyst",
            display_name="Sales Analyst", category="Sales",
            role="agent", type="personal",
            module_path="core.generic_agent", class_name="GenericAgent",
            tenant_id=TENANT, workspace_id=WORKSPACE, status="intern",
            enabled=True, capabilities=["sales"], specialty="sales"))
        db.add(DelegationChain(
            id="chain-truncation", tenant_id=TENANT, root_agent_id="atom_main",
            root_task=TASK, status="active",
            metadata_json={"workspace_id": WORKSPACE}))
        db.commit()
    finally:
        db.close()


def _run(Session, llm):
    with Session() as db:
        admiral = FleetAdmiral(db, llm)
        return asyncio.run(admiral.execute_recruited_specialists(
            task=TASK, user_id="user-truncation",
            chain_id="chain-truncation",
            roster=[dict(item) for item in ROSTER],
            tenant_id=TENANT, workspace_id=WORKSPACE, context={}))


def _durable_result(Session):
    db = Session()
    try:
        chain = db.query(DelegationChain).filter(
            DelegationChain.id == "chain-truncation").one()
        return chain.metadata_json["specialist_execution"]["result"]
    finally:
        db.close()


def _assert_all_actions_grounded(text):
    for action in ACTIONS:
        assert action in text, (action, text)
    # The conditional residual and its attribution survive the fallback.
    assert "6,000" in text
    assert "42,000" in text
    assert "Sales Analyst" in text


def test_complete_synthesis_is_used_and_grounds_all_requested_actions(world):
    _seed_chain(world)
    llm = FakeLLM()
    result = _run(world, llm)

    assert result["success"] is True
    assert result["status"] == "specialists_executed"
    synthesis = result["final_synthesis"]
    assert synthesis["used"] is True
    assert synthesis["reason"] is None
    assert synthesis["evidence_truncated"] is False
    assert synthesis["output_truncated"] is False
    assert synthesis["finish_reason"] == "stop"
    assert "Fleet synthesis" in result["final_output"]
    _assert_all_actions_grounded(result["final_output"])
    assert len(llm.calls) == 1
    assert len(FakeSpecialist.calls) == 1


def test_output_truncated_synthesis_falls_back_to_complete_attributed_actions(
        world):
    _seed_chain(world)
    llm = FakeLLM(content=TRUNCATED_SYNTHESIS, finish_reason="length")
    result = _run(world, llm)

    assert result["success"] is True
    synthesis = result["final_synthesis"]
    assert synthesis["used"] is False
    assert synthesis["reason"] == "output_truncated"
    assert synthesis["output_truncated"] is True
    # INPUT evidence was complete; only the provider output was cut.
    assert synthesis["evidence_truncated"] is False
    assert synthesis["finish_reason"] == "length"
    # The cut editorial text is not shown as the deliverable.
    assert "Prioritize slipped-deal recovery" not in result["final_output"]
    assert "cut off at the model's output limit" in result["final_output"]
    _assert_all_actions_grounded(result["final_output"])
    # One synthesis call, one specialist dispatch; no unpriced retry.
    assert len(llm.calls) == 1
    assert len(FakeSpecialist.calls) == 1


def test_missing_finish_reason_uses_only_strong_text_shape_backstop(world):
    _seed_chain(world)
    llm = FakeLLM(content=STRONG_CUT_SYNTHESIS, finish_reason=None)
    result = _run(world, llm)

    synthesis = result["final_synthesis"]
    assert synthesis["used"] is False
    assert synthesis["reason"] == "output_truncated"
    assert synthesis["output_truncated"] is True
    assert synthesis["finish_reason"] is None
    _assert_all_actions_grounded(result["final_output"])
    # Both provider vocabularies are recognized when they ARE reported.
    assert FleetAdmiral._synthesis_finish_reason_truncated("length") is True
    assert FleetAdmiral._synthesis_finish_reason_truncated(
        "max_tokens") is True
    assert FleetAdmiral._synthesis_finish_reason_truncated("stop") is False


@pytest.mark.parametrize("text", [
    "Completed items: 2 of 2",
    "Risk: unlikely",
    "Recovery is likely",
    "The slipped deals are more likely",
    "3 of 5 items complete",
    "Status: 2026-11-14",
])
def test_valid_concise_outputs_are_not_labelled_as_model_truncation(text):
    """A text shape is weak evidence, never proof of a provider cut.

    The literal outputs from the root negative probe are all valid, complete
    answers. In particular the old letters-only tokenizer dropped the final
    ``2`` in "2 of 2" and inspected the preceding "of", and evaluative words
    such as "likely" were treated as sentence-continuation tokens.
    """
    assert FleetAdmiral._synthesis_text_looks_cut_off(text) is False


@pytest.mark.parametrize("text", [
    "The corrective actions are",
    "Completed items: 2 of",
    "Open the attached evidence (",
])
def test_strong_structural_clues_are_the_only_shape_backstop(text):
    assert FleetAdmiral._synthesis_text_looks_cut_off(text) is True


def test_explicit_stop_reason_wins_over_an_evaluative_ending(world):
    """A known provider reason beats the weak text shape.

    The live answer ended "slipped deals are more likely". That ending alone
    is not evidence of a cut: with finish_reason="stop" the model's own fact
    controls, so the editorial answer is used rather than replaced.
    """
    _seed_chain(world)
    result = _run(world, FakeLLM(
        content=TRUNCATED_SYNTHESIS, finish_reason="stop"))

    synthesis = result["final_synthesis"]
    assert synthesis["used"] is True
    assert synthesis["reason"] is None
    assert synthesis["output_truncated"] is False
    assert synthesis["finish_reason"] == "stop"


def test_explicit_length_reason_wins_over_complete_looking_text(world):
    _seed_chain(world)
    result = _run(world, FakeLLM(
        content=COMPLETE_SYNTHESIS, finish_reason="length"))

    synthesis = result["final_synthesis"]
    assert synthesis["used"] is False
    assert synthesis["reason"] == "output_truncated"
    assert synthesis["output_truncated"] is True
    assert synthesis["finish_reason"] == "length"
    assert "## DIRECT ANSWER:" not in result["final_output"]
    _assert_all_actions_grounded(result["final_output"])


def test_evidence_truncated_is_distinct_from_output_truncation(world):
    _seed_chain(world)
    FakeSpecialist.output = (
        SPECIALIST_OUTPUT
        + "\n\nLong-tail specialist detail: "
        + ("x" * 7000)
        + " END-OF-DURABLE-EVIDENCE")
    llm = FakeLLM(content=COMPLETE_SYNTHESIS, finish_reason="stop")
    result = _run(world, llm)

    synthesis = result["final_synthesis"]
    assert synthesis["used"] is False
    assert synthesis["reason"] == "evidence_truncated"
    assert synthesis["evidence_truncated"] is True
    # The provider finished naturally: this is NOT output truncation.
    assert synthesis["output_truncated"] is False
    assert synthesis["finish_reason"] == "stop"
    assert "bounded evidence omitted specialist content" in (
        result["final_output"])
    # The full durable contribution (past the 6,000-char prompt slice) is
    # delivered, so the long tail is not silently lost.
    assert "END-OF-DURABLE-EVIDENCE" in result["final_output"]
    _assert_all_actions_grounded(result["final_output"])


def test_provider_failure_uses_same_bounded_fallback_without_retry(world):
    _seed_chain(world)
    llm = FakeLLM(error=RuntimeError("synthesis transport down"))
    result = _run(world, llm)

    assert result["success"] is True
    synthesis = result["final_synthesis"]
    assert synthesis["used"] is False
    assert synthesis["reason"] == "error:RuntimeError"
    assert "Final synthesis unavailable" in result["final_output"]
    _assert_all_actions_grounded(result["final_output"])
    # No retry, no hidden second synthesis, no specialist re-dispatch.
    assert len(llm.calls) == 1
    assert len(FakeSpecialist.calls) == 1


def test_cached_readback_preserves_truncated_fallback_without_rerun(world):
    _seed_chain(world)
    llm = FakeLLM(content=TRUNCATED_SYNTHESIS, finish_reason="length")
    first = _run(world, llm)
    second = _run(world, llm)

    assert first["success"] is True and second["success"] is True
    assert second["cached"] is True
    assert second["final_output"] == first["final_output"]
    assert second["final_synthesis"]["used"] is False
    assert second["final_synthesis"]["reason"] == "output_truncated"
    assert second["final_synthesis"]["output_truncated"] is True
    assert second["final_synthesis"]["finish_reason"] == "length"
    _assert_all_actions_grounded(second["final_output"])
    # Exactly one synthesis call and one specialist dispatch across replay.
    assert len(llm.calls) == 1
    assert len(FakeSpecialist.calls) == 1
    durable = _durable_result(world)
    assert durable["final_output"] == first["final_output"]
    assert durable["final_synthesis"]["used"] is False


def test_legacy_cached_incomplete_synthesis_is_repaired_from_durable(world):
    _seed_chain(world)
    first = _run(world, FakeLLM())
    assert first["final_synthesis"]["used"] is True

    # Simulate a durable result written by the pre-fix code: used=True and
    # evidence_truncated=True (the live replay's shape), with a cut answer.
    db = world()
    try:
        chain = db.query(DelegationChain).filter(
            DelegationChain.id == "chain-truncation").one()
        metadata = dict(chain.metadata_json or {})
        cached = dict(metadata["specialist_execution"])
        result = dict(cached["result"])
        result["final_output"] = (
            "Final synthesis (from attributed specialist work):\n"
            "## PROPOSED NEXT STEPS (NOT EXECUTED):\n"
            "1. Prioritize slipped-deal recovery ... more likely")
        result["final_synthesis"] = {
            **result["final_synthesis"],
            "used": True,
            "reason": None,
            "evidence_truncated": True,
            "output_truncated": False,
            "finish_reason": None,
        }
        cached["result"] = result
        metadata["specialist_execution"] = cached
        chain.metadata_json = metadata
        db.commit()
    finally:
        db.close()

    # A cached readback must never call the synthesis service or re-dispatch.
    llm = FakeLLM(error=AssertionError("synthesis must not run on cache hit"))
    repaired = _run(world, llm)

    assert repaired["cached"] is True
    assert repaired["final_synthesis"]["used"] is False
    assert repaired["final_synthesis"]["reason"] == "evidence_truncated"
    assert repaired["final_synthesis"]["repaired_from_durable"] is True
    assert "more likely" not in repaired["final_output"]
    _assert_all_actions_grounded(repaired["final_output"])
    assert len(llm.calls) == 0
    assert len(FakeSpecialist.calls) == 1
    # The repaired answer is durable, so this is not a one-read illusion.
    durable = _durable_result(world)
    assert durable["final_output"] == repaired["final_output"]
    assert durable["final_synthesis"]["used"] is False


def _response(finish_reason, content="answer"):
    return SimpleNamespace(choices=[SimpleNamespace(
        finish_reason=finish_reason,
        message=SimpleNamespace(content=content, reasoning_content=None),
    )])


def test_byok_handler_writes_the_call_local_finish_reason_sink():
    from core.llm.byok_handler import BYOKHandler

    handler = object.__new__(BYOKHandler)
    handler._last_finish_reason = None
    handler._last_reasoning = None

    first_sink = {}
    second_sink = {}
    handler._stash_last_reasoning(_response("stop"), first_sink)
    # A concurrent call on the same shared handler overwrites the legacy
    # attribute, but cannot touch the first call's sink.
    handler._stash_last_reasoning(_response("max_tokens"), second_sink)

    assert first_sink["finish_reason"] == "stop"
    assert second_sink["finish_reason"] == "max_tokens"
    assert handler._last_finish_reason == "max_tokens"
    assert first_sink is not second_sink


def _service_with_handler(monkeypatch, handler):
    from core.llm_service import LLMService

    service = object.__new__(LLMService)
    service._workspace_id = WORKSPACE
    service._tenant_id = TENANT
    service._db = None
    service.continuous_learning = None
    # No tokenizer construction is needed for this contract: the assertion is
    # only that the handler's provider stop reason reaches the caller.
    service.estimate_tokens = lambda *args, **kwargs: 5
    monkeypatch.setattr(service, "_get_handler", lambda **kwargs: handler)
    return service


def test_generate_completion_surfaces_finish_reason_for_text_only_handler(
        monkeypatch):
    """Backward compatibility: a handler that only sets the legacy attribute
    still works with the unchanged text API."""
    class Handler:
        workspace_id = WORKSPACE
        _last_used_model = "synthesis-model"
        _last_used_provider = "synthesis-provider"
        _last_finish_reason = "length"
        _last_feedback_decision_id = None
        _last_reasoning = None

        async def generate_response(self, **kwargs):
            return "cut"

    service = _service_with_handler(monkeypatch, Handler())
    result = asyncio.run(service.generate_completion(
        messages=[{"role": "user", "content": "hello"}],
        workspace_id=WORKSPACE, tenant_id=TENANT))

    assert result["success"] is True
    assert result["finish_reason"] == "length"


def test_generate_completion_prefers_the_per_call_finish_reason_sink(
        monkeypatch):
    """The per-call sink beats a stale shared ``_last_finish_reason``."""
    class Handler:
        workspace_id = WORKSPACE
        _last_used_model = "synthesis-model"
        _last_used_provider = "synthesis-provider"
        # Stale value from some other call on the shared handler.
        _last_finish_reason = "stop"
        _last_feedback_decision_id = None
        _last_reasoning = None

        async def generate_response(self, *, finish_reason_sink, **kwargs):
            finish_reason_sink["finish_reason"] = "max_tokens"
            return "cut"

    service = _service_with_handler(monkeypatch, Handler())
    result = asyncio.run(service.generate_completion(
        messages=[{"role": "user", "content": "hello"}],
        workspace_id=WORKSPACE, tenant_id=TENANT))

    assert result["finish_reason"] == "max_tokens"


def test_joined_concurrent_calls_never_share_finish_reason(monkeypatch):
    """Positive/failure/unknown calls on ONE shared handler stay isolated.

    The producer writes the genuine provider reason into the caller-owned
    sink at the accepted response, exactly as BYOKHandler now does, and then
    parks until all three calls have arrived. Each call overwrites the
    handler's shared ``_last_finish_reason`` before any call returns, which
    is the live interleaving (stash at the response, then await post-response
    feedback before returning). Without per-call metadata the consumer would
    read one neighbour's reason for every call.
    """
    expected = {"positive": "stop", "truncated": "length", "unknown": None}

    class SharedProducer:
        workspace_id = WORKSPACE
        _last_used_model = "shared-model"
        _last_used_provider = "shared-provider"
        _last_feedback_decision_id = None
        _last_reasoning = None
        _last_finish_reason = None

        def __init__(self):
            self.arrived = 0
            self.all_arrived = asyncio.Event()
            self.sinks = []

        async def generate_response(self, *, prompt, finish_reason_sink,
                                    **kwargs):
            reason = expected[prompt]
            finish_reason_sink["finish_reason"] = reason
            self.sinks.append(finish_reason_sink)
            self._last_finish_reason = reason
            self.arrived += 1
            if self.arrived == len(expected):
                self.all_arrived.set()
            await self.all_arrived.wait()
            return f"answer:{prompt}"

    producer = SharedProducer()
    service = _service_with_handler(monkeypatch, producer)

    async def joined():
        return await asyncio.gather(*(
            service.generate_completion(
                messages=[{"role": "user", "content": key}],
                workspace_id=WORKSPACE, tenant_id=TENANT)
            for key in expected
        ))

    results = asyncio.run(joined())

    assert [result["finish_reason"] for result in results] == [
        "stop", "length", None]
    # Three distinct sink objects, one per consumer call.
    assert len({id(sink) for sink in producer.sinks}) == 3
    # The one shared attribute can match at most one result; it cannot serve
    # the other two correctly, proving the results did not come from it.
    shared = producer._last_finish_reason
    assert sum(result["finish_reason"] == shared for result in results) <= 1
