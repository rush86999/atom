"""
Coverage-push part 3: teams_enhanced_service and chat_orchestrator.
"""
import asyncio
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integrations import chat_orchestrator as co

BACKEND = "/Users/rushiparikh/projects/atom/backend"


def _teams_module():
    import importlib
    return importlib.import_module("integrations.teams_enhanced_service")


def _redis_mock():
    r = MagicMock()
    r.get.return_value = None
    r.setex = AsyncMock()
    r.keys.return_value = []
    r.pipeline.return_value = r
    r.incr = MagicMock()
    r.expire = MagicMock()
    r.execute = MagicMock()
    r.close = MagicMock()
    return r


# ============================================================================
# teams_enhanced_service
# ============================================================================

class TestTeamsDataClasses:
    def test_workspace_defaults(self):
        mod = _teams_module()
        ws = mod.TeamsWorkspace(
            team_id="t1", name="n", description="d", display_name="dn",
            visibility="public", mail_nickname="mn", created_at=datetime.now(timezone.utc),
            created_by="u", tenant_id="ten",
        )
        assert ws.scopes == []
        assert ws.settings == {}

    def test_channel_defaults(self):
        mod = _teams_module()
        ch = mod.TeamsChannel(
            channel_id="c1", name="n", display_name="dn", description="d",
            workspace_id="w1", channel_type="standard",
        )
        assert ch.created_at is not None

    def test_file_defaults(self):
        mod = _teams_module()
        f = mod.TeamsFile(
            file_id="f1", name="n", display_name="dn", mime_type="text/plain",
            file_type="text", size=1, user_id="u", user_name="n", user_email="e",
            channel_id="c", workspace_id="w", tenant_id="t",
            timestamp="2026-01-01T00:00:00Z", created_at=datetime.now(timezone.utc),
        )
        assert f.tags == []
        assert f.metadata == {}

    def test_message_defaults(self):
        mod = _teams_module()
        m = mod.TeamsMessage(
            message_id="1", text="hi", user_id="u", user_name="n", user_email="e",
            channel_id="c", workspace_id="w", tenant_id="t", timestamp="x",
        )
        assert m.attachments == []
        assert m.policy_violations == []


class TestTeamsRateLimiter:
    async def test_redis_path(self):
        r = _redis_mock()
        r.get.return_value = "30"
        limiter = _teams_module().TeamsRateLimiter(r)
        assert await limiter.check_limit("w1", "messages_send") is False
        r.get.return_value = None
        assert await limiter.check_limit("w1", "messages_send") is True
        r.incr.assert_called()

    async def test_local_path(self):
        mod = _teams_module()
        limiter = mod.TeamsRateLimiter()
        key = "teams_rate:w1:messages_send"
        for _ in range(30):
            assert await limiter.check_limit("w1", "messages_send") is True
        assert await limiter.check_limit("w1", "messages_send") is False
        limiter.local_limits[key]["reset"] = 0
        assert await limiter.check_limit("w1", "messages_send") is True


class TestTeamsServiceBasics:
    def test_encrypt_decrypt(self):
        mod = _teams_module()
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        svc = mod.TeamsEnhancedService(tenant_id="default", config={"encryption_key": key})
        enc = svc._encrypt_token("secret")
        assert enc != "secret"
        assert svc._decrypt_token(enc) == "secret"
        svc2 = mod.TeamsEnhancedService(tenant_id="default", config={})
        assert svc2._decrypt_token("plain") == "plain"
        with pytest.raises(RuntimeError):
            svc2._encrypt_token("x")

    def test_msal_not_available(self):
        mod = _teams_module()
        svc = mod.TeamsEnhancedService(tenant_id="default", config={})
        assert svc.msal_app is None
        with pytest.raises(RuntimeError):
            svc.generate_oauth_url("st", "u1")
        result = asyncio.run(svc.exchange_code_for_tokens("c", "s"))
        assert result["ok"] is False

    def test_msal_available(self):
        mod = _teams_module()
        import base64
        def _b64(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
        header = _b64(json.dumps({"alg": "none"}).encode())
        payload = _b64(json.dumps({
            "tid": "ten1", "name": "Team", "upn": "u@x.com", "oid": "o1",
        }).encode())
        token = f"{header}.{payload}.{_b64(b'x')}"
        msal_app = MagicMock()
        msal_app.get_authorization_request_url.return_value = "https://login/oauth"
        msal_app.acquire_token_by_authorization_code.return_value = {"access_token": token, "refresh_token": "r"}
        svc = mod.TeamsEnhancedService(tenant_id="default", config={})
        svc.msal_app = msal_app
        url = svc.generate_oauth_url("st", "u1", scopes=["a"])
        assert url == "https://login/oauth"
        with patch.object(svc, "_save_workspace", return_value=True):
            result = asyncio.run(svc.exchange_code_for_tokens("c", "s"))
        assert result["ok"] is True
        assert result["workspace"]["team_id"] == "ten1"

    async def test_exchange_code_error_and_msal_error(self):
        mod = _teams_module()
        msal_app = MagicMock()
        msal_app.acquire_token_by_authorization_code.return_value = {"error": "invalid_grant", "error_description": "bad"}
        svc = mod.TeamsEnhancedService(tenant_id="default", config={})
        svc.msal_app = msal_app
        result = await svc.exchange_code_for_tokens("c", "s")
        assert result["ok"] is False
        msal_app.acquire_token_by_authorization_code.side_effect = RuntimeError("boom")
        result2 = await svc.exchange_code_for_tokens("c", "s")
        assert result2["ok"] is False

    def test_health_and_capabilities(self):
        mod = _teams_module()
        svc = mod.TeamsEnhancedService(tenant_id="default", config={})
        assert svc.health_check()["ok"] is False
        svc.client_id = "cid"
        svc.client_secret = "sec"
        assert svc.health_check()["ok"] is True
        caps = svc.get_capabilities()
        assert caps["supports_webhooks"] is True
        assert len(caps["operations"]) == 4

    async def test_get_service_info(self):
        mod = _teams_module()
        svc = mod.TeamsEnhancedService(tenant_id="default", config={})
        info = await svc.get_service_info()
        assert info["name"] == "Microsoft Teams Enhanced Service"


class TestTeamsWorkspaceStorage:
    def test_get_workspace_db(self):
        mod = _teams_module()
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE teams_workspaces (team_id TEXT, name TEXT, description TEXT,
            display_name TEXT, visibility TEXT, mail_nickname TEXT, created_at TEXT, created_by TEXT,
            tenant_id TEXT, scopes TEXT, settings TEXT)""")
        conn.execute("INSERT INTO teams_workspaces VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     ("t1", "n", "d", "dn", "public", "mn", "2026-01-01T00:00:00+00:00", "u", "ten", "[]", "{}"))
        svc = mod.TeamsEnhancedService(tenant_id="default", config={"database": conn})
        ws = svc._get_workspace("t1")
        assert ws.team_id == "t1"

    def test_get_workspace_redis(self):
        mod = _teams_module()
        r = _redis_mock()
        r.get.return_value = json.dumps({
            "team_id": "t1", "name": "n", "description": "d", "display_name": "dn",
            "visibility": "public", "mail_nickname": "mn", "created_at": "2026-01-01T00:00:00+00:00",
            "created_by": "u", "tenant_id": "ten", "scopes": [], "settings": {},
        })
        svc = mod.TeamsEnhancedService(tenant_id="default", config={})
        svc.redis_client = r
        ws = svc._get_workspace("t1")
        assert ws.team_id == "t1"

    def test_get_workspace_error(self):
        mod = _teams_module()
        db = MagicMock()
        db.execute.side_effect = RuntimeError("boom")
        svc = mod.TeamsEnhancedService(tenant_id="default", config={"database": db})
        assert svc._get_workspace("t1") is None

    def test_save_workspace_db_success(self):
        mod = _teams_module()
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE teams_workspaces (team_id TEXT, name TEXT, description TEXT,
            display_name TEXT, visibility TEXT, mail_nickname TEXT, created_at TEXT, created_by TEXT,
            tenant_id TEXT, internal_id TEXT, classification TEXT, specialization TEXT, web_url TEXT,
            access_token TEXT, refresh_token TEXT, scopes TEXT, last_sync TEXT, is_active INTEGER,
            settings TEXT, member_count INTEGER, channel_count INTEGER)""")
        svc = mod.TeamsEnhancedService(tenant_id="default", config={"database": conn})
        ws = mod.TeamsWorkspace(
            team_id="t1", name="n", description="d", display_name="dn",
            visibility="public", mail_nickname="mn", created_at=datetime.now(timezone.utc),
            created_by="u", tenant_id="ten",
        )
        assert svc._save_workspace(ws) is True
        assert svc.connection_status["t1"] == mod.TeamsConnectionStatus.CONNECTED

    def test_save_workspace_db_failure(self):
        mod = _teams_module()
        db = MagicMock()
        db.execute.side_effect = RuntimeError("boom")
        svc = mod.TeamsEnhancedService(tenant_id="default", config={"database": db})
        ws = mod.TeamsWorkspace(
            team_id="t1", name="n", description="d", display_name="dn",
            visibility="public", mail_nickname="mn", created_at=datetime.now(timezone.utc),
            created_by="u", tenant_id="ten",
        )
        assert svc._save_workspace(ws) is False

    def test_save_workspace_redis(self):
        mod = _teams_module()
        r = _redis_mock()
        svc = mod.TeamsEnhancedService(tenant_id="default", config={})
        svc.redis_client = r
        ws = mod.TeamsWorkspace(
            team_id="t1", name="n", description="d", display_name="dn",
            visibility="public", mail_nickname="mn", created_at=datetime.now(timezone.utc),
            created_by="u", tenant_id="ten",
        )
        assert svc._save_workspace(ws) is True
        r.setex.assert_called_once()

    async def test_get_workspaces(self):
        mod = _teams_module()
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE teams_workspaces (team_id TEXT, name TEXT, description TEXT,
            display_name TEXT, visibility TEXT, mail_nickname TEXT, created_at TEXT, created_by TEXT,
            tenant_id TEXT, scopes TEXT, settings TEXT, is_active INTEGER)""")
        conn.execute("INSERT INTO teams_workspaces VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     ("t1", "n", "d", "dn", "public", "mn", "2026-01-01T00:00:00+00:00", "u1", "ten", "[]", "{}", 1))
        svc = mod.TeamsEnhancedService(tenant_id="default", config={"database": conn})
        workspaces = await svc.get_workspaces("u1")
        assert len(workspaces) == 1
        assert workspaces[0].created_by == "u1"
        r = _redis_mock()
        r.keys.return_value = ["teams_workspace:t2"]
        r.get.return_value = json.dumps({
            "team_id": "t2", "name": "n", "description": "d", "display_name": "dn",
            "visibility": "public", "mail_nickname": "mn", "created_at": "2026-01-01T00:00:00+00:00",
            "created_by": "u2", "tenant_id": "ten", "scopes": [], "settings": {},
        })
        svc2 = mod.TeamsEnhancedService(tenant_id="default", config={})
        svc2.redis_client = r
        workspaces2 = await svc2.get_workspaces()
        assert len(workspaces2) == 1
        db = MagicMock()
        db.execute.side_effect = RuntimeError("boom")
        svc3 = mod.TeamsEnhancedService(tenant_id="default", config={"database": db})
        assert await svc3.get_workspaces() == []


class TestTeamsGraph:
    def test_get_graph_client_no_sdk(self):
        mod = _teams_module()
        svc = mod.TeamsEnhancedService(tenant_id="default", config={})
        with patch.object(svc, "_get_workspace", return_value=MagicMock(access_token="tok")):
            with patch.object(mod, "GraphServiceClient", None):
                assert svc._get_graph_client("w1") is None

    async def test_get_graph_client_errors(self):
        mod = _teams_module()
        svc = mod.TeamsEnhancedService(tenant_id="default", config={})
        with patch.object(svc, "_get_workspace", return_value=None):
            assert svc._get_graph_client("w1") is None
        with patch.object(svc, "_get_workspace", return_value=MagicMock(access_token=None)):
            assert svc._get_graph_client("w1") is None
        with patch.object(svc, "_get_workspace", side_effect=RuntimeError("boom")):
            assert svc._get_graph_client("w1") is None

    def test_get_graph_client_success(self):
        mod = _teams_module()
        svc = mod.TeamsEnhancedService(tenant_id="default", config={})
        gsc = MagicMock()
        with patch.object(svc, "_get_workspace", return_value=MagicMock(access_token="tok")), \
             patch.object(mod, "GraphServiceClient", gsc):
            client = svc._get_graph_client("w1")
        assert client is not None
        assert svc._get_graph_client("w1") is client  # cached

    async def test_test_connection(self):
        mod = _teams_module()
        svc = mod.TeamsEnhancedService(tenant_id="default", config={})
        with patch.object(svc, "_get_graph_client", return_value=None):
            result = await svc.test_connection("w1")
        assert result["connected"] is False
        client = MagicMock()
        team = MagicMock()
        team.id = "t1"
        team.display_name = "Team"
        team.visibility = "public"
        team.additional_data = {"tenantId": "ten"}
        client.teams.get = AsyncMock(return_value=MagicMock(value=[team]))
        svc2 = mod.TeamsEnhancedService(tenant_id="default", config={})
        with patch.object(svc2, "_get_graph_client", return_value=client), \
             patch.object(svc2, "_get_workspace", return_value=MagicMock(last_sync=None)), \
             patch.object(svc2, "_save_workspace", return_value=True):
            result2 = await svc2.test_connection("w1")
        assert result2["connected"] is True
        client2 = MagicMock()
        client2.teams.get = AsyncMock(return_value=MagicMock(value=[]))
        svc3 = mod.TeamsEnhancedService(tenant_id="default", config={})
        with patch.object(svc3, "_get_graph_client", return_value=client2):
            result3 = await svc3.test_connection("w1")
        assert result3["connected"] is False
        svc4 = mod.TeamsEnhancedService(tenant_id="default", config={})
        with patch.object(svc4, "_get_graph_client", side_effect=RuntimeError("boom")):
            result4 = await svc4.test_connection("w1")
        assert result4["connected"] is False


class TestTeamsChannels:
    async def _svc_with_client(self, ws="w1", ch="c1"):
        mod = _teams_module()
        svc = mod.TeamsEnhancedService(tenant_id="default", config={})
        client = MagicMock()
        svc._get_graph_client = MagicMock(return_value=client)
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        return svc, client

    async def test_get_channels_rate_limited(self):
        mod = _teams_module()
        svc = mod.TeamsEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=False)
        assert await svc.get_channels("w1") == []

    async def test_get_channels_no_client(self):
        mod = _teams_module()
        svc = mod.TeamsEnhancedService(tenant_id="default", config={})
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        svc._get_graph_client = MagicMock(return_value=None)
        assert await svc.get_channels("w1") == []

    async def test_get_channels_no_result(self):
        svc, client = await self._svc_with_client()
        client.teams["w1"].channels.get = AsyncMock(return_value=None)
        assert await svc.get_channels("w1") == []

    async def test_get_channels_success_with_filters(self):
        svc, client = await self._svc_with_client()
        ch = MagicMock()
        ch.id = "c1"
        ch.display_name = "General"
        ch.description = "desc"
        ch.membership_type = "private"
        ch.is_archived = True
        ch.email = "e"
        ch.web_url = "w"
        ch.is_favorite_by_default = False
        ch.created_datetime = "2026-01-01T00:00:00Z"
        ch.last_updated_datetime = None
        ch.is_welcome_message_enabled = True
        ch.allow_cross_team_posts = True
        ch.allow_giphy = True
        ch.giphy_content_rating = "moderate"
        ch.allow_memes = True
        ch.allow_custom_memes = True
        ch.allow_stickers_and_gifs = True
        ch.allow_user_edit_messages = True
        ch.allow_owner_delete_messages = True
        ch.allow_team_mentions = True
        ch.allow_channel_mentions = True
        ch.additional_data = {"memberCount": 4}
        client.teams["w1"].channels.get = AsyncMock(return_value=MagicMock(value=[ch]))
        r = _redis_mock()
        svc.redis_client = r
        channels = await svc.get_channels("w1", include_private=True, include_archived=True)
        assert len(channels) == 1
        assert channels[0].channel_id == "c1"
        r.setex.assert_called_once()

    async def test_get_channels_cache_fallback(self):
        svc, client = await self._svc_with_client()
        r = _redis_mock()
        r.get.return_value = json.dumps([{
            "channel_id": "c1", "name": "General", "display_name": "General",
            "description": "", "workspace_id": "w1", "channel_type": "standard",
            "created_at": "2026-01-01T00:00:00+00:00",
        }])
        svc.redis_client = r
        client.teams["w1"].channels.get = AsyncMock(side_effect=RuntimeError("boom"))
        channels = await svc.get_channels("w1")
        assert len(channels) == 1

    async def test_send_message_paths(self):
        mod = _teams_module()
        svc, client = await self._svc_with_client()
        svc.rate_limiter.check_limit = AsyncMock(return_value=False)
        result = await svc.send_message("w1", "c1", "hi")
        assert result["ok"] is False
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        svc._get_graph_client = MagicMock(return_value=None)
        result = await svc.send_message("w1", "c1", "hi")
        assert result["ok"] is False

    async def test_send_message_thread_success(self):
        mod = _teams_module()
        svc, client = await self._svc_with_client()
        reply = MagicMock()
        reply.id = "m1"
        reply.created_datetime = "2026-01-01T00:00:00Z"
        client.teams["w1"].channels["c1"].messages["t1"].replies.post = AsyncMock(return_value=reply)
        result = await svc.send_message("w1", "c1", "<div>hi</div>", thread_id="t1", importance="high", subject="s", attachments=[{}])
        assert result["ok"] is True
        assert result["message_id"] == "m1"

    async def test_send_message_no_result_and_error(self):
        mod = _teams_module()
        svc, client = await self._svc_with_client()
        client.teams["w1"].channels["c1"].messages.post = AsyncMock(return_value=None)
        result = await svc.send_message("w1", "c1", "hi")
        assert result["ok"] is False
        client.teams["w1"].channels["c1"].messages.post = AsyncMock(side_effect=RuntimeError("boom"))
        result2 = await svc.send_message("w1", "c1", "hi")
        assert result2["ok"] is False

    async def test_get_channel_messages_error_paths(self):
        mod = _teams_module()
        svc, client = await self._svc_with_client()
        svc.rate_limiter.check_limit = AsyncMock(return_value=False)
        assert await svc.get_channel_messages("w1", "c1") == []
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        svc._get_graph_client = MagicMock(return_value=None)
        assert await svc.get_channel_messages("w1", "c1") == []
        svc._get_graph_client = MagicMock(return_value=client)
        client.teams["w1"].channels["c1"].messages.get = AsyncMock(return_value=None)
        assert await svc.get_channel_messages("w1", "c1") == []

    async def test_search_messages_error_paths_and_kql(self):
        mod = _teams_module()
        svc, client = await self._svc_with_client()
        svc.rate_limiter.check_limit = AsyncMock(return_value=False)
        result = await svc.search_messages("w1", "q")
        assert result["ok"] is False
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        svc._get_graph_client = MagicMock(return_value=None)
        result = await svc.search_messages("w1", "q")
        assert result["ok"] is False

    async def test_upload_file_paths(self):
        mod = _teams_module()
        import os as _os
        svc, client = await self._svc_with_client()
        svc.rate_limiter.check_limit = AsyncMock(return_value=False)
        result = await svc.upload_file("w1", "c1", "/tmp/x")
        assert result["ok"] is False
        svc.rate_limiter.check_limit = AsyncMock(return_value=True)
        svc._get_graph_client = MagicMock(return_value=None)
        result = await svc.upload_file("w1", "c1", "/tmp/x")
        assert result["ok"] is False

    async def test_upload_file_success(self, tmp_path):
        mod = _teams_module()
        f = tmp_path / "file.txt"
        f.write_text("hello")
        svc, client = await self._svc_with_client()
        ch_info = MagicMock()
        ch_info.additional_data = {"siteId": "site1"}
        client.teams["w1"].channels["c1"].get = AsyncMock(return_value=ch_info)
        resp = MagicMock()
        resp.status_code = 201
        resp.json.return_value = {
            "id": "f1", "name": "file.txt",
            "file": {"mimeType": "text/plain"},
            "size": 5, "createdDateTime": "2026-01-01T00:00:00Z",
            "webUrl": "https://sharepoint/x",
        }
        svc.send_message = AsyncMock(return_value={"ok": True})
        async def fake_put(url, headers=None, content=None):
            return resp
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__ = AsyncMock(return_value=MagicMock(put=AsyncMock(side_effect=fake_put)))
            ac.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await svc.upload_file("w1", "c1", str(f), title="t", description="d")
        assert result["ok"] is True
        assert result["file"]["name"] == "file.txt"
        svc.send_message.assert_awaited_once()

    async def test_upload_file_team_site_and_error(self, tmp_path):
        mod = _teams_module()
        f = tmp_path / "file2.txt"
        f.write_text("hello")
        svc, client = await self._svc_with_client()
        ch_info = MagicMock()
        ch_info.additional_data = {}
        team_info = MagicMock()
        team_info.additional_data = {"siteId": "site2"}
        client.teams["w1"].channels["c1"].get = AsyncMock(return_value=ch_info)
        client.teams["w1"].get = AsyncMock(return_value=team_info)
        resp = MagicMock()
        resp.status_code = 500
        async def fake_put(url, headers=None, content=None):
            return resp
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__ = AsyncMock(return_value=MagicMock(put=AsyncMock(side_effect=fake_put)))
            ac.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await svc.upload_file("w1", "c1", str(f))
        assert result["ok"] is False

    async def test_upload_file_error(self):
        mod = _teams_module()
        svc, client = await self._svc_with_client()
        client.teams["w1"].channels["c1"].get = AsyncMock(side_effect=RuntimeError("boom"))
        result = await svc.upload_file("w1", "c1", "/tmp/nope")
        assert result["ok"] is False


class TestTeamsSyncAndOps:
    async def test_sync_to_postgres_cache_success(self):
        mod = _teams_module()
        svc = mod.TeamsEnhancedService(tenant_id="default", config={})
        ch = mod.TeamsChannel(
            channel_id="c1", name="n", display_name="dn", description="d",
            workspace_id="w1", channel_type="standard", message_count=5,
        )
        svc.get_channels = AsyncMock(return_value=[ch])
        svc._get_workspace = MagicMock(return_value=MagicMock(member_count=10))
        db = MagicMock()
        with patch("core.database.SessionLocal", return_value=db):
            result = await svc.sync_to_postgres_cache("w1")
        assert result["success"] is True
        assert result["metrics_synced"] == 3

    async def test_sync_to_postgres_cache_db_error(self):
        mod = _teams_module()
        svc = mod.TeamsEnhancedService(tenant_id="default", config={})
        svc.get_channels = AsyncMock(return_value=[])
        svc._get_workspace = MagicMock(return_value=None)
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.side_effect = RuntimeError("db")
        with patch("core.database.SessionLocal", return_value=db):
            result = await svc.sync_to_postgres_cache("w1")
        assert result["success"] is False

    async def test_full_sync(self):
        mod = _teams_module()
        svc = mod.TeamsEnhancedService(tenant_id="default", config={})
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True})
        result = await svc.full_sync("w1")
        assert result["success"] is True
        assert result["workspace_id"] == "w1"

    async def test_execute_operation(self):
        mod = _teams_module()
        svc = mod.TeamsEnhancedService(tenant_id="default", config={})
        result = await svc.execute_operation("send_message", {}, {"tenant_id": "other"})
        assert result["success"] is False
        assert result["error"] == "Tenant mismatch"
        svc.send_message = AsyncMock(return_value={"ok": True})
        result2 = await svc.execute_operation(
            "send_message", {"workspace_id": "w1", "channel_id": "c1", "text": "hi"},
            {"tenant_id": "default"},
        )
        assert result2["success"] is True
        svc.get_channel_messages = AsyncMock(return_value=[mod.TeamsMessage(
            message_id="1", text="t", user_id="u", user_name="n", user_email="e",
            channel_id="c", workspace_id="w", tenant_id="t", timestamp="x")])
        result3 = await svc.execute_operation(
            "get_channel_messages", {"workspace_id": "w1", "channel_id": "c1"},
            {"tenant_id": "default"},
        )
        assert result3["success"] is True
        svc.get_channels = AsyncMock(return_value=[])
        result4 = await svc.execute_operation(
            "list_channels", {"workspace_id": "w1"}, {"tenant_id": "default"},
        )
        assert result4["success"] is True
        svc.search_messages = AsyncMock(return_value={"ok": True})
        result5 = await svc.execute_operation(
            "search_messages", {"workspace_id": "w1", "query": "q"}, {"tenant_id": "default"},
        )
        assert result5["success"] is True
        result6 = await svc.execute_operation("nope", {}, {"tenant_id": "default"})
        assert result6["success"] is False
        svc.send_message = AsyncMock(side_effect=RuntimeError("boom"))
        result7 = await svc.execute_operation(
            "send_message", {"workspace_id": "w1", "channel_id": "c1", "text": "hi"},
            {"tenant_id": "default"},
        )
        assert result7["success"] is False

    async def test_close(self):
        mod = _teams_module()
        svc = mod.TeamsEnhancedService(tenant_id="default", config={})
        r = _redis_mock()
        svc.redis_client = r
        await svc.close()
        r.close.assert_called_once()


# ============================================================================
# chat_orchestrator
# ============================================================================

def make_orchestrator(**kwargs):
    orch = co.ChatOrchestrator()
    orch.ai_engines = {}
    orch.session_manager = None
    orch.conversation_sessions = {}
    orch.llm_service = None
    for k, v in kwargs.items():
        setattr(orch, k, v)
    return orch


class TestOrchestratorInit:
    def test_init_no_llm(self):
        with patch.object(co, "LLM_SERVICE_AVAILABLE", False):
            orch = co.ChatOrchestrator()
        assert orch.llm_service is None

    def test_init_session_manager_missing(self):
        with patch.dict("sys.modules", {"core.chat_session_manager": None}):
            with patch("core.chat_session_manager.get_chat_session_manager", side_effect=ImportError):
                orch = make_orchestrator()
        assert orch.session_manager is None

    def test_ai_engines_import_error(self):
        with patch("builtins.__import__", side_effect=ImportError("no nlp")), \
             patch.object(co, "LLM_SERVICE_AVAILABLE", False):
            orch = co.ChatOrchestrator()
        assert orch.ai_engines == {}


class TestOrchestratorSessions:
    def test_get_user_sessions_no_manager(self):
        orch = make_orchestrator()
        orch.conversation_sessions = {
            "s1": {"user_id": "u1", "history": []},
            "s2": {"user_id": "u2", "history": []},
        }
        result = orch.get_user_sessions("u1")
        assert list(result.keys()) == ["s1"]

    def test_get_user_sessions_manager(self):
        orch = make_orchestrator()
        manager = MagicMock()
        manager.list_user_sessions.return_value = [
            {"session_id": "s1", "user_id": "u1", "title": "t", "created_at": "x",
             "last_active": "y", "history": [], "metadata": {}},
        ]
        orch.session_manager = manager
        result = orch.get_user_sessions("u1")
        assert result["s1"]["title"] == "t"
        assert "s1" in orch.conversation_sessions

    def test_load_persisted_sessions(self):
        orch = make_orchestrator()
        manager = MagicMock()
        manager._load_sessions_file.return_value = [
            {"session_id": "s1", "user_id": "u1", "created_at": "x", "last_active": "y", "history": []},
        ]
        orch.session_manager = manager
        orch._load_persisted_sessions()
        assert "s1" in orch.conversation_sessions
        manager._load_sessions_file.side_effect = RuntimeError("boom")
        orch._load_persisted_sessions()

    async def test_emit_agent_step(self):
        orch = make_orchestrator()
        with patch("core.websockets.get_connection_manager") as gm:
            manager = MagicMock()
            manager.broadcast_event = AsyncMock()
            gm.return_value = manager
            await orch._emit_agent_step(1, "t", "a", "o")
            manager.broadcast_event.assert_awaited_once()
            manager.broadcast_event = AsyncMock(side_effect=RuntimeError("boom"))
            await orch._emit_agent_step(1, "t", "a", "o")

    def test_create_platform_connectors(self):
        orch = make_orchestrator()
        assert len(orch.platform_connectors) == len(co.PlatformType)

    def test_get_or_create_session_idor(self):
        orch = make_orchestrator()
        orch.conversation_sessions["s1"] = {
            "id": "s1", "user_id": "u1", "channel_id": None, "thread_id": None,
            "created_at": "x", "history": [],
        }
        session = orch._get_or_create_session("u2", "s1")
        assert session["id"] != "s1"
        assert session["user_id"] == "u2"

    def test_get_or_create_session_new_with_persist_failure(self):
        orch = make_orchestrator()
        manager = MagicMock()
        manager.create_session.side_effect = RuntimeError("boom")
        orch.session_manager = manager
        session = orch._get_or_create_session("u1", "s1", {"channel_id": "ch1", "thread_id": "th1"})
        assert session["id"] == "s1"
        assert session["channel_id"] == "ch1"

    def test_get_or_create_session_existing_same_user(self):
        orch = make_orchestrator()
        orch.conversation_sessions["s1"] = {"id": "s1", "user_id": "u1"}
        assert orch._get_or_create_session("u1", "s1")["id"] == "s1"

    def test_update_session_persist(self):
        orch = make_orchestrator()
        session = {"id": "s1", "user_id": "u1", "channel_id": "ch1", "history": []}
        with patch("core.database.get_db_session") as gdb:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=MagicMock())
            ctx.__exit__ = MagicMock(return_value=False)
            gdb.return_value = ctx
            with patch("core.llm.compression.SESSION_DEDUP_ENABLED", True, create=True):
                orch._update_session(session, "hi", {"message": "hello"}, {"x": 1})
        assert len(session["history"]) == 1
        gdb.assert_called()

    def test_update_session_persist_failure(self):
        orch = make_orchestrator()
        session = {"id": "s1", "user_id": "u1", "history": []}
        with patch("core.database.get_db_session", side_effect=RuntimeError("boom")):
            orch._update_session(session, "hi", {"message": "hello"}, {"x": 1})
        assert len(session["history"]) == 1

    def test_generate_error_response(self):
        orch = make_orchestrator()
        resp = orch._generate_error_response("err", "s1")
        assert resp["success"] is False
        assert resp["session_id"] == "s1"

    def test_cancellation(self):
        orch = make_orchestrator()
        assert orch._is_cancelled("s1") is False
        orch.request_cancellation("s1")
        assert orch._is_cancelled("s1") is True
        assert orch._is_cancelled("s1") is False


class TestOrchestratorIntent:
    def test_fallback_intent_all_branches(self):
        orch = make_orchestrator()
        cases = [
            ("find the report", co.ChatIntent.SEARCH_REQUEST),
            ("send an email", co.ChatIntent.MESSAGE_SEND),
            ("create a task", co.ChatIntent.TASK_MANAGEMENT),
            ("automate workflow", co.ChatIntent.WORKFLOW_CREATION),
            ("schedule meeting", co.ChatIntent.SCHEDULING),
            ("what are my priorities", co.ChatIntent.BUSINESS_HEALTH),
            ("simulate what if i hire", co.ChatIntent.BUSINESS_HEALTH),
            ("pipeline deal forecast", co.ChatIntent.CRM),
            ("hello world", co.ChatIntent.SEARCH_REQUEST),
        ]
        for msg, expected in cases:
            result = orch._fallback_intent_analysis(msg)
            assert result["primary_intent"] == expected, msg
        assert orch._fallback_intent_analysis("x")["confidence"] == 0.6

    def test_classify_intent(self):
        orch = make_orchestrator()
        nlp = MagicMock()
        from ai.nlp_engine import CommandType
        for ct, expected in [
            (CommandType.SEARCH, co.ChatIntent.SEARCH_REQUEST),
            (CommandType.CREATE, co.ChatIntent.TASK_MANAGEMENT),
            (CommandType.SCHEDULE, co.ChatIntent.SCHEDULING),
            (CommandType.ANALYZE, co.ChatIntent.DATA_ANALYSIS),
            (CommandType.BUSINESS_HEALTH, co.ChatIntent.BUSINESS_HEALTH),
            (CommandType.TRIGGER, co.ChatIntent.AUTOMATION_TRIGGER),
            (CommandType.WORKFLOW_CREATION, co.ChatIntent.WORKFLOW_CREATION),
            ("UNKNOWN", co.ChatIntent.SEARCH_REQUEST),
        ]:
            nlp.command_type = ct
            assert orch._classify_intent(nlp) == expected

    async def test_analyze_intent_nlp_and_fallback(self):
        orch = make_orchestrator()
        nlp_engine = MagicMock()
        nlp_result = MagicMock()
        nlp_result.command_type = "SEARCH"
        nlp_result.confidence = 0.9
        nlp_result.entities = []
        nlp_result.platforms = []
        nlp_result.command_type = MagicMock()
        nlp_engine.parse_command = AsyncMock(return_value=nlp_result)
        orch.ai_engines = {"nlp": nlp_engine}
        result = await orch._analyze_intent("find x", {})
        assert result["confidence"] == 0.9
        nlp_engine.parse_command = AsyncMock(side_effect=RuntimeError("boom"))
        result2 = await orch._analyze_intent("find x", {})
        assert result2["confidence"] == 0.6


class TestOrchestratorQwen:
    async def test_get_qwen_response_no_llm(self):
        orch = make_orchestrator()
        assert await orch._get_qwen_response("hi", []) is None

    async def test_get_qwen_response_success(self):
        orch = make_orchestrator()
        llm = MagicMock()
        llm.generate_completion = AsyncMock(return_value={
            "success": True, "content": "hello", "model": "m", "provider": "p",
        })
        orch.llm_service = llm
        result = await orch._get_qwen_response(
            "hi", [{"message": "m1", "response": {"message": "r1"}}],
            {"model": "gpt-4", "tier": "quality", "intent": "chat"},
            sticky_hint=("p", "m"),
        )
        assert result["content"] == "hello"
        llm.generate_completion.assert_called_once()
        kwargs = llm.generate_completion.call_args[1]
        assert kwargs["model"] == "gpt-4"
        assert kwargs["cognitive_tier"] == "quality"
        assert kwargs["intent_override"] == "chat"
        assert kwargs["sticky_hint"] == ("p", "m")

    async def test_get_qwen_response_failure(self):
        orch = make_orchestrator()
        llm = MagicMock()
        llm.generate_completion = AsyncMock(return_value={"success": False})
        orch.llm_service = llm
        assert await orch._get_qwen_response("hi", []) is None
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("boom"))
        assert await orch._get_qwen_response("hi", []) is None


class TestOrchestratorProcessMessage:
    async def _orch(self):
        orch = make_orchestrator()
        orch._get_qwen_response = AsyncMock(return_value={
            "content": "ai answer", "model": "m", "provider": "p",
        })
        orch._analyze_intent = AsyncMock(return_value={
            "primary_intent": co.ChatIntent.SEARCH_REQUEST, "confidence": 0.9,
        })
        orch._route_to_features = AsyncMock(return_value={})
        return orch

    async def test_process_chat_message_success(self):
        orch = await self._orch()
        result = await orch.process_chat_message("u1", "hi", "s1")
        assert result["success"] is True
        assert result["message"] == "ai answer"
        assert result["model"] == "m"
        assert result["session_id"] == "s1"

    async def test_process_chat_message_template(self):
        orch = await self._orch()
        orch._get_qwen_response = AsyncMock(return_value=None)
        orch._generate_main_message = MagicMock(return_value="template msg")
        result = await orch.process_chat_message("u1", "hi", "s1")
        assert result["model"] == "template"
        assert result["message"] == "template msg"

    async def test_process_chat_message_budget_failure(self):
        orch = await self._orch()
        orch._route_to_features = AsyncMock(return_value={
            co.FeatureType.AGENT: {
                "error_code": "budget_exceeded", "message": "out of budget",
                "failure_reason": "limit",
            },
        })
        result = await orch.process_chat_message("u1", "hi", "s1")
        assert result["success"] is False
        assert result["error_code"] == "budget_exceeded"
        assert result["message"] == "out of budget"

    async def test_process_chat_message_cancelled(self):
        orch = await self._orch()
        orch.request_cancellation("s1")
        result = await orch.process_chat_message("u1", "hi", "s1")
        assert result["cancelled"] is True

    async def test_process_chat_message_error(self):
        orch = make_orchestrator()
        orch._get_qwen_response = AsyncMock(side_effect=RuntimeError("boom"))
        with patch.object(orch, "_update_session"):
            result = await orch.process_chat_message("u1", "hi", "s1")
        assert result["success"] is False


class TestOrchestratorRouting:
    async def test_route_to_features_all_intents(self):
        orch = make_orchestrator()
        orch.feature_handlers = {
            co.FeatureType.SEARCH: AsyncMock(return_value={"success": True, "data": {"r": 1}}),
            co.FeatureType.AI_ANALYTICS: AsyncMock(return_value=None),
            co.FeatureType.AGENT: AsyncMock(return_value={"success": True, "message": "done"}),
        }
        for intent in (co.ChatIntent.SEARCH_REQUEST, co.ChatIntent.MESSAGE_SEND,
                       co.ChatIntent.TASK_MANAGEMENT, co.ChatIntent.WORKFLOW_CREATION,
                       co.ChatIntent.SCHEDULING, co.ChatIntent.DATA_ANALYSIS,
                       co.ChatIntent.AUTOMATION_TRIGGER, co.ChatIntent.INTEGRATION_SETUP,
                       co.ChatIntent.STATUS_CHECK, co.ChatIntent.HELP_REQUEST,
                       co.ChatIntent.BUSINESS_HEALTH, co.ChatIntent.CRM,
                       co.ChatIntent.AGENT_REQUEST, co.ChatIntent.MULTI_STEP_PROCESS):
            result = await orch._route_to_features("m", {"primary_intent": intent}, {}, None)
            assert isinstance(result, dict)

    async def test_route_to_features_agent_fallback(self):
        orch = make_orchestrator()
        orch.feature_handlers = {}
        agent_service = MagicMock()
        agent_service.execute_task = AsyncMock(return_value={"id": "t1", "status": "running"})
        with patch.object(co, "agent_service", agent_service):
            result = await orch._route_to_features(
                "do something", {"primary_intent": co.ChatIntent.SEARCH_REQUEST}, {"workspace_id": "w1"}, None
            )
        assert co.FeatureType.AGENT in result
        agent_service.execute_task = AsyncMock(side_effect=RuntimeError("boom"))
        with patch.object(co, "agent_service", agent_service):
            result2 = await orch._route_to_features(
                "create task", {"primary_intent": co.ChatIntent.TASK_MANAGEMENT}, {}, None
            )
        assert co.FeatureType.AGENT not in result2

    def test_generate_coordinated_response(self):
        orch = make_orchestrator()
        orch._generate_main_message = MagicMock(return_value="msg")
        result = orch._generate_coordinated_response(
            "m",
            {"primary_intent": co.ChatIntent.SEARCH_REQUEST, "confidence": 0.9},
            {co.FeatureType.SEARCH: {"data": {"x": 1}, "suggested_actions": ["a"], "ui_updates": ["u"], "requires_confirmation": True}},
            {"id": "s1"},
        )
        assert result["success"] is True
        assert result["requires_confirmation"] is True

    def test_generate_main_message_all_branches(self):
        orch = make_orchestrator()
        agent_resp = {co.FeatureType.AGENT: {"success": True, "message": "agent msg"}}
        assert orch._generate_main_message("m", {"primary_intent": co.ChatIntent.AGENT_REQUEST}, agent_resp) == "agent msg"
        search = {co.FeatureType.SEARCH: {"data": {"results": [1, 2]}}}
        assert "2 results" in orch._generate_main_message("m", {"primary_intent": co.ChatIntent.SEARCH_REQUEST}, search)
        assert "searched" in orch._generate_main_message("m", {"primary_intent": co.ChatIntent.SEARCH_REQUEST}, {})
        comm = {co.FeatureType.COMMUNICATION: {"success": True}}
        assert "Message sent" in orch._generate_main_message("m", {"primary_intent": co.ChatIntent.MESSAGE_SEND}, comm)
        assert "help you send" in orch._generate_main_message("m", {"primary_intent": co.ChatIntent.MESSAGE_SEND}, {})
        tasks = {co.FeatureType.TASKS: {"success": True, "data": {"message": "task msg"}}}
        assert "task msg" in orch._generate_main_message("m", {"primary_intent": co.ChatIntent.TASK_MANAGEMENT}, tasks)
        assert "manage those tasks" in orch._generate_main_message("m", {"primary_intent": co.ChatIntent.TASK_MANAGEMENT}, {})
        wf = {co.FeatureType.WORKFLOWS: {"data": {"workflow_id": "wf1"}}}
        assert "Workflow created" in orch._generate_main_message("m", {"primary_intent": co.ChatIntent.WORKFLOW_CREATION}, wf)
        assert "automation workflow" in orch._generate_main_message("m", {"primary_intent": co.ChatIntent.WORKFLOW_CREATION}, {})
        sched = {co.FeatureType.SCHEDULING: {"data": {"ok": True}}}
        assert "Schedule updated" in orch._generate_main_message("m", {"primary_intent": co.ChatIntent.SCHEDULING}, sched)
        assert "scheduling" in orch._generate_main_message("m", {"primary_intent": co.ChatIntent.SCHEDULING}, {})
        crm = {co.FeatureType.CRM: {"success": True, "data": {"answer": "crm ans"}}}
        assert "crm ans" in orch._generate_main_message("m", {"primary_intent": co.ChatIntent.CRM}, crm)
        assert "CRM request" in orch._generate_main_message("m", {"primary_intent": co.ChatIntent.CRM}, {})
        bh = {co.FeatureType.BUSINESS_HEALTH: {"success": True, "message": "bh msg"}}
        assert "bh msg" in orch._generate_main_message("m", {"primary_intent": co.ChatIntent.BUSINESS_HEALTH}, bh)
        assert "business health" in orch._generate_main_message("m", {"primary_intent": co.ChatIntent.BUSINESS_HEALTH}, {})
        assert "all connected platforms" in orch._generate_main_message("m", {"primary_intent": co.ChatIntent.AGENT_REQUEST}, {})

    def test_generate_next_steps(self):
        orch = make_orchestrator()
        for intent in (co.ChatIntent.SEARCH_REQUEST, co.ChatIntent.WORKFLOW_CREATION,
                       co.ChatIntent.TASK_MANAGEMENT, co.ChatIntent.CRM, co.ChatIntent.MESSAGE_SEND):
            steps = orch._generate_next_steps({"primary_intent": intent}, {})
            assert len(steps) == 3


class TestOrchestratorHandlers:
    async def test_search_handler(self):
        orch = make_orchestrator()
        di = MagicMock()
        di.search_unified_entities.return_value = [{"id": 1}]
        orch.ai_engines = {"data_intelligence": di}
        result = await orch._handle_search_request("find x", {"platforms": ["slack"]}, {}, None)
        assert result["success"] is True
        assert result["data"]["results"] == [{"id": 1}]
        orch.ai_engines = {}
        result2 = await orch._handle_search_request("find x", {}, {}, None)
        assert result2["success"] is True
        di.search_unified_entities.side_effect = RuntimeError("boom")
        orch.ai_engines = {"data_intelligence": di}
        result3 = await orch._handle_search_request("find x", {}, {}, None)
        assert result3["success"] is False

    async def test_communication_handler(self):
        orch = make_orchestrator()
        result = await orch._handle_communication_request("msg", {}, {}, None)
        assert result["success"] is True

    async def test_task_handler(self):
        orch = make_orchestrator()
        di = MagicMock()
        di.extract_task_details.return_value = {"title": "T", "description": "D"}
        orch.ai_engines = {"data_intelligence": di}
        result = await orch._handle_task_request("please create a task: buy milk", {}, {}, None)
        assert result["success"] is True
        orch.ai_engines = {}
        result2 = await orch._handle_task_request("create task: buy milk", {}, {}, None)
        assert result2["success"] is True
        with patch("core.unified_task_endpoints.create_task", side_effect=RuntimeError("boom")):
            result3 = await orch._handle_task_request("create a task to buy milk", {}, {}, None)
        assert result3["success"] is False

    async def test_workflow_handler(self):
        orch = make_orchestrator()
        with patch.object(co, "load_workflows", return_value=[
            {"name": "Daily Report", "workflow_id": "wf1"},
        ]):
            result = await orch._handle_workflow_request("list workflows", {}, {}, None)
            assert result["success"] is True
            assert "Daily Report" in result["message"]
            result2 = await orch._handle_workflow_request("run daily", {}, {}, None)
            engine = MagicMock()
            engine.execute_workflow_definition = AsyncMock()
            with patch("ai.automation_engine.AutomationEngine", return_value=engine):
                result2 = await orch._handle_workflow_request("run daily report", {}, {}, None)
            assert result2["success"] is True
            result3 = await orch._handle_workflow_request("run missing", {}, {}, None)
            assert result3["success"] is False
            result4 = await orch._handle_workflow_request("hello there", {}, {}, None)
            assert result4["success"] is True
        with patch.object(co, "load_workflows", return_value=[]):
            result5 = await orch._handle_workflow_request("list workflows", {}, {}, None)
            assert result5["success"] is True

    async def test_scheduling_and_stub_handlers(self):
        orch = make_orchestrator()
        result = await orch._handle_scheduling_request("schedule the report", {}, {}, None)
        assert result["success"] is True
        result2 = await orch._handle_scheduling_request("whatever", {}, {}, None)
        assert result2["success"] is True
        for handler in (orch._handle_integration_request, orch._handle_ai_analytics_request,
                        orch._handle_document_request, orch._handle_social_media_request,
                        orch._handle_hr_request, orch._handle_ecommerce_request):
            result = await handler("m", {}, {}, None)
            assert result["success"] is True

    async def test_automation_handler(self):
        orch = make_orchestrator()
        with patch.object(co, "execute_agent_task", None):
            result = await orch._handle_automation_request("run payroll", {}, {"id": "s1"}, None)
            assert result["success"] is False  # agent execution unavailable
        with patch.object(co, "execute_agent_task", new=AsyncMock()) as eat:
            result = await orch._handle_automation_request("run payroll", {}, {"id": "s1"}, None)
            assert result["success"] is True
            assert result["data"]["agent_id"] == "payroll_guardian"
            result2 = await orch._handle_automation_request("check competitor prices", {}, {"id": "s1"}, None)
            assert result2["data"]["agent_id"] == "competitive_intel"
            result3 = await orch._handle_automation_request("inventory check", {}, {"id": "s1"}, None)
            assert result3["data"]["agent_id"] == "inventory_reconcile"
            eat.side_effect = RuntimeError("boom")
            result4 = await orch._handle_automation_request("run payroll", {}, {"id": "s1"}, None)
            assert result4["success"] is False

    async def test_automation_handler_disabled(self):
        orch = make_orchestrator()
        with patch.object(co, "execute_agent_task", None):
            result = await orch._handle_automation_request("run payroll", {}, {"id": "s1"}, None)
            assert result["success"] is False

    async def test_business_health_handler(self):
        orch = make_orchestrator()
        service = MagicMock()
        service.simulate_decision = AsyncMock(return_value={
            "prediction": "p", "roi": "10%", "breakeven": "2mo",
        })
        service.get_daily_priorities = AsyncMock(return_value={
            "priorities": [{"priority": "P1", "title": "t", "description": "d"}],
            "owner_advice": "advice",
        })
        with patch("core.business_health_service.business_health_service", service):
            result = await orch._handle_business_health_request("simulate hiring impact", {}, {}, {"workspace_id": "w1"})
            assert result["success"] is True
            assert "ROI" in result["message"]
            result2 = await orch._handle_business_health_request("what should i do today", {}, {}, {"workspace_id": "w1"})
            assert result2["success"] is True
            assert "Top Priorities" in result2["message"]
            service.get_daily_priorities = AsyncMock(return_value={"priorities": [], "owner_advice": ""})
            result3 = await orch._handle_business_health_request("what should i do today", {}, {}, {"workspace_id": "w1"})
            assert result3["success"] is True
            service.simulate_decision = AsyncMock(side_effect=RuntimeError("boom"))
            result4 = await orch._handle_business_health_request("simulate hiring", {}, {}, {"workspace_id": "w1"})
            assert result4["success"] is False

    async def test_crm_handler(self):
        orch = make_orchestrator()
        settings = MagicMock()
        settings.is_sales_enabled.return_value = True
        db = MagicMock()
        db.close = MagicMock()
        with patch.object(co, "get_automation_settings", return_value=settings), \
             patch.object(co, "SessionLocal", return_value=db), \
             patch("sales.assistant.SalesAssistant") as sa:
            sa.return_value.answer_sales_query = AsyncMock(return_value="sales answer")
            result = await orch._handle_crm_request("pipeline", {}, {}, {"workspace_id": "w1"})
        assert result["success"] is True
        settings.is_sales_enabled.return_value = False
        with patch.object(co, "get_automation_settings", return_value=settings):
            result2 = await orch._handle_crm_request("pipeline", {}, {}, {"workspace_id": "w1"})
        assert result2["success"] is False
        settings.is_sales_enabled.return_value = True
        with patch.object(co, "get_automation_settings", return_value=settings), \
             patch.object(co, "SessionLocal", return_value=db), \
             patch("sales.assistant.SalesAssistant", side_effect=RuntimeError("boom")):
            result3 = await orch._handle_crm_request("pipeline", {}, {}, {"workspace_id": "w1"})
        assert result3["success"] is False

    async def test_agent_handler(self):
        orch = make_orchestrator()
        atom = MagicMock()
        atom.execute = AsyncMock(return_value={
            "final_output": "done", "actions_executed": ["a"], "spawned_agent": "x",
        })
        with patch("core.atom_meta_agent.get_atom_agent", return_value=atom):
            result = await orch._handle_agent_request("complex", {}, {"id": "s1", "user_id": "u1"}, None)
        assert result["success"] is True
        assert result["status"] == "success"
        atom.execute = AsyncMock(return_value={
            "final_output": "halted", "failure_reason": "budget",
        })
        with patch("core.atom_meta_agent.get_atom_agent", return_value=atom):
            result2 = await orch._handle_agent_request("complex", {}, {"id": "s1"}, None)
        assert result2["status"] == "budget_exceeded"
        with patch("core.atom_meta_agent.get_atom_agent", side_effect=RuntimeError("boom")):
            result3 = await orch._handle_agent_request("complex", {}, {"id": "s1"}, None)
        assert result3["status"] == "error"
