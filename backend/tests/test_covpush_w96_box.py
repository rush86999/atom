"""Coverage wave 96 — integrations/box_service.py (TDD, 0% baseline).

Pure service module (the box_router in this module has no routes; the
service is consumed via IntegrationRegistry / execute_operation). All
HTTP/DB deps mocked; no network.

Covers: constructor config handling, capabilities, health_check (happy +
clock-failure branch), every operation via execute_operation (success /
failure-mapping / unknown op / exception), each _execute_* wrapper, all
five CRUD methods happy+error paths, authenticate (success + failure),
sync_to_postgres_cache (insert new / update existing / rollback on DB
error / outer error / close-always) and full_sync.
"""
from datetime import datetime
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import os

import pytest

from integrations.box_service import BoxService, box_service


@pytest.fixture
def service():
    return BoxService(tenant_id="t96", config={"access_token": "tok96"})


# ── Constructor / capabilities ───────────────────────────────────────────────
class TestInitCapabilities:
    def test_default_config(self):
        s = BoxService()
        assert s.service_name == "box"
        assert s.base_url == "https://api.box.com/2.0"
        assert s.required_scopes == [
            "root_readonly", "manage_app_users", "manage_webhook"]
        assert s.config == {}

    def test_config_passthrough(self):
        s = BoxService(tenant_id="t1", config={"access_token": "at", "x": 1})
        assert s.tenant_id == "t1"
        assert s.access_token == "at"

    def test_capabilities(self, service):
        caps = service.get_capabilities()
        assert caps["operations"][0]["id"] == "list_files"
        assert "full_sync" in [o["id"] for o in caps["operations"]]
        assert caps["required_params"] == ["access_token"]
        assert caps["supports_webhooks"] is True


# ── Health ───────────────────────────────────────────────────────────────────
class TestHealthCheck:
    async def test_healthy(self, service):
        result = await service.health_check()
        assert result["healthy"] is True
        assert result["status"] == "healthy"
        assert result["service"] == "box"

    async def test_clock_failure_unhealthy(self, service):
        calls = {"n": 0}

        class _BrokenClock(datetime):
            @classmethod
            def now(cls, *a, **k):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise RuntimeError("clock broken")
                return super().now(*a, **k)

        with patch("integrations.box_service.datetime", _BrokenClock):
            result = await service.health_check()
        assert result["healthy"] is False
        assert "clock broken" in result["message"]


# ── execute_operation dispatch ───────────────────────────────────────────────
class TestExecuteOperation:
    async def test_unknown_operation(self, service):
        result = await service.execute_operation("nope", {})
        assert result["success"] is False
        assert "Unknown operation" in result["error"]

    async def test_success_maps_data(self, service):
        with patch.object(service, "list_files",
                          new=AsyncMock(return_value={
                              "status": "success", "data": {"entries": []}})):
            result = await service.execute_operation(
                "list_files", {"access_token": "at"})
        assert result == {"success": True, "result": {"entries": []}}

    async def test_failure_maps_message(self, service):
        with patch.object(service, "search_files",
                          new=AsyncMock(return_value={
                              "status": "error",
                              "message": "Search failed: boom"})):
            result = await service.execute_operation(
                "search_files", {"access_token": "at", "query": "q"})
        assert result["success"] is False
        assert result["error"] == "Search failed: boom"

    async def test_exception_caught(self, service):
        with patch.object(service, "get_file_metadata",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await service.execute_operation(
                "get_file_metadata", {"access_token": "at", "file_id": "f"})
        assert result["success"] is False
        assert result["error"] == "boom"
        assert result["details"] == {"operation": "get_file_metadata"}

    async def test_download_wrapper(self, service):
        with patch.object(service, "download_file",
                          new=AsyncMock(return_value={
                              "status": "success", "data": {"downloadUrl": "u"}})):
            result = await service.execute_operation(
                "download_file", {"access_token": "at", "file_id": "f1"})
        assert result["success"] is True
        assert result["result"]["downloadUrl"] == "u"

    async def test_create_folder_wrapper(self, service):
        with patch.object(service, "create_folder",
                          new=AsyncMock(return_value={
                              "status": "success", "data": {"id": "folder_x"}})):
            result = await service.execute_operation(
                "create_folder", {"access_token": "at",
                                  "parent_folder_id": "0",
                                  "folder_name": "x"})
        assert result["success"] is True
        assert result["result"]["id"] == "folder_x"


# ── Authenticate ─────────────────────────────────────────────────────────────
class TestAuthenticate:
    async def test_success(self, service, monkeypatch):
        monkeypatch.setenv("BOX_CLIENT_ID", "cid96")
        result = await service.authenticate("u96")
        assert result["status"] == "success"
        assert "account.box.com" in result["auth_url"]
        assert "client_id=cid96" in result["auth_url"]
        assert result["state"] == "box_u96"

    async def test_failure(self, service):
        with patch.object(service, "required_scopes", new=[1]):
            result = await service.authenticate("u96")
        assert result["status"] == "error"
        assert "Authentication failed" in result["message"] or "BOX_CLIENT_ID" in result["message"]


# ── File operations ─────────────────────────────────────────────────────────
class _BadStr:
    """Raises when an f-string tries to format it — triggers except branches."""

    def __format__(self, spec):
        raise RuntimeError("boom")


class TestFileOps:
    """Real-API tests: the HTTP layer (_box_get/_box_post/_box_get_bytes)
    is mocked; the assertions verify Box Content API request/response shapes."""

    async def test_list_files_success(self, service):
        with patch.object(service, "_box_get", new=AsyncMock(return_value={
            "entries": [{"id": "123", "name": "Project Proposal.docx", "type": "file"}],
            "total_count": 1, "offset": 5, "limit": 10,
        })) as mock_get:
            result = await service.list_files("at", limit=10, offset=5)
        assert result["status"] == "success"
        data = result["data"]
        assert data["total_count"] == 1
        assert data["offset"] == 5
        assert data["limit"] == 10
        assert data["next_marker"] is None
        assert data["entries"][0]["name"] == "Project Proposal.docx"
        assert "folders/0/items" in mock_get.call_args.args[1]

    async def test_list_files_error(self, service):
        with patch.object(service, "_box_get",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await service.list_files("at")
        assert result["status"] == "error"
        assert "boom" in result["message"]

    async def test_list_files_no_token(self, service):
        service.access_token = None
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BOX_ACCESS_TOKEN", None)
            result = await service.list_files(None)  # type: ignore[arg-type]
        assert result["status"] == "error"
        assert "token" in result["message"].lower()

    async def test_search_files_success(self, service):
        with patch.object(service, "_box_get", new=AsyncMock(return_value={
            "entries": [{"id": "555", "name": f"Search Result: budget.docx", "type": "file"}],
            "total_count": 1,
        })) as mock_get:
            result = await service.search_files("at", query="budget")
        assert result["status"] == "success"
        entries = result["data"]["entries"]
        assert len(entries) == 1
        assert entries[0]["name"] == "Search Result: budget.docx"
        assert mock_get.call_args.kwargs["params"]["query"] == "budget"

    async def test_search_files_error(self, service):
        with patch.object(service, "_box_get",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await service.search_files("at", query="q")
        assert result["status"] == "error"
        assert "boom" in result["message"]

    async def test_get_file_metadata_success(self, service):
        with patch.object(service, "_box_get", new=AsyncMock(return_value={
            "id": "file_9", "type": "file",
            "created_by": {"name": "John Doe", "login": "john.doe@example.com"},
        })) as mock_get:
            result = await service.get_file_metadata("at", "file_9")
        assert result["status"] == "success"
        assert result["data"]["id"] == "file_9"
        assert result["data"]["created_by"]["login"] == "john.doe@example.com"
        assert "files/file_9" in mock_get.call_args.args[1]

    async def test_get_file_metadata_error(self, service):
        with patch.object(service, "_box_get",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await service.get_file_metadata("at", "file_9")
        assert result["status"] == "error"
        assert "boom" in result["message"]

    async def test_download_file_success(self, service):
        with patch.object(service, "_box_get_bytes",
                          new=AsyncMock(return_value=b"file-bytes")) as mock_bytes:
            result = await service.download_file("at", "file_1")
        assert result["status"] == "success"
        data = result["data"]
        assert data["downloadUrl"] == "https://api.box.com/2.0/files/file_1/content"
        assert data["size"] == len(b"file-bytes")
        assert __import__("base64").b64decode(data["content_b64"]) == b"file-bytes"
        assert "files/file_1/content" in mock_bytes.call_args.args[1]

    async def test_download_file_error(self, service):
        with patch.object(service, "_box_get_bytes",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await service.download_file("at", "file_1")
        assert result["status"] == "error"
        assert "boom" in result["message"]

    async def test_create_folder_success(self, service):
        with patch.object(service, "_box_post", new=AsyncMock(return_value={
            "id": "folder_9", "name": "New Folder", "type": "folder",
        })) as mock_post:
            result = await service.create_folder("at", "0", "New Folder")
        assert result["status"] == "success"
        assert result["data"]["name"] == "New Folder"
        assert result["data"]["type"] == "folder"
        assert mock_post.call_args.args[2] == {
            "name": "New Folder", "parent": {"id": "0"}}

    async def test_create_folder_error(self, service):
        with patch.object(service, "_box_post",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await service.create_folder("at", "0", "x")
        assert result["status"] == "error"
        assert "boom" in result["message"]

    async def test_walk_files_recurses_and_paginates(self, service):
        pages = {
            ("0", 0): {
                "entries": [
                    {"id": "d1", "name": "Projects", "type": "folder"},
                    {"id": "f1", "name": "notes.md", "type": "file"},
                ],
            },
            ("d1", 0): {
                "entries": [
                    {"id": "f2", "name": "spec.docx", "type": "file"},
                ],
            },
        }

        async def fake_get(tok, url, params=None):
            fid = url.split("/folders/")[1].split("/")[0]
            offset = (params or {}).get("offset", 0)
            return pages.get((fid, offset), {"entries": []})

        with patch.object(service, "_box_get", new=AsyncMock(side_effect=fake_get)):
            walked = await service.walk_files("at")

        by_id = {f["id"]: f for f in walked}
        assert set(by_id) == {"f1", "f2"}
        assert by_id["f2"]["path"] == "/Projects"
        assert by_id["f1"]["path"] == ""


# ── Sync to PostgreSQL cache ─────────────────────────────────────────────────
class FakeMetric:
    def __init__(self, **kwargs):
        self.value = None
        self.last_synced_at = None
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestSyncToPostgres:
    @contextmanager
    def _patched_sync_db(self, existing=None):
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = existing
        with patch("core.database.SessionLocal", return_value=db), \
                patch("core.models.IntegrationMetric", FakeMetric):
            yield db

    async def test_inserts_new_metric(self, service):
        with patch.object(service, "walk_files",
                          new=AsyncMock(return_value=[
                              {"id": "f1", "path": "/A"},
                              {"id": "f2", "path": ""},
                          ])):
            with self._patched_sync_db(existing=None) as db:
                result = await service.sync_to_postgres_cache("ws-96", "at")
        assert result == {"success": True, "metrics_synced": 2}
        added = db.add.call_args_list[0][0][0]
        assert isinstance(added, FakeMetric)
        assert added.workspace_id == "ws-96"
        assert added.integration_type == "box"
        assert added.metric_key == "box_file_count"
        assert added.value == 2
        db.commit.assert_called_once()
        db.close.assert_called_once()

    async def test_updates_existing_metric(self, service):
        existing = FakeMetric(value=0, last_synced_at=None)
        with patch.object(service, "walk_files",
                          new=AsyncMock(return_value=[
                              {"id": "f1", "path": "/A"},
                              {"id": "f2", "path": "/A/B"},
                          ])):
            with self._patched_sync_db(existing=existing) as db:
                result = await service.sync_to_postgres_cache("ws-96", "at")
        assert result["success"] is True
        assert existing.value == 2.0
        assert existing.last_synced_at is not None
        db.add.assert_not_called()
        db.commit.assert_called_once()

    async def test_db_error_rollback(self, service):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        with patch.object(service, "walk_files", new=AsyncMock(return_value=[])), \
                patch("core.database.SessionLocal", return_value=db):
            result = await service.sync_to_postgres_cache("ws-96", "at")
        assert result["success"] is False
        db.rollback.assert_called_once()
        db.close.assert_called_once()

    async def test_walk_files_error_outer(self, service):
        with patch.object(service, "walk_files",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await service.sync_to_postgres_cache("ws-96", "at")
        assert result["success"] is False
        assert "boom" in result["error"]

    async def test_full_sync(self, service):
        files = [
            {"id": "f1", "name": "a.docx", "path": "/A"},
            {"id": "f2", "name": "b.png", "path": ""},
        ]
        with patch.object(service, "walk_files", new=AsyncMock(return_value=files)), \
                patch.object(service, "ingest_file_to_memory", new=AsyncMock(
                    return_value={"success": True, "result": {"status": "ingested"}})), \
                patch.object(service, "sync_to_postgres_cache", new=AsyncMock(
                    return_value={"success": True, "metrics_synced": 2})):
            result = await service.full_sync("ws-96", "at")
        assert result["success"] is True
        assert result["workspace_id"] == "ws-96"
        assert result["files_found"] == 2
        assert result["files_ingested"] == 2  # every file type attempted
        assert result["postgres_cache"]["metrics_synced"] == 2
        assert result["timestamp"]


# ── OAuth wiring / token resolution ─────────────────────────────────────────
class TestOAuthTokenResolution:
    def test_box_registered_in_unified_oauth_flow(self):
        from core.oauth_handler import PROVIDER_CONFIGS

        cfg = PROVIDER_CONFIGS["box"]
        assert cfg.auth_url == "https://account.box.com/api/oauth2/authorize"
        assert cfg.token_url == "https://api.box.com/oauth2/token"
        assert cfg._client_id_env == "BOX_CLIENT_ID"

    async def test_full_sync_resolves_token_from_integration_token(self, service):
        service.access_token = None
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BOX_ACCESS_TOKEN", None)
            with patch.object(service, "get_access_token",
                              new=AsyncMock(return_value="db-tok")) as mock_get, \
                    patch.object(service, "walk_files",
                                 new=AsyncMock(return_value=[])) as mock_walk, \
                    patch.object(service, "ingest_file_to_memory", AsyncMock()), \
                    patch.object(service, "sync_to_postgres_cache", AsyncMock(
                        return_value={"success": True, "metrics_synced": 2})):
                result = await service.full_sync("ws-96", None)
        assert result["success"] is True
        mock_get.assert_awaited_once_with("ws-96")
        assert mock_walk.call_args.args[0] == "db-tok"

    async def test_full_sync_without_any_token_fails_cleanly(self, service):
        service.access_token = None
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BOX_ACCESS_TOKEN", None)
            with patch.object(service, "get_access_token",
                              new=AsyncMock(return_value=None)):
                result = await service.full_sync("ws-96", None)
        assert result["success"] is False
        assert "No Box access token" in result["error"]

    async def test_get_access_token_none_without_record(self, service):
        record = MagicMock()
        record.access_token = None
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = record
        with patch("core.database.SessionLocal", return_value=db):
            token = await service.get_access_token("u1")
        assert token is None


# ── Singleton ────────────────────────────────────────────────────────────────
class TestSingleton:
    def test_singleton_configured(self):
        assert isinstance(box_service, BoxService)
        assert box_service.service_name == "box"
