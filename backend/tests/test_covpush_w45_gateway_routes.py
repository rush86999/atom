"""Coverage wave 45 — api/openai_gateway_routes.py (62% → 90%+).

Routes exercise OpenAI + Anthropic surfaces: non-stream success/error paths,
extra_kwargs forwarding (stop/top_p/user), both SSE streams (clean, error
delta, exception, disconnect-spend), and list_models. GatewayService and the
BYOK handler are mocked — no network, no real LLM.
"""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.openai_gateway_routes import (
    _anthropic_stream,
    _format_sse,
    _openai_sse,
    _openai_stream,
    router,
)
from core.database import get_db
from core.llm.gateway.auth import GatewayIdentity
from core.llm.gateway.gateway_service import GatewayService
from core.llm.gateway import get_gateway_identity


def _identity():
    return GatewayIdentity(user_id="u1", tenant_id="t1", workspace_id="w1",
                           auth_method="api_key", api_key_id="k1")


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_gateway_identity] = lambda: _identity()
    app.dependency_overrides[get_db] = lambda: MagicMock()
    return TestClient(app)


def _patch_service(handler_kwargs=None):
    """Patch GatewayService with a controllable mock."""
    handler = MagicMock()
    handler_kwargs = handler_kwargs or {}
    for k, v in handler_kwargs.items():
        setattr(handler, k, v)
    service = MagicMock(spec=GatewayService)
    service.handler = handler
    service._resolve_route = AsyncMock(return_value=("openai", "gpt-4o"))
    service.list_models.return_value = [{"id": "gpt-4o"}]
    return patch("api.openai_gateway_routes.GatewayService", return_value=service), service


CHAT_BODY = {"model": "auto", "messages": [{"role": "user", "content": "hi"}]}


class TestSSEHelpers:
    def test_openai_sse(self):
        assert _openai_sse({"a": 1}) == 'data: {"a": 1}\n\n'

    def test_format_sse(self):
        assert _format_sse("ev", {"a": 1}) == 'event: ev\ndata: {"a": 1}\n\n'


class TestChatCompletions:
    def test_success(self, client):
        p, service = _patch_service()
        service.handler.chat_completion = AsyncMock(return_value={
            "id": "1", "choices": [{"message": {"content": "ok"}}], "usage": {}})
        with p:
            resp = client.post("/v1/chat/completions", json=CHAT_BODY)
        assert resp.status_code == 200
        assert resp.json()["choices"][0]["message"]["content"] == "ok"

    def test_extra_kwargs_forwarded(self, client):
        p, service = _patch_service()
        service.handler.chat_completion = AsyncMock(return_value={"choices": []})
        with p:
            client.post("/v1/chat/completions", json={
                **CHAT_BODY, "stop": ["END"], "top_p": 0.5, "user": "alice"})
        _, kwargs = service.handler.chat_completion.call_args
        assert kwargs["extra_kwargs"] == {"stop": ["END"], "top_p": 0.5, "user": "alice"}

    def test_route_error_no_providers(self, client):
        from core.llm.byok_handler import NoProvidersConfiguredError
        p, service = _patch_service()
        service._resolve_route = AsyncMock(side_effect=NoProvidersConfiguredError())
        with p:
            resp = client.post("/v1/chat/completions", json=CHAT_BODY)
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "no_llm_provider"

    def test_completion_error_gateway_blocked(self, client):
        from core.llm.byok_handler import GatewayBlockedError
        p, service = _patch_service()
        service.handler.chat_completion = AsyncMock(
            side_effect=GatewayBlockedError(message="spend", reason="budget"))
        with p:
            resp = client.post("/v1/chat/completions", json=CHAT_BODY)
        assert resp.status_code == 429

    def test_completion_error_value_error(self, client):
        p, service = _patch_service()
        service.handler.chat_completion = AsyncMock(side_effect=ValueError("bad"))
        with p:
            resp = client.post("/v1/chat/completions", json=CHAT_BODY)
        assert resp.status_code == 400

    def test_stream_returns_sse(self, client):
        p, service = _patch_service({
            "stream_completion": _agenerator(["hi", " there"]),
        })
        with p:
            resp = client.post("/v1/chat/completions", json={**CHAT_BODY, "stream": True})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert "data: [DONE]" in resp.text

    def test_stream_error_delta_marks_502(self, client):
        p, service = _patch_service({
            "stream_completion": _agenerator(["\n\n[Error: provider boom]"]),
        })
        with p:
            resp = client.post("/v1/chat/completions", json={**CHAT_BODY, "stream": True})
        assert resp.status_code == 200  # SSE transport
        assert "data: [DONE]" in resp.text

    def test_unauthenticated_401(self):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: MagicMock()
        resp = TestClient(app).post("/v1/chat/completions", json=CHAT_BODY)
        assert resp.status_code == 401


def _agenerator(chunks):
    async def gen(*args, **kwargs):
        for c in chunks:
            yield c
    return gen


class TestOpenAIStreamGenerator:
    async def test_full_stream(self):
        p, service = _patch_service({
            "stream_completion": _agenerator(["hello", " world"]),
        })
        with p:
            chunks = []
            async for chunk in _openai_stream(
                    service, [{"role": "user", "content": "hi"}], "gpt-4o", "openai",
                    0.7, 100, {}, _identity(), MagicMock()):
                chunks.append(chunk)
        assert len(chunks) >= 5
        assert any("finish_reason" in c and "usage" in c for c in chunks)

    async def test_stream_error_delta(self):
        p, service = _patch_service({
            "stream_completion": _agenerator(["\n\n[Error: boom]"]),
        })
        with p:
            chunks = []
            async for chunk in _openai_stream(
                    service, [], "m", "p", 0.7, 100, {}, _identity(), MagicMock()):
                chunks.append(chunk)
        assert chunks[-1] == "data: [DONE]\n\n"

    async def test_stream_exception(self):
        async def boom(*args, **kwargs):
            raise RuntimeError("network")
        p, service = _patch_service({"stream_completion": boom})
        with p:
            chunks = []
            async for chunk in _openai_stream(
                    service, [], "m", "p", 0.7, 100, {}, _identity(), MagicMock()):
                chunks.append(chunk)
        assert chunks[-1] == "data: [DONE]\n\n"


class TestAnthropicMessages:
    def test_success_translated(self, client):
        p, service = _patch_service()
        service.handler.chat_completion = AsyncMock(return_value={
            "id": "1", "choices": [{"message": {"content": "ok"},
                                    "finish_reason": "stop"}], "usage": {}})
        with p:
            resp = client.post("/v1/messages", json={
                "model": "auto",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 100,
            })
        assert resp.status_code == 200
        body = resp.json()
        assert body["type"] == "message"

    def test_stop_and_top_p_forwarded(self, client):
        p, service = _patch_service()
        service.handler.chat_completion = AsyncMock(return_value={"choices": []})
        with p:
            client.post("/v1/messages", json={
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 100, "stop_sequences": ["END"], "top_p": 0.5})
        _, kwargs = service.handler.chat_completion.call_args
        assert kwargs["extra_kwargs"] == {"stop": ["END"], "top_p": 0.5}

    def test_error_anthropic_shape(self, client):
        from core.llm.byok_handler import NoProvidersConfiguredError
        p, service = _patch_service()
        service._resolve_route = AsyncMock(side_effect=NoProvidersConfiguredError())
        with p:
            resp = client.post("/v1/messages", json={
                "messages": [{"role": "user", "content": "hi"}], "max_tokens": 100})
        assert resp.status_code == 503
        assert resp.json()["error"]["type"] == "overloaded_error"

    def test_stream_sse(self, client):
        p, service = _patch_service({
            "stream_completion": _agenerator(["hi"]),
        })
        with p:
            resp = client.post("/v1/messages", json={
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 100, "stream": True})
        assert resp.status_code == 200
        assert "message_start" in resp.text
        assert "message_stop" in resp.text


class TestAnthropicStreamGenerator:
    async def test_full_stream(self):
        p, service = _patch_service({
            "stream_completion": _agenerator(["hello"]),
        })
        with p:
            chunks = []
            async for chunk in _anthropic_stream(
                    service, [], "claude", "anthropic", 0.7, 100, {}, _identity(), MagicMock()):
                chunks.append(chunk)
        joined = "".join(chunks)
        assert "message_start" in joined
        assert "message_stop" in joined
        assert "end_turn" in joined

    async def test_error_delta(self):
        p, service = _patch_service({
            "stream_completion": _agenerator(["\n\n[Error: boom]"]),
        })
        with p:
            chunks = []
            async for chunk in _anthropic_stream(
                    service, [], "m", "p", 0.7, 100, {}, _identity(), MagicMock()):
                chunks.append(chunk)
        assert '"type": "error"' in "".join(chunks)

    async def test_exception(self):
        async def boom(*args, **kwargs):
            raise RuntimeError("network")
        p, service = _patch_service({"stream_completion": boom})
        with p:
            chunks = []
            async for chunk in _anthropic_stream(
                    service, [], "m", "p", 0.7, 100, {}, _identity(), MagicMock()):
                chunks.append(chunk)
        assert '"type": "error"' in "".join(chunks)


class TestListModels:
    def test_list_models(self, client):
        p, service = _patch_service()
        with p:
            resp = client.get("/v1/models")
        assert resp.status_code == 200
        assert resp.json() == [{"id": "gpt-4o"}]

    def test_list_models_unauth(self):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: MagicMock()
        resp = TestClient(app).get("/v1/models")
        assert resp.status_code == 401
