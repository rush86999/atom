"""
Coverage-push tests: integrations.discord_service + integrations.integration_helpers.

TDD: bug tests written RED first (URL encoding, missing-credential crash, health
exception path, user_id TypeError on AgentExecution, str(e) leak), then minimal fixes.
"""

import json
import logging
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import HTTPException

import integrations.discord_service as discord_mod
from integrations.discord_service import DiscordService
from integrations.integration_helpers import (
    create_execution_record,
    standard_error_response,
    with_governance_check,
)
from core.models import AgentExecution, AgentRegistry, User


@pytest.fixture
def discord_factory(monkeypatch):
    real_client = httpx.AsyncClient

    def build(handler, **config):
        transport = httpx.MockTransport(handler)

        def make_client(*args, **kwargs):
            kwargs["transport"] = transport
            return real_client(*args, **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", make_client)
        return DiscordService(config={
            "client_id": "cid", "client_secret": "csec", "bot_token": "btok", **config
        })

    return build


def ok_handler(payload=None, **kwargs):
    body = payload if payload is not None else {}

    def handler(request):
        return httpx.Response(200, json=body, **kwargs)

    return handler


class TestDiscordInit:
    def test_defaults(self):
        svc = DiscordService()
        assert svc.config == {}
        assert svc.tenant_id == "default"
        assert svc.base_url == "https://discord.com/api/v10"
        assert svc.token_url == "https://discord.com/api/oauth2/token"

    def test_config_values_used(self):
        svc = DiscordService(config={
            "client_id": "cfg-id", "client_secret": "cfg-secret", "bot_token": "cfg-bot",
            "access_token": "cfg-access",
        })
        assert svc.client_id == "cfg-id"
        assert svc.client_secret == "cfg-secret"
        assert svc.bot_token == "cfg-bot"
        assert svc.access_token == "cfg-access"

    async def test_close(self, discord_factory):
        svc = discord_factory(ok_handler())
        await svc.close()


class TestGetHeaders:
    def test_bot_token_headers(self):
        svc = DiscordService(config={"bot_token": "btok"})
        headers = svc._get_headers(use_bot_token=True)
        assert headers == {"Authorization": "Bot btok", "Content-Type": "application/json"}

    def test_bearer_explicit_token(self):
        svc = DiscordService(config={"access_token": "self-access"})
        headers = svc._get_headers(access_token="explicit")
        assert headers["Authorization"] == "Bearer explicit"

    def test_bearer_default_token(self):
        svc = DiscordService(config={"access_token": "self-access"})
        headers = svc._get_headers()
        assert headers["Authorization"] == "Bearer self-access"

    def test_bot_fallback_without_bot_token(self):
        svc = DiscordService(config={"access_token": "at"})
        headers = svc._get_headers(use_bot_token=True)
        assert headers["Authorization"] == "Bearer at"


class TestAuthorizationUrl:
    def test_basic_url(self):
        svc = DiscordService(config={"client_id": "cid"})
        url = svc.get_authorization_url("https://app.example.com/callback")
        parts = urlparse(url)
        assert parts.scheme == "https"
        assert parts.netloc == "discord.com"
        params = parse_qs(parts.query)
        assert params["client_id"] == ["cid"]
        assert params["response_type"] == ["code"]
        assert params["redirect_uri"] == ["https://app.example.com/callback"]
        assert params["scope"] == ["identify guilds"]

    def test_with_state(self):
        svc = DiscordService(config={"client_id": "cid"})
        url = svc.get_authorization_url("https://app.example.com/callback", state="s3cret")
        assert parse_qs(urlparse(url).query)["state"] == ["s3cret"]

    def test_custom_scope(self):
        svc = DiscordService(config={"client_id": "cid"})
        url = svc.get_authorization_url("https://app.example.com/callback", scope="identify")
        assert parse_qs(urlparse(url).query)["scope"] == ["identify"]

    def test_redirect_uri_is_url_encoded(self):
        svc = DiscordService(config={"client_id": "cid"})
        redirect_uri = "https://app.example.com/callback?utm=1&x=2"
        url = svc.get_authorization_url(redirect_uri, scope="identify")
        params = parse_qs(urlparse(url).query)
        assert params["redirect_uri"] == [redirect_uri]
        assert params["scope"] == ["identify"]


class TestExchangeToken:
    async def test_success(self, discord_factory):
        captured = {}

        def handler(request):
            captured["url"] = str(request.url)
            captured["auth"] = request.headers.get("Authorization")
            captured["body"] = request.content.decode()
            return httpx.Response(200, json={"access_token": "new-tok", "expires_in": 3600})

        svc = discord_factory(handler)
        result = await svc.exchange_token("code123", "https://app.example.com/cb")
        assert result["access_token"] == "new-tok"
        assert svc.access_token == "new-tok"
        assert captured["url"] == "https://discord.com/api/oauth2/token"
        assert "code=code123" in captured["body"]
        assert "redirect_uri=https%3A%2F%2Fapp.example.com%2Fcb" in captured["body"]
        assert captured["auth"].startswith("Basic ")

    async def test_http_error_raises_400(self, discord_factory):
        def handler(request):
            return httpx.Response(400, json={"error": "invalid_grant"})

        svc = discord_factory(handler)
        with pytest.raises(HTTPException) as exc:
            await svc.exchange_token("bad", "https://app.example.com/cb")
        assert exc.value.status_code == 400

    async def test_missing_credentials_raises_400(self, discord_factory):
        svc = discord_factory({})
        svc.client_id = None
        svc.client_secret = None
        with pytest.raises(HTTPException) as exc:
            await svc.exchange_token("code123", "https://app.example.com/cb")
        assert exc.value.status_code == 400


class TestGetCurrentUser:
    async def test_success(self, discord_factory):
        captured = {}

        def handler(request):
            captured["path"] = request.url.path
            captured["auth"] = request.headers.get("Authorization")
            return httpx.Response(200, json={"id": "u1", "username": "alice"})

        svc = discord_factory(handler)
        result = await svc.get_current_user(access_token="at")
        assert result == {"id": "u1", "username": "alice"}
        assert captured["path"] == "/api/v10/users/@me"
        assert captured["auth"] == "Bearer at"

    async def test_no_token_raises_401(self):
        svc = DiscordService()
        with pytest.raises(HTTPException) as exc:
            await svc.get_current_user()
        assert exc.value.status_code == 401

    async def test_http_error_raises_400(self, discord_factory):
        svc = discord_factory(lambda request: httpx.Response(500, json={}))
        svc.access_token = "at"
        with pytest.raises(HTTPException) as exc:
            await svc.get_current_user()
        assert exc.value.status_code == 400


class TestGetUserGuilds:
    async def test_success(self, discord_factory):
        captured = {}

        def handler(request):
            captured["path"] = request.url.path
            captured["limit"] = request.url.params.get("limit")
            return httpx.Response(200, json=[{"id": "g1", "name": "Guild"}])

        svc = discord_factory(handler)
        result = await svc.get_user_guilds(access_token="at", limit=5)
        assert result[0]["id"] == "g1"
        assert captured["path"] == "/api/v10/users/@me/guilds"
        assert captured["limit"] == "5"

    async def test_default_limit(self, discord_factory):
        captured = {}

        def handler(request):
            captured["limit"] = request.url.params.get("limit")
            return httpx.Response(200, json=[])

        svc = discord_factory(handler)
        svc.access_token = "at"
        await svc.get_user_guilds()
        assert captured["limit"] == "100"

    async def test_no_token_raises_401(self):
        svc = DiscordService()
        with pytest.raises(HTTPException) as exc:
            await svc.get_user_guilds()
        assert exc.value.status_code == 401

    async def test_http_error_raises_400(self, discord_factory):
        svc = discord_factory(lambda request: httpx.Response(403, json={}))
        svc.access_token = "at"
        with pytest.raises(HTTPException) as exc:
            await svc.get_user_guilds()
        assert exc.value.status_code == 400


class TestGetGuildChannels:
    async def test_success_bot_token(self, discord_factory):
        captured = {}

        def handler(request):
            captured["path"] = request.url.path
            captured["auth"] = request.headers.get("Authorization")
            return httpx.Response(200, json=[{"id": "c1"}])

        svc = discord_factory(handler)
        result = await svc.get_guild_channels("g1")
        assert result == [{"id": "c1"}]
        assert captured["path"] == "/api/v10/guilds/g1/channels"
        assert captured["auth"] == "Bot btok"

    async def test_success_user_token(self, discord_factory):
        captured = {}

        def handler(request):
            captured["auth"] = request.headers.get("Authorization")
            return httpx.Response(200, json=[])

        svc = discord_factory(handler)
        await svc.get_guild_channels("g1", use_bot_token=False, access_token="at")
        assert captured["auth"] == "Bearer at"

    async def test_http_error_raises_400(self, discord_factory):
        svc = discord_factory(lambda request: httpx.Response(404, json={}))
        with pytest.raises(HTTPException) as exc:
            await svc.get_guild_channels("g1")
        assert exc.value.status_code == 400


class TestSendMessage:
    async def test_success(self, discord_factory):
        captured = {}

        def handler(request):
            captured["path"] = request.url.path
            captured["auth"] = request.headers.get("Authorization")
            captured["payload"] = json.loads(request.content)
            return httpx.Response(200, json={"id": "m1", "content": "hello"})

        svc = discord_factory(handler)
        result = await svc.send_message("c1", "hello")
        assert result["id"] == "m1"
        assert captured["path"] == "/api/v10/channels/c1/messages"
        assert captured["auth"] == "Bot btok"
        assert captured["payload"] == {"content": "hello"}

    async def test_success_with_embeds(self, discord_factory):
        captured = {}

        def handler(request):
            captured["payload"] = json.loads(request.content)
            return httpx.Response(200, json={"id": "m2"})

        svc = discord_factory(handler)
        embeds = [{"title": "Report", "description": "Q3"}]
        await svc.send_message("c1", "hello", embeds=embeds, use_bot_token=False, access_token="at")
        assert captured["payload"] == {"content": "hello", "embeds": embeds}

    async def test_http_error_raises_400(self, discord_factory):
        svc = discord_factory(lambda request: httpx.Response(429, json={}))
        with pytest.raises(HTTPException) as exc:
            await svc.send_message("c1", "hello")
        assert exc.value.status_code == 400


class TestGetChannelMessages:
    async def test_success(self, discord_factory):
        captured = {}

        def handler(request):
            captured["path"] = request.url.path
            captured["limit"] = request.url.params.get("limit")
            return httpx.Response(200, json=[{"id": "m1"}])

        svc = discord_factory(handler)
        result = await svc.get_channel_messages("c1", limit=10)
        assert result == [{"id": "m1"}]
        assert captured["path"] == "/api/v10/channels/c1/messages"
        assert captured["limit"] == "10"

    async def test_http_error_raises_400(self, discord_factory):
        svc = discord_factory(lambda request: httpx.Response(500, json={}))
        with pytest.raises(HTTPException) as exc:
            await svc.get_channel_messages("c1")
        assert exc.value.status_code == 400


class TestHealthCheck:
    async def test_healthy(self):
        svc = DiscordService()
        result = await svc.health_check()
        assert result["healthy"] is True
        assert result["status"] == "healthy"
        assert result["service"] == "discord"
        assert result["version"] == "1.0.0"

    async def test_unhealthy_does_not_raise(self, monkeypatch):
        class BoomClock:
            @staticmethod
            def now(tz=None):
                raise RuntimeError("clock failure")

        monkeypatch.setattr(discord_mod, "datetime", BoomClock)
        svc = DiscordService()
        result = await svc.health_check()
        assert result["healthy"] is False
        assert result["status"] == "unhealthy"
        assert result["error"] == "Discord health check failed"


class TestCapabilitiesAndExecute:
    def test_get_capabilities(self):
        svc = DiscordService()
        caps = svc.get_capabilities()
        assert [op["id"] for op in caps["operations"]] == [
            "get_current_user", "get_user_guilds", "send_message",
        ]
        assert caps["supports_webhooks"] is True

    async def test_execute_get_current_user(self, discord_factory):
        svc = discord_factory(ok_handler({"id": "u1"}))
        result = await svc.execute_operation(
            "get_current_user", {"access_token": "at"}
        )
        assert result == {"success": True, "result": {"id": "u1"}}

    async def test_execute_send_message(self, discord_factory):
        svc = discord_factory(ok_handler({"id": "m1"}))
        result = await svc.execute_operation(
            "send_message", {"channel_id": "c1", "content": "hi", "access_token": "at"}
        )
        assert result["success"] is True
        assert result["result"]["id"] == "m1"

    async def test_execute_unknown_operation(self, discord_factory):
        svc = discord_factory(ok_handler())
        with pytest.raises(NotImplementedError):
            await svc.execute_operation("delete_server", {})


def make_user(db, user_id="u1", email="u1@example.com"):
    user = User(
        id=user_id,
        email=email,
        hashed_password="hashed",
        first_name="First",
        last_name="Last",
        role="admin",
        status="active",
    )
    db.add(user)
    return user


def make_agent(db, agent_id="a1", status="AUTONOMOUS", workspace_id="default"):
    agent = AgentRegistry(
        id=agent_id,
        name="Ops Agent",
        category="Operations",
        module_path="operations",
        class_name="OpsAgent",
        status=status,
        workspace_id=workspace_id,
    )
    db.add(agent)
    return agent


class TestCreateExecutionRecord:
    def test_creates_and_persists(self, db_session):
        user = make_user(db_session)
        db_session.commit()
        rec = create_execution_record(
            db_session, agent_id=None, user_id=user.id, action="send_message"
        )
        assert rec.id
        assert rec.workspace_id == "default"
        assert rec.status == "running"
        assert rec.input_summary == "Integration action: send_message"
        assert rec.triggered_by == "integration_route"
        assert rec.metadata_json == {"user_id": user.id}

        db_session.expire_all()
        fetched = db_session.query(AgentExecution).filter(AgentExecution.id == rec.id).first()
        assert fetched is not None
        assert fetched.input_summary == "Integration action: send_message"

    def test_with_agent_and_status(self, db_session):
        user = make_user(db_session, user_id="u2", email="u2@example.com")
        agent = make_agent(db_session, agent_id="a2")
        db_session.commit()
        rec = create_execution_record(
            db_session, agent_id=agent.id, user_id=user.id, action="get", status="completed"
        )
        assert rec.agent_id == "a2"
        assert rec.status == "completed"


class TestWithGovernanceCheck:
    async def test_allowed(self, db_session):
        user = make_user(db_session)
        make_agent(db_session, status="AUTONOMOUS")
        db_session.commit()
        agent, check = await with_governance_check(db_session, user, "search", agent_id="a1")
        assert agent is not None
        assert agent.id == "a1"
        assert check["allowed"] is True

    async def test_denied_raises_403(self, db_session):
        user = make_user(db_session)
        make_agent(db_session, status="paused")
        db_session.commit()
        with pytest.raises(HTTPException) as exc:
            await with_governance_check(db_session, user, "create", agent_id="a1")
        assert exc.value.status_code == 403
        assert "Agent not permitted" in exc.value.detail

    async def test_no_agent_allowed(self, db_session, monkeypatch):
        user = make_user(db_session)
        db_session.commit()

        async def fake_resolve(self, user_id=None, session_id=None, requested_agent_id=None,
                               action_type="chat"):
            return None, {"resolution_path": ["resolution_failed"], "user_id": user_id}

        from core.agent_context_resolver import AgentContextResolver
        monkeypatch.setattr(
            AgentContextResolver, "resolve_agent_for_request", fake_resolve
        )
        agent, check = await with_governance_check(db_session, user, "search", agent_id=None)
        assert agent is None
        assert check == {"allowed": True}


class TestStandardErrorResponse:
    def test_format_and_no_leak(self, caplog):
        with caplog.at_level(logging.ERROR):
            resp = standard_error_response(ValueError("postgres down: /var/lib/data"), "my_op")
        assert resp["success"] is False
        assert resp["error_type"] == "ValueError"
        assert resp["operation"] == "my_op"
        assert "postgres down" not in resp["error"]
        assert resp["error"]
        assert "my_op" in resp["error"]
