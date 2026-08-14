"""Coverage wave 100 — integrations/zoom_routes.py (TDD, 0% baseline).

Fully mocked (zoom_auth_handler methods, zoom_service methods, mock-mode
manager), zero network, zero LLM spend.

BUG FOUND + FIXED (TDD RED->GREEN): the data routes (POST /meetings,
GET /meetings, GET /users, GET /recordings) had NO authentication — anyone
could create Zoom meetings / read meetings, users and recordings through the
platform. The anonymous-401 tests below were RED (200) before the fix;
`get_current_user` is now required on every data route. OAuth flow
(/auth/url, /callback) + /status + /health stay public (wave-98 dropbox
convention). Also added the missing generic 500 handler on GET /meetings
(service failures previously leaked an uncaught exception).

Covers: /auth/url (success + failure 500), /callback (success + failure 400),
/status (success + failure 500), /health (mock mode, real healthy, real
unhealthy), POST /meetings (success + re-raise + failure 500 + anon 401 +
422), GET /meetings (success + no-token 401 + failure 500 + anon 401),
/users (success + no-token 401 + failure 500 + anon 401),
/recordings (success + no-token 401 + failure 500 + anon 401).
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi import HTTPException

from core.auth import get_current_user
from core.models import User

from integrations import zoom_routes as zr


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = "zoom100-user"
    u.email = "zoom100@x.com"
    return u


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(zr.router)
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(zr.router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _mocks():
    """Patch every zoom dependency used by the routes."""
    with (
        patch.object(zr.zoom_auth_handler, "get_authorization_url",
                     return_value="https://zoom.us/oauth/authorize?x=1"),
        patch.object(zr.zoom_auth_handler, "exchange_code_for_token",
                     AsyncMock(return_value={"access_token": "at",
                                             "refresh_token": "rt",
                                             "expires_in": 3600})),
        patch.object(zr.zoom_auth_handler, "get_connection_status",
                     return_value={"connected": True,
                                   "has_access_token": True}),
        patch.object(zr.zoom_auth_handler, "ensure_valid_token",
                     AsyncMock(return_value="tok-100")),
        patch.object(zr.zoom_service, "create_meeting",
                     AsyncMock(return_value={"id": "m1", "topic": "t",
                                             "join_url": "https://zoom.us/j/1",
                                             "start_time": "2026-01-01",
                                             "duration": 60})),
        patch.object(zr.zoom_service, "list_meetings",
                     AsyncMock(return_value={"meetings": [{"id": "m1"}],
                                             "total_records": 1,
                                             "page_size": 30})),
        patch.object(zr.zoom_service, "list_users",
                     AsyncMock(return_value={"users": [{"id": "u1"}],
                                             "total_records": 1,
                                             "page_size": 30})),
        patch.object(zr.zoom_service, "list_recordings",
                     AsyncMock(return_value={"meetings": [{"id": "r1"}],
                                             "total_records": 1,
                                             "page_size": 30})),
        patch.object(zr.zoom_service, "health_check",
                     AsyncMock(return_value={"ok": True,
                                             "status": "healthy"})),
    ):
        yield


class TestAuthUrl:
    def test_success(self, anon_client):
        response = anon_client.get("/api/zoom/v1/auth/url",
                                   params={"state": "st-1"})
        assert response.status_code == 200
        body = response.json()
        assert body["url"].startswith("https://zoom.us/oauth/authorize")
        assert "timestamp" in body
        zr.zoom_auth_handler.get_authorization_url.assert_called_with("st-1")

    def test_no_state(self, anon_client):
        response = anon_client.get("/api/zoom/v1/auth/url")
        assert response.status_code == 200

    def test_failure_500(self, anon_client):
        zr.zoom_auth_handler.get_authorization_url.side_effect = \
            RuntimeError("boom")
        response = anon_client.get("/api/zoom/v1/auth/url")
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to generate OAuth URL"


class TestCallback:
    def test_success(self, anon_client):
        response = anon_client.get("/api/zoom/v1/callback",
                                   params={"code": "code-1"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["access_token"] == "at"
        assert body["refresh_token"] == "rt"
        assert body["expires_in"] == 3600

    def test_exchange_failure_400(self, anon_client):
        zr.zoom_auth_handler.exchange_code_for_token.side_effect = \
            RuntimeError("invalid code")
        response = anon_client.get("/api/zoom/v1/callback",
                                   params={"code": "bad"})
        assert response.status_code == 400
        assert response.json()["detail"] == "Internal error"


class TestStatus:
    def test_connected(self, anon_client):
        response = anon_client.get("/api/zoom/v1/status")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["status"] == "connected"
        assert body["user_id"] == "test_user"

    def test_disconnected(self, anon_client):
        zr.zoom_auth_handler.get_connection_status.return_value = {
            "connected": False}
        response = anon_client.get("/api/zoom/v1/status",
                                   params={"user_id": "u2"})
        assert response.status_code == 200
        assert response.json()["status"] == "disconnected"
        assert response.json()["user_id"] == "u2"

    def test_failure_500(self, anon_client):
        zr.zoom_auth_handler.get_connection_status.side_effect = \
            RuntimeError("boom")
        response = anon_client.get("/api/zoom/v1/status")
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to get Zoom status"


class TestHealth:
    def test_mock_mode(self, anon_client):
        mock_manager = MagicMock()
        mock_manager.is_mock_mode.return_value = True
        with patch.object(zr, "get_mock_mode_manager",
                          return_value=mock_manager):
            response = anon_client.get("/api/zoom/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["is_mock"] is True
        mock_manager.is_mock_mode.assert_called_with("zoom", False)

    def test_real_healthy(self, anon_client):
        mock_manager = MagicMock()
        mock_manager.is_mock_mode.return_value = False
        with patch.object(zr, "get_mock_mode_manager",
                          return_value=mock_manager):
            response = anon_client.get("/api/zoom/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["is_mock"] is False
        assert body["status"] == "healthy"
        assert body["oauth_connected"] is True
        assert body["has_access_token"] is True

    def test_health_check_exception_unhealthy(self, anon_client):
        mock_manager = MagicMock()
        mock_manager.is_mock_mode.return_value = False
        zr.zoom_service.health_check.side_effect = RuntimeError("boom")
        with patch.object(zr, "get_mock_mode_manager",
                          return_value=mock_manager):
            response = anon_client.get("/api/zoom/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is False
        assert body["status"] == "unhealthy"
        assert "boom" in body["error"]


class TestCreateMeeting:
    def test_success(self, client):
        response = client.post("/api/zoom/v1/meetings",
                               json={"topic": "Standup"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["meeting_id"] == "m1"
        assert body["topic"] == "t"
        zr.zoom_auth_handler.ensure_valid_token.assert_awaited_once()
        zr.zoom_service.create_meeting.assert_awaited_once()

    def test_full_payload(self, client):
        response = client.post("/api/zoom/v1/meetings", json={
            "topic": "Review", "user_id": "me",
            "start_time": "2026-02-01T10:00:00Z", "duration": 30,
            "timezone": "UTC", "agenda": "sync"})
        assert response.status_code == 200
        zr.zoom_service.create_meeting.assert_awaited_once()
        kwargs = zr.zoom_service.create_meeting.await_args.kwargs
        assert kwargs["duration"] == 30
        assert kwargs["agenda"] == "sync"

    def test_missing_topic_422(self, client):
        response = client.post("/api/zoom/v1/meetings", json={})
        assert response.status_code == 422

    def test_http_exception_re_raised(self, client):
        zr.zoom_service.create_meeting.side_effect = \
            HTTPException(status_code=401, detail="unauthorized")
        response = client.post("/api/zoom/v1/meetings",
                               json={"topic": "Standup"})
        assert response.status_code == 401

    def test_service_failure_500(self, client):
        zr.zoom_service.create_meeting.side_effect = RuntimeError("boom")
        response = client.post("/api/zoom/v1/meetings",
                               json={"topic": "Standup"})
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal error"

    def test_anonymous_401(self, anon_client):
        response = anon_client.post("/api/zoom/v1/meetings",
                                    json={"topic": "Standup"})
        assert response.status_code == 401


class TestListMeetings:
    def test_success(self, client):
        response = client.get("/api/zoom/v1/meetings")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["total"] == 1
        assert body["meetings"][0]["id"] == "m1"

    def test_params_forwarded(self, client):
        response = client.get("/api/zoom/v1/meetings",
                              params={"user_id": "u9", "type": "upcoming",
                                      "page_size": 10})
        assert response.status_code == 200
        kwargs = zr.zoom_service.list_meetings.await_args.kwargs
        assert kwargs["user_id"] == "u9"
        assert kwargs["type"] == "upcoming"
        assert kwargs["page_size"] == 10

    def test_no_token_401(self, client):
        zr.zoom_auth_handler.ensure_valid_token.return_value = None
        response = client.get("/api/zoom/v1/meetings")
        assert response.status_code == 401
        assert "Zoom credentials required" in response.json()["detail"]

    def test_service_failure_500(self, client):
        zr.zoom_service.list_meetings.side_effect = RuntimeError("boom")
        response = client.get("/api/zoom/v1/meetings")
        assert response.status_code == 500

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/api/zoom/v1/meetings")
        assert response.status_code == 401


class TestListUsers:
    def test_success(self, client):
        response = client.get("/api/zoom/v1/users")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["users"][0]["id"] == "u1"
        assert body["total_records"] == 1

    def test_params_forwarded(self, client):
        response = client.get("/api/zoom/v1/users",
                              params={"status": "pending", "page_size": 5})
        assert response.status_code == 200
        kwargs = zr.zoom_service.list_users.await_args.kwargs
        assert kwargs["status"] == "pending"
        assert kwargs["page_size"] == 5

    def test_no_token_401(self, client):
        zr.zoom_auth_handler.ensure_valid_token.return_value = None
        response = client.get("/api/zoom/v1/users")
        assert response.status_code == 401

    def test_service_failure_500(self, client):
        zr.zoom_service.list_users.side_effect = RuntimeError("boom")
        response = client.get("/api/zoom/v1/users")
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal error"

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/api/zoom/v1/users")
        assert response.status_code == 401


class TestListRecordings:
    def test_success(self, client):
        response = client.get("/api/zoom/v1/recordings")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["recordings"][0]["id"] == "r1"
        assert body["total_records"] == 1

    def test_params_forwarded(self, client):
        response = client.get(
            "/api/zoom/v1/recordings",
            params={"user_id": "u9", "from_date": "2026-01-01",
                    "to_date": "2026-02-01", "page_size": 7})
        assert response.status_code == 200
        kwargs = zr.zoom_service.list_recordings.await_args.kwargs
        assert kwargs["from_date"] == "2026-01-01"
        assert kwargs["to_date"] == "2026-02-01"

    def test_no_token_401(self, client):
        zr.zoom_auth_handler.ensure_valid_token.return_value = None
        response = client.get("/api/zoom/v1/recordings")
        assert response.status_code == 401

    def test_service_failure_500(self, client):
        zr.zoom_service.list_recordings.side_effect = RuntimeError("boom")
        response = client.get("/api/zoom/v1/recordings")
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal error"

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/api/zoom/v1/recordings")
        assert response.status_code == 401
