"""Bughunt — LLM gateway (core/llm/gateway + api/openai_gateway_routes +
api/gateway_key_routes).

TDD red-green targets:
- B1: explicit ``model`` in the request body is ignored by
  ``GatewayService._resolve_route`` — the ``model`` argument is never
  consulted, so every request auto-routes regardless of the requested model.
- B2: ``ATOM_GATEWAY_DEFAULT_MAX_TOKENS`` (DEFAULT_MAX_TOKENS) is defined but
  dead — both routes hardcode 1000 instead of honoring the env value.
- B3: empty ``messages`` arrays are accepted and forwarded to the provider
  instead of being rejected as invalid.
- B4: gateway audit gaps — routing failures (503/400 at route resolution) are
  never logged to ``GatewayRequestLog``, and completion-failure rows record
  status 400 even when the client receives 502/503.
"""
import hashlib
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.database import get_db
from core.llm.byok_handler import AllProvidersFailedError, NoProvidersConfiguredError
from core.llm.gateway.auth import GatewayIdentity
from core.llm.gateway.gateway_service import GatewayService
from core.models import GatewayApiKey


# --------------------------------------------------------------------------- #
# Helpers (mirrors test_round70_gateway.py conventions)
# --------------------------------------------------------------------------- #
def make_key_row(plaintext="atom_sk_0123456789abcdef", **overrides):
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


def make_client(db):
    from api.openai_gateway_routes import router as gateway_router_mod

    app = FastAPI()
    app.include_router(gateway_router_mod)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def _identity():
    return GatewayIdentity(
        user_id="u-1",
        tenant_id="t-1",
        workspace_id="ws-1",
        auth_method="api_key",
        api_key_id="key-1",
    )


def _fake_handler(**overrides):
    handler = MagicMock()
    handler.analyze_query_complexity.return_value = "simple"
    handler.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")
    handler.get_ranked_providers.return_value = [("openai", "gpt-4o-mini")]
    handler._provider_serves_model.return_value = False
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
    for k, v in overrides.items():
        setattr(handler, k, v)
    return handler


def _service_harness(handler):
    with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler):
        return GatewayService(_identity(), MagicMock())


_KEY = "atom_sk_0123456789abcdef"
_KEY_HEADERS = {"x-api-key": _KEY}
_MSGS = [{"role": "user", "content": "hi"}]


# --------------------------------------------------------------------------- #
# B1: explicit model in the request body must be honored.
# --------------------------------------------------------------------------- #
class TestExplicitBodyModel:
    async def test_resolve_route_forces_body_model(self):
        service = _service_harness(_fake_handler())
        provider, model = await service._resolve_route(_MSGS, "gpt-4o")
        assert provider == "openai"
        assert model == "gpt-4o"

    async def test_resolve_route_reroutes_to_provider_serving_model(self):
        handler = _fake_handler()
        handler._provider_serves_model.side_effect = lambda pid, m: pid == "anthropic"
        service = _service_harness(handler)
        provider, model = await service._resolve_route(_MSGS, "claude-3-5-sonnet-20240620")
        assert provider == "anthropic"
        assert model == "claude-3-5-sonnet-20240620"

    async def test_resolve_route_header_override_still_wins(self):
        service = _service_harness(_fake_handler())
        provider, model = await service._resolve_route(_MSGS, "gpt-4o", {"x-atom-model": "deepseek-chat"})
        assert model == "deepseek-chat"

    async def test_resolve_route_auto_model_still_auto_routes(self):
        service = _service_harness(_fake_handler())
        provider, model = await service._resolve_route(_MSGS, "auto")
        assert provider == "openai"
        assert model == "gpt-4o-mini"

    def test_openai_route_forwards_requested_model_to_handler(self):
        db = make_db(make_key_row(_KEY))
        client = make_client(db)
        handler = _fake_handler()
        with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler):
            r = client.post(
                "/v1/chat/completions",
                headers=_KEY_HEADERS,
                json={"model": "gpt-4o", "messages": _MSGS},
            )
        assert r.status_code == 200
        assert handler.chat_completion.await_args.args[1] == "gpt-4o"
        assert r.json()["model"] == "gpt-4o"

    def test_anthropic_route_forwards_requested_model_to_handler(self):
        db = make_db(make_key_row(_KEY))
        client = make_client(db)
        handler = _fake_handler(
            chat_completion=AsyncMock(
                return_value={
                    "model": "claude-3-5-sonnet-20240620",
                    "choices": [{"message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                }
            )
        )
        with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler):
            r = client.post(
                "/v1/messages",
                headers={**_KEY_HEADERS, "anthropic-version": "2023-06-01"},
                json={"model": "claude-3-5-sonnet-20240620", "max_tokens": 100, "messages": _MSGS},
            )
        assert r.status_code == 200
        assert handler.chat_completion.await_args.args[1] == "claude-3-5-sonnet-20240620"
        assert r.json()["model"] == "claude-3-5-sonnet-20240620"


# --------------------------------------------------------------------------- #
# B2: ATOM_GATEWAY_DEFAULT_MAX_TOKENS must be honored, not hardcoded 1000.
# --------------------------------------------------------------------------- #
class TestDefaultMaxTokens:
    def test_openai_route_uses_default_max_tokens_env(self):
        import api.openai_gateway_routes as routes

        client = make_client(make_db(make_key_row(_KEY)))
        handler = _fake_handler()
        # The routes module resolves defaults via default_max_tokens() (env /
        # runtime-settings driven) — patch the function, not a constant.
        old = routes.default_max_tokens
        routes.default_max_tokens = lambda: 7777
        try:
            with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler):
                r = client.post(
                    "/v1/chat/completions", headers=_KEY_HEADERS, json={"messages": _MSGS}
                )
        finally:
            routes.default_max_tokens = old
        assert r.status_code == 200
        assert handler.chat_completion.await_args.kwargs["max_tokens"] == 7777

    def test_anthropic_route_uses_default_max_tokens_env(self):
        import api.openai_gateway_routes as routes

        client = make_client(make_db(make_key_row(_KEY)))
        handler = _fake_handler()
        # The /v1/messages body model binds default_max_tokens as a pydantic
        # default_factory at class-definition time, so the env seam is the
        # contract here (B2): ATOM_GATEWAY_DEFAULT_MAX_TOKENS must be honored.
        with patch.dict(os.environ, {"ATOM_GATEWAY_DEFAULT_MAX_TOKENS": "4242"}):
            with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler):
                r = client.post(
                    "/v1/messages",
                    headers={**_KEY_HEADERS, "anthropic-version": "2023-06-01"},
                    json={"messages": _MSGS},
                )
        assert r.status_code == 200
        assert handler.chat_completion.await_args.kwargs["max_tokens"] == 4242


# --------------------------------------------------------------------------- #
# B3: empty messages arrays are invalid.
# --------------------------------------------------------------------------- #
class TestEmptyMessages:
    def test_openai_empty_messages_rejected(self):
        client = make_client(make_db(make_key_row(_KEY)))
        with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=_fake_handler()):
            r = client.post(
                "/v1/chat/completions", headers=_KEY_HEADERS,
                json={"model": "gpt-4o", "messages": []},
            )
        assert r.status_code == 422

    def test_anthropic_empty_messages_rejected(self):
        client = make_client(make_db(make_key_row(_KEY)))
        with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=_fake_handler()):
            r = client.post(
                "/v1/messages",
                headers={**_KEY_HEADERS, "anthropic-version": "2023-06-01"},
                json={"model": "claude-sonnet", "max_tokens": 100, "messages": []},
            )
        assert r.status_code == 422


# --------------------------------------------------------------------------- #
# B4: audit completeness + correct error statuses in GatewayRequestLog.
# --------------------------------------------------------------------------- #
class TestAuditStatusAccuracy:
    def test_openai_routing_503_is_audit_logged_with_503(self):
        client = make_client(make_db(make_key_row(_KEY)))
        log_mock = MagicMock(return_value="log-id")
        with patch.object(GatewayService, "_resolve_route", side_effect=NoProvidersConfiguredError()), \
             patch("api.openai_gateway_routes.log_gateway_request", log_mock), \
             patch("api.openai_gateway_routes.record_gateway_spend", AsyncMock()):
            r = client.post(
                "/v1/chat/completions", headers=_KEY_HEADERS, json={"messages": _MSGS}
            )
        assert r.status_code == 503
        assert log_mock.called
        assert log_mock.call_args.kwargs["status_code"] == 503

    def test_anthropic_routing_503_is_audit_logged_with_503(self):
        client = make_client(make_db(make_key_row(_KEY)))
        log_mock = MagicMock(return_value="log-id")
        with patch.object(GatewayService, "_resolve_route", side_effect=NoProvidersConfiguredError()), \
             patch("api.openai_gateway_routes.log_gateway_request", log_mock), \
             patch("api.openai_gateway_routes.record_gateway_spend", AsyncMock()):
            r = client.post(
                "/v1/messages",
                headers={**_KEY_HEADERS, "anthropic-version": "2023-06-01"},
                json={"messages": _MSGS},
            )
        assert r.status_code == 503
        assert log_mock.called
        assert log_mock.call_args.kwargs["status_code"] == 503

    def test_openai_completion_502_is_audit_logged_with_502_not_400(self):
        client = make_client(make_db(make_key_row(_KEY)))
        handler = _fake_handler(
            chat_completion=AsyncMock(side_effect=AllProvidersFailedError("boom"))
        )
        log_mock = MagicMock(return_value="log-id")
        with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler), \
             patch.object(GatewayService, "_resolve_route", return_value=("openai", "gpt-4o")), \
             patch("api.openai_gateway_routes.log_gateway_request", log_mock), \
             patch("api.openai_gateway_routes.record_gateway_spend", AsyncMock()):
            r = client.post(
                "/v1/chat/completions", headers=_KEY_HEADERS, json={"messages": _MSGS}
            )
        assert r.status_code == 502
        assert log_mock.called
        assert log_mock.call_args.kwargs["status_code"] == 502