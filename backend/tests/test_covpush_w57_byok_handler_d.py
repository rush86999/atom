"""Coverage wave 57 — core/llm/byok_handler.py section D: chat_completion + stream_completion.

chat_completion: no-clients ValueError, budget fail-closed, trial gate,
success path (cost attribution, health/rate/llm-call tracking, outcome
feedback), fallback chain (provider not serving model, provider failure →
heal → next provider), all-failed raise. stream_completion: success token
yield, error tokens, fallback chain. Uses make_handler from section A.
"""
import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.llm.byok_handler import (
    AllProvidersFailedError,
    AwaitableResult,
    BYOKHandler,
    GatewayBlockedError,
)


def _resp(content="ok", finish="stop", usage=None):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content),
                                 finish_reason=finish)],
        usage=usage or SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


def make_handler(**attrs):
    h = BYOKHandler.__new__(BYOKHandler)
    h.clients = {}
    h.async_clients = {}
    h.byok_manager = Mock()
    h.credential_service = None
    h.cognitive_classifier = Mock()
    h.cache_router = Mock()
    h.pricing_fetcher = Mock()
    h.db_session = None
    h.tier_service = Mock()
    h.excluded_models = set()
    h.health_monitor = MagicMock()
    h.health_monitor.health_scores = {}
    h.rate_tracker = Mock()
    h._last_used_model = None
    h._last_used_provider = None
    h._pending_routing_result_id = None
    h._embedding_initialized = False
    h._embedding_init_lock = None
    h._clients_initialized = True
    h.workspace_id = "ws1"
    h.tenant_id = "tenant"
    h.default_provider_id = None
    for k, v in attrs.items():
        setattr(h, k, v)
    return h


def _patch_trackers(h, budget_exceeded=False, trial_expired=False):
    ut = Mock()
    ut.is_budget_exceeded.return_value = budget_exceeded
    ut.is_trial_expired.return_value = trial_expired
    return patch("core.llm.byok_handler.llm_usage_tracker", ut), ut


class TestChatCompletionGuards:
    async def test_no_clients_raises(self):
        h = make_handler()
        with pytest.raises(ValueError):
            await h.chat_completion([{"role": "user", "content": "hi"}], "m", "openai")

    async def test_budget_exceeded_fail_closed(self):
        h = make_handler(async_clients={"openai": Mock()})
        p, ut = _patch_trackers(h, budget_exceeded=True)
        with p:
            with pytest.raises(GatewayBlockedError) as ei:
                await h.chat_completion([{"role": "user", "content": "hi"}], "m", "openai")
        assert ei.value.reason == "budget_exceeded"

    async def test_budget_tracker_error_fail_closed(self):
        h = make_handler(async_clients={"openai": Mock()})
        ut = Mock()
        ut.is_budget_exceeded.side_effect = RuntimeError("db down")
        with patch("core.llm.byok_handler.llm_usage_tracker", ut):
            with pytest.raises(GatewayBlockedError) as ei:
                await h.chat_completion([{"role": "user", "content": "hi"}], "m", "openai")
        assert ei.value.reason == "budget_check_failed"

    async def test_trial_expired(self):
        h = make_handler(async_clients={"openai": Mock()})
        p, ut = _patch_trackers(h, trial_expired=True)
        with p:
            with pytest.raises(GatewayBlockedError) as ei:
                await h.chat_completion([{"role": "user", "content": "hi"}], "m", "openai")
        assert ei.value.reason == "trial_expired"

    async def test_no_provider_order_raises(self):
        h = make_handler()
        p, ut = _patch_trackers(h)
        with p, patch.object(h, "_get_provider_fallback_order", return_value=[]):
            with pytest.raises(ValueError):
                await h.chat_completion([{"role": "user", "content": "hi"}], "m", "openai")


class TestChatCompletionSuccess:
    async def test_success_path(self):
        client = Mock()
        client.chat.completions.create = AsyncMock(return_value=_resp("hello"))
        h = make_handler(async_clients={"openai": client})
        p, ut = _patch_trackers(h)
        with p, \
             patch.object(h, "_get_provider_fallback_order",
                          return_value=["openai"]), \
             patch("core.llm.byok_handler.get_pricing_fetcher") as gpf, \
             patch.object(h, "_record_outcome_feedback",
                          new=AsyncMock()) as rof, \
             patch.object(h, "_stash_decision_features", return_value=None):
            gpf.return_value.estimate_cost.return_value = 0.01
            result = await h.chat_completion(
                [{"role": "user", "content": "hi"}], "gpt-4o", "openai",
                extra_kwargs={"stop": ["END"]})
        assert result["choices"][0]["message"]["content"] == "hello"
        _, kwargs = client.chat.completions.create.call_args
        assert kwargs["stop"] == ["END"]
        assert kwargs["max_tokens"] == 1000
        rof.assert_awaited_once()
        ut.record.assert_called_once()
        h.health_monitor.record_call.assert_called_once()
        h.rate_tracker.record_usage.assert_called_once()

    async def test_fallback_skips_non_serving_provider(self):
        client = Mock()
        client.chat.completions.create = AsyncMock(return_value=_resp("ok"))
        h = make_handler(async_clients={"openai": client})
        p, ut = _patch_trackers(h)
        with p, \
             patch.object(h, "_get_provider_fallback_order",
                          return_value=["anthropic", "openai"]), \
             patch.object(h, "_provider_serves_model",
                          side_effect=lambda pid, m: pid == "openai"), \
             patch.object(h, "_record_outcome_feedback", new=AsyncMock()):
            result = await h.chat_completion(
                [{"role": "user", "content": "hi"}], "gpt-4o", "openai")
        assert result["choices"][0]["message"]["content"] == "ok"

    async def test_fallback_after_failure(self):
        bad = Mock()
        bad.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))
        good = Mock()
        good.chat.completions.create = AsyncMock(return_value=_resp("recovered"))
        h = make_handler(async_clients={"openai": bad, "deepseek": good})
        p, ut = _patch_trackers(h)
        with p, \
             patch.object(h, "_get_provider_fallback_order",
                          return_value=["openai", "deepseek"]), \
             patch.object(h, "_record_outcome_feedback", new=AsyncMock()), \
             patch("core.llm.routing.request_healer.get_request_healer") as grh:
            healer = grh.return_value
            healer.heal.return_value = SimpleNamespace(patched_kwargs=None,
                                                       rule=None, patched_keys=[])
            result = await h.chat_completion(
                [{"role": "user", "content": "hi"}], "deepseek-chat", "openai")
        assert result["choices"][0]["message"]["content"] == "recovered"

    async def test_all_failed_raises(self):
        bad = Mock()
        bad.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))
        h = make_handler(async_clients={"openai": bad})
        p, ut = _patch_trackers(h)
        with p, \
             patch.object(h, "_get_provider_fallback_order", return_value=["openai"]), \
             patch("core.llm.routing.request_healer.get_request_healer") as grh:
            healer = grh.return_value
            healer.heal.return_value = SimpleNamespace(patched_kwargs=None,
                                                       rule=None, patched_keys=[])
            with pytest.raises(AllProvidersFailedError):
                await h.chat_completion(
                    [{"role": "user", "content": "hi"}], "deepseek-chat", "openai")


class _FakeStream:
    def __init__(self, chunks):
        self.chunks = chunks

    def __aiter__(self):
        async def it():
            for c in self.chunks:
                yield c
        return it()


def _streaming_client(chunks=None, error_text=None):
    client = Mock()

    async def create(**kw):
        if error_text:
            return _FakeStream([error_text])
        return _FakeStream([
            SimpleNamespace(choices=[SimpleNamespace(
                delta=SimpleNamespace(content=c), finish_reason=None)])
            for c in (chunks or ["hi"])
        ])

    client.chat.completions.create = create
    return client


class TestStreamCompletion:
    async def test_success_stream(self):
        client = _streaming_client(["hello", " world"])
        h = make_handler(async_clients={"openai": client})
        p, ut = _patch_trackers(h)
        with p, \
             patch.object(h, "_get_provider_fallback_order", return_value=["openai"]), \
             patch.object(h, "_record_outcome_feedback", new=AsyncMock()), \
             patch.object(h, "_stash_decision_features", return_value=None):
            chunks = []
            async for chunk in h.stream_completion(
                    [{"role": "user", "content": "hi"}], "gpt-4o", "openai"):
                chunks.append(chunk)
        assert "".join(chunks) == "hello world"

    async def test_error_delta(self):
        client = _streaming_client(error_text="\n\n[Error: provider down]")
        h = make_handler(async_clients={"openai": client})
        p, ut = _patch_trackers(h)
        with p, \
             patch.object(h, "_get_provider_fallback_order", return_value=["openai"]), \
             patch.object(h, "_record_outcome_feedback", new=AsyncMock()), \
             patch.object(h, "_stash_decision_features", return_value=None):
            chunks = []
            async for chunk in h.stream_completion(
                    [{"role": "user", "content": "hi"}], "gpt-4o", "openai"):
                chunks.append(chunk)
        assert any("[Error:" in c for c in chunks)
