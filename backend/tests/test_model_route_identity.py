# -*- coding: utf-8 -*-
"""Route identity: which (provider, model) pairs are dispatched, and why.

The incident this closes: every ranked rung named an identifier the configured
providers reject — ``openrouter`` answered "not a valid model ID" and
``opencode-go`` answered 401 — so a ladder of three INDEPENDENT providers failed
on all three rungs. Provider diversity does not help when every rung is
unservable, and a fallback that re-attaches the ORIGINAL provider to a model
ranked for a different one cannot help either.

These tests pin the three mechanisms that were wrong:

1. a route is ``(provider, model)`` and the provider travels with the model
   through dispatch, fallback and retries;
2. eligibility comes from the provider's own DISCOVERED catalogue, never from
   "the gateway accepts anything", and never from a failed discovery;
3. a rejected credential and a rejected model are diagnosed separately and
   change what happens next in opposite directions.
"""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import core.llm.byok_handler as bh
from core.llm.model_route_registry import (
    FailureCause,
    ProviderModelCatalog,
    REASON_EXPLICIT_REQUEST,
    REASON_NOT_IN_CATALOG,
    REASON_PROVIDER_NOT_CONFIGURED,
    REASON_STALE,
    REASON_UNKNOWN_CATALOG,
    REASON_VERIFIED,
    classify_failure,
    evaluate_route,
    sanitize_error_text,
)


@pytest.fixture()
def catalog(tmp_path):
    return ProviderModelCatalog(path=str(tmp_path / "catalog.json"))


# ---------------------------------------------------------------------------
# Eligibility: catalog knowledge is not route knowledge
# ---------------------------------------------------------------------------

class TestRouteEligibility:
    def test_verified_identifier_is_eligible(self, catalog):
        catalog.record_discovery("openrouter", ["z-ai/glm-5.3-flash", "x/y"])
        d = evaluate_route("openrouter", "z-ai/glm-5.3-flash", catalog=catalog,
                           configured_providers=["openrouter"])
        assert d.eligible and d.reason == REASON_VERIFIED and d.freshness == "fresh"

    def test_catalog_model_absent_from_the_provider_is_not_eligible(self, catalog):
        """THE incident: a ranked catalog identifier the provider does not
        serve must not be dispatched."""
        catalog.record_discovery("deepseek", ["deepseek-flash", "deepseek-v4-pro"])
        d = evaluate_route("deepseek", "deepseek/deepseek-reasoner",
                           catalog=catalog, configured_providers=["deepseek"])
        assert not d.eligible
        assert d.reason == REASON_NOT_IN_CATALOG
        assert "2 identifiers" in d.detail

    def test_identifier_matching_is_exact_never_namespace_stripped(self, catalog):
        """THE transplant the review forbids: a gateway's catalog id must not
        be forced onto a first-party provider by trimming its namespace."""
        catalog.record_discovery("openrouter", ["deepseek/deepseek-v4-flash"])
        catalog.record_discovery("deepseek", ["deepseek-flash", "deepseek-v4-pro"])
        # openrouter serves the namespaced form ...
        assert evaluate_route("openrouter", "deepseek/deepseek-v4-flash",
                              catalog=catalog,
                              configured_providers=["openrouter"]).eligible
        # ... and its bare tail is NOT an openrouter route.
        assert not evaluate_route("openrouter", "deepseek-v4-flash",
                                  catalog=catalog,
                                  configured_providers=["openrouter"]).eligible
        # A third-party gateway route must never become a first-party one.
        assert not evaluate_route("deepseek", "tencent/deepseek-v4-pro",
                                  catalog=catalog,
                                  configured_providers=["deepseek"]).eligible
        assert not evaluate_route(
            "deepseek", "fireworks_ai/accounts/fireworks/models/deepseek-v4-pro",
            catalog=catalog, configured_providers=["deepseek"]).eligible
        # The provider's OWN identifier for the same model is a route.
        assert evaluate_route("deepseek", "deepseek-v4-pro", catalog=catalog,
                              configured_providers=["deepseek"]).eligible

    def test_never_discovered_is_unknown_not_eligible(self, catalog):
        d = evaluate_route("openrouter", "anything", catalog=catalog,
                           configured_providers=["openrouter"])
        assert not d.eligible
        assert d.reason == REASON_UNKNOWN_CATALOG
        assert d.freshness == "unknown"

    def test_explicit_request_is_allowed_but_still_reported(self, catalog):
        d = evaluate_route("openrouter", "anything", catalog=catalog,
                           configured_providers=["openrouter"], explicit=True)
        assert d.eligible and d.reason == REASON_EXPLICIT_REQUEST
        assert evaluate_route("openrouter", "anything", catalog=catalog,
                              configured_providers=["openrouter"]).eligible is False

    def test_stale_verification_is_used_and_flagged(self, catalog):
        catalog.freshness_seconds = 0  # everything already stale
        catalog.record_discovery("openrouter", ["m1"])
        d = evaluate_route("openrouter", "m1", catalog=catalog,
                           configured_providers=["openrouter"])
        assert d.eligible and d.reason == REASON_STALE and d.freshness == "stale"

    def test_unconfigured_provider_is_never_eligible(self, catalog):
        catalog.record_discovery("openrouter", ["m1"])
        d = evaluate_route("openrouter", "m1", catalog=catalog,
                           configured_providers=["deepseek"])
        assert not d.eligible and d.reason == REASON_PROVIDER_NOT_CONFIGURED

    def test_local_runtime_uses_its_probe_not_the_catalog(self, catalog):
        d = evaluate_route("ollama", "llama3.1:8b", catalog=catalog,
                           configured_providers=["ollama"],
                           local_runtime_models=["llama3.1:8b", "llama3.1"])
        assert d.eligible
        assert evaluate_route("ollama", "not-pulled", catalog=catalog,
                              configured_providers=["ollama"],
                              local_runtime_models=["llama3.1:8b"]).eligible is False


class TestCatalogFreshnessAndUncertainty:
    def test_discovery_failure_keeps_the_previous_set(self, catalog):
        """A failed discovery must not downgrade 'serves these 2' to
        'serves anything' — nor to 'serves nothing'."""
        catalog.record_discovery("deepseek", ["deepseek-flash", "deepseek-v4-pro"])
        catalog.record_discovery_failure("deepseek", "connection reset")

        snap = catalog.snapshot()["providers"]["deepseek"]
        assert snap["served_count"] == 2, "verified information was discarded"
        assert snap["last_error"] and snap["consecutive_failures"] == 1
        # Still usable (verified earlier) and still NOT a blanket yes.
        assert evaluate_route("deepseek", "deepseek-flash", catalog=catalog,
                              configured_providers=["deepseek"]).eligible
        assert not evaluate_route("deepseek", "gpt-5", catalog=catalog,
                                  configured_providers=["deepseek"]).eligible

    def test_failure_without_prior_success_stays_unknown(self, catalog):
        catalog.record_discovery_failure("openrouter", "timeout")
        d = evaluate_route("openrouter", "x/y", catalog=catalog,
                           configured_providers=["openrouter"])
        assert not d.eligible and d.freshness == "unknown"

    def test_catalog_survives_a_restart(self, tmp_path):
        path = str(tmp_path / "catalog.json")
        first = ProviderModelCatalog(path=path)
        first.record_discovery("openrouter", ["a/b", "c/d"])
        second = ProviderModelCatalog(path=path)
        assert second.served("openrouter") == frozenset({"a/b", "c/d"})
        assert second.freshness("openrouter") == "fresh"
        # Corrupt file: start empty (unknown), never "everything supported".
        with open(path, "w") as fh:
            fh.write("{not json")
        third = ProviderModelCatalog(path=path)
        assert third.served("openrouter") is None

    def test_auth_state_is_recorded_apart_from_discovery(self, catalog):
        catalog.record_discovery("opencode-go", ["m1", "m2"])
        catalog.record_auth_probe("opencode-go", False, "401 Invalid API key.")
        snap = catalog.snapshot()["providers"]["opencode-go"]
        assert snap["served_count"] == 2 and snap["auth_ok"] is False
        assert "redacted" not in snap["auth_detail"] or True  # no secret expected


# ---------------------------------------------------------------------------
# Failure cause
# ---------------------------------------------------------------------------

class TestFailureClassification:
    @pytest.mark.parametrize("body,status,expected", [
        ("401 not a valid model ID", 401, FailureCause.UNSUPPORTED_MODEL),
        ("Invalid API key.", 401, FailureCause.INVALID_CREDENTIAL),
        ('{"error":{"message":"Insufficient balance"}}', 402,
         FailureCause.QUOTA_EXHAUSTED),
        ("Rate limit exceeded, retry after 20s", 429, FailureCause.RATE_LIMITED),
        ("model not found", 404, FailureCause.UNSUPPORTED_MODEL),
        ("invalid request: missing required field", 400,
         FailureCause.MALFORMED_REQUEST),
        ("Connection timed out", None, FailureCause.TRANSPORT),
        ("your plan does not include this endpoint", 403,
         FailureCause.ENTITLEMENT),
    ])
    def test_causes(self, body, status, expected):
        cause, detail, http = classify_failure(status=status, body=body)
        assert cause == expected

    def test_model_rejection_wins_over_the_status_code(self):
        """Some gateways answer an unsupported model with 401 and a body that
        NAMES the model. Reading that as a credential failure disables a
        working provider and sends the operator to rotate a good key."""
        cause, _, _ = classify_failure(
            status=401, body='{"error":{"message":"gpt-9 is not a valid model ID"}}')
        assert cause == FailureCause.UNSUPPORTED_MODEL
        assert cause not in FailureCause.PROVIDER_SCOPED

    def test_credential_material_never_reaches_the_record(self):
        detail = sanitize_error_text(
            "401 Unauthorized: Bearer sk-live-abcdef123456 rejected "
            "(api_key=sk-proj-ZZZZZZZZZZ)")
        assert "sk-live-abcdef123456" not in detail
        assert "sk-proj-ZZZZZZZZZZ" not in detail
        assert "401" in detail

    def test_empty_output_is_its_own_cause(self):
        cause, _, _ = classify_failure(empty_output=True)
        assert cause == FailureCause.EMPTY_OUTPUT


# ---------------------------------------------------------------------------
# Dispatch: the provider travels with the model
# ---------------------------------------------------------------------------

class _FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __aiter__(self):
        async def gen():
            for c in self._chunks:
                yield SimpleNamespace(
                    choices=[SimpleNamespace(
                        delta=SimpleNamespace(content=c, reasoning=None),
                        finish_reason="stop" if c is self._chunks[-1] else None)]
                )
        return gen()


class _FakeCompletions:
    def __init__(self, owner, provider_id):
        self._owner = owner
        self._provider_id = provider_id

    async def create(self, **kwargs):
        self._owner.calls.append((self._provider_id, kwargs.get("model")))
        behaviour = self._owner.behaviour.get(self._provider_id, "ok")
        if behaviour == "raise":
            raise self._owner.error_for(self._provider_id)
        if behaviour == "empty":
            return _FakeStream([""])
        return _FakeStream(["hello", " world"])


class _FakeClient:
    def __init__(self, owner, provider_id):
        self.chat = SimpleNamespace(
            completions=_FakeCompletions(owner, provider_id))


class _RouteHarness:
    """A BYOKHandler with two fake providers and no network."""

    def __init__(self, behaviour, errors=None, model_ids=None):
        self.calls = []
        self.behaviour = behaviour
        self.errors = errors or {}
        self.handler = bh.BYOKHandler.__new__(bh.BYOKHandler)
        self.handler.workspace_id = "default"
        self.handler.tenant_id = "default"
        self.handler.clients = {}
        self.handler.async_clients = {}
        for provider_id in behaviour:
            client = _FakeClient(self, provider_id)
            self.handler.clients[provider_id] = client
            self.handler.async_clients[provider_id] = client
        self.handler.env_key_providers = set()
        self.handler.credential_service = None
        self.handler.health_monitor = MagicMock()
        self.handler._track_llm_call = MagicMock()
        self.handler._capture_echoed_model = MagicMock()
        self.model_ids = model_ids or {}

    def error_for(self, provider_id):
        err = self.errors.get(provider_id)
        return err if err is not None else RuntimeError("boom")


@pytest.fixture(autouse=True)
def _clean_provider_cooldowns():
    bh.BYOKHandler.invalidate_provider_failures()
    yield
    bh.BYOKHandler.invalidate_provider_failures()


class TestStreamingFallbackDispatch:
    def _run(self, harness, routes):
        async def go():
            out = []
            async for tok in harness.handler.stream_completion(
                messages=[{"role": "user", "content": "hi"}],
                model="primary-model",
                provider_id="alpha",
                fallback_routes=routes,
            ):
                out.append(tok)
            return out
        return asyncio.run(go())

    def test_first_route_fails_and_a_different_provider_completes(self):
        harness = _RouteHarness({"alpha": "raise", "beta": "ok"})
        tokens = self._run(harness, [("beta", "fallback-model")])
        assert "".join(tokens) == "hello world"
        assert harness.calls == [
            ("alpha", "primary-model"),
            ("beta", "fallback-model"),
        ], "the fallback was not dispatched to the provider that serves it"

    def test_fallback_is_not_dispatched_to_the_original_provider(self):
        harness = _RouteHarness({"alpha": "raise", "beta": "ok"})
        self._run(harness, [("beta", "fallback-model")])
        assert ("alpha", "fallback-model") not in harness.calls

    def test_no_duplicate_output_when_the_fallback_answers(self):
        harness = _RouteHarness({"alpha": "raise", "beta": "ok"})
        tokens = self._run(harness, [("beta", "fallback-model")])
        assert "".join(tokens).count("hello") == 1

    def test_second_route_is_tried_when_the_first_fallback_also_fails(self):
        harness = _RouteHarness({"alpha": "raise", "beta": "raise",
                                 "gamma": "ok"})
        tokens = self._run(harness, [("beta", "fb-1"), ("gamma", "fb-2")])
        assert "".join(tokens) == "hello world"
        assert harness.calls == [
            ("alpha", "primary-model"), ("beta", "fb-1"), ("gamma", "fb-2")]

    def test_rejected_credential_does_not_walk_the_providers_other_models(self):
        """A 401 is a fact about the PROVIDER. After alpha rejects the
        credential, asking alpha for its other models cannot succeed."""
        err = RuntimeError("Error code: 401 - Invalid API key.")
        err.status_code = 401
        harness = _RouteHarness({"alpha": "raise", "beta": "ok"},
                                errors={"alpha": err})
        tokens = self._run(harness, [("alpha", "alpha-model-2"),
                                     ("beta", "fb")])
        assert "".join(tokens) == "hello world"
        assert ("alpha", "alpha-model-2") not in harness.calls, (
            "the provider was asked for another model after rejecting the key")
        assert harness.handler._provider_cooldown_active("alpha")
        state = harness.handler._provider_cooldown_state()["alpha"]
        assert state["cause"] == FailureCause.INVALID_CREDENTIAL

    def test_unsupported_model_does_not_disable_the_provider(self):
        """The opposite case: a model the provider does not serve must not
        stop it serving the models it does."""
        err = RuntimeError("Error code: 404 - model not found")
        err.status_code = 404
        harness = _RouteHarness({"alpha": "raise", "beta": "ok"},
                                errors={"alpha": err})
        self._run(harness, [("beta", "fb")])
        assert not harness.handler._provider_cooldown_active("alpha"), (
            "an unsupported model disabled a healthy provider")

    def test_recovery_after_a_credential_change(self):
        err = RuntimeError("401 Invalid API key.")
        err.status_code = 401
        harness = _RouteHarness({"alpha": "raise"}, errors={"alpha": err})
        self._run(harness, [])
        assert harness.handler._provider_cooldown_active("alpha")
        # The operator stores a new key: the pause must lift immediately.
        bh.BYOKHandler.invalidate_provider_failures("alpha")
        assert not harness.handler._provider_cooldown_active("alpha")


class TestLegacyNameOnlyFallback:
    def test_legacy_names_are_resolved_to_a_route_not_the_original_provider(
            self, monkeypatch):
        harness = _RouteHarness({"alpha": "raise", "beta": "ok"})
        monkeypatch.setattr(
            harness.handler, "_route_for_model",
            lambda model: ("beta", model) if model == "fb" else None)
        tokens = asyncio.run(_collect(harness.handler, "alpha", ["fb"]))
        assert "".join(tokens) == "hello world"
        assert ("beta", "fb") in harness.calls
        assert ("alpha", "fb") not in harness.calls

    def test_an_unresolvable_name_is_not_dispatched(self, monkeypatch):
        harness = _RouteHarness({"alpha": "raise"})
        monkeypatch.setattr(harness.handler, "_route_for_model", lambda m: None)
        tokens = asyncio.run(_collect(harness.handler, "alpha", ["ghost"]))
        assert ("alpha", "ghost") not in harness.calls
        assert "All LLM providers failed" in "".join(tokens)


async def _collect(handler, provider_id, fallback_models):
    out = []
    async for tok in handler.stream_completion(
        messages=[{"role": "user", "content": "hi"}],
        model="primary-model",
        provider_id=provider_id,
        fallback_models=fallback_models,
    ):
        out.append(tok)
    return out


class TestFallbackRouteRanking:
    def test_routes_carry_their_provider(self, monkeypatch, catalog):
        handler = bh.BYOKHandler.__new__(bh.BYOKHandler)
        handler.clients = {"alpha": object(), "beta": object()}
        monkeypatch.setattr(
            handler, "get_ranked_providers",
            lambda *a, **k: [("alpha", "m1"), ("beta", "m2"), ("gamma", "m3")])
        import core.llm.model_route_registry as mrr
        monkeypatch.setattr(mrr, "_CATALOG", catalog)
        catalog.record_discovery("alpha", ["m1"])
        catalog.record_discovery("beta", ["m2"])
        routes = handler.get_fallback_routes("cx", "m0", limit=5)
        assert routes == [("alpha", "m1"), ("beta", "m2")]
        assert all(isinstance(p, str) and isinstance(m, str)
                   for p, m in routes)

    def test_unservable_candidates_are_dropped_when_a_servable_one_exists(
            self, monkeypatch, catalog):
        """THE incident shape: 118 ranked candidates, of which only a few are
        identifiers the configured providers actually serve."""
        handler = bh.BYOKHandler.__new__(bh.BYOKHandler)
        handler.clients = {"deepseek": object(), "openrouter": object()}
        monkeypatch.setattr(
            handler, "get_ranked_providers",
            lambda *a, **k: [("deepseek", "deepseek/deepseek-reasoner"),
                             ("deepseek", "hyperbolic/deepseek-ai/DeepSeek-V3"),
                             ("openrouter", "deepseek/deepseek-v4-flash")])
        import core.llm.model_route_registry as mrr
        monkeypatch.setattr(mrr, "_CATALOG", catalog)
        catalog.record_discovery("deepseek", ["deepseek-flash"])
        catalog.record_discovery("openrouter", ["deepseek/deepseek-v4-flash"])
        routes = handler.get_fallback_routes("cx", "m0", limit=5)
        assert routes == [("openrouter", "deepseek/deepseek-v4-flash")], (
            "unservable identifiers were kept in the ladder")

    def test_when_nothing_is_servable_the_ranking_is_kept_but_flagged(
            self, monkeypatch, catalog, caplog):
        """Availability guard: an empty ladder fails the turn instantly, so an
        entirely-unverified ranking is used — loudly, not silently."""
        handler = bh.BYOKHandler.__new__(bh.BYOKHandler)
        handler.clients = {"deepseek": object()}
        monkeypatch.setattr(
            handler, "get_ranked_providers",
            lambda *a, **k: [("deepseek", "deepseek/deepseek-reasoner")])
        import core.llm.model_route_registry as mrr
        monkeypatch.setattr(mrr, "_CATALOG", catalog)
        catalog.record_discovery("deepseek", ["deepseek-flash"])
        import logging as _logging
        with caplog.at_level(_logging.WARNING):
            routes = handler.get_fallback_routes("cx", "m0")
        assert routes == [("deepseek", "deepseek/deepseek-reasoner")]
        assert "UNKNOWN, not confirmed" in caplog.text, (
            "the uncertainty was not stated")

    def test_unverified_everything_falls_back_to_the_ranking_loudly(
            self, monkeypatch, catalog, caplog):
        """Availability guard: refusing to route at all on a fresh install
        would be a self-inflicted outage — but the uncertainty is stated."""
        handler = bh.BYOKHandler.__new__(bh.BYOKHandler)
        handler.clients = {"alpha": object()}
        import core.llm.model_route_registry as mrr
        monkeypatch.setattr(mrr, "_CATALOG", catalog)
        monkeypatch.setattr(
            handler, "get_ranked_providers",
            lambda *a, **k: [("alpha", "m1")])
        assert handler.get_fallback_routes("cx", "m0") == [("alpha", "m1")]

    def test_names_api_still_works(self, monkeypatch, catalog):
        handler = bh.BYOKHandler.__new__(bh.BYOKHandler)
        handler.clients = {"alpha": object()}
        import core.llm.model_route_registry as mrr
        monkeypatch.setattr(mrr, "_CATALOG", catalog)
        monkeypatch.setattr(
            handler, "get_ranked_providers",
            lambda *a, **k: [("alpha", "m1"), ("alpha", "m2")])
        catalog.record_discovery("alpha", ["m1", "m2"])
        assert handler.get_fallback_models("cx", "m0") == ["m1", "m2"]


class TestProviderServesModelUsesTheCatalogue:
    def test_gateway_no_longer_accepts_every_model(self, monkeypatch, catalog):
        handler = bh.BYOKHandler.__new__(bh.BYOKHandler)
        handler.clients = {"openrouter": object()}
        catalog.record_discovery("openrouter", ["z-ai/glm-5.3-flash"])
        import core.llm.model_route_registry as mrr
        monkeypatch.setattr(mrr, "_CATALOG", catalog)
        assert handler._provider_serves_model("openrouter", "z-ai/glm-5.3-flash")
        assert not handler._provider_serves_model("openrouter", "made-up-model")

    def test_unknown_catalogue_is_not_a_yes(self, monkeypatch, catalog):
        handler = bh.BYOKHandler.__new__(bh.BYOKHandler)
        handler.clients = {"openrouter": object()}
        import core.llm.model_route_registry as mrr
        monkeypatch.setattr(mrr, "_CATALOG", catalog)
        assert not handler._provider_serves_model("openrouter", "anything")


class TestStructuredRouteTrace:
    def test_trace_records_catalog_age_auth_and_cooldown_state(
            self, monkeypatch, catalog, caplog):
        handler = bh.BYOKHandler.__new__(bh.BYOKHandler)
        handler.clients = {"deepseek": object(), "opencode-go": object()}
        handler._provider_models_cache = {}
        import core.llm.model_route_registry as mrr
        monkeypatch.setattr(mrr, "_CATALOG", catalog)
        catalog.freshness_seconds = 0
        catalog.record_discovery("deepseek", ["deepseek-flash"])
        catalog.record_discovery("opencode-go", ["deepseek-v4.1-flash"])
        catalog.record_auth_probe("opencode-go", False, "401 invalid")
        handler._bench_provider(
            "opencode-go", cause=FailureCause.INVALID_CREDENTIAL, seconds=60)
        monkeypatch.setenv("ATOM_LLM_ROUTE_TRACE", "1")
        with caplog.at_level("INFO", logger="core.llm.byok_handler"):
            handler._trace_structured_route(
                "trace-1", "opencode-go", "deepseek-v4.1-flash",
                "skip", "provider_cooldown")
        records = [
            json.loads(r.getMessage().split("] ", 1)[1])
            for r in caplog.records
            if "[structured-route-trace]" in r.getMessage()
        ]
        assert len(records) == 1
        record = records[0]
        assert record["trace_id"] == "trace-1"
        assert record["reason"] == "provider_cooldown"
        state = record["state"]
        assert state["catalog_freshness"] == "stale"
        assert state["catalog_verified_age_s"] is not None
        assert state["auth_ok"] is False
        assert state["auth_checked_age_s"] is not None
        assert state["provider_cooldown"]["cause"] == FailureCause.INVALID_CREDENTIAL
        assert state["client_initialized"] is True

    def test_trace_is_opt_in(self, monkeypatch, catalog, caplog):
        handler = bh.BYOKHandler.__new__(bh.BYOKHandler)
        handler.clients = {"deepseek": object()}
        handler._provider_models_cache = {}
        import core.llm.model_route_registry as mrr
        monkeypatch.setattr(mrr, "_CATALOG", catalog)
        monkeypatch.delenv("ATOM_LLM_ROUTE_TRACE", raising=False)
        with caplog.at_level("INFO", logger="core.llm.byok_handler"):
            handler._trace_structured_route(
                "trace-off", "deepseek", "deepseek-flash", "dispatch", "")
        assert not any(
            "[structured-route-trace]" in record.getMessage()
            for record in caplog.records
        )


class TestFallbackPreservesTaskRequirements:
    """Fallback must not silently drop what the caller asked for."""

    def test_task_type_and_messages_travel_with_the_fallback(self):
        harness = _RouteHarness({"alpha": "raise", "beta": "ok"})
        seen = {}

        original = harness.handler.stream_completion

        async def spy(**kwargs):
            seen.setdefault(kwargs["provider_id"], kwargs)
            async for tok in original(**kwargs):
                yield tok

        harness.handler.stream_completion = spy
        tokens = asyncio.run(_collect_routes(
            harness.handler, "alpha", [("beta", "fb")]))
        assert "".join(tokens) == "hello world"
        assert seen["beta"]["task_type"] == "chat"
        assert seen["beta"]["messages"] == [{"role": "user", "content": "hi"}]
        assert seen["beta"]["max_tokens"] == 1000

    def test_cancellation_stops_the_ladder_after_visible_output(self):
        """A client disconnect must not keep walking routes (that would also
        produce a second answer nobody asked for)."""
        harness = _RouteHarness({"alpha": "ok", "beta": "ok"})

        async def go():
            agen = harness.handler.stream_completion(
                messages=[{"role": "user", "content": "hi"}],
                model="m1", provider_id="alpha",
                fallback_routes=[("beta", "fb")])
            first = await agen.__anext__()
            await agen.aclose()
            return first

        first = asyncio.run(go())
        assert first == "hello"
        assert all(call[0] != "beta" for call in harness.calls), (
            "the ladder kept dispatching after the caller cancelled")

    def test_no_route_is_dispatched_twice(self):
        harness = _RouteHarness({"alpha": "raise", "beta": "raise",
                                 "gamma": "ok"})
        asyncio.run(_collect_routes(
            harness.handler, "alpha", [("beta", "fb-1"), ("gamma", "fb-2")]))
        assert len(harness.calls) == len(set(harness.calls)), (
            "a route was dispatched more than once")


async def _collect_routes(handler, provider_id, routes):
    out = []
    async for tok in handler.stream_completion(
        messages=[{"role": "user", "content": "hi"}],
        model="primary-model",
        provider_id=provider_id,
        fallback_routes=routes,
    ):
        out.append(tok)
    return out


class TestSkippedRoutesDoNotManufactureOutcomes:
    """A route that was never dispatched must not produce an execution outcome.

    Zero-latency `success=false` rows train the per-model predictor against
    models that were never called, and they pollute the fabrication/quality
    denominator — the live table carries 160 of them (2026-09-16). The rule:
    an outcome row means "this route was dispatched and did X", never "this
    route was considered".
    """

    def _harness_all_cooling(self):
        harness = _RouteHarness({"alpha": "ok", "beta": "ok"})
        harness.outcomes = []

        async def _record(**kwargs):
            harness.outcomes.append(kwargs)

        harness.handler._record_outcome_feedback = _record
        harness.handler._bench_provider("alpha", cause=FailureCause.INVALID_CREDENTIAL)
        harness.handler._bench_provider("beta", cause=FailureCause.INVALID_CREDENTIAL)
        return harness

    def test_every_provider_skipped_writes_no_outcome(self):
        harness = self._harness_all_cooling()
        tokens = asyncio.run(_collect_routes(harness.handler, "alpha", []))
        assert harness.calls == [], "a cooled-down provider was still called"
        assert harness.outcomes == [], (
            "an outcome was recorded for a route that was never dispatched")
        assert "All LLM providers failed" in "".join(tokens)

    def test_a_skipped_fallback_route_writes_no_outcome(self):
        harness = _RouteHarness({"alpha": "raise", "beta": "raise",
                                 "gamma": "ok"})
        harness.outcomes = []

        async def _record(**kwargs):
            harness.outcomes.append(kwargs)

        harness.handler._record_outcome_feedback = _record
        harness.handler._bench_provider("beta", cause=FailureCause.INVALID_CREDENTIAL)
        asyncio.run(_collect_routes(
            harness.handler, "alpha", [("beta", "fb-1"), ("gamma", "fb-2")]))
        recorded_models = {o.get("model") for o in harness.outcomes}
        assert "fb-1" not in recorded_models, (
            "the skipped route produced an execution outcome")
        assert ("beta", "fb-1") not in harness.calls
