"""Coverage wave 102 — integrations/box_routes.py (TDD, 0% baseline).

Fully mocked (box_service methods patched on the module singleton, fake
get_current_user), zero network, zero LLM spend.

BUG FOUND + FIXED (TDD RED->GREEN): the data/action endpoints
GET /files, GET /files/{file_id}, GET /download/{file_id}, POST /folders and
POST /search had NO authentication — anonymous users could read any Box
folder/file content reachable via a leaked access_token, create folders, and
search the account. The anonymous-401 tests below were RED (200) before the
fix; `get_current_user` is now required on all five. (/auth/url, /status and
/health stay public, matching the wave-93 dropbox convention.)

Covers: /auth/url (success, service failure -> 500), /files (success,
service failure -> 500, anon 401, limit 422 ge/le), /files/{file_id}
(success, 500, anon 401), /download/{file_id} (success, 500, anon 401),
/folders (success + defaults, 500, missing folder_name -> 422, anon 401),
/search (success with defaults, 500, anon 401), /status, /health.
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.models import User

from integrations import box_routes as br


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = "box102-user"
    u.email = "box102@x.com"
    return u


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(br.router)
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(br.router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _svc():
    with patch.object(br.box_service, "authenticate",
                      new=AsyncMock(return_value={"auth_url": "https://box/auth"})), \
            patch.object(br.box_service, "list_files",
                         new=AsyncMock(return_value=[{"id": "f1"}])), \
            patch.object(br.box_service, "get_file_metadata",
                         new=AsyncMock(return_value={"id": "f1", "name": "a.txt"})), \
            patch.object(br.box_service, "download_file",
                         new=AsyncMock(return_value={"download_url": "https://dl"})), \
            patch.object(br.box_service, "create_folder",
                         new=AsyncMock(return_value={"id": "folder1"})), \
            patch.object(br.box_service, "search_files",
                         new=AsyncMock(return_value=[{"id": "f2"}])):
        yield br.box_service


class TestAuthUrl:
    def test_success(self, anon_client):
        response = anon_client.get("/api/box/auth/url", params={"user_id": "u1"})
        assert response.status_code == 200
        body = response.json()
        assert body["url"] == "https://box/auth"
        assert "timestamp" in body

    def test_default_user_id(self, anon_client):
        response = anon_client.get("/api/box/auth/url")
        assert response.status_code == 200
        br.box_service.authenticate.assert_awaited_once_with("default")

    def test_service_failure_500(self, anon_client):
        br.box_service.authenticate.side_effect = RuntimeError("boom")
        response = anon_client.get("/api/box/auth/url")
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal error"


class TestListFiles:
    def test_success(self, client):
        response = client.get(
            "/api/box/files",
            params={"access_token": "tok", "folder_id": "123",
                    "limit": 50, "offset": 10})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["files"] == [{"id": "f1"}]
        assert "timestamp" in body
        br.box_service.list_files.assert_awaited_once_with("tok", "123", 50, 10)

    def test_success_defaults(self, client):
        response = client.get("/api/box/files", params={"access_token": "tok"})
        assert response.status_code == 200
        br.box_service.list_files.assert_awaited_once_with("tok", "0", 100, 0)

    def test_service_failure_500(self, client):
        br.box_service.list_files.side_effect = HTTPException(
            status_code=502, detail="upstream")
        response = client.get("/api/box/files", params={"access_token": "tok"})
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal error"

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/api/box/files",
                                   params={"access_token": "tok"})
        assert response.status_code == 401

    def test_limit_validation_422(self, client):
        response = client.get("/api/box/files",
                              params={"access_token": "tok", "limit": 0})
        assert response.status_code == 422

    def test_limit_too_high_422(self, client):
        response = client.get("/api/box/files",
                              params={"access_token": "tok", "limit": 1001})
        assert response.status_code == 422

    def test_missing_access_token_422(self, client):
        response = client.get("/api/box/files")
        assert response.status_code == 422


class TestGetFileMetadata:
    def test_success(self, client):
        response = client.get("/api/box/files/f1",
                              params={"access_token": "tok"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["file"]["id"] == "f1"
        br.box_service.get_file_metadata.assert_awaited_once_with("tok", "f1")

    def test_service_failure_500(self, client):
        br.box_service.get_file_metadata.side_effect = RuntimeError("boom")
        response = client.get("/api/box/files/f1",
                              params={"access_token": "tok"})
        assert response.status_code == 500

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/api/box/files/f1",
                                   params={"access_token": "tok"})
        assert response.status_code == 401


class TestDownload:
    def test_success(self, client):
        response = client.get("/api/box/download/f1",
                              params={"access_token": "tok"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["download_url"] == "https://dl"
        br.box_service.download_file.assert_awaited_once_with("tok", "f1")

    def test_service_failure_500(self, client):
        br.box_service.download_file.side_effect = RuntimeError("boom")
        response = client.get("/api/box/download/f1",
                              params={"access_token": "tok"})
        assert response.status_code == 500

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/api/box/download/f1",
                                   params={"access_token": "tok"})
        assert response.status_code == 401


class TestCreateFolder:
    def test_success(self, client):
        response = client.post(
            "/api/box/folders",
            params={"access_token": "tok", "folder_name": "New"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["folder"] == {"id": "folder1"}
        br.box_service.create_folder.assert_awaited_once_with(
            "tok", "0", "New")

    def test_service_failure_500(self, client):
        br.box_service.create_folder.side_effect = RuntimeError("boom")
        response = client.post(
            "/api/box/folders",
            params={"access_token": "tok", "folder_name": "New"})
        assert response.status_code == 500

    def test_missing_folder_name_422(self, client):
        response = client.post("/api/box/folders",
                               params={"access_token": "tok"})
        assert response.status_code == 422

    def test_anonymous_401(self, anon_client):
        response = anon_client.post(
            "/api/box/folders",
            params={"access_token": "tok", "folder_name": "New"})
        assert response.status_code == 401


class TestSearch:
    def test_success(self, client):
        response = client.post(
            "/api/box/search",
            params={"access_token": "tok"},
            json={"query": "invoice", "limit": 25, "offset": 5})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["results"] == [{"id": "f2"}]
        assert body["query"] == "invoice"
        br.box_service.search_files.assert_awaited_once_with("tok", "invoice", 25, 5)

    def test_success_defaults(self, client):
        response = client.post(
            "/api/box/search",
            params={"access_token": "tok"},
            json={"query": "invoice"})
        assert response.status_code == 200
        br.box_service.search_files.assert_awaited_once_with("tok", "invoice", 100, 0)

    def test_service_failure_500(self, client):
        br.box_service.search_files.side_effect = RuntimeError("boom")
        response = client.post(
            "/api/box/search",
            params={"access_token": "tok"},
            json={"query": "invoice"})
        assert response.status_code == 500

    def test_missing_query_422(self, client):
        response = client.post("/api/box/search", params={"access_token": "tok"},
                               json={})
        assert response.status_code == 422

    def test_anonymous_401(self, anon_client):
        response = anon_client.post(
            "/api/box/search",
            params={"access_token": "tok"},
            json={"query": "invoice"})
        assert response.status_code == 401


class TestStatusHealth:
    def test_status(self, anon_client):
        response = anon_client.get("/api/box/status")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["status"] == "connected"
        assert body["service"] == "box"

    def test_status_user_id(self, anon_client):
        response = anon_client.get("/api/box/status?user_id=u1")
        assert response.json()["user_id"] == "u1"

    def test_health(self, anon_client):
        response = anon_client.get("/api/box/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert "files" in body["capabilities"]
