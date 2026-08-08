"""
Coverage-push tests for comms integration services (R84 wave).

Drives line coverage of:
  integrations/slack_enhanced_service.py
  integrations/slack_analytics_engine.py
  integrations/discord_enhanced_service.py
  integrations/discord_analytics_engine.py
  integrations/google_chat_analytics_engine.py
  integrations/teams_enhanced_service.py
  integrations/chat_orchestrator.py

All network/DB/LLM calls are mocked.
"""
import asyncio
import json
import os
import re
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from integrations.slack_enhanced_service import (
    SlackEnhancedService,
    SlackWorkspace,
    SlackChannel,
    SlackMessage,
    SlackFile,
    SlackEventType,
    SlackConnectionStatus,
    SlackRateLimiter,
)
from integrations.slack_analytics_engine import (
    SlackAnalyticsEngine,
    AnalyticsDataPoint,
    AnalyticsReport,
    AnalyticsMetric,
    AnalyticsTimeRange,
    AnalyticsGranularity,
    LLMSentiment,
    LLMTopics,
)
from integrations.discord_enhanced_service import (
    DiscordEnhancedService,
    DiscordGuild,
    DiscordChannel,
    DiscordMessage,
    DiscordUser,
    DiscordChannelType,
    DiscordConnectionStatus,
    DiscordRateLimiter,
)
from integrations.discord_analytics_engine import (
    DiscordAnalyticsEngine,
    DiscordAnalyticsDataPoint,
    DiscordAnalyticsMetric,
    DiscordAnalyticsTimeRange,
    DiscordAnalyticsGranularity,
)
from integrations.google_chat_analytics_engine import (
    GoogleChatAnalyticsEngine,
    GoogleChatAnalyticsDataPoint,
    GoogleChatAnalyticsMetric,
    GoogleChatAnalyticsTimeRange,
    GoogleChatAnalyticsGranularity,
)
from integrations import chat_orchestrator as co

BACKEND = "/Users/rushiparikh/projects/atom/backend"


def _teams_module():
    import importlib
    return importlib.import_module("integrations.teams_enhanced_service")


def _slack_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE slack_workspaces (
        team_id TEXT, team_name TEXT, domain TEXT, url TEXT, icon_url TEXT,
        enterprise_id TEXT, enterprise_name TEXT, access_token TEXT, bot_token TEXT,
        user_id TEXT, bot_id TEXT, scopes TEXT, created_at TEXT, last_sync TEXT,
        is_active INTEGER, settings TEXT)"""
    )
    return conn


def _redis_mock():
    r = MagicMock()
    r.get.return_value = None
    r.setex = AsyncMock()
    r.lpush = AsyncMock()
    r.ltrim = AsyncMock()
    r.keys.return_value = []
    r.close = MagicMock()
    return r


# ============================================================================
# slack_enhanced_service
# ============================================================================

class TestSlackRateLimiterRedis:
    async def test_redis_limit_not_exceeded(self):
        r = _redis_mock()
        r.get.return_value = None
        r.pipeline.return_value = r
        r.incr = MagicMock()
        r.expire = MagicMock()
        r.execute = MagicMock()
        limiter = SlackRateLimiter(r)
        assert await limiter.check_limit("T1", "chat.postMessage") is True
        r.incr.assert_called_once()

    async def test_redis_limit_exceeded(self):
        r = _redis_mock()
        r.get.return_value = "5"
        limiter = SlackRateLimiter(r)
        assert await limiter.check_limit("T1", "chat.postMessage") is False

    async def test_redis_window_search(self):
        r = _redis_mock()
        r.get.return_value = "200"
        limiter = SlackRateLimiter(r)
        assert await limiter.check_limit("T1", "search.messages") is False


class TestSlackDataClasses:
    def test_workspace_defaults(self):
        ws = SlackWorkspace(team_id="T1", team_name="n", domain="d", url="u")
        assert ws.scopes == []
        assert ws.created_at.tzinfo is not None
        assert ws.settings == {}

    def test_slack_file_post_init(self):
        f = SlackFile(
            file_id="F1", name="n", title="t", mimetype="m", filetype="t",
            pretty_type="p", size=1, url_private="u", permalink="p",
            user_id="U1", user_name="n", timestamp="1700000000",
            metadata=None,
        )
        assert f.created is not None
        assert f.metadata == {}

    def test_slack_file_post_init_invalid_ts(self):
        with pytest.raises(ValueError):
            SlackFile(
                file_id="F1", name="n", title="t", mimetype="m", filetype="t",
                pretty_type="p", size=1, url_private="u", permalink="p",
                user_id="U1", user_name="n", timestamp="not-a-number",
            )


class TestSlackClientErrors:
    def test_get_client_exception(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.clients = {}
        with patch.object(svc, "_get_workspace", side_effect=RuntimeError("boom")):
            assert svc._get_client("T1") is None

    def test_get_sync_client_exception(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        with patch.object(svc, "_get_workspace", side_effect=RuntimeError("boom")):
            assert svc._get_sync_client("T1") is None


class TestSlackWorkspaceStorage:
    def test_get_workspace_from_db(self):
        conn = _slack_db()
        conn.execute(
            "INSERT INTO slack_workspaces VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("T1", "n", "d", "u", None, None, None, "tok", None, "U1", None,
             "[]", "2026-01-01T00:00:00+00:00", None, 1, "{}"),
        )
        svc = SlackEnhancedService(tenant_id="default", config={"database": conn})
        ws = svc._get_workspace("T1")
        assert ws.team_id == "T1"
        assert ws.access_token == "tok"

    def test_get_workspace_from_redis_cache(self):
        r = _redis_mock()
        ws = SlackWorkspace(team_id="T1", team_name="n", domain="d", url="u")
        r.get.return_value = json.dumps({
            "team_id": "T1", "team_name": "n", "domain": "d", "url": "u",
            "scopes": [], "created_at": "2026-01-01T00:00:00+00:00", "settings": {},
        })
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.redis_client = r
        got = svc._get_workspace("T1")
        assert got.team_id == "T1"

    def test_get_workspace_token_storage_error(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        with patch(
            "integrations.slack_enhanced_service.token_storage.get_token",
            side_effect=RuntimeError("boom"),
        ):
            assert svc._get_workspace("T1") is None

    def test_get_workspace_db_error(self):
        db = MagicMock()
        db.execute.side_effect = RuntimeError("db down")
        svc = SlackEnhancedService(tenant_id="default", config={"database": db})
        assert svc._get_workspace("T1") is None

    def test_save_workspace_db_success(self):
        conn = _slack_db()
        svc = SlackEnhancedService(tenant_id="default", config={"database": conn})
        ws = SlackWorkspace(team_id="T1", team_name="n", domain="d", url="u")
        assert svc._save_workspace(ws) is True
        row = conn.execute("SELECT * FROM slack_workspaces").fetchone()
        assert row["team_id"] == "T1"

    def test_save_workspace_db_failure(self):
        db = MagicMock()
        db.execute.side_effect = RuntimeError("boom")
        svc = SlackEnhancedService(tenant_id="default", config={"database": db})
        ws = SlackWorkspace(team_id="T1", team_name="n", domain="d", url="u")
        assert svc._save_workspace(ws) is False

    def test_save_workspace_redis(self):
        r = _redis_mock()
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.redis_client = r
        ws = SlackWorkspace(team_id="T1", team_name="n", domain="d", url="u")
        assert svc._save_workspace(ws) is True
        r.setex.assert_called_once()

    def test_get_workspaces_from_db_with_user(self):
        conn = _slack_db()
        for i, uid in enumerate(("U1", "U2")):
            conn.execute(
                "INSERT INTO slack_workspaces VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (f"T{i}", "n", "d", "u", None, None, None, "tok", None, uid, None,
                 "[]", "2026-01-01T00:00:00+00:00", None, 1, "{}"),
            )
        svc = SlackEnhancedService(tenant_id="default", config={"database": conn})
        async def run():
            return await svc.get_workspaces("U1")
        workspaces = asyncio.run(run())
        assert len(workspaces) == 1
        assert workspaces[0].user_id == "U1"

    async def test_get_workspaces_from_cache(self):
        r = _redis_mock()
        r.keys.return_value = ["workspace:T1"]
        r.get.return_value = json.dumps({
            "team_id": "T1", "team_name": "n", "domain": "d", "url": "u",
            "user_id": "U1", "scopes": [], "created_at": "2026-01-01T00:00:00+00:00",
            "settings": {},
        })
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.redis_client = r
        workspaces = await svc.get_workspaces("U1")
        assert len(workspaces) == 1

    async def test_get_workspaces_error(self):
        db = MagicMock()
        db.execute.side_effect = RuntimeError("boom")
        svc = SlackEnhancedService(tenant_id="default", config={"database": db})
        assert await svc.get_workspaces() == []


class TestSlackOAuthErrors:
    async def test_generate_oauth_url_error(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.required_scopes = ["a b"]
        svc.client_id = "cid"
        svc.redirect_uri = "http://x"
        with patch.object(svc, "client_id", "cid"):
            url = svc.generate_oauth_url("st", "u1")
        assert url.startswith("https://slack.com/oauth/v2/authorize?")
        with pytest.raises(Exception):
            svc.generate_oauth_url("st", "u1", scopes=[None])

    async def test_exchange_code_save_failure(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        async def fake_post(url, data=None, **kw):
            resp = MagicMock()
            resp.status_code = 200
            resp.json = lambda: {
                "ok": True, "team": {"id": "T1", "name": "n", "domain": "d"},
                "enterprise": {}, "authed_user": {"id": "U1"},
                "access_token": "tok", "bot_user_id": "B1", "scope": "a",
            }
            return resp
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__ = AsyncMock(return_value=MagicMock(post=AsyncMock(side_effect=fake_post)))
            ac.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch.object(svc, "_save_workspace", return_value=False):
                result = await svc.exchange_code_for_tokens("c", "s")
        assert result["ok"] is False

    async def test_exchange_code_http_error(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        async def fake_post(url, data=None, **kw):
            resp = MagicMock()
            resp.status_code = 500
            resp.text = "boom"
            return resp
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__ = AsyncMock(return_value=MagicMock(post=AsyncMock(side_effect=fake_post)))
            ac.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await svc.exchange_code_for_tokens("c", "s")
        assert result["ok"] is False
        assert "error" in result


class TestSlackConnection:
    async def test_connection_test_not_ok(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        client = MagicMock()
        client.auth_test = AsyncMock(return_value={"ok": False, "error": "invalid_auth"})
        with patch.object(svc, "_get_client", return_value=client):
            result = await svc.test_connection("T1")
        assert result["connected"] is False
        assert svc.connection_status["T1"] == SlackConnectionStatus.ERROR

    async def test_connection_test_rate_limited_dict_response(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        from slack_sdk.errors import SlackApiError
        resp = {"data": {"error": "ratelimited"}, "headers": {"Retry-After": 5}}
        err = SlackApiError("rate", response=resp)
        with patch.object(svc, "_get_client", side_effect=err):
            result = await svc.test_connection("T1")
        assert result["status"] == "rate_limited"
        assert result["retry_after"] == 5

    async def test_connection_test_slack_error_non_ratelimited(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        from slack_sdk.errors import SlackApiError
        resp = {"data": {"error": "invalid_auth"}, "headers": {}}
        with patch.object(svc, "_get_client", side_effect=SlackApiError("e", response=resp)):
            result = await svc.test_connection("T1")
        assert result["connected"] is False

    async def test_connection_test_unexpected_error(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        with patch.object(svc, "_get_client", side_effect=RuntimeError("boom")):
            result = await svc.test_connection("T1")
        assert result["connected"] is False


class TestSlackChannelBranches:
    async def test_get_channels_rate_limited(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        with patch.object(svc.rate_limiter, "check_limit", new=AsyncMock(return_value=False)):
            assert await svc.get_channels("T1") == []

    async def test_get_channels_no_client(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        with patch.object(svc.rate_limiter, "check_limit", new=AsyncMock(return_value=True)), \
             patch.object(svc, "_get_client", return_value=None):
            assert await svc.get_channels("T1") == []

    async def test_get_channels_not_ok(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        client = MagicMock()
        client.conversations_list = AsyncMock(return_value={"ok": False, "error": "x"})
        with patch.object(svc.rate_limiter, "check_limit", new=AsyncMock(return_value=True)), \
             patch.object(svc, "_get_client", return_value=client):
            assert await svc.get_channels("T1") == []

    async def test_get_channels_cached_fallback(self):
        from slack_sdk.errors import SlackApiError
        svc = SlackEnhancedService(tenant_id="default", config={})
        r = _redis_mock()
        r.get.return_value = json.dumps([{
            "channel_id": "C1", "name": "general", "workspace_id": "T1",
            "created": "2026-01-01T00:00:00+00:00", "is_private": False,
            "is_archived": False, "is_general": False, "is_shared": False,
            "is_im": False, "is_mpim": False, "num_members": 0, "unread_count": 0,
            "is_muted": False,
        }])
        svc.redis_client = r
        client = MagicMock()
        client.conversations_list = AsyncMock(side_effect=SlackApiError("api down", response={"data": {"error": "x"}}))
        with patch.object(svc.rate_limiter, "check_limit", new=AsyncMock(return_value=True)), \
             patch.object(svc, "_get_client", return_value=client):
            channels = await svc.get_channels("T1")
        assert len(channels) == 1
        assert channels[0].channel_id == "C1"

    async def test_get_channels_unexpected_error(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        client = MagicMock()
        client.conversations_list = AsyncMock(side_effect=RuntimeError("boom"))
        with patch.object(svc.rate_limiter, "check_limit", new=AsyncMock(return_value=True)), \
             patch.object(svc, "_get_client", return_value=client):
            assert await svc.get_channels("T1") == []

    async def test_get_channels_success_with_cache(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        r = _redis_mock()
        svc.redis_client = r
        client = MagicMock()
        client.conversations_list = AsyncMock(return_value={
            "ok": True,
            "channels": [{
                "id": "C1", "name": "general", "purpose": {"value": "p"},
                "topic": {"value": "t"}, "is_private": False, "is_archived": False,
                "is_general": True, "is_shared": False, "is_im": False,
                "is_mpim": False, "num_members": 3, "created": 1700000000,
            }],
        })
        with patch.object(svc.rate_limiter, "check_limit", new=AsyncMock(return_value=True)), \
             patch.object(svc, "_get_client", return_value=client):
            channels = await svc.get_channels("T1", include_private=True)
        assert len(channels) == 1
        r.setex.assert_called_once()


class TestSlackMessageBranches:
    async def _svc_with_client(self, **overrides):
        svc = SlackEnhancedService(tenant_id="default", config={})
        client = MagicMock()
        for name, val in overrides.items():
            setattr(client, name, val)
        svc._get_client = MagicMock(return_value=client)
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        return svc, client

    async def test_send_message_rate_limited(self):
        svc, _ = await self._svc_with_client()
        svc.rate_limiter.check_limit = AsyncMock(return_value=False)
        result = await svc.send_message("T1", "C1", "hi")
        assert result["ok"] is False

    async def test_send_message_no_client(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        svc._get_client = MagicMock(return_value=None)
        result = await svc.send_message("T1", "C1", "hi")
        assert result["ok"] is False

    async def test_send_message_not_ok(self):
        svc, client = await self._svc_with_client(chat_postMessage=AsyncMock(return_value={"ok": False, "error": "e"}))
        result = await svc.send_message("T1", "C1", "hi")
        assert result["ok"] is False

    async def test_send_message_unexpected_error(self):
        svc, client = await self._svc_with_client(chat_postMessage=AsyncMock(side_effect=RuntimeError("boom")))
        result = await svc.send_message("T1", "C1", "hi")
        assert result["ok"] is False

    async def test_get_channel_history_rate_limited(self):
        svc, _ = await self._svc_with_client()
        svc.rate_limiter.check_limit = AsyncMock(return_value=False)
        assert await svc.get_channel_history("T1", "C1") == []

    async def test_get_channel_history_no_client(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        svc._get_client = MagicMock(return_value=None)
        assert await svc.get_channel_history("T1", "C1") == []

    async def test_get_channel_history_not_ok(self):
        svc, client = await self._svc_with_client(conversations_history=AsyncMock(return_value={"ok": False, "error": "e"}))
        assert await svc.get_channel_history("T1", "C1") == []

    async def test_get_channel_history_success(self):
        svc, client = await self._svc_with_client(conversations_history=AsyncMock(return_value={
            "ok": True,
            "messages": [{
                "ts": "1700000000.1", "text": "hi <@U123ABC>", "user": "U1",
                "thread_ts": None, "reply_count": 0, "type": "message",
                "reactions": [], "files": [], "pinned_to": [], "is_starred": False,
                "edited": {"ts": "1"}, "blocks": [], "bot_profile": None,
            }],
        }))
        messages = await svc.get_channel_history("T1", "C1")
        assert len(messages) == 1
        assert messages[0].mentions == ["U123ABC"]

    async def test_get_channel_history_unexpected_error(self):
        svc, client = await self._svc_with_client(conversations_history=AsyncMock(side_effect=RuntimeError("boom")))
        assert await svc.get_channel_history("T1", "C1") == []

    async def test_upload_file_rate_limited(self):
        svc, _ = await self._svc_with_client()
        svc.rate_limiter.check_limit = AsyncMock(return_value=False)
        result = await svc.upload_file("T1", "C1", "/tmp/f")
        assert result["ok"] is False

    async def test_upload_file_no_client(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        svc._get_client = MagicMock(return_value=None)
        result = await svc.upload_file("T1", "C1", "/tmp/f")
        assert result["ok"] is False

    async def test_upload_file_not_ok(self):
        svc, client = await self._svc_with_client(files_upload_v2=AsyncMock(return_value={"ok": False, "error": "e"}))
        result = await svc.upload_file("T1", "C1", "/tmp/f")
        assert result["ok"] is False

    async def test_upload_file_unexpected_error(self):
        svc, client = await self._svc_with_client(files_upload_v2=AsyncMock(side_effect=RuntimeError("boom")))
        result = await svc.upload_file("T1", "C1", "/tmp/f")
        assert result["ok"] is False

    async def test_search_messages_rate_limited(self):
        svc, _ = await self._svc_with_client()
        svc.rate_limiter.check_limit = AsyncMock(return_value=False)
        result = await svc.search_messages("T1", "q")
        assert result["ok"] is False

    async def test_search_messages_no_client(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        svc._get_client = MagicMock(return_value=None)
        result = await svc.search_messages("T1", "q")
        assert result["ok"] is False

    async def test_search_messages_not_ok(self):
        svc, client = await self._svc_with_client(search_messages=AsyncMock(return_value={"ok": False, "error": "e"}))
        result = await svc.search_messages("T1", "q")
        assert result["ok"] is False

    async def test_search_messages_unexpected_error(self):
        svc, client = await self._svc_with_client(search_messages=AsyncMock(side_effect=RuntimeError("boom")))
        result = await svc.search_messages("T1", "q")
        assert result["ok"] is False

    async def test_search_messages_success(self):
        svc, client = await self._svc_with_client(search_messages=AsyncMock(return_value={
            "ok": True,
            "messages": {
                "matches": [{
                    "ts": "1", "text": "hi", "user": "U1", "channel": {"id": "C1", "name": "g"},
                    "thread_ts": None, "reply_count": 0, "reactions": [], "files": [],
                    "pinned_to": [], "is_starred": False, "blocks": [], "score": 0.9,
                }],
                "total": 1, "paging": {},
            },
        }))
        result = await svc.search_messages("T1", "q", channel_id="C1")
        assert result["ok"] is True
        assert result["messages"][0].metadata == {"search_score": 0.9}

    async def test_add_reaction_rate_limited(self):
        svc, _ = await self._svc_with_client()
        svc.rate_limiter.check_limit = AsyncMock(return_value=False)
        result = await svc.add_reaction("T1", "C1", "1", ":thumbsup:")
        assert result["ok"] is False

    async def test_add_reaction_no_client(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        svc._get_client = MagicMock(return_value=None)
        result = await svc.add_reaction("T1", "C1", "1", "thumbsup")
        assert result["ok"] is False

    async def test_add_reaction_not_ok(self):
        svc, client = await self._svc_with_client(reactions_add=AsyncMock(return_value={"ok": False, "error": "e"}))
        result = await svc.add_reaction("T1", "C1", "1", "thumbsup")
        assert result["ok"] is False

    async def test_add_reaction_api_error(self):
        from slack_sdk.errors import SlackApiError
        svc, client = await self._svc_with_client(reactions_add=AsyncMock(side_effect=SlackApiError("no_reaction", response={"data": {"error": "no_reaction"}})))
        result = await svc.add_reaction("T1", "C1", "1", "thumbsup")
        assert result["ok"] is False

    async def test_add_reaction_success(self):
        svc, client = await self._svc_with_client(reactions_add=AsyncMock(return_value={"ok": True}))
        result = await svc.add_reaction("T1", "C1", "1", ":thumbsup:")
        assert result["ok"] is True

    async def test_send_dm_rate_limited(self):
        svc, _ = await self._svc_with_client()
        svc.rate_limiter.check_limit = AsyncMock(return_value=False)
        result = await svc.send_dm("T1", "U1", "hi")
        assert result["ok"] is False

    async def test_send_dm_no_client(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        svc._get_client = MagicMock(return_value=None)
        result = await svc.send_dm("T1", "U1", "hi")
        assert result["ok"] is False

    async def test_send_dm_open_failed(self):
        svc, client = await self._svc_with_client(conversations_open=AsyncMock(return_value={"ok": False, "error": "e"}))
        result = await svc.send_dm("T1", "U1", "hi")
        assert result["ok"] is False

    async def test_send_dm_send_failed(self):
        svc, client = await self._svc_with_client(
            conversations_open=AsyncMock(return_value={"ok": True, "channel": {"id": "D1"}}),
            chat_postMessage=AsyncMock(return_value={"ok": False, "error": "e"}),
        )
        result = await svc.send_dm("T1", "U1", "hi")
        assert result["ok"] is False

    async def test_send_dm_unexpected_error(self):
        svc, client = await self._svc_with_client(conversations_open=AsyncMock(side_effect=RuntimeError("boom")))
        result = await svc.send_dm("T1", "U1", "hi")
        assert result["ok"] is False

    async def test_send_dm_success(self):
        svc, client = await self._svc_with_client(
            conversations_open=AsyncMock(return_value={"ok": True, "channel": {"id": "D1"}}),
            chat_postMessage=AsyncMock(return_value={"ok": True, "message": {"ts": "1"}}),
        )
        result = await svc.send_dm("T1", "U1", "hi", blocks=[{"type": "section"}])
        assert result["ok"] is True
        assert result["message_id"] == "1"

    async def test_create_channel_rate_limited(self):
        svc, _ = await self._svc_with_client()
        svc.rate_limiter.check_limit = AsyncMock(return_value=False)
        result = await svc.create_channel("T1", "new")
        assert result["ok"] is False

    async def test_create_channel_no_client(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        svc._get_client = MagicMock(return_value=None)
        result = await svc.create_channel("T1", "new")
        assert result["ok"] is False

    async def test_create_channel_not_ok(self):
        svc, client = await self._svc_with_client(conversations_create=AsyncMock(return_value={"ok": False, "error": "e"}))
        result = await svc.create_channel("T1", "new")
        assert result["ok"] is False

    async def test_create_channel_api_error(self):
        from slack_sdk.errors import SlackApiError
        svc, client = await self._svc_with_client(conversations_create=AsyncMock(side_effect=SlackApiError("e", response={"data": {"error": "e"}})))
        result = await svc.create_channel("T1", "new")
        assert result["ok"] is False

    async def test_create_channel_success_with_topic(self):
        svc, client = await self._svc_with_client(
            conversations_create=AsyncMock(return_value={
                "ok": True, "channel": {"id": "C1", "name": "new", "is_private": True, "created": 1},
            }),
            conversations_setTopic=AsyncMock(return_value={"ok": True}),
        )
        result = await svc.create_channel("T1", "new", is_private=True, description="desc")
        assert result["ok"] is True

    async def test_invite_rate_limited_pause(self):
        svc, client = await self._svc_with_client(
            conversations_invite=AsyncMock(return_value={"ok": True}),
        )
        calls = {"n": 0}
        async def flaky(ws, ep):
            calls["n"] += 1
            return calls["n"] > 1
        svc.rate_limiter.check_limit = flaky
        with patch("asyncio.sleep", new=AsyncMock()) as sleep_mock:
            result = await svc.invite_to_channel("T1", "C1", ["U1", "U2"])
        sleep_mock.assert_awaited_once()
        assert result["invited_users"] == ["U1", "U2"]
        assert result["failed_users"] == []

    async def test_invite_not_ok(self):
        svc, client = await self._svc_with_client(conversations_invite=AsyncMock(return_value={"ok": False, "error": "e"}))
        result = await svc.invite_to_channel("T1", "C1", ["U1"])
        assert result["failed_users"][0]["error"] == "e"

    async def test_invite_slack_error(self):
        from slack_sdk.errors import SlackApiError
        svc, client = await self._svc_with_client(conversations_invite=AsyncMock(side_effect=SlackApiError("e", response={"data": {"error": "e"}})))
        result = await svc.invite_to_channel("T1", "C1", ["U1"])
        assert result["failed_users"][0]["user_id"] == "U1"

    async def test_invite_unexpected_error(self):
        svc, client = await self._svc_with_client(conversations_invite=AsyncMock(side_effect=RuntimeError("boom")))
        result = await svc.invite_to_channel("T1", "C1", ["U1"])
        assert result["ok"] is False

    async def test_invite_no_client(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc._get_client = MagicMock(return_value=None)
        result = await svc.invite_to_channel("T1", "C1", ["U1"])
        assert result["ok"] is False

    async def test_pin_rate_limited(self):
        svc, _ = await self._svc_with_client()
        svc.rate_limiter.check_limit = AsyncMock(return_value=False)
        result = await svc.pin_message("T1", "C1", "1")
        assert result["ok"] is False

    async def test_pin_no_client(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        svc._get_client = MagicMock(return_value=None)
        result = await svc.pin_message("T1", "C1", "1")
        assert result["ok"] is False

    async def test_pin_not_ok(self):
        svc, client = await self._svc_with_client(pins_add=AsyncMock(return_value={"ok": False, "error": "e"}))
        result = await svc.pin_message("T1", "C1", "1")
        assert result["ok"] is False

    async def test_pin_api_error(self):
        from slack_sdk.errors import SlackApiError
        svc, client = await self._svc_with_client(pins_add=AsyncMock(side_effect=SlackApiError("e", response={"data": {"error": "e"}})))
        result = await svc.pin_message("T1", "C1", "1")
        assert result["ok"] is False

    async def test_pin_success(self):
        svc, client = await self._svc_with_client(pins_add=AsyncMock(return_value={"ok": True}))
        result = await svc.pin_message("T1", "C1", "1")
        assert result["ok"] is True


class TestSlackWebhookBranches:
    async def test_verify_webhook_bad_timestamp(self):
        svc = SlackEnhancedService(tenant_id="default", config={"signing_secret": "sec"})
        assert await svc.verify_webhook_signature(b"{}", "0", "v0=abc") is False

    async def test_verify_webhook_error_path(self):
        svc = SlackEnhancedService(tenant_id="default", config={"signing_secret": "sec"})
        assert await svc.verify_webhook_signature(b"{}", "not-a-number", "v0=x") is False

    async def test_handle_webhook_event_redis_and_handlers(self):
        r = _redis_mock()
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.redis_client = r
        seen = []
        async def handler(event):
            seen.append(event)
            raise RuntimeError("handler boom")
        svc.webhook_handlers.append(handler)
        result = await svc.handle_webhook_event({"team_id": "T1", "event": {"type": "message"}})
        assert result["ok"] is True
        r.lpush.assert_called_once()
        r.ltrim.assert_called_once()
        assert len(seen) == 1

    async def test_handle_webhook_event_error(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        result = await svc.handle_webhook_event({"team_id": None, "event": None})
        assert result["ok"] is False

    async def test_handle_webhook_event_registered_event_handler(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        seen = []
        async def handler(event):
            seen.append(event)
        svc.event_handlers[SlackEventType.MESSAGE].append(handler)
        result = await svc.handle_webhook_event({"team_id": "T1", "event": {"type": "message"}})
        assert result["ok"] is True
        assert len(seen) == 1

    async def test_cache_file_error(self):
        r = _redis_mock()
        r.setex.side_effect = RuntimeError("redis down")
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.redis_client = r
        f = SlackFile(
            file_id="F1", name="n", title="t", mimetype="m", filetype="t",
            pretty_type="p", size=1, url_private="u", permalink="p",
            user_id="U1", user_name="n", timestamp="1700000000",
        )
        await svc._cache_file("T1", f)


class TestSlackAnalyticsAndSync:
    async def test_get_analytics_rate_limited(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=False)
        result = await svc.get_analytics("T1")
        assert result == {"error": "Rate limit exceeded"}

    async def test_get_analytics_not_authenticated(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        svc._get_client = MagicMock(return_value=None)
        result = await svc.get_analytics("T1")
        assert result == {"error": "Not authenticated"}

    async def test_get_analytics_success(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        client = MagicMock()
        client.conversations_list = AsyncMock(return_value={
            "channels": [{"id": "C1"}, {"id": "C2"}],
        })
        client.conversations_history = AsyncMock(return_value={"messages": [{"ts": "1"}]})
        svc._get_client = MagicMock(return_value=client)
        result = await svc.get_analytics("T1")
        assert result["channel_count"] == 2

    async def test_get_analytics_error(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        svc._get_client = MagicMock(side_effect=RuntimeError("boom"))
        result = await svc.get_analytics("T1")
        assert "error" in result

    async def test_sync_to_postgres_cache_success(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.get_analytics = AsyncMock(return_value={
            "channel_count": 3, "message_count": 100, "active_users": 5,
        })
        db = MagicMock()
        existing = MagicMock()
        db.query.return_value.filter_by.return_value.first.side_effect = [existing, None, None]
        with patch("core.database.SessionLocal", return_value=db):
            result = await svc.sync_to_postgres_cache("T1")
        assert result["success"] is True
        assert result["metrics_synced"] == 3
        existing.value = 99
        existing.last_synced_at = None

    async def test_sync_to_postgres_cache_analytics_error(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.get_analytics = AsyncMock(return_value={"error": "boom"})
        result = await svc.sync_to_postgres_cache("T1")
        assert result["success"] is False

    async def test_sync_to_postgres_cache_db_error(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.get_analytics = AsyncMock(return_value={"channel_count": 1})
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.side_effect = RuntimeError("db down")
        with patch("core.database.SessionLocal", return_value=db):
            result = await svc.sync_to_postgres_cache("T1")
        assert result["success"] is True  # inner error swallowed, rolled back
        db.rollback.assert_called_once()

    async def test_sync_to_postgres_cache_session_error(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        svc.get_analytics = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("core.database.SessionLocal", side_effect=RuntimeError("no session")):
            result = await svc.sync_to_postgres_cache("T1")
        assert result["success"] is False


class TestSlackOperationDispatch:
    async def test_execute_operation_unsupported(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        result = await svc.execute_operation("nope", {})
        assert result["success"] is False

    async def test_send_message_operation_success(self):
        svc = SlackEnhancedService(tenant_id="default", config={"workspace_id": "T1"})
        svc.send_message = AsyncMock(return_value={"ok": True, "ts": "1"})
        result = await svc._send_message_operation({"channel": "C1", "text": "hi"})
        assert result["success"] is True

    async def test_send_message_operation_missing_params(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        result = await svc._send_message_operation({"channel": "C1"})
        assert result["success"] is False

    async def test_send_message_operation_failure(self):
        svc = SlackEnhancedService(tenant_id="default", config={"workspace_id": "T1"})
        svc.send_message = AsyncMock(return_value={"ok": False, "error": "e"})
        result = await svc._send_message_operation({"channel": "C1", "text": "hi"})
        assert result["success"] is False

    async def test_send_message_operation_exception(self):
        svc = SlackEnhancedService(tenant_id="default", config={"workspace_id": "T1"})
        svc.send_message = AsyncMock(side_effect=RuntimeError("boom"))
        result = await svc._send_message_operation({"channel": "C1", "text": "hi"})
        assert result["success"] is False


class TestSlackClose:
    async def test_close(self):
        svc = SlackEnhancedService(tenant_id="default", config={})
        ac = MagicMock()
        ac.close = AsyncMock()
        sc = MagicMock()
        svc.clients = {"T1": ac}
        svc.sync_clients = {"T1": sc}
        r = _redis_mock()
        svc.redis_client = r
        await svc.close()
        ac.close.assert_awaited_once()
        sc.close.assert_called_once()
        r.close.assert_called_once()


# ============================================================================
# slack_analytics_engine
# ============================================================================

@pytest.fixture
def slack_engine():
    with patch("integrations.slack_analytics_engine.get_llm_service", return_value=MagicMock()):
        yield SlackAnalyticsEngine({"database": None, "redis_client": None})


class TestSlackEngineDataClasses:
    def test_data_point_naive_tz(self):
        p = AnalyticsDataPoint(
            timestamp=datetime(2026, 1, 1), metric=AnalyticsMetric.MESSAGE_VOLUME, value=5,
        )
        assert p.timestamp.tzinfo is not None
        assert p.dimensions == {}
        assert p.metadata == {}

    def test_report_defaults(self):
        r = AnalyticsReport(
            id="1", name="n", description="d",
            metrics=[AnalyticsMetric.MESSAGE_VOLUME],
            time_range=AnalyticsTimeRange.LAST_7_DAYS,
            granularity=AnalyticsGranularity.DAY,
            created_by="u",
        )
        assert r.filters == {}
        assert r.visualizations == []
        assert r.created_at is not None
        assert r.recipients == []


class TestSlackEngineCore:
    async def test_get_analytics_cached(self):
        r = _redis_mock()
        now = datetime.now(timezone.utc)
        r.get.return_value = json.dumps([{
            "timestamp": now.isoformat(), "metric": "message_volume", "value": 1,
            "dimensions": {}, "metadata": {},
        }])
        engine = SlackAnalyticsEngine({"database": None, "redis_client": r})
        data = await engine.get_analytics(
            AnalyticsMetric.MESSAGE_VOLUME, AnalyticsTimeRange.TODAY,
            AnalyticsGranularity.HOUR, None, None, None, None,
        )
        assert len(data) == 1
        assert data[0].value == 1

    async def test_get_analytics_no_processor(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        with patch.object(engine, "_fetch_data", new=AsyncMock(return_value=[])):
            assert await engine.get_analytics(
                AnalyticsMetric.MESSAGE_VOLUME, AnalyticsTimeRange.TODAY, filters={}
            ) == []

    async def test_get_analytics_error(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        with patch.object(engine, "_generate_cache_key", side_effect=RuntimeError("boom")):
            assert await engine.get_analytics(
                AnalyticsMetric.MESSAGE_VOLUME, AnalyticsTimeRange.TODAY
            ) == []

    async def test_get_insights_no_data(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        with patch.object(engine, "get_analytics", new=AsyncMock(return_value=[])):
            assert await engine.get_insights(AnalyticsMetric.MESSAGE_VOLUME, AnalyticsTimeRange.TODAY) == {}

    async def test_get_insights_all_metrics(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        points = [
            AnalyticsDataPoint(
                timestamp=datetime.now(timezone.utc),
                metric=AnalyticsMetric.MESSAGE_VOLUME, value=10,
                dimensions={"user_id": "U1", "channel_id": "C1"},
            ),
            AnalyticsDataPoint(
                timestamp=datetime.now(timezone.utc),
                metric=AnalyticsMetric.MESSAGE_VOLUME, value=20,
                dimensions={"user_id": "U2", "channel_id": "C2"},
            ),
        ]
        for metric in (
            AnalyticsMetric.MESSAGE_VOLUME, AnalyticsMetric.USER_ACTIVITY,
            AnalyticsMetric.ENGAGEMENT, AnalyticsMetric.RESPONSE_TIME,
            AnalyticsMetric.SENTIMENT,
        ):
            with patch.object(engine, "get_analytics", new=AsyncMock(return_value=points)):
                insights = await engine.get_insights(metric, AnalyticsTimeRange.TODAY)
            assert insights["metric"] == metric.value
            assert "data_points" in insights

    async def test_get_insights_error(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        with patch.object(engine, "get_analytics", new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert await engine.get_insights(AnalyticsMetric.MESSAGE_VOLUME, AnalyticsTimeRange.TODAY) == {}


class TestSlackEngineReports:
    async def test_generate_report_not_found(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        result = await engine.generate_report("nope")
        assert "error" in result

    async def test_generate_report_success_with_metric_error(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        report = AnalyticsReport(
            id="1", name="n", description="d",
            metrics=[AnalyticsMetric.MESSAGE_VOLUME, AnalyticsMetric.SENTIMENT],
            time_range=AnalyticsTimeRange.TODAY,
            granularity=AnalyticsGranularity.DAY,
            created_by="u", visualizations=["bar"],
        )
        engine.reports["1"] = report
        points = [AnalyticsDataPoint(
            timestamp=datetime.now(timezone.utc), metric=AnalyticsMetric.MESSAGE_VOLUME, value=1,
        )]
        engine.get_analytics = AsyncMock(return_value=points)
        engine.get_insights = AsyncMock(side_effect=[{"x": 1}, RuntimeError("boom")])
        result = await engine.generate_report("1")
        assert result["id"] == "1"
        assert len(result["metrics"]) == 2

    async def test_get_top_users(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        points = [
            AnalyticsDataPoint(timestamp=datetime.now(timezone.utc), metric=AnalyticsMetric.MESSAGE_VOLUME,
                               value=5, dimensions={"user_id": "U1"}),
            AnalyticsDataPoint(timestamp=datetime.now(timezone.utc), metric=AnalyticsMetric.MESSAGE_VOLUME,
                               value=3, dimensions={"user_id": "U2"}),
            AnalyticsDataPoint(timestamp=datetime.now(timezone.utc), metric=AnalyticsMetric.MESSAGE_VOLUME,
                               value=9, dimensions={}),
        ]
        with patch.object(engine, "get_analytics", new=AsyncMock(return_value=points)):
            top = await engine.get_top_users(AnalyticsMetric.MESSAGE_VOLUME, AnalyticsTimeRange.TODAY)
        assert top[0]["user_id"] == "U1"

    async def test_get_top_users_error(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        with patch.object(engine, "get_analytics", new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert await engine.get_top_users(AnalyticsMetric.MESSAGE_VOLUME, AnalyticsTimeRange.TODAY) == []

    async def test_get_top_channels(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        points = [AnalyticsDataPoint(
            timestamp=datetime.now(timezone.utc), metric=AnalyticsMetric.MESSAGE_VOLUME,
            value=7, dimensions={"channel_id": "C1"},
        )]
        with patch.object(engine, "get_analytics", new=AsyncMock(return_value=points)):
            top = await engine.get_top_channels(AnalyticsMetric.MESSAGE_VOLUME, AnalyticsTimeRange.TODAY)
        assert top[0]["channel_id"] == "C1"

    async def test_get_trending_topics(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        points = [
            AnalyticsDataPoint(timestamp=datetime.now(timezone.utc), metric=AnalyticsMetric.TOPICS,
                               value=["ai", "sales"]),
            AnalyticsDataPoint(timestamp=datetime.now(timezone.utc), metric=AnalyticsMetric.TOPICS,
                               value="ai, marketing"),
        ]
        with patch.object(engine, "get_analytics", new=AsyncMock(return_value=points)):
            topics = await engine.get_trending_topics(AnalyticsTimeRange.TODAY)
        assert topics[0]["topic"] == "ai"

    async def test_get_engagement_heatmap(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        points = [
            AnalyticsDataPoint(timestamp=datetime.now(timezone.utc), metric=AnalyticsMetric.ENGAGEMENT,
                               value=4),
            AnalyticsDataPoint(timestamp=datetime.now(timezone.utc) - timedelta(hours=1),
                               metric=AnalyticsMetric.ENGAGEMENT, value=2),
        ]
        with patch.object(engine, "get_analytics", new=AsyncMock(return_value=points)):
            result = await engine.get_engagement_heatmap(AnalyticsTimeRange.TODAY)
        assert len(result["heatmap"]) == 7
        assert result["max_value"] == 4

    async def test_predict_message_volume_insufficient(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        with patch.object(engine, "get_analytics", new=AsyncMock(return_value=[])):
            result = await engine.predict_message_volume()
        assert "error" in result

    async def test_predict_message_volume_success(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        now = datetime.now(timezone.utc)
        points = []
        for i in range(170):
            points.append(AnalyticsDataPoint(
                timestamp=now - timedelta(hours=i), metric=AnalyticsMetric.MESSAGE_VOLUME,
                value=float(i % 10 + 1),
            ))
        with patch.object(engine, "get_analytics", new=AsyncMock(return_value=points)):
            result = await engine.predict_message_volume(hours_ahead=2)
        assert "predictions" in result
        assert len(result["predictions"]) == 2

    async def test_get_productivity_metrics(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        points = [AnalyticsDataPoint(
            timestamp=datetime.now(timezone.utc), metric=AnalyticsMetric.MESSAGE_VOLUME, value=10,
        )]
        engine.get_analytics = AsyncMock(return_value=points)
        result = await engine.get_productivity_metrics(AnalyticsTimeRange.TODAY)
        assert result["overall_productivity"] >= 0
        assert "trends" in result


class TestSlackEngineProcessors:
    def _raw(self, ts=None, **kw):
        item = {"timestamp": (ts or datetime.now(timezone.utc)).isoformat(), "text": "task decision"}
        item.update(kw)
        return item

    async def test_process_message_volume(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        data = await engine._process_message_volume(
            [self._raw(), self._raw()], AnalyticsGranularity.HOUR
        )
        assert len(data) == 1
        data2 = await engine._process_message_volume([self._raw()], AnalyticsGranularity.WEEK)
        assert len(data2) == 1

    async def test_process_user_activity(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        ts = datetime.now(timezone.utc)
        data = await engine._process_user_activity(
            [self._raw(ts=ts, user_id="U1"), self._raw(ts=ts, user_id="U1")],
            AnalyticsGranularity.HOUR,
        )
        assert data and data[0].value == 1
        data2 = await engine._process_user_activity(
            [self._raw(ts=ts, user_id="U1")], AnalyticsGranularity.DAY
        )
        assert data2

    async def test_process_engagement(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        data = await engine._process_engagement(
            [self._raw(reactions=[{"name": "x"}], reply_count=2, mentions=["U2"])],
            AnalyticsGranularity.HOUR,
        )
        assert data[0].value == 1 + 4 + 3
        data2 = await engine._process_engagement([self._raw()], AnalyticsGranularity.WEEK)
        assert data2

    async def test_process_response_time(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        data = await engine._process_response_time(
            [self._raw(response_time_seconds=5), self._raw(response_time_seconds=15)],
            AnalyticsGranularity.HOUR,
        )
        assert data[0].value == 10.0
        assert data[0].dimensions["min_response_time"] == 5
        data2 = await engine._process_response_time([self._raw()], AnalyticsGranularity.DAY)
        assert data2 == []

    async def test_process_sentiment(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        engine._analyze_sentiment = AsyncMock(return_value={"score": 0.5, "label": "positive"})
        data = await engine._process_sentiment(
            [self._raw(text="great job"), self._raw(text="")], AnalyticsGranularity.HOUR
        )
        assert data[0].value == 0.5
        data2 = await engine._process_sentiment([self._raw(text="")], AnalyticsGranularity.DAY)
        assert data2 == []

    async def test_process_collaboration(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        data = await engine._process_collaboration(
            [self._raw(thread_ts="1", files=[{"id": "f"}], mentions=["U1"])],
            AnalyticsGranularity.HOUR,
        )
        assert data[0].value == 2 + 1 + 1.5
        data2 = await engine._process_collaboration([self._raw()], AnalyticsGranularity.WEEK)
        assert data2

    async def test_process_productivity(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        data = await engine._process_productivity(
            [self._raw(text="create task"), self._raw(text="we agreed and decided")],
            AnalyticsGranularity.HOUR,
        )
        assert data[0].value == 3 + 5
        data2 = await engine._process_productivity([self._raw()], AnalyticsGranularity.DAY)
        assert data2

    async def test_process_topics(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        engine._extract_topics = AsyncMock(return_value={"topics": ["ai"]})
        data = await engine._process_topics(
            [self._raw(text="ai"), self._raw(text="")], AnalyticsGranularity.HOUR
        )
        assert data[0].value == ["ai"]
        data2 = await engine._process_topics([self._raw()], AnalyticsGranularity.DAY)
        assert data2

    async def test_process_reactions(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        data = await engine._process_reactions(
            [self._raw(reactions=[{"name": "thumbsup", "count": 2}, {"name": "fire", "count": 1}])],
            AnalyticsGranularity.HOUR,
        )
        assert data[0].value == 3
        data2 = await engine._process_reactions([self._raw()], AnalyticsGranularity.WEEK)
        assert data2

    async def test_process_file_sharing(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        data = await engine._process_file_sharing(
            [self._raw(files=[{"filetype": "png", "size": 100}, {"filetype": "png", "size": 300}])],
            AnalyticsGranularity.HOUR,
        )
        assert data[0].value == 2
        assert data[0].dimensions["average_file_size"] == 200
        data2 = await engine._process_file_sharing([self._raw()], AnalyticsGranularity.DAY)
        assert data2


class TestSlackEngineHelpers:
    def test_cache_key(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        key = engine._generate_cache_key(
            AnalyticsMetric.MESSAGE_VOLUME, AnalyticsTimeRange.TODAY,
            AnalyticsGranularity.HOUR, {"a": 1}, "T1", ["C2", "C1"], ["U2", "U1"],
        )
        assert "C1" in key and "C2" in key

    async def test_fetch_data_db(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        engine = SlackAnalyticsEngine({"database": conn, "redis_client": None})
        data = await engine._fetch_data(
            AnalyticsMetric.MESSAGE_VOLUME, AnalyticsTimeRange.TODAY, None, None, None, None
        )
        assert data == []

    async def test_fetch_data_mock(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        data = await engine._fetch_data(
            AnalyticsMetric.MESSAGE_VOLUME, AnalyticsTimeRange.LAST_7_DAYS, None, None, None, None
        )
        assert len(data) > 0

    async def test_fetch_data_error(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        with patch.object(engine, "_get_date_range", side_effect=RuntimeError("boom")):
            data = await engine._fetch_data(
                AnalyticsMetric.MESSAGE_VOLUME, AnalyticsTimeRange.TODAY, None, None, None, None
            )
        assert data == []

    def test_get_date_range_all(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        for tr in AnalyticsTimeRange:
            start, end = engine._get_date_range(tr)
            assert start <= end

    def test_parse_timestamp_branches(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        assert engine._parse_timestamp("") is None
        assert engine._parse_timestamp("1700000000").tzinfo is not None
        assert engine._parse_timestamp("2026-01-01T00:00:00Z").tzinfo is not None
        assert engine._parse_timestamp("2026-01-01 00:00:00") == datetime(2026, 1, 1)
        assert engine._parse_timestamp("garbage") is None

    def test_group_helpers(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        items = [{"timestamp": "1700000000.123"}]
        assert len(engine._group_by_hour(items, "timestamp")) == 1
        assert len(engine._group_by_day(items, "timestamp")) == 1
        assert len(engine._group_by_raw_timestamp(items)) == 1
        assert len(engine._group_by_hour([{"timestamp": "bad"}], "timestamp")) == 0

    async def test_analyze_sentiment_llm(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        llm = MagicMock()
        llm.generate_structured = AsyncMock(return_value=LLMSentiment(score=0.9, label="positive", confidence=1.0))
        engine.llm_service = llm
        result = await engine._analyze_sentiment("amazing work team")
        assert result["method"] == "llm_service"
        assert result["score"] == 0.9

    async def test_analyze_sentiment_llm_none(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        llm = MagicMock()
        llm.generate_structured = AsyncMock(return_value=None)
        engine.llm_service = llm
        engine.use_vader = False
        result = await engine._analyze_sentiment("amazing work team")
        assert result["method"] == "fallback"

    async def test_analyze_sentiment_llm_fail_vader(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        llm = MagicMock()
        llm.generate_structured = AsyncMock(side_effect=RuntimeError("boom"))
        engine.llm_service = llm
        analyzer = MagicMock()
        analyzer.polarity_scores.return_value = {"compound": -0.8}
        engine.vader_analyzer = analyzer
        engine.use_vader = True
        result = await engine._analyze_sentiment("terrible work team")
        assert result["method"] == "vader"
        assert result["label"] == "negative"

    async def test_analyze_sentiment_empty(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        result = await engine._analyze_sentiment("")
        assert result["method"] == "empty"

    def test_sentiment_distribution(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        assert engine._get_sentiment_distribution([]) == {"positive": 0, "neutral": 0, "negative": 0}
        dist = engine._get_sentiment_distribution([0.5, -0.5, 0.0])
        assert dist["positive"] == pytest.approx(1 / 3)
        assert dist["negative"] == pytest.approx(1 / 3)

    async def test_extract_topics_llm(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        llm = MagicMock()
        llm.generate_structured = AsyncMock(return_value=LLMTopics(topics=["a", "b"], confidence=0.8))
        engine.llm_service = llm
        result = await engine._extract_topics("talk about #pricing and #launch")
        assert result["method"] == "llm_service"

    async def test_extract_topics_fallback(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        llm = MagicMock()
        llm.generate_structured = AsyncMock(side_effect=RuntimeError("boom"))
        engine.llm_service = llm
        result = await engine._extract_topics("talk about #pricing and #launch")
        assert result["method"] == "keyword_fallback"
        assert result["topics"] == ["pricing", "launch"]

    async def test_extract_topics_empty(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        result = await engine._extract_topics("")
        assert result["method"] == "empty"

    def test_train_lda_not_available(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        with patch("integrations.slack_analytics_engine.SKLEARN_AVAILABLE", False):
            result = engine.train_lda_model(["a" * 50, "b" * 50], num_topics=2)
        assert result["success"] is False

    def test_train_lda_success(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        texts = ["the quick brown fox jumps", "lazy dog sleeps all day",
                 "fox chases the dog", "dog eats the fox food"] * 3
        result = engine.train_lda_model(texts, num_topics=2)
        assert result["success"] is True
        assert engine.lda_model is not None

    def test_add_training_texts(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        assert engine.add_training_texts(["a", "b"]) == 2
        assert engine.add_training_texts(["c"], timestamps=[datetime.now(timezone.utc)]) == 1
        assert engine.get_training_corpus_size()["total_texts"] == 3

    def test_calculate_score(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        points = [AnalyticsDataPoint(timestamp=datetime.now(timezone.utc), metric=AnalyticsMetric.MESSAGE_VOLUME, value=10),
                  AnalyticsDataPoint(timestamp=datetime.now(timezone.utc), metric=AnalyticsMetric.MESSAGE_VOLUME, value=20)]
        assert engine._calculate_score(points) == pytest.approx(0.75)
        assert engine._calculate_score(points, reverse=True) == pytest.approx(0.25)
        assert engine._calculate_score([]) == 0

    def test_calculate_trends(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        def pts(vals):
            return [AnalyticsDataPoint(timestamp=datetime.now(timezone.utc), metric=AnalyticsMetric.MESSAGE_VOLUME, value=v) for v in vals]
        assert engine._calculate_trends([("m", pts([1]))])["m_trend"] == "insufficient_data"
        assert engine._calculate_trends([("m", pts([1, 1, 2, 2]))])["m_trend"] == "increasing"
        assert engine._calculate_trends([("m", pts([5, 5, 1, 1]))])["m_trend"] == "decreasing"
        assert engine._calculate_trends([("m", pts([2, 2, 2, 2]))])["m_trend"] == "stable"

    def test_generate_mock_data(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        start = datetime.now(timezone.utc) - timedelta(hours=5)
        data = engine._generate_mock_data(AnalyticsMetric.RESPONSE_TIME, start, datetime.now(timezone.utc))
        assert len(data) >= 4

    def test_redis_caching(self):
        r = _redis_mock()
        engine = SlackAnalyticsEngine({"database": None, "redis_client": r})
        key = "k1"
        point = AnalyticsDataPoint(timestamp=datetime.now(timezone.utc), metric=AnalyticsMetric.MESSAGE_VOLUME, value=1)
        engine._cache_analytics(key, [point])
        r.setex.assert_called_once()
        r.get.return_value = json.dumps([{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metric": "message_volume", "value": 1, "dimensions": {}, "metadata": {},
        }])
        cached = engine._get_cached_analytics(key)
        assert cached is not None
        assert cached[0].value == 1


# ============================================================================
# discord_enhanced_service (additional coverage)
# ============================================================================

class TestDiscordDataClasses:
    def test_guild_icon_url(self):
        g = DiscordGuild(guild_id="1", name="n", owner_id="o", owner_name="o", icon="abc")
        assert g.icon_url == "https://cdn.discordapp.com/icons/1/abc.png"
        g2 = DiscordGuild(guild_id="1", name="n", owner_id="o", owner_name="o", icon="abc", icon_url="x")
        assert g2.icon_url == "x"

    def test_channel_type_flags(self):
        c = DiscordChannel(channel_id="1", name="n", type=DiscordChannelType.VOICE, guild_id="g", guild_name="g")
        assert c.is_voice is True
        c2 = DiscordChannel(channel_id="1", name="n", type=DiscordChannelType.DM, guild_id="g", guild_name="g")
        assert c2.is_private is True

    def test_user_avatar_urls(self):
        u = DiscordUser(user_id="1", username="n", discriminator="0", avatar="aa")
        assert u.avatar_url == "https://cdn.discordapp.com/avatars/1/aa.png"
        u2 = DiscordUser(user_id="1", username="n", discriminator="0", avatar="bb", guild_id="g1")
        assert "g1" in u2.avatar_url
        u3 = DiscordUser(user_id="1", username="n", discriminator="0")
        assert u3.display_name == "n"
        assert u3.is_bot_account is False


class TestDiscordRateLimiter:
    async def test_global_limit_exceeded(self):
        rl = DiscordRateLimiter()
        rl.global_limit["remaining"] = 0
        rl.global_limit["reset_time"] = time.time() + 100
        assert await rl.check_limit("send_message", "c1") is False

    async def test_redis_path(self):
        r = _redis_mock()
        r.pipeline.return_value = r
        rl = DiscordRateLimiter(r)
        assert await rl.check_limit("send_message", "c1") is True

    async def test_redis_exceeded(self):
        r = _redis_mock()
        r.get.return_value = "5"
        rl = DiscordRateLimiter(r)
        assert await rl.check_limit("send_message", "c1") is False

    async def test_local_reset_and_exceeded(self):
        rl = DiscordRateLimiter()
        key = "discord_rate:get_messages:c1"
        rl.local_limits[key] = {"count": 49, "reset": time.time() + 100}
        assert await rl.check_limit("get_messages", "c1") is True
        rl.local_limits[key] = {"count": 50, "reset": time.time() + 100}
        assert await rl.check_limit("get_messages", "c1") is False
        rl.local_limits[key] = {"count": 50, "reset": time.time() - 1}
        assert await rl.check_limit("get_messages", "c1") is True

    def test_update_global_limit(self):
        rl = DiscordRateLimiter()
        rl.update_global_limit(10, 5)
        assert rl.global_limit["remaining"] == 10


class TestDiscordServiceBranches:
    def test_setup_session_error(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        with patch("httpx.AsyncClient", side_effect=RuntimeError("boom")):
            svc._setup_session()
        assert svc.session is None

    async def test_generate_oauth_url_error(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        svc.client_id = "cid"
        svc.redirect_uri = "http://x"
        url = svc.generate_oauth_url("st", "u1")
        assert url.startswith("https://discord.com/oauth2/authorize?")
        with pytest.raises(Exception):
            svc.generate_oauth_url("st", "u1", scopes=[None])

    async def test_exchange_code_http_error(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        async def fake_post(url, data=None, **kw):
            resp = MagicMock()
            resp.status_code = 500
            resp.text = "boom"
            return resp
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__ = AsyncMock(return_value=MagicMock(post=AsyncMock(side_effect=fake_post)))
            ac.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await svc.exchange_code_for_tokens("c", "s")
        assert result["ok"] is False

    async def test_exchange_code_user_info_fail(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        token_resp = MagicMock()
        token_resp.status_code = 200
        token_resp.json = lambda: {"access_token": "tok", "refresh_token": "r", "scope": "identify"}
        user_resp = MagicMock()
        user_resp.status_code = 500
        user_resp.text = "boom"
        async def fake_post(url, data=None, **kw):
            return token_resp
        async def fake_get(url, headers=None):
            return user_resp
        with patch("httpx.AsyncClient") as ac:
            c = MagicMock(post=AsyncMock(side_effect=fake_post), get=AsyncMock(side_effect=fake_get))
            ac.return_value.__aenter__ = AsyncMock(return_value=c)
            ac.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await svc.exchange_code_for_tokens("c", "s")
        assert result["ok"] is False

    async def test_exchange_code_save_fail(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        token_resp = MagicMock()
        token_resp.status_code = 200
        token_resp.json = lambda: {"access_token": "tok", "refresh_token": "r", "scope": "identify"}
        user_resp = MagicMock()
        user_resp.status_code = 200
        user_resp.json = lambda: {"id": "u1", "username": "n"}
        guilds_resp = MagicMock()
        guilds_resp.status_code = 200
        guilds_resp.json = lambda: [{"id": "g1", "name": "g"}]
        async def fake_post(url, data=None, **kw):
            return token_resp
        async def fake_get(url, headers=None):
            return user_resp if "users/@me/guilds" not in url else guilds_resp
        with patch("httpx.AsyncClient") as ac:
            c = MagicMock(post=AsyncMock(side_effect=fake_post), get=AsyncMock(side_effect=fake_get))
            ac.return_value.__aenter__ = AsyncMock(return_value=c)
            ac.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch.object(svc, "_save_guild", return_value=False):
                result = await svc.exchange_code_for_tokens("c", "s")
        assert result["ok"] is True
        assert result["guilds"] == []

    async def test_exchange_code_exception(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        with patch("httpx.AsyncClient", side_effect=RuntimeError("boom")):
            result = await svc.exchange_code_for_tokens("c", "s")
        assert result["ok"] is False

    async def test_test_connection_guild_not_found(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        with patch.object(svc, "_get_guild_by_id", return_value=None):
            result = await svc.test_connection("g1")
        assert result["connected"] is False

    async def test_test_connection_api_failure(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        guild = DiscordGuild(guild_id="g1", name="g", owner_id="o", owner_name="o")
        session = MagicMock()
        session.get = AsyncMock(return_value=MagicMock(status_code=403, text="forbidden"))
        svc.session = session
        with patch.object(svc, "_get_guild_by_id", return_value=guild):
            result = await svc.test_connection("g1")
        assert result["connected"] is False

    async def test_test_connection_no_session(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        guild = DiscordGuild(guild_id="g1", name="g", owner_id="o", owner_name="o")
        svc.session = None
        with patch.object(svc, "_get_guild_by_id", return_value=guild):
            result = await svc.test_connection("g1")
        assert result["connected"] is False

    def test_get_guild_by_id_db(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE discord_guilds (guild_id TEXT, name TEXT, owner_id TEXT, owner_name TEXT,
            scopes TEXT, integration_data TEXT, is_active INTEGER)""")
        conn.execute("INSERT INTO discord_guilds VALUES (?,?,?,?,?,?,?)",
                     ("g1", "g", "o", "on", '["a"]', '{"x": 1}', 1))
        svc = DiscordEnhancedService(tenant_id="default", config={"database": conn})
        guild = svc._get_guild_by_id("g1")
        assert guild.guild_id == "g1"
        assert guild.scopes == ["a"]
        assert guild.integration_data == {"x": 1}

    def test_get_guild_by_id_redis(self):
        r = _redis_mock()
        r.get.return_value = json.dumps({
            "guild_id": "g1", "name": "g", "owner_id": "o", "owner_name": "on",
            "scopes": [], "integration_data": {},
        })
        svc = DiscordEnhancedService(tenant_id="default", config={"redis": {"client": r}})
        guild = svc._get_guild_by_id("g1")
        assert guild.guild_id == "g1"

    def test_get_guild_by_id_neither(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        assert svc._get_guild_by_id("g1") is None

    def test_get_guild_by_id_error(self):
        db = MagicMock()
        db.execute.side_effect = RuntimeError("boom")
        svc = DiscordEnhancedService(tenant_id="default", config={"database": db})
        assert svc._get_guild_by_id("g1") is None

    def test_save_guild_db_success(self):
        from integrations.discord_enhanced_service import _GUILD_COLUMNS
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE discord_guilds (%s)" % ", ".join(f"{c} TEXT" for c in _GUILD_COLUMNS))
        svc = DiscordEnhancedService(tenant_id="default", config={"database": conn})
        guild = DiscordGuild(guild_id="g1", name="g", owner_id="o", owner_name="on")
        assert svc._save_guild(guild) is True
        assert svc.connection_status["g1"] == DiscordConnectionStatus.CONNECTED

    def test_save_guild_db_failure(self):
        db = MagicMock()
        db.execute.side_effect = RuntimeError("boom")
        svc = DiscordEnhancedService(tenant_id="default", config={"database": db})
        guild = DiscordGuild(guild_id="g1", name="g", owner_id="o", owner_name="on")
        assert svc._save_guild(guild) is False

    def test_save_guild_redis(self):
        r = _redis_mock()
        svc = DiscordEnhancedService(tenant_id="default", config={"redis": {"client": r}})
        guild = DiscordGuild(guild_id="g1", name="g", owner_id="o", owner_name="on")
        assert svc._save_guild(guild) is True
        r.setex.assert_called_once()

    async def test_get_guilds_db_user_filter(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE discord_guilds (guild_id TEXT, name TEXT, owner_id TEXT, owner_name TEXT,
            user_id TEXT, is_active INTEGER, scopes TEXT, integration_data TEXT)""")
        for i in range(2):
            conn.execute("INSERT INTO discord_guilds VALUES (?,?,?,?,?,?,?,?)",
                         (f"g{i}", "g", "o", "on", f"u{i}", 1, "[]", "{}"))
        svc = DiscordEnhancedService(tenant_id="default", config={"database": conn})
        guilds = await svc.get_guilds("u1")
        assert len(guilds) == 1

    async def test_get_guilds_cache(self):
        r = _redis_mock()
        r.keys.return_value = ["discord_guild:g1"]
        r.get.return_value = json.dumps({
            "guild_id": "g1", "name": "g", "owner_id": "o", "owner_name": "on",
            "user_id": "u1", "scopes": [], "integration_data": {},
        })
        svc = DiscordEnhancedService(tenant_id="default", config={"redis": {"client": r}})
        guilds = await svc.get_guilds("u1")
        assert len(guilds) == 1

    async def test_get_guilds_error(self):
        db = MagicMock()
        db.execute.side_effect = RuntimeError("boom")
        svc = DiscordEnhancedService(tenant_id="default", config={"database": db})
        assert await svc.get_guilds() == []

    async def test_send_message_rate_limited(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=False)
        result = await svc.send_message("g1", "c1", "hi")
        assert result["ok"] is False

    async def test_send_message_no_session(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        svc.session = None
        result = await svc.send_message("g1", "c1", "hi")
        assert result["ok"] is False

    async def test_send_message_error_status(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        session = MagicMock()
        session.post = AsyncMock(return_value=MagicMock(status_code=429, text="rate"))
        svc.session = session
        result = await svc.send_message("g1", "c1", "hi")
        assert result["ok"] is False

    async def test_send_message_success_with_headers(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        session = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.json = lambda: {"id": "m1", "channel_id": "c1", "guild_id": "g1", "timestamp": "t", "content": "hi"}
        resp.headers = {"X-RateLimit-Remaining": "10", "X-RateLimit-Reset-After": "5"}
        session.post = AsyncMock(return_value=resp)
        svc.session = session
        result = await svc.send_message("g1", "c1", "hi", embed={"title": "x"}, components=[{}], tts=True)
        assert result["ok"] is True
        assert svc.rate_limiter.global_limit["remaining"] == 10

    async def test_get_channel_messages_rate_limited(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=False)
        assert await svc.get_channel_messages("g1", "c1") == []

    async def test_get_channel_messages_no_session(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        svc.session = None
        assert await svc.get_channel_messages("g1", "c1") == []

    async def test_get_channel_messages_error_status(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        session = MagicMock()
        session.get = AsyncMock(return_value=MagicMock(status_code=500, text="err"))
        svc.session = session
        assert await svc.get_channel_messages("g1", "c1") == []

    async def test_get_channel_messages_cached_fallback(self):
        r = _redis_mock()
        r.get.return_value = json.dumps([{
            "message_id": "m1", "content": "hi", "channel_id": "c1", "guild_id": "g1",
            "guild_name": "g", "user_id": "u1", "user_name": "n", "user_discriminator": "0",
            "timestamp": "2026-01-01T00:00:00Z", "type": 0, "pinned": False,
        }])
        svc = DiscordEnhancedService(tenant_id="default", config={"redis": {"client": r}})
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        session = MagicMock()
        session.get = AsyncMock(side_effect=RuntimeError("net"))
        svc.session = session
        messages = await svc.get_channel_messages("g1", "c1")
        assert len(messages) == 1

    async def test_search_messages_rate_limited(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=False)
        result = await svc.search_messages("g1", "c1", "q")
        assert result["ok"] is False

    async def test_search_messages_no_session(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        svc.session = None
        result = await svc.search_messages("g1", "c1", "q")
        assert result["ok"] is False

    async def test_search_messages_error(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        session = MagicMock()
        session.post = AsyncMock(return_value=MagicMock(status_code=500, text="err"))
        svc.session = session
        result = await svc.search_messages("g1", "c1", "q")
        assert result["ok"] is False

    async def test_search_messages_success(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        session = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.json = lambda: {"messages": [{"results": [{"id": "m1"}]}], "total_results": 1}
        session.post = AsyncMock(return_value=resp)
        svc.session = session
        result = await svc.search_messages("g1", "c1", "q", before="b", after="a")
        assert result["ok"] is True

    async def test_get_service_info(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        info = await svc.get_service_info()
        assert info["name"] == "Discord Enhanced Service"

    async def test_sync_to_postgres_cache_guild_not_found(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        with patch.object(svc, "_get_guild_by_id", return_value=None):
            result = await svc.sync_to_postgres_cache("g1")
        assert result["success"] is False

    async def test_sync_to_postgres_cache_success(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        guild = DiscordGuild(guild_id="g1", name="g", owner_id="o", owner_name="on",
                             integration_data={"total_messages": 5})
        guild.member_count = 10
        db = MagicMock()
        with patch.object(svc, "_get_guild_by_id", return_value=guild), \
             patch("core.database.SessionLocal", return_value=db):
            result = await svc.sync_to_postgres_cache("g1")
        assert result["success"] is True
        assert result["metrics_synced"] == 3

    async def test_sync_to_postgres_cache_db_error(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        guild = DiscordGuild(guild_id="g1", name="g", owner_id="o", owner_name="on")
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.side_effect = RuntimeError("db")
        with patch.object(svc, "_get_guild_by_id", return_value=guild), \
             patch("core.database.SessionLocal", return_value=db):
            result = await svc.sync_to_postgres_cache("g1")
        assert result["success"] is False

    async def test_full_sync(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True})
        result = await svc.full_sync("g1")
        assert result["success"] is True

    async def test_close(self):
        svc = DiscordEnhancedService(tenant_id="default", config={})
        ws = MagicMock()
        ws.close = AsyncMock()
        session = MagicMock()
        session.aclose = AsyncMock()
        svc.websocket = ws
        svc.session = session
        await svc.close()
        ws.close.assert_awaited_once()
        session.aclose.assert_awaited_once()
