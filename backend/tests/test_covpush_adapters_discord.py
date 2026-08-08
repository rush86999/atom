"""
Coverage-push + bug-hunt tests for integrations/discord_enhanced_service.py.

TDD target (RED first):
1. DiscordMessage.__post_init__ crashes with AttributeError (self.author
   never exists) -> every message conversion in get_channel_messages fails.
2. DiscordGuild lacks a `permissions` field -> exchange_code_for_tokens
   raises TypeError on the first guild and always fails.
3. DiscordGuild lacks `is_active` + JSON columns are not parsed on DB read
   -> SELECT * round-trip produces TypeError / JSON-string columns.
"""

import asyncio
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest

from integrations.discord_enhanced_service import (
    DiscordChannel,
    DiscordChannelType,
    DiscordConnectionStatus,
    DiscordEnhancedService,
    DiscordEventType,
    DiscordGuild,
    DiscordMessage,
    DiscordPermission,
    DiscordRateLimiter,
    DiscordUser,
)

GUILD_FIELDS = [
    "guild_id", "name", "description", "icon", "icon_url", "splash",
    "discovery_splash", "owner_id", "owner_name", "region", "afk_channel_id",
    "afk_timeout", "embed_enabled", "embed_channel_id", "verification_level",
    "default_message_notifications", "explicit_content_filter", "roles",
    "emojis", "features", "mfa_level", "application_id", "widget_enabled",
    "widget_channel_id", "system_channel_id", "system_channel_flags",
    "rules_channel_id", "max_members", "vanity_url_code", "description_hash",
    "banner", "premium_tier", "premium_subscription_count", "preferred_locale",
    "public_updates_channel_id", "max_video_channel_users",
    "approximate_member_count", "approximate_presence_count", "welcome_screen",
    "nsfw_level", "stage_instances", "stickers", "guild_scheduled_events",
    "is_bot", "is_ready", "created_at", "last_modified_at", "member_count",
    "channel_count", "voice_state_count", "roles_count", "emojis_count",
    "features_count", "is_connected", "access_token", "refresh_token",
    "scopes", "user_id", "integration_data", "is_active",
]


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cols = ", ".join(f"{f} TEXT" for f in GUILD_FIELDS)
    cols = cols.replace("is_active TEXT", "is_active INTEGER DEFAULT 1")
    conn.execute(f"CREATE TABLE discord_guilds ({cols})")
    return conn


class FakeRedis:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.store[key] = value

    def keys(self, pattern):
        prefix = pattern.replace("*", "")
        return [k for k in self.store if k.startswith(prefix)]

    def incr(self, key):
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self.store[key]

    def expire(self, key, ttl):
        return True

    def pipeline(self):
        return self

    def execute(self):
        return []


def _resp(status, json=None, text=None, headers=None):
    return httpx.Response(status, json=json, text=text, headers=headers or {})


class TestDiscordEnumsAndModels:
    def test_event_type_values(self):
        assert DiscordEventType.MESSAGE_CREATE.value == "MESSAGE_CREATE"
        assert DiscordEventType.READY.value == "READY"
        assert len(list(DiscordEventType)) == 19

    def test_connection_status_values(self):
        assert DiscordConnectionStatus.CONNECTED.value == "connected"
        assert DiscordConnectionStatus.RATE_LIMITED.value == "rate_limited"

    def test_channel_type_values(self):
        assert DiscordChannelType.TEXT.value == "GUILD_TEXT"
        assert DiscordChannelType.DM.value == "DM"

    def test_permission_values(self):
        assert DiscordPermission.SEND_MESSAGES.value == 0x00000800
        assert DiscordPermission.ADMINISTRATOR.value == 0x00000008

    def test_guild_post_init_defaults(self):
        g = DiscordGuild(guild_id="1", name="G", owner_id="o", owner_name="O")
        assert g.created_at.tzinfo is not None
        assert g.roles == [] and g.emojis == [] and g.features == []
        assert g.stage_instances == [] and g.stickers == []
        assert g.guild_scheduled_events == [] and g.scopes == []
        assert g.integration_data == {}
        assert g.premium_tier == 0
        assert g.is_active is True

    def test_guild_post_init_icon_url(self):
        g = DiscordGuild(guild_id="1", name="G", owner_id="o", owner_name="O",
                         icon="abc123")
        assert g.icon_url == "https://cdn.discordapp.com/icons/1/abc123.png"

    def test_channel_post_init(self):
        ch = DiscordChannel(channel_id="c", name="gen", type=DiscordChannelType.TEXT,
                            guild_id="g", guild_name="G")
        assert ch.is_text and not ch.is_voice and not ch.is_private
        assert ch.is_stage is False and ch.is_news is False
        assert ch.created_at.tzinfo is not None
        assert ch.permission_overwrites == [] and ch.recipients == []
        ch2 = DiscordChannel(channel_id="c2", name="vc", type=DiscordChannelType.VOICE,
                             guild_id="g", guild_name="G")
        assert ch2.is_voice and not ch2.is_text
        ch3 = DiscordChannel(channel_id="c3", name="dm", type=DiscordChannelType.DM,
                             guild_id="g", guild_name="G")
        assert ch3.is_private
        ch4 = DiscordChannel(channel_id="c4", name="s", type=DiscordChannelType.STAGE,
                             guild_id="g", guild_name="G")
        assert ch4.is_stage and ch4.is_voice
        ch5 = DiscordChannel(channel_id="c5", name="n", type=DiscordChannelType.NEWS,
                             guild_id="g", guild_name="G")
        assert ch5.is_news and ch5.is_text

    def test_message_post_init_flags(self):
        m = DiscordMessage(
            message_id="m1", content="hi", channel_id="c", guild_id="g",
            guild_name="G", user_id="u", user_name="U", user_discriminator="0000",
            timestamp="2026-01-01T00:00:00Z", type=19, pinned=True,
            edited_timestamp="2026-01-01T00:01:00Z", webhook_id="w",
            referenced_message={"message_id": "m0"},
        )
        assert m.is_edited and m.is_pinned and m.is_crossposted
        assert m.is_webhook and not m.is_command and not m.is_system
        assert m.reply_to_id == "m0"
        assert m.mentions == [] and m.embeds == [] and m.stickers == []
        assert m.created_at.tzinfo is not None

    def test_message_post_init_thread_and_types(self):
        m = DiscordMessage(
            message_id="m2", content="", channel_id="thread:123", guild_id="g",
            guild_name="G", user_id="u", user_name="U", user_discriminator="0000",
            timestamp="x", type=20,
        )
        assert m.thread_id == "thread:123"
        assert m.is_command
        m2 = DiscordMessage(
            message_id="m3", content="", channel_id="c", guild_id="g",
            guild_name="G", user_id="u", user_name="U", user_discriminator="0000",
            timestamp="x", type=24,
        )
        assert m2.is_system

    def test_user_post_init(self):
        u = DiscordUser(user_id="1", username="bob", discriminator="0001",
                        avatar="aa", guild_id="9")
        assert u.avatar_url == "https://cdn.discordapp.com/avatars/9/aa.png"
        assert u.display_name == "bob"
        assert u.is_bot_account is False
        u2 = DiscordUser(user_id="1", username="bot", discriminator="0000",
                         bot=True, global_name="Bobby")
        assert u2.display_name == "Bobby"
        assert u2.is_bot_account is True
        assert u2.roles == []


class TestDiscordRateLimiter:
    def test_local_limit_allowed_then_blocked(self):
        rl = DiscordRateLimiter()
        for _ in range(5):
            assert asyncio.run(rl.check_limit("send_message", "c1")) is True
        assert asyncio.run(rl.check_limit("send_message", "c1")) is False

    def test_local_limit_resets_after_window(self):
        rl = DiscordRateLimiter()
        rl.default_limits["send_message"] = 2
        rl.window_times["send_message"] = 0.05
        assert asyncio.run(rl.check_limit("send_message", "c1")) is True
        assert asyncio.run(rl.check_limit("send_message", "c1")) is True
        assert asyncio.run(rl.check_limit("send_message", "c1")) is False
        time.sleep(0.06)
        assert asyncio.run(rl.check_limit("send_message", "c1")) is True

    def test_unknown_endpoint_default(self):
        rl = DiscordRateLimiter()
        assert asyncio.run(rl.check_limit("weird_endpoint", "r1")) is True
        assert asyncio.run(rl.check_limit("weird_endpoint", "r1")) is False

    def test_global_limit_block(self):
        rl = DiscordRateLimiter()
        rl.global_limit["remaining"] = 0
        rl.global_limit["reset_time"] = time.time() + 100
        assert asyncio.run(rl.check_limit("get_guilds", "u1")) is False

    def test_global_limit_reset(self):
        rl = DiscordRateLimiter()
        rl.global_limit["remaining"] = 0
        rl.global_limit["reset_time"] = time.time() - 1
        assert asyncio.run(rl.check_limit("get_guilds", "u1")) is True

    def test_redis_path(self):
        redis = FakeRedis()
        rl = DiscordRateLimiter(redis_client=redis)
        for _ in range(50):
            assert asyncio.run(rl.check_limit("get_messages", "c1")) is True
        assert asyncio.run(rl.check_limit("get_messages", "c1")) is False

    def test_update_global_limit(self):
        rl = DiscordRateLimiter()
        rl.update_global_limit(10, 2)
        assert rl.global_limit["remaining"] == 10
        assert rl.global_limit["reset_time"] > time.time()


def _svc(config=None, bot_token="bot"):
    cfg = dict(config or {})
    cfg.setdefault("bot_token", bot_token)
    return DiscordEnhancedService(tenant_id="t1", config=cfg)


class TestDiscordServiceBasics:
    def test_init_from_config(self):
        svc = _svc({"client_id": "cid", "client_secret": "cs", "redirect_uri": "ru"})
        assert svc.api_base_url == "https://discord.com/api/v10"
        assert svc.client_id == "cid"
        assert svc.bot_token == "bot"
        assert svc.rate_limiter is not None
        assert svc.cipher is None
        assert len(svc.required_scopes) == 8
        assert svc.redis_client is None
        assert svc.session is not None

    def test_get_capabilities(self):
        caps = _svc().get_capabilities()
        assert caps["supports_webhooks"] is True
        assert caps["required_params"] == ["bot_token"]

    def test_health_check_healthy(self):
        h = _svc().health_check()
        assert h["ok"] is True and h["status"] == "healthy"

    def test_health_check_unhealthy(self):
        h = _svc(bot_token=None).health_check()
        assert h["ok"] is False and h["status"] == "unhealthy"
        assert "Missing bot token" in h["message"]

    def test_execute_operation_placeholder(self):
        svc = _svc()
        svc.session.post = AsyncMock(return_value=_resp(200, json={
            "id": "m1", "channel_id": "c1", "guild_id": "g1",
            "timestamp": "2026-01-01T00:00:00.000Z", "content": "hi"}))
        r = asyncio.run(svc.execute_operation("send_message", {
            "guild_id": "g1", "channel_id": "c1", "content": "hi"}))
        assert r["success"] is True
        assert r["result"]["ok"] is True

    def test_execute_operation_unknown(self):
        svc = _svc()
        r = asyncio.run(svc.execute_operation("nope", {}))
        assert r["success"] is False

    def test_execute_operation_error(self):
        svc = _svc()
        svc.session = None
        r = asyncio.run(svc.execute_operation("send_message", {
            "guild_id": "g1", "channel_id": "c1", "content": "hi"}))
        assert r["success"] is False

    def test_token_encryption_no_cipher(self):
        svc = _svc()
        assert svc._encrypt_token("tok") == "tok"
        assert svc._decrypt_token("tok") == "tok"

    def test_token_encryption_with_cipher(self):
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
        svc = _svc({"encryption_key": key.decode()})
        assert svc.cipher is not None
        enc = svc._encrypt_token("secret")
        assert enc != "secret"
        assert svc._decrypt_token(enc) == "secret"

    def test_generate_oauth_url_default(self):
        svc = _svc({"client_id": "cid", "redirect_uri": "http://x/cb"})
        url = svc.generate_oauth_url("st", "u1")
        assert url.startswith("https://discord.com/oauth2/authorize?")
        assert "client_id=cid" in url
        assert "state=st" in url
        assert "permissions=" in url
        assert "scope=bot" in url

    def test_generate_oauth_url_custom_scopes(self):
        svc = _svc({"client_id": "cid", "redirect_uri": "http://x/cb"})
        url = svc.generate_oauth_url("st", "u1", scopes=["identify"])
        assert "scope=identify" in url

    def test_get_service_info(self):
        svc = _svc()
        svc.connection_status["g1"] = DiscordConnectionStatus.CONNECTED
        svc.connection_status["g2"] = DiscordConnectionStatus.ERROR
        info = asyncio.run(svc.get_service_info())
        assert info["name"] == "Discord Enhanced Service"
        assert info["status"]["connected_guilds"] == 1
        assert info["status"]["total_clients"] == 2
        assert info["version"] == "4.0.0"


class TestDiscordExchangeCode:
    class FakeClient:
        def __init__(self, token_status=200, user_status=200, guilds_status=200,
                     guilds=None):
            self.token_status = token_status
            self.user_status = user_status
            self.guilds_status = guilds_status
            self.guilds = guilds

        async def __aenter__(self):
            if self.token_status == 200:
                self.post = AsyncMock(return_value=_resp(200, json={
                    "access_token": "at", "refresh_token": "rt",
                    "scope": "guilds identify email", "token_type": "Bearer"}))
            else:
                self.post = AsyncMock(return_value=_resp(self.token_status, text="bad"))
            if self.user_status == 200:
                self.get = AsyncMock(side_effect=[
                    _resp(200, json={"id": "u1", "username": "alice"}),
                    _resp(self.guilds_status, json=self.guilds or []),
                ])
            else:
                self.get = AsyncMock(return_value=_resp(self.user_status, text="boom"))
            return self

        async def __aexit__(self, *a):
            return False

    def _patch(self, monkeypatch, **kwargs):
        import integrations.discord_enhanced_service as d
        monkeypatch.setattr(d.httpx, "AsyncClient",
                            lambda *a, **k: self.FakeClient(**kwargs))

    def test_exchange_success_no_guilds(self, monkeypatch):
        self._patch(monkeypatch)
        svc = _svc({"client_id": "cid", "client_secret": "cs",
                    "redirect_uri": "http://x/cb"})
        with patch.object(svc, "_save_guild", return_value=True) as sg:
            result = asyncio.run(svc.exchange_code_for_tokens("code", "st"))
        assert result["ok"] is True
        assert result["access_token"] == "at"
        assert result["guilds"] == []
        assert sg.call_count == 0

    def test_exchange_creates_guild(self, monkeypatch):
        self._patch(monkeypatch, guilds=[{
            "id": "g1", "name": "Guild One", "description": "d", "icon": "ic",
            "features": ["f1"], "owner_id": "u1",
            "approximate_member_count": 10, "joined_at": "j",
        }])
        svc = _svc({"client_id": "cid", "client_secret": "cs",
                    "redirect_uri": "http://x/cb"})
        with patch.object(svc, "_save_guild", return_value=True) as sg:
            result = asyncio.run(svc.exchange_code_for_tokens("code", "st"))
        assert result["ok"] is True
        assert len(result["guilds"]) == 1
        assert result["guilds"][0]["guild_id"] == "g1"
        assert result["guilds"][0]["owner"] is True
        assert result["guilds"][0]["member_count"] == 10
        assert sg.call_count == 1
        guild = sg.call_args[0][0]
        assert guild.guild_id == "g1"
        assert guild.access_token == "at"
        assert guild.scopes == ["guilds", "identify", "email"]

    def test_exchange_token_failure(self, monkeypatch):
        self._patch(monkeypatch, token_status=400)
        svc = _svc()
        result = asyncio.run(svc.exchange_code_for_tokens("code", "st"))
        assert result["ok"] is False
        assert "failed" in result["message"]

    def test_exchange_user_fetch_failure(self, monkeypatch):
        self._patch(monkeypatch, user_status=500)
        svc = _svc()
        result = asyncio.run(svc.exchange_code_for_tokens("code", "st"))
        assert result["ok"] is False

    def test_exchange_guilds_fetch_failure(self, monkeypatch):
        self._patch(monkeypatch, guilds_status=500, guilds=[])
        svc = _svc()
        result = asyncio.run(svc.exchange_code_for_tokens("code", "st"))
        assert result["ok"] is True
        assert result["guilds"] == []


class TestDiscordGuildPersistence:
    def test_get_guild_by_id_db_round_trip(self):
        svc = _svc()
        conn = _make_db()
        svc.db = conn
        guild = DiscordGuild(
            guild_id="g1", name="Guild One", owner_id="o1", owner_name="O",
            features=["f1", "f2"], member_count=5,
            integration_data={"total_messages": 42},
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        assert svc._save_guild(guild) is True
        assert svc.connection_status["g1"] == DiscordConnectionStatus.CONNECTED
        loaded = svc._get_guild_by_id("g1")
        assert loaded is not None
        assert loaded.guild_id == "g1"
        assert loaded.name == "Guild One"
        assert loaded.features == ["f1", "f2"]
        assert loaded.integration_data == {"total_messages": 42}
        assert loaded.is_active
        assert int(loaded.member_count) == 5

    def test_get_guild_by_id_not_found(self):
        svc = _svc()
        svc.db = _make_db()
        assert svc._get_guild_by_id("missing") is None

    def test_get_guild_by_id_db_error(self):
        svc = _svc()
        svc.db = MagicMock()
        svc.db.execute.side_effect = Exception("db down")
        assert svc._get_guild_by_id("g1") is None

    def test_get_guild_by_id_no_db_no_redis(self):
        svc = _svc()
        svc.db = None
        svc.redis_client = None
        assert svc._get_guild_by_id("g1") is None

    def test_get_guild_by_id_redis(self):
        svc = _svc()
        redis = FakeRedis()
        svc.redis_client = redis
        guild = DiscordGuild(guild_id="g1", name="G", owner_id="o", owner_name="O",
                             scopes=["identify"])
        svc._save_guild(guild)
        loaded = svc._get_guild_by_id("g1")
        assert loaded is not None
        assert loaded.guild_id == "g1"
        assert loaded.scopes == ["identify"]

    def test_save_guild_redis_error(self):
        svc = _svc()
        redis = MagicMock()
        redis.setex.side_effect = Exception("redis down")
        svc.redis_client = redis
        guild = DiscordGuild(guild_id="g1", name="G", owner_id="o", owner_name="O")
        assert svc._save_guild(guild) is False

    def test_get_guilds_db(self):
        svc = _svc()
        conn = _make_db()
        svc.db = conn
        svc._save_guild(DiscordGuild(guild_id="g1", name="A", owner_id="o1",
                                     owner_name="O", user_id="u1"))
        svc._save_guild(DiscordGuild(guild_id="g2", name="B", owner_id="o2",
                                     owner_name="O", user_id="u2"))
        assert len(asyncio.run(svc.get_guilds())) == 2
        assert len(asyncio.run(svc.get_guilds("u1"))) == 1

    def test_get_guilds_redis(self):
        svc = _svc()
        redis = FakeRedis()
        svc.redis_client = redis
        svc._save_guild(DiscordGuild(guild_id="g1", name="A", owner_id="o",
                                     owner_name="O", user_id="u1"))
        svc._save_guild(DiscordGuild(guild_id="g2", name="B", owner_id="o",
                                     owner_name="O", user_id="u2"))
        guilds = asyncio.run(svc.get_guilds("u1"))
        assert len(guilds) == 1
        assert guilds[0].guild_id == "g1"
        assert len(asyncio.run(svc.get_guilds())) == 2

    def test_get_guilds_error(self):
        svc = _svc()
        svc.db = MagicMock()
        svc.db.execute.side_effect = Exception("down")
        assert asyncio.run(svc.get_guilds()) == []


class TestDiscordConnectionAndMessages:
    def test_test_connection_success(self):
        svc = _svc()
        svc.db = _make_db()
        svc._save_guild(DiscordGuild(guild_id="g1", name="G", owner_id="o",
                                     owner_name="O", member_count=5))
        svc.session.get = AsyncMock(return_value=_resp(200, json={
            "approximate_member_count": 7}))
        result = asyncio.run(svc.test_connection("g1"))
        assert result["connected"] is True
        assert result["guild"]["member_count"] == 7
        assert svc.connection_status["g1"] == DiscordConnectionStatus.CONNECTED

    def test_test_connection_guild_missing(self):
        svc = _svc()
        svc.db = _make_db()
        result = asyncio.run(svc.test_connection("g1"))
        assert result["connected"] is False
        assert svc.connection_status["g1"] == DiscordConnectionStatus.ERROR

    def test_test_connection_api_failure(self):
        svc = _svc()
        svc.db = _make_db()
        svc._save_guild(DiscordGuild(guild_id="g1", name="G", owner_id="o",
                                     owner_name="O"))
        svc.session.get = AsyncMock(return_value=_resp(500))
        result = asyncio.run(svc.test_connection("g1"))
        assert result["connected"] is False

    def test_test_connection_no_session(self):
        svc = _svc()
        svc.db = _make_db()
        svc._save_guild(DiscordGuild(guild_id="g1", name="G", owner_id="o",
                                     owner_name="O"))
        svc.session = None
        result = asyncio.run(svc.test_connection("g1"))
        assert result["connected"] is False

    def test_send_message_success(self):
        svc = _svc()
        resp = _resp(200, json={
            "id": "m1", "channel_id": "c1", "guild_id": "g1",
            "timestamp": "2026-01-01T00:00:00.000Z", "content": "hi"},
            headers={"X-RateLimit-Remaining": "49", "X-RateLimit-Reset-After": "1"})
        svc.session.post = AsyncMock(return_value=resp)
        result = asyncio.run(svc.send_message("g1", "c1", "hi",
                                              embed={"title": "T"}, tts=False))
        assert result["ok"] is True
        assert result["message_id"] == "m1"
        assert svc.rate_limiter.global_limit["remaining"] == 49
        payload = svc.session.post.call_args[1]["json"]
        assert payload["embeds"] == [{"title": "T"}]
        assert "components" not in payload
        assert payload["tts"] is False

    def test_send_message_rate_limited(self):
        svc = _svc()
        rl = DiscordRateLimiter()
        svc.rate_limiter = rl
        rl.default_limits["send_message"] = 1
        asyncio.run(svc.send_message("g1", "c1", "one"))
        result = asyncio.run(svc.send_message("g1", "c1", "two"))
        assert result["ok"] is False
        assert "Rate limit" in result["error"]

    def test_send_message_no_session(self):
        svc = _svc()
        svc.session = None
        result = asyncio.run(svc.send_message("g1", "c1", "hi"))
        assert result["ok"] is False
        assert "session" in result["error"].lower()

    def test_send_message_api_failure(self):
        svc = _svc()
        svc.session.post = AsyncMock(return_value=_resp(429, text="slow down"))
        result = asyncio.run(svc.send_message("g1", "c1", "hi"))
        assert result["ok"] is False
        assert "Message send failed" in result["error"]

    def test_get_channel_messages_success(self):
        svc = _svc()
        svc.db = _make_db()
        svc._save_guild(DiscordGuild(guild_id="g1", name="Guild", owner_id="o",
                                     owner_name="O"))
        svc.session.get = AsyncMock(return_value=_resp(200, json=[{
            "id": "m1", "content": "hello", "channel_id": "c1",
            "author": {"id": "u1", "username": "bob", "discriminator": "0001",
                       "bot": False},
            "member": {"nick": "Bobby"},
            "timestamp": "2026-01-01T10:00:00.000Z", "type": 0,
            "pinned": False, "edited_timestamp": None,
        }]))
        redis = FakeRedis()
        svc.redis_client = redis
        messages = asyncio.run(svc.get_channel_messages("g1", "c1", limit=10))
        assert len(messages) == 1
        assert messages[0].message_id == "m1"
        assert messages[0].guild_name == "Guild"
        assert messages[0].user_display_name == "Bobby"
        assert messages[0].is_bot is False
        assert "discord_messages:c1" in redis.store
        params = svc.session.get.call_args[1]["params"]
        assert params["limit"] == 10

    def test_get_channel_messages_after_before_around(self):
        svc = _svc()
        svc.session.get = AsyncMock(return_value=_resp(200, json=[]))
        asyncio.run(svc.get_channel_messages("g1", "c1", limit=500,
                                             before="b", after="a", around="r"))
        params = svc.session.get.call_args[1]["params"]
        assert params["limit"] == 100
        assert params["before"] == "b" and params["after"] == "a" and params["around"] == "r"

    def test_get_channel_messages_rate_limited(self):
        svc = _svc()
        rl = DiscordRateLimiter()
        svc.rate_limiter = rl
        rl.default_limits["get_messages"] = 1
        asyncio.run(svc.get_channel_messages("g1", "c1"))
        assert asyncio.run(svc.get_channel_messages("g1", "c1")) == []

    def test_get_channel_messages_api_failure_cached_fallback(self):
        svc = _svc()
        svc.session.get = AsyncMock(return_value=_resp(500, text="err"))
        redis = FakeRedis()
        svc.redis_client = redis
        assert asyncio.run(svc.get_channel_messages("g1", "c1")) == []
        cached_msg = DiscordMessage(
            message_id="m9", content="old", channel_id="c1", guild_id="g1",
            guild_name="G", user_id="u", user_name="U", user_discriminator="0000",
            timestamp="x")
        redis.setex("discord_messages:c1", 30, json.dumps(
            [cached_msg.__dict__], default=str))
        cached = asyncio.run(svc.get_channel_messages("g1", "c1"))
        assert len(cached) == 1
        assert cached[0].message_id == "m9"

    def test_get_channel_messages_no_session(self):
        svc = _svc()
        svc.session = None
        assert asyncio.run(svc.get_channel_messages("g1", "c1")) == []

    def test_search_messages_success(self):
        svc = _svc()
        svc.session.post = AsyncMock(return_value=_resp(200, json={
            "messages": [{"results": [{"id": "m1"}]}], "total_results": 1}))
        result = asyncio.run(svc.search_messages("g1", "c1", "query",
                                                 before="b", after="a"))
        assert result["ok"] is True
        assert result["total"] == 1
        assert result["query"] == "query"
        payload = svc.session.post.call_args[1]["json"]
        assert payload["limit"] == 25
        assert payload["min_id"] == "a" and payload["max_id"] == "b"

    def test_search_messages_api_failure(self):
        svc = _svc()
        svc.session.post = AsyncMock(return_value=_resp(500, text="err"))
        result = asyncio.run(svc.search_messages("g1", "c1", "q"))
        assert result["ok"] is False

    def test_search_messages_rate_limited(self):
        svc = _svc()
        rl = DiscordRateLimiter()
        svc.rate_limiter = rl
        rl.default_limits["search_messages"] = 1
        asyncio.run(svc.search_messages("g1", "c1", "q"))
        result = asyncio.run(svc.search_messages("g1", "c1", "q"))
        assert result["ok"] is False

    def test_full_sync(self):
        svc = _svc()
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True})
        result = asyncio.run(svc.full_sync("ws1"))
        assert result["success"] is True
        assert result["workspace_id"] == "ws1"
        assert "timestamp" in result

    def test_close(self):
        svc = _svc()
        svc.websocket = AsyncMock()
        svc.session = AsyncMock()
        asyncio.run(svc.close())
        svc.websocket.close.assert_awaited_once()
        svc.session.aclose.assert_awaited_once()


class TestDiscordPostgresSync:
    def test_sync_success(self):
        svc = _svc()
        svc.db = _make_db()
        svc._save_guild(DiscordGuild(
            guild_id="g1", name="G", owner_id="o", owner_name="O",
            member_count=5, channel_count=2,
            integration_data={"total_messages": 42}))

        fake_session = MagicMock()
        existing = MagicMock()
        fake_session.query.return_value.filter_by.return_value.first.side_effect = [
            None, existing, None,
        ]
        metric_model = MagicMock()

        with patch("core.database.SessionLocal", return_value=fake_session), \
                patch("core.models.IntegrationMetric", metric_model):
            result = asyncio.run(svc.sync_to_postgres_cache("g1"))
        assert result["success"] is True
        assert result["metrics_synced"] == 3
        assert fake_session.add.call_count == 2
        assert existing.value == float(2)

    def test_sync_guild_not_found(self):
        svc = _svc()
        svc.db = _make_db()
        result = asyncio.run(svc.sync_to_postgres_cache("missing"))
        assert result["success"] is False
        assert result["error"] == "Guild not found"

    def test_sync_db_error_rollback(self):
        svc = _svc()
        svc.db = _make_db()
        svc._save_guild(DiscordGuild(guild_id="g1", name="G", owner_id="o",
                                     owner_name="O", member_count=5))
        fake_session = MagicMock()
        fake_session.query.return_value.filter_by.return_value.first.return_value = None
        fake_session.commit.side_effect = Exception("commit failed")
        with patch("core.database.SessionLocal", return_value=fake_session):
            result = asyncio.run(svc.sync_to_postgres_cache("g1"))
        assert result["success"] is False
        fake_session.rollback.assert_called_once()
        fake_session.close.assert_called_once()

    def test_sync_exception(self):
        svc = _svc()
        svc._get_guild_by_id = Mock(side_effect=Exception("boom"))
        result = asyncio.run(svc.sync_to_postgres_cache("g1"))
        assert result["success"] is False
