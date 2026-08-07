"""Wiring tests: BYOKHandler dispatch sites emit per-call LLM usage records.

Verifies that ``generate_response``, ``stream_completion`` and
``chat_completion`` call ``_track_llm_call`` with correct
provider/model/success/latency/tokens/fallback/error on the success,
failure, heal-retry and cross-provider fallback paths.

Uses the FakeClient pattern from ``test_byok_chat_completion.py``; the
tracker singleton is mocked so no real metrics are emitted.
"""
import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm.byok_handler import (
    AllProvidersFailedError,
    BYOKHandler,
)


class FakeChoices:
    def __init__(self, content, finish_reason="stop"):
        self.message = MagicMock(content=content)
        self.finish_reason = finish_reason


class FakeUsage:
    prompt_tokens = 5
    completion_tokens = 3
    total_tokens = 8


class FakeResponse:
    def __init__(self, content="hi", finish_reason="stop"):
        self.choices = [FakeChoices(content, finish_reason)]
        self.usage = FakeUsage()


class FakeClient:
    """Mimics an OpenAI async client: ``chat.completions.create``."""

    def __init__(self, responses=None, excs=None):
        self._responses = list(responses or [])
        self._excs = list(excs or [])
        create = AsyncMock(side_effect=self._next)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

    def _next(self, **kwargs):
        if self._excs:
            raise self._excs.pop(0)
        if self._responses:
            return self._responses.pop(0)
        return FakeResponse()


class SyncFakeClient:
    """Mimics a SYNC OpenAI client for generate_response (sync dispatch)."""

    def __init__(self, responses=None, excs=None):
        self._responses = list(responses or [])
        self._excs = list(excs or [])
        create = MagicMock(side_effect=self._next)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

    def _next(self, **kwargs):
        if self._excs:
            raise self._excs.pop(0)
        if self._responses:
            return self._responses.pop(0)
        return FakeResponse()


def make_handler(async_clients=None, clients=None):
    """Build a BYOKHandler without running __init__ (heavy I/O)."""
    handler = object.__new__(BYOKHandler)
    handler.async_clients = async_clients or {}
    handler.clients = clients if clients is not None else {}
    handler.workspace_id = "ws-1"
    handler.tenant_id = "t-1"
    handler.user_id = "u-1"
    handler.health_monitor = MagicMock()
    handler.health_monitor.record_call = MagicMock()
    handler.cache_router = MagicMock()
    handler.rate_tracker = MagicMock()
    handler._last_used_model = None
    handler._last_used_provider = None
    handler._pending_routing_result_id = None
    handler._stash_decision_features = MagicMock(return_value="test-id")
    handler._record_outcome_feedback = AsyncMock()
    handler.byok_manager = MagicMock()
    handler._provider_serves_model = lambda pid, model: True
    handler._is_trial_restricted = lambda: False
    return handler


def patch_fallback(order):
    return patch.object(
        BYOKHandler, "_get_provider_fallback_order", lambda self, p: order
    )


@contextmanager
def fake_db_session():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    yield db


@pytest.fixture
def tracker_mock():
    with patch("core.llm.byok_handler.get_llm_call_tracker") as m:
        m.return_value = MagicMock()
        yield m.return_value


def assert_recorded(mock_tracker, **kwargs):
    calls = mock_tracker.record.call_args_list
    for call in calls:
        kw = call.kwargs
        if all(kw.get(k) == v for k, v in kwargs.items()):
            return call
    raise AssertionError(
        f"No record matching {kwargs} in {[c.kwargs for c in calls]}"
    )


# ---------------------------------------------------------------------------
# chat_completion
# ---------------------------------------------------------------------------

class TestChatCompletionTracking:
    @pytest.mark.asyncio
    async def test_success_records_call(self, tracker_mock):
        handler = make_handler({"openai": FakeClient([FakeResponse("hi")])})
        with patch_fallback(["openai"]):
            await handler.chat_completion(
                [{"role": "user", "content": "x"}], "gpt-4o", "openai"
            )
        assert_recorded(
            tracker_mock, provider="openai", model="gpt-4o", success=True,
            input_tokens=5, output_tokens=3, fallback=False,
            fallback_provider=None, error=None,
        )
        rec = assert_recorded(tracker_mock, provider="openai", success=True)
        assert rec.kwargs["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_fallback_records_failure_and_flagged_success(self, tracker_mock):
        fail_client = FakeClient(excs=[Exception("boom")])
        ok_client = FakeClient([FakeResponse("ok")])
        handler = make_handler(
            {"openai": fail_client, "anthropic": ok_client}
        )
        with patch_fallback(["openai", "anthropic"]):
            result = await handler.chat_completion(
                [{"role": "user", "content": "x"}], "claude-3", "openai"
            )
        assert result["choices"][0]["message"]["content"] == "ok"
        # Failed primary attempt: success=False, no fallback flag.
        assert_recorded(
            tracker_mock, provider="openai", model="claude-3", success=False,
            fallback=False, error="boom",
        )
        # Successful fallback attempt: fallback=True + primary provider.
        assert_recorded(
            tracker_mock, provider="anthropic", model="claude-3", success=True,
            fallback=True, fallback_provider="openai", error=None,
        )

    @pytest.mark.asyncio
    async def test_heal_retry_records_failure_then_success(self, tracker_mock):
        client = FakeClient()
        exc = ValueError("400 schema mismatch")
        client.chat.completions.create = AsyncMock(
            side_effect=[exc, FakeResponse("healed")]
        )
        handler = make_handler({"openai": client})
        heal = MagicMock()
        heal.patched_kwargs = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "x"}],
            "temperature": 0.7,
            "max_tokens": 100,
        }
        heal.rule = "test-rule"
        heal.patched_keys = ["model"]
        with patch_fallback(["openai"]), patch(
            "core.llm.routing.request_healer.get_request_healer",
            return_value=MagicMock(heal=MagicMock(return_value=heal)),
        ):
            await handler.chat_completion(
                [{"role": "user", "content": "x"}], "gpt-4o", "openai"
            )
        assert_recorded(
            tracker_mock, provider="openai", success=False, error="400 schema mismatch"
        )
        # Healed success: same provider, still fallback=False.
        assert_recorded(
            tracker_mock, provider="openai", success=True, fallback=False,
        )

    @pytest.mark.asyncio
    async def test_all_failed_records_failure(self, tracker_mock):
        handler = make_handler({"openai": FakeClient(excs=[Exception("boom")])})
        with patch_fallback(["openai"]):
            with pytest.raises(AllProvidersFailedError):
                await handler.chat_completion(
                    [{"role": "user", "content": "x"}], "gpt-4o", "openai"
                )
        assert_recorded(
            tracker_mock, provider="openai", model="gpt-4o", success=False,
            error="boom", fallback=False,
        )


# ---------------------------------------------------------------------------
# stream_completion
# ---------------------------------------------------------------------------

class TestStreamCompletionTracking:
    @pytest.mark.asyncio
    async def test_success_records_call_with_output_tokens(self, tracker_mock):
        async def chunks():
            yield SimpleNamespace(choices=[SimpleNamespace(
                delta=SimpleNamespace(content="hello"), finish_reason=None)])
            yield SimpleNamespace(choices=[SimpleNamespace(
                delta=SimpleNamespace(content=" world"), finish_reason=None)])
            yield SimpleNamespace(choices=[SimpleNamespace(
                delta=SimpleNamespace(content=None), finish_reason="stop")])

        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=chunks())
        handler = make_handler({"openai": client})
        with patch_fallback(["openai"]):
            async for _ in handler.stream_completion(
                [{"role": "user", "content": "x"}], "gpt-5", "openai"
            ):
                pass
        assert_recorded(
            tracker_mock, provider="openai", model="gpt-5", success=True,
            output_tokens=2, fallback=False, error=None,
        )

    @pytest.mark.asyncio
    async def test_fallback_records_failure_then_flagged_success(self, tracker_mock):
        async def ok_chunks():
            yield SimpleNamespace(choices=[SimpleNamespace(
                delta=SimpleNamespace(content="ok"), finish_reason=None)])
            yield SimpleNamespace(choices=[SimpleNamespace(
                delta=SimpleNamespace(content=None), finish_reason="stop")])

        fail_client = MagicMock()
        fail_client.chat.completions.create = AsyncMock(
            side_effect=Exception("stream boom")
        )
        ok_client = MagicMock()
        ok_client.chat.completions.create = AsyncMock(return_value=ok_chunks())
        handler = make_handler(
            {"opencode-go": fail_client, "openai": ok_client}
        )
        with patch_fallback(["opencode-go", "openai"]):
            async for _ in handler.stream_completion(
                [{"role": "user", "content": "x"}], "gpt-5", "opencode-go"
            ):
                pass
        assert_recorded(
            tracker_mock, provider="opencode-go", model="gpt-5", success=False,
            error="stream boom", fallback=False,
        )
        assert_recorded(
            tracker_mock, provider="openai", model="gpt-5", success=True,
            fallback=True, fallback_provider="opencode-go",
        )


# ---------------------------------------------------------------------------
# generate_response
# ---------------------------------------------------------------------------

class TestGenerateResponseTracking:
    @pytest.mark.asyncio
    async def test_success_records_call(self, tracker_mock):
        handler = make_handler(clients={"openai": SyncFakeClient([FakeResponse("hello")])})
        handler.analyze_query_complexity = lambda p, t: SimpleNamespace(value="simple")
        handler.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o")])
        handler._rerank_with_learning = AsyncMock(
            side_effect=lambda options, *a, **k: options
        )
        with patch("core.llm.byok_handler.get_db_session", fake_db_session), \
             patch("core.llm.byok_handler.llm_usage_tracker") as usage_tracker, \
             patch("core.llm.byok_handler.get_pricing_fetcher") as pricing:
            usage_tracker.is_budget_exceeded = lambda ws: False
            pricing.return_value.estimate_cost = lambda m, i, o: None
            result = await handler.generate_response("hello", task_type="chat")
        assert result == "hello"
        assert_recorded(
            tracker_mock, provider="openai", model="gpt-4o", success=True,
            input_tokens=5, output_tokens=3, fallback=False, error=None,
        )

    @pytest.mark.asyncio
    async def test_fallback_records_failure_then_flagged_success(self, tracker_mock):
        fail_client = SyncFakeClient(excs=[Exception("nope")])
        ok_client = SyncFakeClient([FakeResponse("ok")])
        handler = make_handler(
            clients={"openai": fail_client, "deepseek": ok_client}
        )
        handler.analyze_query_complexity = lambda p, t: SimpleNamespace(value="simple")
        handler.get_ranked_providers = AsyncMock(
            return_value=[("openai", "gpt-4o"), ("deepseek", "deepseek-chat")]
        )
        handler._rerank_with_learning = AsyncMock(
            side_effect=lambda options, *a, **k: options
        )
        with patch("core.llm.byok_handler.get_db_session", fake_db_session), \
             patch("core.llm.byok_handler.llm_usage_tracker") as usage_tracker, \
             patch("core.llm.byok_handler.get_pricing_fetcher") as pricing:
            usage_tracker.is_budget_exceeded = lambda ws: False
            pricing.return_value.estimate_cost = lambda m, i, o: None
            result = await handler.generate_response("hello", task_type="chat")
        assert result == "ok"
        assert_recorded(
            tracker_mock, provider="openai", model="gpt-4o", success=False,
            error="nope", fallback=False,
        )
        assert_recorded(
            tracker_mock, provider="deepseek", model="deepseek-chat", success=True,
            fallback=True, fallback_provider="openai",
        )

    @pytest.mark.asyncio
    async def test_all_failed_records_failure(self, tracker_mock):
        handler = make_handler(clients={"openai": SyncFakeClient(excs=[Exception("nope")])})
        handler.analyze_query_complexity = lambda p, t: SimpleNamespace(value="simple")
        handler.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o")])
        handler._rerank_with_learning = AsyncMock(
            side_effect=lambda options, *a, **k: options
        )
        with patch("core.llm.byok_handler.get_db_session", fake_db_session), \
             patch("core.llm.byok_handler.llm_usage_tracker") as usage_tracker, \
             patch("core.llm.byok_handler.get_pricing_fetcher") as pricing:
            usage_tracker.is_budget_exceeded = lambda ws: False
            pricing.return_value.estimate_cost = lambda m, i, o: None
            result = await handler.generate_response("hello", task_type="chat")
        assert result.startswith("I'm sorry")
        assert_recorded(
            tracker_mock, provider="openai", model="gpt-4o", success=False,
            error="nope", fallback=False,
        )
