"""Coverage wave 102 — integrations/onedrive_routes.py (TDD, 0% baseline).

Fully mocked (OneDriveService methods patched on the module singleton, fake
get_current_user), zero network, zero LLM spend.

BUG FOUND + FIXED (TDD RED->GREEN): the data endpoints GET /files,
POST /search, GET /files/{file_id} and GET /files/{file_id}/download had NO
authentication — anonymous users could list/search/read/download any file in
the tenant's OneDrive reachable via a leaked access_token. The anonymous-401
tests below were RED (200) before the fix; `get_current_user` is now required
on all four. (/auth, /health and /capabilities stay public, matching the
wave-93 dropbox OAuth-flow convention.)

Covers: /auth (success, error envelope -> 400, missing user_id -> 422),
/files (success, error envelope -> 400, anon 401), /search (success, error
envelope -> 400, anon 401), /files/{file_id} (success, error -> 400, anon
401), /files/{file_id}/download (success, error -> 400, anon 401), /health,
/capabilities.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.models import User

from integrations import onedrive_routes as odr

FILE_DATA = {"value": [{"id": "f1", "name": "report.xlsx"}], "nextLink": None}


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = "od102-user"
    u.email = "od102@x.com"
    return u


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(odr.onedrive_router)
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(odr.onedrive_router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _svc():
    with patch.object(odr.onedrive_service, "authenticate",
                      new=AsyncMock(
                          return_value={"status": "success",
                                        "auth_url": "https://login/auth",
                                        "state": "onedrive_u1"})), \
            patch.object(odr.onedrive_service, "list_files",
                         new=AsyncMock(return_value={"status": "success",
                                                     "data": FILE_DATA})), \
            patch.object(odr.onedrive_service, "search_files",
                         new=AsyncMock(return_value={"status": "success",
                                                     "data": FILE_DATA})), \
            patch.object(odr.onedrive_service, "get_file_metadata",
                         new=AsyncMock(
                             return_value={"status": "success",
                                           "data": {"id": "f1",
                                                    "name": "report.xlsx"}})), \
            patch.object(odr.onedrive_service, "download_file",
                         new=AsyncMock(
                             return_value={"status": "success",
                                           "data": {"@microsoft.graph.downloadUrl":
                                                    "https://dl"}})):
        yield odr.onedrive_service


class TestAuth:
    def test_success(self, anon_client):
        response = anon_client.get("/onedrive/auth", params={"user_id": "u1"})
        assert response.status_code == 200
        body = response.json()
        assert body["auth_url"] == "https://login/auth"
        assert body["state"] == "onedrive_u1"
        odr.onedrive_service.authenticate.assert_awaited_once_with("u1")

    def test_error_envelope_400(self, anon_client):
        odr.onedrive_service.authenticate.return_value = {
            "status": "error", "message": "MICROSOFT_CLIENT_ID not configured"}
        response = anon_client.get("/onedrive/auth", params={"user_id": "u1"})
        assert response.status_code == 400
        assert response.json()["detail"] == \
            "MICROSOFT_CLIENT_ID not configured"

    def test_missing_user_id_422(self, anon_client):
        response = anon_client.get("/onedrive/auth")
        assert response.status_code == 422


class TestListFiles:
    def test_success(self, client):
        response = client.get("/onedrive/files",
                              params={"access_token": "tok",
                                      "folder_id": "folder1",
                                      "page_size": 50, "page_token": "pg1"})
        assert response.status_code == 200
        body = response.json()
        assert body["value"][0]["id"] == "f1"
        assert body["value"][0]["name"] == "report.xlsx"
        assert body["nextLink"] is None
        odr.onedrive_service.list_files.assert_awaited_once_with(
            "tok", "folder1", 50, "pg1")

    def test_success_defaults(self, client):
        response = client.get("/onedrive/files",
                              params={"access_token": "tok"})
        assert response.status_code == 200
        odr.onedrive_service.list_files.assert_awaited_once_with(
            "tok", None, 100, None)

    def test_error_envelope_400(self, client):
        odr.onedrive_service.list_files.return_value = {
            "status": "error", "message": "No access token provided"}
        response = client.get("/onedrive/files",
                              params={"access_token": "tok"})
        assert response.status_code == 400
        assert response.json()["detail"] == "No access token provided"

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/onedrive/files",
                                   params={"access_token": "tok"})
        assert response.status_code == 401


class TestSearch:
    def test_success(self, client):
        response = client.post(
            "/onedrive/search",
            params={"access_token": "tok"},
            json={"query": "invoice", "pageSize": 20, "pageToken": "pg"})
        assert response.status_code == 200
        body = response.json()
        assert body["value"][0]["id"] == "f1"
        assert body["value"][0]["name"] == "report.xlsx"
        odr.onedrive_service.search_files.assert_awaited_once_with(
            "tok", "invoice", 20, "pg")

    def test_error_envelope_400(self, client):
        odr.onedrive_service.search_files.return_value = {
            "status": "error", "message": "No access token provided"}
        response = client.post("/onedrive/search",
                               params={"access_token": "tok"},
                               json={"query": "invoice"})
        assert response.status_code == 400

    def test_missing_query_422(self, client):
        response = client.post("/onedrive/search",
                               params={"access_token": "tok"}, json={})
        assert response.status_code == 422

    def test_anonymous_401(self, anon_client):
        response = anon_client.post("/onedrive/search",
                                    params={"access_token": "tok"},
                                    json={"query": "invoice"})
        assert response.status_code == 401


class TestGetFileMetadata:
    def test_success(self, client):
        response = client.get("/onedrive/files/f1",
                              params={"access_token": "tok"})
        assert response.status_code == 200
        assert response.json()["id"] == "f1"
        odr.onedrive_service.get_file_metadata.assert_awaited_once_with(
            "tok", "f1")

    def test_error_envelope_400(self, client):
        odr.onedrive_service.get_file_metadata.return_value = {
            "status": "error", "message": "File not found"}
        response = client.get("/onedrive/files/missing",
                              params={"access_token": "tok"})
        assert response.status_code == 400
        assert response.json()["detail"] == "File not found"

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/onedrive/files/f1",
                                   params={"access_token": "tok"})
        assert response.status_code == 401


class TestDownload:
    def test_success(self, client):
        response = client.get("/onedrive/files/f1/download",
                              params={"access_token": "tok"})
        assert response.status_code == 200
        assert response.json()["@microsoft.graph.downloadUrl"] == "https://dl"
        odr.onedrive_service.download_file.assert_awaited_once_with(
            "tok", "f1")

    def test_error_envelope_400(self, client):
        odr.onedrive_service.download_file.return_value = {
            "status": "error", "message": "Download failed"}
        response = client.get("/onedrive/files/f1/download",
                              params={"access_token": "tok"})
        assert response.status_code == 400

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/onedrive/files/f1/download",
                                   params={"access_token": "tok"})
        assert response.status_code == 401


class TestServiceMockStub:
    def test_mock_client_id(self, anon_client):
        assert odr.OneDriveServiceMock().client_id == "mock_client_id"


class TestHealthCapabilities:
    def test_health(self, anon_client):
        response = anon_client.get("/onedrive/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["service"] == "onedrive"

    def test_capabilities(self, anon_client):
        response = anon_client.get("/onedrive/capabilities")
        assert response.status_code == 200
        body = response.json()
        assert body["service"] == "onedrive"
        assert "file_listing" in body["capabilities"]
        assert "file_download" in body["capabilities"]
        assert "documents" in body["supported_file_types"]
