"""Coverage wave 10b — LLM gateway + BYOK handler coverage push (TDD).

Red-green targets (real bugs):
- WB1: ``x-atom-intent`` header is parsed then discarded in
  ``GatewayService._resolve_route`` — the documented "forces intent"
  behavior is a no-op (the learning-router re-rank never runs).
- WB2: ``GatewayService._absolute_fallback`` hardcodes ``"gpt-4o-mini"``
  regardless of the first configured client — an Anthropic-only deployment
  falls back to a model its provider does not serve (guaranteed 502).
- WB3: ``openai_response_to_anthropic`` emits ``"text": [ ... ]`` (a nested
  list) when the OpenAI response carries multi-part list content — a
  malformed Anthropic message.
- WB4: the gateway streaming routes accept ``stop``/``top_p`` but never
  forward them — ``stream_completion`` has no ``extra_kwargs`` seam, so
  stop sequences are silently ignored in streaming mode.
"""
import asyncio
import hashlib
import json
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.database import get_db
from core.llm.byok_handler import (
    AllProvidersFailedError,
    GatewayBlockedError,
    NoProvidersConfiguredError,
)
from core.llm.gateway.auth import GatewayIdentity, hash_api_key, _rate_limit_state
from core.llm.gateway.gateway_service import GatewayService
from core.llm.gateway.request_logger import (
    MAX_LOG_BODY_CHARS,
    _drop_auth_headers,
    _redact_text,
    _sanitize_body,
    _truncate,
    estimate_cost_usd,
    log_gateway_request,
    sweep_gateway_logs,
)
from core.llm.gateway.wire_formats import (
    anthropic_request_to_openai,
    map_error_type,
    map_stop_reason,
    openai_error_to_anthropic,
    openai_response_to_anthropic,
    prompt_from_messages,
)
from core.llm.provider_rate_limits import ProviderRateTracker
from core.models import GatewayApiKey, GatewayRequestLog, User

_KEY = "atom_sk_0123456789abcdef"
_KEY_HEADERS = {"x-api-key": _KEY}
_MSGS = [{"role": "user", "content": "hi"}]


# --------------------------------------------------------------------------- #
# Shared harness (mirrors test_bughunt_gateway conventions)
# --------------------------------------------------------------------------- #
def make_key_row(plaintext=_KEY, **overrides):
    row = MagicMock(spec=GatewayApiKey)
    row.id = "key-1"
    row.key_hash = hashlib.sha256(plaintext.encode()).hexdigest()
    row.key_prefix = "atom_sk_"
    row.name = "test"
    row.user_id = "u-1"
    row.tenant_id = "t-1"
    row.workspace_id = None
    row.is_active = True
    row.revoked_at = None
    row.expires_at = None
    row.rate_limit_per_minute = 60
    row.total_requests = 0
    row.last_used = None
    for k, v in overrides.items():
        setattr(row, k, v)
    return row


def make_db(key_row=None):
    db = MagicMock()
    stored_hash = key_row.key_hash if key_row else None

    def query_side_effect(model, *a, **k):
        q = MagicMock()
        name = getattr(model, "__name__", str(model))
        if name == "GatewayApiKey":
            def filter_side(expr, *fa, **fk):
                right = getattr(expr, "right", None)
                req_hash = getattr(right, "value", None)
                q2 = MagicMock()
                if req_hash is not None and stored_hash is not None and req_hash == stored_hash:
                    q2.first.return_value = key_row
                else:
                    q2.first.return_value = None
                return q2

            q.filter.side_effect = filter_side
            q.filter.return_value.first.return_value = key_row
        elif name == "User":
            u = MagicMock()
            u.id = key_row.user_id if key_row else "u-1"
            u.status = "active"
            u.tenant_id = "t-1"
            q.filter.return_value.first.return_value = u
        else:
            q.filter.return_value.first.return_value = None
            q.filter.return_value.all.return_value = []
        return q

    db.query.side_effect = query_side_effect
    return db


def make_client(db, routes=None):
    from api.openai_gateway_routes import router as gateway_router

    app = FastAPI()
    app.include_router(routes or gateway_router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def _identity(**overrides):
    base = dict(
        user_id="u-1", tenant_id="t-1", workspace_id="ws-1",
        auth_method="api_key", api_key_id="key-1",
    )
    base.update(overrides)
    return GatewayIdentity(**base)


def _fake_handler(**overrides):
    handler = MagicMock()
    handler.analyze_query_complexity.return_value = "simple"
    handler.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")
    handler.get_ranked_providers.return_value = [("openai", "gpt-4o-mini")]
    handler._provider_serves_model.return_value = False
    handler._rerank_with_learning = AsyncMock(
        side_effect=lambda options, prompt, task_type, intent=None: options
    )
    handler.async_clients = {"openai": object(), "anthropic": object()}
    handler.clients = {}
    handler.byok_manager = SimpleNamespace(providers={})
    handler.chat_completion = AsyncMock(
        return_value={
            "model": "gpt-4o",
            "choices": [{"message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
    )
    handler.stream_completion = AsyncMock()
    for k, v in overrides.items():
        setattr(handler, k, v)
    return handler


def _service_harness(handler):
    with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler):
        return GatewayService(_identity(), MagicMock())


# =========================================================================== #
# WB1 — x-atom-intent header is a no-op (must drive the learning re-rank)
# =========================================================================== #
class TestIntentOverride:
    async def test_intent_header_threads_through_rerank(self):
        handler = _fake_handler()
        service = _service_harness(handler)
        provider, model = await service._resolve_route(
            _MSGS, None, {"x-atom-intent": "coding"}
        )
        assert handler._rerank_with_learning.called
        assert handler._rerank_with_learning.await_args.kwargs["intent"] == "coding"
        assert provider == "openai"

    async def test_intent_with_forced_tier_reranks_ranked_options(self):
        handler = _fake_handler()
        handler.get_ranked_providers.return_value = [
            ("openai", "gpt-4o-mini"), ("anthropic", "claude-sonnet"),
        ]

        async def _rerank(options, prompt, task_type, intent=None):
            return [("anthropic", "claude-sonnet"), ("openai", "gpt-4o-mini")]

        handler._rerank_with_learning = AsyncMock(side_effect=_rerank)
        service = _service_harness(handler)
        provider, model = await service._resolve_route(
            _MSGS, None, {"x-atom-intent": "reasoning", "x-atom-tier": "heavy"}
        )
        assert handler.get_ranked_providers.await_args.kwargs["cognitive_tier"] is not None
        assert provider == "anthropic"
        assert model == "claude-sonnet"

    async def test_no_intent_header_skips_rerank(self):
        handler = _fake_handler()
        service = _service_harness(handler)
        await service._resolve_route(_MSGS, None, {"x-atom-model": "gpt-4o"})
        assert not handler._rerank_with_learning.called


# =========================================================================== #
# WB2 — _absolute_fallback hardcodes gpt-4o-mini for non-OpenAI providers
# =========================================================================== #
class TestAbsoluteFallbackModel:
    def test_fallback_uses_provider_configured_model(self):
        handler = _fake_handler()
        handler.byok_manager = SimpleNamespace(
            providers={"anthropic": SimpleNamespace(model="claude-3-5-sonnet-20240620")}
        )
        handler.async_clients = {"anthropic": object()}
        service = _service_harness(handler)
        provider, model = service._absolute_fallback()
        assert provider == "anthropic"
        assert model == "claude-3-5-sonnet-20240620"

    def test_fallback_keeps_default_when_no_configured_model(self):
        handler = _fake_handler()
        handler.byok_manager = SimpleNamespace(providers={"openai": SimpleNamespace(model="")})
        service = _service_harness(handler)
        provider, model = service._absolute_fallback()
        assert provider == "openai"
        assert model == "gpt-4o-mini"

    def test_fallback_raises_without_clients(self):
        handler = _fake_handler()
        handler.async_clients = {}
        handler.clients = {}
        service = _service_harness(handler)
        with pytest.raises(NoProvidersConfiguredError):
            service._absolute_fallback()

    def test_invalid_tier_override_dropped_at_parse_routes_normally(self):
        # parse_routing_overrides drops unknown tiers (test_routing_header_overrides
        # contract) — the bogus value never reaches _resolve_route, so routing is
        # the plain BPC path, NOT the absolute fallback.
        handler = _fake_handler()
        handler.byok_manager = SimpleNamespace(
            providers={"anthropic": SimpleNamespace(model="claude-sonnet-4-5")}
        )
        handler.async_clients = {"anthropic": object()}
        service = _service_harness(handler)

        async def run():
            return await service._resolve_route(_MSGS, None, {"x-atom-tier": "bogus"})

        provider, model = asyncio.run(run())
        assert provider == "openai"
        assert model == "gpt-4o-mini"


# =========================================================================== #
# WB3 — openai_response_to_anthropic emits nested list for list content
# =========================================================================== #
class TestMultiPartContentFlatten:
    def test_list_content_flattened_to_text(self):
        resp = {
            "model": "gpt-4o",
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "Hello "},
                            {"type": "text", "text": "world"},
                        ]
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
        }
        out = openai_response_to_anthropic(resp)
        assert out["content"] == [{"type": "text", "text": "Hello world"}]

    def test_list_content_string_parts(self):
        resp = {
            "model": "m",
            "choices": [{"message": {"content": ["part-a", "part-b"]}, "finish_reason": "stop"}],
        }
        out = openai_response_to_anthropic(resp)
        assert out["content"] == [{"type": "text", "text": "part-apart-b"}]


# =========================================================================== #
# WB4 — streaming drops stop/top_p (extra_kwargs never forwarded)
# =========================================================================== #
class TestStreamExtraKwargs:
    def _stream_route_client(self):
        db = make_db(make_key_row(_KEY))
        return make_client(db)

    @staticmethod
    def _async_gen(*chunks):
        async def gen():
            for c in chunks:
                yield c

        return gen()

    def test_openai_stream_forwards_stop_sequences(self):
        client = self._stream_route_client()
        handler = _fake_handler()
        seen = {}

        def _fake_stream(*args, **kwargs):
            seen.update(kwargs)
            return self._async_gen("Hello", " world")

        handler.stream_completion = _fake_stream
        with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler):
            r = client.post(
                "/v1/chat/completions",
                headers=_KEY_HEADERS,
                json={"messages": _MSGS, "stream": True, "stop": ["\n\n"], "top_p": 0.5},
            )
        assert r.status_code == 200
        assert seen["extra_kwargs"] == {
            "stop": ["\n\n"], "top_p": 0.5,
        }
        assert "Hello" in r.text

    def test_anthropic_stream_forwards_stop_sequences(self):
        client = self._stream_route_client()
        handler = _fake_handler()
        seen = {}

        def _fake_stream(*args, **kwargs):
            seen.update(kwargs)
            return self._async_gen("Hello", " world")

        handler.stream_completion = _fake_stream
        with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler):
            r = client.post(
                "/v1/messages",
                headers={**_KEY_HEADERS, "anthropic-version": "2023-06-01"},
                json={"messages": _MSGS, "stream": True, "stop_sequences": ["</s>"], "top_p": 0.9},
            )
        assert r.status_code == 200
        assert seen["extra_kwargs"] == {
            "stop": ["</s>"], "top_p": 0.9,
        }
        assert "Hello" in r.text

    def test_stream_completion_forwards_extra_kwargs_to_client(self):
        from core.llm.byok_handler import BYOKHandler

        client = AsyncMock()
        client.chat.completions.create = AsyncMock()

        async def _chunks():
            for c in ["a", "b"]:
                yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=c), finish_reason=None)])

        client.chat.completions.create.return_value = _chunks()
        h = MagicMock()
        h.async_clients = {"openai": client}
        h.clients = {}
        h._get_provider_fallback_order = MagicMock(return_value=["openai"])
        h.health_monitor = MagicMock()
        h.health_monitor.record_call = MagicMock()
        h._stash_decision_features = MagicMock(return_value=None)
        # The P4 prompt-taint gate is consulted in the stream path; an
        # un-stubbed MagicMock returns a truthy "block reason" and the stream
        # yields an error token instead of model output.
        h._llm_taint_check = MagicMock(return_value=None)
        h._track_llm_call = MagicMock()
        h._track_rate_usage = MagicMock()
        h.rate_tracker = MagicMock()
        h._record_outcome_feedback = AsyncMock()
        h.tenant_id = "t-1"
        h.workspace_id = "ws-1"

        async def run():
            out = []
            async for tok in BYOKHandler.stream_completion(
                h, _MSGS, "gpt-4o", "openai", extra_kwargs={"stop": ["END"]}
            ):
                out.append(tok)
            return out

        out = asyncio.run(run())
        assert out == ["a", "b"]
        assert client.chat.completions.create.await_args.kwargs["stop"] == ["END"]
        assert client.chat.completions.create.await_args.kwargs["stream"] is True


# =========================================================================== #
# wire_formats coverage
# =========================================================================== #
class TestPromptFromMessages:
    def test_empty_returns_default(self):
        assert prompt_from_messages([], "fallback") == "fallback"

    def test_no_user_message_returns_default(self):
        assert prompt_from_messages([{"role": "assistant", "content": "x"}]) == ""

    def test_non_dict_message_skipped(self):
        assert prompt_from_messages(["junk", {"role": "user", "content": "real"}]) == "real"

    def test_none_content_skipped(self):
        assert prompt_from_messages([{"role": "user", "content": None}]) == ""

    def test_list_content_with_mixed_parts(self):
        msgs = [{
            "role": "user",
            "content": [
                {"type": "text", "text": "What "},
                {"type": "image_url", "image_url": {"url": "http://x"}},
                {"text": "is 2+2?"},
                "plain",
            ],
        }]
        assert prompt_from_messages(msgs) == "What is 2+2? plain"

    def test_non_str_non_list_content_str_casted(self):
        assert prompt_from_messages([{"role": "user", "content": 42}]) == "42"

    def test_last_user_wins(self):
        msgs = [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "middle"},
            {"role": "user", "content": "last"},
        ]
        assert prompt_from_messages(msgs) == "last"


class TestAnthropicToOpenAI:
    def test_full_payload_translation(self):
        payload = {
            "model": "claude-3-5-sonnet",
            "system": [{"type": "text", "text": "Sys A "}, {"type": "text", "text": "Sys B"}],
            "messages": [
                {"role": "user", "content": "plain text"},
                {"role": "assistant", "content": [
                    {"type": "text", "text": "hi"},
                    {"type": "image", "source": {"type": "url", "url": "https://img"}},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "AAAA"}},
                    {"type": "tool_use", "name": "calc", "input": {"x": 1}, "id": "t1"},
                    {"type": "tool_result", "tool_use_id": "t1", "content": "42"},
                    {"type": "thinking", "thinking": "hmm"},
                    "raw-string-block",
                ]},
                {"role": "other", "content": ["a", "b"]},
                {"role": "user", "content": []},
            ],
            "stop_sequences": ["</s>"],
            "top_p": 0.3,
        }
        out = anthropic_request_to_openai(payload)
        assert out["messages"][0] == {"role": "system", "content": "Sys A Sys B"}
        assert out["messages"][1] == {"role": "user", "content": "plain text"}
        assert out["messages"][2]["role"] == "assistant"
        content = out["messages"][2]["content"]
        assert {"type": "text", "text": "hi"} in content
        assert any(
            p.get("type") == "image_url" and p["image_url"]["url"] == "https://img"
            for p in content
        )
        assert any(
            p.get("type") == "image_url" and p["image_url"]["url"].startswith("data:image/png;base64,")
            for p in content
        )
        assert out["messages"][3]["content"] == ["a", "b"] or out["messages"][3]["content"] == "ab"
        assert out["messages"][4]["content"] == ""
        assert out["stop"] == ["</s>"]
        assert out["top_p"] == 0.3
        assert out["max_tokens"] == 1000

    def test_system_str_and_no_model(self):
        out = anthropic_request_to_openai({
            "system": "Root sys",
            "messages": [{"role": "user", "content": "q"}],
        })
        assert out["messages"][0]["content"] == "Root sys"
        assert "model" not in out
        assert "stop" not in out

    def test_content_block_empty_tool_blocks_dropped(self):
        out = anthropic_request_to_openai({
            "messages": [
                {"role": "assistant", "content": [
                    {"type": "tool_use", "name": "x", "id": "t1"},
                    {"type": "tool_result", "tool_use_id": "t1", "content": ""},
                ]},
            ],
        })
        assert out["messages"][0]["content"] == ""

    def test_content_block_non_dict_parts(self):
        out = anthropic_request_to_openai({
            "messages": [{"role": "user", "content": [{"type": "text", "text": "t1"}]}],
        })
        assert out["messages"][0]["content"] == [{"type": "text", "text": "t1"}]


class TestStopReasonAndErrors:
    def test_map_stop_reason_known(self):
        assert map_stop_reason("stop") == "end_turn"
        assert map_stop_reason("length") == "max_tokens"
        assert map_stop_reason("tool_calls") == "tool_use"
        assert map_stop_reason("function_call") == "tool_use"
        assert map_stop_reason("content_filter") == "max_tokens"
        assert map_stop_reason(None) == "end_turn"

    def test_map_stop_reason_unknown_passthrough(self):
        assert map_stop_reason("weird") == "weird"

    def test_map_error_type(self):
        assert map_error_type(400) == "invalid_request_error"
        assert map_error_type(401) == "authentication_error"
        assert map_error_type(403) == "permission_error"
        assert map_error_type(404) == "not_found_error"
        assert map_error_type(422) == "invalid_request_error"
        assert map_error_type(429) == "rate_limit_error"
        assert map_error_type(500) == "api_error"
        assert map_error_type(502) == "api_error"
        assert map_error_type(503) == "overloaded_error"
        assert map_error_type(504) == "api_error"
        assert map_error_type(418) == "api_error"

    def test_openai_error_to_anthropic(self):
        body = openai_error_to_anthropic(429, "rate_limit_exceeded", "slow down")
        assert body == {
            "type": "error",
            "error": {"type": "rate_limit_error", "message": "slow down", "code": "rate_limit_exceeded"},
        }


class TestOpenAIResponseToAnthropic:
    def test_basic_translation(self):
        out = openai_response_to_anthropic({
            "model": "gpt-4o",
            "created": 1234,
            "choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
        })
        assert out["model"] == "gpt-4o"
        assert out["role"] == "assistant"
        assert out["content"] == [{"type": "text", "text": "hi"}]
        assert out["stop_reason"] == "end_turn"
        assert out["usage"]["input_tokens"] == 2
        assert out["usage"]["output_tokens"] == 3
        assert out["usage"]["total_tokens"] == 5
        assert out["created"] == 1234
        assert out["id"].startswith("msg_atom_")

    def test_no_choices_and_explicit_stop_reason(self):
        out = openai_response_to_anthropic({"model": "m", "created": 5}, stop_reason="max_tokens")
        assert out["content"] == [{"type": "text", "text": ""}]
        assert out["stop_reason"] == "max_tokens"
        assert out["usage"]["input_tokens"] == 0

    def test_no_created_falls_back_to_time(self):
        out = openai_response_to_anthropic({"model": "m", "choices": []})
        assert abs(out["created"] - int(time.time())) <= 2


# =========================================================================== #
# request_logger coverage
# =========================================================================== #
class TestRequestLoggerUnits:
    def test_drop_auth_headers(self):
        headers = {
            "Authorization": "Bearer x",
            "x-api-key": "atom_sk_",
            "Cookie": "a=b",
            "Proxy-Authorization": "y",
            "content-type": "application/json",
        }
        dropped = _drop_auth_headers(headers)
        assert dropped == {"content-type": "application/json"}

    def test_drop_auth_headers_non_dict(self):
        assert _drop_auth_headers("nope") == {}

    def test_redact_text_empty(self):
        assert _redact_text("") == ""

    def test_redact_text_redacts(self):
        with patch("core.pii_redactor.redact_pii", return_value="***"):  # noqa: F841
            import core.llm.gateway.request_logger as rl
            assert rl._redact_text("some secret text") == "***"

    def test_redact_text_fails_closed(self, monkeypatch):
        def _boom(text):
            raise RuntimeError("redactor down")

        monkeypatch.setitem(
            __import__("sys").modules, "core.pii_redactor",
            SimpleNamespace(redact_pii=_boom),
        )
        assert _redact_text("raw pii") == "[redaction unavailable — body omitted]"

    def test_truncate(self):
        long = "x" * (MAX_LOG_BODY_CHARS + 100)
        assert len(_truncate(long)) == MAX_LOG_BODY_CHARS
        assert _truncate("short") == "short"
        assert _truncate("") == ""

    def test_sanitize_body_disabled(self):
        assert _sanitize_body({"a": 1}, False) is None
        assert _sanitize_body(None, True) is None

    def test_sanitize_body_serialize_and_redact(self):
        # _sanitize_body takes include_body directly; the ATOM_GATEWAY_LOG_BODIES
        # setting is resolved by log_bodies() at the call sites.
        out = _sanitize_body({"msg": "hi", "nested": [1, 2]}, True)
        assert json.loads(out) == {"msg": "hi", "nested": [1, 2]}

    def test_sanitize_body_dumps_failure_falls_back_to_str(self):
        body = SimpleNamespace()  # not JSON-serializable
        out = _sanitize_body(body, True)
        assert "namespace" in out.lower() or "object" in out.lower()

    def test_estimate_cost_fetcher_path(self):
        fetcher = MagicMock()
        fetcher.estimate_cost.return_value = 0.0042
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=fetcher):
            assert estimate_cost_usd("gpt-4o", 10, 5) == 0.0042

    def test_estimate_cost_fallback_to_static(self):
        fetcher = MagicMock()
        fetcher.estimate_cost.return_value = None
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=fetcher), \
             patch("core.cost_config.get_llm_cost", return_value=0.001):
            assert estimate_cost_usd("gpt-4o", 10, 5) == 0.001

    def test_estimate_cost_none_when_zero_or_error(self):
        fetcher = MagicMock()
        fetcher.estimate_cost.return_value = 0.0
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=fetcher), \
             patch("core.cost_config.get_llm_cost", return_value=0.0):
            assert estimate_cost_usd("gpt-4o", 10, 5) is None
        fetcher.estimate_cost.side_effect = RuntimeError("boom")
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=fetcher):
            assert estimate_cost_usd("gpt-4o", 10, 5) is None


class TestLogGatewayRequestDb:
    def test_writes_row_and_returns_id(self, worker_database):
        session = worker_database()
        log_id = log_gateway_request(
            session, _identity(),
            provider="openai", model="gpt-4o", stream=False, status_code=200,
            latency_ms=12, prompt_tokens=3, completion_tokens=4, cost_usd=0.01,
            request_body={"messages": _MSGS}, response_body={"choices": []},
        )
        assert log_id is not None
        row = session.query(GatewayRequestLog).filter(GatewayRequestLog.id == log_id).first()
        assert row is not None
        assert row.user_id == "u-1"
        assert row.request_json is None  # bodies disabled by default
        session.close()

    def test_writes_body_when_enabled(self, worker_database):
        session = worker_database()
        with patch("core.llm.gateway.request_logger.log_bodies", return_value=True):
            log_id = log_gateway_request(
                session, _identity(), provider="openai", model="m",
                request_body={"messages": [{"role": "user", "content": "hello"}]},
            )
        row = session.query(GatewayRequestLog).filter(GatewayRequestLog.id == log_id).first()
        assert "hello" in row.request_json
        session.close()

    def test_none_identity_is_safe(self, worker_database):
        # user_id is NOT NULL on GatewayRequestLog — a None identity cannot
        # persist a row; log_gateway_request must degrade gracefully (None,
        # never raise) so logging can never break a gateway response.
        session = worker_database()
        log_id = log_gateway_request(session, None, model="m")
        assert log_id is None
        session.close()

    def test_db_failure_returns_none_and_rolls_back(self, worker_database):
        session = worker_database()
        session.add = MagicMock(side_effect=RuntimeError("db down"))
        assert log_gateway_request(session, _identity()) is None
        session.close()

    def test_sweep_deletes_old_rows(self, worker_database):
        session = worker_database()
        old_id = log_gateway_request(session, _identity(), model="old")
        new_id = log_gateway_request(session, _identity(), model="new")
        row = session.query(GatewayRequestLog).filter(GatewayRequestLog.id == old_id).first()
        row.created_at = datetime.now(timezone.utc) - timedelta(days=90)
        session.commit()
        deleted = sweep_gateway_logs(session)
        assert deleted >= 1
        assert session.query(GatewayRequestLog).filter(GatewayRequestLog.id == old_id).first() is None
        assert session.query(GatewayRequestLog).filter(GatewayRequestLog.id == new_id).first() is not None
        session.close()

    def test_sweep_failure_returns_zero(self, worker_database):
        session = worker_database()
        session.commit = MagicMock(side_effect=RuntimeError("boom"))
        assert sweep_gateway_logs(session) == 0
        session.close()


# =========================================================================== #
# budget_alerts coverage
# =========================================================================== #
class TestBudgetAlerts:
    @pytest.fixture(autouse=True)
    def _reset(self):
        from core.llm.gateway.budget_alerts import reset_budget_alerts

        reset_budget_alerts()
        yield
        reset_budget_alerts()

    async def test_disabled_flag_returns_empty(self):
        from core.llm.gateway.budget_alerts import record_gateway_spend

        with patch("core.llm.gateway.budget_alerts.GATEWAY_BUDGET_ALERTS_ENABLED", False):
            assert await record_gateway_spend("ws-1", 5.0, user_id="u-1") == []

    async def test_no_cost_returns_empty(self):
        from core.llm.gateway.budget_alerts import record_gateway_spend

        with patch("core.llm.gateway.budget_alerts.GATEWAY_BUDGET_ALERTS_ENABLED", True):
            assert await record_gateway_spend("ws-1", None, user_id="u-1") == []
            assert await record_gateway_spend("ws-1", 0.0, user_id="u-1") == []
            assert await record_gateway_spend("ws-1", -1.0, user_id="u-1") == []

    async def test_zero_budget_returns_empty(self):
        from core.llm.gateway.budget_alerts import record_gateway_spend

        with patch("core.llm.gateway.budget_alerts.GATEWAY_BUDGET_ALERTS_ENABLED", True), \
             patch("core.llm.gateway.budget_alerts.resolve_budget_limit", return_value=0.0):
            assert await record_gateway_spend("ws-1", 1.0) == []

    async def test_threshold_crossed_and_fire_once(self):
        from core.llm.gateway.budget_alerts import record_gateway_spend

        notifier = AsyncMock()
        with patch("core.llm.gateway.budget_alerts.GATEWAY_BUDGET_ALERTS_ENABLED", True), \
             patch("core.llm.gateway.budget_alerts.resolve_budget_limit", return_value=100.0), \
             patch("core.llm.gateway.budget_alerts._resolve_recipient_id", return_value="u-admin"), \
             patch("core.llm.gateway.budget_alerts.NotificationService", return_value=notifier):
            crossed = await record_gateway_spend("ws-1", 51.0, user_id="u-1")
            assert crossed == [50]
            # second call past 80% fires only the new threshold
            crossed2 = await record_gateway_spend("ws-1", 30.0, user_id="u-1")
            assert crossed2 == [80]
            assert notifier.send_notification.await_count == 2
            args = notifier.send_notification.await_args.args
            assert args[0] == "u-admin"
            assert args[1] == "gateway_budget_alert"
            assert "80" in args[2]["title"]
            assert args[2]["metadata"]["usage_percent"] > 80

    async def test_new_day_resets_fired_state(self):
        import core.llm.gateway.budget_alerts as ba
        from core.llm.gateway.budget_alerts import record_gateway_spend

        with patch("core.llm.gateway.budget_alerts.GATEWAY_BUDGET_ALERTS_ENABLED", True), \
             patch("core.llm.gateway.budget_alerts.resolve_budget_limit", return_value=100.0), \
             patch("core.llm.gateway.budget_alerts._resolve_recipient_id", return_value="u-admin"), \
             patch("core.llm.gateway.budget_alerts.NotificationService", return_value=AsyncMock()):
            await record_gateway_spend("ws-1", 51.0)
            # module-attr access: _reset_if_new_day REBINDS the module global,
            # so a locally imported _fired binding would be stale
            assert 50 in ba._fired["ws-1"]
            # simulate a new day
            with patch("core.llm.gateway.budget_alerts._today", "2099-01-01"):
                ba._reset_if_new_day()
                await record_gateway_spend("ws-1", 51.0)
            assert 50 in ba._fired["ws-1"]  # fired again on the new day

    async def test_recipient_fallback_and_notifier_error_swallowed(self):
        from core.llm.gateway.budget_alerts import record_gateway_spend

        # Recipient only gates the NOTIFICATION — crossed thresholds are still
        # returned and recorded (fire-once state is independent of delivery).
        with patch("core.llm.gateway.budget_alerts.GATEWAY_BUDGET_ALERTS_ENABLED", True), \
             patch("core.llm.gateway.budget_alerts.resolve_budget_limit", return_value=10.0), \
             patch("core.llm.gateway.budget_alerts._resolve_recipient_id", return_value=None):
            assert await record_gateway_spend("ws-1", 6.0) == [50]  # 60% crossed 50%

        notifier = AsyncMock(side_effect=RuntimeError("notify failed"))
        with patch("core.llm.gateway.budget_alerts.GATEWAY_BUDGET_ALERTS_ENABLED", True), \
             patch("core.llm.gateway.budget_alerts.resolve_budget_limit", return_value=10.0), \
             patch("core.llm.gateway.budget_alerts._resolve_recipient_id", return_value="u-a"), \
             patch("core.llm.gateway.budget_alerts.NotificationService", return_value=notifier):
            crossed = await record_gateway_spend("ws-2", 6.0)
            assert crossed == [50]

    def test_sync_shim(self):
        from core.llm.gateway.budget_alerts import run_budget_alert_sync

        with patch("core.llm.gateway.budget_alerts.GATEWAY_BUDGET_ALERTS_ENABLED", False):
            assert run_budget_alert_sync("ws-1", 5.0) == []

    def test_resolve_budget_limit_fallback(self):
        from core.llm.gateway.budget_alerts import resolve_budget_limit

        with patch(
            "core.personal_budget_service.personal_budget_service",
            SimpleNamespace(_get_budget_limit=lambda: None),
        ):
            assert resolve_budget_limit("ws-1") == 100.0
        with patch(
            "core.personal_budget_service.personal_budget_service",
            SimpleNamespace(_get_budget_limit=lambda: 250.0),
        ):
            assert resolve_budget_limit("ws-1") == 250.0

    def test_resolve_recipient_preference_order(self):
        from core.llm.gateway.budget_alerts import _resolve_recipient_id

        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            SimpleNamespace(id="u-pref"),
            SimpleNamespace(id="u-admin"),
        ]
        with patch("core.database.SessionLocal", return_value=db):
            assert _resolve_recipient_id("u-pref") == "u-pref"
        db.query.return_value.filter.return_value.first.side_effect = [None, None]
        with patch("core.database.SessionLocal", return_value=db):
            assert _resolve_recipient_id("u-ghost") is None
        db.query.side_effect = RuntimeError("db down")
        with patch("core.database.SessionLocal", return_value=db):
            assert _resolve_recipient_id() is None


# =========================================================================== #
# gateway auth coverage
# =========================================================================== #
class TestGatewayAuth:
    @pytest.fixture(autouse=True)
    def _clean_rates(self):
        _rate_limit_state.clear()
        yield
        _rate_limit_state.clear()

    def test_to_audit_with_and_without_key(self):
        assert _identity().to_audit()["api_key_id"] == "key-1"
        i = _identity(api_key_id=None, auth_method="jwt")
        assert i.to_audit()["api_key_id"] == ""

    def test_extract_secret_paths(self):
        from core.llm.gateway.auth import _extract_secret

        def req(headers):
            raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
            return Request({
                "type": "http", "method": "POST", "path": "/v1/chat/completions",
                "headers": raw, "query_string": b"", "client": ("1.2.3.4", 1),
                "server": ("localhost", 8000), "scheme": "http",
            })

        assert _extract_secret(req({"x-api-key": "  atom_sk_abc  "})) == "atom_sk_abc"
        assert _extract_secret(req({"Authorization": "Bearer tok.ey.jwt"})) == "tok.ey.jwt"
        assert _extract_secret(req({"Authorization": "basic abc"})) is None
        assert _extract_secret(req({})) is None

    async def test_get_gateway_identity_bearer_atom_sk(self, worker_database):
        from core.llm.gateway.auth import get_gateway_identity

        session = worker_database()
        user = User(id="u-1", email="u@t.com", first_name="A", last_name="B", role="user", status="active")
        session.add(user)
        session.commit()
        key = GatewayApiKey(
            id="k-1", key_hash=hash_api_key(_KEY), key_prefix="atom_sk_abcd",
            name="t", user_id="u-1", is_active=True, rate_limit_per_minute=10,
        )
        session.add(key)
        session.commit()
        raw = [(b"authorization", b"Bearer " + _KEY.encode())]
        req = Request({
            "type": "http", "method": "POST", "path": "/v1/chat/completions",
            "headers": raw, "query_string": b"", "client": ("1.2.3.4", 1),
            "server": ("localhost", 8000), "scheme": "http",
        })
        identity = await get_gateway_identity(req, session)
        assert identity.auth_method == "api_key"
        assert identity.user_id == "u-1"
        assert identity.rate_limit_per_minute == 10
        session.close()

    async def test_get_gateway_identity_jwt_path(self):
        from core.llm.gateway.auth import get_gateway_identity

        fake_user = SimpleNamespace(id="u-jwt", tenant_id="t-9")
        with patch("core.auth.get_current_user", new=AsyncMock(return_value=fake_user)):
            raw = [(b"authorization", b"Bearer aaa.bbb.ccc")]
            req = Request({
                "type": "http", "method": "POST", "path": "/v1/chat/completions",
                "headers": raw, "query_string": b"", "client": ("1.2.3.4", 1),
                "server": ("localhost", 8000), "scheme": "http",
            })
            identity = await get_gateway_identity(req, MagicMock())
        assert identity.auth_method == "jwt"
        assert identity.user_id == "u-jwt"

    async def test_get_gateway_identity_invalid_and_missing(self):
        from core.llm.gateway.auth import get_gateway_identity

        raw = [(b"x-api-key", b"not-a-key-format")]
        req = Request({
            "type": "http", "method": "POST", "path": "/v1/chat/completions",
            "headers": raw, "query_string": b"", "client": ("1.2.3.4", 1),
            "server": ("localhost", 8000), "scheme": "http",
        })
        with pytest.raises(Exception) as exc:
            await get_gateway_identity(req, MagicMock())
        assert exc.value.status_code == 401
        empty_req = Request({
            "type": "http", "method": "POST", "path": "/v1/chat/completions",
            "headers": [], "query_string": b"", "client": ("1.2.3.4", 1),
            "server": ("localhost", 8000), "scheme": "http",
        })
        with pytest.raises(Exception) as exc2:
            await get_gateway_identity(empty_req, MagicMock())
        assert exc2.value.status_code == 401
        assert "Missing" in str(exc2.value.detail)

    def test_rate_limit_zero_disables(self):
        from core.llm.gateway.auth import _check_rate_limit

        _check_rate_limit("h1", 0)
        assert _check_rate_limit("h1", -5) is None

    def test_rate_limit_window_purges_old(self):
        from core.llm.gateway.auth import _check_rate_limit, _rate_limit_state

        for _ in range(3):
            _check_rate_limit("h2", 3)
        with pytest.raises(Exception) as exc:
            _check_rate_limit("h2", 3)
        assert exc.value.status_code == 429
        _rate_limit_state["h2"][0] -= 61  # age the first entry
        _check_rate_limit("h2", 3)  # purged -> allowed
        assert len(_rate_limit_state["h2"]) == 3

    def test_rate_limit_eviction_purges_dead_keys(self):
        from core.llm.gateway.auth import _check_rate_limit, _rate_limit_state

        for i in range(1001):
            _rate_limit_state[f"dead-{i}"] = []
        _check_rate_limit("alive", 60)
        assert len(_rate_limit_state) < 1001
        assert all(not k.startswith("dead-") for k in _rate_limit_state)


# =========================================================================== #
# gateway_service coverage
# =========================================================================== #
class TestGatewayServiceRouting:
    async def test_forced_tier_routes_via_ranked(self):
        handler = _fake_handler()
        service = _service_harness(handler)
        provider, model = await service._resolve_route(_MSGS, None, {"x-atom-tier": "heavy"})
        assert handler.get_ranked_providers.await_args.kwargs["cognitive_tier"] is not None
        assert provider == "openai"

    async def test_forced_tier_no_options_falls_back(self):
        handler = _fake_handler()
        handler.get_ranked_providers.return_value = []
        handler.byok_manager = SimpleNamespace(
            providers={"openai": SimpleNamespace(model="custom-1")}
        )
        service = _service_harness(handler)
        provider, model = await service._resolve_route(_MSGS, None, {"x-atom-tier": "micro"})
        assert provider == "openai"
        assert model == "custom-1"

    async def test_forced_model_header_wins_over_body(self):
        handler = _fake_handler()
        service = _service_harness(handler)
        provider, model = await service._resolve_route(_MSGS, "gpt-4o", {"x-atom-model": "deepseek-chat"})
        assert model == "deepseek-chat"

    async def test_body_model_honored(self):
        handler = _fake_handler()
        service = _service_harness(handler)
        provider, model = await service._resolve_route(_MSGS, "gpt-4o")
        assert model == "gpt-4o"

    async def test_auto_routes_via_bpc(self):
        handler = _fake_handler()
        service = _service_harness(handler)
        provider, model = await service._resolve_route(_MSGS, "auto")
        assert provider == "openai"
        assert model == "gpt-4o-mini"

    async def test_routing_raises_when_no_providers(self):
        handler = _fake_handler()
        handler.get_ranked_providers.return_value = []
        handler.async_clients = {}
        handler.clients = {}
        service = _service_harness(handler)
        with pytest.raises(NoProvidersConfiguredError):
            await service._resolve_route(_MSGS, None)

    def test_optimal_raises_without_providers(self):
        handler = _fake_handler()
        handler.get_optimal_provider.side_effect = NoProvidersConfiguredError("none")
        service = _service_harness(handler)
        with pytest.raises(NoProvidersConfiguredError):
            service._optimal()

    def test_optimal_exception_falls_back(self):
        handler = _fake_handler()
        handler.get_optimal_provider.side_effect = RuntimeError("boom")
        service = _service_harness(handler)
        provider, model = service._optimal()
        assert provider == "openai"
        assert model == "gpt-4o-mini"

    def test_resolve_provider_for_model(self):
        handler = _fake_handler()
        handler._provider_serves_model.side_effect = lambda pid, m: pid == "anthropic"
        service = _service_harness(handler)
        assert service._resolve_provider_for_model("openai", "claude-x") == ("anthropic", "claude-x")
        handler._provider_serves_model.side_effect = None
        handler._provider_serves_model.return_value = False
        assert service._resolve_provider_for_model("openai", "claude-x") == ("openai", "claude-x")

    def test_list_models_from_registry(self):
        handler = _fake_handler()
        service = _service_harness(handler)
        with patch(
            "core.llm.registry.queries.get_models_for_provider",
            side_effect=lambda db, pid: ["gpt-4o", "gpt-4o-mini"] if pid == "openai" else ["claude-3"],
        ):
            out = service.list_models()
        ids = [m["id"] for m in out["data"]]
        assert ids == ["gpt-4o", "gpt-4o-mini", "claude-3"]

    def test_list_models_registry_error_falls_back_to_cfg(self):
        handler = _fake_handler()
        handler.byok_manager = SimpleNamespace(
            providers={"openai": SimpleNamespace(model="gpt-4o-cfg")}
        )
        service = _service_harness(handler)
        with patch(
            "core.llm.registry.queries.get_models_for_provider",
            side_effect=RuntimeError("registry down"),
        ):
            out = service.list_models()
        assert out["data"][0]["id"] == "gpt-4o-cfg"

    def test_list_models_empty_falls_back_to_provider_ids(self):
        handler = _fake_handler()
        handler.byok_manager = SimpleNamespace(providers={"openai": SimpleNamespace(model=None)})
        service = _service_harness(handler)
        with patch(
            "core.llm.registry.queries.get_models_for_provider",
            side_effect=lambda db, pid: [],
        ):
            out = service.list_models()
        assert [m["id"] for m in out["data"]] == ["openai", "anthropic"]

    def test_models_for_provider_no_cfg(self):
        handler = _fake_handler()
        service = _service_harness(handler)
        with patch("core.llm.registry.queries.get_models_for_provider", return_value=[]):
            assert service._models_for_provider("unknown") == []

    def test_map_gateway_error_branches(self):
        service = _service_harness(_fake_handler())
        no_providers = NoProvidersConfiguredError("nope")
        blocked = GatewayBlockedError("budget_exceeded", "Budget exceeded")
        all_failed = AllProvidersFailedError("boom")

        body = service.map_gateway_error(no_providers)
        assert body["_status"] == 503
        assert body["error"]["recovery_url"] == "/settings/ai"
        assert service.map_gateway_error(blocked)["_status"] == 429
        assert service.map_gateway_error(blocked)["error"]["code"] == "budget_exceeded"
        assert service.map_gateway_error(all_failed)["_status"] == 502

        from fastapi import HTTPException

        assert service.map_gateway_error(HTTPException(403, "forbidden"))["_status"] == 403
        assert service.map_gateway_error(ValueError("bad"))["_status"] == 400
        assert service.map_gateway_error(RuntimeError("internal"))["_status"] == 500
        assert service.map_gateway_error(RuntimeError("internal"))["error"]["message"] == "Internal server error."

    def test_map_gateway_error_anthropic_shape(self):
        service = _service_harness(_fake_handler())
        body = service.map_gateway_error(NoProvidersConfiguredError("nope"), anthropic=True)
        assert body["error"]["type"] == "overloaded_error"
        assert body["_status"] == 503

    def test_error_body_openai_and_anthropic(self):
        service = _service_harness(_fake_handler())
        openai_body = service._error_body(503, "msg", "code", recovery_url="/settings")
        assert openai_body["error"]["type"] == "server_error"
        assert openai_body["error"]["recovery_url"] == "/settings"
        anth = service._error_body(400, "msg", "code", anthropic=True)
        assert anth["error"]["type"] == "invalid_request_error"

    def test_parse_tier(self):
        from core.llm.gateway.gateway_service import _parse_tier

        assert _parse_tier("HEAVY") is not None
        assert _parse_tier("nonsense") is None

    def test_master_switch_helpers(self):
        from core.llm.gateway.gateway_service import (
            get_gateway_enabled,
            require_gateway_enabled,
        )
        from core.llm.gateway import gateway_service as gs

        # gateway_enabled() resolves live (env > runtime-settings DB row);
        # patch the function, not the import-time module constant.
        with patch("core.llm.gateway.gateway_service.gateway_enabled", return_value=False):
            assert get_gateway_enabled() is False
            with pytest.raises(Exception) as exc:
                require_gateway_enabled()
            assert exc.value.status_code == 404
        assert get_gateway_enabled() is True  # restored -> no raise
        require_gateway_enabled()

    def test_gateway_init_builds_handler(self):
        handler = _fake_handler()
        with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler) as mock_cls:
            service = GatewayService(_identity(), MagicMock())
        # BYOKHandler is a plain (sync) constructor call — `await_count` is
        # not meaningful on a MagicMock (it auto-creates child attributes).
        mock_cls.assert_called_once_with(
            workspace_id="ws-1", tenant_id="t-1", db_session=service.db, user_id="u-1"
        )
        assert service.handler is handler


class TestGatewayInitMap:
    def test_map_gateway_error_module_level(self):
        from core.llm.gateway import map_gateway_error

        body = map_gateway_error(NoProvidersConfiguredError("none"))
        assert body["_status"] == 503
        assert body["error"]["recovery_url"] == "/settings/ai"
        anth = map_gateway_error(GatewayBlockedError("r", "m"), anthropic=True)
        assert anth["error"]["type"] == "rate_limit_error"
        assert map_gateway_error(ValueError("x"))["_status"] == 400
        assert map_gateway_error(RuntimeError("x"))["_status"] == 500
        from fastapi import HTTPException

        assert map_gateway_error(HTTPException(418, "teapot"))["_status"] == 418
        assert map_gateway_error(AllProvidersFailedError("x"))["_status"] == 502
        assert map_gateway_error(AllProvidersFailedError("x"))["error"]["message"] == (
            "All LLM providers failed. Please try again."
        )


# =========================================================================== #
# provider_rate_limits coverage
# =========================================================================== #
class TestProviderRateTracker:
    def make_tracker(self):
        tracker = ProviderRateTracker(window_seconds=60)
        tracker.set_rate_limits("opencode-go", rpm=10, tpm=1000, max_context=200000)
        return tracker

    def test_env_int(self):
        from core.llm.provider_rate_limits import _env_int

        assert _env_int("OPENCODE_RPM", 60) >= 0
        with patch.dict("os.environ", {"OPENCODE_RPM": "42"}):
            assert _env_int("OPENCODE_RPM", 60) == 42
        with patch.dict("os.environ", {"OPENCODE_RPM": "not-an-int"}):
            assert _env_int("OPENCODE_RPM", 60) == 60

    def test_default_registry_has_opencode_and_openrouter(self):
        from core.llm.provider_rate_limits import PROVIDER_RATE_LIMITS

        assert "opencode-go" in PROVIDER_RATE_LIMITS
        assert "openrouter" in PROVIDER_RATE_LIMITS
        assert PROVIDER_RATE_LIMITS["opencode-go"]["rpm"] > 0

    def test_get_set_rate_limits(self):
        tracker = self.make_tracker()
        assert tracker.get_rate_limits("opencode-go")["rpm"] == 10
        tracker.set_rate_limits("opencode-go", rpm=5)
        assert tracker.get_rate_limits("opencode-go")["rpm"] == 5
        tracker.set_rate_limits("brand-new", tpm=99)
        assert tracker.get_rate_limits("brand-new") == {"tpm": 99}
        assert tracker.get_rate_limits("never-configured") == {}

    def test_record_usage_skips_without_limits(self):
        tracker = ProviderRateTracker()
        tracker.record_usage("unlimited-provider", 100, 50, "m1")  # no crash
        assert tracker._usage == {}

    def test_record_usage_tracks_weighted(self):
        tracker = self.make_tracker()
        registry = SimpleNamespace(
            get_weight=lambda p, m: 2.0,
            get_model_rate_limits=lambda p, m: {},
        )
        tracker._model_registry = registry
        tracker.record_usage("opencode-go", 10, 5, "flash-model")
        requests, tokens = tracker._window_totals("opencode-go", weighted=True)
        assert requests == 1
        assert tokens == 30.0  # (10+5) * weight 2.0
        unweighted_req, unweighted_tok = tracker._window_totals("opencode-go", weighted=False)
        assert unweighted_tok == 15.0

    def test_window_totals_legacy_3tuples(self):
        tracker = self.make_tracker()
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        tracker._usage["opencode-go"] = __import__("collections").deque([
            (now, 10, 5),
            (now, 1, 1, "model-a"),
        ])
        requests, tokens = tracker._window_totals("opencode-go", weighted=False)
        assert requests == 2
        assert tokens == 17.0
        # per-model filter ignores legacy entries
        mreq, mtok = tracker._window_totals("opencode-go", model_id="model-a", weighted=False)
        assert mreq == 1
        assert mtok == 2.0

    def test_trim_drops_expired(self):
        tracker = self.make_tracker()
        from datetime import datetime, timedelta, timezone

        old = datetime.now(timezone.utc) - timedelta(seconds=120)
        tracker._usage["opencode-go"] = __import__("collections").deque([(old, 1, 1)])
        tracker._trim("opencode-go")
        assert not tracker._usage["opencode-go"]

    def test_headroom_math(self):
        from core.llm.provider_rate_limits import ProviderRateTracker

        assert ProviderRateTracker._headroom_from(0, 0, 100, 1000) == 1.0
        assert ProviderRateTracker._headroom_from(50, 0, 100, 1000) == 0.5
        assert ProviderRateTracker._headroom_from(0, 500, 100, 1000) == 0.5
        assert ProviderRateTracker._headroom_from(50, 500, 100, 1000) == 0.5
        assert ProviderRateTracker._headroom_from(200, 0, 100, 1000) == 0.0
        assert ProviderRateTracker._headroom_from(0, 0, 0, 0) == 1.0
        assert ProviderRateTracker._headroom_from(0, 0, 0, 500) == 1.0

    def test_get_headroom(self):
        tracker = self.make_tracker()
        assert tracker.get_headroom("unlimited") == 1.0
        tracker.record_usage("opencode-go", 5, 5, "m")
        assert 0.0 < tracker.get_headroom("opencode-go") < 1.0
        for _ in range(20):
            tracker.record_usage("opencode-go", 5, 5, "m")
        assert tracker.get_headroom("opencode-go") == 0.0

    def test_model_headroom_fallbacks(self):
        tracker = self.make_tracker()
        assert tracker.get_model_headroom("opencode-go", None) == tracker.get_headroom("opencode-go")
        # no model limits -> provider headroom
        registry = SimpleNamespace(
            get_weight=lambda p, m: 1.0,
            get_model_rate_limits=lambda p, m: {},
        )
        tracker._model_registry = registry
        assert tracker.get_model_headroom("opencode-go", "m1") == tracker.get_headroom("opencode-go")
        # model limits present -> per-model math
        registry.get_model_rate_limits = lambda p, m: {"rpm": 1, "tpm": 100}
        tracker.record_usage("opencode-go", 5, 5, "m1")
        assert tracker.get_model_headroom("opencode-go", "m1") == 0.0

    def test_model_limits_registry_unavailable(self):
        tracker = ProviderRateTracker()
        tracker._model_registry = None
        with patch(
            "core.llm.opencode_model_limits.get_opencode_model_limits",
            side_effect=RuntimeError("no registry"),
        ):
            assert tracker.get_model_rate_limits("p", "m") == {}
            assert tracker.get_model_weight("p", "m") == 1.0
        with patch(
            "core.llm.opencode_model_limits.get_opencode_model_limits",
            return_value=SimpleNamespace(set_model_limits=MagicMock()),
        ):
            tracker.set_model_limits("p", "m", weight=3.0, rpm=5, tpm=500)
        registry = SimpleNamespace(
            get_weight=lambda p, m: 4.0,
            get_model_rate_limits=lambda p, m: {"rpm": 2},
            set_model_limits=MagicMock(),
        )
        tracker._model_registry = registry
        assert tracker.get_model_rate_limits("p", "m") == {"rpm": 2}
        assert tracker.get_model_weight("p", "m") == 4.0
        tracker.set_model_limits("p", "m", rpm=9)
        registry.set_model_limits.assert_called_once_with("p", "m", weight=None, rpm=9, tpm=None)

    def test_get_max_context(self):
        tracker = self.make_tracker()
        assert tracker.get_max_context("opencode-go") == 200000
        tracker.set_rate_limits("opencode-go", max_context=0)
        assert tracker.get_max_context("opencode-go") is None
        assert tracker.get_max_context("unlimited") is None

    def test_monthly_usage(self):
        tracker = self.make_tracker()
        assert tracker.get_monthly_usage("opencode-go") is None
        persistence = MagicMock()
        persistence.monthly_usage.return_value = {"tpm": 100}
        tracker._persistence = persistence
        assert tracker.get_monthly_usage("opencode-go") == {"tpm": 100}
        persistence.monthly_usage.return_value = None
        assert tracker.get_monthly_usage("opencode-go") is None
        persistence.monthly_usage.side_effect = RuntimeError("boom")
        assert tracker.get_monthly_usage("opencode-go") is None

    def test_persistence_wired_in_record_usage(self):
        tracker = self.make_tracker()
        persistence = MagicMock()
        persistence.record = MagicMock(side_effect=RuntimeError("persist down"))
        tracker._persistence = persistence
        tracker.record_usage("opencode-go", 1, 2, "m")  # non-fatal
        persistence.record.assert_called_once()

    def test_usage_summary_with_models_and_monthly(self):
        tracker = self.make_tracker()
        tracker._model_registry = SimpleNamespace(
            get_weight=lambda p, m: 1.0,
            get_model_rate_limits=lambda p, m: {},
        )
        tracker._persistence = MagicMock()
        tracker._persistence.monthly_usage.return_value = {"tpm": 500}
        tracker.record_usage("opencode-go", 4, 6, "model-a")
        summary = tracker.usage_summary("opencode-go")
        assert summary["requests_in_window"] == 1
        assert summary["tokens_in_window"] == 10.0
        assert "model-a" in summary["models"]
        assert summary["monthly"] == {"tpm": 500}
        assert summary["headroom"] > 0

    def test_singleton_creation(self):
        from core.llm.provider_rate_limits import (
            _rate_tracker,
            _singleton_lock,
            get_provider_rate_tracker,
        )

        old = _rate_tracker
        try:
            _rate_tracker = None
            with patch(
                "core.llm.rate_usage_persistence.get_rate_usage_persistence",
                side_effect=RuntimeError("no persistence"),
            ):
                tracker = get_provider_rate_tracker()
            assert isinstance(tracker, ProviderRateTracker)
            assert get_provider_rate_tracker() is tracker  # singleton
        finally:
            _rate_tracker = old
        assert _singleton_lock is not None


# =========================================================================== #
# gateway key routes (real DB)
# =========================================================================== #
class TestGatewayKeyRoutes:
    @pytest.fixture
    def db(self, worker_database):
        session = worker_database()
        session.query(GatewayApiKey).delete()
        session.query(User).delete()
        session.commit()
        yield session
        session.close()

    def _app_client(self, db, auth=True):
        from api.gateway_key_routes import router as key_router

        app = FastAPI()
        app.include_router(key_router)
        app.dependency_overrides[get_db] = lambda: db

        async def _current_user():
            return User(
                id="u-1", email="u@t.com", first_name="A", last_name="B",
                role="user", status="active", tenant_id="t-1",
            )

        from core.auth import get_current_user

        if auth:
            app.dependency_overrides[get_current_user] = _current_user
        return TestClient(app, raise_server_exceptions=False)

    def test_create_key_returns_plaintext_once_and_stores_hash(self, db):
        client = self._app_client(db)
        r = client.post("/api/gateway/keys", json={"name": "my-key"})
        assert r.status_code == 201
        body = r.json()
        assert body["key"].startswith("atom_sk_")
        assert body["key_prefix"].startswith("atom_sk_")
        row = db.query(GatewayApiKey).filter(GatewayApiKey.id == body["id"]).first()
        assert row is not None
        assert row.key_hash == hash_api_key(body["key"])
        assert row.key_hash != body["key"]
        assert row.user_id == "u-1"

    def test_create_key_validation(self, db):
        client = self._app_client(db)
        assert client.post("/api/gateway/keys", json={"rate_limit_per_minute": 0}).status_code == 422
        assert client.post("/api/gateway/keys", json={"rate_limit_per_minute": 99999}).status_code == 422

    def test_list_keys(self, db):
        client = self._app_client(db)
        client.post("/api/gateway/keys", json={"name": "k1"})
        client.post("/api/gateway/keys", json={"name": "k2"})
        r = client.get("/api/gateway/keys")
        assert r.status_code == 200
        assert len(r.json()["data"]) == 2
        assert all(k["key_prefix"].startswith("atom_sk_") for k in r.json()["data"])
        assert all("key_hash" not in k for k in r.json()["data"])

    def test_revoke_key(self, db):
        client = self._app_client(db)
        key_id = client.post("/api/gateway/keys", json={}).json()["id"]
        r = client.delete(f"/api/gateway/keys/{key_id}")
        assert r.status_code == 200
        row = db.query(GatewayApiKey).filter(GatewayApiKey.id == key_id).first()
        assert row.is_active is False
        assert row.revoked_at is not None

    def test_revoke_other_users_key_404(self, db):
        client = self._app_client(db)
        assert client.delete("/api/gateway/keys/not-mine").status_code == 404

    def test_rotate_key_revokes_old_and_issues_new(self, db):
        client = self._app_client(db)
        key_id = client.post("/api/gateway/keys", json={"name": "orig"}).json()["id"]
        r = client.post(f"/api/gateway/keys/{key_id}/rotate")
        assert r.status_code == 200
        body = r.json()
        assert body["key"].startswith("atom_sk_")
        assert body["id"] != key_id
        old = db.query(GatewayApiKey).filter(GatewayApiKey.id == key_id).first()
        assert old.is_active is False
        new = db.query(GatewayApiKey).filter(GatewayApiKey.id == body["id"]).first()
        assert new.name == "orig"
        assert new.rate_limit_per_minute == old.rate_limit_per_minute

    def test_rotate_missing_key_404(self, db):
        client = self._app_client(db)
        assert client.post("/api/gateway/keys/ghost/rotate").status_code == 404

    def test_requires_auth(self, db):
        client = self._app_client(db, auth=False)
        assert client.get("/api/gateway/keys").status_code == 401
        assert client.post("/api/gateway/keys", json={}).status_code == 401


# =========================================================================== #
# gateway log routes (real DB)
# =========================================================================== #
class TestGatewayLogRoutes:
    @pytest.fixture
    def db(self, worker_database):
        session = worker_database()
        session.query(GatewayRequestLog).delete()
        session.commit()
        yield session
        session.close()

    def _client(self, db, user_id="u-1"):
        from api.gateway_log_routes import router as log_router

        app = FastAPI()
        app.include_router(log_router)
        app.dependency_overrides[get_db] = lambda: db

        async def _current_user():
            return SimpleNamespace(id=user_id)

        from core.auth import get_current_user

        app.dependency_overrides[get_current_user] = _current_user
        return TestClient(app, raise_server_exceptions=False)

    def _seed(self, db, user_id, model):
        return log_gateway_request(
            db, _identity(user_id=user_id), provider="openai", model=model,
            status_code=200, request_body={"messages": []},
        )

    def test_list_owner_scoped_and_paginated(self, db):
        client = self._client(db)
        self._seed(db, "u-1", "gpt-4o")
        self._seed(db, "u-1", "gpt-4o-mini")
        self._seed(db, "u-2", "claude-3")
        r = client.get("/api/v1/gateway/logs")
        assert r.status_code == 200
        assert len(r.json()["data"]) == 2
        assert all(x["model"] != "claude-3" for x in r.json()["data"])
        r2 = client.get("/api/v1/gateway/logs", params={"limit": 1})
        assert len(r2.json()["data"]) == 1
        assert client.get("/api/v1/gateway/logs", params={"limit": 500}).status_code == 422

    def test_get_log_owner_scoped(self, db):
        client = self._client(db)
        log_id = self._seed(db, "u-1", "gpt-4o")
        r = client.get(f"/api/v1/gateway/logs/{log_id}")
        assert r.status_code == 200
        assert r.json()["data"]["model"] == "gpt-4o"
        other = self._seed(db, "u-2", "claude-3")
        assert client.get(f"/api/v1/gateway/logs/{other}").status_code == 404
        assert client.get("/api/v1/gateway/logs/nope").status_code == 404

    def test_requires_auth(self, db):
        from api.gateway_log_routes import router as log_router

        app = FastAPI()
        app.include_router(log_router)
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        assert client.get("/api/v1/gateway/logs").status_code == 401


# =========================================================================== #
# openai_gateway_routes coverage
# =========================================================================== #
class TestOpenAIRoutesCoverage:
    def test_success_route_and_body_forwarded(self):
        db = make_db(make_key_row(_KEY))
        client = make_client(db)
        handler = _fake_handler()
        with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler):
            r = client.post(
                "/v1/chat/completions", headers=_KEY_HEADERS,
                json={"messages": _MSGS, "stop": ["STOP"], "top_p": 0.3, "user": "u-x", "max_tokens": 50},
            )
        assert r.status_code == 200
        call = handler.chat_completion.await_args
        assert call.kwargs["max_tokens"] == 50
        assert call.kwargs["extra_kwargs"] == {"stop": ["STOP"], "top_p": 0.3, "user": "u-x"}

    def test_gateway_blocked_429(self):
        db = make_db(make_key_row(_KEY))
        client = make_client(db)
        handler = _fake_handler(
            chat_completion=AsyncMock(side_effect=GatewayBlockedError("budget_exceeded", "Budget exceeded"))
        )
        with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler), \
             patch("core.llm.gateway.gateway_service.GatewayService._resolve_route",
                   return_value=("openai", "gpt-4o")), \
             patch("api.openai_gateway_routes.record_gateway_spend", AsyncMock()):
            r = client.post("/v1/chat/completions", headers=_KEY_HEADERS, json={"messages": _MSGS})
        assert r.status_code == 429
        assert r.json()["error"]["code"] == "budget_exceeded"

    def test_value_error_400(self):
        db = make_db(make_key_row(_KEY))
        client = make_client(db)
        handler = _fake_handler(
            chat_completion=AsyncMock(side_effect=ValueError("bad request"))
        )
        with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler), \
             patch("core.llm.gateway.gateway_service.GatewayService._resolve_route",
                   return_value=("openai", "gpt-4o")):
            r = client.post("/v1/chat/completions", headers=_KEY_HEADERS, json={"messages": _MSGS})
        assert r.status_code == 400

    def test_stream_error_delta_and_exception_paths(self):
        db = make_db(make_key_row(_KEY))
        client = make_client(db)

        async def _err_gen():
            yield "before"
            yield "\n\n[Error: provider blew up]"

        handler = _fake_handler(stream_completion=_err_gen)
        with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler), \
             patch("api.openai_gateway_routes.record_gateway_spend", AsyncMock()):
            r = client.post(
                "/v1/chat/completions", headers=_KEY_HEADERS,
                json={"messages": _MSGS, "stream": True},
            )
        assert r.status_code == 200
        assert "data: [DONE]" in r.text

        async def _boom_gen():
            raise RuntimeError("stream exploded")
            yield "unreachable"  # pragma: no cover

        handler2 = _fake_handler(stream_completion=_boom_gen)
        with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler2), \
             patch("api.openai_gateway_routes.record_gateway_spend", AsyncMock()):
            r2 = client.post(
                "/v1/chat/completions", headers=_KEY_HEADERS,
                json={"messages": _MSGS, "stream": True},
            )
        assert r2.status_code == 200
        assert "data: [DONE]" in r2.text

    def test_models_endpoint(self):
        db = make_db(make_key_row(_KEY))
        client = make_client(db)
        handler = _fake_handler()
        handler.byok_manager = SimpleNamespace(providers={})
        with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler), \
             patch("core.llm.registry.queries.get_models_for_provider",
                   side_effect=lambda db, pid: [f"{pid}-model"]):
            r = client.get("/v1/models", headers=_KEY_HEADERS)
        assert r.status_code == 200
        ids = [m["id"] for m in r.json()["data"]]
        assert "openai-model" in ids


class TestAnthropicRoutesCoverage:
    def test_success_translated_response(self):
        db = make_db(make_key_row(_KEY))
        client = make_client(db)
        handler = _fake_handler()
        with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler):
            r = client.post(
                "/v1/messages",
                headers={**_KEY_HEADERS, "anthropic-version": "2023-06-01"},
                json={
                    "model": "claude-3-5-sonnet-20240620", "max_tokens": 200,
                    "system": "be nice", "messages": _MSGS, "stop_sequences": ["END"],
                },
            )
        assert r.status_code == 200
        body = r.json()
        assert body["type"] == "message"
        assert body["content"] == [{"type": "text", "text": "hi"}]
        assert body["usage"]["input_tokens"] == 1
        call = handler.chat_completion.await_args
        assert call.kwargs["max_tokens"] == 200
        assert call.kwargs["extra_kwargs"] == {"stop": ["END"]}

    def test_gateway_blocked_429_anthropic(self):
        db = make_db(make_key_row(_KEY))
        client = make_client(db)
        handler = _fake_handler(
            chat_completion=AsyncMock(side_effect=GatewayBlockedError("budget_exceeded", "Budget exceeded"))
        )
        with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler), \
             patch("core.llm.gateway.gateway_service.GatewayService._resolve_route",
                   return_value=("openai", "gpt-4o")):
            r = client.post(
                "/v1/messages",
                headers={**_KEY_HEADERS, "anthropic-version": "2023-06-01"},
                json={"messages": _MSGS, "max_tokens": 10},
            )
        assert r.status_code == 429
        assert r.json()["error"]["type"] == "rate_limit_error"

    def test_stream_shapes(self):
        db = make_db(make_key_row(_KEY))
        client = make_client(db)
        handler = _fake_handler()

        def _fake_stream(*args, **kwargs):
            async def _gen():
                yield "Hello"
                yield " world"

            return _gen()

        handler.stream_completion = _fake_stream
        with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler), \
             patch("api.openai_gateway_routes.record_gateway_spend", AsyncMock()):
            r = client.post(
                "/v1/messages",
                headers={**_KEY_HEADERS, "anthropic-version": "2023-06-01"},
                json={"messages": _MSGS, "max_tokens": 10, "stream": True},
            )
        assert r.status_code == 200
        assert "message_start" in r.text
        assert "content_block_start" in r.text
        assert "Hello" in r.text
        assert "message_stop" in r.text

    def test_stream_error_paths(self):
        db = make_db(make_key_row(_KEY))
        client = make_client(db)

        async def _err_gen():
            yield "\n\n[Error: nope]"

        handler = _fake_handler(stream_completion=_err_gen)
        with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler), \
             patch("api.openai_gateway_routes.record_gateway_spend", AsyncMock()):
            r = client.post(
                "/v1/messages",
                headers={**_KEY_HEADERS, "anthropic-version": "2023-06-01"},
                json={"messages": _MSGS, "max_tokens": 10, "stream": True},
            )
        assert r.status_code == 200
        assert "stop_reason\": \"error\"" in r.text or "error" in r.text

        async def _boom_gen():
            raise RuntimeError("boom")
            yield "x"  # pragma: no cover

        handler2 = _fake_handler(stream_completion=_boom_gen)
        with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler2), \
             patch("api.openai_gateway_routes.record_gateway_spend", AsyncMock()):
            r2 = client.post(
                "/v1/messages",
                headers={**_KEY_HEADERS, "anthropic-version": "2023-06-01"},
                json={"messages": _MSGS, "max_tokens": 10, "stream": True},
            )
        assert r2.status_code == 200
        assert "message_stop" in r2.text


class TestGatewayMasterSwitch:
    def test_disabled_returns_404(self):
        import api.openai_gateway_routes as routes

        db = make_db(make_key_row(_KEY))
        client = make_client(db)
        with patch.object(routes, "require_gateway_enabled",
                          side_effect=Exception("Gateway disabled")):
            from fastapi import HTTPException

            with patch.object(routes, "require_gateway_enabled",
                              side_effect=HTTPException(404, "Gateway disabled")):
                r = client.post("/v1/chat/completions", headers=_KEY_HEADERS, json={"messages": _MSGS})
                assert r.status_code == 404
                r2 = client.get("/v1/models", headers=_KEY_HEADERS)
                assert r2.status_code == 404
