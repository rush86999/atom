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
    async def test_success(self, service):
        result = await service.authenticate("u96")
        assert result["status"] == "success"
        assert "account.box.com" in result["auth_url"]
        assert "root_readonly" in result["auth_url"]
        assert result["state"] == "box_u96"

    async def test_failure(self, service):
        with patch.object(service, "required_scopes", new=[1]):
            result = await service.authenticate("u96")
        assert result["status"] == "error"
        assert "Authentication failed" in result["message"]


# ── File operations ─────────────────────────────────────────────────────────
class _BadStr:
    """Raises when an f-string tries to format it — triggers except branches."""

    def __format__(self, spec):
        raise RuntimeError("boom")


class TestFileOps:
    async def test_list_files_success(self, service):
        result = await service.list_files("at", limit=10, offset=5)
        assert result["status"] == "success"
        data = result["data"]
        assert data["total_count"] == 2
        assert data["offset"] == 5
        assert data["limit"] == 10
        assert data["next_marker"] is None
        assert data["entries"][0]["name"] == "Project Proposal.docx"

    async def test_search_files_success(self, service):
        result = await service.search_files("at", query="budget")
        assert result["status"] == "success"
        entries = result["data"]["entries"]
        assert len(entries) == 1
        assert entries[0]["name"] == "Search Result: budget.docx"

    async def test_search_files_error(self, service):
        result = await service.search_files("at", query=_BadStr())
        assert result["status"] == "error"
        assert "boom" in result["message"]

    async def test_search_files_execute_error(self, service):
        with patch.object(service, "_execute_search_files",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await service.execute_operation(
                "search_files", {"access_token": "at", "query": "q"})
        assert result["success"] is False
        assert result["error"] == "boom"

    async def test_get_file_metadata_success(self, service):
        result = await service.get_file_metadata("at", "file_9")
        assert result["status"] == "success"
        assert result["data"]["id"] == "file_9"
        assert result["data"]["created_by"]["login"] == "john.doe@example.com"

    async def test_get_file_metadata_error(self, service):
        result = await service.get_file_metadata("at", _BadStr())
        assert result["status"] == "error"
        assert "boom" in result["message"]

    async def test_download_file_success(self, service):
        result = await service.download_file("at", "file_1")
        assert result["status"] == "success"
        assert result["data"]["downloadUrl"] == (
            "https://api.box.com/2.0/files/file_1/content")

    async def test_download_file_error(self, service):
        with patch.object(service, "base_url", new=_BadStr()):
            result = await service.download_file("at", "file_1")
        assert result["status"] == "error"
        assert "boom" in result["message"]

    async def test_create_folder_success(self, service):
        result = await service.create_folder("at", "0", "New Folder")
        assert result["status"] == "success"
        assert result["data"]["name"] == "New Folder"
        assert result["data"]["type"] == "folder"

    async def test_create_folder_error(self, service):
        result = await service.create_folder("at", "0", _BadStr())
        assert result["status"] == "error"
        assert "boom" in result["message"] or "len" in result["message"]


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
        with self._patched_sync_db(existing=None) as db:
            result = await service.sync_to_postgres_cache("ws-96", "at")
        assert result == {"success": True, "metrics_synced": 1}
        db.add.assert_called_once()
        added = db.add.call_args[0][0]
        assert isinstance(added, FakeMetric)
        assert added.tenant_id == "ws-96"
        assert added.integration_type == "box"
        assert added.metric_key == "box_file_count"
        assert added.value == 2
        db.commit.assert_called_once()
        db.close.assert_called_once()

    async def test_updates_existing_metric(self, service):
        existing = FakeMetric(value=0, last_synced_at=None)
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
        with patch("core.database.SessionLocal", return_value=db):
            result = await service.sync_to_postgres_cache("ws-96", "at")
        assert result["success"] is False
        db.rollback.assert_called_once()
        db.close.assert_called_once()

    async def test_list_files_error_outer(self, service):
        with patch.object(service, "list_files",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await service.sync_to_postgres_cache("ws-96", "at")
        assert result["success"] is False
        assert "boom" in result["error"]

    async def test_full_sync(self, service):
        with patch.object(service, "sync_to_postgres_cache",
                          new=AsyncMock(return_value={
                              "success": True, "metrics_synced": 1})):
            result = await service.full_sync("ws-96", "at")
        assert result["success"] is True
        assert result["workspace_id"] == "ws-96"
        assert result["postgres_cache"]["metrics_synced"] == 1
        assert result["timestamp"]


# ── Singleton ────────────────────────────────────────────────────────────────
class TestSingleton:
    def test_singleton_configured(self):
        assert isinstance(box_service, BoxService)
        assert box_service.service_name == "box"
