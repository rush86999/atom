"""Coverage wave 38 — api/zoho_workdrive_routes.py (→ 90%+).

The router (auth'd via router-level Depends) delegates to
ZohoWorkDriveService: teams / files-list / ingest / health. Service calls are
mocked — no network.
"""
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.zoho_workdrive_routes import router
from core.auth import get_current_user
from core.models import User


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: User(
        id="u1", email="u@example.com", first_name="U", last_name="X",
        role="admin", status="active",
    )
    return TestClient(app)


class TestTeams:
    def test_teams_success(self, client):
        with patch("api.zoho_workdrive_routes.zoho_service.get_teams",
                   new=AsyncMock(return_value=[{"id": "t1", "name": "Team A"}])):
            resp = client.get("/api/zoho-workdrive/teams")
        assert resp.status_code == 200
        assert resp.json()["data"] == [{"id": "t1", "name": "Team A"}]

    def test_teams_error_500(self, client):
        with patch("api.zoho_workdrive_routes.zoho_service.get_teams",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            resp = client.get("/api/zoho-workdrive/teams")
        assert resp.status_code == 500
        body = resp.json()
        assert body["detail"]["success"] is False
        assert body["detail"]["error"]["code"] == "INTERNAL_ERROR"

    def test_teams_unauthenticated_401(self):
        app = FastAPI()
        app.include_router(router)
        resp = TestClient(app).get("/api/zoho-workdrive/teams")
        assert resp.status_code == 401


class TestListFiles:
    def test_list_files_success(self, client):
        with patch("api.zoho_workdrive_routes.zoho_service.list_files",
                   new=AsyncMock(return_value=[{"id": "f1"}])):
            resp = client.post("/api/zoho-workdrive/files/list", json={
                "parent_id": "root"})
        assert resp.status_code == 200
        assert resp.json()["data"] == [{"id": "f1"}]

    def test_list_files_default_parent(self, client):
        with patch("api.zoho_workdrive_routes.zoho_service.list_files",
                   new=AsyncMock(return_value=[])) as m:
            resp = client.post("/api/zoho-workdrive/files/list", json={})
        assert resp.status_code == 200
        m.assert_awaited_once_with("u1", "root", None, None, False)

    def test_list_files_forged_user_id_ignored(self, client):
        # Identity comes from the token: a client-supplied user_id in the body
        # must be ignored (extra fields) — the service still receives "u1".
        with patch("api.zoho_workdrive_routes.zoho_service.list_files",
                   new=AsyncMock(return_value=[])) as m:
            resp = client.post("/api/zoho-workdrive/files/list",
                               json={"user_id": "attacker", "parent_id": "root"})
        assert resp.status_code == 200
        m.assert_awaited_once_with("u1", "root", None, None, False)

    def test_list_files_error_500(self, client):
        with patch("api.zoho_workdrive_routes.zoho_service.list_files",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            resp = client.post("/api/zoho-workdrive/files/list", json={})
        assert resp.status_code == 500

    def test_list_files_empty_body_is_valid(self, client):
        # Every FileListRequest field is optional (user_id removed — identity
        # is token-derived), so an empty body now defaults to the root folder.
        with patch("api.zoho_workdrive_routes.zoho_service.list_files",
                   new=AsyncMock(return_value=[])) as m:
            resp = client.post("/api/zoho-workdrive/files/list", json={})
        assert resp.status_code == 200
        m.assert_awaited_once_with("u1", "root", None, None, False)

    def test_ingest_folder_max_files_bounds_422(self, client):
        resp = client.post("/api/zoho-workdrive/ingest-folder", json={
            "folder_id": "root", "max_files": 10_000_000})
        assert resp.status_code == 422


class TestIngest:
    @staticmethod
    def _await_ingest_job(client, job_id, timeout=5.0):
        # Ingest runs as a background task; poll the job-status endpoint
        # until it leaves "running" (mocked service calls resolve fast).
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = client.get(f"/api/zoho-workdrive/ingest/jobs/{job_id}")
            assert resp.status_code == 200
            job = resp.json()["data"]
            if job["status"] != "running":
                return job
            time.sleep(0.02)
        raise AssertionError(f"ingest job {job_id} never finished")

    def test_ingest_starts_background_job_and_completes(self, client):
        with patch("api.zoho_workdrive_routes.zoho_service.ingest_file_to_memory",
                   new=AsyncMock(return_value={"success": True, "doc_id": "d1"})):
            resp = client.post("/api/zoho-workdrive/ingest", json={
                "user_id": "u1", "file_id": "f1"})
        assert resp.status_code == 200
        started = resp.json()["data"]
        assert started["status"] == "started"
        assert started["file_id"] == "f1"
        job = self._await_ingest_job(client, started["job_id"])
        assert job["status"] == "completed"
        assert job["result"]["doc_id"] == "d1"

    def test_ingest_service_error_becomes_failed_job(self, client):
        # A failure used to surface as a synchronous 500 while the client was
        # still waiting (proxy timeout at 30s made it worse); now it lands in
        # the job record and the poller reports it.
        with patch("api.zoho_workdrive_routes.zoho_service.ingest_file_to_memory",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            resp = client.post("/api/zoho-workdrive/ingest", json={
                "user_id": "u1", "file_id": "f1"})
        assert resp.status_code == 200
        job = self._await_ingest_job(client, resp.json()["data"]["job_id"])
        assert job["status"] == "failed"
        assert "boom" in job["error"]

    def test_ingest_validation_422(self, client):
        resp = client.post("/api/zoho-workdrive/ingest", json={})
        assert resp.status_code == 422


class TestHealth:
    def test_health_configured(self, client):
        with patch("api.zoho_workdrive_routes.zoho_service") as svc:
            svc.client_id = "id"
            svc.client_secret = "sec"
            svc.redirect_uri = "uri"
            resp = client.get("/api/zoho-workdrive/health")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "configured"

    def test_health_unconfigured(self, client):
        with patch("api.zoho_workdrive_routes.zoho_service") as svc:
            svc.client_id = None
            svc.client_secret = None
            svc.redirect_uri = None
            resp = client.get("/api/zoho-workdrive/health")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "unconfigured"
