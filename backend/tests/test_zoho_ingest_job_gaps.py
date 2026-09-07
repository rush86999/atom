"""Ingest-job UX gaps for api/zoho_workdrive_routes.py.

Covers the three gaps found in live use (2026-09-04):
1. Duplicate ingest coalescing — a second POST for the same file/folder while
   a job is running returns the RUNNING job instead of racing it (double
   clicks doubled the Zoho API load on a quota-limited tree walk).
2. GET /ingest/jobs — recent-jobs list so the UI can re-attach after page
   navigation (job ids otherwise lived only in the starting page).
3. POST /ingested-ids — durable badge source of truth (which of these
   WorkDrive file ids are already in ATOM memory).
"""
import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import zoho_workdrive_routes as zwr
from core import ingest_jobs
from core.auth import get_current_user
from core.models import User

USER_ID = "gaps-user"
OTHER_ID = "gaps-other"


def _client_for(user_id: str) -> TestClient:
    app = FastAPI()
    app.include_router(zwr.router)
    app.dependency_overrides[get_current_user] = lambda: User(
        id=user_id, email=f"{user_id}@x.com", first_name="G", last_name="U",
        role="admin", status="active",
    )
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client():
    ingest_jobs.registry.clear()
    yield _client_for(USER_ID)
    ingest_jobs.registry.clear()


@pytest.fixture
def other_client():
    return _client_for(OTHER_ID)


def _stalled():
    """AsyncMock whose coroutine stays pending — the job remains 'running'."""
    async def _never(*args, **kwargs):
        await asyncio.sleep(3600)
        return {"success": True}
    return AsyncMock(side_effect=_never)


class TestDuplicateCoalescing:
    def test_second_file_post_returns_running_job(self, client):
        with patch.object(zwr.zoho_service, "ingest_file_to_memory", new=_stalled()):
            first = client.post("/api/zoho-workdrive/ingest", json={"file_id": "f1"})
            second = client.post("/api/zoho-workdrive/ingest", json={"file_id": "f1"})
        assert first.json()["data"]["job_id"] == second.json()["data"]["job_id"]
        assert second.json()["data"]["coalesced"] is True

    def test_different_file_gets_own_job(self, client):
        with patch.object(zwr.zoho_service, "ingest_file_to_memory", new=_stalled()):
            first = client.post("/api/zoho-workdrive/ingest", json={"file_id": "f1"})
            second = client.post("/api/zoho-workdrive/ingest", json={"file_id": "f2"})
        assert first.json()["data"]["job_id"] != second.json()["data"]["job_id"]

    def test_second_folder_post_returns_running_job(self, client):
        with patch.object(zwr.zoho_service, "ingest_folder_tree", new=_stalled()):
            first = client.post("/api/zoho-workdrive/ingest-folder", json={"folder_id": "fldA"})
            # same folder via the batch form must coalesce too (sorted ids match)
            second = client.post("/api/zoho-workdrive/ingest-folder", json={"folder_ids": ["fldA"]})
        assert first.json()["data"]["job_id"] == second.json()["data"]["job_id"]

    def test_repost_after_completion_starts_new_job(self, client):
        with patch.object(zwr.zoho_service, "ingest_file_to_memory",
                          new=AsyncMock(return_value={"success": True, "doc_id": "d1"})):
            first = client.post("/api/zoho-workdrive/ingest", json={"file_id": "f1"})
            job_id = first.json()["data"]["job_id"]
            deadline = time.time() + 5
            while time.time() < deadline:
                snap = client.get(f"/api/zoho-workdrive/ingest/jobs/{job_id}").json()["data"]
                if snap["status"] != "running":
                    break
                time.sleep(0.02)
            assert snap["status"] == "completed"
            second = client.post("/api/zoho-workdrive/ingest", json={"file_id": "f1"})
        assert second.json()["data"]["job_id"] != job_id
        assert "coalesced" not in second.json()["data"]


class TestRecentJobsList:
    def test_lists_running_jobs_for_current_user_only(self, client, other_client):
        with patch.object(zwr.zoho_service, "ingest_folder_tree", new=_stalled()):
            mine = client.post("/api/zoho-workdrive/ingest-folder", json={"folder_id": "fldA"})
            theirs = other_client.post("/api/zoho-workdrive/ingest-folder", json={"folder_id": "fldB"})
        jobs = client.get("/api/zoho-workdrive/ingest/jobs").json()["data"]
        ids = {j["job_id"] for j in jobs}
        assert mine.json()["data"]["job_id"] in ids
        assert theirs.json()["data"]["job_id"] not in ids
        assert all(j["status"] == "running" for j in jobs)

    def test_running_jobs_listed_first_with_kind(self, client):
        with patch.object(zwr.zoho_service, "ingest_folder_tree", new=_stalled()):
            client.post("/api/zoho-workdrive/ingest-folder", json={"folder_id": "fldA"})
        jobs = client.get("/api/zoho-workdrive/ingest/jobs").json()["data"]
        assert jobs and jobs[0]["kind"] == "folder"
        assert jobs[0]["folder_ids"] == ["fldA"]


class TestIngestedIds:
    def test_returns_ingested_ids_from_document_store(self, client):
        with patch("core.auto_document_ingestion.AutoDocumentIngestionService") as svc_cls:
            svc_cls.return_value.ingested_external_ids = AsyncMock(return_value=["f1"])
            resp = client.post("/api/zoho-workdrive/ingested-ids",
                               json={"file_ids": ["f1", "f2"]})
        assert resp.status_code == 200
        assert resp.json()["data"]["ingested"] == ["f1"]
        svc_cls.return_value.ingested_external_ids.assert_awaited_once_with(
            "zoho_workdrive", ["f1", "f2"])

    def test_empty_file_ids_rejected_422(self, client):
        resp = client.post("/api/zoho-workdrive/ingested-ids", json={"file_ids": []})
        assert resp.status_code == 422

    def test_unauthenticated_401(self):
        app = FastAPI()
        app.include_router(zwr.router)
        resp = TestClient(app).post("/api/zoho-workdrive/ingested-ids",
                                    json={"file_ids": ["f1"]})
        assert resp.status_code == 401


class TestUnchangedSkipNotFailure:
    """Re-ingesting an already-stored, byte-identical file must succeed as a
    no-op — previously the 'unchanged' skip surfaced to the panel as
    'File ingest failed' (2026-09-05 live report on Consolidated Price List
    2019.xlsx). Real skips (unsupported format, write failures) stay failures."""

    @staticmethod
    def _run_ingest(monkeypatch, process_result):
        from unittest.mock import MagicMock

        from integrations.zoho_workdrive_service import ZohoWorkDriveService
        svc = ZohoWorkDriveService.__new__(ZohoWorkDriveService)
        monkeypatch.setattr(svc, "get_access_token", AsyncMock(return_value="tok"))
        monkeypatch.setattr(svc, "download_file", AsyncMock(return_value=b"bytes"))
        meta_resp = MagicMock()
        meta_resp.json.return_value = {"data": {"attributes": {"name": "a.xlsx"}}}
        svc.base_url = "https://workdrive.example"
        svc.client = MagicMock()
        svc.client.get = AsyncMock(return_value=meta_resp)
        monkeypatch.setattr(
            "core.auto_document_ingestion.AutoDocumentIngestionService.process_file_bytes",
            AsyncMock(return_value=process_result),
        )
        return asyncio.run(svc.ingest_file_to_memory("u", "f1"))

    def test_unchanged_skip_is_success(self, monkeypatch):
        result = self._run_ingest(monkeypatch, {
            "status": "skipped", "reason": "unchanged", "file_name": "a.xlsx",
        })
        assert result["success"] is True
        assert result["unchanged"] is True

    def test_unsupported_skip_still_fails(self, monkeypatch):
        result = self._run_ingest(monkeypatch, {
            "status": "skipped", "reason": "unsupported_format", "file_name": "a.exe",
        })
        assert result["success"] is False
        assert "unsupported_format" in result["error"]

    def test_write_failed_still_fails(self, monkeypatch):
        result = self._run_ingest(monkeypatch, {
            "status": "skipped", "reason": "write_failed (store_error)",
            "file_name": "a.docx",
        })
        assert result["success"] is False
