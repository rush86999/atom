"""Coverage wave 100 — integrations/microsoft365_routes.py (TDD, 0% baseline).

Fully mocked (Microsoft365Service methods), zero network, zero LLM spend.

BUG FOUND + FIXED (TDD RED->GREEN): every data route (/user, /teams,
/teams/{id}/channels, /outlook/messages, /calendar/events,
/services/status, DELETE /outlook/messages/{id}, DELETE
/calendar/events/{id}, /excel|/teams|/outlook|/onedrive /execute,
DELETE /files/{id}, DELETE /teams/{id}/channels/{id}/messages/{id},
POST /subscriptions) had NO authentication — anyone holding a leaked MS
Graph access token could read mail/calendar/teams and delete items through
the platform. The anonymous-401 tests below were RED (200) before the fix;
`get_current_user` is now required on every data route (matching the
router-level auth the sibling microsoft365_service router already has).
/health, /capabilities and /webhook (external Graph validation-token
handshake) stay public per the wave-98 convention.

Covers: every route x {success, error -> 400, anon 401, 422 as applicable},
webhook validationToken plaintext handshake + notification payload.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.models import User

from integrations import microsoft365_routes as mr


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = "m365-user"
    u.email = "m365@x.com"
    return u


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(mr.microsoft365_router)
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(mr.microsoft365_router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _svc():
    """Patch every Microsoft365Service method used by the routes."""
    with patch.multiple(
        mr.microsoft365_service,
        authenticate=AsyncMock(return_value={
            "status": "success", "auth_url": "https://login.microsoftonline"
            ".com/common/oauth2/v2.0/authorize?x=1", "state": "st-1"}),
        get_user_profile=AsyncMock(return_value={
            "status": "success",
            "data": {"id": "u1", "displayName": "Ada",
                     "mail": "ada@x.com", "userPrincipalName": "ada@x.com"}}),
        list_teams=AsyncMock(return_value={
            "status": "success", "data": {"value": [{"id": "t1"}]}}),
        list_channels=AsyncMock(return_value={
            "status": "success", "data": {"value": [{"id": "c1"}]}}),
        get_outlook_messages=AsyncMock(return_value={
            "status": "success", "data": {"value": [{"id": "msg1"}]}}),
        get_calendar_events=AsyncMock(return_value={
            "status": "success", "data": {"value": [{"id": "ev1"}]}}),
        get_service_status=AsyncMock(return_value={
            "status": "success", "data": {"status": "healthy"}}),
        delete_item=AsyncMock(return_value={
            "status": "success", "data": {}}),
        create_subscription=AsyncMock(return_value={
            "status": "success", "data": {"id": "sub1"}}),
        execute_excel_action=AsyncMock(return_value={
            "status": "success", "data": {"done": True}}),
        execute_teams_action=AsyncMock(return_value={
            "status": "success", "data": {"done": True}}),
        execute_outlook_action=AsyncMock(return_value={
            "status": "success", "data": {"done": True}}),
        execute_onedrive_action=AsyncMock(return_value={
            "status": "success", "data": {"done": True}}),
    ):
        yield mr.microsoft365_service


def _auth_q(token="tok-100"):
    return {"access_token": token}


class TestAuth:
    def test_success(self, anon_client):
        response = anon_client.get("/auth", params={"user_id": "u1"})
        assert response.status_code == 200
        body = response.json()
        assert body["auth_url"].startswith("https://login.microsoftonline")
        assert body["state"] == "st-1"
        mr.microsoft365_service.authenticate.assert_awaited_once_with("u1")

    def test_error_400(self, anon_client):
        mr.microsoft365_service.authenticate.return_value = {
            "status": "error", "message": "Auth failed"}
        response = anon_client.get("/auth", params={"user_id": "u1"})
        assert response.status_code == 400
        assert response.json()["detail"] == "Auth failed"

    def test_missing_user_id_422(self, anon_client):
        response = anon_client.get("/auth")
        assert response.status_code == 422


class TestUserProfile:
    def test_success(self, client):
        response = client.get("/user", params=_auth_q())
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == "u1"
        assert body["displayName"] == "Ada"
        assert body["mail"] == "ada@x.com"

    def test_error_400(self, client):
        mr.microsoft365_service.get_user_profile.return_value = {
            "status": "error", "message": "bad token"}
        response = client.get("/user", params=_auth_q())
        assert response.status_code == 400
        assert response.json()["detail"] == "bad token"

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/user", params=_auth_q())
        assert response.status_code == 401


class TestTeams:
    def test_list_success(self, client):
        response = client.get("/teams", params=_auth_q())
        assert response.status_code == 200
        assert response.json()["teams"] == [{"id": "t1"}]

    def test_list_error_400(self, client):
        mr.microsoft365_service.list_teams.return_value = {
            "status": "error", "message": "denied"}
        response = client.get("/teams", params=_auth_q())
        assert response.status_code == 400

    def test_list_anonymous_401(self, anon_client):
        response = anon_client.get("/teams", params=_auth_q())
        assert response.status_code == 401

    def test_channels_success(self, client):
        response = client.get("/teams/t1/channels", params=_auth_q())
        assert response.status_code == 200
        assert response.json()["channels"] == [{"id": "c1"}]
        mr.microsoft365_service.list_channels.assert_awaited_once_with(
            "tok-100", "t1")

    def test_channels_error_400(self, client):
        mr.microsoft365_service.list_channels.return_value = {
            "status": "error", "message": "no team"}
        response = client.get("/teams/nope/channels", params=_auth_q())
        assert response.status_code == 400

    def test_channels_anonymous_401(self, anon_client):
        response = anon_client.get("/teams/t1/channels", params=_auth_q())
        assert response.status_code == 401


class TestOutlookMessages:
    def test_success_defaults(self, client):
        response = client.get("/outlook/messages", params=_auth_q())
        assert response.status_code == 200
        assert response.json()["messages"] == [{"id": "msg1"}]
        mr.microsoft365_service.get_outlook_messages.assert_awaited_once_with(
            "tok-100", "inbox", 10)

    def test_success_params(self, client):
        response = client.get("/outlook/messages",
                              params={**_auth_q(), "folder_id": "sent",
                                      "top": 25})
        assert response.status_code == 200
        mr.microsoft365_service.get_outlook_messages.assert_awaited_once_with(
            "tok-100", "sent", 25)

    def test_error_400(self, client):
        mr.microsoft365_service.get_outlook_messages.return_value = {
            "status": "error", "message": "graph down"}
        response = client.get("/outlook/messages", params=_auth_q())
        assert response.status_code == 400

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/outlook/messages", params=_auth_q())
        assert response.status_code == 401


class TestCalendar:
    def test_success(self, client):
        response = client.get("/calendar/events",
                              params={**_auth_q(),
                                      "start_date": "2026-01-01",
                                      "end_date": "2026-01-31"})
        assert response.status_code == 200
        assert response.json()["events"] == [{"id": "ev1"}]
        mr.microsoft365_service.get_calendar_events.assert_awaited_once_with(
            "tok-100", "2026-01-01", "2026-01-31")

    def test_missing_dates_422(self, client):
        response = client.get("/calendar/events", params=_auth_q())
        assert response.status_code == 422

    def test_error_400(self, client):
        mr.microsoft365_service.get_calendar_events.return_value = {
            "status": "error", "message": "bad range"}
        response = client.get("/calendar/events",
                              params={**_auth_q(),
                                      "start_date": "2026-01-01",
                                      "end_date": "2026-01-31"})
        assert response.status_code == 400

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/calendar/events",
                                   params={**_auth_q(),
                                           "start_date": "2026-01-01",
                                           "end_date": "2026-01-31"})
        assert response.status_code == 401


class TestServiceStatus:
    def test_success(self, client):
        response = client.get("/services/status", params=_auth_q())
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_error_400(self, client):
        mr.microsoft365_service.get_service_status.return_value = {
            "status": "error", "message": "outage"}
        response = client.get("/services/status", params=_auth_q())
        assert response.status_code == 400

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/services/status", params=_auth_q())
        assert response.status_code == 401


class TestHealthCapabilities:
    def test_health(self, anon_client):
        response = anon_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        assert response.json()["service"] == "microsoft365"

    def test_capabilities(self, anon_client):
        response = anon_client.get("/capabilities")
        assert response.status_code == 200
        body = response.json()
        assert "teams_integration" in body["capabilities"]
        assert "microsoft_graph" in body["supported_services"]

    def test_mock_placeholder_class(self):
        """Legacy Microsoft365ServiceMock placeholder still constructs."""
        mock_svc = mr.Microsoft365ServiceMock()
        assert mock_svc.client_id == "mock_client_id"


class TestDeleteMessage:
    def test_success(self, client):
        response = client.delete("/outlook/messages/msg9", params=_auth_q())
        assert response.status_code == 200
        assert response.json()["message"] == "Message deleted"
        mr.microsoft365_service.delete_item.assert_awaited_once()
        assert mr.microsoft365_service.delete_item.await_args.args[1] \
            == "message"

    def test_error_400(self, client):
        mr.microsoft365_service.delete_item.return_value = {
            "status": "error", "message": "not found"}
        response = client.delete("/outlook/messages/msg9", params=_auth_q())
        assert response.status_code == 400

    def test_anonymous_401(self, anon_client):
        response = anon_client.delete("/outlook/messages/msg9",
                                      params=_auth_q())
        assert response.status_code == 401


class TestDeleteEvent:
    def test_success(self, client):
        response = client.delete("/calendar/events/ev9", params=_auth_q())
        assert response.status_code == 200
        assert response.json()["message"] == "Event deleted"

    def test_error_400(self, client):
        mr.microsoft365_service.delete_item.return_value = {
            "status": "error", "message": "gone"}
        response = client.delete("/calendar/events/ev9", params=_auth_q())
        assert response.status_code == 400

    def test_anonymous_401(self, anon_client):
        response = anon_client.delete("/calendar/events/ev9",
                                      params=_auth_q())
        assert response.status_code == 401


class TestExecuteActions:
    @pytest.mark.parametrize("path,method", [
        ("/excel/execute", "execute_excel_action"),
        ("/teams/execute", "execute_teams_action"),
        ("/outlook/execute", "execute_outlook_action"),
        ("/onedrive/execute", "execute_onedrive_action"),
    ])
    def test_success(self, client, path, method):
        response = client.post(path, json={"action": "list"},
                               params=_auth_q())
        assert response.status_code == 200
        getattr(mr.microsoft365_service, method).assert_awaited_once_with(
            "tok-100", "list", {})

    @pytest.mark.parametrize("path", [
        "/excel/execute", "/teams/execute",
        "/outlook/execute", "/onedrive/execute",
    ])
    def test_anonymous_401(self, anon_client, path):
        response = anon_client.post(path, json={"action": "list"},
                                    params=_auth_q())
        assert response.status_code == 401

    def test_params_forwarded(self, client):
        response = client.post(
            "/teams/execute",
            json={"action": "send", "params": {"channel": "general"}},
            params=_auth_q())
        assert response.status_code == 200
        mr.microsoft365_service.execute_teams_action.assert_awaited_once_with(
            "tok-100", "send", {"channel": "general"})

    def test_422(self, client):
        response = client.post("/excel/execute", json={},
                               params=_auth_q())
        assert response.status_code == 422


class TestDeleteFile:
    def test_success(self, client):
        response = client.delete("/files/f1", params=_auth_q())
        assert response.status_code == 200
        assert response.json()["message"] == "File deleted"
        assert mr.microsoft365_service.delete_item.await_args.args[1] \
            == "file"

    def test_error_400(self, client):
        mr.microsoft365_service.delete_item.return_value = {
            "status": "error", "message": "no file"}
        response = client.delete("/files/f1", params=_auth_q())
        assert response.status_code == 400

    def test_anonymous_401(self, anon_client):
        response = anon_client.delete("/files/f1", params=_auth_q())
        assert response.status_code == 401


class TestDeleteTeamMessage:
    def test_success(self, client):
        response = client.delete(
            "/teams/t1/channels/c1/messages/m1", params=_auth_q())
        assert response.status_code == 200
        assert response.json()["message"] == "Message deleted"
        call = mr.microsoft365_service.delete_item.await_args
        assert call.args[1] == "team_message"
        assert call.kwargs["params"] == {"team_id": "t1",
                                         "channel_id": "c1"}

    def test_error_400(self, client):
        mr.microsoft365_service.delete_item.return_value = {
            "status": "error", "message": "denied"}
        response = client.delete(
            "/teams/t1/channels/c1/messages/m1", params=_auth_q())
        assert response.status_code == 400

    def test_anonymous_401(self, anon_client):
        response = anon_client.delete(
            "/teams/t1/channels/c1/messages/m1", params=_auth_q())
        assert response.status_code == 401


class TestSubscriptions:
    def test_success(self, client):
        response = client.post("/subscriptions", json={
            "resource": "me/messages", "changeType": "created",
            "notificationUrl": "https://hooks.example.com/m365",
            "expirationDateTime": "2026-02-01T00:00:00Z"},
            params=_auth_q())
        assert response.status_code == 200
        assert response.json()["id"] == "sub1"
        mr.microsoft365_service.create_subscription.assert_awaited_once_with(
            "tok-100", "me/messages", "created",
            "https://hooks.example.com/m365", "2026-02-01T00:00:00Z")

    def test_error_400(self, client):
        mr.microsoft365_service.create_subscription.return_value = {
            "status": "error", "message": "bad url"}
        response = client.post("/subscriptions", json={
            "resource": "me/messages", "changeType": "created",
            "notificationUrl": "https://hooks.example.com/m365",
            "expirationDateTime": "2026-02-01T00:00:00Z"},
            params=_auth_q())
        assert response.status_code == 400

    def test_422(self, client):
        response = client.post("/subscriptions", json={},
                               params=_auth_q())
        assert response.status_code == 422

    def test_anonymous_401(self, anon_client):
        response = anon_client.post("/subscriptions", json={
            "resource": "me/messages", "changeType": "created",
            "notificationUrl": "https://hooks.example.com/m365",
            "expirationDateTime": "2026-02-01T00:00:00Z"},
            params=_auth_q())
        assert response.status_code == 401


class TestWebhook:
    def test_validation_token_plaintext(self, anon_client):
        response = anon_client.post(
            "/webhook", params={"validationToken": "validate-abc"},
            content=b'{"a": 1}')
        assert response.status_code == 200
        assert response.text == "validate-abc"

    def test_notification_payload(self, anon_client):
        response = anon_client.post(
            "/webhook", json={"value": [{"id": "n1"}]})
        assert response.status_code == 200
        assert response.json() == {"status": "received"}
