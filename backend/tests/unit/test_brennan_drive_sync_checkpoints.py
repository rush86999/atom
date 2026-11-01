"""Durable WorkDrive/OneDrive page checkpoints, restart and deletion controls."""
from __future__ import annotations

import asyncio

import pytest

from core import drive_sync_checkpoints as checkpoints


class FakeStateService:
    def __init__(self):
        self.usage_stats = {}
        self.persists = 0

    def _persist_integration(self, integration_id):
        self.persists += 1


def _patch_state(monkeypatch, service):
    monkeypatch.setattr(checkpoints, "_state_service", lambda ws, tid: service)


def _patch_index(monkeypatch, written=1):
    writes = []

    async def fake_index(self, integration_id, rows, max_rows=500):
        writes.extend(rows)
        return {"success": True, "rows_found": len(rows),
                "rows_written": written, "counts": {}}

    monkeypatch.setattr(
        "core.drive_tree_ingestion.IntegrationMemoryIndexer.index_rows",
        fake_index)
    return writes


def _page(*ids, cursor=None, has_more=False):
    return {
        "status": "success",
        "provider": "zoho_workdrive",
        "items": [
            {"id": item, "name": f"{item}.pdf", "type": "file",
             "size": 10, "modified_at": "2026-11-01T00:00:00Z",
             "version": "1"}
            for item in ids
        ],
        "next_cursor": cursor,
        "has_more": has_more,
        "coverage": "partial" if has_more else "page_complete",
    }


def test_two_pages_resume_from_saved_cursor(monkeypatch):
    service = FakeStateService()
    _patch_state(monkeypatch, service)
    writes = _patch_index(monkeypatch)
    cursors = []

    async def fake_read(provider, **kwargs):
        cursors.append(kwargs.get("cursor"))
        if kwargs.get("cursor") is None:
            return _page("a", "b", cursor="cursor-1", has_more=True)
        return _page("c", cursor=None, has_more=False)

    monkeypatch.setattr(checkpoints, "_read_page", fake_read)
    common = dict(provider="zoho_workdrive", user_id="user-1",
                  workspace_id="ws-1", tenant_id="t1",
                  folder_id="folder-1", provider_workspace_id="provider-ws")

    first = asyncio.run(checkpoints.sync_drive_page(**common))
    assert first["has_more"] is True
    assert first["checkpoint"]["coverage"] == "in_progress"
    assert first["checkpoint"]["next_cursor"] == "cursor-1"

    second = asyncio.run(checkpoints.sync_drive_page(**common))
    assert cursors == [None, "cursor-1"]
    assert second["has_more"] is False
    assert second["checkpoint"]["coverage"] == "complete"
    assert second["checkpoint"]["checkpoint"]["pages_completed"] == 2
    assert [row["external_id"] for row in writes] == ["a", "b", "c"]
    assert service.persists >= 2


def test_restart_reads_checkpoint_from_persisted_state(monkeypatch):
    first_service = FakeStateService()
    _patch_state(monkeypatch, first_service)
    _patch_index(monkeypatch)

    async def first_read(provider, **kwargs):
        return _page("a", cursor="cursor-1", has_more=True)

    monkeypatch.setattr(checkpoints, "_read_page", first_read)
    asyncio.run(checkpoints.sync_drive_page(
        provider="zoho_workdrive", user_id="u", workspace_id="ws-1",
        tenant_id="t1", folder_id="folder-1",
        provider_workspace_id="provider-ws"))

    # Simulate a process restart: only the persisted JSON survives.
    from core.hybrid_data_ingestion import IntegrationUsageStats

    persisted = dict(first_service.usage_stats["zoho_workdrive"].sync_cursors)
    second_service = FakeStateService()
    second_service.usage_stats["zoho_workdrive"] = IntegrationUsageStats(
        integration_id="zoho_workdrive", integration_name="zoho_workdrive")
    second_service.usage_stats["zoho_workdrive"].sync_cursors = persisted
    _patch_state(monkeypatch, second_service)
    _patch_index(monkeypatch)
    cursors = []

    async def second_read(provider, **kwargs):
        cursors.append(kwargs.get("cursor"))
        return _page("b", cursor=None, has_more=False)

    monkeypatch.setattr(checkpoints, "_read_page", second_read)
    result = asyncio.run(checkpoints.sync_drive_page(
        provider="zoho_workdrive", user_id="u", workspace_id="ws-1",
        tenant_id="t1", folder_id="folder-1",
        provider_workspace_id="provider-ws"))

    assert cursors == ["cursor-1"]
    assert result["checkpoint"]["coverage"] == "complete"


def test_complete_relisting_reports_remote_deletions_without_deleting(monkeypatch):
    service = FakeStateService()
    _patch_state(monkeypatch, service)
    writes = _patch_index(monkeypatch)
    scope = checkpoints.checkpoint_scope(
        "zoho_workdrive", folder_id="folder-1",
        provider_workspace_id="provider-ws")
    checkpoints.save_checkpoint(
        "zoho_workdrive", scope,
        {
            "version": 1, "provider": "zoho_workdrive", "scope": scope,
            "state": "complete", "pages_completed": 1, "rows_seen": 2,
            "rows_written": 2, "run_seen_ids": [], "prior_known_ids": [],
            "known_ids": ["a", "b"], "missing_external_ids": [],
            "ids_truncated": False, "deletion_check": "complete",
            "last_success_at": "2026-11-01T00:00:00+00:00",
            "started_at": "2026-11-01T00:00:00+00:00",
        },
        workspace_id="ws-1", tenant_id="t1")

    async def fake_read(provider, **kwargs):
        return _page("a", cursor=None, has_more=False)

    monkeypatch.setattr(checkpoints, "_read_page", fake_read)
    result = asyncio.run(checkpoints.sync_drive_page(
        provider="zoho_workdrive", user_id="u", workspace_id="ws-1",
        tenant_id="t1", folder_id="folder-1",
        provider_workspace_id="provider-ws", fresh=True))

    assert result["missing_external_ids"] == ["b"]
    assert result["checkpoint"]["coverage"] == "complete_with_remote_deletions"
    assert [row["external_id"] for row in writes] == ["a"]
    assert result["checkpoint"]["checkpoint"]["known_ids"] == ["a"]


def test_revoked_grant_is_persisted_and_not_an_empty_page(monkeypatch):
    service = FakeStateService()
    _patch_state(monkeypatch, service)
    writes = _patch_index(monkeypatch)

    async def revoked(provider, **kwargs):
        return {
            "status": "error", "success": False, "provider": "onedrive",
            "operation": "list_files_page", "error_kind": "auth_revoked",
            "error": "The grant was revoked.", "retryable": False,
            "requires_reconnect": True,
        }

    monkeypatch.setattr(checkpoints, "_read_page", revoked)
    result = asyncio.run(checkpoints.sync_drive_page(
        provider="onedrive", user_id="u", workspace_id="ws-1",
        tenant_id="t1", drive_id="drive-1", site_id="site-1",
        folder_id="folder-1"))

    assert result["status"] == "error"
    assert result["action_result"] == "unavailable"
    assert result["checkpoint"]["coverage"] == "revoked"
    assert writes == []
    assert service.persists == 1


def test_coverage_status_reports_stale_and_unknown(monkeypatch):
    service = FakeStateService()
    _patch_state(monkeypatch, service)
    scope = checkpoints.checkpoint_scope(
        "onedrive", folder_id="f", drive_id="d", site_id="s")
    checkpoints.save_checkpoint(
        "onedrive", scope,
        {
            "version": 1, "provider": "onedrive", "scope": scope,
            "state": "complete", "pages_completed": 1,
            "rows_seen": 1, "rows_written": 1, "run_seen_ids": [],
            "prior_known_ids": [], "known_ids": ["a"],
            "missing_external_ids": [], "ids_truncated": False,
            "deletion_check": "complete",
            "last_success_at": "2020-01-01T00:00:00+00:00",
            "started_at": "2020-01-01T00:00:00+00:00",
        },
        workspace_id="ws-1", tenant_id="t1")

    status = checkpoints.coverage_status(
        "onedrive", scope, workspace_id="ws-1", tenant_id="t1")
    assert status["coverage"] == "complete"
    assert status["stale"] is True
    assert status["age_seconds"] > 0

    missing = checkpoints.coverage_status(
        "onedrive", "site=-|drive=me|folder=never",
        workspace_id="ws-1", tenant_id="t1")
    assert missing["coverage"] == "never_synced"
    assert missing["checkpoint"] is None


def test_status_route_surfaces_coverage(monkeypatch):
    from types import SimpleNamespace
    from api import document_ingestion_routes as routes

    service = FakeStateService()
    _patch_state(monkeypatch, service)
    scope = checkpoints.checkpoint_scope(
        "zoho_workdrive", folder_id="folder-1",
        provider_workspace_id="provider-ws")
    checkpoints.save_checkpoint(
        "zoho_workdrive", scope,
        {
            "version": 1, "provider": "zoho_workdrive", "scope": scope,
            "state": "in_progress", "pages_completed": 1, "rows_seen": 2,
            "rows_written": 2, "run_seen_ids": ["a", "b"],
            "prior_known_ids": [], "known_ids": [],
            "missing_external_ids": [], "ids_truncated": False,
            "deletion_check": "pending", "next_cursor": "cursor-2",
            "last_success_at": "2026-11-01T00:00:00+00:00",
            "started_at": "2026-11-01T00:00:00+00:00",
        },
        workspace_id="ws-1", tenant_id="t1")

    user = SimpleNamespace(id="user-1", tenant_id="t1",
                           workspace_id="ws-1", workspaces=[])
    result = asyncio.run(routes.get_drive_sync_status(
        "zoho_workdrive", current_user=user, workspace_id="ws-1",
        folder_id="folder-1", drive_id=None, site_id=None,
        provider_workspace_id="provider-ws", max_age_seconds=None))

    assert result["coverage"] == "in_progress"
    assert result["next_cursor"] == "cursor-2"


def test_sync_page_route_returns_page_and_records_feedback(monkeypatch):
    from types import SimpleNamespace
    from api import document_ingestion_routes as routes

    recorded = []
    monkeypatch.setattr(routes, "record_ingestion_feedback",
                        lambda *a, **k: recorded.append((a, k)))

    async def fake_sync(**kwargs):
        assert kwargs["provider"] == "onedrive"
        assert kwargs["drive_id"] == "drive-1"
        return {"status": "success", "rows_written": 3,
                "coverage": "partial", "next_cursor": "c2"}

    monkeypatch.setattr("core.drive_sync_checkpoints.sync_drive_page",
                        fake_sync)
    user = SimpleNamespace(id="user-1", tenant_id="t1",
                           workspace_id="ws-1", workspaces=[])
    result = asyncio.run(routes.sync_drive_page_route(
        "onedrive",
        routes.DriveSyncPageRequest(
            workspace_id="ws-1", folder_id="folder-1",
            drive_id="drive-1", site_id="site-1", page_size=50),
        current_user=user))

    assert result["coverage"] == "partial"
    assert recorded and recorded[0][0][1] == "onedrive"
