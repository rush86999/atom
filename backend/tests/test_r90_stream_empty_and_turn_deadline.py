"""
R90 regression: /api/chat/message hit the frontend's 120s axios timeout.

Root cause (live evidence, uvicorn_8001_restart.log line 1509653):
a provider STREAM completed with ZERO visible tokens. ``stream_completion``
counted that as a SUCCESS and returned, so the caller's only signal was the
orchestrator's "chat streaming produced no tokens — falling back" warning;
the turn then re-ran the SAME model through the non-streaming path, which
serialized with the block's grounded-regeneration second call and overshot
the client's 120s budget (observed reply-generation times: 128.7s, 196.5s,
245.5s, 392.4s).

The non-streaming path already treats an empty visible payload as a FAILED
attempt (``_EmptyCompletionError`` → next ranked provider). The streaming
path did not — this module pins that parity, plus the turn budget that keeps
a chat reply leg bounded below the client timeout.
"""
import asyncio
import sys
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.llm import byok_handler


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _Delta(SimpleNamespace):
    """A stream delta; only ``content`` is read by the token loop."""


def _chunk(content):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=_Delta(content=content), finish_reason=None)]
    )


class _AsyncStream:
    """Async-iterable chunk stream (mimics the OpenAI SDK's AsyncStream)."""

    def __init__(self, chunks):
        self._chunks = chunks

    def __aiter__(self):
        self._it = iter(self._chunks)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class _FakeClient:
    """Async OpenAI-shaped client whose stream is supplied per provider."""

    def __init__(self, chunks):
        self._chunks = chunks
        self.create_calls = 0
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    async def _create(self, **kwargs):
        self.create_calls += 1
        return _AsyncStream(list(self._chunks))


def _build_handler(providers):
    """BYOKHandler skeleton wired to fake async clients.

    ``providers`` maps provider_id -> chunk list, e.g. ``{"openai": []}`` for
    a provider that streams nothing at all.
    """
    handler = byok_handler.BYOKHandler.__new__(byok_handler.BYOKHandler)
    handler.workspace_id = "ws_test"
    handler.clients = {}
    handler.async_clients = {
        pid: _FakeClient(chunks) for pid, chunks in providers.items()
    }
    handler.env_key_providers = set(providers)
    handler.health_monitor = MagicMock()
    handler._last_reasoning = None
    return handler


async def _drain(agen):
    return [tok async for tok in agen]


# ---------------------------------------------------------------------------
# Red test: zero-token stream must NOT be reported as success
# ---------------------------------------------------------------------------

class TestEmptyStreamIsAFailedAttempt:
    """A stream that yields no visible content is a failed attempt."""

    async def test_empty_stream_falls_through_to_next_provider(self, monkeypatch):
        """Provider #1 streams no tokens -> provider #2 must be tried."""
        handler = _build_handler({
            "openai": [],                       # silent stream (the live bug)
            "anthropic": [_chunk("Hello"), _chunk(" world")],
        })

        monkeypatch.setattr(
            handler, "_get_provider_fallback_order",
            lambda requested: ["openai", "anthropic"],
        )
        monkeypatch.setattr(handler, "_provider_serves_model", lambda p, m: True)
        monkeypatch.setattr(handler, "_llm_taint_check", lambda *a, **k: None)
        monkeypatch.setattr(handler, "_stash_decision_features", lambda *a, **k: None)
        monkeypatch.setattr(
            handler, "_record_outcome_feedback", AsyncMock(return_value=None)
        )

        tokens = await _drain(handler.stream_completion(
            messages=[{"role": "user", "content": "hi"}],
            model="m",
            provider_id="openai",
        ))

        # Red today: the empty stream returns first, so nothing is yielded and
        # the healthy provider is never asked.
        assert "".join(tokens) == "Hello world"
        assert handler.async_clients["anthropic"].create_calls == 1

    async def test_empty_stream_records_provider_failure(self, monkeypatch):
        """The silent provider must not be recorded as a healthy call."""
        handler = _build_handler({
            "openai": [],
            "anthropic": [_chunk("ok")],
        })
        monkeypatch.setattr(
            handler, "_get_provider_fallback_order",
            lambda requested: ["openai", "anthropic"],
        )
        monkeypatch.setattr(handler, "_provider_serves_model", lambda p, m: True)
        monkeypatch.setattr(handler, "_llm_taint_check", lambda *a, **k: None)
        monkeypatch.setattr(handler, "_stash_decision_features", lambda *a, **k: None)
        monkeypatch.setattr(
            handler, "_record_outcome_feedback", AsyncMock(return_value=None)
        )

        await _drain(handler.stream_completion(
            messages=[{"role": "user", "content": "hi"}],
            model="m",
            provider_id="openai",
        ))

        failures = [
            c for c in handler.health_monitor.record_call.call_args_list
            if c.kwargs.get("success") is False
        ]
        assert failures, "silent stream was not recorded as a failed provider call"
        assert failures[0].args[0] == "openai"

    async def test_all_providers_silent_surfaces_error(self, monkeypatch):
        """If every provider streams nothing the caller must not be left with a
        silent success — either an exception or the service's existing error
        envelope (``stream_completion`` yields one when every provider fails).
        What must NOT happen is an empty-token "success" that the caller then
        re-runs on the non-streaming path."""
        handler = _build_handler({"openai": [], "anthropic": []})
        monkeypatch.setattr(
            handler, "_get_provider_fallback_order",
            lambda requested: ["openai", "anthropic"],
        )
        monkeypatch.setattr(handler, "_provider_serves_model", lambda p, m: True)
        monkeypatch.setattr(handler, "_llm_taint_check", lambda *a, **k: None)
        monkeypatch.setattr(handler, "_stash_decision_features", lambda *a, **k: None)
        monkeypatch.setattr(
            handler, "_record_outcome_feedback", AsyncMock(return_value=None)
        )

        try:
            tokens = await _drain(handler.stream_completion(
                messages=[{"role": "user", "content": "hi"}],
                model="m",
                provider_id="openai",
            ))
        except Exception:
            return  # raising is the stricter, acceptable outcome

        assert tokens, (
            "all-providers-silent stream produced no tokens and no error "
            "envelope — the caller cannot distinguish this from success"
        )
        assert any("[Error:" in t for t in tokens), (
            f"expected the all-providers-failed error envelope, got {tokens!r}"
        )


# ---------------------------------------------------------------------------
# The turn budget helper the orchestrator uses to stay under the client
# timeout.
# ---------------------------------------------------------------------------

class TestChatTurnBudget:
    def test_budget_resolves_from_env(self, monkeypatch):
        monkeypatch.setenv("ATOM_CHAT_TURN_BUDGET_SECONDS", "90")
        from integrations.chat_orchestrator import _chat_turn_budget_seconds

        assert _chat_turn_budget_seconds() == 90.0

    def test_budget_defaults_below_client_timeout(self, monkeypatch):
        """Default must leave headroom under the frontend's 120s axios limit."""
        monkeypatch.delenv("ATOM_CHAT_TURN_BUDGET_SECONDS", raising=False)
        from integrations.chat_orchestrator import _chat_turn_budget_seconds

        budget = _chat_turn_budget_seconds()
        assert 0 < budget < 120

    def test_remaining_never_negative(self):
        import time as _time

        from integrations.chat_orchestrator import _remaining_budget

        # Anchor a turn that has already burned its whole budget.
        assert _remaining_budget(_time.monotonic() - 100.0, 10.0) == 0.0
        # A fresh turn still has most of its budget.
        assert _remaining_budget(_time.monotonic(), 10.0) > 0
        # A disabled budget is unbounded, not zero.
        assert _remaining_budget(_time.monotonic(), 0) == float("inf")

    def test_invalid_env_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("ATOM_CHAT_TURN_BUDGET_SECONDS", "not-a-number")
        from integrations.chat_orchestrator import _chat_turn_budget_seconds

        assert _chat_turn_budget_seconds() > 0


# ---------------------------------------------------------------------------
# R90b: anonymous integration storm from the intelligence background worker.
#
# ``IntelligenceBackgroundWorker._perform_scan`` runs every 300s and refreshes
# salesforce/jira/asana. When no active IntegrationToken exists it passed an
# empty context, so UniversalIntegrationService raised
# "user_id required for non-system agents" -> 3 ERROR logs + a traceback every
# 5 minutes, ~6,400 failures over 8 days of the live log, plus circuit-breaker
# churn for integrations that were never configured.
# ---------------------------------------------------------------------------

class TestIntelligenceWorkerSkipsUnconfiguredPlatforms:
    async def test_no_configured_user_skips_the_fetch(self, monkeypatch):
        from ai.intelligence_background_worker import IntelligenceBackgroundWorker

        worker = IntelligenceBackgroundWorker()
        monkeypatch.setattr(worker, "_get_configured_user_id", lambda platform: None)
        calls = []

        async def _record(platform, context):
            calls.append((platform, context))
            return []

        monkeypatch.setattr(worker.engine, "_get_platform_data", _record)
        monkeypatch.setattr(
            worker.engine, "detect_anomalies", AsyncMock(return_value=[])
        )
        monkeypatch.setattr(
            worker.engine, "ingest_platform_data", AsyncMock(return_value=None)
        )

        await worker._perform_scan()

        assert calls == [], (
            "worker fetched platform data with no user identity — this is the "
            f"anonymous-integration storm (calls={calls})"
        )

    async def test_configured_user_still_fetches(self, monkeypatch):
        """A configured token owner must still be refreshed (BUG-051)."""
        from ai.intelligence_background_worker import IntelligenceBackgroundWorker

        worker = IntelligenceBackgroundWorker()
        monkeypatch.setattr(
            worker, "_get_configured_user_id", lambda platform: "user-1"
        )
        calls = []

        async def _record(platform, context):
            calls.append((platform.value, context))
            return [{"id": "x"}]

        monkeypatch.setattr(worker.engine, "_get_platform_data", _record)
        monkeypatch.setattr(
            worker.engine, "detect_anomalies", AsyncMock(return_value=[])
        )
        monkeypatch.setattr(
            worker.engine, "ingest_platform_data", AsyncMock(return_value=None)
        )

        await worker._perform_scan()

        assert len(calls) == 3
        assert all(ctx.get("user_id") == "user-1" for _, ctx in calls)


class TestPlatformDataRequiresIdentity:
    async def test_missing_user_id_returns_empty_without_calling_integrations(
        self, monkeypatch
    ):
        """Defense in depth: even if a caller forgets the guard, empty context
        must not reach UniversalIntegrationService (which would raise and log
        a full traceback)."""
        from ai.data_intelligence import DataIntelligenceEngine, PlatformType

        engine = DataIntelligenceEngine()
        reached = []

        class _Boom:
            def __init__(self, *a, **k):
                raise AssertionError(
                    "UniversalIntegrationService constructed with no user identity"
                )

        monkeypatch.setattr(
            "integrations.universal_integration_service.UniversalIntegrationService",
            _Boom,
        )

        result = await engine._get_platform_data(PlatformType.SALESFORCE, {})

        assert result == []
        assert reached == []


class TestCircuitOpenShortCircuit:
    """The circuit-open envelope must actually be returned.

    ``circuit_breaker.get_stats`` is async; the un-awaited call produced a
    coroutine, so ``stats['disabled_until']`` raised
    ``TypeError: 'coroutine' object is not subscriptable`` and the short
    circuit escaped into the caller's generic handler (420 tracebacks in the
    live log).
    """

    async def test_open_circuit_returns_envelope(self, monkeypatch):
        from core import circuit_breaker as cb_mod
        from integrations.universal_integration_service import (
            UniversalIntegrationService,
        )

        async def _disabled(integration):
            return False

        async def _stats(integration):
            return {"disabled_until": 1234567890.0}

        monkeypatch.setattr(cb_mod.circuit_breaker, "is_enabled", _disabled)
        monkeypatch.setattr(cb_mod.circuit_breaker, "get_stats", _stats)

        svc = UniversalIntegrationService(workspace_id="ws_test")
        result = await svc.execute(
            "salesforce",
            "list",
            {"entity": "contact"},
            {"user_id": "user-1", "workspace_id": "ws_test"},
        )

        assert result.get("circuit_open") is True
        assert result.get("status") == "error"
        assert "1234567890" in result.get("error", "")

    async def test_open_circuit_without_stats_row_still_returns(self, monkeypatch):
        """A service with no recorded stats must not break the envelope."""
        from core import circuit_breaker as cb_mod
        from integrations.universal_integration_service import (
            UniversalIntegrationService,
        )

        async def _disabled(integration):
            return False

        async def _stats(integration):
            raise KeyError(integration)

        monkeypatch.setattr(cb_mod.circuit_breaker, "is_enabled", _disabled)
        monkeypatch.setattr(cb_mod.circuit_breaker, "get_stats", _stats)

        svc = UniversalIntegrationService(workspace_id="ws_test")
        result = await svc.execute(
            "jira", "list", {}, {"user_id": "user-1"},
        )

        assert result.get("circuit_open") is True


class TestChatRouteSurfacesTurnBudget:
    """POST /api/chat/message must forward the turn-budget code, not render the
    structured failure as a normal assistant message."""

    def test_turn_budget_error_code_passthrough(self):
        from datetime import datetime as _dt
        from types import SimpleNamespace as _NS
        from unittest.mock import AsyncMock, patch as _patch

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.security_dependencies import get_current_user
        from integrations import chat_routes as cr

        app = FastAPI()
        app.include_router(cr.router)
        app.dependency_overrides[get_current_user] = lambda: _NS(
            id="user_1", tenant_id="t1"
        )
        client = TestClient(app)

        with _patch.object(cr, "chat_orchestrator") as orch:
            orch.session_manager = MagicMock()
            orch.process_chat_message = AsyncMock(return_value={
                "success": False,
                "message": "This turn ran past its time budget before a reply "
                           "could be generated. Please try again.",
                "session_id": "s1",
                "intent": "conversation",
                "confidence": 0.5,
                "error_code": "turn_budget_exceeded",
                "timestamp": _dt.now().isoformat(),
            })
            resp = client.post(
                "/api/chat/message", json={"message": "hi", "user_id": "u"}
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert body["error_code"] == "turn_budget_exceeded"
        assert "time budget" in body["message"]
