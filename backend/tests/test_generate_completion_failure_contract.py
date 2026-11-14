"""Completion facade: a failed generation is never a successful answer.

Live boundary (2026-11-14, root negative probe): the bounded synthesis called
``LLMService.generate_completion`` with a 2,000-token budget. The BYOK ladder
made ZERO provider requests (the configured gateway id was excluded by the
installation provider policy), so ``generate_response`` returned its legacy
text "I couldn't generate a response — every configured provider failed. Last
error: no provider attempted." ``generate_completion`` unconditionally
returned ``success=True`` with that text as ``content`` (and inferred
``provider="deepseek"`` from the model string), so Fleet Admiral appended a
quantitative block to it as if it were a valid synthesis. The earlier 1,400
variant hit the same seam differently: the provider answered
``finish_reason="length"`` with no visible content, the handler raised its
empty-completion error internally, and the facade still published the failure
text as an accepted reply.

These tests lock the replacement contract at the shared BYOK ->
``LLMService.generate_completion`` seam:

  * every terminal failure (all providers failed / zero attempts / empty
    generation / policy block / budget denial / accounting refusal / trial /
    no providers) returns ``success=False`` with EMPTY ``content``/``text``
    and no fabricated served provider/model;
  * the human-readable cause lives in ``error``/``failure``; attempt
    diagnostics (last error, retained attempt stop reason, candidate count)
    are call-local, never borrowed from shared handler state;
  * an accepted non-empty response keeps the REAL served provider/model and
    provider stop reason;
  * concurrent calls on one shared handler preserve each call's own status,
    identity and stop metadata;
  * the legacy ``generate_response`` text API still returns exactly the same
    strings to its direct consumers, and a producer that cannot receive the
    outcome sink keeps the historical ``success=True`` contract;
  * a real Fleet synthesis provider failure withholds the editorial answer and
    falls back to the complete attributed contributions (covered in
    ``test_fleet_synthesis_truncation_contract.py``).

No provider, network, live DB, credential or push is used.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

import core.llm.byok_handler as bh
from core.llm.byok_handler import (
    BYOKHandler,
    QueryComplexity,
    _AccountingBlockedError,
)
from core.llm.provider_policy import ProviderPolicy
from core.llm_service import LLMService

TENANT = "tenant-completion-failure"
WORKSPACE = "workspace-completion-failure"


@contextmanager
def _no_db():
    """The routing/plan lookup tolerates a missing session (it is guarded)."""
    yield None


class _Health:
    def record_call(self, *args, **kwargs):
        pass


class _RaisingCompletions:
    def __init__(self):
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        raise RuntimeError("transport exploded")


class _RaisingClient:
    def __init__(self):
        self.completions = _RaisingCompletions()
        self.chat = SimpleNamespace(completions=self.completions)


class _EmptyLengthCompletions:
    def __init__(self):
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(choices=[SimpleNamespace(
            finish_reason="length",
            message=SimpleNamespace(content=None, reasoning_content=None),
        )])


class _EmptyLengthClient:
    def __init__(self):
        self.completions = _EmptyLengthCompletions()
        self.chat = SimpleNamespace(completions=self.completions)


class _AcceptedCompletions:
    def __init__(self, content="The real accepted answer."):
        self.content = content
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(choices=[SimpleNamespace(
            finish_reason="stop",
            message=SimpleNamespace(
                content=self.content, reasoning_content=None),
        )])


class _AcceptedClient:
    def __init__(self, content="The real accepted answer."):
        self.completions = _AcceptedCompletions(content)
        self.chat = SimpleNamespace(completions=self.completions)


async def _async_noop(*args, **kwargs):
    return None


def _handler(
    clients,
    *,
    policy=None,
    ranked=None,
    trial=False,
    budget=False,
    admit_error=None,
):
    """A REAL BYOKHandler with only the external edges replaced.

    ``object.__new__`` avoids constructing credentials/clients from the
    machine; ``generate_response`` itself is the production implementation,
    including the provider ladder, the empty-content guard and the terminal
    failure branches this contract is about. ``get_db_session`` is patched to
    a null context by the fixture, so no scratch/live DB is touched.
    """
    handler = object.__new__(BYOKHandler)
    handler.workspace_id = WORKSPACE
    handler.tenant_id = TENANT
    handler.clients = dict(clients)
    handler.async_clients = {}
    handler.provider_policy = policy or ProviderPolicy(mode="unset")
    handler._local_routes = {}
    handler._last_used_model = None
    handler._last_used_provider = None
    handler._last_finish_reason = None
    handler._last_reasoning = None
    handler._last_feedback_decision_id = None
    handler._pending_routing_result_id = None
    handler._last_ranking_skips = []
    handler.health_monitor = _Health()
    handler.refresh_credentials_if_changed = lambda: None
    handler._is_trial_restricted = lambda: trial
    handler.analyze_query_complexity = (
        lambda *args, **kwargs: QueryComplexity.MODERATE)
    handler._local_only_active = lambda: False
    handler._llm_taint_check = lambda *args, **kwargs: None
    handler._provider_cooldown_active = lambda *args, **kwargs: False
    handler._model_cooldown_active = lambda *args, **kwargs: False
    handler._dispatch_catalog_admits = lambda *args, **kwargs: True
    handler._provider_models_cached = lambda *args, **kwargs: []
    handler._record_outcome_feedback = _async_noop
    handler._track_llm_call = lambda *args, **kwargs: None
    handler._track_rate_usage = lambda *args, **kwargs: None
    handler._capture_echoed_model = lambda *args, **kwargs: None
    handler._bench_model = lambda *args, **kwargs: None
    handler._bench_provider_on_quota_error = lambda *args, **kwargs: False
    if admit_error is not None:
        def _admit(*args, **kwargs):
            raise admit_error
        handler._admit_physical_attempt = _admit
    else:
        handler._admit_physical_attempt = lambda *args, **kwargs: 0.0
    handler._settle_physical_response = lambda *args, **kwargs: None

    async def _ranked(*args, **kwargs):
        return list(ranked or [])

    handler.get_ranked_providers = _ranked
    if budget:
        bh.llm_usage_tracker.is_budget_exceeded = lambda *a, **k: True
    else:
        bh.llm_usage_tracker.is_budget_exceeded = lambda *a, **k: False
    return handler


def _service(handler):
    """The REAL LLMService.generate_completion over the supplied handler."""
    service = object.__new__(LLMService)
    service._workspace_id = WORKSPACE
    service._tenant_id = TENANT
    service._db = None
    service.continuous_learning = None
    service._get_handler = lambda **kwargs: handler
    service.estimate_tokens = lambda *args, **kwargs: 7
    return service


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """No DB, no budget ledger, no provider/credential construction."""
    monkeypatch.setattr(bh, "get_db_session", _no_db)
    monkeypatch.setattr(
        bh.llm_usage_tracker, "is_budget_exceeded",
        lambda *args, **kwargs: False)
    yield


def _assert_failure(result, reason):
    assert result["success"] is False
    assert result["content"] == ""
    assert result["text"] == ""
    # No fabricated served route: the request alias and a provider guessed
    # from the model name are not a pair that answered.
    assert result["model"] is None
    assert result["provider"] is None
    assert result["finish_reason"] is None
    assert result["usage"] == {
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    assert result["error"]
    assert result["failure"]["reason"] == reason
    assert result["failure"]["message"]
    # The legacy error text must never be republished as answer content.
    assert "couldn't generate" not in result["content"]
    assert "couldn't generate" not in result["text"]


def test_all_providers_failed_is_a_structured_failure_not_content():
    client = _RaisingClient()
    handler = _handler({"p": client}, ranked=[("p", "m")])

    result = asyncio.run(_service(handler).generate_completion(
        messages=[{"role": "user", "content": "synthesize this"}]))

    _assert_failure(result, "all_providers_failed")
    assert client.completions.calls == 1
    failure = result["failure"]
    assert failure["last_error"] == "transport exploded"
    assert failure["last_error_type"] == "RuntimeError"
    assert failure["candidate_count"] == 1
    assert failure["routing"] == "ranked_candidates_exhausted"
    assert "couldn't generate a response" in result["error"]


def test_empty_length_generation_is_not_an_accepted_reply():
    """HTTP-200 + finish_reason=length + no visible content (live shape)."""
    client = _EmptyLengthClient()
    handler = _handler({"p": client}, ranked=[("p", "m")])

    result = asyncio.run(_service(handler).generate_completion(
        messages=[{"role": "user", "content": "synthesize this"}]))

    _assert_failure(result, "empty_generation")
    assert client.completions.calls == 1
    failure = result["failure"]
    # The provider stop reason is retained as ATTEMPT evidence only.
    assert failure["last_finish_reason"] == "length"
    assert result["finish_reason"] is None
    assert failure["last_error_type"] == "_EmptyCompletionError"
    assert "no visible content" in result["error"]


def test_zero_attempt_policy_block_is_not_success_and_invents_no_route():
    """The live 2,000-token variant: zero provider requests.

    Ranking applies the installation provider policy before BPC, so the
    legacy provider id is filtered out and the cascade + sweep both have
    nothing to dispatch. The old facade called that an answer.
    """
    client = _RaisingClient()
    policy = ProviderPolicy(
        mode="selected", allowed_providers=frozenset({"deepseek"}),
        revision="rev-live")
    handler = _handler(
        {"opencode": client}, policy=policy, ranked=[])

    result = asyncio.run(_service(handler).generate_completion(
        messages=[{"role": "user", "content": "synthesize this"}],
        max_tokens=2000))

    _assert_failure(result, "policy_blocked")
    # ZERO transport requests: this is the exact live diagnosis.
    assert client.completions.calls == 0
    failure = result["failure"]
    assert failure["candidate_count"] == 0
    assert failure["last_error"] is None
    assert failure["last_error_type"] is None
    assert failure["last_finish_reason"] is None
    assert failure["routing"] == "provider_policy_excluded_all"
    assert failure["policy"] == {
        "mode": "selected",
        "allowed_providers": ["deepseek"],
        "revision": "rev-live",
    }
    assert "No provider was attempted" in result["error"]
    assert "policy" in result["error"]
    assert "deepseek" in result["error"]


def test_budget_denial_is_a_structured_failure_with_zero_calls():
    client = _RaisingClient()
    handler = _handler({"p": client}, ranked=[("p", "m")], budget=True)

    result = asyncio.run(_service(handler).generate_completion(
        messages=[{"role": "user", "content": "synthesize this"}]))

    _assert_failure(result, "budget_exceeded")
    assert client.completions.calls == 0
    assert "BUDGET EXCEEDED" in result["error"]


def test_accounting_refusal_is_a_structured_failure_with_zero_calls():
    client = _RaisingClient()
    handler = _handler(
        {"p": client}, ranked=[("p", "m")],
        admit_error=_AccountingBlockedError(
            "budget authorization unavailable for this request"))

    result = asyncio.run(_service(handler).generate_completion(
        messages=[{"role": "user", "content": "synthesize this"}]))

    _assert_failure(result, "accounting_blocked")
    assert client.completions.calls == 0
    assert result["failure"]["last_error_type"] == "_AccountingBlockedError"


@pytest.mark.parametrize(
    "kwargs, reason",
    [
        ({"clients": {}, "ranked": [], "trial": False},
         "no_providers_configured"),
        ({"clients": {"p": object()}, "ranked": [], "trial": True},
         "trial_restricted"),
    ],
)
def test_pre_dispatch_refusals_are_structured_failures(kwargs, reason):
    handler = _handler(**kwargs)
    result = asyncio.run(_service(handler).generate_completion(
        messages=[{"role": "user", "content": "synthesize this"}]))
    _assert_failure(result, reason)


def test_accepted_reply_keeps_real_served_identity_and_stop_reason():
    client = _AcceptedClient("The real accepted answer.")
    handler = _handler({"p": client}, ranked=[("p", "m")])

    result = asyncio.run(_service(handler).generate_completion(
        messages=[{"role": "user", "content": "synthesize this"}]))

    assert result["success"] is True
    assert result["content"] == "The real accepted answer."
    assert result["text"] == "The real accepted answer."
    assert result["model"] == "m"
    assert result["provider"] == "p"
    assert result["finish_reason"] == "stop"
    assert client.completions.calls == 1


def test_legacy_text_api_still_returns_the_same_failure_text():
    """Direct generate_response consumers keep the historical string."""
    handler = _handler({"p": _RaisingClient()}, ranked=[("p", "m")])

    text = asyncio.run(handler.generate_response(
        prompt="synthesize this",
        system_instruction="be useful",
        model_type="auto",
        temperature=0.2,
        turn_index=0,
        estimated_tokens=10,
        messages=[{"role": "user", "content": "synthesize this"}],
    ))

    assert text.startswith(
        "I couldn't generate a response — every configured provider failed.")
    assert "transport exploded" in text


def test_unwritten_outcome_sink_keeps_the_legacy_success_contract():
    """A ``**kwargs`` wrapper that drops the sink behaves as before.

    Only an explicitly written outcome can turn a text return into a
    structured failure; silence is the legacy contract, not a guessed
    failure.
    """
    class LegacyWrapper:
        workspace_id = WORKSPACE
        _last_used_model = "legacy-model"
        _last_used_provider = "legacy-provider"
        _last_feedback_decision_id = None
        _last_reasoning = None

        async def generate_response(self, **kwargs):
            self.seen = kwargs
            return "legacy answer"

    handler = LegacyWrapper()
    result = asyncio.run(_service(handler).generate_completion(
        messages=[{"role": "user", "content": "hi"}]))

    assert result["success"] is True
    assert result["content"] == "legacy answer"
    assert result["model"] == "legacy-model"
    assert result["provider"] == "legacy-provider"
    # The sink really was dispatched and simply stayed unwritten.
    assert handler.seen["outcome_sink"] == {}


def test_autodev_code_proposers_do_not_return_empty_on_structured_failure():
    """Direct-persist consumers must not store "" as generated code.

    Auto-Dev's Memento/AlphaEvolve proposers persist what they return. With
    the new empty-content failure contract an unguarded ``content`` read would
    create an empty skill/mutation; both use their existing failure fallback
    instead.
    """
    from core.auto_dev.alpha_evolver_engine import AlphaEvolverEngine
    from core.auto_dev.memento_engine import MementoEngine

    class FailingLLM:
        async def generate_completion(self, **kwargs):
            return {
                "success": False,
                "content": "",
                "text": "",
                "error": "provider/policy failure",
                "failure": {"reason": "all_providers_failed"},
            }

    memento = object.__new__(MementoEngine)
    memento.llm = FailingLLM()
    memento.db = None
    skill_code = asyncio.run(memento.propose_code_change(
        {"task_description": "parse the invoice"}))
    assert skill_code.startswith("# Skill generation failed")
    assert "provider/policy failure" in skill_code

    alpha = object.__new__(AlphaEvolverEngine)
    alpha.llm = FailingLLM()
    alpha.db = None
    mutation = asyncio.run(alpha.propose_code_change(
        {"base_code": "def run(): return 1", "mutation_prompt": "improve"}))
    assert mutation.startswith("def run(): return 1")
    assert "# Mutation failed" in mutation


def test_narrow_legacy_handler_without_sink_is_unchanged():
    class NarrowLegacy:
        workspace_id = WORKSPACE
        _last_used_model = "narrow-model"
        _last_used_provider = "narrow-provider"
        _last_feedback_decision_id = None
        _last_reasoning = None

        async def generate_response(
                self, prompt, system_instruction, model_type, temperature,
                turn_index, estimated_tokens, messages):
            return "narrow answer"

    result = asyncio.run(_service(NarrowLegacy()).generate_completion(
        messages=[{"role": "user", "content": "hi"}]))

    assert result["success"] is True
    assert result["content"] == "narrow answer"
    assert result["model"] == "narrow-model"
    assert result["provider"] == "narrow-provider"


def test_concurrent_calls_preserve_call_owned_status_identity_and_stop():
    """One shared handler, three simultaneous different outcomes.

    The producer writes each call's outcome/stop reason into the caller-owned
    sinks, then parks until all calls arrive. A consumer that borrowed shared
    handler state would mislabel at least one call.
    """
    expected = {
        "accepted": {"success": True, "content": "answer:accepted",
                     "provider": "p-a", "model": "m-a",
                     "finish_reason": "stop"},
        "failed": {"success": False, "reason": "all_providers_failed",
                   "error": "provider exploded", "finish_reason": None},
        "empty": {"success": False, "reason": "empty_generation",
                  "error": "no visible content", "finish_reason": None},
    }

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
            self.outcome_sinks = []

        async def generate_response(self, *, prompt, outcome_sink,
                                    finish_reason_sink, **kwargs):
            spec = expected[prompt]
            self.outcome_sinks.append(outcome_sink)
            if spec["success"]:
                outcome_sink.update({
                    "success": True,
                    "reason": None,
                    "message": None,
                    "provider": spec["provider"],
                    "model": spec["model"],
                    "diagnostics": {},
                })
                finish_reason_sink["finish_reason"] = spec["finish_reason"]
                text = spec["content"]
                # A concurrent call overwrites the shared attributes.
                self._last_used_model = "neighbour-model"
                self._last_used_provider = "neighbour-provider"
                self._last_finish_reason = "length"
            else:
                outcome_sink.update({
                    "success": False,
                    "reason": spec["reason"],
                    "message": spec["error"],
                    "provider": None,
                    "model": None,
                    "diagnostics": {
                        "last_error": spec["error"],
                        "last_finish_reason": (
                            "length" if prompt == "empty" else None),
                    },
                })
                finish_reason_sink["finish_reason"] = (
                    "length" if prompt == "empty" else None)
                text = "I couldn't generate a response — every configured provider failed."
            self.arrived += 1
            if self.arrived == len(expected):
                self.all_arrived.set()
            await self.all_arrived.wait()
            return text

    producer = SharedProducer()
    service = _service(producer)

    async def joined():
        return await asyncio.gather(*(
            service.generate_completion(
                messages=[{"role": "user", "content": key}],
                workspace_id=WORKSPACE, tenant_id=TENANT)
            for key in expected
        ))

    results = asyncio.run(joined())
    by_key = dict(zip(expected, results))

    accepted = by_key["accepted"]
    assert accepted["success"] is True
    assert accepted["content"] == "answer:accepted"
    assert accepted["provider"] == "p-a"
    assert accepted["model"] == "m-a"
    assert accepted["finish_reason"] == "stop"

    for key in ("failed", "empty"):
        result = by_key[key]
        assert result["success"] is False
        assert result["content"] == ""
        assert result["text"] == ""
        assert result["provider"] is None
        assert result["model"] is None
        assert result["finish_reason"] is None
        assert result["failure"]["reason"] == expected[key]["reason"]
    assert by_key["empty"]["failure"]["last_finish_reason"] == "length"

    # Three distinct caller-owned sinks; the shared attribute can match at
    # most one accepted call and is never used for a structured outcome.
    assert len({id(s) for s in producer.outcome_sinks}) == 3
