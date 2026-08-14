"""Coverage wave 102 — integrations/google_drive_routes.py (TDD, 0% baseline).

Fully mocked (GoogleDriveService methods patched on the module singleton,
fake get_current_user), zero network, zero LLM spend.

BUG FOUND + FIXED (TDD RED->GREEN): the data endpoints GET /files,
POST /search, GET /files/{file_id} and GET /files/{file_id}/download had NO
authentication — anonymous users could list/search/read/download any file in
the tenant's Google Drive reachable via a leaked access_token. The
anonymous-401 tests below were RED (200) before the fix; `get_current_user`
is now required on all four. (/auth, /health and /capabilities stay public,
matching the wave-93 dropbox OAuth-flow convention.)

Covers: /auth (success, error envelope -> 400, missing user_id -> 422),
/files (success, error envelope -> 400, anon 401), /search (success, error
envelope -> 400, anon 401), /files/{file_id} (success, error -> 400, anon
401), /files/{file_id}/download (success, error -> 400, anon 401), /health,
/capabilities.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.models import User

from integrations import google_drive_routes as gdr

FILE_DATA = {"files": [{"id": "f1", "name": "report.pdf"}], "nextPageToken": None}


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = "gd102-user"
    u.email = "gd102@x.com"
    return u


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(gdr.google_drive_router)
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(gdr.google_drive_router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _svc():
    with patch.object(gdr.google_drive_service, "authenticate",
                      new=AsyncMock(
                          return_value={"status": "success",
                                        "auth_url": "https://accounts.google.com/o/oauth2/auth",
                                        "state": "gdrive_u1"})), \
            patch.object(gdr.google_drive_service, "list_files",
                         new=AsyncMock(return_value={"status": "success",
                                                     "data": FILE_DATA})), \
            patch.object(gdr.google_drive_service, "search_files",
                         new=AsyncMock(return_value={"status": "success",
                                                     "data": FILE_DATA})), \
            patch.object(gdr.google_drive_service, "get_file_metadata",
                         new=AsyncMock(
                             return_value={"status": "success",
                                           "data": {"id": "f1",
                                                    "name": "report.pdf"}})), \
            patch.object(gdr.google_drive_service, "download_file",
                         new=AsyncMock(
                             return_value={"status": "success",
                                           "data": {"webContentLink": "https://dl"}})):
        yield gdr.google_drive_service


class TestAuth:
    def test_success(self, anon_client):
        response = anon_client.get("/google_drive/auth",
                                   params={"user_id": "u1"})
        assert response.status_code == 200
        body = response.json()
        assert "accounts.google.com" in body["auth_url"]
        assert body["state"] == "gdrive_u1"
        gdr.google_drive_service.authenticate.assert_awaited_once_with("u1")

    def test_error_envelope_400(self, anon_client):
        gdr.google_drive_service.authenticate.return_value = {
            "status": "error", "message": "GOOGLE_CLIENT_ID not configured"}
        response = anon_client.get("/google_drive/auth",
                                   params={"user_id": "u1"})
        assert response.status_code == 400
        assert response.json()["detail"] == "GOOGLE_CLIENT_ID not configured"

    def test_missing_user_id_422(self, anon_client):
        response = anon_client.get("/google_drive/auth")
        assert response.status_code == 422


class TestListFiles:
    def test_success(self, client):
        response = client.get("/google_drive/files",
                              params={"access_token": "tok",
                                      "folder_id": "folder1",
                                      "page_size": 50, "page_token": "pg1"})
        assert response.status_code == 200
        body = response.json()
        assert body["files"][0]["id"] == "f1"
        assert body["files"][0]["name"] == "report.pdf"
        assert body["nextPageToken"] is None
        gdr.google_drive_service.list_files.assert_awaited_once_with(
            "tok", "folder1", 50, "pg1")

    def test_success_defaults(self, client):
        response = client.get("/google_drive/files",
                              params={"access_token": "tok"})
        assert response.status_code == 200
        gdr.google_drive_service.list_files.assert_awaited_once_with(
            "tok", None, 100, None)

    def test_error_envelope_400(self, client):
        gdr.google_drive_service.list_files.return_value = {
            "status": "error", "message": "No access token provided"}
        response = client.get("/google_drive/files",
                              params={"access_token": "tok"})
        assert response.status_code == 400
        assert response.json()["detail"] == "No access token provided"

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/google_drive/files",
                                   params={"access_token": "tok"})
        assert response.status_code == 401


class TestSearch:
    def test_success(self, client):
        response = client.post(
            "/google_drive/search",
            params={"access_token": "tok"},
            json={"query": "invoice", "pageSize": 20, "pageToken": "pg"})
        assert response.status_code == 200
        body = response.json()
        assert body["files"][0]["id"] == "f1"
        assert body["files"][0]["name"] == "report.pdf"
        gdr.google_drive_service.search_files.assert_awaited_once_with(
            "tok", "invoice", 20, "pg")

    def test_error_envelope_400(self, client):
        gdr.google_drive_service.search_files.return_value = {
            "status": "error", "message": "No access token provided"}
        response = client.post("/google_drive/search",
                               params={"access_token": "tok"},
                               json={"query": "invoice"})
        assert response.status_code == 400

    def test_missing_query_422(self, client):
        response = client.post("/google_drive/search",
                               params={"access_token": "tok"}, json={})
        assert response.status_code == 422

    def test_anonymous_401(self, anon_client):
        response = anon_client.post("/google_drive/search",
                                    params={"access_token": "tok"},
                                    json={"query": "invoice"})
        assert response.status_code == 401


class TestGetFileMetadata:
    def test_success(self, client):
        response = client.get("/google_drive/files/f1",
                              params={"access_token": "tok"})
        assert response.status_code == 200
        assert response.json()["id"] == "f1"
        gdr.google_drive_service.get_file_metadata.assert_awaited_once_with(
            "tok", "f1")

    def test_error_envelope_400(self, client):
        gdr.google_drive_service.get_file_metadata.return_value = {
            "status": "error", "message": "File not found"}
        response = client.get("/google_drive/files/missing",
                              params={"access_token": "tok"})
        assert response.status_code == 400
        assert response.json()["detail"] == "File not found"

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/google_drive/files/f1",
                                   params={"access_token": "tok"})
        assert response.status_code == 401


class TestDownload:
    def test_success(self, client):
        response = client.get("/google_drive/files/f1/download",
                              params={"access_token": "tok"})
        assert response.status_code == 200
        assert response.json()["webContentLink"] == "https://dl"
        gdr.google_drive_service.download_file.assert_awaited_once_with(
            "tok", "f1")

    def test_error_envelope_400(self, client):
        gdr.google_drive_service.download_file.return_value = {
            "status": "error", "message": "Download failed"}
        response = client.get("/google_drive/files/f1/download",
                              params={"access_token": "tok"})
        assert response.status_code == 400

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/google_drive/files/f1/download",
                                   params={"access_token": "tok"})
        assert response.status_code == 401


class TestServiceMockStub:
    def test_mock_client_id(self, anon_client):
        assert gdr.GoogleDriveServiceMock().client_id == "mock_client_id"


class TestHealthCapabilities:
    def test_health(self, anon_client):
        response = anon_client.get("/google_drive/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["service"] == "google_drive"

    def test_capabilities(self, anon_client):
        response = anon_client.get("/google_drive/capabilities")
        assert response.status_code == 200
        body = response.json()
        assert body["service"] == "google_drive"
        assert "file_listing" in body["capabilities"]
        assert "oauth_authentication" in body["capabilities"]
        assert "pdfs" in body["supported_file_types"]
