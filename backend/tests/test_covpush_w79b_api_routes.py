# -*- coding: utf-8 -*-
"""Coverage wave 79b — api/openai_gateway_routes.py (LLM gateway, 100%).

Split from tests/test_covpush_w79a_api_routes.py (>300 tests in one file).

No LLM spend, no network, no real DB: FastAPI TestClient + dependency_overrides
+ mocked GatewayService/BYOK handler (REAL module names, no `backend.` prefix).
401 tests run the real auth dependency chain (no token -> 401).
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from core.database import get_db


def _app(router):
    app = FastAPI()
    app.include_router(router)
    return app


def await_coroutine(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def collect_asyncgen(agen):
    async def _inner():
        out = []
        async for item in agen:
            out.append(item)
        return out

    return await_coroutine(_inner())


class TestOpenAIGatewayRoutes:
    def _identity(self):
        from core.llm.gateway.auth import GatewayIdentity
        return GatewayIdentity(user_id="u1", tenant_id="t1", workspace_id="w1",
                               auth_method="api_key", api_key_id="k1")

    def _client(self):
        from api.openai_gateway_routes import router
        from core.llm.gateway import get_gateway_identity

        app = _app(router)
        app.dependency_overrides[get_gateway_identity] = lambda: self._identity()
        app.dependency_overrides[get_db] = lambda: MagicMock()
        return TestClient(app, raise_server_exceptions=False)

    @pytest.fixture()
    def client(self):
        return self._client()

    def _patch_service(self, handler_kwargs=None):
        from core.llm.gateway.gateway_service import GatewayService

        handler = MagicMock()
        for k, v in (handler_kwargs or {}).items():
            setattr(handler, k, v)
        service = MagicMock(spec=GatewayService)
        service.handler = handler
        service._resolve_route = AsyncMock(return_value=("openai", "gpt-4o"))
        service.list_models.return_value = [{"id": "gpt-4o"}, {"id": "deepseek"}]
        return patch("api.openai_gateway_routes.GatewayService", return_value=service), service

    CHAT_BODY = {"model": "auto", "messages": [{"role": "user", "content": "hi"}]}

    def _agenerator(self, chunks, exc=None):
        async def gen(*args, **kwargs):
            for c in chunks:
                yield c
            if exc is not None:
                raise exc

        return gen

    # ---------------- auth / gateway gate ----------------
    def test_unauth_401(self):
        from api.openai_gateway_routes import router
        app = _app(router)
        app.dependency_overrides[get_db] = lambda: MagicMock()
        assert TestClient(app).post("/v1/chat/completions",
                                    json=self.CHAT_BODY).status_code == 401

    def test_gateway_disabled_503(self):
        from api import openai_gateway_routes as routes
        with patch.object(routes, "require_gateway_enabled",
                          side_effect=HTTPException(status_code=503, detail="gateway disabled")):
            r = self._client().post("/v1/chat/completions", json=self.CHAT_BODY)
        assert r.status_code == 503

    # ---------------- SSE helpers ----------------
    def test_openai_sse_and_format_sse(self):
        from api.openai_gateway_routes import _format_sse, _openai_sse
        assert _openai_sse({"a": 1}) == 'data: {"a": 1}\n\n'
        assert _format_sse("ev", {"a": 1}) == 'event: ev\ndata: {"a": 1}\n\n'

    # ---------------- chat completions ----------------
    def test_chat_completions_success(self, client):
        p, service = self._patch_service()
        service.handler.chat_completion = AsyncMock(return_value={
            "id": "1", "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1}})
        with p:
            r = client.post("/v1/chat/completions", json=self.CHAT_BODY)
        assert r.status_code == 200
        assert r.json()["choices"][0]["message"]["content"] == "ok"

    def test_chat_completions_default_max_tokens(self, client):
        from core.llm.gateway.gateway_service import DEFAULT_MAX_TOKENS
        p, service = self._patch_service()
        service.handler.chat_completion = AsyncMock(return_value={"choices": []})
        with p:
            client.post("/v1/chat/completions", json=self.CHAT_BODY)
        assert service.handler.chat_completion.call_args.kwargs["max_tokens"] == DEFAULT_MAX_TOKENS

    def test_chat_completions_extra_kwargs(self, client):
        p, service = self._patch_service()
        service.handler.chat_completion = AsyncMock(return_value={"choices": []})
        with p:
            client.post("/v1/chat/completions", json={
                **self.CHAT_BODY, "stop": ["END"], "top_p": 0.5, "user": "alice",
                "max_tokens": 42})
        kwargs = service.handler.chat_completion.call_args.kwargs
        assert kwargs["extra_kwargs"] == {"stop": ["END"], "top_p": 0.5, "user": "alice"}
        assert kwargs["max_tokens"] == 42

    def test_chat_completions_empty_messages_422(self, client):
        r = client.post("/v1/chat/completions", json={"model": "auto", "messages": []})
        assert r.status_code == 422

    def test_chat_completions_route_no_providers_503(self, client):
        from core.llm.byok_handler import NoProvidersConfiguredError
        p, service = self._patch_service()
        service._resolve_route = AsyncMock(side_effect=NoProvidersConfiguredError())
        with p:
            r = client.post("/v1/chat/completions", json=self.CHAT_BODY)
        assert r.status_code == 503
        assert r.json()["error"]["code"] == "no_llm_provider"

    def test_chat_completions_route_value_error_400(self, client):
        p, service = self._patch_service()
        service._resolve_route = AsyncMock(side_effect=ValueError("bad model"))
        with p:
            r = client.post("/v1/chat/completions", json=self.CHAT_BODY)
        assert r.status_code == 400

    def test_chat_completions_gateway_blocked_429(self, client):
        from core.llm.byok_handler import GatewayBlockedError
        p, service = self._patch_service()
        service.handler.chat_completion = AsyncMock(
            side_effect=GatewayBlockedError(message="spend", reason="budget"))
        with p:
            r = client.post("/v1/chat/completions", json=self.CHAT_BODY)
        assert r.status_code == 429

    def test_chat_completions_all_providers_failed_502(self, client):
        from core.llm.byok_handler import AllProvidersFailedError
        p, service = self._patch_service()
        service.handler.chat_completion = AsyncMock(
            side_effect=AllProvidersFailedError("all down"))
        with p:
            r = client.post("/v1/chat/completions", json=self.CHAT_BODY)
        assert r.status_code == 502

    def test_chat_completions_value_error_400(self, client):
        p, service = self._patch_service()
        service.handler.chat_completion = AsyncMock(side_effect=ValueError("bad"))
        with p:
            r = client.post("/v1/chat/completions", json=self.CHAT_BODY)
        assert r.status_code == 400

    def test_chat_completions_stream_sse(self, client):
        p, service = self._patch_service({
            "stream_completion": self._agenerator(["hi", " there"]),
        })
        with p:
            r = client.post("/v1/chat/completions", json={**self.CHAT_BODY, "stream": True})
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        assert "data: [DONE]" in r.text
        assert "usage" in r.text

    def test_chat_completions_stream_error_delta(self, client):
        p, service = self._patch_service({
            "stream_completion": self._agenerator(["\n\n[Error: provider boom]"]),
        })
        with p:
            r = client.post("/v1/chat/completions", json={**self.CHAT_BODY, "stream": True})
        assert "data: [DONE]" in r.text

    # ---------------- _openai_stream direct ----------------
    def test_openai_stream_clean(self):
        from api.openai_gateway_routes import _openai_stream
        p, service = self._patch_service({
            "stream_completion": self._agenerator(["a", "b"]),
        })
        with p:
            chunks = collect_asyncgen(_openai_stream(
                service, self.CHAT_BODY["messages"], "gpt-4o", "openai",
                0.7, 100, {}, self._identity(), MagicMock()))
        assert any("finish_reason\": \"stop" in c for c in chunks)
        assert chunks[-1] == "data: [DONE]\n\n"

    def test_openai_stream_exception_yields_error_chunk(self):
        from api.openai_gateway_routes import _openai_stream
        p, service = self._patch_service({
            "stream_completion": self._agenerator([], exc=RuntimeError("stream broke")),
        })
        with p:
            chunks = collect_asyncgen(_openai_stream(
                service, self.CHAT_BODY["messages"], "gpt-4o", "openai",
                0.7, 100, {}, self._identity(), MagicMock()))
        assert chunks[-1] == "data: [DONE]\n\n"

    # ---------------- anthropic ----------------
    def _anthropic_body(self, **over):
        body = {
            "model": "auto",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 512,
        }
        body.update(over)
        return body

    def test_anthropic_success(self, client):
        p, service = self._patch_service()
        service.handler.chat_completion = AsyncMock(return_value={
            "id": "1", "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3}})
        with p:
            r = client.post("/v1/messages", json=self._anthropic_body())
        assert r.status_code == 200
        assert r.json()["content"] is not None

    def test_anthropic_extra_kwargs_stop_top_p(self, client):
        p, service = self._patch_service()
        service.handler.chat_completion = AsyncMock(return_value={"choices": []})
        with p:
            client.post("/v1/messages", json=self._anthropic_body(
                stop_sequences=["END"], top_p=0.9))
        kwargs = service.handler.chat_completion.call_args.kwargs
        assert kwargs["extra_kwargs"] == {"stop": ["END"], "top_p": 0.9}

    def test_anthropic_route_no_providers_503(self, client):
        from core.llm.byok_handler import NoProvidersConfiguredError
        p, service = self._patch_service()
        service._resolve_route = AsyncMock(side_effect=NoProvidersConfiguredError())
        with p:
            r = client.post("/v1/messages", json=self._anthropic_body())
        assert r.status_code == 503

    def test_anthropic_gateway_blocked_429(self, client):
        from core.llm.byok_handler import GatewayBlockedError
        p, service = self._patch_service()
        service.handler.chat_completion = AsyncMock(
            side_effect=GatewayBlockedError(message="spend", reason="budget"))
        with p:
            r = client.post("/v1/messages", json=self._anthropic_body())
        assert r.status_code == 429

    def test_anthropic_value_error_400(self, client):
        p, service = self._patch_service()
        service.handler.chat_completion = AsyncMock(side_effect=ValueError("bad"))
        with p:
            r = client.post("/v1/messages", json=self._anthropic_body())
        assert r.status_code == 400

    def test_anthropic_empty_messages_422(self, client):
        r = client.post("/v1/messages", json={"messages": [], "max_tokens": 100})
        assert r.status_code == 422

    def test_anthropic_stream_sse(self, client):
        p, service = self._patch_service({
            "stream_completion": self._agenerator(["hello", " world"]),
        })
        with p:
            r = client.post("/v1/messages", json=self._anthropic_body(stream=True))
        assert r.status_code == 200
        assert "message_start" in r.text
        assert "message_stop" in r.text

    def test_anthropic_stream_error_delta(self, client):
        p, service = self._patch_service({
            "stream_completion": self._agenerator(["\n\n[Error: boom]"]),
        })
        with p:
            r = client.post("/v1/messages", json=self._anthropic_body(stream=True))
        assert 'type": "error"' in r.text

    # ---------------- _anthropic_stream direct ----------------
    def test_anthropic_stream_clean(self):
        from api.openai_gateway_routes import _anthropic_stream
        p, service = self._patch_service({
            "stream_completion": self._agenerator(["a", "b"]),
        })
        with p:
            chunks = collect_asyncgen(_anthropic_stream(
                service, self._anthropic_body()["messages"], "claude", "anthropic",
                0.7, 100, {}, self._identity(), MagicMock()))
        assert any('"stop_reason": "end_turn"' in c for c in chunks)
        assert chunks[-1] == 'event: message_stop\ndata: {"type": "message_stop"}\n\n'

    def test_anthropic_stream_exception(self):
        from api.openai_gateway_routes import _anthropic_stream
        p, service = self._patch_service({
            "stream_completion": self._agenerator([], exc=RuntimeError("boom")),
        })
        with p:
            chunks = collect_asyncgen(_anthropic_stream(
                service, self._anthropic_body()["messages"], "claude", "anthropic",
                0.7, 100, {}, self._identity(), MagicMock()))
        assert chunks[-1] == 'event: error\ndata: {"type": "error", "error": {"type": "api_error", "message": "Stream failed"}}\n\n'

    # ---------------- models ----------------
    def test_list_models(self, client):
        p, service = self._patch_service()
        with p:
            r = client.get("/v1/models")
        assert r.status_code == 200
        assert r.json()[0]["id"] == "gpt-4o"
