# -*- coding: utf-8 -*-
"""
Coverage-push tests for chat analytics integrations:
- integrations/slack_enhanced_service.py
- integrations/teams_enhanced_service.py
- integrations/discord_analytics_engine.py
- integrations/google_chat_analytics_engine.py

All external APIs (slack_sdk, httpx, MS Graph, redis, LLM service) are mocked.
"""

import asyncio
import base64
import fnmatch
import io
import json
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from slack_sdk.errors import SlackApiError

from integrations.slack_enhanced_service import (
    SlackChannel,
    SlackConnectionStatus,
    SlackEnhancedService,
    SlackEventType,
    SlackFile,
    SlackMessage,
    SlackRateLimiter,
    SlackWorkspace,
)
from integrations.teams_enhanced_service import (
    TeamsChannel,
    TeamsConnectionStatus,
    TeamsEnhancedService,
    TeamsMessage,
    TeamsRateLimiter,
    TeamsWorkspace,
)
from integrations.discord_analytics_engine import (
    DiscordAnalyticsDataPoint,
    DiscordAnalyticsEngine,
    DiscordAnalyticsGranularity,
    DiscordAnalyticsMetric,
    DiscordAnalyticsTimeRange,
    LLMSentiment,
    LLMTopics,
)
from integrations.google_chat_analytics_engine import (
    GoogleChatAnalyticsDataPoint,
    GoogleChatAnalyticsEngine,
    GoogleChatAnalyticsGranularity,
    GoogleChatAnalyticsMetric,
    GoogleChatAnalyticsTimeRange,
)


class FakeRedis:
    """Minimal sync redis client double (store: key -> (value, ttl))."""

    def __init__(self):
        self.store = {}

    def get(self, key):
        entry = self.store.get(key)
        return entry[0] if entry else None

    def setex(self, key, ttl, value):
        self.store[key] = (value, ttl)

    def keys(self, pattern="*"):
        return [k for k in self.store if fnmatch.fnmatch(k, pattern)]

    def delete(self, *keys):
        for k in keys:
            self.store.pop(k, None)

    def incr(self, key):
        entry = self.store.get(key)
        cur = int(entry[0]) if entry else 0
        self.store[key] = (str(cur + 1), entry[1] if entry else 0)
        return cur + 1

    def expire(self, key, ttl):
        if key in self.store:
            self.store[key] = (self.store[key][0], ttl)
        return True

    def pipeline(self):
        return _FakePipeline(self)

    def lpush(self, key, value):
        entry = self.store.setdefault(key, ([], 0))
        entry[0].insert(0, value)
        return len(entry[0])

    def ltrim(self, key, start, end):
        entry = self.store.get(key, ([], 0))
        entry[0][:] = entry[0][start:end + 1]
        return True

    def close(self):
        pass


class _FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.ops = []

    def incr(self, key):
        self.ops.append(("incr", key))
        return self

    def expire(self, key, ttl):
        self.ops.append(("expire", key, ttl))
        return self

    def execute(self):
        results = []
        for op in self.ops:
            if op[0] == "incr":
                results.append(self.redis.incr(op[1]))
            else:
                results.append(self.redis.expire(op[1], op[2]))
        self.ops = []
        return results


class FakeDB:
    """DB double returning preconfigured rows (dict or sqlite3.Row)."""

    def __init__(self, rows=None, fail_on_execute=False):
        self.rows = rows or []
        self.fail_on_execute = fail_on_execute
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if self.fail_on_execute:
            raise RuntimeError("db exploded")
        return self

    def fetchall(self):
        return [dict(row) for row in self.rows]

    def fetchone(self):
        if not self.rows:
            return None
        return dict(self.rows[0])

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def make_jwt(payload: dict) -> str:
    def b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header = b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    body = b64url(json.dumps(payload).encode())
    return f"{header}.{body}.sig"


class FakeMetricSession:
    def __init__(self):
        self.metrics = {}
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self.fail_commit = False

    def query(self, model):
        return _FakeQuery(self)

    def add(self, metric):
        pass

    def commit(self):
        if self.fail_commit:
            raise RuntimeError("commit failed")
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class _FakeQuery:
    def __init__(self, session):
        self.session = session
        self.kwargs = {}

    def filter_by(self, **kwargs):
        self.kwargs = kwargs
        return self

    def first(self):
        key = tuple(sorted(self.kwargs.items()))
        return self.session.metrics.get(key)


class FakeGraphClient:
    """Chainable fake Graph client: client.teams[ws].channels[ch].messages.get()."""

    def __init__(self, credentials=None, scopes=None, default_headers=None):
        self._default_headers = default_headers or {"Authorization": "Bearer tok"}
        self.teams = _FakeNode("teams")

    async def get(self, **kwargs):
        return None


class _FakeNode:
    def __init__(self, name):
        self._name = name
        self._children = {}
        self._return_values = {}

    def __getitem__(self, key):
        if key not in self._children:
            self._children[key] = _FakeNode(f"{self._name}[{key}]")
        return self._children[key]

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._children:
            self._children[name] = _FakeNode(f"{self._name}.{name}")
        return self._children[name]

    def set_result(self, method, value):
        self._return_values[method] = value

    async def get(self, **kwargs):
        return self._return_values.get("get")

    async def post(self, data):
        return self._return_values.get("post")


class FakeHTTPSession:
    """httpx.AsyncClient double: async context manager with post/put."""

    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, *args, **kwargs):
        return self.response

    async def put(self, *args, **kwargs):
        return self.response


class FakeHTTPResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json


# ---------------------------------------------------------------------------
# Slack rate limiter + dataclasses
# ---------------------------------------------------------------------------

class TestSlackRateLimiter:
    async def test_local_allow_then_deny(self):
        limiter = SlackRateLimiter(None)
        assert await limiter.check_limit("ws1", "chat.postMessage") is True
        assert await limiter.check_limit("ws1", "chat.postMessage") is False

    async def test_local_window_reset(self, monkeypatch):
        limiter = SlackRateLimiter(None)
        assert await limiter.check_limit("ws1", "chat.postMessage") is True
        assert await limiter.check_limit("ws1", "chat.postMessage") is False
        real_now = time.time()
        monkeypatch.setattr(
            "integrations.slack_enhanced_service.time.time",
            lambda: real_now + 5,
        )
        assert await limiter.check_limit("ws1", "chat.postMessage") is True

    async def test_history_limit_window_is_minute(self):
        limiter = SlackRateLimiter(None)
        for _ in range(50):
            assert await limiter.check_limit("ws1", "conversations.history") is True
        assert await limiter.check_limit("ws1", "conversations.history") is False

    async def test_redis_path_allow_then_deny(self):
        redis = FakeRedis()
        limiter = SlackRateLimiter(redis)
        assert await limiter.check_limit("ws1", "chat.postMessage") is True
        assert await limiter.check_limit("ws1", "chat.postMessage") is False
        assert "slack_rate:ws1:chat.postMessage" in redis.store

    async def test_unknown_endpoint_defaults(self):
        limiter = SlackRateLimiter(None)
        assert await limiter.check_limit("ws1", "unknown.endpoint") is True
        assert await limiter.check_limit("ws1", "unknown.endpoint") is False


class TestSlackDataclasses:
    def test_workspace_defaults(self):
        ws = SlackWorkspace(team_id="T1", team_name="N", domain="d", url="u")
        assert ws.scopes == []
        assert ws.settings == {}
        assert ws.is_active is True
        assert ws.created_at.tzinfo is not None

    def test_channel_defaults(self):
        ch = SlackChannel(channel_id="C1", name="n")
        assert ch.created.tzinfo is not None
        assert ch.is_private is False

    def test_message_defaults(self):
        msg = SlackMessage(
            message_id="1", text="t", user_id="U1", user_name="u",
            channel_id="C1", channel_name="c", workspace_id="W1", timestamp="1",
        )
        assert msg.reactions == []
        assert msg.files == []
        assert msg.pinned_to == []
        assert msg.blocks == []
        assert msg.mentions == []
        assert msg.metadata == {}

    def test_file_defaults(self):
        f = SlackFile(
            file_id="F1", name="n", title="t", mimetype="m", filetype="f",
            pretty_type="p", size=1, url_private="u", permalink="p",
            user_id="U1", user_name="u", timestamp="1700000000",
        )
        assert f.created == datetime.fromtimestamp(1700000000)
        assert f.metadata == {}
        assert f.is_public is False


@pytest.fixture
def slack_service(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(
        "integrations.slack_enhanced_service.redis.Redis",
        lambda *a, **k: fake_redis,
    )
    svc = SlackEnhancedService(
        tenant_id="default",
        config={
            "client_id": "cid",
            "client_secret": "cs",
            "signing_secret": "ss",
            "redirect_uri": "http://localhost/cb",
            "encryption_key": Fernet.generate_key().decode(),
            "redis": {"enabled": True},
        },
    )
    svc._fake_redis = fake_redis
    return svc


def make_slack_client():
    client = AsyncMock()
    client.close = AsyncMock()
    return client


class TestSlackServiceInit:
    def test_init_required_scopes_and_state(self, slack_service):
        assert slack_service.client_id == "cid"
        assert slack_service.cipher is not None
        assert slack_service.redis_client is not None
        assert len(slack_service.event_handlers) == len(SlackEventType)
        assert "channels:read" in slack_service.required_scopes

    def test_init_invalid_encryption_key(self, monkeypatch):
        fake_redis = FakeRedis()
        monkeypatch.setattr(
            "integrations.slack_enhanced_service.redis.Redis",
            lambda *a, **k: fake_redis,
        )
        svc = SlackEnhancedService(
            tenant_id="default",
            config={"encryption_key": "not-a-fernet-key"},
        )
        assert svc.cipher is None

    def test_init_no_redis_when_disabled(self, monkeypatch):
        monkeypatch.setattr(
            "integrations.slack_enhanced_service.redis.Redis",
            lambda *a, **k: FakeRedis(),
        )
        svc = SlackEnhancedService(tenant_id="default", config={})
        assert svc.redis_client is None

    def test_encrypt_decrypt_roundtrip(self, slack_service):
        token = "xoxb-secret-token"
        enc = slack_service._encrypt_token(token)
        assert enc != token
        assert slack_service._decrypt_token(enc) == token

    def test_encrypt_noop_without_cipher(self, monkeypatch):
        monkeypatch.setattr(
            "integrations.slack_enhanced_service.redis.Redis",
            lambda *a, **k: FakeRedis(),
        )
        svc = SlackEnhancedService(tenant_id="default", config={})
        assert svc._encrypt_token("tok") == "tok"
        assert svc._decrypt_token("tok") == "tok"

    def test_get_service_info(self, slack_service):
        info = asyncio.get_event_loop().run_until_complete(
            slack_service.get_service_info()
        )
        assert info["name"] == "Slack Enhanced Service"

    def test_get_operations_and_capabilities(self, slack_service):
        ops = slack_service.get_operations()
        assert [o["name"] for o in ops] == [
            "send_message", "get_channels", "list_users", "get_messages", "create_channel",
        ]
        caps = slack_service.get_capabilities()
        assert caps["supports_webhooks"] is True

    def test_health_check(self, slack_service):
        info = asyncio.get_event_loop().run_until_complete(slack_service.health_check())
        assert info["healthy"] is True


class TestSlackWorkspaceStore:
    def test_get_workspace_from_redis_cache(self, slack_service):
        ws = SlackWorkspace(
            team_id="T1", team_name="N", domain="d", url="u", access_token="tok",
        )
        slack_service.redis_client.setex(
            "workspace:T1", 3600, json.dumps(
                ws.__dict__, default=lambda o: o.isoformat() if isinstance(o, datetime) else str(o)
            )
        )
        found = slack_service._get_workspace("T1")
        assert found is not None
        assert found.team_id == "T1"
        assert found.access_token == "tok"

    def test_get_workspace_from_token_storage(self, slack_service, monkeypatch):
        stored = {
            "access_token": "xoxb-1",
            "bot_user_id": "B1",
            "scope": "channels:read,chat:write",
            "team": {"id": "T1", "name": "Team", "domain": "acme"},
            "authed_user": {"id": "U1"},
        }
        monkeypatch.setattr(
            "integrations.slack_enhanced_service.token_storage.get_token",
            lambda provider: stored,
        )
        found = slack_service._get_workspace("T1")
        assert found is not None
        assert found.access_token == "xoxb-1"
        assert found.scopes == ["channels:read", "chat:write"]
        assert found.url == "https://acme.slack.com"

    def test_get_workspace_none(self, slack_service, monkeypatch):
        monkeypatch.setattr(
            "integrations.slack_enhanced_service.token_storage.get_token",
            lambda provider: None,
        )
        assert slack_service._get_workspace("missing") is None

    def test_get_workspace_db_path(self, slack_service, monkeypatch):
        row = {
            "team_id": "T9", "team_name": "DB Team", "domain": "db",
            "url": "https://db.slack.com", "icon_url": None, "enterprise_id": None,
            "enterprise_name": None, "access_token": "tok", "bot_token": None,
            "user_id": None, "bot_id": None, "scopes": "[]",
            "created_at": datetime.now(timezone.utc).isoformat(), "last_sync": None,
            "is_active": 1, "settings": "{}",
        }
        db = FakeDB(rows=[row])
        monkeypatch.setattr(slack_service, "db", db)
        found = slack_service._get_workspace("T9")
        assert found is not None
        assert found.team_id == "T9"

    def test_save_workspace_redis_path(self, slack_service):
        ws = SlackWorkspace(team_id="T2", team_name="N", domain="d", url="u")
        assert slack_service._save_workspace(ws) is True
        assert "workspace:T2" in slack_service.redis_client.store
        assert slack_service.connection_status["T2"] == SlackConnectionStatus.CONNECTED

    def test_save_workspace_db_path(self, slack_service, monkeypatch):
        db = FakeDB()
        monkeypatch.setattr(slack_service, "db", db)
        ws = SlackWorkspace(team_id="T3", team_name="N", domain="d", url="u")
        assert slack_service._save_workspace(ws) is True
        assert db.executed
        assert slack_service.connection_status["T3"] == SlackConnectionStatus.CONNECTED

    def test_save_workspace_error(self, slack_service, monkeypatch):
        db = FakeDB(fail_on_execute=True)
        monkeypatch.setattr(slack_service, "db", db)
        ws = SlackWorkspace(team_id="T4", team_name="N", domain="d", url="u")
        assert slack_service._save_workspace(ws) is False


class TestSlackOAuth:
    def test_generate_oauth_url_default_scopes(self, slack_service):
        url = slack_service.generate_oauth_url("state123", "U1")
        assert url.startswith("https://slack.com/oauth/v2/authorize?")
        assert "client_id=cid" in url
        assert "state=state123" in url

    def test_generate_oauth_url_custom_scopes(self, slack_service):
        url = slack_service.generate_oauth_url("s", "U1", scopes=["chat:write"])
        assert "chat%3Awrite" in url or "chat:write" in url
        assert "channels:read" not in url

    async def test_exchange_code_success(self, slack_service, monkeypatch):
        response = FakeHTTPResponse(
            status_code=200,
            json_data={
                "ok": True,
                "access_token": "xoxb-2",
                "bot_user_id": "B1",
                "scope": "channels:read,chat:write",
                "team": {"id": "T1", "name": "Team", "domain": "acme", "icon": {"image_132": "i"}},
                "enterprise": {"id": "E1", "name": "Ent"},
                "authed_user": {"id": "U1"},
            },
        )
        monkeypatch.setattr(
            "integrations.slack_enhanced_service.httpx.AsyncClient",
            lambda *a, **k: FakeHTTPSession(response),
        )
        result = await slack_service.exchange_code_for_tokens("code", "state")
        assert result["ok"] is True
        assert result["workspace"]["team_id"] == "T1"
        assert "workspace:T1" in slack_service.redis_client.store

    async def test_exchange_code_http_error(self, slack_service, monkeypatch):
        response = FakeHTTPResponse(status_code=500, text="boom")
        monkeypatch.setattr(
            "integrations.slack_enhanced_service.httpx.AsyncClient",
            lambda *a, **k: FakeHTTPSession(response),
        )
        result = await slack_service.exchange_code_for_tokens("code", "state")
        assert result["ok"] is False
        assert result["message"] == "OAuth token exchange failed"

    async def test_exchange_code_api_error(self, slack_service, monkeypatch):
        response = FakeHTTPResponse(
            status_code=200,
            json_data={"ok": False, "error": "invalid_code"},
        )
        monkeypatch.setattr(
            "integrations.slack_enhanced_service.httpx.AsyncClient",
            lambda *a, **k: FakeHTTPSession(response),
        )
        result = await slack_service.exchange_code_for_tokens("code", "state")
        assert result["ok"] is False

    async def test_exchange_code_save_failure(self, slack_service, monkeypatch):
        response = FakeHTTPResponse(
            status_code=200,
            json_data={
                "ok": True,
                "access_token": "xoxb-3",
                "scope": "",
                "team": {"id": "T1", "name": "Team", "domain": "acme"},
                "enterprise": {},
                "authed_user": {},
            },
        )
        monkeypatch.setattr(
            "integrations.slack_enhanced_service.httpx.AsyncClient",
            lambda *a, **k: FakeHTTPSession(response),
        )
        with patch.object(slack_service, "_save_workspace", return_value=False):
            result = await slack_service.exchange_code_for_tokens("code", "state")
        assert result["ok"] is False
        assert result["error"] == "Failed to save workspace"


class TestSlackClients:
    def test_get_client_creates_and_caches(self, slack_service, monkeypatch):
        ws = SlackWorkspace(
            team_id="T1", team_name="N", domain="d", url="u",
            access_token=slack_service._encrypt_token("tok"),
        )
        monkeypatch.setattr(slack_service, "_get_workspace", lambda wid: ws)
        fake_class = MagicMock()
        monkeypatch.setattr(
            "integrations.slack_enhanced_service.AsyncWebClient", fake_class
        )
        client = slack_service._get_client("T1")
        assert client is not None
        fake_class.assert_called_once()
        assert slack_service._get_client("T1") is client

    def test_get_client_no_token(self, slack_service, monkeypatch):
        monkeypatch.setattr(slack_service, "_get_workspace", lambda wid: None)
        assert slack_service._get_client("T1") is None

    def test_get_client_error(self, slack_service, monkeypatch):
        ws = SlackWorkspace(
            team_id="T1", team_name="N", domain="d", url="u",
            access_token=slack_service._encrypt_token("tok"),
        )
        monkeypatch.setattr(slack_service, "_get_workspace", lambda wid: ws)
        monkeypatch.setattr(
            "integrations.slack_enhanced_service.AsyncWebClient",
            MagicMock(side_effect=RuntimeError("boom")),
        )
        assert slack_service._get_client("T1") is None

    def test_get_sync_client(self, slack_service, monkeypatch):
        ws = SlackWorkspace(
            team_id="T1", team_name="N", domain="d", url="u",
            access_token=slack_service._encrypt_token("tok"),
        )
        monkeypatch.setattr(slack_service, "_get_workspace", lambda wid: ws)
        fake_class = MagicMock()
        monkeypatch.setattr("integrations.slack_enhanced_service.WebClient", fake_class)
        client = slack_service._get_sync_client("T1")
        assert client is not None
        assert slack_service._get_sync_client("T1") is client

    def test_get_sync_client_no_token(self, slack_service, monkeypatch):
        monkeypatch.setattr(slack_service, "_get_workspace", lambda wid: None)
        assert slack_service._get_sync_client("T1") is None


class TestSlackConnection:
    async def test_test_connection_success(self, slack_service):
        client = make_slack_client()
        client.auth_test.return_value = {
            "ok": True, "team_id": "T1", "team": "Team", "user_id": "U1",
            "user": "u", "bot_id": "B1",
        }
        slack_service.clients["T1"] = client
        result = await slack_service.test_connection("T1")
        assert result["connected"] is True
        assert result["workspace"]["team_id"] == "T1"
        assert slack_service.connection_status["T1"] == SlackConnectionStatus.CONNECTED

    async def test_test_connection_no_client(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        result = await svc.test_connection("missing")
        assert result["connected"] is False
        assert result["status"] == "error"

    async def test_test_connection_not_ok(self, slack_service):
        client = make_slack_client()
        client.auth_test.return_value = {"ok": False, "error": "invalid_auth"}
        slack_service.clients["T1"] = client
        result = await slack_service.test_connection("T1")
        assert result["connected"] is False
        assert result["error"] == "invalid_auth"

    async def test_test_connection_ratelimited(self, slack_service):
        client = make_slack_client()
        client.auth_test.side_effect = SlackApiError(
            "ratelimited",
            response={"data": {"error": "ratelimited"}, "headers": {"Retry-After": "30"}},
        )
        slack_service.clients["T1"] = client
        result = await slack_service.test_connection("T1")
        assert result["connected"] is False
        assert result["status"] == "rate_limited"
        assert slack_service.connection_status["T1"] == SlackConnectionStatus.RATE_LIMITED

    async def test_test_connection_slack_response_error(self, slack_service):
        client = make_slack_client()
        fake_response = type(
            "SlackResponse",
            (),
            {"data": {"error": "invalid_auth"}, "headers": {"Retry-After": "5"}},
        )()
        client.auth_test.side_effect = SlackApiError("invalid_auth", response=fake_response)
        slack_service.clients["T1"] = client
        result = await slack_service.test_connection("T1")
        assert result["connected"] is False
        assert result["status"] == "error"

    async def test_test_connection_generic_error(self, slack_service):
        client = make_slack_client()
        client.auth_test.side_effect = RuntimeError("network down")
        slack_service.clients["T1"] = client
        result = await slack_service.test_connection("T1")
        assert result["connected"] is False
        assert result["status"] == "error"


class TestSlackChannels:
    async def test_get_channels_success(self, slack_service):
        client = make_slack_client()
        client.conversations_list.return_value = {
            "ok": True,
            "channels": [
                {
                    "id": "C1", "name": "general", "purpose": {"value": "p"},
                    "topic": {"value": "t"}, "is_private": False, "is_archived": False,
                    "is_general": True, "is_shared": False, "is_im": False, "is_mpim": False,
                    "num_members": 5, "created": 1700000000,
                }
            ],
        }
        slack_service.clients["T1"] = client
        channels = await slack_service.get_channels("T1", include_private=True, limit=50)
        assert len(channels) == 1
        assert channels[0].channel_id == "C1"
        assert channels[0].workspace_id == "T1"
        assert "channels:T1" in slack_service.redis_client.store

    async def test_get_channels_no_client(self, slack_service):
        result = await slack_service.get_channels("missing")
        assert result == []

    async def test_get_channels_not_ok(self, slack_service):
        client = make_slack_client()
        client.conversations_list.return_value = {"ok": False, "error": "missing_scope"}
        slack_service.clients["T1"] = client
        assert await slack_service.get_channels("T1") == []

    async def test_get_channels_api_error_cached_fallback(self, slack_service):
        cached = [
            {"channel_id": "C1", "name": "general", "display_name": "general",
             "purpose": None, "topic": None, "is_private": False, "is_archived": False,
             "is_general": False, "is_shared": False, "is_im": False, "is_mpim": False,
             "workspace_id": "T1", "num_members": 0, "created": datetime.now(timezone.utc),
             "last_read": None, "unread_count": 0, "is_muted": False},
        ]
        slack_service.redis_client.setex(
            "channels:T1", 1800, json.dumps(cached, default=str)
        )
        client = make_slack_client()
        client.conversations_list.side_effect = SlackApiError("ratelimited", response=None)
        slack_service.clients["T1"] = client
        channels = await slack_service.get_channels("T1")
        assert len(channels) == 1
        assert channels[0].channel_id == "C1"

    async def test_get_channels_unexpected_error(self, slack_service):
        client = make_slack_client()
        client.conversations_list.side_effect = RuntimeError("boom")
        slack_service.clients["T1"] = client
        assert await slack_service.get_channels("T1") == []

    async def test_get_channels_rate_limited(self, slack_service):
        client = make_slack_client()
        slack_service.clients["T1"] = client
        for _ in range(2):
            await slack_service.rate_limiter.check_limit("T1", "conversations.list")
        assert await slack_service.get_channels("T1") == []

    async def test_get_workspaces_redis(self, slack_service):
        ws = SlackWorkspace(team_id="T1", team_name="N", domain="d", url="u", user_id="U1")
        slack_service.redis_client.setex("workspace:T1", 3600, json.dumps(ws.__dict__, default=str))
        result = await slack_service.get_workspaces()
        assert len(result) == 1
        result = await slack_service.get_workspaces(user_id="U2")
        assert result == []

    async def test_get_workspaces_db(self, slack_service, monkeypatch):
        row = {
            "team_id": "T9", "team_name": "DB Team", "domain": "db",
            "url": "https://db.slack.com", "icon_url": None, "enterprise_id": None,
            "enterprise_name": None, "access_token": "tok", "bot_token": None,
            "user_id": "U1", "bot_id": None, "scopes": "[]",
            "created_at": datetime.now(timezone.utc).isoformat(), "last_sync": None,
            "is_active": 1, "settings": "{}",
        }
        db = FakeDB(rows=[row])
        monkeypatch.setattr(slack_service, "db", db)
        assert len(await slack_service.get_workspaces()) == 1
        assert len(await slack_service.get_workspaces(user_id="U1")) == 1

    async def test_get_workspaces_error(self, slack_service, monkeypatch):
        db = FakeDB(fail_on_execute=True)
        monkeypatch.setattr(slack_service, "db", db)
        assert await slack_service.get_workspaces() == []


class TestSlackMessaging:
    async def test_send_message_success_with_extras(self, slack_service):
        client = make_slack_client()
        client.chat_postMessage.return_value = {
            "ok": True, "ts": "123.456", "channel": "C1",
            "message": {"ts": "123.456", "text": "hi"},
        }
        slack_service.clients["T1"] = client
        result = await slack_service.send_message(
            "T1", "C1", "hi", thread_ts="111.222", blocks=[{"type": "section"}],
            attachments=[{"text": "a"}],
        )
        assert result["ok"] is True
        assert result["message_id"] == "123.456"
        kwargs = client.chat_postMessage.call_args.kwargs
        assert kwargs["thread_ts"] == "111.222"
        assert kwargs["blocks"] == [{"type": "section"}]

    async def test_send_message_caches_with_redis(self, slack_service):
        client = make_slack_client()
        client.chat_postMessage.return_value = {
            "ok": True, "ts": "123.456", "channel": "C1",
            "message": {"ts": "123.456", "text": "hi"},
        }
        slack_service.clients["T1"] = client
        result = await slack_service.send_message("T1", "C1", "hi")
        assert result["ok"] is True
        assert slack_service.redis_client.get("message:T1:123.456") is not None

    async def test_send_message_not_ok(self, slack_service):
        client = make_slack_client()
        client.chat_postMessage.return_value = {"ok": False, "error": "too_many"}
        slack_service.clients["T1"] = client
        result = await slack_service.send_message("T1", "C1", "hi")
        assert result["ok"] is False

    async def test_send_message_no_client(self, slack_service):
        result = await slack_service.send_message("missing", "C1", "hi")
        assert result["ok"] is False

    async def test_send_message_rate_limited(self, slack_service):
        client = make_slack_client()
        slack_service.clients["T1"] = client
        await slack_service.rate_limiter.check_limit("T1", "chat.postMessage")
        result = await slack_service.send_message("T1", "C1", "hi")
        assert result["ok"] is False

    async def test_send_message_unexpected_error(self, slack_service):
        client = make_slack_client()
        client.chat_postMessage.side_effect = RuntimeError("boom")
        slack_service.clients["T1"] = client
        result = await slack_service.send_message("T1", "C1", "hi")
        assert result["ok"] is False
        assert result["message"] == "Unexpected error occurred"


class TestSlackHistory:
    async def test_get_channel_history_success(self, slack_service):
        client = make_slack_client()
        client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                {
                    "ts": "1.1", "text": "hello <@U123ABC>", "user": "U1",
                    "thread_ts": "1.0", "reply_count": 2, "type": "message",
                    "reactions": [], "files": [], "pinned_to": [], "is_starred": False,
                    "edited": {"ts": "1.2"}, "blocks": [],
                    "bot_profile": None,
                },
                {
                    "ts": "2.1", "text": "plain", "user": "U2", "type": "message",
                    "reactions": [], "files": [], "pinned_to": [],
                },
            ],
        }
        slack_service.clients["T1"] = client
        messages = await slack_service.get_channel_history(
            "T1", "C1", latest="3.0", oldest="1.0", include_threads=False
        )
        assert len(messages) == 2
        assert messages[0].mentions == ["U123ABC"]
        assert messages[0].is_edited is True
        assert messages[0].edit_timestamp == "1.2"
        assert "messages:T1:C1" in slack_service.redis_client.store

    async def test_get_channel_history_no_client(self, slack_service):
        assert await slack_service.get_channel_history("missing", "C1") == []

    async def test_get_channel_history_not_ok(self, slack_service):
        client = make_slack_client()
        client.conversations_history.return_value = {"ok": False, "error": "x"}
        slack_service.clients["T1"] = client
        assert await slack_service.get_channel_history("T1", "C1") == []

    async def test_get_channel_history_rate_limited(self, slack_service):
        client = make_slack_client()
        slack_service.clients["T1"] = client
        for _ in range(50):
            await slack_service.rate_limiter.check_limit("T1", "conversations.history")
        assert await slack_service.get_channel_history("T1", "C1") == []

    async def test_get_channel_history_error(self, slack_service):
        client = make_slack_client()
        client.conversations_history.side_effect = RuntimeError("boom")
        slack_service.clients["T1"] = client
        assert await slack_service.get_channel_history("T1", "C1") == []

    async def test_extract_mentions(self, slack_service):
        assert slack_service._extract_mentions(
            "hi <@U123ABC> and <@W456XYZ>"
        ) == ["U123ABC", "W456XYZ"]
        assert slack_service._extract_mentions("no mentions") == []


class TestSlackFiles:
    async def test_upload_file_success(self, slack_service):
        client = make_slack_client()
        client.files_upload_v2.return_value = {
            "ok": True,
            "file": {
                "id": "F1", "name": "n.txt", "title": "t", "mimetype": "text/plain",
                "filetype": "text", "pretty_type": "Plain Text", "size": 3,
                "url_private": "u", "url_private_download": "d", "permalink": "p",
                "permalink_public": "pp", "user": "U1", "timestamp": "1700000000",
                "is_public": True, "is_editable": False, "external_type": None,
                "external_url": None,
            },
        }
        slack_service.clients["T1"] = client
        result = await slack_service.upload_file("T1", "C1", "/tmp/f.txt", title="t", initial_comment="c")
        assert result["ok"] is True
        assert result["file"]["file_id"] == "F1"
        assert "file:T1:F1" in slack_service.redis_client.store

    async def test_upload_file_not_ok(self, slack_service):
        client = make_slack_client()
        client.files_upload_v2.return_value = {"ok": False, "error": "quota"}
        slack_service.clients["T1"] = client
        result = await slack_service.upload_file("T1", "C1", "/tmp/f.txt")
        assert result["ok"] is False

    async def test_upload_file_no_client(self, slack_service):
        result = await slack_service.upload_file("missing", "C1", "/tmp/f.txt")
        assert result["ok"] is False

    async def test_upload_file_error(self, slack_service):
        client = make_slack_client()
        client.files_upload_v2.side_effect = RuntimeError("boom")
        slack_service.clients["T1"] = client
        result = await slack_service.upload_file("T1", "C1", "/tmp/f.txt")
        assert result["ok"] is False
        assert result["message"] == "Unexpected error occurred"


class TestSlackSearch:
    async def test_search_messages_success(self, slack_service):
        client = make_slack_client()
        client.search_messages.return_value = {
            "ok": True,
            "messages": {
                "matches": [
                    {
                        "ts": "1.1", "text": "hi <@U123ABC>", "user": "U1",
                        "channel": {"id": "C1", "name": "general"},
                        "thread_ts": None, "reply_count": 0, "reactions": [],
                        "files": [], "pinned_to": [], "is_starred": False,
                        "blocks": [], "score": 0.9,
                    }
                ],
                "total": 1,
                "paging": {"page": 1},
            },
        }
        slack_service.clients["T1"] = client
        result = await slack_service.search_messages("T1", "hi", channel_id="C1", user_id="U1")
        assert result["ok"] is True
        assert result["total"] == 1
        assert result["messages"][0].metadata == {"search_score": 0.9}
        assert result["messages"][0].mentions == ["U123ABC"]

    async def test_search_messages_not_ok(self, slack_service):
        client = make_slack_client()
        client.search_messages.return_value = {"ok": False, "error": "x"}
        slack_service.clients["T1"] = client
        result = await slack_service.search_messages("T1", "hi")
        assert result["ok"] is False

    async def test_search_messages_error(self, slack_service):
        client = make_slack_client()
        client.search_messages.side_effect = RuntimeError("boom")
        slack_service.clients["T1"] = client
        result = await slack_service.search_messages("T1", "hi")
        assert result["ok"] is False


class TestSlackReactionsPinsDmChannels:
    async def test_add_reaction_success(self, slack_service):
        client = make_slack_client()
        client.reactions_add.return_value = {"ok": True}
        slack_service.clients["T1"] = client
        result = await slack_service.add_reaction("T1", "C1", "123.456", ":thumbsup:")
        assert result["ok"] is True
        assert result["reaction"] == "thumbsup"
        assert client.reactions_add.call_args.kwargs["name"] == "thumbsup"

    async def test_add_reaction_not_ok(self, slack_service):
        client = make_slack_client()
        client.reactions_add.return_value = {"ok": False, "error": "no_reaction"}
        slack_service.clients["T1"] = client
        result = await slack_service.add_reaction("T1", "C1", "123.456", "thumbsup")
        assert result["ok"] is False

    async def test_add_reaction_error(self, slack_service):
        client = make_slack_client()
        client.reactions_add.side_effect = RuntimeError("boom")
        slack_service.clients["T1"] = client
        result = await slack_service.add_reaction("T1", "C1", "123.456", "thumbsup")
        assert result["ok"] is False

    async def test_send_dm_success(self, slack_service):
        client = make_slack_client()
        client.conversations_open.return_value = {"ok": True, "channel": {"id": "D1"}}
        client.chat_postMessage.return_value = {
            "ok": True, "message": {"ts": "1.1"},
        }
        slack_service.clients["T1"] = client
        result = await slack_service.send_dm(
            "T1", "U1", "hello", blocks=[{"type": "section"}], unfurl_links=False
        )
        assert result["ok"] is True
        assert result["channel"] == "D1"
        assert client.chat_postMessage.call_args.kwargs["unfurl_links"] is False

    async def test_send_dm_open_fails(self, slack_service):
        client = make_slack_client()
        client.conversations_open.return_value = {"ok": False, "error": "cant_open"}
        slack_service.clients["T1"] = client
        result = await slack_service.send_dm("T1", "U1", "hello")
        assert result["ok"] is False

    async def test_send_dm_post_fails(self, slack_service):
        client = make_slack_client()
        client.conversations_open.return_value = {"ok": True, "channel": {"id": "D1"}}
        client.chat_postMessage.return_value = {"ok": False, "error": "x"}
        slack_service.clients["T1"] = client
        result = await slack_service.send_dm("T1", "U1", "hello")
        assert result["ok"] is False

    async def test_create_channel_success_with_description(self, slack_service):
        client = make_slack_client()
        client.conversations_create.return_value = {
            "ok": True,
            "channel": {"id": "C9", "name": "newch", "is_private": False, "created": 1700000000},
        }
        client.conversations_setTopic.return_value = {"ok": True}
        slack_service.clients["T1"] = client
        result = await slack_service.create_channel("T1", "newch", is_private=True, description="desc")
        assert result["ok"] is True
        assert result["channel_id"] == "C9"
        client.conversations_setTopic.assert_awaited_once()

    async def test_create_channel_not_ok(self, slack_service):
        client = make_slack_client()
        client.conversations_create.return_value = {"ok": False, "error": "name_taken"}
        slack_service.clients["T1"] = client
        result = await slack_service.create_channel("T1", "newch")
        assert result["ok"] is False

    async def test_pin_message_success(self, slack_service):
        client = make_slack_client()
        client.pins_add.return_value = {"ok": True}
        slack_service.clients["T1"] = client
        result = await slack_service.pin_message("T1", "C1", "123.456")
        assert result["ok"] is True

    async def test_pin_message_not_ok(self, slack_service):
        client = make_slack_client()
        client.pins_add.return_value = {"ok": False, "error": "already_pinned"}
        slack_service.clients["T1"] = client
        result = await slack_service.pin_message("T1", "C1", "123.456")
        assert result["ok"] is False


class TestSlackInvite:
    async def test_invite_to_channel_success_and_partial_failure(self, slack_service, monkeypatch):
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())
        client = make_slack_client()

        async def invite_side_effect(channel, users):
            if users == ["U2"]:
                return {"ok": False, "error": "not_in_channel"}
            return {"ok": True}

        client.conversations_invite.side_effect = invite_side_effect
        slack_service.clients["T1"] = client
        result = await slack_service.invite_to_channel("T1", "C1", ["U1", "U2", "U3"])
        assert result["ok"] is True
        assert result["invited_users"] == ["U1", "U3"]
        assert len(result["failed_users"]) == 1

    async def test_invite_to_channel_api_error_per_user(self, slack_service, monkeypatch):
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())
        client = make_slack_client()

        async def invite_side_effect(channel, users):
            raise SlackApiError("invalid_user", response=None)

        client.conversations_invite.side_effect = invite_side_effect
        slack_service.clients["T1"] = client
        result = await slack_service.invite_to_channel("T1", "C1", ["U1"])
        assert result["ok"] is False
        assert len(result["failed_users"]) == 1

    async def test_invite_to_channel_no_client_returns_error(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        result = await svc.invite_to_channel("missing", "C1", ["U1"])
        assert result["ok"] is False
        assert result["invited_users"] == []
        assert result["failed_users"] == []

    async def test_invite_to_channel_empty_list(self, slack_service):
        client = make_slack_client()
        slack_service.clients["T1"] = client
        result = await slack_service.invite_to_channel("T1", "C1", [])
        assert result["ok"] is False


class TestSlackWebhooks:
    async def test_verify_webhook_signature_valid(self, slack_service):
        import hashlib
        import hmac as hmac_mod

        timestamp = str(int(time.time()))
        body = b'{"type":"url_verification"}'
        sig_basestring = f"v0:{timestamp}:{body.decode()}"
        expected = "v0=" + hmac_mod.new(
            slack_service.signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256,
        ).hexdigest()
        assert await slack_service.verify_webhook_signature(body, timestamp, expected) is True

    async def test_verify_webhook_signature_replay(self, slack_service):
        old_ts = str(int(time.time()) - 600)
        assert await slack_service.verify_webhook_signature(b"{}", old_ts, "v0=deadbeef") is False

    async def test_verify_webhook_signature_no_secret(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        assert await svc.verify_webhook_signature(b"{}", "1", "v0=x") is False

    async def test_verify_webhook_signature_mismatch(self, slack_service):
        assert await slack_service.verify_webhook_signature(
            b"{}", str(int(time.time())), "v0=wrong"
        ) is False

    async def test_verify_webhook_signature_bad_timestamp(self, slack_service):
        assert await slack_service.verify_webhook_signature(
            b"{}", "not-a-number", "v0=x"
        ) is False

    async def test_handle_webhook_event_dispatches_with_redis(self, slack_service):
        called = []

        async def handler(event_data):
            called.append(event_data)

        slack_service.register_event_handler(SlackEventType.MESSAGE, handler)
        result = await slack_service.handle_webhook_event(
            {"team_id": "T1", "event": {"type": "message", "text": "hi"}}
        )
        assert result["ok"] is True
        assert len(called) == 1
        assert "slack_events:T1" in slack_service.redis_client.store

    async def test_handle_webhook_event_unknown_type(self, slack_service):
        result = await slack_service.handle_webhook_event(
            {"team_id": "T1", "event": {"type": "unknown_type"}}
        )
        assert result["ok"] is True
        assert result["event_type"] == "unknown_type"

    async def test_handle_webhook_event_handler_exception(self, slack_service):
        async def bad_handler(event_data):
            raise RuntimeError("handler boom")

        async def good_handler(event_data):
            pass

        slack_service.register_event_handler(SlackEventType.MESSAGE, bad_handler)
        slack_service.register_event_handler(SlackEventType.MESSAGE, good_handler)
        result = await slack_service.handle_webhook_event(
            {"team_id": "T1", "event": {"type": "message"}}
        )
        assert result["ok"] is True

    async def test_handle_webhook_event_webhook_handlers(self, slack_service):
        called = []

        async def wh(event_data):
            called.append(event_data)

        slack_service.register_webhook_handler(wh)
        result = await slack_service.handle_webhook_event(
            {"team_id": "T1", "event": {"type": "message"}}
        )
        assert result["ok"] is True
        assert len(called) == 1

    async def test_handle_webhook_event_internal_error(self, slack_service):
        slack_service.redis_client = object()
        result = await slack_service.handle_webhook_event(
            {"team_id": "T1", "event": {"type": "message"}}
        )
        assert result["ok"] is False

    async def test_register_handlers_dedupe(self, slack_service):
        async def handler(data):
            pass

        slack_service.register_event_handler(SlackEventType.MENTION, handler)
        slack_service.register_event_handler(SlackEventType.MENTION, handler)
        assert len(slack_service.event_handlers[SlackEventType.MENTION]) == 1
        slack_service.register_webhook_handler(handler)
        slack_service.register_webhook_handler(handler)
        assert len(slack_service.webhook_handlers) == 1


class TestSlackCache:
    async def test_cache_message_no_redis(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        await svc._cache_message("T1", {"ts": "1.1"})

    async def test_cache_message_error(self, slack_service):
        slack_service.redis_client = object()
        await slack_service._cache_message("T1", {"ts": "1.1"})

    async def test_cache_messages(self, slack_service):
        msg = SlackMessage(
            message_id="1", text="t", user_id="U1", user_name="u",
            channel_id="C1", channel_name="c", workspace_id="W1", timestamp="1",
        )
        await slack_service._cache_messages("T1", "C1", [msg])
        assert slack_service.redis_client.get("messages:T1:C1") is not None

    async def test_cache_file(self, slack_service):
        f = SlackFile(
            file_id="F1", name="n", title="t", mimetype="m", filetype="f",
            pretty_type="p", size=1, url_private="u", permalink="p",
            user_id="U1", user_name="u", timestamp="1700000000",
        )
        await slack_service._cache_file("T1", f)
        assert slack_service.redis_client.get("file:T1:F1") is not None


class TestSlackAnalytics:
    async def test_get_analytics_success(self, slack_service):
        client = make_slack_client()
        client.conversations_list.return_value = {
            "ok": True,
            "channels": [{"id": "C1"}, {"id": "C2"}],
        }
        client.conversations_history.return_value = {
            "ok": True, "messages": [{"ts": "1"}, {"ts": "2"}],
        }
        slack_service.clients["T1"] = client
        result = await slack_service.get_analytics("T1")
        assert result["channel_count"] == 2
        assert result["message_count"] == 80

    async def test_get_analytics_rate_limited(self, slack_service):
        client = make_slack_client()
        slack_service.clients["T1"] = client
        await slack_service.rate_limiter.check_limit("T1", "conversations.list")
        result = await slack_service.get_analytics("T1")
        assert result == {"error": "Rate limit exceeded"}

    async def test_get_analytics_no_client(self, slack_service):
        result = await slack_service.get_analytics("missing")
        assert result == {"error": "Not authenticated"}

    async def test_get_analytics_error(self, slack_service):
        client = make_slack_client()
        client.conversations_list.side_effect = RuntimeError("boom")
        slack_service.clients["T1"] = client
        result = await slack_service.get_analytics("T1")
        assert "error" in result

    async def test_sync_to_postgres_cache_success(self, slack_service, monkeypatch):
        import core.database
        import core.models

        session = FakeMetricSession()
        monkeypatch.setattr(core.database, "SessionLocal", lambda: session)
        monkeypatch.setattr(core.models, "IntegrationMetric", MagicMock())

        client = make_slack_client()
        client.conversations_list.return_value = {"ok": True, "channels": [{"id": "C1"}]}
        client.conversations_history.return_value = {"ok": True, "messages": []}
        slack_service.clients["T1"] = client

        result = await slack_service.sync_to_postgres_cache("T1")
        assert result["success"] is True
        assert result["metrics_synced"] == 3
        assert session.committed is True
        assert session.closed is True

    async def test_sync_to_postgres_cache_updates_existing(self, slack_service, monkeypatch):
        import core.database
        import core.models

        existing = SimpleNamespace(value=1, last_synced_at=None)
        session = FakeMetricSession()
        session.metrics[
            ("integration_type", "slack"),
            ("metric_key", "slack_channel_count"),
            ("workspace_id", "T1"),
        ] = existing
        monkeypatch.setattr(core.database, "SessionLocal", lambda: session)
        monkeypatch.setattr(core.models, "IntegrationMetric", MagicMock())

        client = make_slack_client()
        client.conversations_list.return_value = {"ok": True, "channels": []}
        slack_service.clients["T1"] = client

        result = await slack_service.sync_to_postgres_cache("T1")
        assert result["success"] is True
        assert existing.value == 0

    async def test_sync_to_postgres_cache_analytics_error(self, slack_service):
        result = await slack_service.sync_to_postgres_cache("missing")
        assert result["success"] is False

    async def test_sync_to_postgres_cache_commit_failure_reports_failure(
        self, slack_service, monkeypatch
    ):
        import core.database
        import core.models

        session = FakeMetricSession()
        session.fail_commit = True
        monkeypatch.setattr(core.database, "SessionLocal", lambda: session)
        monkeypatch.setattr(core.models, "IntegrationMetric", MagicMock())

        client = make_slack_client()
        client.conversations_list.return_value = {"ok": True, "channels": []}
        slack_service.clients["T1"] = client

        result = await slack_service.sync_to_postgres_cache("T1")
        assert result["success"] is False
        assert session.rolled_back is True

    async def test_full_sync(self, slack_service, monkeypatch):
        monkeypatch.setattr(
            slack_service, "sync_to_postgres_cache",
            AsyncMock(return_value={"success": True, "metrics_synced": 3}),
        )
        result = await slack_service.full_sync("T1", "team-1")
        assert result["success"] is True
        assert result["team_id"] == "team-1"


class TestSlackExecute:
    async def test_execute_operation_send_message(self, slack_service):
        client = make_slack_client()
        client.chat_postMessage.return_value = {
            "ok": True, "ts": "1.1", "channel": "C1", "message": {"ts": "1.1"},
        }
        slack_service.clients["T1"] = client
        with patch.object(slack_service, "config", {"workspace_id": "T1"}):
            result = await slack_service.execute_operation(
                "send_message", {"channel": "C1", "text": "hi", "thread_ts": "2.2"}
            )
        assert result["success"] is True

    async def test_execute_operation_missing_params(self, slack_service):
        result = await slack_service.execute_operation("send_message", {"channel": "C1"})
        assert result["success"] is False

    async def test_execute_operation_send_failure(self, slack_service):
        with patch.object(
            slack_service, "send_message",
            AsyncMock(return_value={"ok": False, "error": "e"}),
        ):
            result = await slack_service.execute_operation(
                "send_message", {"channel": "C1", "text": "hi"}
            )
        assert result["success"] is False

    async def test_execute_operation_unsupported(self, slack_service):
        result = await slack_service.execute_operation("frobnicate", {})
        assert result["success"] is False

    async def test_close(self, slack_service):
        client = make_slack_client()
        slack_service.clients["T1"] = client
        slack_service.sync_clients["T1"] = MagicMock()
        await slack_service.close()
        client.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# Teams rate limiter + dataclasses
# ---------------------------------------------------------------------------

class TestTeamsRateLimiter:
    async def test_local_allow_then_deny(self):
        limiter = TeamsRateLimiter(None)
        for _ in range(30):
            assert await limiter.check_limit("ws1", "messages_send") is True
        assert await limiter.check_limit("ws1", "messages_send") is False

    async def test_local_window_reset(self, monkeypatch):
        limiter = TeamsRateLimiter(None)
        await limiter.check_limit("ws1", "messages_send")
        real_now = time.time()
        monkeypatch.setattr(
            "integrations.teams_enhanced_service.time.time",
            lambda: real_now + 70,
        )
        assert await limiter.check_limit("ws1", "messages_send") is True

    async def test_redis_path(self):
        redis = FakeRedis()
        limiter = TeamsRateLimiter(redis)
        for _ in range(30):
            assert await limiter.check_limit("ws1", "messages_send") is True
        assert await limiter.check_limit("ws1", "messages_send") is False

    async def test_unknown_endpoint_default(self):
        limiter = TeamsRateLimiter(None)
        for _ in range(10):
            assert await limiter.check_limit("ws1", "unknown") is True
        assert await limiter.check_limit("ws1", "unknown") is False


class TestTeamsDataclasses:
    def test_workspace_defaults(self):
        ws = TeamsWorkspace(
            team_id="T1", name="N", description="d", display_name="D",
            visibility="public", mail_nickname="n", created_at=datetime.now(timezone.utc),
            created_by="U1", tenant_id="TEN",
        )
        assert ws.scopes == []
        assert ws.settings == {}
        assert ws.is_active is True

    def test_channel_defaults(self):
        ch = TeamsChannel(
            channel_id="C1", name="n", display_name="D", description="d",
            workspace_id="W1", channel_type="standard",
        )
        assert ch.created_at.tzinfo is not None

    def test_message_defaults(self):
        msg = TeamsMessage(
            message_id="1", text="t", user_id="U1", user_name="u", user_email="e",
            channel_id="C1", workspace_id="W1", tenant_id="TEN", timestamp="1",
        )
        assert msg.policy_violations == []
        assert msg.attachments == []
        assert msg.mentions == []
        assert msg.reactions == []
        assert msg.files == []
        assert msg.localized == {}
        assert msg.channel_identity == {}


@pytest.fixture
def teams_service(monkeypatch):
    svc = TeamsEnhancedService(
        tenant_id="default",
        config={
            "client_id": "cid",
            "client_secret": "cs",
            "redirect_uri": "http://localhost/cb",
            "encryption_key": Fernet.generate_key().decode(),
            "redis": {"client": FakeRedis()},
        },
    )
    return svc


def make_teams_client():
    return FakeGraphClient()


class TestTeamsServiceInit:
    def test_init_with_msal(self, monkeypatch):
        import types as _types

        class FakeCCApp:
            def __init__(self, *a, **k):
                self.client_id = k.get("client_id")

            def get_authorization_request_url(self, **k):
                return "https://login.microsoftonline.com/authorize"

        monkeypatch.setattr(
            "integrations.teams_enhanced_service.msal",
            _types.SimpleNamespace(ConfidentialClientApplication=FakeCCApp),
        )
        svc = TeamsEnhancedService(
            tenant_id="default",
            config={"client_id": "cid", "client_secret": "cs", "msal_tenant_id": "TEN"},
        )
        assert svc.msal_app is not None

    def test_init_msal_missing(self, teams_service):
        assert teams_service.msal_app is None

    def test_init_encryption_key_missing(self, monkeypatch):
        svc = TeamsEnhancedService(tenant_id="default", config={})
        assert svc.cipher is None

    def test_encrypt_token_requires_cipher(self):
        svc = TeamsEnhancedService(tenant_id="default", config={})
        with pytest.raises(RuntimeError):
            svc._encrypt_token("tok")

    def test_decrypt_token_without_cipher(self):
        svc = TeamsEnhancedService(tenant_id="default", config={})
        assert svc._decrypt_token("tok") == "tok"

    def test_encrypt_decrypt_roundtrip(self, teams_service):
        enc = teams_service._encrypt_token("tok")
        assert enc != "tok"
        assert teams_service._decrypt_token(enc) == "tok"

    def test_get_service_info(self, teams_service):
        info = asyncio.get_event_loop().run_until_complete(teams_service.get_service_info())
        assert info["name"] == "Microsoft Teams Enhanced Service"

    def test_get_capabilities(self, teams_service):
        caps = teams_service.get_capabilities()
        assert caps["required_params"] == ["access_token"]
        assert caps["supports_webhooks"] is True

    def test_health_check_healthy(self, teams_service):
        result = teams_service.health_check()
        assert result["ok"] is True

    def test_health_check_unhealthy(self, monkeypatch):
        svc = TeamsEnhancedService(tenant_id="default", config={})
        result = svc.health_check()
        assert result["ok"] is False


class TestTeamsWorkspaceStore:
    def test_get_workspace_from_redis(self, teams_service):
        ws = TeamsWorkspace(
            team_id="T1", name="N", description="d", display_name="D",
            visibility="public", mail_nickname="n", created_at=datetime.now(timezone.utc),
            created_by="U1", tenant_id="TEN", access_token="tok",
        )
        teams_service.redis_client.setex(
            "teams_workspace:T1", 3600, json.dumps(ws.__dict__, default=str)
        )
        found = teams_service._get_workspace("T1")
        assert found is not None
        assert found.team_id == "T1"

    def test_get_workspace_none(self, teams_service):
        assert teams_service._get_workspace("missing") is None

    def test_get_workspace_db_path(self, teams_service, monkeypatch):
        row = {
            "team_id": "T9", "name": "N", "description": "d", "display_name": "D",
            "visibility": "public", "mail_nickname": "n",
            "created_at": datetime.now(timezone.utc).isoformat(), "created_by": "U1",
            "tenant_id": "TEN", "internal_id": None, "classification": None,
            "specialization": None, "web_url": None, "access_token": "tok",
            "refresh_token": None, "scopes": "[]", "last_sync": None, "is_active": 1,
            "settings": "{}", "member_count": 0, "channel_count": 0,
        }
        db = FakeDB(rows=[row])
        monkeypatch.setattr(teams_service, "db", db)
        found = teams_service._get_workspace("T9")
        assert found is not None
        assert found.team_id == "T9"

    def test_save_workspace_redis(self, teams_service):
        ws = TeamsWorkspace(
            team_id="T2", name="N", description="d", display_name="D",
            visibility="public", mail_nickname="n", created_at=datetime.now(timezone.utc),
            created_by="U1", tenant_id="TEN",
        )
        assert teams_service._save_workspace(ws) is True
        assert "teams_workspace:T2" in teams_service.redis_client.store
        assert teams_service.connection_status["T2"] == TeamsConnectionStatus.CONNECTED

    def test_save_workspace_db(self, teams_service, monkeypatch):
        db = FakeDB()
        monkeypatch.setattr(teams_service, "db", db)
        ws = TeamsWorkspace(
            team_id="T3", name="N", description="d", display_name="D",
            visibility="public", mail_nickname="n", created_at=datetime.now(timezone.utc),
            created_by="U1", tenant_id="TEN",
        )
        assert teams_service._save_workspace(ws) is True
        assert db.executed

    def test_save_workspace_error(self, teams_service, monkeypatch):
        db = FakeDB(fail_on_execute=True)
        monkeypatch.setattr(teams_service, "db", db)
        ws = TeamsWorkspace(
            team_id="T4", name="N", description="d", display_name="D",
            visibility="public", mail_nickname="n", created_at=datetime.now(timezone.utc),
            created_by="U1", tenant_id="TEN",
        )
        assert teams_service._save_workspace(ws) is False


class TestTeamsOAuth:
    def test_generate_oauth_url_with_msal(self, monkeypatch):
        import types as _types

        class FakeCCApp:
            def __init__(self, *a, **k):
                pass

            def get_authorization_request_url(self, **k):
                return "https://login.microsoftonline.com/auth?state=abc"

        monkeypatch.setattr(
            "integrations.teams_enhanced_service.msal",
            _types.SimpleNamespace(ConfidentialClientApplication=FakeCCApp),
        )
        svc = TeamsEnhancedService(
            tenant_id="default",
            config={"client_id": "cid", "client_secret": "cs", "redirect_uri": "http://r"},
        )
        url = svc.generate_oauth_url("state123", "U1")
        assert "state=abc" in url

    def test_generate_oauth_url_no_msal(self, teams_service):
        with pytest.raises(RuntimeError):
            teams_service.generate_oauth_url("state123", "U1")

    async def test_exchange_code_success(self, teams_service, monkeypatch):
        token = make_jwt({
            "tid": "tenant-1", "name": "Acme", "upn": "user@acme.com", "oid": "obj-1",
        })
        app = MagicMock()
        app.acquire_token_by_authorization_code.return_value = {
            "access_token": token, "refresh_token": "r",
        }
        monkeypatch.setattr(teams_service, "msal_app", app)
        result = await teams_service.exchange_code_for_tokens("code", "state")
        assert result["ok"] is True
        assert result["workspace"]["team_id"] == "tenant-1"

    async def test_exchange_code_no_msal(self, monkeypatch):
        svc = TeamsEnhancedService(tenant_id="default", config={})
        result = await svc.exchange_code_for_tokens("code", "state")
        assert result["ok"] is False
        assert result["error"] == "MSAL not available"

    async def test_exchange_code_error_result(self, teams_service, monkeypatch):
        app = MagicMock()
        app.acquire_token_by_authorization_code.return_value = {
            "error": "invalid_grant", "error_description": "bad code",
        }
        monkeypatch.setattr(teams_service, "msal_app", app)
        result = await teams_service.exchange_code_for_tokens("code", "state")
        assert result["ok"] is False

    async def test_exchange_code_save_failure(self, teams_service, monkeypatch):
        token = make_jwt({
            "tid": "tenant-1", "name": "Acme", "upn": "user@acme.com", "oid": "obj-1",
        })
        app = MagicMock()
        app.acquire_token_by_authorization_code.return_value = {
            "access_token": token, "refresh_token": "r",
        }
        monkeypatch.setattr(teams_service, "msal_app", app)
        with patch.object(teams_service, "_save_workspace", return_value=False):
            result = await teams_service.exchange_code_for_tokens("code", "state")
        assert result["ok"] is False
        assert result["error"] == "Failed to save workspace"


class TestTeamsGraphClients:
    def test_get_graph_client_creates(self, teams_service, monkeypatch):
        ws = TeamsWorkspace(
            team_id="T1", name="N", description="d", display_name="D",
            visibility="public", mail_nickname="n", created_at=datetime.now(timezone.utc),
            created_by="U1", tenant_id="TEN",
            access_token=teams_service._encrypt_token("tok"),
        )
        monkeypatch.setattr(teams_service, "_get_workspace", lambda wid: ws)
        monkeypatch.setattr(
            "integrations.teams_enhanced_service.GraphServiceClient", FakeGraphClient
        )
        client = teams_service._get_graph_client("T1")
        assert client is not None
        assert teams_service._get_graph_client("T1") is client

    def test_get_graph_client_no_token(self, teams_service, monkeypatch):
        monkeypatch.setattr(teams_service, "_get_workspace", lambda wid: None)
        assert teams_service._get_graph_client("T1") is None

    def test_get_graph_client_sdk_missing(self, teams_service, monkeypatch):
        ws = TeamsWorkspace(
            team_id="T1", name="N", description="d", display_name="D",
            visibility="public", mail_nickname="n", created_at=datetime.now(timezone.utc),
            created_by="U1", tenant_id="TEN", access_token="tok",
        )
        monkeypatch.setattr(teams_service, "_get_workspace", lambda wid: ws)
        monkeypatch.setattr(
            "integrations.teams_enhanced_service.GraphServiceClient", None
        )
        assert teams_service._get_graph_client("T1") is None

    def test_get_graph_client_error(self, teams_service, monkeypatch):
        ws = TeamsWorkspace(
            team_id="T1", name="N", description="d", display_name="D",
            visibility="public", mail_nickname="n", created_at=datetime.now(timezone.utc),
            created_by="U1", tenant_id="TEN", access_token="tok",
        )
        monkeypatch.setattr(teams_service, "_get_workspace", lambda wid: ws)
        monkeypatch.setattr(
            "integrations.teams_enhanced_service.GraphServiceClient",
            MagicMock(side_effect=RuntimeError("boom")),
        )
        assert teams_service._get_graph_client("T1") is None


class TestTeamsConnection:
    async def test_test_connection_success(self, teams_service):
        client = make_teams_client()
        team = SimpleNamespace(
            id="T1", display_name="Team", visibility="public",
            additional_data={"tenantId": "TEN"},
        )
        client.teams.set_result("get", SimpleNamespace(value=[team]))
        teams_service.graph_clients["T1"] = client
        result = await teams_service.test_connection("T1")
        assert result["connected"] is True
        assert result["workspace"]["team_id"] == "T1"
        assert teams_service.connection_status["T1"] == TeamsConnectionStatus.CONNECTED

    async def test_test_connection_no_client(self, monkeypatch):
        svc = TeamsEnhancedService(tenant_id="default", config={})
        result = await svc.test_connection("missing")
        assert result["connected"] is False
        assert result["status"] == "error"

    async def test_test_connection_empty(self, teams_service):
        client = make_teams_client()
        client.teams.set_result("get", SimpleNamespace(value=[]))
        teams_service.graph_clients["T1"] = client
        result = await teams_service.test_connection("T1")
        assert result["connected"] is False
        assert result["error"] == "No teams found"

    async def test_test_connection_error(self, teams_service):
        client = make_teams_client()
        client.teams.set_result("get", RuntimeError("graph down"))
        teams_service.graph_clients["T1"] = client
        result = await teams_service.test_connection("T1")
        assert result["connected"] is False
        assert result["status"] == "error"

    async def test_get_workspaces_db(self, teams_service, monkeypatch):
        row = {
            "team_id": "T9", "name": "N", "description": "d", "display_name": "D",
            "visibility": "public", "mail_nickname": "n",
            "created_at": datetime.now(timezone.utc).isoformat(), "created_by": "U1",
            "tenant_id": "TEN", "internal_id": None, "classification": None,
            "specialization": None, "web_url": None, "access_token": "tok",
            "refresh_token": None, "scopes": "[]", "last_sync": None, "is_active": 1,
            "settings": "{}", "member_count": 0, "channel_count": 0,
        }
        db = FakeDB(rows=[row])
        monkeypatch.setattr(teams_service, "db", db)
        assert len(await teams_service.get_workspaces()) == 1
        assert len(await teams_service.get_workspaces(user_id="U1")) == 1

    async def test_get_workspaces_redis(self, teams_service):
        ws = TeamsWorkspace(
            team_id="T1", name="N", description="d", display_name="D",
            visibility="public", mail_nickname="n", created_at=datetime.now(timezone.utc),
            created_by="U1", tenant_id="TEN",
        )
        teams_service.redis_client.setex(
            "teams_workspace:T1", 3600, json.dumps(ws.__dict__, default=str)
        )
        assert len(await teams_service.get_workspaces()) == 1
        assert await teams_service.get_workspaces(user_id="U2") == []

    async def test_get_workspaces_error(self, teams_service, monkeypatch):
        db = FakeDB(fail_on_execute=True)
        monkeypatch.setattr(teams_service, "db", db)
        assert await teams_service.get_workspaces() == []


def _teams_channel_sn(**kw):
    data = {
        "id": "C1", "display_name": "general", "description": "d",
        "membership_type": "standard", "email": None, "web_url": None,
        "is_favorite_by_default": False, "created_datetime": "2024-01-01T10:00:00Z",
        "last_updated_datetime": None, "additional_data": {},
        "is_archived": False, "is_welcome_message_enabled": True,
        "allow_cross_team_posts": True, "allow_giphy": True,
        "giphy_content_rating": "moderate", "allow_memes": True,
        "allow_custom_memes": True, "allow_stickers_and_gifs": True,
        "allow_user_edit_messages": True, "allow_owner_delete_messages": True,
        "allow_team_mentions": True, "allow_channel_mentions": True,
    }
    data.update(kw)
    return SimpleNamespace(**data)


class TestTeamsChannels:
    async def test_get_channels_success_with_filters(self, teams_service):
        client = make_teams_client()
        chans = [
            _teams_channel_sn(id="C1", last_updated_datetime="2024-01-02T10:00:00Z",
                              additional_data={"memberCount": 5}),
            _teams_channel_sn(id="C2", membership_type="private", is_archived=True),
        ]
        client.teams["T1"].channels.set_result("get", SimpleNamespace(value=chans))
        teams_service.graph_clients["T1"] = client
        channels = await teams_service.get_channels(
            "T1", include_private=True, include_archived=True
        )
        assert len(channels) == 2
        assert channels[0].channel_id == "C1"
        assert channels[1].is_archived is True
        assert "teams_channels:T1" in teams_service.redis_client.store

    async def test_get_channels_filters_exclude(self, teams_service):
        client = make_teams_client()
        chans = [_teams_channel_sn(id="C2", membership_type="private", is_archived=True)]
        client.teams["T1"].channels.set_result("get", SimpleNamespace(value=chans))
        teams_service.graph_clients["T1"] = client
        channels = await teams_service.get_channels("T1", include_private=False)
        assert channels == []

    async def test_get_channels_no_result(self, teams_service):
        client = make_teams_client()
        client.teams["T1"].channels.set_result("get", None)
        teams_service.graph_clients["T1"] = client
        assert await teams_service.get_channels("T1") == []

    async def test_get_channels_error_cache_fallback(self, teams_service):
        cached = [
            {"channel_id": "C1", "name": "general", "display_name": "general",
             "description": "", "workspace_id": "T1", "channel_type": "standard",
             "email": None, "web_url": None, "is_favorite_by_default": False,
             "membership_type": "standard",
             "created_at": datetime.now(timezone.utc).isoformat(),
             "last_activity_at": None, "member_count": 0, "message_count": 0,
             "files_count": 0, "is_archived": False, "is_welcome_message_enabled": True,
             "allow_cross_team_posts": True, "allow_giphy": True,
             "giphy_content_rating": "moderate", "allow_memes": True,
             "allow_custom_memes": True, "allow_stickers_and_gifs": True,
             "allow_user_edit_messages": True, "allow_owner_delete_messages": True,
             "allow_team_mentions": True, "allow_channel_mentions": True},
        ]
        teams_service.redis_client.setex(
            "teams_channels:T1", 1800, json.dumps(cached, default=str)
        )
        client = make_teams_client()
        client.teams["T1"].channels.set_result("get", RuntimeError("graph down"))
        teams_service.graph_clients["T1"] = client
        channels = await teams_service.get_channels("T1")
        assert len(channels) == 1
        assert channels[0].channel_id == "C1"

    async def test_get_channels_no_client(self, teams_service):
        assert await teams_service.get_channels("missing") == []

    async def test_get_channels_rate_limited(self, teams_service):
        client = make_teams_client()
        teams_service.graph_clients["T1"] = client
        for _ in range(50):
            await teams_service.rate_limiter.check_limit("T1", "channels_list")
        assert await teams_service.get_channels("T1") == []


class TestTeamsMessaging:
    async def test_send_message_new(self, teams_service):
        client = make_teams_client()
        result = SimpleNamespace(id="M1", created_datetime="2024-01-01T10:00:00Z")
        client.teams["T1"].channels["C1"].messages.set_result("post", result)
        teams_service.graph_clients["T1"] = client
        resp = await teams_service.send_message(
            "T1", "C1", "<div>hello</div>", importance="high", subject="subj",
            attachments=[{"id": "a"}],
        )
        assert resp["ok"] is True
        assert resp["message_id"] == "M1"

    async def test_send_message_thread_reply(self, teams_service):
        client = make_teams_client()
        result = SimpleNamespace(id="M2", created_datetime="2024-01-01T10:00:00Z")
        client.teams["T1"].channels["C1"].messages["TH1"].replies.set_result("post", result)
        teams_service.graph_clients["T1"] = client
        resp = await teams_service.send_message("T1", "C1", "plain text", thread_id="TH1")
        assert resp["ok"] is True
        assert resp["message_id"] == "M2"

    async def test_send_message_no_result(self, teams_service):
        client = make_teams_client()
        client.teams["T1"].channels["C1"].messages.set_result("post", None)
        teams_service.graph_clients["T1"] = client
        resp = await teams_service.send_message("T1", "C1", "hi")
        assert resp["ok"] is False

    async def test_send_message_no_client(self, teams_service):
        resp = await teams_service.send_message("missing", "C1", "hi")
        assert resp["ok"] is False

    async def test_send_message_rate_limited(self, teams_service):
        client = make_teams_client()
        teams_service.graph_clients["T1"] = client
        for _ in range(30):
            await teams_service.rate_limiter.check_limit("T1", "messages_send")
        resp = await teams_service.send_message("T1", "C1", "hi")
        assert resp["ok"] is False

    async def test_send_message_error(self, teams_service):
        client = make_teams_client()
        client.teams["T1"].channels["C1"].messages.set_result("post", RuntimeError("boom"))
        teams_service.graph_clients["T1"] = client
        resp = await teams_service.send_message("T1", "C1", "hi")
        assert resp["ok"] is False


def _teams_msg_sn(mid="M1", text="hi", created="2024-01-01T10:00:00Z", modified=None):
    msg = SimpleNamespace(
        id=mid,
        body=SimpleNamespace(content=text),
        created_datetime=created,
        last_modified_datetime=modified or created,
        reply_to_id=None,
        message_type="message",
        importance="normal",
        subject=None,
        summary=None,
        attachments=[],
        mentions=[],
        reactions=[],
        files=[],
        localized={},
        etag="e",
        channel_identity={},
        additional_data={},
    )
    setattr(msg, "from", SimpleNamespace(additional_data={
        "user": {"id": "U1", "displayName": "u", "emailAddress": "e"}
    }))
    return msg


class TestTeamsMessages:
    async def test_get_channel_messages_success(self, teams_service):
        client = make_teams_client()
        msg = _teams_msg_sn()
        msg.additional_data = {"participantCount": 3}
        client.teams["T1"].channels["C1"].messages.set_result(
            "get", SimpleNamespace(value=[msg])
        )
        teams_service.graph_clients["T1"] = client
        messages = await teams_service.get_channel_messages(
            "T1", "C1", limit=10, latest="2024-02-01", oldest="2024-01-01"
        )
        assert len(messages) == 1
        assert messages[0].user_id == "U1"
        assert messages[0].participant_count == 3
        assert "teams_messages:T1:C1" in teams_service.redis_client.store

    async def test_get_channel_messages_edited(self, teams_service):
        client = make_teams_client()
        msg = _teams_msg_sn(modified="2024-01-01T12:00:00Z")
        client.teams["T1"].channels["C1"].messages.set_result(
            "get", SimpleNamespace(value=[msg])
        )
        teams_service.graph_clients["T1"] = client
        messages = await teams_service.get_channel_messages("T1", "C1")
        assert messages[0].is_edited is True
        assert messages[0].edit_timestamp == "2024-01-01T12:00:00Z"

    async def test_get_channel_messages_no_result(self, teams_service):
        client = make_teams_client()
        client.teams["T1"].channels["C1"].messages.set_result("get", None)
        teams_service.graph_clients["T1"] = client
        assert await teams_service.get_channel_messages("T1", "C1") == []

    async def test_get_channel_messages_error_cache_fallback(self, teams_service):
        cached = [
            {"message_id": "M1", "text": "t", "user_id": "U1", "user_name": "",
             "user_email": "", "channel_id": "C1", "workspace_id": "T1",
             "tenant_id": "T1", "timestamp": "2024-01-01T10:00:00Z", "html": None,
             "thread_id": None, "reply_to_id": None, "message_type": "message",
             "importance": "normal", "subject": None, "summary": None,
             "policy_violations": [], "attachments": [], "mentions": [],
             "reactions": [], "files": [], "localized": {}, "etag": None,
             "last_modified_at": None, "is_edited": False, "edit_timestamp": None,
             "is_deleted": False, "delete_timestamp": None, "channel_identity": {},
             "reply_chain_id": None, "parent_message_id": None, "participant_count": 0},
        ]
        teams_service.redis_client.setex(
            "teams_messages:T1:C1", 1800, json.dumps(cached)
        )
        client = make_teams_client()
        client.teams["T1"].channels["C1"].messages.set_result(
            "get", RuntimeError("graph down")
        )
        teams_service.graph_clients["T1"] = client
        messages = await teams_service.get_channel_messages("T1", "C1")
        assert len(messages) == 1
        assert messages[0].message_id == "M1"

    async def test_get_channel_messages_no_client(self, teams_service):
        assert await teams_service.get_channel_messages("missing", "C1") == []


class TestTeamsSearch:
    async def test_search_messages_success(self, teams_service, monkeypatch):
        client = make_teams_client()
        teams_service.graph_clients["T1"] = client
        hit = {
            "resource": {
                "id": "M1", "body": {"content": "hello"},
                "from": {"id": "U1", "displayName": "u", "emailAddress": "e"},
                "channelIdentity": {"channelId": "C1"},
                "createdDateTime": "2024-01-01T10:00:00Z",
                "lastModifiedDateTime": "2024-01-01T10:00:00Z",
                "replyToId": None, "messageType": "message", "importance": "normal",
                "subject": None, "summary": None, "attachments": [], "mentions": [],
                "files": [], "etag": "e", "participantCount": 2,
            }
        }
        response = FakeHTTPResponse(
            status_code=200,
            json_data={
                "value": [{"hitsContainers": [{"hits": [hit], "total": 1}]}]
            },
        )
        monkeypatch.setattr(
            "integrations.teams_enhanced_service.httpx.AsyncClient",
            lambda *a, **k: FakeHTTPSession(response),
        )
        result = await teams_service.search_messages(
            "T1", "hello", channel_id="C1", user_id="U1"
        )
        assert result["ok"] is True
        assert result["total"] == 1
        assert result["messages"][0].message_id == "M1"

    async def test_search_messages_http_error(self, teams_service, monkeypatch):
        client = make_teams_client()
        teams_service.graph_clients["T1"] = client
        response = FakeHTTPResponse(status_code=500)
        monkeypatch.setattr(
            "integrations.teams_enhanced_service.httpx.AsyncClient",
            lambda *a, **k: FakeHTTPSession(response),
        )
        result = await teams_service.search_messages("T1", "hello")
        assert result["ok"] is False

    async def test_search_messages_no_client(self, teams_service):
        result = await teams_service.search_messages("missing", "hello")
        assert result["ok"] is False

    async def test_search_messages_error(self, teams_service, monkeypatch):
        client = make_teams_client()
        teams_service.graph_clients["T1"] = client
        response = FakeHTTPResponse(status_code=200, json_data={})
        monkeypatch.setattr(
            "integrations.teams_enhanced_service.httpx.AsyncClient",
            lambda *a, **k: FakeHTTPSession(response),
        )
        result = await teams_service.search_messages("T1", "hello")
        assert result["ok"] is False


class TestTeamsUpload:
    async def test_upload_file_success(self, teams_service, monkeypatch, tmp_path):
        client = make_teams_client()
        client.teams["T1"].channels["C1"].set_result(
            "get", SimpleNamespace(additional_data={"siteId": "SITE1"})
        )
        teams_service.graph_clients["T1"] = client
        fpath = tmp_path / "note.txt"
        fpath.write_text("hello")
        file_data = {
            "id": "F1", "name": "note.txt",
            "file": {"mimeType": "text/plain"},
            "size": 5, "createdDateTime": "2024-01-01T10:00:00Z",
            "webUrl": "https://sharepoint/f1", "@microsoft.graph.downloadUrl": "https://dl",
        }
        response = FakeHTTPResponse(status_code=201, json_data=file_data)
        monkeypatch.setattr(
            "integrations.teams_enhanced_service.httpx.AsyncClient",
            lambda *a, **k: FakeHTTPSession(response),
        )
        with patch.object(teams_service, "send_message", AsyncMock(return_value={"ok": True})):
            result = await teams_service.upload_file(
                "T1", "C1", str(fpath), title="Note", description="d"
            )
        assert result["ok"] is True
        assert result["file"]["file_id"] == "F1"

    async def test_upload_file_team_site_fallback(self, teams_service, monkeypatch, tmp_path):
        client = make_teams_client()
        client.teams["T1"].channels["C1"].set_result(
            "get", SimpleNamespace(additional_data={})
        )
        client.teams["T1"].set_result("get", SimpleNamespace(additional_data={"siteId": "SITE2"}))
        teams_service.graph_clients["T1"] = client
        fpath = tmp_path / "a.txt"
        fpath.write_text("x")
        file_data = {
            "id": "F2", "name": "a.txt", "file": {"mimeType": "image/png"},
            "size": 1, "createdDateTime": "2024-01-01T10:00:00Z", "webUrl": "u",
        }
        response = FakeHTTPResponse(status_code=200, json_data=file_data)
        monkeypatch.setattr(
            "integrations.teams_enhanced_service.httpx.AsyncClient",
            lambda *a, **k: FakeHTTPSession(response),
        )
        with patch.object(teams_service, "send_message", AsyncMock(return_value={"ok": True})):
            result = await teams_service.upload_file("T1", "C1", str(fpath))
        assert result["ok"] is True
        assert result["file"]["is_image"] is True

    async def test_upload_file_http_error(self, teams_service, monkeypatch, tmp_path):
        client = make_teams_client()
        client.teams["T1"].channels["C1"].set_result(
            "get", SimpleNamespace(additional_data={"siteId": "SITE1"})
        )
        teams_service.graph_clients["T1"] = client
        fpath = tmp_path / "b.txt"
        fpath.write_text("x")
        response = FakeHTTPResponse(status_code=403)
        monkeypatch.setattr(
            "integrations.teams_enhanced_service.httpx.AsyncClient",
            lambda *a, **k: FakeHTTPSession(response),
        )
        result = await teams_service.upload_file("T1", "C1", str(fpath))
        assert result["ok"] is False

    async def test_upload_file_no_client(self, teams_service, tmp_path):
        fpath = tmp_path / "c.txt"
        fpath.write_text("x")
        result = await teams_service.upload_file("missing", "C1", str(fpath))
        assert result["ok"] is False

    async def test_upload_file_missing_created_datetime_defaults(
        self, teams_service, monkeypatch, tmp_path
    ):
        client = make_teams_client()
        client.teams["T1"].channels["C1"].set_result(
            "get", SimpleNamespace(additional_data={"siteId": "SITE1"})
        )
        teams_service.graph_clients["T1"] = client
        fpath = tmp_path / "d.txt"
        fpath.write_text("x")
        file_data = {
            "id": "F3", "name": "d.txt", "file": {"mimeType": "text/plain"},
            "size": 1, "webUrl": "u",
        }
        response = FakeHTTPResponse(status_code=201, json_data=file_data)
        monkeypatch.setattr(
            "integrations.teams_enhanced_service.httpx.AsyncClient",
            lambda *a, **k: FakeHTTPSession(response),
        )
        with patch.object(teams_service, "send_message", AsyncMock(return_value={"ok": True})):
            result = await teams_service.upload_file("T1", "C1", str(fpath))
        assert result["ok"] is True
        assert result["file"]["file_id"] == "F3"


class TestTeamsSync:
    async def test_sync_to_postgres_cache_success(self, teams_service, monkeypatch):
        import core.database
        import core.models

        session = FakeMetricSession()
        monkeypatch.setattr(core.database, "SessionLocal", lambda: session)
        monkeypatch.setattr(core.models, "IntegrationMetric", MagicMock())

        client = make_teams_client()
        client.teams["T1"].channels.set_result(
            "get", SimpleNamespace(value=[_teams_channel_sn()])
        )
        teams_service.graph_clients["T1"] = client

        result = await teams_service.sync_to_postgres_cache("T1")
        assert result["success"] is True
        assert result["metrics_synced"] == 3
        assert session.committed is True

    async def test_sync_to_postgres_cache_commit_failure(self, teams_service, monkeypatch):
        import core.database
        import core.models

        session = FakeMetricSession()
        session.fail_commit = True
        monkeypatch.setattr(core.database, "SessionLocal", lambda: session)
        monkeypatch.setattr(core.models, "IntegrationMetric", MagicMock())

        client = make_teams_client()
        client.teams["T1"].channels.set_result("get", SimpleNamespace(value=[]))
        teams_service.graph_clients["T1"] = client

        result = await teams_service.sync_to_postgres_cache("T1")
        assert result["success"] is False
        assert session.rolled_back is True

    async def test_full_sync(self, teams_service, monkeypatch):
        import core.database
        import core.models

        session = FakeMetricSession()
        monkeypatch.setattr(core.database, "SessionLocal", lambda: session)
        monkeypatch.setattr(core.models, "IntegrationMetric", MagicMock())

        client = make_teams_client()
        client.teams["T1"].channels.set_result("get", SimpleNamespace(value=[]))
        teams_service.graph_clients["T1"] = client
        result = await teams_service.full_sync("T1")
        assert result["success"] is True
        assert result["success"] is True
        assert result["postgres_cache"]["success"] is True


class TestTeamsExecute:
    async def test_execute_operation_tenant_mismatch(self, teams_service):
        result = await teams_service.execute_operation(
            "send_message", {}, context={"tenant_id": "other"}
        )
        assert result["success"] is False
        assert result["error"] == "Tenant mismatch"

    async def test_execute_operation_send_message(self, teams_service, monkeypatch):
        with patch.object(
            teams_service, "send_message",
            AsyncMock(return_value={"ok": True, "message_id": "M1"}),
        ):
            result = await teams_service.execute_operation(
                "send_message",
                {"workspace_id": "T1", "channel_id": "C1", "text": "hi", "thread_id": "TH1"},
            )
        assert result["success"] is True

    async def test_execute_operation_get_channel_messages(self, teams_service, monkeypatch):
        msg = TeamsMessage(
            message_id="M1", text="t", user_id="U1", user_name="u", user_email="e",
            channel_id="C1", workspace_id="W1", tenant_id="TEN", timestamp="1",
        )
        with patch.object(
            teams_service, "get_channel_messages", AsyncMock(return_value=[msg])
        ):
            result = await teams_service.execute_operation(
                "get_channel_messages", {"workspace_id": "T1", "channel_id": "C1"}
            )
        assert result["success"] is True
        assert result["result"][0]["message_id"] == "M1"

    async def test_execute_operation_list_channels(self, teams_service, monkeypatch):
        ch = TeamsChannel(
            channel_id="C1", name="n", display_name="D", description="d",
            workspace_id="W1", channel_type="standard",
        )
        with patch.object(teams_service, "get_channels", AsyncMock(return_value=[ch])):
            result = await teams_service.execute_operation(
                "list_channels", {"workspace_id": "T1"}
            )
        assert result["success"] is True
        assert result["result"][0]["channel_id"] == "C1"

    async def test_execute_operation_search_messages(self, teams_service, monkeypatch):
        with patch.object(
            teams_service, "search_messages",
            AsyncMock(return_value={"ok": True, "messages": []}),
        ):
            result = await teams_service.execute_operation(
                "search_messages", {"workspace_id": "T1", "query": "hi"}
            )
        assert result["success"] is True

    async def test_execute_operation_unknown(self, teams_service):
        result = await teams_service.execute_operation("nope", {})
        assert result["success"] is False
        assert "Unknown operation" in result["error"]

    async def test_execute_operation_error(self, teams_service):
        with patch.object(
            teams_service, "send_message", AsyncMock(side_effect=RuntimeError("boom"))
        ):
            result = await teams_service.execute_operation(
                "send_message",
                {"workspace_id": "T1", "channel_id": "C1", "text": "hi"},
            )
        assert result["success"] is False

    async def test_close(self, teams_service):
        await teams_service.close()
        assert teams_service.graph_clients == {}
        assert teams_service.teams_clients == {}


# ---------------------------------------------------------------------------
# DiscordAnalyticsEngine
# ---------------------------------------------------------------------------

@pytest.fixture
def discord_engine():
    return DiscordAnalyticsEngine({
        "database": None,
        "redis": {"client": FakeRedis()},
        "cache_ttl": 300,
    })


class TestDiscordEngineInit:
    def test_init(self, discord_engine):
        assert discord_engine.cache_ttl == 300
        assert discord_engine.redis_client is not None
        assert len(discord_engine.aggregation_patterns) >= 10

    def test_get_engine_info(self, discord_engine):
        info = discord_engine.get_engine_info()
        assert info["name"] == "Discord Analytics Engine"
        assert info["cache_enabled"] is True
        assert len(info["supported_metrics"]) == len(DiscordAnalyticsMetric)

    def test_global_instance_exists(self):
        from integrations.discord_analytics_engine import discord_analytics_engine
        assert discord_analytics_engine.redis_client is None


class TestDiscordCache:
    def test_generate_cache_key(self, discord_engine):
        key = discord_engine._generate_cache_key(
            DiscordAnalyticsMetric.MESSAGE_COUNT,
            DiscordAnalyticsTimeRange.LAST_7_DAYS,
            DiscordAnalyticsGranularity.DAY,
            filters={"channel_type": "text"},
            workspace_id="discord_ws1",
            guild_ids=["g2", "g1"],
            channel_ids=["c1"],
            user_ids=["u1"],
        )
        assert key.startswith("discord_analytics|message_count|last_7_days|day")
        assert "guilds:g1,g2" in key
        assert "filters:" in key

    def test_generate_cache_key_minimal(self, discord_engine):
        key = discord_engine._generate_cache_key(
            DiscordAnalyticsMetric.MESSAGE_COUNT,
            DiscordAnalyticsTimeRange.LAST_24_HOURS,
            DiscordAnalyticsGranularity.HOUR,
        )
        assert key == "discord_analytics|message_count|last_24_hours|hour"

    def test_get_from_cache_hit(self, discord_engine):
        point = DiscordAnalyticsDataPoint(
            timestamp=datetime.now(timezone.utc),
            metric=DiscordAnalyticsMetric.MESSAGE_COUNT,
            value=5,
            dimensions={},
            metadata={},
        )
        discord_engine._cache_result("k1", [point])
        cached = discord_engine._get_from_cache("k1")
        assert cached is not None
        assert cached[0].metric == DiscordAnalyticsMetric.MESSAGE_COUNT

    def test_get_from_cache_miss(self, discord_engine):
        assert discord_engine._get_from_cache("nope") is None

    def test_get_from_cache_no_redis(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        assert engine._get_from_cache("k") is None

    def test_get_from_cache_corrupt(self, discord_engine):
        discord_engine.redis_client.setex("bad", 300, "{not json")
        assert discord_engine._get_from_cache("bad") is None

    def test_cache_result_no_redis_or_empty(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        point = DiscordAnalyticsDataPoint(
            timestamp=datetime.now(timezone.utc),
            metric=DiscordAnalyticsMetric.MESSAGE_COUNT,
            value=1,
            dimensions={},
            metadata={},
        )
        engine._cache_result("k", [point])
        engine2 = DiscordAnalyticsEngine({"database": None, "redis": {"client": FakeRedis()}})
        engine2._cache_result("k2", [])
        assert engine2._get_from_cache("k2") is None

    def test_cache_result_error(self, discord_engine):
        discord_engine.redis_client = object()
        point = DiscordAnalyticsDataPoint(
            timestamp=datetime.now(timezone.utc),
            metric=DiscordAnalyticsMetric.MESSAGE_COUNT,
            value=1,
            dimensions={},
            metadata={},
        )
        discord_engine._cache_result("k", [point])

    async def test_clear_cache(self, discord_engine):
        point = DiscordAnalyticsDataPoint(
            timestamp=datetime.now(timezone.utc),
            metric=DiscordAnalyticsMetric.MESSAGE_COUNT,
            value=1,
            dimensions={},
            metadata={},
        )
        discord_engine._cache_result("discord_analytics|a", [point])
        discord_engine._cache_result("other|b", [point])
        await discord_engine.clear_cache()
        assert discord_engine._get_from_cache("discord_analytics|a") is None
        assert discord_engine._get_from_cache("other|b") is not None

    async def test_clear_cache_no_keys(self, discord_engine):
        await discord_engine.clear_cache()

    async def test_clear_cache_error(self, discord_engine):
        discord_engine.redis_client = object()
        await discord_engine.clear_cache()


class TestDiscordTimeRanges:
    def test_time_range_boundaries(self, discord_engine):
        for tr in [
            DiscordAnalyticsTimeRange.LAST_24_HOURS,
            DiscordAnalyticsTimeRange.LAST_7_DAYS,
            DiscordAnalyticsTimeRange.LAST_30_DAYS,
            DiscordAnalyticsTimeRange.LAST_90_DAYS,
            DiscordAnalyticsTimeRange.CUSTOM,
        ]:
            start, end = discord_engine._get_time_range_boundaries(tr)
            assert start <= end

    def test_interval_delta(self, discord_engine):
        assert discord_engine._get_interval_delta(
            DiscordAnalyticsGranularity.HOUR
        ) == timedelta(hours=1)
        assert discord_engine._get_interval_delta(
            DiscordAnalyticsGranularity.DAY
        ) == timedelta(days=1)
        assert discord_engine._get_interval_delta(
            DiscordAnalyticsGranularity.WEEK
        ) == timedelta(weeks=1)
        assert discord_engine._get_interval_delta(
            DiscordAnalyticsGranularity.MONTH
        ) == timedelta(days=30)
        assert discord_engine._get_interval_delta(
            DiscordAnalyticsGranularity.YEAR
        ) == timedelta(days=1)

    def test_generate_mock_value(self, discord_engine):
        ts = datetime(2024, 1, 6, 20, 0, tzinfo=timezone.utc)
        assert discord_engine._generate_mock_value(
            DiscordAnalyticsMetric.MESSAGE_COUNT, ts
        ) > 0
        assert discord_engine._generate_mock_value(
            DiscordAnalyticsMetric.SENTIMENT, ts
        ) >= 0

    async def test_generate_mock_analytics_data(self, discord_engine):
        start = datetime.now(timezone.utc) - timedelta(days=2)
        end = datetime.now(timezone.utc)
        points = await discord_engine._generate_mock_analytics_data(
            DiscordAnalyticsMetric.MESSAGE_COUNT, start, end,
            DiscordAnalyticsGranularity.DAY,
        )
        assert len(points) == 3
        assert points[0].dimensions["workspace_id"] == "mock_workspace"

    async def test_generate_mock_analytics_data_error(self, discord_engine):
        with patch.object(
            discord_engine, "_get_interval_delta", side_effect=RuntimeError("boom")
        ):
            points = await discord_engine._generate_mock_analytics_data(
                DiscordAnalyticsMetric.MESSAGE_COUNT,
                datetime.now(timezone.utc), datetime.now(timezone.utc),
                DiscordAnalyticsGranularity.DAY,
            )
        assert points == []


class TestDiscordQueries:
    async def test_build_query_message_count(self, discord_engine):
        q = await discord_engine._build_analytics_query(
            DiscordAnalyticsMetric.MESSAGE_COUNT,
            datetime.now(timezone.utc), datetime.now(timezone.utc),
            DiscordAnalyticsGranularity.DAY,
        )
        assert "COUNT(*)" in q["sql"]
        assert q["params"][0]

    async def test_build_query_active_users(self, discord_engine):
        q = await discord_engine._build_analytics_query(
            DiscordAnalyticsMetric.ACTIVE_USERS,
            datetime.now(timezone.utc), datetime.now(timezone.utc),
            DiscordAnalyticsGranularity.HOUR,
        )
        assert "COUNT(DISTINCT user_id)" in q["sql"]

    async def test_build_query_bot_human(self, discord_engine):
        start, end = datetime.now(timezone.utc), datetime.now(timezone.utc)
        q_bot = await discord_engine._build_analytics_query(
            DiscordAnalyticsMetric.BOT_MESSAGE_COUNT, start, end,
            DiscordAnalyticsGranularity.DAY,
        )
        assert "is_bot = 1" in q_bot["sql"]
        q_human = await discord_engine._build_analytics_query(
            DiscordAnalyticsMetric.HUMAN_MESSAGE_COUNT, start, end,
            DiscordAnalyticsGranularity.DAY,
        )
        assert "is_bot = 0" in q_human["sql"]

    async def test_build_query_reaction_and_files(self, discord_engine):
        start, end = datetime.now(timezone.utc), datetime.now(timezone.utc)
        q = await discord_engine._build_analytics_query(
            DiscordAnalyticsMetric.REACTION_COUNT, start, end,
            DiscordAnalyticsGranularity.DAY,
        )
        assert "json_array_length" in q["sql"]
        q = await discord_engine._build_analytics_query(
            DiscordAnalyticsMetric.FILE_UPLOADS, start, end,
            DiscordAnalyticsGranularity.DAY,
        )
        assert "attachments" in q["sql"]

    async def test_build_query_default_and_filters(self, discord_engine):
        start, end = datetime.now(timezone.utc), datetime.now(timezone.utc)
        q = await discord_engine._build_analytics_query(
            DiscordAnalyticsMetric.VOICE_MINUTES, start, end,
            DiscordAnalyticsGranularity.WEEK,
            filters={"channel_type": "text", "category_id": ["a", "b"]},
            workspace_id="discord_12345",
            guild_ids=["g1", "g2"],
            channel_ids=["c1"],
            user_ids=["u1", "u2"],
        )
        assert "guild_id = ?" in q["sql"]
        assert "guild_id IN (?,?)" in q["sql"]
        assert "channel_type = ?" in q["sql"]
        assert "category_id IN (?,?)" in q["sql"]
        assert "12345" in q["params"]
        assert q["params"][0] == start.isoformat()

    async def test_build_query_unsupported_metric(self, discord_engine):
        q = await discord_engine._build_analytics_query(
            DiscordAnalyticsMetric.SENTIMENT,
            datetime.now(timezone.utc), datetime.now(timezone.utc),
            DiscordAnalyticsGranularity.DAY,
        )
        assert q == {"sql": "", "params": []}

    async def test_build_query_bad_granularity(self, discord_engine):
        q = await discord_engine._build_analytics_query(
            DiscordAnalyticsMetric.MESSAGE_COUNT,
            datetime.now(timezone.utc), datetime.now(timezone.utc),
            DiscordAnalyticsGranularity.YEAR,
        )
        assert q == {"sql": "", "params": []}

    async def test_fetch_analytics_data_db(self, discord_engine, monkeypatch):
        now = datetime.now(timezone.utc)
        row = {
            "timestamp": now.isoformat(), "value": 7,
            "dimensions": {"d": 1}, "metadata": {},
        }
        db = FakeDB(rows=[row])
        monkeypatch.setattr(discord_engine, "db", db)
        points = await discord_engine._fetch_analytics_data(
            DiscordAnalyticsMetric.MESSAGE_COUNT, now, now,
            DiscordAnalyticsGranularity.DAY,
        )
        assert len(points) == 1
        assert points[0].value == 7

    async def test_fetch_analytics_data_no_db_mock(self, discord_engine):
        points = await discord_engine._fetch_analytics_data(
            DiscordAnalyticsMetric.MESSAGE_COUNT,
            datetime.now(timezone.utc) - timedelta(days=2), datetime.now(timezone.utc),
            DiscordAnalyticsGranularity.DAY,
        )
        assert len(points) == 3

    async def test_fetch_analytics_data_error(self, discord_engine, monkeypatch):
        db = FakeDB(fail_on_execute=True)
        monkeypatch.setattr(discord_engine, "db", db)
        points = await discord_engine._fetch_analytics_data(
            DiscordAnalyticsMetric.MESSAGE_COUNT,
            datetime.now(timezone.utc), datetime.now(timezone.utc),
            DiscordAnalyticsGranularity.DAY,
        )
        assert points == []


class TestDiscordAnalytics:
    async def test_get_analytics_mock_data_and_cache(self, discord_engine):
        points = await discord_engine.get_analytics(
            DiscordAnalyticsMetric.MESSAGE_COUNT,
            DiscordAnalyticsTimeRange.LAST_24_HOURS,
            DiscordAnalyticsGranularity.DAY,
        )
        assert len(points) == 2
        cached = await discord_engine.get_analytics(
            DiscordAnalyticsMetric.MESSAGE_COUNT,
            DiscordAnalyticsTimeRange.LAST_24_HOURS,
            DiscordAnalyticsGranularity.DAY,
        )
        assert cached == points

    async def test_get_analytics_db_path(self, discord_engine, monkeypatch):
        now = datetime.now(timezone.utc)
        row = {"timestamp": now.isoformat(), "value": 3, "dimensions": {}, "metadata": {}}
        monkeypatch.setattr(discord_engine, "db", FakeDB(rows=[row]))
        points = await discord_engine.get_analytics(
            DiscordAnalyticsMetric.MESSAGE_COUNT,
            DiscordAnalyticsTimeRange.LAST_7_DAYS,
            DiscordAnalyticsGranularity.DAY,
        )
        assert len(points) == 1

    async def test_get_analytics_error(self, discord_engine):
        with patch.object(
            discord_engine, "_generate_cache_key", side_effect=RuntimeError("boom")
        ):
            points = await discord_engine.get_analytics(
                DiscordAnalyticsMetric.MESSAGE_COUNT,
                DiscordAnalyticsTimeRange.LAST_7_DAYS,
                DiscordAnalyticsGranularity.DAY,
            )
        assert points == []

    async def test_get_analytics_sentiment(self, discord_engine, monkeypatch):
        now = datetime.now(timezone.utc)
        row = {
            "timestamp": now.isoformat(),
            "content": "this community is really great and welcoming",
            "user_id": "U1", "channel_id": "C1",
        }
        monkeypatch.setattr(discord_engine, "db", FakeDB(rows=[row]))
        fake_llm = AsyncMock()
        fake_llm.generate_structured.return_value = LLMSentiment(
            score=0.8, label="positive", confidence=0.9
        )
        monkeypatch.setattr(
            "integrations.discord_analytics_engine.get_llm_service",
            lambda: fake_llm,
        )
        points = await discord_engine.get_analytics(
            DiscordAnalyticsMetric.SENTIMENT,
            DiscordAnalyticsTimeRange.LAST_7_DAYS,
            DiscordAnalyticsGranularity.DAY,
        )
        assert len(points) == 1
        assert points[0].value == 0.8
        assert points[0].dimensions["label"] == "positive"

    async def test_get_analytics_topics(self, discord_engine, monkeypatch):
        now = datetime.now(timezone.utc)
        row = {
            "timestamp": now.isoformat(),
            "content": "discussing the new roadmap plans",
            "user_id": "U1", "channel_id": "C1",
        }
        monkeypatch.setattr(discord_engine, "db", FakeDB(rows=[row]))
        fake_llm = AsyncMock()
        fake_llm.generate_structured.return_value = LLMTopics(
            topics=["roadmap", "plans"], confidence=0.8
        )
        monkeypatch.setattr(
            "integrations.discord_analytics_engine.get_llm_service",
            lambda: fake_llm,
        )
        points = await discord_engine.get_analytics(
            DiscordAnalyticsMetric.TOPICS,
            DiscordAnalyticsTimeRange.LAST_7_DAYS,
            DiscordAnalyticsGranularity.DAY,
        )
        assert len(points) == 1
        assert points[0].value == "roadmap, plans"

    async def test_sentiment_no_messages(self, discord_engine):
        points = await discord_engine._get_sentiment_analytics(
            datetime.now(timezone.utc), datetime.now(timezone.utc),
            DiscordAnalyticsGranularity.DAY,
        )
        assert points == []

    async def test_sentiment_short_text(self, discord_engine, monkeypatch):
        now = datetime.now(timezone.utc)
        row = {"timestamp": now.isoformat(), "content": "ok", "user_id": "U1", "channel_id": "C1"}
        monkeypatch.setattr(discord_engine, "db", FakeDB(rows=[row]))
        points = await discord_engine._get_sentiment_analytics(
            now, now, DiscordAnalyticsGranularity.DAY
        )
        assert points[0].value == 0.0
        assert points[0].dimensions["label"] == "neutral"

    async def test_sentiment_llm_error(self, discord_engine, monkeypatch):
        fake_llm = AsyncMock()
        fake_llm.generate_structured.side_effect = RuntimeError("llm down")
        monkeypatch.setattr(
            "integrations.discord_analytics_engine.get_llm_service",
            lambda: fake_llm,
        )
        result = await discord_engine._analyze_sentiment("a reasonably long message")
        assert result == {"score": 0.0, "label": "neutral", "confidence": 0.0}

    async def test_topics_empty(self, discord_engine):
        result = await discord_engine._extract_topics([])
        assert result == {"topics": [], "confidence": 1.0}

    async def test_topics_llm_error(self, discord_engine, monkeypatch):
        fake_llm = AsyncMock()
        fake_llm.generate_structured.side_effect = RuntimeError("llm down")
        monkeypatch.setattr(
            "integrations.discord_analytics_engine.get_llm_service",
            lambda: fake_llm,
        )
        result = await discord_engine._extract_topics(["some texts"])
        assert result == {"topics": [], "confidence": 0.0}

    async def test_fetch_raw_messages_no_db(self, discord_engine):
        assert await discord_engine._fetch_raw_messages(
            datetime.now(timezone.utc), datetime.now(timezone.utc)
        ) == []

    async def test_fetch_raw_messages_db(self, discord_engine, monkeypatch):
        now = datetime.now(timezone.utc)
        row = {"timestamp": now.isoformat(), "content": "hi", "user_id": "U1", "channel_id": "C1"}
        monkeypatch.setattr(discord_engine, "db", FakeDB(rows=[row]))
        rows = await discord_engine._fetch_raw_messages(
            now, now, workspace_id="discord_123"
        )
        assert len(rows) == 1
        assert rows[0]["content"] == "hi"

    async def test_fetch_raw_messages_error(self, discord_engine, monkeypatch):
        monkeypatch.setattr(discord_engine, "db", FakeDB(fail_on_execute=True))
        rows = await discord_engine._fetch_raw_messages(
            datetime.now(timezone.utc), datetime.now(timezone.utc)
        )
        assert rows == []

    def test_group_messages_by_granularity(self, discord_engine):
        ts = "2024-01-01T10:30:00+00:00"
        messages = [
            {"timestamp": ts, "content": "a"},
            {"timestamp": datetime(2024, 1, 1, 10, 45, tzinfo=timezone.utc), "content": "b"},
            {"timestamp": "2024-01-02T10:30:00+00:00", "content": "c"},
        ]
        grouped = discord_engine._group_messages_by_granularity(
            messages, DiscordAnalyticsGranularity.HOUR
        )
        assert len(grouped) == 2
        grouped_day = discord_engine._group_messages_by_granularity(
            messages, DiscordAnalyticsGranularity.DAY
        )
        assert len(grouped_day) == 2
        grouped_raw = discord_engine._group_messages_by_granularity(
            messages, DiscordAnalyticsGranularity.WEEK
        )
        assert len(grouped_raw) == 3


class TestDiscordTopGuildsUsers:
    async def test_get_top_guilds_mock(self, discord_engine):
        result = await discord_engine.get_top_guilds(
            DiscordAnalyticsMetric.MESSAGE_COUNT,
            DiscordAnalyticsTimeRange.LAST_7_DAYS,
            limit=3,
        )
        assert len(result) == 3
        assert result[0]["metric"] == "message_count"

    async def test_get_top_guilds_db(self, discord_engine, monkeypatch):
        rows = [
            {"guild_id": "G1", "guild_name": "Gaming", "value": 10, "human_ratio": 0.8},
            {"guild_id": "G2", "guild_name": "Tech", "value": 5, "human_ratio": 0.9},
        ]
        monkeypatch.setattr(discord_engine, "db", FakeDB(rows=rows))
        result = await discord_engine.get_top_guilds(
            DiscordAnalyticsMetric.MESSAGE_COUNT,
            DiscordAnalyticsTimeRange.LAST_7_DAYS,
            workspace_id="discord_G1",
        )
        assert len(result) == 2
        assert result[0]["guild_name"] == "Gaming"

    async def test_get_top_guilds_unsupported_metric(self, discord_engine, monkeypatch):
        monkeypatch.setattr(discord_engine, "db", FakeDB(rows=[]))
        result = await discord_engine.get_top_guilds(
            DiscordAnalyticsMetric.SENTIMENT,
            DiscordAnalyticsTimeRange.LAST_7_DAYS,
        )
        assert result == []

    async def test_get_top_guilds_error(self, discord_engine, monkeypatch):
        monkeypatch.setattr(discord_engine, "db", FakeDB(fail_on_execute=True))
        result = await discord_engine.get_top_guilds(
            DiscordAnalyticsMetric.MESSAGE_COUNT,
            DiscordAnalyticsTimeRange.LAST_7_DAYS,
        )
        assert result == []

    async def test_user_activity_summary_mock(self, discord_engine):
        result = await discord_engine.get_user_activity_summary(
            "U1", DiscordAnalyticsTimeRange.LAST_7_DAYS
        )
        assert result["user_id"] == "U1"
        assert result["message_count"] == 280

    async def test_user_activity_summary_db(self, discord_engine, monkeypatch):
        main_row = {
            "message_count": 30, "channels_participated": 3,
            "reactions_given": 4, "files_uploaded": 2, "avg_message_length": 20,
        }
        hourly_rows = [
            {"hour": "20"}, {"hour": "14"}, {"hour": "9"},
        ]
        main_db = FakeDB(rows=[main_row])
        hourly_db = FakeDB(rows=hourly_rows)

        def fake_execute(sql, params=None):
            if "strftime" in sql:
                return hourly_db.execute(sql, params)
            return main_db.execute(sql, params)

        fake_conn = FakeDB(rows=[main_row])
        fake_conn.execute = fake_execute
        monkeypatch.setattr(discord_engine, "db", fake_conn)
        result = await discord_engine.get_user_activity_summary(
            "U1", DiscordAnalyticsTimeRange.LAST_7_DAYS
        )
        assert result["message_count"] == 30
        assert result["most_active_hours"] == [20, 14, 9]
        assert result["engagement_score"] == 0.1

    async def test_user_activity_summary_error(self, discord_engine, monkeypatch):
        monkeypatch.setattr(discord_engine, "db", FakeDB(fail_on_execute=True))
        result = await discord_engine.get_user_activity_summary(
            "U1", DiscordAnalyticsTimeRange.LAST_7_DAYS
        )
        assert result == {}

    async def test_guild_activity_report_mock(self, discord_engine):
        result = await discord_engine.get_guild_activity_report(
            "G1", DiscordAnalyticsTimeRange.LAST_7_DAYS
        )
        assert result["guild_id"] == "G1"
        assert result["total_messages"] == 2450

    async def test_guild_activity_report_db(self, discord_engine, monkeypatch):
        metrics_row = {
            "total_messages": 100, "active_users": 5, "bot_messages": 10,
            "human_messages": 90, "reaction_count": 20, "file_uploads": 3,
            "avg_message_length": 15,
        }
        metrics_db = FakeDB(rows=[metrics_row])
        peak_db = FakeDB(rows=[{"hour": "18"}])
        contrib_db = FakeDB(rows=[{"user_name": "U1", "message_count": 60}])

        def fake_execute(sql, params=None):
            if "LIMIT 1" in sql:
                return peak_db.execute(sql, params)
            if "user_name" in sql:
                return contrib_db.execute(sql, params)
            return metrics_db.execute(sql, params)

        fake_conn = FakeDB(rows=[metrics_row])
        fake_conn.execute = fake_execute
        monkeypatch.setattr(discord_engine, "db", fake_conn)
        result = await discord_engine.get_guild_activity_report(
            "G1", DiscordAnalyticsTimeRange.LAST_7_DAYS
        )
        assert result["total_messages"] == 100
        assert result["peak_activity_hour"] == 18
        assert result["top_contributors"][0]["user_name"] == "U1"

    async def test_guild_activity_report_no_peak(self, discord_engine, monkeypatch):
        metrics_row = {
            "total_messages": 0, "active_users": 0, "bot_messages": 0,
            "human_messages": 0, "reaction_count": 0, "file_uploads": 0,
            "avg_message_length": 0,
        }
        metrics_db = FakeDB(rows=[metrics_row])
        peak_db = FakeDB(rows=[])
        contrib_db = FakeDB(rows=[])

        def fake_execute(sql, params=None):
            if "LIMIT 1" in sql:
                return peak_db.execute(sql, params)
            if "user_name" in sql:
                return contrib_db.execute(sql, params)
            return metrics_db.execute(sql, params)

        fake_conn = FakeDB(rows=[metrics_row])
        fake_conn.execute = fake_execute
        monkeypatch.setattr(discord_engine, "db", fake_conn)
        result = await discord_engine.get_guild_activity_report(
            "G1", DiscordAnalyticsTimeRange.LAST_7_DAYS
        )
        assert result["peak_activity_hour"] is None
        assert result["top_contributors"] == []

    async def test_guild_activity_report_error(self, discord_engine, monkeypatch):
        monkeypatch.setattr(discord_engine, "db", FakeDB(fail_on_execute=True))
        result = await discord_engine.get_guild_activity_report(
            "G1", DiscordAnalyticsTimeRange.LAST_7_DAYS
        )
        assert result == {}

    async def test_voice_chat_analytics_mock(self, discord_engine):
        result = await discord_engine.get_voice_chat_analytics(
            "G1", DiscordAnalyticsTimeRange.LAST_7_DAYS
        )
        assert result["guild_id"] == "G1"
        assert result["total_voice_minutes"] == 24000

    async def test_voice_chat_analytics_db(self, discord_engine, monkeypatch):
        monkeypatch.setattr(discord_engine, "db", FakeDB(rows=[]))
        result = await discord_engine.get_voice_chat_analytics(
            "G1", DiscordAnalyticsTimeRange.LAST_7_DAYS
        )
        assert result["guild_id"] == "G1"
        assert len(result["most_used_voice_channels"]) == 4

    async def test_voice_chat_analytics_error(self, discord_engine, monkeypatch):
        monkeypatch.setattr(discord_engine, "db", FakeDB(rows=[]))
        with patch.object(
            discord_engine, "_generate_mock_voice_analytics",
            side_effect=RuntimeError("boom"),
        ):
            result = await discord_engine.get_voice_chat_analytics(
                "G1", DiscordAnalyticsTimeRange.LAST_7_DAYS
            )
        assert result == {}


class TestDiscordExport:
    async def test_export_csv(self, discord_engine):
        result = await discord_engine.export_analytics_data(
            DiscordAnalyticsMetric.MESSAGE_COUNT,
            DiscordAnalyticsTimeRange.LAST_24_HOURS,
            DiscordAnalyticsGranularity.DAY,
            format="csv",
        )
        assert result["ok"] is True
        assert result["format"] == "csv"
        assert result["data"].startswith("timestamp,metric,value,dimensions,metadata")
        assert result["filename"].endswith(".csv")

    async def test_export_json(self, discord_engine):
        result = await discord_engine.export_analytics_data(
            DiscordAnalyticsMetric.MESSAGE_COUNT,
            DiscordAnalyticsTimeRange.LAST_24_HOURS,
            DiscordAnalyticsGranularity.DAY,
            format="json",
        )
        assert result["ok"] is True
        data = json.loads(result["data"])
        assert data[0]["metric"] == "message_count"

    async def test_export_excel(self, discord_engine):
        result = await discord_engine.export_analytics_data(
            DiscordAnalyticsMetric.MESSAGE_COUNT,
            DiscordAnalyticsTimeRange.LAST_24_HOURS,
            DiscordAnalyticsGranularity.DAY,
            format="excel",
        )
        assert result["ok"] is True
        assert result["format"] == "excel"
        assert len(result["data"]) > 0

    async def test_export_excel_openpyxl_missing(self, discord_engine, monkeypatch):
        monkeypatch.setattr(
            "integrations.discord_analytics_engine.OPENPYXL_AVAILABLE", False
        )
        result = await discord_engine.export_analytics_data(
            DiscordAnalyticsMetric.MESSAGE_COUNT,
            DiscordAnalyticsTimeRange.LAST_24_HOURS,
            DiscordAnalyticsGranularity.DAY,
            format="excel",
        )
        assert result["ok"] is False
        assert "openpyxl" in result["error"]

    async def test_export_no_data(self, discord_engine, monkeypatch):
        with patch.object(
            discord_engine, "get_analytics", AsyncMock(return_value=[])
        ):
            result = await discord_engine.export_analytics_data(
                DiscordAnalyticsMetric.MESSAGE_COUNT,
                DiscordAnalyticsTimeRange.LAST_24_HOURS,
                DiscordAnalyticsGranularity.DAY,
            )
        assert result == {"ok": False, "error": "No data available for export"}

    async def test_export_unsupported_format(self, discord_engine):
        result = await discord_engine.export_analytics_data(
            DiscordAnalyticsMetric.MESSAGE_COUNT,
            DiscordAnalyticsTimeRange.LAST_24_HOURS,
            DiscordAnalyticsGranularity.DAY,
            format="xml",
        )
        assert result["ok"] is False

    async def test_export_error(self, discord_engine, monkeypatch):
        with patch.object(
            discord_engine, "get_analytics", AsyncMock(side_effect=RuntimeError("boom"))
        ):
            result = await discord_engine.export_analytics_data(
                DiscordAnalyticsMetric.MESSAGE_COUNT,
                DiscordAnalyticsTimeRange.LAST_24_HOURS,
                DiscordAnalyticsGranularity.DAY,
            )
        assert result["ok"] is False

    def test_convert_to_csv(self, discord_engine):
        point = DiscordAnalyticsDataPoint(
            timestamp=datetime.now(timezone.utc),
            metric=DiscordAnalyticsMetric.MESSAGE_COUNT,
            value=3,
            dimensions={"channel": "general"},
            metadata={},
        )
        csv_data = discord_engine._convert_to_csv([point])
        assert csv_data.startswith("timestamp,metric,value,dimensions,metadata")
        assert "message_count" in csv_data

    def test_convert_to_csv_empty(self, discord_engine):
        assert discord_engine._convert_to_csv([]) == ""

    def test_convert_to_excel_single_point(self, discord_engine):
        point = DiscordAnalyticsDataPoint(
            timestamp=datetime.now(timezone.utc),
            metric=DiscordAnalyticsMetric.MESSAGE_COUNT,
            value=1,
            dimensions={},
            metadata={},
        )
        data = discord_engine._convert_to_excel(
            [point], DiscordAnalyticsMetric.MESSAGE_COUNT,
            DiscordAnalyticsTimeRange.LAST_24_HOURS,
        )
        assert data is not None and len(data) > 0

    def test_convert_to_excel_multiple_points(self, discord_engine):
        points = []
        for i in range(3):
            points.append(DiscordAnalyticsDataPoint(
                timestamp=datetime.now(timezone.utc),
                metric=DiscordAnalyticsMetric.MESSAGE_COUNT,
                value=float(i),
                dimensions={},
                metadata={},
            ))
        data = discord_engine._convert_to_excel(
            points, DiscordAnalyticsMetric.MESSAGE_COUNT,
            DiscordAnalyticsTimeRange.LAST_7_DAYS,
        )
        assert data is not None

    def test_convert_to_excel_empty(self, discord_engine):
        assert discord_engine._convert_to_excel(
            [], DiscordAnalyticsMetric.MESSAGE_COUNT,
            DiscordAnalyticsTimeRange.LAST_24_HOURS,
        ) is None


# ---------------------------------------------------------------------------
# GoogleChatAnalyticsEngine
# ---------------------------------------------------------------------------

@pytest.fixture
def google_engine():
    return GoogleChatAnalyticsEngine({
        "database": None,
        "redis": {"client": FakeRedis()},
        "cache_ttl": 300,
    })


class TestGoogleEngineInit:
    def test_init(self, google_engine):
        assert google_engine.cache_ttl == 300
        assert google_engine.redis_client is not None
        assert len(google_engine.aggregation_patterns) >= 11

    def test_get_engine_info(self, google_engine):
        info = google_engine.get_engine_info()
        assert info["name"] == "Google Chat Analytics Engine"
        assert info["cache_enabled"] is True

    def test_global_instance_exists(self):
        from integrations.google_chat_analytics_engine import google_chat_analytics_engine
        assert google_chat_analytics_engine.redis_client is None


class TestGoogleCache:
    def test_generate_cache_key(self, google_engine):
        key = google_engine._generate_cache_key(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            GoogleChatAnalyticsTimeRange.LAST_7_DAYS,
            GoogleChatAnalyticsGranularity.DAY,
            filters={"space_type": "direct"},
            workspace_id="ws1",
            space_ids=["s2", "s1"],
            user_ids=["u1"],
        )
        assert key.startswith("google_chat_analytics|message_count|last_7_days|day")
        assert "spaces:s1,s2" in key

    def test_generate_cache_key_minimal(self, google_engine):
        key = google_engine._generate_cache_key(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            GoogleChatAnalyticsTimeRange.LAST_24_HOURS,
            GoogleChatAnalyticsGranularity.HOUR,
        )
        assert key == "google_chat_analytics|message_count|last_24_hours|hour"

    def test_get_from_cache_hit(self, google_engine):
        point = GoogleChatAnalyticsDataPoint(
            timestamp=datetime.now(timezone.utc),
            metric=GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            value=5,
            dimensions={},
            metadata={},
        )
        google_engine._cache_result("k1", [point])
        cached = google_engine._get_from_cache("k1")
        assert cached is not None
        assert cached[0].metric == GoogleChatAnalyticsMetric.MESSAGE_COUNT

    def test_get_from_cache_corrupt(self, google_engine):
        google_engine.redis_client.setex("bad", 300, "not json")
        assert google_engine._get_from_cache("bad") is None

    async def test_clear_cache(self, google_engine):
        point = GoogleChatAnalyticsDataPoint(
            timestamp=datetime.now(timezone.utc),
            metric=GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            value=1,
            dimensions={},
            metadata={},
        )
        google_engine._cache_result("google_chat_analytics|a", [point])
        google_engine._cache_result("other|b", [point])
        await google_engine.clear_cache()
        assert google_engine._get_from_cache("google_chat_analytics|a") is None
        assert google_engine._get_from_cache("other|b") is not None

    async def test_clear_cache_error(self, google_engine):
        google_engine.redis_client = object()
        await google_engine.clear_cache()


class TestGoogleTimeRanges:
    def test_time_range_boundaries(self, google_engine):
        for tr in [
            GoogleChatAnalyticsTimeRange.LAST_24_HOURS,
            GoogleChatAnalyticsTimeRange.LAST_7_DAYS,
            GoogleChatAnalyticsTimeRange.LAST_30_DAYS,
            GoogleChatAnalyticsTimeRange.LAST_90_DAYS,
            GoogleChatAnalyticsTimeRange.CUSTOM,
        ]:
            start, end = google_engine._get_time_range_boundaries(tr)
            assert start <= end

    def test_interval_delta(self, google_engine):
        assert google_engine._get_interval_delta(
            GoogleChatAnalyticsGranularity.HOUR
        ) == timedelta(hours=1)
        assert google_engine._get_interval_delta(
            GoogleChatAnalyticsGranularity.YEAR
        ) == timedelta(days=1)

    def test_generate_mock_value(self, google_engine):
        ts = datetime(2024, 1, 3, 10, 0, tzinfo=timezone.utc)
        assert google_engine._generate_mock_value(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT, ts
        ) > 0
        assert google_engine._generate_mock_value(
            GoogleChatAnalyticsMetric.SENTIMENT, ts
        ) >= 0

    async def test_generate_mock_analytics_data(self, google_engine):
        start = datetime.now(timezone.utc) - timedelta(days=1)
        end = datetime.now(timezone.utc)
        points = await google_engine._generate_mock_analytics_data(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT, start, end,
            GoogleChatAnalyticsGranularity.DAY,
        )
        assert len(points) == 2
        assert points[0].dimensions["space_id"] == "mock_space"

    async def test_generate_mock_analytics_data_error(self, google_engine):
        with patch.object(
            google_engine, "_get_interval_delta", side_effect=RuntimeError("boom")
        ):
            points = await google_engine._generate_mock_analytics_data(
                GoogleChatAnalyticsMetric.MESSAGE_COUNT,
                datetime.now(timezone.utc), datetime.now(timezone.utc),
                GoogleChatAnalyticsGranularity.DAY,
            )
        assert points == []


class TestGoogleQueries:
    async def test_build_query_message_count(self, google_engine):
        q = await google_engine._build_analytics_query(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            datetime.now(timezone.utc), datetime.now(timezone.utc),
            GoogleChatAnalyticsGranularity.DAY,
        )
        assert "COUNT(*)" in q["sql"]

    async def test_build_query_active_users(self, google_engine):
        q = await google_engine._build_analytics_query(
            GoogleChatAnalyticsMetric.ACTIVE_USERS,
            datetime.now(timezone.utc), datetime.now(timezone.utc),
            GoogleChatAnalyticsGranularity.HOUR,
        )
        assert "COUNT(DISTINCT user_id)" in q["sql"]

    async def test_build_query_bot_human(self, google_engine):
        start, end = datetime.now(timezone.utc), datetime.now(timezone.utc)
        q_bot = await google_engine._build_analytics_query(
            GoogleChatAnalyticsMetric.BOT_MESSAGE_COUNT, start, end,
            GoogleChatAnalyticsGranularity.DAY,
        )
        assert "sender_type = 'BOT'" in q_bot["sql"]
        q_human = await google_engine._build_analytics_query(
            GoogleChatAnalyticsMetric.HUMAN_MESSAGE_COUNT, start, end,
            GoogleChatAnalyticsGranularity.DAY,
        )
        assert "sender_type = 'HUMAN'" in q_human["sql"]

    async def test_build_query_thread_creation(self, google_engine):
        q = await google_engine._build_analytics_query(
            GoogleChatAnalyticsMetric.THREAD_CREATION,
            datetime.now(timezone.utc), datetime.now(timezone.utc),
            GoogleChatAnalyticsGranularity.DAY,
        )
        assert "thread_id IS NOT NULL" in q["sql"]

    async def test_build_query_card_interactions(self, google_engine):
        q = await google_engine._build_analytics_query(
            GoogleChatAnalyticsMetric.CARD_INTERACTIONS,
            datetime.now(timezone.utc), datetime.now(timezone.utc),
            GoogleChatAnalyticsGranularity.DAY,
        )
        assert "action_response" in q["sql"]

    async def test_build_query_response_time(self, google_engine):
        q = await google_engine._build_analytics_query(
            GoogleChatAnalyticsMetric.RESPONSE_TIME,
            datetime.now(timezone.utc), datetime.now(timezone.utc),
            GoogleChatAnalyticsGranularity.DAY,
        )
        assert "julianday" in q["sql"]

    async def test_build_query_reaction_count(self, google_engine):
        q = await google_engine._build_analytics_query(
            GoogleChatAnalyticsMetric.REACTION_COUNT,
            datetime.now(timezone.utc), datetime.now(timezone.utc),
            GoogleChatAnalyticsGranularity.DAY,
        )
        assert "json_array_length" in q["sql"]

    async def test_build_query_default_and_filters(self, google_engine):
        start, end = datetime.now(timezone.utc), datetime.now(timezone.utc)
        q = await google_engine._build_analytics_query(
            GoogleChatAnalyticsMetric.SPACE_ACTIVITY, start, end,
            GoogleChatAnalyticsGranularity.WEEK,
            filters={"space_type": "room", "labels": ["a", "b"]},
            workspace_id="ws1",
            space_ids=["s1", "s2"],
            user_ids=["u1"],
        )
        assert "workspace_id = ?" in q["sql"]
        assert "space_id IN (?,?)" in q["sql"]
        assert "user_id IN (?)" in q["sql"]
        assert "space_type = ?" in q["sql"]
        assert "labels IN (?,?)" in q["sql"]

    async def test_build_query_unsupported_metric(self, google_engine):
        q = await google_engine._build_analytics_query(
            GoogleChatAnalyticsMetric.SENTIMENT,
            datetime.now(timezone.utc), datetime.now(timezone.utc),
            GoogleChatAnalyticsGranularity.DAY,
        )
        assert q == {"sql": "", "params": []}

    async def test_fetch_analytics_data_db(self, google_engine, monkeypatch):
        now = datetime.now(timezone.utc)
        row = {"timestamp": now.isoformat(), "value": 7, "dimensions": {}, "metadata": {}}
        monkeypatch.setattr(google_engine, "db", FakeDB(rows=[row]))
        points = await google_engine._fetch_analytics_data(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT, now, now,
            GoogleChatAnalyticsGranularity.DAY,
        )
        assert len(points) == 1
        assert points[0].value == 7

    async def test_fetch_analytics_data_no_db_mock(self, google_engine):
        points = await google_engine._fetch_analytics_data(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            datetime.now(timezone.utc) - timedelta(days=2), datetime.now(timezone.utc),
            GoogleChatAnalyticsGranularity.DAY,
        )
        assert len(points) == 3

    async def test_fetch_analytics_data_error(self, google_engine, monkeypatch):
        monkeypatch.setattr(google_engine, "db", FakeDB(fail_on_execute=True))
        points = await google_engine._fetch_analytics_data(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            datetime.now(timezone.utc), datetime.now(timezone.utc),
            GoogleChatAnalyticsGranularity.DAY,
        )
        assert points == []


class TestGoogleAnalytics:
    async def test_get_analytics_mock_data_and_cache(self, google_engine):
        points = await google_engine.get_analytics(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            GoogleChatAnalyticsTimeRange.LAST_24_HOURS,
            GoogleChatAnalyticsGranularity.DAY,
        )
        assert len(points) == 2
        cached = await google_engine.get_analytics(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            GoogleChatAnalyticsTimeRange.LAST_24_HOURS,
            GoogleChatAnalyticsGranularity.DAY,
        )
        assert cached == points

    async def test_get_analytics_error(self, google_engine):
        with patch.object(
            google_engine, "_generate_cache_key", side_effect=RuntimeError("boom")
        ):
            points = await google_engine.get_analytics(
                GoogleChatAnalyticsMetric.MESSAGE_COUNT,
                GoogleChatAnalyticsTimeRange.LAST_7_DAYS,
                GoogleChatAnalyticsGranularity.DAY,
            )
        assert points == []

    async def test_get_analytics_sentiment(self, google_engine, monkeypatch):
        now = datetime.now(timezone.utc)
        row = {
            "timestamp": now.isoformat(),
            "content": "the project launch was a huge success",
            "user_id": "U1", "space_id": "S1",
        }
        monkeypatch.setattr(google_engine, "db", FakeDB(rows=[row]))
        fake_llm = AsyncMock()
        fake_llm.generate_structured.return_value = LLMSentiment(
            score=0.9, label="positive", confidence=0.95
        )
        monkeypatch.setattr(
            "integrations.google_chat_analytics_engine.get_llm_service",
            lambda: fake_llm,
        )
        points = await google_engine.get_analytics(
            GoogleChatAnalyticsMetric.SENTIMENT,
            GoogleChatAnalyticsTimeRange.LAST_7_DAYS,
            GoogleChatAnalyticsGranularity.DAY,
        )
        assert len(points) == 1
        assert points[0].value == 0.9

    async def test_get_analytics_topics(self, google_engine, monkeypatch):
        now = datetime.now(timezone.utc)
        row = {
            "timestamp": now.isoformat(),
            "content": "we are planning the next sprint cycle",
            "user_id": "U1", "space_id": "S1",
        }
        monkeypatch.setattr(google_engine, "db", FakeDB(rows=[row]))
        fake_llm = AsyncMock()
        fake_llm.generate_structured.return_value = LLMTopics(
            topics=["sprint", "planning"], confidence=0.8
        )
        monkeypatch.setattr(
            "integrations.google_chat_analytics_engine.get_llm_service",
            lambda: fake_llm,
        )
        points = await google_engine.get_analytics(
            GoogleChatAnalyticsMetric.TOPICS,
            GoogleChatAnalyticsTimeRange.LAST_7_DAYS,
            GoogleChatAnalyticsGranularity.DAY,
        )
        assert len(points) == 1
        assert points[0].value == "sprint, planning"

    async def test_sentiment_short_text(self, google_engine, monkeypatch):
        now = datetime.now(timezone.utc)
        row = {"timestamp": now.isoformat(), "content": "ok", "user_id": "U1", "space_id": "S1"}
        monkeypatch.setattr(google_engine, "db", FakeDB(rows=[row]))
        points = await google_engine._get_sentiment_analytics(
            now, now, GoogleChatAnalyticsGranularity.DAY
        )
        assert points[0].value == 0.0

    async def test_sentiment_llm_error(self, google_engine, monkeypatch):
        fake_llm = AsyncMock()
        fake_llm.generate_structured.side_effect = RuntimeError("llm down")
        monkeypatch.setattr(
            "integrations.google_chat_analytics_engine.get_llm_service",
            lambda: fake_llm,
        )
        result = await google_engine._analyze_sentiment("a long enough message")
        assert result == {"score": 0.0, "label": "neutral", "confidence": 0.0}

    async def test_topics_empty(self, google_engine):
        result = await google_engine._extract_topics([])
        assert result == {"topics": [], "confidence": 1.0}

    async def test_topics_llm_error(self, google_engine, monkeypatch):
        fake_llm = AsyncMock()
        fake_llm.generate_structured.side_effect = RuntimeError("llm down")
        monkeypatch.setattr(
            "integrations.google_chat_analytics_engine.get_llm_service",
            lambda: fake_llm,
        )
        result = await google_engine._extract_topics(["some texts"])
        assert result == {"topics": [], "confidence": 0.0}

    async def test_fetch_raw_messages_no_db(self, google_engine):
        assert await google_engine._fetch_raw_messages(
            datetime.now(timezone.utc), datetime.now(timezone.utc)
        ) == []

    async def test_fetch_raw_messages_db(self, google_engine, monkeypatch):
        now = datetime.now(timezone.utc)
        row = {"timestamp": now.isoformat(), "content": "hi", "user_id": "U1", "space_id": "S1"}
        monkeypatch.setattr(google_engine, "db", FakeDB(rows=[row]))
        rows = await google_engine._fetch_raw_messages(
            now, now, workspace_id="ws1"
        )
        assert len(rows) == 1

    async def test_fetch_raw_messages_error(self, google_engine, monkeypatch):
        monkeypatch.setattr(google_engine, "db", FakeDB(fail_on_execute=True))
        rows = await google_engine._fetch_raw_messages(
            datetime.now(timezone.utc), datetime.now(timezone.utc)
        )
        assert rows == []

    def test_group_messages_by_granularity(self, google_engine):
        messages = [
            {"timestamp": "2024-01-01T10:30:00+00:00", "content": "a"},
            {"timestamp": "2024-01-01T10:45:00+00:00", "content": "b"},
        ]
        grouped = google_engine._group_messages_by_granularity(
            messages, GoogleChatAnalyticsGranularity.HOUR
        )
        assert len(grouped) == 1
        grouped_day = google_engine._group_messages_by_granularity(
            messages, GoogleChatAnalyticsGranularity.DAY
        )
        assert len(grouped_day) == 1
        grouped_raw = google_engine._group_messages_by_granularity(
            messages, GoogleChatAnalyticsGranularity.WEEK
        )
        assert len(grouped_raw) == 2


class TestGoogleTopSpacesUsers:
    async def test_get_top_spaces_mock(self, google_engine):
        result = await google_engine.get_top_spaces(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            GoogleChatAnalyticsTimeRange.LAST_7_DAYS,
            limit=2,
        )
        assert len(result) == 2
        assert result[0]["metric"] == "message_count"

    async def test_get_top_spaces_db(self, google_engine, monkeypatch):
        rows = [
            {"space_id": "S1", "space_name": "General", "value": 10, "human_ratio": 0.8},
        ]
        monkeypatch.setattr(google_engine, "db", FakeDB(rows=rows))
        result = await google_engine.get_top_spaces(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            GoogleChatAnalyticsTimeRange.LAST_7_DAYS,
            workspace_id="ws1",
        )
        assert len(result) == 1
        assert result[0]["space_name"] == "General"

    async def test_get_top_spaces_unsupported_metric(self, google_engine, monkeypatch):
        monkeypatch.setattr(google_engine, "db", FakeDB(rows=[]))
        result = await google_engine.get_top_spaces(
            GoogleChatAnalyticsMetric.SENTIMENT,
            GoogleChatAnalyticsTimeRange.LAST_7_DAYS,
        )
        assert result == []

    async def test_get_top_spaces_error(self, google_engine, monkeypatch):
        monkeypatch.setattr(google_engine, "db", FakeDB(fail_on_execute=True))
        result = await google_engine.get_top_spaces(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            GoogleChatAnalyticsTimeRange.LAST_7_DAYS,
        )
        assert result == []

    async def test_user_activity_summary_mock(self, google_engine):
        result = await google_engine.get_user_activity_summary(
            "U1", GoogleChatAnalyticsTimeRange.LAST_7_DAYS
        )
        assert result["user_id"] == "U1"
        assert result["message_count"] == 150

    async def test_user_activity_summary_db(self, google_engine, monkeypatch):
        main_row = {
            "message_count": 60, "spaces_participated": 4, "threads_created": 2,
            "reactions_given": 6, "card_interactions": 1, "avg_message_length": 30,
        }
        hourly_rows = [{"hour": "10"}, {"hour": "14"}]
        main_db = FakeDB(rows=[main_row])
        hourly_db = FakeDB(rows=hourly_rows)

        def fake_execute(sql, params=None):
            if "strftime" in sql:
                return hourly_db.execute(sql, params)
            return main_db.execute(sql, params)

        fake_conn = FakeDB(rows=[main_row])
        fake_conn.execute = fake_execute
        monkeypatch.setattr(google_engine, "db", fake_conn)
        result = await google_engine.get_user_activity_summary(
            "U1", GoogleChatAnalyticsTimeRange.LAST_7_DAYS
        )
        assert result["message_count"] == 60
        assert result["most_active_hours"] == [10, 14]
        assert result["engagement_score"] == 0.3

    async def test_user_activity_summary_error_no_leak(self, google_engine):
        with patch.object(
            google_engine, "_get_time_range_boundaries",
            side_effect=RuntimeError("internal-secret-detail"),
        ):
            result = await google_engine.get_user_activity_summary(
                "U1", GoogleChatAnalyticsTimeRange.LAST_7_DAYS
            )
        assert result["success"] is False
        assert "internal-secret-detail" not in json.dumps(result)

    async def test_space_activity_report_mock(self, google_engine):
        result = await google_engine.get_space_activity_report(
            "S1", GoogleChatAnalyticsTimeRange.LAST_7_DAYS
        )
        assert result["space_id"] == "S1"
        assert result["total_messages"] == 1250

    async def test_space_activity_report_db(self, google_engine, monkeypatch):
        metrics_row = {
            "total_messages": 80, "active_users": 4, "new_threads": 5,
            "card_interactions": 2, "bot_messages": 10, "human_messages": 70,
            "avg_message_length": 12,
        }
        metrics_db = FakeDB(rows=[metrics_row])
        peak_db = FakeDB(rows=[{"hour": "15"}])
        contrib_db = FakeDB(rows=[{"user_name": "Jane", "message_count": 40}])

        def fake_execute(sql, params=None):
            if "LIMIT 1" in sql:
                return peak_db.execute(sql, params)
            if "user_name" in sql:
                return contrib_db.execute(sql, params)
            return metrics_db.execute(sql, params)

        fake_conn = FakeDB(rows=[metrics_row])
        fake_conn.execute = fake_execute
        monkeypatch.setattr(google_engine, "db", fake_conn)
        result = await google_engine.get_space_activity_report(
            "S1", GoogleChatAnalyticsTimeRange.LAST_7_DAYS
        )
        assert result["total_messages"] == 80
        assert result["peak_activity_hour"] == 15
        assert result["top_contributors"][0]["user_name"] == "Jane"

    async def test_space_activity_report_no_peak(self, google_engine, monkeypatch):
        metrics_row = {
            "total_messages": 0, "active_users": 0, "new_threads": 0,
            "card_interactions": 0, "bot_messages": 0, "human_messages": 0,
            "avg_message_length": 0,
        }
        metrics_db = FakeDB(rows=[metrics_row])
        peak_db = FakeDB(rows=[])
        contrib_db = FakeDB(rows=[])

        def fake_execute(sql, params=None):
            if "LIMIT 1" in sql:
                return peak_db.execute(sql, params)
            if "user_name" in sql:
                return contrib_db.execute(sql, params)
            return metrics_db.execute(sql, params)

        fake_conn = FakeDB(rows=[metrics_row])
        fake_conn.execute = fake_execute
        monkeypatch.setattr(google_engine, "db", fake_conn)
        result = await google_engine.get_space_activity_report(
            "S1", GoogleChatAnalyticsTimeRange.LAST_7_DAYS
        )
        assert result["peak_activity_hour"] is None
        assert result["top_contributors"] == []

    async def test_space_activity_report_error_no_leak(self, google_engine):
        with patch.object(
            google_engine, "_get_time_range_boundaries",
            side_effect=RuntimeError("internal-secret-detail"),
        ):
            result = await google_engine.get_space_activity_report(
                "S1", GoogleChatAnalyticsTimeRange.LAST_7_DAYS
            )
        assert result["success"] is False
        assert "internal-secret-detail" not in json.dumps(result)


class TestGoogleExport:
    async def test_export_csv(self, google_engine):
        result = await google_engine.export_analytics_data(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            GoogleChatAnalyticsTimeRange.LAST_24_HOURS,
            GoogleChatAnalyticsGranularity.DAY,
            format="csv",
        )
        assert result["ok"] is True
        assert result["data"].startswith("timestamp,metric,value,dimensions,metadata")
        assert result["filename"].endswith(".csv")

    async def test_export_json(self, google_engine):
        result = await google_engine.export_analytics_data(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            GoogleChatAnalyticsTimeRange.LAST_24_HOURS,
            GoogleChatAnalyticsGranularity.DAY,
            format="json",
        )
        assert result["ok"] is True
        data = json.loads(result["data"])
        assert data[0]["metric"] == "message_count"

    async def test_export_excel(self, google_engine):
        result = await google_engine.export_analytics_data(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            GoogleChatAnalyticsTimeRange.LAST_24_HOURS,
            GoogleChatAnalyticsGranularity.DAY,
            format="excel",
        )
        assert result["ok"] is True
        assert len(result["data"]) > 0

    async def test_export_excel_openpyxl_missing(self, google_engine, monkeypatch):
        monkeypatch.setattr(
            "integrations.google_chat_analytics_engine.OPENPYXL_AVAILABLE", False
        )
        result = await google_engine.export_analytics_data(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            GoogleChatAnalyticsTimeRange.LAST_24_HOURS,
            GoogleChatAnalyticsGranularity.DAY,
            format="excel",
        )
        assert result["ok"] is False

    async def test_export_no_data(self, google_engine):
        with patch.object(google_engine, "get_analytics", AsyncMock(return_value=[])):
            result = await google_engine.export_analytics_data(
                GoogleChatAnalyticsMetric.MESSAGE_COUNT,
                GoogleChatAnalyticsTimeRange.LAST_24_HOURS,
                GoogleChatAnalyticsGranularity.DAY,
            )
        assert result == {"ok": False, "error": "No data available for export"}

    async def test_export_unsupported_format(self, google_engine):
        result = await google_engine.export_analytics_data(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            GoogleChatAnalyticsTimeRange.LAST_24_HOURS,
            GoogleChatAnalyticsGranularity.DAY,
            format="xml",
        )
        assert result["ok"] is False

    def test_convert_to_csv(self, google_engine):
        point = GoogleChatAnalyticsDataPoint(
            timestamp=datetime.now(timezone.utc),
            metric=GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            value=3,
            dimensions={},
            metadata={},
        )
        csv_data = google_engine._convert_to_csv([point])
        assert csv_data.startswith("timestamp,metric,value,dimensions,metadata")

    def test_convert_to_excel(self, google_engine):
        points = [
            GoogleChatAnalyticsDataPoint(
                timestamp=datetime.now(timezone.utc),
                metric=GoogleChatAnalyticsMetric.MESSAGE_COUNT,
                value=1.0,
                dimensions={},
                metadata={},
            ),
            GoogleChatAnalyticsDataPoint(
                timestamp=datetime.now(timezone.utc),
                metric=GoogleChatAnalyticsMetric.MESSAGE_COUNT,
                value=2.0,
                dimensions={},
                metadata={},
            ),
        ]
        data = google_engine._convert_to_excel(
            points, GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            GoogleChatAnalyticsTimeRange.LAST_7_DAYS,
        )
        assert data is not None and len(data) > 0

    def test_convert_to_excel_empty(self, google_engine):
        assert google_engine._convert_to_excel(
            [], GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            GoogleChatAnalyticsTimeRange.LAST_24_HOURS,
        ) is None


class TestDataPoint:
    def test_discord_data_point_to_dict(self):
        point = DiscordAnalyticsDataPoint(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            metric=DiscordAnalyticsMetric.MESSAGE_COUNT,
            value=5,
            dimensions={"d": 1},
            metadata={"m": 2},
        )
        d = point.to_dict()
        assert d["metric"] == "message_count"
        assert d["value"] == 5

    def test_google_data_point_to_dict(self):
        point = GoogleChatAnalyticsDataPoint(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            metric=GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            value=5,
            dimensions={},
            metadata={},
        )
        d = point.to_dict()
        assert d["metric"] == "message_count"


class TestCsvEscapingBugs:
    """BUG: _convert_to_csv does not escape embedded quotes -> malformed CSV."""

    def test_discord_csv_escapes_embedded_quotes(self, discord_engine):
        import csv as csv_mod

        point = DiscordAnalyticsDataPoint(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            metric=DiscordAnalyticsMetric.MESSAGE_COUNT,
            value=3,
            dimensions={"note": 'said "hello" to everyone'},
            metadata={},
        )
        csv_data = discord_engine._convert_to_csv([point])
        parsed = list(csv_mod.reader(io.StringIO(csv_data)))
        assert len(parsed) == 2
        assert len(parsed[1]) == 5
        assert parsed[1][3] == json.dumps(point.dimensions)

    def test_google_csv_escapes_embedded_quotes(self, google_engine):
        import csv as csv_mod

        point = GoogleChatAnalyticsDataPoint(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            metric=GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            value=3,
            dimensions={"note": 'quoted "value" here'},
            metadata={},
        )
        csv_data = google_engine._convert_to_csv([point])
        parsed = list(csv_mod.reader(io.StringIO(csv_data)))
        assert len(parsed) == 2
        assert len(parsed[1]) == 5
        assert parsed[1][3] == json.dumps(point.dimensions)
