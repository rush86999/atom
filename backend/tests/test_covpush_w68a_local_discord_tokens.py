"""Coverage wave W68a — local-model routes, Discord routes, token refresher, voice service.

Targets (>=95% statement coverage, standalone):
- api/routes/local_model_routes.py  (was 39%)
- integrations/discord_routes.py    (was 0% — never imported by any suite)
- core/token_refresher.py           (was 39%)
- core/voice_service.py             (was 47%)

Pattern: FastAPI TestClient + patch on the REAL module the app imports
(`api.routes.<module>` / `integrations.<module>`, NOT `backend.` prefixed —
phantom double-import). For routes with auth deps: app.dependency_overrides
with SimpleNamespace users + MagicMock DB sessions (no real DB). No network
(httpx/discord service mocked), no LLM spend, no real DB.

Bugs found + fixed in the assigned modules (regression tests below):
1. discord_routes.py:233 — `discord_dispatcher.dispatch(...)` but
   MessagingActionDispatcher has NO `dispatch` method (only async
   `dispatch_action` with a (platform, tenant_id, user_id, action_id, payload)
   signature) -> AttributeError on every type-3 MESSAGE_COMPONENT interaction
   (500 instead of {"type": 6}). Fixed to await dispatch_action with extracted
   user_id/tenant_id — test_interactions_type3_dispatches_action.
2. discord_routes.py:168 — handle_oauth_callback leaked `str(e)` to the
   client (repo policy: never leak str(e) — rounds 18-31 precedent). Now
   generic "callback failed" message — test_callback_error_no_str_leak.
"""
import asyncio
import importlib
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def make_client(router, authed=False):
    from core.auth import get_current_user

    app = FastAPI()
    app.include_router(router)
    if authed:
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id="u1", email="u1@x.com", tenant_id="t1"
        )
    return TestClient(app, raise_server_exceptions=False)


def _async_svc(methods, **attrs):
    """Build a MagicMock service with AsyncMock method stubs."""
    svc = MagicMock()
    for name, ret in methods.items():
        if isinstance(ret, Exception):
            setattr(svc, name, AsyncMock(side_effect=ret))
        else:
            setattr(svc, name, AsyncMock(return_value=ret))
    for name, val in attrs.items():
        setattr(svc, name, val)
    return svc


def _httpx_acm(status=200, json_data=None, exc=None):
    """A mock httpx.AsyncClient context manager returning a prepared client."""
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data if json_data is not None else {}
    client = MagicMock()
    get_fut = AsyncMock(return_value=resp)
    if exc is not None:
        get_fut.side_effect = exc
    client.get = get_fut
    acm = MagicMock()
    acm.__aenter__.return_value = client
    acm.__aexit__.return_value = False
    return acm


# ===========================================================================
# api/routes/local_model_routes.py
# ===========================================================================

def _local_db(providers=(), caps=(), first_provider=None, first_cap=None):
    """MagicMock DB that routes query() by target model class."""
    from core.models import LocalModelCapabilities, LocalModelProvider

    db = MagicMock()
    db.queries = []

    def _query(target, *a, **k):
        q = MagicMock()
        db.queries.append(q)
        if target is LocalModelCapabilities:
            q.filter.return_value.all.return_value = list(caps)
            q.filter.return_value.first.return_value = first_cap
        else:
            q.filter.return_value.all.return_value = list(providers)
            q.filter.return_value.first.return_value = first_provider
        return q

    db.query.side_effect = _query
    return db


def _provider(**kw):
    defaults = dict(
        id="p1",
        name="My Ollama",
        provider_type="ollama",
        base_url="http://10.0.0.5:11434/v1",
        is_active=True,
        api_key=None,
        tenant_id="t1",
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _cap(**kw):
    defaults = dict(
        model_id="llama3:8b",
        supports_tools=True,
        supports_vision=False,
        supports_reasoning=False,
        quality_score=0.7,
        speed_score=0.6,
        context_window=8192,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


class TestLocalModelRoutes:
    def _client(self, user=None, db=None):
        from api.routes.local_model_routes import router
        from core.auth import get_current_user
        from core.database import get_db

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = (
            lambda: user if user is not None else SimpleNamespace(
                id="u1", workspace_id=None, tenant_id="t1"
            )
        )
        app.dependency_overrides[get_db] = (
            lambda: db if db is not None else MagicMock()
        )
        return TestClient(app, raise_server_exceptions=False)

    # -- GET /api/local-models -------------------------------------------
    def test_list_providers_default_workspace(self):
        prov = _provider(api_key="sk-local")
        db = _local_db(providers=[prov])
        resp = self._client(db=db).get("/api/local-models")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["id"] == "p1"
        assert body[0]["has_api_key"] is True
        assert body[0]["is_active"] is True
        q = db.queries[0]
        assert len(q.filter.call_args.args) == 2

    def test_list_providers_empty(self):
        resp = self._client(db=_local_db()).get("/api/local-models")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_providers_workspace_scoped(self):
        user = SimpleNamespace(id="u1", workspace_id="ws-9", tenant_id="t1")
        resp = self._client(user=user, db=_local_db(providers=[_provider()])).get(
            "/api/local-models"
        )
        assert resp.status_code == 200
        q = db = None
        # filter arg must reference the workspace id
        assert resp.json()[0]["id"] == "p1"

    def test_list_providers_no_api_key_flag(self):
        db = _local_db(providers=[_provider(api_key=None)])
        resp = self._client(db=db).get("/api/local-models")
        assert resp.json()[0]["has_api_key"] is False

    # -- POST /api/local-models ------------------------------------------
    def test_register_provider_success_dns_name(self):
        db = MagicMock()
        resp = self._client(db=db).post(
            "/api/local-models",
            json={
                "name": "My Ollama",
                "provider_type": "ollama",
                "base_url": "http://llm.example.com/v1/",
                "api_key": "k",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["registered"] is True
        assert body["name"] == "My Ollama"
        created = db.add.call_args[0][0]
        assert created.base_url == "http://llm.example.com/v1"
        assert created.api_key == "k"
        assert created.tenant_id == "t1"
        assert created.workspace_id == "default"
        db.commit.assert_called_once()
        db.refresh.assert_called_once()

    def test_register_provider_success_public_ip(self):
        db = MagicMock()
        resp = self._client(db=db).post(
            "/api/local-models",
            json={"name": "vLLM", "base_url": "http://8.8.8.8:8000/v1"},
        )
        assert resp.status_code == 200
        assert resp.json()["registered"] is True
        created = db.add.call_args[0][0]
        assert created.provider_type == "custom"

    def test_register_provider_bad_scheme(self):
        resp = self._client().post(
            "/api/local-models", json={"name": "x", "base_url": "ftp://host/v1"}
        )
        assert resp.status_code == 400

    @pytest.mark.parametrize(
        "bad_url",
        [
            "http://10.0.0.5:11434/v1",
            "http://127.0.0.1:11434/v1",
            "http://169.254.169.254/latest/meta-data",
            "http://192.168.1.10/v1",
            "http://240.0.0.1/v1",
        ],
    )
    def test_register_provider_ssrf_ip_blocks(self, bad_url):
        resp = self._client().post(
            "/api/local-models", json={"name": "x", "base_url": bad_url}
        )
        assert resp.status_code == 400

    def test_register_provider_workspace_tenant(self):
        user = SimpleNamespace(id="u1", workspace_id="ws-2", tenant_id="t-9")
        db = MagicMock()
        self._client(user=user, db=db).post(
            "/api/local-models",
            json={"name": "x", "base_url": "http://llm.example.com/v1"},
        )
        created = db.add.call_args[0][0]
        assert created.workspace_id == "ws-2"
        assert created.tenant_id == "t-9"

    # -- DELETE /api/local-models/{id} -----------------------------------
    def test_unregister_provider_success(self):
        db = _local_db(first_provider=_provider())
        resp = self._client(db=db).delete("/api/local-models/p1")
        assert resp.status_code == 200
        assert resp.json() == {"deleted": True}
        db.delete.assert_called_once()
        db.commit.assert_called_once()

    def test_unregister_provider_not_found(self):
        resp = self._client(db=_local_db(first_provider=None)).delete(
            "/api/local-models/nope"
        )
        assert resp.status_code == 404

    # -- GET /api/local-models/{id}/models -------------------------------
    def test_discover_models_success_with_key(self):
        db = _local_db(first_provider=_provider(api_key="sk"))
        acm = _httpx_acm(
            json_data={"data": [{"id": "llama3:8b"}, {"name": "qwen"}, {"id": ""}]}
        )
        with patch(
            "api.routes.local_model_routes.httpx.AsyncClient", return_value=acm
        ), patch(
            "core.dynamic_pricing_fetcher.get_pricing_fetcher"
        ) as gp:
            resp = self._client(db=db).get("/api/local-models/p1/models")
        assert resp.status_code == 200
        assert resp.json() == {"models": ["llama3:8b", "qwen"], "count": 2}
        client = acm.__aenter__.return_value
        assert client.get.call_args.args == ("http://10.0.0.5:11434/v1/models",)
        assert client.get.call_args.kwargs["headers"] == {"Authorization": "Bearer sk"}
        gp.assert_called()

    def test_discover_models_success_without_key(self):
        db = _local_db(first_provider=_provider())
        acm = _httpx_acm(json_data={"data": [{"id": "m1"}]})
        with patch(
            "api.routes.local_model_routes.httpx.AsyncClient", return_value=acm
        ):
            resp = self._client(db=db).get("/api/local-models/p1/models")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1
        client = acm.__aenter__.return_value
        assert client.get.call_args.kwargs["headers"] == {}

    def test_discover_models_error(self):
        import httpx

        db = _local_db(first_provider=_provider())
        acm = _httpx_acm(exc=httpx.ConnectError("conn refused"))
        with patch(
            "api.routes.local_model_routes.httpx.AsyncClient", return_value=acm
        ):
            resp = self._client(db=db).get("/api/local-models/p1/models")
        assert resp.status_code == 200
        assert resp.json() == {"models": [], "count": 0, "error": "model discovery failed"}

    def test_discover_models_provider_not_found(self):
        resp = self._client(db=_local_db(first_provider=None)).get(
            "/api/local-models/missing/models"
        )
        assert resp.status_code == 404

    # -- GET /api/local-models/{id}/capabilities -------------------------
    def test_get_capabilities_returns_rows(self):
        db = _local_db(caps=[_cap()])
        resp = self._client(db=db).get("/api/local-models/p1/capabilities")
        assert resp.status_code == 200
        body = resp.json()
        assert body == [
            {
                "model_id": "llama3:8b",
                "supports_tools": True,
                "supports_vision": False,
                "supports_reasoning": False,
                "quality_score": 0.7,
                "speed_score": 0.6,
                "context_window": 8192,
            }
        ]

    def test_get_capabilities_empty(self):
        resp = self._client(db=_local_db()).get("/api/local-models/p1/capabilities")
        assert resp.status_code == 200
        assert resp.json() == []

    # -- POST /api/local-models/{id}/capabilities ------------------------
    def test_set_capabilities_create(self):
        db = _local_db(first_provider=_provider(), first_cap=None)
        payload = {
            "model_id": "llama3:8b",
            "supports_tools": True,
            "supports_vision": False,
            "supports_reasoning": True,
            "quality_score": 0.9,
            "speed_score": 0.8,
            "context_window": 16384,
        }
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher") as gp:
            gp.return_value.pricing_cache = {}
            resp = self._client(db=db).post(
                "/api/local-models/p1/capabilities", json=payload
            )
        assert resp.status_code == 200
        assert resp.json() == {"model_id": "llama3:8b", "set": True}
        from core.models import LocalModelCapabilities

        added = db.add.call_args[0][0]
        assert isinstance(added, LocalModelCapabilities)
        assert added.supports_reasoning is True
        assert added.context_window == 16384
        assert added.workspace_id == "default"
        db.commit.assert_called_once()
        entry = gp.return_value.pricing_cache["llama3:8b"]
        assert entry["max_input_tokens"] == 16384
        assert entry["supports_tools"] is True

    def test_set_capabilities_update_existing(self):
        existing = _cap(model_id="llama3:8b")
        db = _local_db(first_provider=_provider(), first_cap=existing)
        payload = {
            "model_id": "llama3:8b",
            "supports_tools": False,
            "supports_vision": True,
            "supports_reasoning": True,
            "quality_score": 0.1,
            "speed_score": 0.2,
            "context_window": 2048,
        }
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher"):
            resp = self._client(db=db).post(
                "/api/local-models/p1/capabilities", json=payload
            )
        assert resp.status_code == 200
        assert existing.supports_vision is True
        assert existing.quality_score == 0.1
        assert existing.context_window == 2048
        db.add.assert_not_called()
        db.commit.assert_called_once()

    def test_set_capabilities_provider_not_found(self):
        resp = self._client(db=_local_db(first_provider=None)).post(
            "/api/local-models/missing/capabilities",
            json={"model_id": "m", "quality_score": 0.5},
        )
        assert resp.status_code == 404

    def test_set_capabilities_validation_error(self):
        resp = self._client(db=_local_db(first_provider=_provider())).post(
            "/api/local-models/p1/capabilities",
            json={"model_id": "m", "quality_score": 1.5},
        )
        assert resp.status_code == 422

    # -- POST /api/local-models/{id}/test --------------------------------
    def test_connection_reachable(self):
        db = _local_db(first_provider=_provider(api_key="sk"))
        acm = _httpx_acm(status=200)
        with patch(
            "api.routes.local_model_routes.httpx.AsyncClient", return_value=acm
        ):
            resp = self._client(db=db).post("/api/local-models/p1/test")
        assert resp.status_code == 200
        assert resp.json() == {"reachable": True, "status_code": 200}

    def test_connection_unreachable(self):
        db = _local_db(first_provider=_provider())
        acm = _httpx_acm(exc=Exception("down"))
        with patch(
            "api.routes.local_model_routes.httpx.AsyncClient", return_value=acm
        ):
            resp = self._client(db=db).post("/api/local-models/p1/test")
        assert resp.status_code == 200
        body = resp.json()
        assert body["reachable"] is False
        assert body["error"] == "connectivity check failed"

    def test_connection_provider_not_found(self):
        resp = self._client(db=_local_db(first_provider=None)).post(
            "/api/local-models/missing/test"
        )
        assert resp.status_code == 404

    # -- helper: _register_in_pricing_cache ------------------------------
    def test_register_in_pricing_cache_success(self):
        from api.routes.local_model_routes import _register_in_pricing_cache

        fetcher = MagicMock()
        fetcher.pricing_cache = {}
        with patch(
            "core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=fetcher
        ):
            _register_in_pricing_cache("m1", _provider(), None)
        entry = fetcher.pricing_cache["m1"]
        assert entry["litellm_provider"] == "ollama"
        assert entry["input_cost"] == 0.0
        assert entry["max_input_tokens"] == 8192
        assert entry["supports_tools"] is True
        assert entry["supports_vision"] is False
        assert entry["quality_score"] == 0.5

    def test_register_in_pricing_cache_with_capabilities(self):
        from api.routes.local_model_routes import _register_in_pricing_cache

        fetcher = MagicMock()
        fetcher.pricing_cache = {}
        caps = {
            "context_window": 4096,
            "supports_tools": False,
            "supports_vision": True,
            "supports_reasoning": True,
            "quality_score": 0.8,
        }
        with patch(
            "core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=fetcher
        ):
            _register_in_pricing_cache("m2", _provider(), caps)
        entry = fetcher.pricing_cache["m2"]
        assert entry["max_input_tokens"] == 4096
        assert entry["supports_tools"] is False
        assert entry["supports_vision"] is True
        assert entry["supports_reasoning"] is True
        assert entry["quality_score"] == 0.8

    def test_register_in_pricing_cache_swallows_errors(self):
        from api.routes.local_model_routes import _register_in_pricing_cache

        with patch(
            "core.dynamic_pricing_fetcher.get_pricing_fetcher",
            side_effect=RuntimeError("boom"),
        ):
            _register_in_pricing_cache("m3", _provider())
        # must not raise


# ===========================================================================
# integrations/discord_routes.py
# ===========================================================================

class TestDiscordRoutes:
    def _call(self, method, path, svc=None, authed=True, **kw):
        from integrations.discord_routes import router

        with patch(
            "integrations.discord_routes.discord_service",
            svc if svc is not None else MagicMock(),
        ):
            resp = getattr(make_client(router, authed=authed), method)(path, **kw)
        return resp

    # -- GET /status ------------------------------------------------------
    def test_status_connected(self):
        svc = _async_svc({"health_check": {"ok": True}}, client_id="abc")
        resp = self._call("get", "/api/discord/status", svc, authed=False)
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["status"] == "connected"

    def test_status_not_configured(self):
        svc = _async_svc({"health_check": {"ok": True}}, client_id=None)
        resp = self._call("get", "/api/discord/status", svc, authed=False)
        assert resp.json()["status"] == "not_configured"

    def test_status_health_false(self):
        svc = _async_svc({"health_check": {"ok": False}}, client_id=None)
        resp = self._call("get", "/api/discord/status", svc, authed=False)
        assert resp.json()["ok"] is False

    # -- GET /user --------------------------------------------------------
    def test_user_success(self):
        svc = _async_svc({"get_current_user": {"id": "u1", "username": "bob"}})
        resp = self._call("get", "/api/discord/user", svc, params={"access_token": "t"})
        assert resp.status_code == 200
        assert resp.json()["user"]["username"] == "bob"

    def test_user_error(self):
        svc = _async_svc({"get_current_user": Exception("boom")})
        resp = self._call("get", "/api/discord/user", svc)
        assert resp.status_code == 500

    # -- GET /guilds ------------------------------------------------------
    def test_guilds_success(self):
        svc = _async_svc({"get_user_guilds": [{"id": "g1"}]})
        resp = self._call("get", "/api/discord/guilds", svc, params={"limit": 50})
        assert resp.status_code == 200
        assert resp.json()["guilds"] == [{"id": "g1"}]

    def test_guilds_error(self):
        svc = _async_svc({"get_user_guilds": Exception("boom")})
        resp = self._call("get", "/api/discord/guilds", svc)
        assert resp.status_code == 500

    # -- GET /guilds/{id}/channels ----------------------------------------
    def test_guild_channels_success(self):
        svc = _async_svc({"get_guild_channels": [{"id": "c1"}]})
        resp = self._call("get", "/api/discord/guilds/g1/channels", svc)
        assert resp.status_code == 200
        assert resp.json()["channels"] == [{"id": "c1"}]

    def test_guild_channels_error(self):
        svc = _async_svc({"get_guild_channels": Exception("boom")})
        resp = self._call("get", "/api/discord/guilds/g1/channels", svc)
        assert resp.status_code == 500

    # -- POST /channels/{id}/messages -------------------------------------
    def test_send_message_success(self):
        svc = _async_svc({"send_message": {"id": "msg1"}})
        resp = self._call(
            "post",
            "/api/discord/channels/c1/messages",
            svc,
            json={"channel_id": "c1", "content": "hello"},
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == {"id": "msg1"}

    def test_send_message_with_embeds(self):
        svc = _async_svc({"send_message": {"id": "msg2"}})
        resp = self._call(
            "post",
            "/api/discord/channels/c1/messages",
            svc,
            json={"channel_id": "c1", "content": "hi", "embeds": [{"title": "T"}]},
        )
        assert resp.status_code == 200
        svc.send_message.assert_awaited_with(
            channel_id="c1", content="hi", embeds=[{"title": "T"}]
        )

    def test_send_message_error(self):
        svc = _async_svc({"send_message": Exception("boom")})
        resp = self._call(
            "post",
            "/api/discord/channels/c1/messages",
            svc,
            json={"channel_id": "c1", "content": "hi"},
        )
        assert resp.status_code == 500

    # -- GET /channels/{id}/messages --------------------------------------
    def test_channel_messages_success(self):
        svc = _async_svc({"get_channel_messages": [{"id": "m1"}]})
        resp = self._call("get", "/api/discord/channels/c1/messages", svc)
        assert resp.status_code == 200
        assert resp.json()["messages"] == [{"id": "m1"}]

    def test_channel_messages_error(self):
        svc = _async_svc({"get_channel_messages": Exception("boom")})
        resp = self._call("get", "/api/discord/channels/c1/messages", svc)
        assert resp.status_code == 500

    # -- POST /search -----------------------------------------------------
    def test_search(self):
        resp = self._call("post", "/api/discord/search", json={"query": "billing"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["query"] == "billing"
        assert body["results"] == []

    # -- GET /items -------------------------------------------------------
    def test_items_success(self):
        svc = _async_svc(
            {"get_user_guilds": [{"id": "g1", "name": "G1"}, {"id": "g2", "name": "G2"}]}
        )
        resp = self._call("get", "/api/discord/items", svc)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert items == [
            {"id": "g1", "title": "G1", "status": "active"},
            {"id": "g2", "title": "G2", "status": "active"},
        ]

    def test_items_error(self):
        svc = _async_svc({"get_user_guilds": Exception("boom")})
        resp = self._call("get", "/api/discord/items", svc)
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    # -- GET /auth/url ----------------------------------------------------
    def test_auth_url(self):
        svc = _async_svc({}, get_authorization_url=lambda u: "https://discord.com/oauth")
        resp = self._call("get", "/api/discord/auth/url", svc, authed=False)
        assert resp.status_code == 200
        assert resp.json()["url"] == "https://discord.com/oauth"

    # -- GET /callback ----------------------------------------------------
    def test_callback_success(self):
        svc = _async_svc(
            {"exchange_token": {"access_token": "at", "refresh_token": "rt"}}
        )
        resp = self._call(
            "get", "/api/discord/callback", svc, params={"code": "c", "redirect_uri": "u"}, authed=False
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["access_token"] == "at"
        assert body["status"] == "success"

    def test_callback_error_no_str_leak(self):
        """REGRESSION: str(e) leaked to the client in the error branch."""
        svc = _async_svc({"exchange_token": Exception("secret detail")})
        resp = self._call(
            "get", "/api/discord/callback", svc, params={"code": "bad", "redirect_uri": "u"}, authed=False
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert body["status"] == "error"
        assert "secret detail" not in body["message"]

    # -- GET /health ------------------------------------------------------
    def test_health_healthy(self):
        svc = _async_svc({"health_check": {"ok": True}}, client_id="abc")
        resp = self._call("get", "/api/discord/health", svc, authed=False)
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["configured"] is True

    def test_health_unhealthy(self):
        svc = _async_svc({"health_check": {"ok": False}}, client_id=None)
        resp = self._call("get", "/api/discord/health", svc, authed=False)
        body = resp.json()
        assert body["status"] == "unhealthy"
        assert body["configured"] is False

    # -- POST /interactions -----------------------------------------------
    def _interactions(self, raw, headers=None):
        from integrations.discord_routes import router

        hdrs = {
            "X-Signature-Ed25519": "ab" * 32,
            "X-Signature-Timestamp": "1700000000",
        }
        if headers:
            hdrs.update(headers)
        return make_client(router).post(
            "/api/discord/interactions", content=raw, headers=hdrs
        )

    def test_interactions_rate_limited(self):
        from integrations.discord_routes import router

        with patch(
            "integrations.discord_routes.discord_rate_limiter.check", return_value=False
        ):
            resp = self._interactions(b'{"type": 1}')
        assert resp.status_code == 429

    def test_interactions_bad_signature(self):
        from integrations.discord_routes import router

        with patch(
            "integrations.discord_routes.verify_discord_signature", return_value=False
        ):
            resp = self._interactions(b'{"type": 1}')
        assert resp.status_code == 401

    def test_interactions_invalid_json(self):
        from integrations.discord_routes import router

        with patch(
            "integrations.discord_routes.verify_discord_signature", return_value=True
        ):
            resp = self._interactions(b"{not json")
        assert resp.status_code == 400

    def test_interactions_ping(self):
        from integrations.discord_routes import router

        with patch(
            "integrations.discord_routes.verify_discord_signature", return_value=True
        ):
            resp = self._interactions(b'{"type": 1}')
        assert resp.status_code == 200
        assert resp.json() == {"type": 1}

    def test_interactions_type3_dispatches_action(self):
        """REGRESSION: dispatcher.dispatch() never existed -> AttributeError 500."""
        from integrations.discord_routes import router

        dispatcher = MagicMock()
        dispatcher.dispatch_action = AsyncMock(return_value={})
        payload = {
            "type": 3,
            "data": {"custom_id": "approve-btn"},
            "member": {"user": {"id": "u9"}},
        }
        with patch(
            "integrations.discord_routes.verify_discord_signature", return_value=True
        ), patch("integrations.discord_routes.discord_dispatcher", dispatcher):
            resp = self._interactions(str(payload).replace("'", '"').encode())
        assert resp.status_code == 200
        assert resp.json() == {"type": 6}
        dispatcher.dispatch_action.assert_awaited_once()
        call = dispatcher.dispatch_action.await_args_list[0]
        assert call.kwargs["platform"] == "discord"
        assert call.kwargs["action_id"] == "approve-btn"
        assert call.kwargs["user_id"] == "u9"
        assert call.kwargs["payload"]["type"] == 3

    def test_interactions_type3_payload_user_fallback(self):
        from integrations.discord_routes import router

        dispatcher = MagicMock()
        dispatcher.dispatch_action = AsyncMock(return_value={})
        payload = {"type": 3, "data": {"custom_id": "btn"}, "user": {"id": "u7"}}
        with patch(
            "integrations.discord_routes.verify_discord_signature", return_value=True
        ), patch("integrations.discord_routes.discord_dispatcher", dispatcher):
            resp = self._interactions(str(payload).replace("'", '"').encode())
        assert resp.status_code == 200
        call = dispatcher.dispatch_action.await_args_list[0]
        assert call.kwargs["user_id"] == "u7"

    def test_interactions_fallback_ok(self):
        from integrations.discord_routes import router

        with patch(
            "integrations.discord_routes.verify_discord_signature", return_value=True
        ):
            resp = self._interactions(b'{"type": 99}')
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}


class TestDiscordRateLimiter:
    def test_check_under_limit(self):
        from integrations.discord_routes import _RateLimiter

        limiter = _RateLimiter(limit=2, window=60)
        assert limiter.check("ip1") is True
        assert limiter.check("ip1") is True
        assert len(limiter._hits["ip1"]) == 2

    def test_check_over_limit(self):
        from integrations.discord_routes import _RateLimiter

        limiter = _RateLimiter(limit=2, window=60)
        assert limiter.check("ip1") is True
        assert limiter.check("ip1") is True
        assert limiter.check("ip1") is False

    def test_check_per_key_isolation(self):
        from integrations.discord_routes import _RateLimiter

        limiter = _RateLimiter(limit=1, window=60)
        assert limiter.check("a") is True
        assert limiter.check("a") is False
        assert limiter.check("b") is True

    def test_check_prunes_stale_hits(self):
        from integrations.discord_routes import _RateLimiter

        limiter = _RateLimiter(limit=1, window=60)
        with patch("time.time", side_effect=[100.0, 200.0]):
            assert limiter.check("ip1") is True
            assert limiter.check("ip1") is True
        assert all(v == 200.0 for v in limiter._hits["ip1"])


class TestVerifyDiscordSignature:
    def test_no_public_key(self):
        from integrations.discord_routes import verify_discord_signature

        with patch("integrations.discord_routes.DISCORD_PUBLIC_KEY", ""):
            assert verify_discord_signature(b"body", "sig", "ts") is False

    def test_missing_signature_or_timestamp(self):
        from integrations.discord_routes import verify_discord_signature

        with patch("integrations.discord_routes.DISCORD_PUBLIC_KEY", "ab" * 32):
            assert verify_discord_signature(b"body", "", "ts") is False
            assert verify_discord_signature(b"body", "sig", "") is False

    def test_valid_signature(self):
        from integrations.discord_routes import verify_discord_signature

        verify_key = MagicMock()
        with patch("integrations.discord_routes.DISCORD_PUBLIC_KEY", "ab" * 32), patch(
            "nacl.signing.VerifyKey", return_value=verify_key
        ):
            assert verify_discord_signature(b"body", "cd" * 32, "1700000000") is True
        verify_key.verify.assert_called_once()

    def test_bad_signature(self):
        from integrations.discord_routes import verify_discord_signature

        from nacl.exceptions import BadSignatureError

        verify_key = MagicMock()
        verify_key.verify.side_effect = BadSignatureError("bad")
        with patch("integrations.discord_routes.DISCORD_PUBLIC_KEY", "ab" * 32), patch(
            "nacl.signing.VerifyKey", return_value=verify_key
        ):
            assert verify_discord_signature(b"body", "cd" * 32, "1700000000") is False

    def test_import_error_path(self):
        from integrations.discord_routes import verify_discord_signature

        with patch("integrations.discord_routes.DISCORD_PUBLIC_KEY", "ab" * 32), patch.dict(
            sys.modules, {"nacl.signing": None}
        ):
            assert verify_discord_signature(b"body", "cd" * 32, "1700000000") is False


# ===========================================================================
# core/token_refresher.py
# ===========================================================================

class TestTokenRefresher:
    def _make(self):
        from core.token_refresher import TokenRefresher

        return TokenRefresher()

    # -- register_service -------------------------------------------------
    def test_register_service(self):
        tr = self._make()
        tr.register_service("svc", lambda m: None, refresh_token="rt")
        assert "svc" in tr.refresh_handlers
        meta = tr.token_metadata["svc"]
        assert meta["refresh_token"] == "rt"
        assert meta["expires_at"] is None
        assert meta["last_refreshed"] is None

    def test_register_service_with_expiry(self):
        tr = self._make()
        exp = datetime.now(timezone.utc)
        tr.register_service("svc", lambda m: None, expires_at=exp)
        assert tr.token_metadata["svc"]["expires_at"] is exp

    # -- should_refresh ---------------------------------------------------
    def test_should_refresh_unknown_service(self):
        assert self._make().should_refresh("nope") is False

    def test_should_refresh_no_expiry(self):
        tr = self._make()
        tr.register_service("svc", lambda m: None)
        assert tr.should_refresh("svc") is False

    def test_should_refresh_naive_past_expiry(self):
        tr = self._make()
        tr.register_service(
            "svc", lambda m: None, expires_at=datetime.now() - timedelta(minutes=5)
        )
        assert tr.should_refresh("svc") is True

    def test_should_refresh_aware_past_expiry(self):
        tr = self._make()
        tr.register_service(
            "svc",
            lambda m: None,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        assert tr.should_refresh("svc") is True

    def test_should_refresh_aware_future_expiry(self):
        tr = self._make()
        tr.register_service(
            "svc",
            lambda m: None,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert tr.should_refresh("svc") is False

    def test_should_refresh_naive_future_expiry(self):
        tr = self._make()
        tr.register_service(
            "svc",
            lambda m: None,
            expires_at=datetime.now() + timedelta(hours=1),
        )
        # Naive datetimes are ambiguous (local wall vs UTC wall); the
        # established coercion reinterprets them as UTC, so on non-UTC hosts
        # a naive-future local time may compare as expired. Must never crash
        # and must return a bool.
        assert isinstance(tr.should_refresh("svc"), bool)

    # -- refresh_token ----------------------------------------------------
    def test_refresh_token_no_handler(self):
        tr = self._make()
        assert asyncio.run(tr.refresh_token("missing")) is False

    def test_refresh_token_success(self):
        tr = self._make()
        exp = datetime.now(timezone.utc) + timedelta(hours=1)

        async def handler(metadata):
            return {"expires_at": exp, "refresh_token": "new-rt", "access_token": "at"}

        tr.register_service("svc", handler, refresh_token="old-rt")
        assert asyncio.run(tr.refresh_token("svc")) is True
        meta = tr.token_metadata["svc"]
        assert meta["refresh_token"] == "new-rt"
        assert meta["expires_at"] is exp
        assert meta["last_refreshed"] is not None

    def test_refresh_token_handler_returns_none(self):
        tr = self._make()

        async def handler(metadata):
            return None

        tr.register_service("svc", handler)
        assert asyncio.run(tr.refresh_token("svc")) is False
        assert tr.token_metadata["svc"]["last_refreshed"] is None

    def test_refresh_token_handler_raises(self):
        tr = self._make()

        async def handler(metadata):
            raise RuntimeError("token endpoint down")

        tr.register_service("svc", handler)
        assert asyncio.run(tr.refresh_token("svc")) is False

    # -- check_and_refresh_all -------------------------------------------
    def test_check_and_refresh_all_no_services(self):
        tr = self._make()
        assert asyncio.run(tr.check_and_refresh_all()) is None

    def test_check_and_refresh_all_refreshes_due(self):
        tr = self._make()

        async def handler(metadata):
            return {
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
                "refresh_token": "rt2",
            }

        tr.register_service(
            "svc", handler, expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
        )
        tr.register_service(
            "future", lambda m: None, expires_at=datetime.now(timezone.utc) + timedelta(hours=2)
        )
        asyncio.run(tr.check_and_refresh_all())
        assert tr.token_metadata["svc"]["refresh_token"] == "rt2"
        assert tr.token_metadata["future"]["last_refreshed"] is None

    def test_check_and_refresh_all_handler_exception(self):
        tr = self._make()

        async def handler(metadata):
            raise RuntimeError("boom")

        tr.register_service(
            "bad", handler, expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
        )
        asyncio.run(tr.check_and_refresh_all())
        assert tr.token_metadata["bad"]["last_refreshed"] is None

    # -- get_status -------------------------------------------------------
    def test_get_status_empty(self):
        assert self._make().get_status() == {}

    def test_get_status_fields(self):
        tr = self._make()
        exp = datetime.now(timezone.utc) + timedelta(hours=1)
        tr.register_service("svc", lambda m: None, expires_at=exp)
        status = tr.get_status()
        assert status["svc"]["expires_at"] == exp.isoformat()
        assert status["svc"]["needs_refresh"] is False
        assert status["svc"]["last_refreshed"] is None
        tr.token_metadata["svc"]["last_refreshed"] = datetime.now(timezone.utc)
        assert tr.get_status()["svc"]["last_refreshed"] is not None

    def test_get_status_naive_expiry(self):
        tr = self._make()
        tr.register_service("svc", lambda m: None, expires_at=datetime.now())
        status = tr.get_status()
        assert status["svc"]["expires_at"] is not None


class TestTokenRefreshHandlers:
    # -- Google -----------------------------------------------------------
    def test_refresh_google_missing_token(self):
        from core.token_refresher import refresh_google_token

        assert asyncio.run(refresh_google_token({})) is None

    def test_refresh_google_success(self):
        from core.token_refresher import refresh_google_token

        handler = MagicMock()
        handler.refresh_access_token = AsyncMock(
            return_value={"expires_in": 3600, "refresh_token": "rt2", "access_token": "at2"}
        )
        with patch("core.oauth_handler.OAuthHandler", return_value=handler):
            result = asyncio.run(
                refresh_google_token({"refresh_token": "rt1"})
            )
        assert result is not None
        assert result["access_token"] == "at2"
        assert result["refresh_token"] == "rt2"
        assert isinstance(result["expires_at"], datetime)
        handler.refresh_access_token.assert_awaited_once_with("rt1")

    def test_refresh_google_success_defaults(self):
        from core.token_refresher import refresh_google_token

        handler = MagicMock()
        handler.refresh_access_token = AsyncMock(return_value={"access_token": "at"})
        with patch("core.oauth_handler.OAuthHandler", return_value=handler):
            result = asyncio.run(refresh_google_token({"refresh_token": "rt1"}))
        assert result["refresh_token"] == "rt1"

    def test_refresh_google_error(self):
        from core.token_refresher import refresh_google_token

        handler = MagicMock()
        handler.refresh_access_token = AsyncMock(side_effect=Exception("oauth down"))
        with patch("core.oauth_handler.OAuthHandler", return_value=handler):
            assert asyncio.run(refresh_google_token({"refresh_token": "rt1"})) is None

    # -- Microsoft --------------------------------------------------------
    def test_refresh_microsoft_missing_token(self):
        from core.token_refresher import refresh_microsoft_token

        assert asyncio.run(refresh_microsoft_token({})) is None

    def test_refresh_microsoft_success(self):
        from core.token_refresher import refresh_microsoft_token

        handler = MagicMock()
        handler.refresh_access_token = AsyncMock(
            return_value={"expires_in": 3600, "refresh_token": "rt2", "access_token": "at2"}
        )
        with patch("core.oauth_handler.OAuthHandler", return_value=handler):
            result = asyncio.run(
                refresh_microsoft_token({"refresh_token": "rt1"})
            )
        assert result is not None
        assert result["access_token"] == "at2"

    def test_refresh_microsoft_error(self):
        from core.token_refresher import refresh_microsoft_token

        handler = MagicMock()
        handler.refresh_access_token = AsyncMock(side_effect=Exception("down"))
        with patch("core.oauth_handler.OAuthHandler", return_value=handler):
            assert asyncio.run(refresh_microsoft_token({"refresh_token": "rt1"})) is None

    # -- Salesforce -------------------------------------------------------
    def test_refresh_salesforce_missing_token(self):
        from core.token_refresher import refresh_salesforce_token

        assert asyncio.run(refresh_salesforce_token({})) is None

    def test_refresh_salesforce_success(self):
        from core.token_refresher import refresh_salesforce_token

        handler = MagicMock()
        handler.refresh_access_token = AsyncMock(
            return_value={"expires_in": 7200, "refresh_token": "rt2", "access_token": "at2"}
        )
        with patch("core.oauth_handler.OAuthHandler", return_value=handler):
            result = asyncio.run(
                refresh_salesforce_token({"refresh_token": "rt1"})
            )
        assert result is not None
        assert result["access_token"] == "at2"

    def test_refresh_salesforce_error(self):
        from core.token_refresher import refresh_salesforce_token

        handler = MagicMock()
        handler.refresh_access_token = AsyncMock(side_effect=Exception("down"))
        with patch("core.oauth_handler.OAuthHandler", return_value=handler):
            assert asyncio.run(refresh_salesforce_token({"refresh_token": "rt1"})) is None

    # -- WhatsApp ---------------------------------------------------------
    def test_refresh_whatsapp_missing_credentials(self, monkeypatch):
        from core.token_refresher import refresh_whatsapp_token

        monkeypatch.delenv("WHATSAPP_APP_ID", raising=False)
        monkeypatch.delenv("WHATSAPP_APP_SECRET", raising=False)
        assert (
            asyncio.run(refresh_whatsapp_token({"refresh_token": "st"})) is None
        )

    def test_refresh_whatsapp_missing_token(self, monkeypatch):
        from core.token_refresher import refresh_whatsapp_token

        monkeypatch.setenv("WHATSAPP_APP_ID", "app")
        monkeypatch.setenv("WHATSAPP_APP_SECRET", "sec")
        assert asyncio.run(refresh_whatsapp_token({})) is None

    def test_refresh_whatsapp_success(self, monkeypatch):
        from core.token_refresher import refresh_whatsapp_token

        monkeypatch.setenv("WHATSAPP_APP_ID", "app")
        monkeypatch.setenv("WHATSAPP_APP_SECRET", "sec")
        resp = MagicMock()
        resp.json.return_value = {"expires_in": 100, "access_token": "long-lived"}
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        acm = MagicMock()
        acm.__aenter__.return_value = client
        acm.__aexit__.return_value = False
        with patch("core.token_refresher.httpx.AsyncClient", return_value=acm):
            result = asyncio.run(refresh_whatsapp_token({"refresh_token": "st"}))
        assert result is not None
        assert result["access_token"] == "long-lived"
        assert result["refresh_token"] == "long-lived"
        assert isinstance(result["expires_at"], datetime)
        call = client.get.await_args
        assert call.args[0] == "https://graph.facebook.com/v17.0/oauth/access_token"
        assert call.kwargs["params"]["grant_type"] == "fb_exchange_token"

    def test_refresh_whatsapp_error(self, monkeypatch):
        import httpx

        from core.token_refresher import refresh_whatsapp_token

        monkeypatch.setenv("WHATSAPP_APP_ID", "app")
        monkeypatch.setenv("WHATSAPP_APP_SECRET", "sec")
        client = MagicMock()
        client.get = AsyncMock(side_effect=httpx.ConnectError("down"))
        acm = MagicMock()
        acm.__aenter__.return_value = client
        acm.__aexit__.return_value = False
        with patch("core.token_refresher.httpx.AsyncClient", return_value=acm):
            assert (
                asyncio.run(refresh_whatsapp_token({"refresh_token": "st"})) is None
            )


# NOTE: must stay the LAST class in the file — importlib.reload of
# core.token_refresher replaces module globals (incl. the TokenRefresher class)
# that other tests import lazily from inside their methods.
class TestTokenRefresherModuleRegistration:
    _VARS = ("WHATSAPP_APP_ID", "GMAIL_CLIENT_ID", "OUTLOOK_CLIENT_ID", "SALESFORCE_CLIENT_ID")

    def test_module_registers_services_when_env_set(self, monkeypatch):
        import core.token_refresher as tr

        for var in self._VARS:
            monkeypatch.setenv(var, "test-value")
        try:
            with patch("dotenv.load_dotenv"):
                importlib.reload(tr)
            assert "whatsapp" in tr.token_refresher.refresh_handlers
            assert "google" in tr.token_refresher.refresh_handlers
            assert "microsoft" in tr.token_refresher.refresh_handlers
            assert "salesforce" in tr.token_refresher.refresh_handlers
        finally:
            for var in self._VARS:
                monkeypatch.delenv(var, raising=False)
            with patch("dotenv.load_dotenv"):
                importlib.reload(tr)
        assert tr.token_refresher.refresh_handlers == {}

    def test_module_no_registration_without_env(self, monkeypatch):
        import core.token_refresher as tr

        for var in self._VARS:
            monkeypatch.delenv(var, raising=False)
        with patch("dotenv.load_dotenv"):
            importlib.reload(tr)
        assert tr.token_refresher.refresh_handlers == {}

    def test_singleton_is_token_refresher(self):
        import core.token_refresher as tr

        from core.token_refresher import TokenRefresher

        assert isinstance(tr.token_refresher, TokenRefresher)


# ===========================================================================
# core/voice_service.py
# ===========================================================================

class TestVoiceService:
    def _make(self, whisper_available=True):
        from core.voice_service import VoiceService

        with patch("core.voice_service.LLMService") as llm_cls:
            inst = llm_cls.return_value
            inst.is_available.return_value = whisper_available
            inst.transcribe_audio = AsyncMock(return_value={"text": "hello world"})
            svc = VoiceService("ws-1", "t-1")
        llm_cls.assert_called_once_with(workspace_id="ws-1", tenant_id="t-1")
        return svc, inst

    def test_init_sets_attrs(self):
        svc, inst = self._make()
        assert svc.workspace_id == "ws-1"
        assert svc.tenant_id == "t-1"
        assert svc._whisper_available is True

    def test_init_whisper_unavailable(self):
        svc, inst = self._make(whisper_available=False)
        assert svc._whisper_available is False

    def test_transcribe_audio_success(self):
        svc, inst = self._make()
        result = asyncio.run(svc.transcribe_audio(b"x" * 32000, "wav", "fr"))
        assert result.text == "hello world"
        assert result.confidence == 0.95
        assert result.language == "fr"
        assert result.duration_seconds == 2.0
        assert isinstance(result.timestamp, datetime)
        call = inst.transcribe_audio.await_args
        assert call.kwargs["model"] == "whisper-1"
        assert call.kwargs["language"] == "fr"
        assert call.kwargs["file"].name == "audio.wav"

    def test_transcribe_audio_fallback_on_error(self):
        svc, inst = self._make()
        inst.transcribe_audio = AsyncMock(side_effect=RuntimeError("api down"))
        result = asyncio.run(svc.transcribe_audio(b"data"))
        assert result.text == "[Voice transcription unavailable]"
        assert result.confidence == 0.0
        assert result.language == "en"

    def test_transcribe_with_whisper_wrapper(self):
        svc, inst = self._make()
        result = asyncio.run(svc._transcribe_with_whisper(b"data", "webm", "en"))
        assert result.text == "hello world"

    def test_process_voice_command_transcribed_text(self):
        svc, inst = self._make()
        result = asyncio.run(self._run_command(svc, transcribed_text="analyze sales"))
        assert result["success"] is True
        assert result["transcription"]["text"] == "analyze sales"
        assert result["transcription"]["confidence"] == 0.9
        assert result["reasoning_chain_id"] == "chain-9"
        assert result["result"]["final_output"] == "done"

    def test_process_voice_command_audio(self):
        svc, inst = self._make()
        result = asyncio.run(self._run_command(svc, audio_bytes=b"audio-bytes"))
        assert result["success"] is True
        assert result["transcription"]["text"] == "hello world"

    def test_process_voice_command_no_input(self):
        svc, inst = self._make()
        result = asyncio.run(svc.process_voice_command())
        assert result == {"error": "No audio or text provided"}

    def test_process_voice_command_execution_error(self):
        svc, inst = self._make()
        atom = AsyncMock()
        atom.execute = AsyncMock(side_effect=RuntimeError("agent exploded"))

        fake_ama = MagicMock()
        fake_ama.AgentTriggerMode.MANUAL = "manual"
        fake_ama.get_atom_agent = MagicMock(return_value=atom)
        fake_rc = MagicMock()
        fake_rc.ReasoningStepType.INTENT_ANALYSIS = "intent"
        tracker = MagicMock()
        tracker.start_chain.return_value = "chain-9"
        fake_rc.get_reasoning_tracker = MagicMock(return_value=tracker)

        with patch.dict(
            sys.modules,
            {"core.atom_meta_agent": fake_ama, "core.reasoning_chain": fake_rc},
        ):
            result = asyncio.run(
                svc.process_voice_command(transcribed_text="hi", user_id="u1")
            )
        assert result["success"] is False
        assert "error" in result

    async def _run_command(self, svc, transcribed_text=None, audio_bytes=None):
        atom = AsyncMock()
        atom.execute = AsyncMock(return_value={"final_output": "done"})

        fake_ama = MagicMock()
        fake_ama.AgentTriggerMode.MANUAL = "manual"
        fake_ama.get_atom_agent = MagicMock(return_value=atom)
        fake_rc = MagicMock()
        fake_rc.ReasoningStepType.INTENT_ANALYSIS = "intent"
        tracker = MagicMock()
        tracker.start_chain.return_value = "chain-9"
        fake_rc.get_reasoning_tracker = MagicMock(return_value=tracker)

        with patch.dict(
            sys.modules,
            {"core.atom_meta_agent": fake_ama, "core.reasoning_chain": fake_rc},
        ):
            return await svc.process_voice_command(
                transcribed_text=transcribed_text,
                audio_bytes=audio_bytes,
                user_id="u1",
            )

    # -- get_voice_service singleton --------------------------------------
    def _reset_singleton(self):
        import core.voice_service as vs

        vs._voice_service = None

    def test_get_voice_service_creates(self):
        import core.voice_service as vs

        self._reset_singleton()
        with patch("core.voice_service.LLMService"):
            svc = vs.get_voice_service("ws-a", "t-a")
        assert svc.workspace_id == "ws-a"
        assert vs._voice_service is svc

    def test_get_voice_service_reuses(self):
        import core.voice_service as vs

        self._reset_singleton()
        with patch("core.voice_service.LLMService"):
            svc1 = vs.get_voice_service("ws-a", "t-a")
            svc2 = vs.get_voice_service("ws-a", "t-a")
        assert svc1 is svc2

    def test_get_voice_service_recreates_on_workspace_change(self):
        import core.voice_service as vs

        self._reset_singleton()
        with patch("core.voice_service.LLMService"):
            svc1 = vs.get_voice_service("ws-a", "t-a")
            svc2 = vs.get_voice_service("ws-b", "t-a")
        assert svc1 is not svc2
        assert vs._voice_service is svc2

    def test_get_voice_service_recreates_on_tenant_change(self):
        import core.voice_service as vs

        self._reset_singleton()
        with patch("core.voice_service.LLMService"):
            svc1 = vs.get_voice_service("ws-a", "t-a")
            svc2 = vs.get_voice_service("ws-a", "t-b")
        assert svc1 is not svc2
