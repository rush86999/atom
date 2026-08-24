"""Coverage-push + bug-hunt tests for Google Calendar/Drive services and Gmail/Email routes."""

import base64
import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from integrations.gmail_routes import router as gmail_router
from integrations.email_routes import router as email_router

TESTAPP = FastAPI()
TESTAPP.include_router(gmail_router)
TESTAPP.include_router(email_router)


# ---------------------------------------------------------------------------
# gmail_routes
# ---------------------------------------------------------------------------

class TestGmailRoutes:
    def test_auth_url(self):
        with TestClient(TESTAPP) as c:
            r = c.get("/api/gmail/auth/url")
        assert r.status_code == 200
        assert "accounts.google.com" in r.json()["url"]
        assert "timestamp" in r.json()

    def test_callback(self):
        with TestClient(TESTAPP) as c:
            r = c.get("/api/gmail/callback?code=secretcode")
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["code"] == "secretcode"

    def test_status_default_user(self):
        with TestClient(TESTAPP) as c:
            r = c.get("/api/gmail/status")
        assert r.status_code == 200
        data = r.json()
        assert data["service"] == "gmail"
        assert data["user_id"] == "test_user"
        assert data["status"] == "connected"

    def test_status_custom_user(self):
        with TestClient(TESTAPP) as c:
            r = c.get("/api/gmail/status?user_id=alice")
        assert r.status_code == 200
        assert r.json()["user_id"] == "alice"

    def test_health(self):
        with TestClient(TESTAPP) as c:
            r = c.get("/api/gmail/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_search_default_max_results(self):
        with TestClient(TESTAPP) as c:
            r = c.post("/api/gmail/search", json={"query": "invoices"})
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["total_results"] == 10
        assert len(data["results"]) == 10
        assert data["results"][0]["subject"].startswith("Email about invoices")

    def test_search_custom_max_results(self):
        with TestClient(TESTAPP) as c:
            r = c.post("/api/gmail/search", json={"query": "receipts", "max_results": 3})
        assert r.status_code == 200
        data = r.json()
        assert data["total_results"] == 3
        assert len(data["results"]) == 3

    def test_search_missing_query_422(self):
        with TestClient(TESTAPP) as c:
            r = c.post("/api/gmail/search", json={})
        assert r.status_code == 422

    def test_search_zero_max_results_rejected(self):
        with TestClient(TESTAPP) as c:
            r = c.post("/api/gmail/search", json={"query": "x", "max_results": 0})
        assert r.status_code == 422

    def test_search_huge_max_results_rejected(self):
        with TestClient(TESTAPP) as c:
            r = c.post("/api/gmail/search", json={"query": "x", "max_results": 1000000})
        assert r.status_code == 422

    def test_communication_intelligence_imports_exist(self):
        from integrations.gmail_routes import create_gmail_draft, send_gmail_message
        assert callable(create_gmail_draft)
        assert callable(send_gmail_message)

    async def test_create_gmail_draft(self):
        from integrations.gmail_routes import create_gmail_draft
        draft_id = await create_gmail_draft(user_id="u1", thread_id="t1", body="hello")
        assert isinstance(draft_id, str)
        assert draft_id.startswith("draft_")

    async def test_send_gmail_message(self):
        from integrations.gmail_routes import send_gmail_message
        result = await send_gmail_message(user_id="u1", thread_id="t1", body="hello")
        assert result["ok"] is True
        assert result["user_id"] == "u1"
        assert result["thread_id"] == "t1"


# ---------------------------------------------------------------------------
# email_routes
# ---------------------------------------------------------------------------

class TestEmailRoutes:
    def test_auth_url(self):
        with TestClient(TESTAPP) as c:
            r = c.get("/api/email/auth/url")
        assert r.status_code == 200
        assert r.json()["url"] == "/api/email/health"

    def test_callback(self):
        with TestClient(TESTAPP) as c:
            r = c.get("/api/email/callback")
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_health_default_provider(self):
        with TestClient(TESTAPP) as c:
            r = c.get("/api/email/health")
        assert r.status_code == 200
        data = r.json()
        assert data["service"] == "email"
        assert data["provider"] == "gmail"
        assert data["status"] == "connected"

    def test_health_custom_provider(self):
        with TestClient(TESTAPP) as c:
            r = c.get("/api/email/health?provider=outlook")
        assert r.status_code == 200
        assert r.json()["provider"] == "outlook"

    def test_send_email_full(self):
        with TestClient(TESTAPP) as c:
            r = c.post(
                "/api/email/send",
                json={"to": "bob@example.com", "subject": "Hi", "body": "Body", "provider": "gmail"},
            )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["to"] == "bob@example.com"
        assert data["subject"] == "Hi"
        assert data["provider"] == "gmail"
        assert data["message_id"].startswith("email_")

    def test_send_email_defaults(self):
        with TestClient(TESTAPP) as c:
            r = c.post("/api/email/send", json={})
        assert r.status_code == 200
        data = r.json()
        assert data["provider"] == "gmail"
        assert data["to"] == ""

    def test_send_email_outlook_provider(self):
        with TestClient(TESTAPP) as c:
            r = c.post("/api/email/send", json={"provider": "outlook", "to": "x@y.z"})
        assert r.status_code == 200
        assert r.json()["provider"] == "outlook"

    def test_send_email_non_dict_422(self):
        with TestClient(TESTAPP) as c:
            r = c.post("/api/email/send", json=[1, 2, 3])
        assert r.status_code == 422

    def test_list_emails_default(self):
        with TestClient(TESTAPP) as c:
            r = c.get("/api/email/messages")
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["total"] == 0
        assert data["limit"] == 10

    def test_list_emails_custom_limit(self):
        with TestClient(TESTAPP) as c:
            r = c.get("/api/email/messages?limit=5")
        assert r.status_code == 200
        assert r.json()["limit"] == 5

    def test_email_service_singleton(self):
        from integrations.email_routes import EmailService, email_service
        assert email_service.provider == "internal"
        result = asyncio_run(email_service.send_email("to", "subj", "body"))
        assert "message_id" in result


# ---------------------------------------------------------------------------
# google_calendar_service
# ---------------------------------------------------------------------------

class _BoomError(Exception):
    pass


def _calendar_svc(tmp_path=None):
    from integrations.google_calendar_service import GoogleCalendarService

    token_file = str(tmp_path / "token.json") if tmp_path else "/nonexistent/token.json"
    return GoogleCalendarService("default", {"token_file": token_file})


def _fake_service_for(svc, events_result=None):
    service = MagicMock()
    events = service.events().list().execute
    events.return_value = events_result if events_result is not None else {"items": []}
    return service


class TestGoogleCalendarServiceInit:
    def test_init_defaults(self, tmp_path):
        from integrations.google_calendar_service import GoogleCalendarService

        svc = GoogleCalendarService()
        assert svc.tenant_id == "default"
        assert svc.credentials_json is None
        assert svc.token_file == "token.json"
        assert svc.service is None
        assert svc.creds is None

    def test_init_with_config(self, tmp_path):
        from integrations.google_calendar_service import GoogleCalendarService

        svc = GoogleCalendarService("tenant-1", {"credentials_json": "{}", "token_file": "tok.json"})
        assert svc.tenant_id == "tenant-1"
        assert svc.credentials_json == "{}"
        assert svc.token_file == "tok.json"

    def test_init_credentials_from_env(self, tmp_path, monkeypatch):
        from integrations.google_calendar_service import GoogleCalendarService

        monkeypatch.setenv("GOOGLE_CALENDAR_CREDENTIALS", "envcreds")
        svc = GoogleCalendarService("t", {"token_file": "tok.json"})
        assert svc.credentials_json == "envcreds"


class TestGoogleCalendarServiceTokenAndAuth:
    def test_get_service_with_token(self):
        svc = _calendar_svc()
        with patch("integrations.google_calendar_service.Credentials") as creds_cls, \
                patch("integrations.google_calendar_service.build") as build:
            result = svc._get_service_with_token("my-token")
        creds_cls.assert_called_once_with("my-token")
        build.assert_called_once_with("calendar", "v3", credentials=creds_cls.return_value)
        assert result == build.return_value

    def test_get_service_cached(self):
        svc = _calendar_svc()
        svc.service = "cached-service"
        assert svc._get_service_with_token(None) == "cached-service"

    def test_get_service_auth_fails(self):
        svc = _calendar_svc()
        svc.authenticate = Mock(return_value=False)
        assert svc._get_service_with_token(None) is None

    def test_get_service_auth_succeeds(self):
        svc = _calendar_svc()
        svc.authenticate = Mock(return_value=True)
        svc.service = "svc"
        assert svc._get_service_with_token(None) == "svc"

    def test_authenticate_google_apis_unavailable(self):
        svc = _calendar_svc()
        with patch("integrations.google_calendar_service.GOOGLE_APIS_AVAILABLE", False):
            assert svc.authenticate() is False

    def test_authenticate_no_credentials(self, tmp_path, monkeypatch):
        svc = _calendar_svc(tmp_path)
        monkeypatch.delenv("GOOGLE_CALENDAR_CREDENTIALS", raising=False)
        with patch("os.path.exists", return_value=False):
            assert svc.authenticate() is False

    def test_authenticate_valid_token_file(self, tmp_path):
        from integrations.google_calendar_service import SCOPES

        svc = _calendar_svc(tmp_path)
        creds = MagicMock()
        creds.valid = True
        with patch("os.path.exists", return_value=True), \
                patch("integrations.google_calendar_service.Credentials") as creds_cls, \
                patch("integrations.google_calendar_service.build") as build:
            creds_cls.from_authorized_user_file.return_value = creds
            assert svc.authenticate() is True
        creds_cls.from_authorized_user_file.assert_called_once_with(svc.token_file, SCOPES)
        build.assert_called_once()
        assert svc.service is not None

    def test_authenticate_refresh_token(self, tmp_path):
        svc = _calendar_svc(tmp_path)
        creds = MagicMock()
        creds.valid = False
        creds.expired = True
        creds.refresh_token = "refresh-tok"
        creds.to_json.return_value = "{}"
        with patch("os.path.exists", return_value=True), \
                patch("integrations.google_calendar_service.Credentials") as creds_cls, \
                patch("integrations.google_calendar_service.Request"), \
                patch("integrations.google_calendar_service.build"):
            creds_cls.from_authorized_user_file.return_value = creds
            assert svc.authenticate() is True
        creds.refresh.assert_called_once()
        with open(svc.token_file) as f:
            assert f.read() == "{}"

    def test_authenticate_exception_path(self, tmp_path):
        svc = _calendar_svc(tmp_path)
        with patch("os.path.exists", return_value=True), \
                patch("integrations.google_calendar_service.Credentials") as creds_cls:
            creds_cls.from_authorized_user_file.side_effect = ValueError("corrupt token file")
            assert svc.authenticate() is False

    def test_authenticate_flow_json_string(self, tmp_path):
        svc = _calendar_svc(tmp_path)
        svc.credentials_json = json.dumps({"web": {"client_id": "cid"}})
        flow = MagicMock()
        flow.authorization_url.return_value = ("http://auth-url", "state123")
        flow.fetch_token = Mock()
        creds = MagicMock()
        creds.to_json.return_value = "{}"
        flow.credentials = creds
        captured = {}

        class FakeHTTPServer:
            def __init__(self, host, port, app):
                captured["app"] = app
            def handle_request(self):
                captured["app"]({"QUERY_STRING": "code=AUTHCODE"}, lambda *a, **k: None)

        with patch("os.path.exists", return_value=False), \
                patch("os.path.isfile", return_value=False), \
                patch("integrations.google_calendar_service.InstalledAppFlow") as flow_cls, \
                patch("wsgiref.simple_server.make_server", FakeHTTPServer), \
                patch("webbrowser.open"), \
                patch("integrations.google_calendar_service.build"):
            flow_cls.from_client_config.return_value = flow
            assert svc.authenticate() is True
        flow_cls.from_client_config.assert_called_once()
        flow.fetch_token.assert_called_once_with(code="AUTHCODE")
        assert flow.redirect_uri == "http://localhost:8080"

    def test_authenticate_flow_secrets_file(self, tmp_path):
        svc = _calendar_svc(tmp_path)
        svc.credentials_json = str(tmp_path / "client_secret.json")
        flow = MagicMock()
        flow.authorization_url.return_value = ("http://auth-url", "s")
        flow.fetch_token = Mock()
        creds = MagicMock()
        creds.to_json.return_value = "{}"
        flow.credentials = creds

        class FakeHTTPServer:
            def __init__(self, host, port, app):
                pass
            def handle_request(self):
                pass

        with patch("os.path.exists", return_value=False), \
                patch("os.path.isfile", return_value=True), \
                patch("integrations.google_calendar_service.InstalledAppFlow") as flow_cls, \
                patch("wsgiref.simple_server.make_server", FakeHTTPServer), \
                patch("webbrowser.open"), \
                patch("integrations.google_calendar_service.build"):
            flow_cls.from_client_secrets_file.return_value = flow
            assert svc.authenticate() is False
        flow_cls.from_client_secrets_file.assert_called_once()

    def test_authenticate_port_in_use(self, tmp_path):
        svc = _calendar_svc(tmp_path)
        svc.credentials_json = "{}"
        flow = MagicMock()
        flow.authorization_url.return_value = ("http://auth-url", "s")
        with patch("os.path.exists", return_value=False), \
                patch("os.path.isfile", return_value=False), \
                patch("integrations.google_calendar_service.InstalledAppFlow") as flow_cls, \
                patch("wsgiref.simple_server.make_server", side_effect=OSError("port busy")), \
                patch("webbrowser.open"):
            flow_cls.from_client_config.return_value = flow
            assert svc.authenticate() is False

    def test_authenticate_wsgi_404_no_code(self, tmp_path):
        svc = _calendar_svc(tmp_path)
        svc.credentials_json = "{}"
        flow = MagicMock()
        flow.authorization_url.return_value = ("http://auth-url", "s")
        start_calls = []

        class FakeHTTPServer:
            def __init__(self, host, port, app):
                captured["app"] = app
            def handle_request(self):
                captured["app"]({"QUERY_STRING": "error=1"}, lambda s, h: start_calls.append(s))

        captured = {}
        with patch("os.path.exists", return_value=False), \
                patch("os.path.isfile", return_value=False), \
                patch("integrations.google_calendar_service.InstalledAppFlow") as flow_cls, \
                patch("wsgiref.simple_server.make_server", FakeHTTPServer), \
                patch("webbrowser.open"):
            flow_cls.from_client_config.return_value = flow
            assert svc.authenticate() is False
        assert start_calls[0] == "404 Not Found"

    def test_authenticate_no_auth_code_captured(self, tmp_path):
        svc = _calendar_svc(tmp_path)
        svc.credentials_json = "{}"
        flow = MagicMock()
        flow.authorization_url.return_value = ("http://auth-url", "s")

        class FakeHTTPServer:
            def __init__(self, host, port, app):
                pass
            def handle_request(self):
                pass

        with patch("os.path.exists", return_value=False), \
                patch("os.path.isfile", return_value=False), \
                patch("integrations.google_calendar_service.InstalledAppFlow") as flow_cls, \
                patch("wsgiref.simple_server.make_server", FakeHTTPServer), \
                patch("webbrowser.open"):
            flow_cls.from_client_config.return_value = flow
            assert svc.authenticate() is False


class TestGoogleCalendarServiceOps:
    def test_list_calendars_success(self):
        svc = _calendar_svc()
        service = MagicMock()
        service.calendarList().list().execute.return_value = {"items": [{"id": "c1"}, {"id": "c2"}]}
        svc._get_service_with_token = Mock(return_value=service)
        result = asyncio_run(svc.list_calendars("tok"))
        assert len(result) == 2

    def test_list_calendars_no_service(self):
        svc = _calendar_svc()
        svc._get_service_with_token = Mock(return_value=None)
        assert asyncio_run(svc.list_calendars(None)) == []

    def test_list_calendars_exception(self):
        svc = _calendar_svc()
        service = MagicMock()
        service.calendarList().list().execute.side_effect = RuntimeError("boom")
        svc._get_service_with_token = Mock(return_value=service)
        assert asyncio_run(svc.list_calendars("tok")) == []

    def test_get_events_apis_unavailable(self):
        svc = _calendar_svc()
        with patch("integrations.google_calendar_service.GOOGLE_APIS_AVAILABLE", False):
            assert asyncio_run(svc.get_events()) == []

    def test_get_events_no_service(self):
        svc = _calendar_svc()
        svc._get_service_with_token = Mock(return_value=None)
        assert asyncio_run(svc.get_events()) == []

    def test_get_events_success_aware_times(self):
        svc = _calendar_svc()
        service = _fake_service_for(svc, {
            "items": [
                {"id": "e1", "summary": "Meet", "start": {"dateTime": "2025-11-01T10:00:00Z"},
                 "end": {"dateTime": "2025-11-01T11:00:00Z"}}
            ]
        })
        svc._get_service_with_token = Mock(return_value=service)
        start = datetime(2025, 11, 1, 9, 0, tzinfo=timezone.utc)
        end = datetime(2025, 11, 1, 12, 0, tzinfo=timezone.utc)
        events = asyncio_run(svc.get_events("primary", start, end, max_results=5, token="tok"))
        assert len(events) == 1
        assert events[0]["title"] == "Meet"
        call_kwargs = service.events().list.call_args.kwargs
        assert call_kwargs["timeMin"] == "2025-11-01T09:00:00Z"
        assert call_kwargs["timeMax"] == "2025-11-01T12:00:00Z"
        assert call_kwargs["maxResults"] == 5
        assert call_kwargs["calendarId"] == "primary"

    def test_get_events_success_naive_times(self):
        svc = _calendar_svc()
        service = _fake_service_for(svc, {"items": []})
        svc._get_service_with_token = Mock(return_value=service)
        events = asyncio_run(svc.get_events(time_min=datetime(2025, 11, 1, 9, 0)))
        assert events == []
        call_kwargs = service.events().list.call_args.kwargs
        assert call_kwargs["timeMin"] == "2025-11-01T09:00:00Z"

    def test_get_events_defaults_7_days(self):
        svc = _calendar_svc()
        service = _fake_service_for(svc, {"items": []})
        svc._get_service_with_token = Mock(return_value=service)
        asyncio_run(svc.get_events())
        call_kwargs = service.events().list.call_args.kwargs
        time_min = call_kwargs["timeMin"]
        time_max = call_kwargs["timeMax"]
        assert time_min.endswith("Z") and time_max.endswith("Z")
        assert time_min < time_max

    def test_get_events_http_error(self):
        svc = _calendar_svc()
        service = _fake_service_for(svc)
        service.events().list().execute.side_effect = _BoomError("api error")
        svc._get_service_with_token = Mock(return_value=service)
        with patch("integrations.google_calendar_service.HttpError", _BoomError):
            assert asyncio_run(svc.get_events()) == []

    def test_create_event_success(self):
        svc = _calendar_svc()
        service = MagicMock()
        service.events().insert().execute.return_value = {
            "id": "new-1", "summary": "Party",
            "start": {"dateTime": "2025-12-01T18:00:00Z"},
            "end": {"dateTime": "2025-12-01T19:00:00Z"},
        }
        svc._get_service_with_token = Mock(return_value=service)
        event = asyncio_run(svc.create_event({"title": "Party", "start_time": "2025-12-01T18:00:00Z", "end_time": "2025-12-01T19:00:00Z"}, "tok"))
        assert event["id"] == "new-1"
        assert event["title"] == "Party"
        body = service.events().insert.call_args.kwargs["body"]
        assert body["summary"] == "Party"

    def test_create_event_no_service(self):
        svc = _calendar_svc()
        svc._get_service_with_token = Mock(return_value=None)
        assert asyncio_run(svc.create_event({})) is None

    def test_create_event_http_error(self):
        svc = _calendar_svc()
        service = MagicMock()
        service.events().insert().execute.side_effect = _BoomError("fail")
        svc._get_service_with_token = Mock(return_value=service)
        with patch("integrations.google_calendar_service.HttpError", _BoomError):
            assert asyncio_run(svc.create_event({})) is None

    def test_update_event_success(self):
        svc = _calendar_svc()
        service = MagicMock()
        service.events().get().execute.return_value = {"id": "e1", "summary": "Old"}
        service.events().update().execute.return_value = {
            "id": "e1", "summary": "New",
            "start": {"dateTime": "2025-12-01T10:00:00Z"},
            "end": {"dateTime": "2025-12-01T11:00:00Z"},
        }
        svc.service = service
        result = asyncio_run(svc.update_event("e1", {
            "title": "New", "description": "d", "start_time": "2025-12-01T10:00:00Z",
            "end_time": "2025-12-01T11:00:00Z",
        }))
        assert result["title"] == "New"
        body = service.events().update.call_args.kwargs["body"]
        assert body["summary"] == "New"
        assert body["description"] == "d"
        assert body["start"]["dateTime"] == "2025-12-01T10:00:00Z"
        assert body["end"]["timeZone"] == "UTC"

    def test_update_event_auth_fails(self):
        svc = _calendar_svc()
        svc.authenticate = Mock(return_value=False)
        assert asyncio_run(svc.update_event("e1", {})) is None

    def test_update_event_http_error(self):
        svc = _calendar_svc()
        service = MagicMock()
        service.events().get().execute.side_effect = _BoomError("boom")
        svc.service = service
        with patch("integrations.google_calendar_service.HttpError", _BoomError):
            assert asyncio_run(svc.update_event("e1", {})) is None

    def test_delete_event_success(self):
        svc = _calendar_svc()
        service = MagicMock()
        delete_mock = service.events.return_value.delete
        delete_mock.return_value.execute.return_value = None
        svc.service = service
        assert asyncio_run(svc.delete_event("e1")) is True
        delete_mock.assert_called_once_with(calendarId="primary", eventId="e1")

    def test_delete_event_auth_fails(self):
        svc = _calendar_svc()
        svc.authenticate = Mock(return_value=False)
        assert asyncio_run(svc.delete_event("e1")) is False

    def test_delete_event_http_error(self):
        svc = _calendar_svc()
        service = MagicMock()
        service.events().delete().execute.side_effect = _BoomError("boom")
        svc.service = service
        with patch("integrations.google_calendar_service.HttpError", _BoomError):
            assert asyncio_run(svc.delete_event("e1")) is False

    def test_check_conflicts_not_authenticated(self):
        svc = _calendar_svc()
        svc.authenticate = Mock(return_value=False)
        result = asyncio_run(svc.check_conflicts(
            datetime(2025, 11, 1, 9, 0, tzinfo=timezone.utc),
            datetime(2025, 11, 1, 10, 0, tzinfo=timezone.utc),
        ))
        assert result["has_conflicts"] is False
        assert result["error"] == "Not authenticated"

    def test_check_conflicts_none(self):
        svc = _calendar_svc()
        svc.service = MagicMock()
        svc.get_events = AsyncMock(return_value=[])
        result = asyncio_run(svc.check_conflicts(
            datetime(2025, 11, 1, 9, 0, tzinfo=timezone.utc),
            datetime(2025, 11, 1, 10, 0, tzinfo=timezone.utc),
        ))
        assert result["success"] is True
        assert result["has_conflicts"] is False
        assert result["conflict_count"] == 0

    def test_check_conflicts_found(self):
        svc = _calendar_svc()
        svc.service = MagicMock()
        svc.get_events = AsyncMock(return_value=[{
            "id": "e1", "title": "Busy",
            "start_time": "2025-11-01T09:30:00Z",
            "end_time": "2025-11-01T10:30:00Z",
        }])
        result = asyncio_run(svc.check_conflicts(
            datetime(2025, 11, 1, 9, 0, tzinfo=timezone.utc),
            datetime(2025, 11, 1, 10, 0, tzinfo=timezone.utc),
        ))
        assert result["success"] is True
        assert result["has_conflicts"] is True
        assert result["conflict_count"] == 1
        assert result["conflicts"][0]["event_id"] == "e1"

    def test_check_conflicts_all_day_event_no_crash(self):
        svc = _calendar_svc()
        svc.service = MagicMock()
        svc.get_events = AsyncMock(return_value=[{
            "id": "e1", "title": "All Day",
            "start_time": "2025-11-01",
            "end_time": "2025-11-02",
        }])
        result = asyncio_run(svc.check_conflicts(
            datetime(2025, 11, 1, 9, 0, tzinfo=timezone.utc),
            datetime(2025, 11, 1, 10, 0, tzinfo=timezone.utc),
        ))
        assert result["success"] is True
        assert result["has_conflicts"] is True

    def test_check_conflicts_naive_query_times(self):
        svc = _calendar_svc()
        svc.service = MagicMock()
        svc.get_events = AsyncMock(return_value=[{
            "id": "e1", "title": "Busy",
            "start_time": "2025-11-01T09:30:00Z",
            "end_time": "2025-11-01T10:30:00Z",
        }])
        result = asyncio_run(svc.check_conflicts(
            datetime(2025, 11, 1, 9, 0),
            datetime(2025, 11, 1, 10, 0),
        ))
        assert result["success"] is True
        assert result["has_conflicts"] is True

    def test_check_conflicts_exception(self):
        svc = _calendar_svc()
        svc.service = MagicMock()
        svc.get_events = AsyncMock(return_value=[{
            "id": "e1", "title": "Bad",
            "start_time": "not-a-date",
            "end_time": "2025-11-01T10:30:00Z",
        }])
        result = asyncio_run(svc.check_conflicts(
            datetime(2025, 11, 1, 9, 0, tzinfo=timezone.utc),
            datetime(2025, 11, 1, 10, 0, tzinfo=timezone.utc),
        ))
        assert result["success"] is False
        assert result["has_conflicts"] is False
        assert "error" in result


class TestGoogleCalendarServiceConverters:
    def test_convert_google_to_unified_datetime(self):
        svc = _calendar_svc()
        result = svc._convert_google_to_unified({
            "id": "e1", "summary": "Meet", "description": "desc",
            "start": {"dateTime": "2025-11-01T10:00:00Z"},
            "end": {"dateTime": "2025-11-01T11:00:00Z"},
            "attendees": [{"email": "a@x.com", "responseStatus": "accepted"}, {"email": "b@x.com"}],
            "location": "Room 1", "created": "2025-10-01T00:00:00Z", "updated": "2025-10-02T00:00:00Z",
        })
        assert result["id"] == "e1"
        assert result["title"] == "Meet"
        assert result["start_time"] == "2025-11-01T10:00:00Z"
        assert result["attendees"] == ["a@x.com", "b@x.com"]
        assert result["platform"] == "google_calendar"

    def test_convert_google_to_unified_all_day(self):
        svc = _calendar_svc()
        result = svc._convert_google_to_unified({
            "id": "e2", "start": {"date": "2025-11-01"}, "end": {"date": "2025-11-02"},
        })
        assert result["title"] == "Untitled Event"
        assert result["start_time"] == "2025-11-01"
        assert result["end_time"] == "2025-11-02"
        assert result["attendees"] == []

    def test_convert_unified_to_google_minimal(self):
        svc = _calendar_svc()
        result = svc._convert_unified_to_google({
            "title": "T", "description": "D", "start_time": "2025-11-01T10:00:00Z",
            "end_time": "2025-11-01T11:00:00Z",
        })
        assert result["summary"] == "T"
        assert result["start"]["timeZone"] == "UTC"
        assert "location" not in result
        assert "attendees" not in result

    def test_convert_unified_to_google_full(self):
        svc = _calendar_svc()
        result = svc._convert_unified_to_google({
            "title": "T", "start_time": "s", "end_time": "e",
            "location": "HQ", "attendees": ["a@x.com", "b@x.com"],
        })
        assert result["location"] == "HQ"
        assert result["attendees"] == [{"email": "a@x.com"}, {"email": "b@x.com"}]

    def test_convert_unified_to_google_empty_attendees(self):
        svc = _calendar_svc()
        result = svc._convert_unified_to_google({
            "title": "T", "start_time": "s", "end_time": "e", "attendees": [],
        })
        assert "attendees" not in result


class TestGoogleCalendarServiceSync:
    def test_sync_to_postgres_cache_new_metric(self, tmp_path):
        svc = _calendar_svc(tmp_path)
        svc.get_events = AsyncMock(return_value=[{"id": "a"}, {"id": "b"}])
        db = MagicMock()
        db.query().filter_by().first.return_value = None
        with patch("core.database.SessionLocal", return_value=db):
            result = asyncio_run(svc.sync_to_postgres_cache("ws-1"))
        assert result["success"] is True
        assert result["metrics_synced"] == 1
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.close.assert_called_once()

    def test_sync_to_postgres_cache_existing_metric(self, tmp_path):
        svc = _calendar_svc(tmp_path)
        svc.get_events = AsyncMock(return_value=[])
        existing = MagicMock()
        db = MagicMock()
        db.query().filter_by().first.return_value = existing
        with patch("core.database.SessionLocal", return_value=db):
            result = asyncio_run(svc.sync_to_postgres_cache("ws-1"))
        assert result["success"] is True
        assert existing.value == 0.0
        assert db.add.call_count == 0

    def test_sync_to_postgres_cache_get_events_raises(self, tmp_path):
        svc = _calendar_svc(tmp_path)
        svc.get_events = AsyncMock(side_effect=RuntimeError("boom"))
        db = MagicMock()
        db.query().filter_by().first.return_value = None
        with patch("core.database.SessionLocal", return_value=db):
            result = asyncio_run(svc.sync_to_postgres_cache("ws-1"))
        assert result["success"] is True
        assert result["metrics_synced"] == 1

    def test_sync_to_postgres_cache_db_failure(self, tmp_path):
        svc = _calendar_svc(tmp_path)
        svc.get_events = AsyncMock(return_value=[])
        db = MagicMock()
        db.commit.side_effect = RuntimeError("db down")
        with patch("core.database.SessionLocal", return_value=db):
            result = asyncio_run(svc.sync_to_postgres_cache("ws-1"))
        assert result["success"] is False
        assert "Failed to save" in result["error"]
        db.rollback.assert_called_once()
        db.close.assert_called_once()

    def test_sync_to_postgres_cache_outer_failure(self, tmp_path):
        svc = _calendar_svc(tmp_path)
        with patch("core.database.SessionLocal", side_effect=RuntimeError("no db")):
            result = asyncio_run(svc.sync_to_postgres_cache("ws-1"))
        assert result["success"] is False
        assert "cache sync failed" in result["error"]

    def test_full_sync(self, tmp_path):
        svc = _calendar_svc(tmp_path)
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True, "metrics_synced": 1})
        result = asyncio_run(svc.full_sync("ws-1"))
        assert result["success"] is True
        assert result["workspace_id"] == "ws-1"
        assert result["postgres_cache"]["metrics_synced"] == 1


class TestGoogleCalendarServiceMeta:
    def test_get_capabilities(self):
        svc = _calendar_svc()
        caps = svc.get_capabilities()
        assert "get_events" in caps["operations"]
        assert caps["authentication"] == "oauth"

    def test_health_check_healthy(self):
        svc = _calendar_svc()
        svc.authenticate = Mock(return_value=True)
        result = svc.health_check()
        assert result["status"] == "healthy"
        assert result["authenticated"] is True

    def test_health_check_unhealthy(self):
        svc = _calendar_svc()
        svc.authenticate = Mock(return_value=False)
        result = svc.health_check()
        assert result["status"] == "unhealthy"

    def test_health_check_exception(self):
        svc = _calendar_svc()
        svc.authenticate = Mock(side_effect=RuntimeError("boom"))
        result = svc.health_check()
        assert result["status"] == "unhealthy"
        assert result["error"] == "Google Calendar health check failed"

    def test_execute_operation_tenant_mismatch(self):
        svc = _calendar_svc()
        result = asyncio_run(svc.execute_operation("get_events", {}, {"tenant_id": "other"}))
        assert result["success"] is False
        assert result["error"] == "Tenant ID mismatch"

    def test_execute_operation_get_events(self):
        svc = _calendar_svc()
        svc.get_events = AsyncMock(return_value=[{"id": "e1"}])
        result = asyncio_run(svc.execute_operation("get_events", {"calendar_id": "c1", "max_results": 5}))
        assert result["success"] is True
        assert result["data"] == [{"id": "e1"}]

    def test_execute_operation_create_event(self):
        svc = _calendar_svc()
        svc.create_event = AsyncMock(return_value={"id": "e1"})
        result = asyncio_run(svc.execute_operation("create_event", {"event_data": {"title": "T"}}))
        assert result["success"] is True
        assert result["data"] == {"id": "e1"}

    def test_execute_operation_create_event_failure(self):
        svc = _calendar_svc()
        svc.create_event = AsyncMock(return_value=None)
        result = asyncio_run(svc.execute_operation("create_event", {"event_data": {}}))
        assert result["success"] is False

    def test_execute_operation_update_event(self):
        svc = _calendar_svc()
        svc.update_event = AsyncMock(return_value={"id": "e1"})
        result = asyncio_run(svc.execute_operation("update_event", {"event_id": "e1", "updates": {"title": "T"}}))
        assert result["success"] is True

    def test_execute_operation_delete_event(self):
        svc = _calendar_svc()
        svc.delete_event = AsyncMock(return_value=True)
        result = asyncio_run(svc.execute_operation("delete_event", {"event_id": "e1"}))
        assert result["success"] is True

    def test_execute_operation_check_conflicts(self):
        svc = _calendar_svc()
        svc.check_conflicts = AsyncMock(return_value={"has_conflicts": False})
        result = asyncio_run(svc.execute_operation("check_conflicts", {"start_time": "s", "end_time": "e"}))
        assert result["success"] is True

    def test_execute_operation_unknown(self):
        svc = _calendar_svc()
        result = asyncio_run(svc.execute_operation("fly_to_moon", {}))
        assert result["success"] is False
        assert "Unknown operation" in result["error"]

    def test_execute_operation_exception(self):
        svc = _calendar_svc()
        svc.get_events = AsyncMock(side_effect=RuntimeError("boom"))
        result = asyncio_run(svc.execute_operation("get_events", {}))
        assert result["success"] is False
        assert result["error"] == "Google Calendar operation failed"


# ---------------------------------------------------------------------------
# google_drive_service
# ---------------------------------------------------------------------------

def _drive_svc(access_token=None):
    from integrations.google_drive_service import GoogleDriveService

    return GoogleDriveService("default", {"access_token": access_token})


def _patch_httpx(client=None):
    return patch("integrations.google_drive_service.httpx.AsyncClient")


def _http_client(get_result=None, get_side_effect=None):
    client = AsyncMock()
    if get_side_effect is not None:
        client.get = AsyncMock(side_effect=get_side_effect)
    else:
        client.get = AsyncMock(return_value=get_result)
    client.post = AsyncMock(return_value=get_result)
    return client


def _json_response(payload, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = json.dumps(payload).encode()
    resp.json.return_value = payload
    resp.raise_for_status = Mock()
    return resp


def _http_error(status=400):
    request = httpx.Request("GET", "http://x")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("boom", request=request, response=response)


class TestGoogleDriveServiceBasics:
    def test_init_no_config(self):
        from integrations.google_drive_service import GoogleDriveService

        svc = GoogleDriveService("default")
        assert svc.access_token is None
        assert svc.service_name == "google_drive"

    def test_init_with_access_token(self):
        svc = _drive_svc("tok1")
        assert svc.access_token == "tok1"
        assert svc.service_name == "google_drive"
        assert svc.required_scopes

    def test_init_without_access_token(self):
        svc = _drive_svc()
        assert svc.access_token is None

    def test_resolve_token_prefers_arg(self):
        svc = _drive_svc("config-tok")
        assert svc._resolve_token("arg-tok") == "arg-tok"
        assert svc._resolve_token(None) == "config-tok"
        svc2 = _drive_svc()
        assert svc2._resolve_token(None) is None

    def test_get_capabilities(self):
        svc = _drive_svc()
        caps = svc.get_capabilities()
        assert [op["id"] for op in caps["operations"]] == [
            "list_files", "walk_files", "search_files", "get_file_metadata", "download_file",
            "ingest_file_to_memory", "sync_to_postgres_cache", "full_sync",
        ]
        assert caps["required_params"] == ["access_token"]

    async def test_get_access_token_google_drive_connection(self):
        svc = _drive_svc()
        with patch("integrations.google_drive_service.connection_service") as cs:
            cs.get_connections.return_value = [{"id": "c1"}]
            cs.get_connection_credentials = AsyncMock(return_value={"access_token": "conn-tok"})
            token = await svc.get_access_token("u1")
        assert token == "conn-tok"
        cs.get_connections.assert_called_with("u1", "google_drive")

    async def test_get_access_token_falls_to_google_connection(self):
        svc = _drive_svc()
        with patch("integrations.google_drive_service.connection_service") as cs:
            cs.get_connections.side_effect = [[], [{"id": "c2"}]]
            cs.get_connection_credentials = AsyncMock(return_value={"access_token": "g-tok"})
            token = await svc.get_access_token("u1")
        assert token == "g-tok"

    async def test_get_access_token_connection_no_creds(self):
        svc = _drive_svc()
        with patch("integrations.google_drive_service.connection_service") as cs:
            cs.get_connections.return_value = [{"id": "c1"}]
            cs.get_connection_credentials = AsyncMock(return_value=None)
            token = await svc.get_access_token("u1")
        assert token is None

    async def test_authenticate_success(self, monkeypatch):
        svc = _drive_svc()
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-123")
        result = await svc.authenticate("u1")
        assert result["status"] == "success"
        assert "client_id=client-123" in result["auth_url"]
        assert result["state"] == "google_drive_u1"
        assert "drive.readonly" in result["auth_url"]
        assert "access_type=offline" in result["auth_url"]

    async def test_authenticate_missing_client_id(self, monkeypatch):
        svc = _drive_svc()
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        result = await svc.authenticate("u1")
        assert result["status"] == "error"
        assert "GOOGLE_CLIENT_ID" in result["message"]

    async def test_authenticate_exception(self, monkeypatch):
        svc = _drive_svc()
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
        with patch("integrations.google_drive_service.urlencode", side_effect=RuntimeError("boom")):
            result = await svc.authenticate("u1")
        assert result["status"] == "error"
        assert result["message"] == "Authentication failed"

    async def test_health_check_no_token(self, monkeypatch):
        svc = _drive_svc()
        monkeypatch.delenv("GOOGLE_DRIVE_ACCESS_TOKEN", raising=False)
        result = await svc.health_check()
        assert result["status"] == "unhealthy"
        assert "No access token" in result["message"]

    async def test_health_check_healthy(self, monkeypatch):
        svc = _drive_svc("tok")
        result = await svc.health_check()
        assert result["status"] == "healthy"
        assert result["service"] == "google_drive"

    async def test_health_check_env_token(self, monkeypatch):
        svc = _drive_svc()
        monkeypatch.setenv("GOOGLE_DRIVE_ACCESS_TOKEN", "envtok")
        result = await svc.health_check()
        assert result["status"] == "healthy"

    async def test_health_check_exception(self, monkeypatch):
        svc = _drive_svc()
        with patch("os.getenv", side_effect=RuntimeError("boom")):
            result = await svc.health_check()
        assert result["status"] == "unhealthy"

    async def test_drive_get_json(self):
        svc = _drive_svc()
        resp = _json_response({"files": []})
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_result=resp)
            ac.return_value.__aenter__.return_value = client
            data = await svc._drive_get("tok", "http://api/files", {"q": "x"})
        assert data == {"files": []}
        client.get.assert_called_once_with("http://api/files", headers={"Authorization": "Bearer tok"}, params={"q": "x"})

    async def test_drive_get_empty_204(self):
        svc = _drive_svc()
        resp = MagicMock()
        resp.status_code = 204
        resp.content = b""
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_result=resp)
            ac.return_value.__aenter__.return_value = client
            assert await svc._drive_get("tok", "http://api/x") == {}

    async def test_drive_get_bytes(self):
        svc = _drive_svc()
        resp = MagicMock()
        resp.content = b"raw-bytes"
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_result=resp)
            ac.return_value.__aenter__.return_value = client
            assert await svc._drive_get_bytes("tok", "http://api/x") == b"raw-bytes"


class TestGoogleDriveServiceExecuteOperation:
    async def test_execute_operation_list_files_success(self):
        svc = _drive_svc()
        svc.list_files = AsyncMock(return_value={"status": "success", "data": {"files": []}})
        result = await svc.execute_operation("list_files", {"access_token": "t"})
        assert result == {"success": True, "result": {"files": []}}

    async def test_execute_operation_operation_error(self):
        svc = _drive_svc()
        svc.list_files = AsyncMock(return_value={"status": "error", "message": "no token"})
        result = await svc.execute_operation("list_files", {})
        assert result == {"success": False, "error": "no token"}

    async def test_execute_operation_search_files(self):
        svc = _drive_svc()
        svc.search_files = AsyncMock(return_value={"status": "success", "data": {"files": [{"id": "1"}]}})
        result = await svc.execute_operation("search_files", {"access_token": "t", "query": "q"})
        assert result["success"] is True

    async def test_execute_operation_get_metadata(self):
        svc = _drive_svc()
        svc.get_file_metadata = AsyncMock(return_value={"status": "success", "data": {"id": "f"}})
        result = await svc.execute_operation("get_file_metadata", {"access_token": "t", "file_id": "f"})
        assert result["success"] is True

    async def test_execute_operation_download(self):
        svc = _drive_svc()
        svc.download_file = AsyncMock(return_value={"status": "success", "data": {"content_b64": "x"}})
        result = await svc.execute_operation("download_file", {"access_token": "t", "file_id": "f"})
        assert result["success"] is True

    async def test_execute_operation_unknown(self):
        svc = _drive_svc()
        result = await svc.execute_operation("nope", {})
        assert result["success"] is False
        assert "Unknown operation" in result["error"]

    async def test_execute_operation_exception_no_leak(self):
        svc = _drive_svc()
        svc.list_files = AsyncMock(side_effect=RuntimeError("sensitive-detail-123"))
        result = await svc.execute_operation("list_files", {})
        assert result["success"] is False
        assert "sensitive-detail-123" not in result["error"]
        assert result["details"] == {"operation": "list_files"}


class TestGoogleDriveServiceListAndSearch:
    async def test_list_files_no_token(self):
        svc = _drive_svc()
        result = await svc.list_files(None)
        assert result["status"] == "error"
        assert "token" in result["message"].lower()

    async def test_list_files_success_root(self):
        svc = _drive_svc("tok")
        payload = {"files": [{"id": "f1", "name": "a.txt"}], "nextPageToken": "np1"}
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_result=_json_response(payload))
            ac.return_value.__aenter__.return_value = client
            result = await svc.list_files(None)
        assert result["status"] == "success"
        assert result["data"]["files"][0]["id"] == "f1"
        assert result["data"]["nextPageToken"] == "np1"
        params = client.get.call_args.kwargs["params"]
        assert params["q"] == "trashed = false"
        assert params["pageSize"] == 100

    async def test_list_files_folder(self):
        svc = _drive_svc("tok")
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_result=_json_response({"files": []}))
            ac.return_value.__aenter__.return_value = client
            result = await svc.list_files(None, folder_id="F1", page_size=50, page_token="pt")
        assert result["status"] == "success"
        params = client.get.call_args.kwargs["params"]
        assert params["q"] == "'F1' in parents and trashed = false"
        assert params["pageSize"] == 50
        assert params["pageToken"] == "pt"

    async def test_list_files_root_folder_id(self):
        svc = _drive_svc("tok")
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_result=_json_response({"files": []}))
            ac.return_value.__aenter__.return_value = client
            await svc.list_files(None, folder_id="root")
        params = client.get.call_args.kwargs["params"]
        assert params["q"] == "trashed = false"

    async def test_list_files_page_size_capped(self):
        svc = _drive_svc("tok")
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_result=_json_response({"files": []}))
            ac.return_value.__aenter__.return_value = client
            await svc.list_files(None, page_size=5000)
        assert client.get.call_args.kwargs["params"]["pageSize"] == 1000

    async def test_list_files_http_error(self):
        svc = _drive_svc("tok")
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_side_effect=_http_error(429))
            ac.return_value.__aenter__.return_value = client
            result = await svc.list_files(None)
        assert result["status"] == "error"
        assert "429" in result["message"]

    async def test_list_files_generic_error(self):
        svc = _drive_svc("tok")
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_side_effect=RuntimeError("net down"))
            ac.return_value.__aenter__.return_value = client
            result = await svc.list_files(None)
        assert result["status"] == "error"
        assert "net down" not in result["message"]

    async def test_search_files_escapes_quotes(self):
        svc = _drive_svc("tok")
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_result=_json_response({"files": [{"id": "s1"}], "nextPageToken": None}))
            ac.return_value.__aenter__.return_value = client
            result = await svc.search_files(None, "O'Brien's file")
        assert result["status"] == "success"
        params = client.get.call_args.kwargs["params"]
        assert "fullText contains 'O\\'Brien\\'s file'" in params["q"]

    async def test_search_files_no_token(self):
        svc = _drive_svc()
        result = await svc.search_files(None, "q")
        assert result["status"] == "error"

    async def test_search_files_page_token(self):
        svc = _drive_svc("tok")
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_result=_json_response({"files": []}))
            ac.return_value.__aenter__.return_value = client
            await svc.search_files(None, "q", page_token="pt2")
        assert client.get.call_args.kwargs["params"]["pageToken"] == "pt2"

    async def test_search_files_http_error(self):
        svc = _drive_svc("tok")
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_side_effect=_http_error(400))
            ac.return_value.__aenter__.return_value = client
            result = await svc.search_files(None, "q")
        assert result["status"] == "error"
        assert "400" in result["message"]

    async def test_search_files_generic_error(self):
        svc = _drive_svc("tok")
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_side_effect=RuntimeError("boom"))
            ac.return_value.__aenter__.return_value = client
            result = await svc.search_files(None, "q")
        assert result["status"] == "error"


class TestGoogleDriveServiceFileOps:
    async def test_get_file_metadata_success(self):
        svc = _drive_svc("tok")
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_result=_json_response({"id": "f1", "name": "x.txt"}))
            ac.return_value.__aenter__.return_value = client
            result = await svc.get_file_metadata(None, "f1")
        assert result["status"] == "success"
        assert result["data"]["id"] == "f1"
        params = client.get.call_args.kwargs["params"]
        assert params["supportsAllDrives"] == "true"

    async def test_get_file_metadata_no_token(self):
        svc = _drive_svc()
        result = await svc.get_file_metadata(None, "f1")
        assert result["status"] == "error"

    async def test_get_file_metadata_http_error(self):
        svc = _drive_svc("tok")
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_side_effect=_http_error(404))
            ac.return_value.__aenter__.return_value = client
            result = await svc.get_file_metadata(None, "f1")
        assert result["status"] == "error"
        assert "404" in result["message"]

    async def test_get_file_metadata_generic_error(self):
        svc = _drive_svc("tok")
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_side_effect=RuntimeError("boom"))
            ac.return_value.__aenter__.return_value = client
            result = await svc.get_file_metadata(None, "f1")
        assert result["status"] == "error"

    async def test_download_file_no_token(self):
        svc = _drive_svc()
        result = await svc.download_file(None, "f1")
        assert result["status"] == "error"

    async def test_download_file_google_doc_export(self):
        svc = _drive_svc("tok")
        svc.get_file_metadata = AsyncMock(return_value={
            "status": "success", "data": {"mimeType": "application/vnd.google-apps.document"},
        })
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_result=MagicMock(content=b"docx-bytes"))
            ac.return_value.__aenter__.return_value = client
            result = await svc.download_file(None, "f1")
        assert result["status"] == "success"
        assert result["data"]["content_b64"] == base64.b64encode(b"docx-bytes").decode()
        assert result["data"]["mimeType"] == "application/vnd.google-apps.document"
        export_url = client.get.call_args.args[0]
        assert export_url.endswith("/export")
        assert client.get.call_args.kwargs["params"] == {"mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}

    async def test_download_file_regular(self):
        svc = _drive_svc("tok")
        svc.get_file_metadata = AsyncMock(return_value={
            "status": "success", "data": {"mimeType": "text/plain"},
        })
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_result=MagicMock(content=b"hello"))
            ac.return_value.__aenter__.return_value = client
            result = await svc.download_file(None, "f1")
        assert result["status"] == "success"
        assert result["data"]["downloadUrl"].endswith("?alt=media")
        assert result["data"]["size"] == 5

    async def test_download_file_metadata_failure_still_downloads(self):
        svc = _drive_svc("tok")
        svc.get_file_metadata = AsyncMock(return_value={"status": "error", "message": "no"})
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_result=MagicMock(content=b"x"))
            ac.return_value.__aenter__.return_value = client
            result = await svc.download_file(None, "f1")
        assert result["status"] == "success"
        assert result["data"]["mimeType"] is None

    async def test_download_file_http_error(self):
        svc = _drive_svc("tok")
        svc.get_file_metadata = AsyncMock(return_value={"status": "error"})
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_side_effect=_http_error(403))
            ac.return_value.__aenter__.return_value = client
            result = await svc.download_file(None, "f1")
        assert result["status"] == "error"
        assert "403" in result["message"]

    async def test_download_file_generic_error(self):
        svc = _drive_svc("tok")
        svc.get_file_metadata = AsyncMock(side_effect=RuntimeError("boom"))
        result = await svc.download_file(None, "f1")
        assert result["status"] == "error"

    async def test_download_file_bytes_no_token(self):
        svc = _drive_svc()
        assert await svc.download_file_bytes(None, "f1") is None

    async def test_download_file_bytes_export(self):
        svc = _drive_svc("tok")
        svc.get_file_metadata = AsyncMock(return_value={
            "status": "success", "data": {"mimeType": "application/vnd.google-apps.spreadsheet"},
        })
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_result=MagicMock(content=b"xlsx"))
            ac.return_value.__aenter__.return_value = client
            data = await svc.download_file_bytes(None, "f1")
        assert data == b"xlsx"
        assert "spreadsheetml" in client.get.call_args.kwargs["params"]["mimeType"]

    async def test_download_file_bytes_regular(self):
        svc = _drive_svc("tok")
        svc.get_file_metadata = AsyncMock(return_value={"status": "success", "data": {"mimeType": "text/plain"}})
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_result=MagicMock(content=b"raw"))
            ac.return_value.__aenter__.return_value = client
            data = await svc.download_file_bytes(None, "f1")
        assert data == b"raw"

    async def test_download_file_bytes_error(self):
        svc = _drive_svc("tok")
        svc.get_file_metadata = AsyncMock(return_value={"status": "success", "data": {"mimeType": "text/plain"}})
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_side_effect=RuntimeError("boom"))
            ac.return_value.__aenter__.return_value = client
            assert await svc.download_file_bytes(None, "f1") is None

    async def test_upload_file_no_token(self):
        svc = _drive_svc()
        result = await svc.upload_file(None, "a.txt", b"data")
        assert result["status"] == "error"

    async def test_upload_file_success(self):
        svc = _drive_svc("tok")
        resp = _json_response({"id": "u1", "name": "a.txt"})
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_result=resp)
            ac.return_value.__aenter__.return_value = client
            result = await svc.upload_file(None, "a.txt", b"data")
        assert result["status"] == "success"
        assert result["data"]["id"] == "u1"
        call_kwargs = client.post.call_args.kwargs
        assert call_kwargs["headers"]["Authorization"] == "Bearer tok"
        assert b"a.txt" in call_kwargs["content"]
        assert call_kwargs["content"].endswith(b"--atom-drive-314159--")

    async def test_upload_file_with_folder(self):
        svc = _drive_svc("tok")
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_result=_json_response({"id": "u2"}))
            ac.return_value.__aenter__.return_value = client
            result = await svc.upload_file(None, "a.txt", b"data", folder_id="FOLDER9")
        assert result["status"] == "success"
        assert b'"FOLDER9"' in client.post.call_args.kwargs["content"]

    async def test_upload_file_http_error(self):
        svc = _drive_svc("tok")
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_result=None)
            client.post = AsyncMock(side_effect=_http_error(413))
            ac.return_value.__aenter__.return_value = client
            result = await svc.upload_file(None, "a.txt", b"data")
        assert result["status"] == "error"
        assert "413" in result["message"]

    async def test_upload_file_generic_error(self):
        svc = _drive_svc("tok")
        with patch("integrations.google_drive_service.httpx.AsyncClient") as ac:
            client = _http_client(get_result=None)
            client.post = AsyncMock(side_effect=RuntimeError("boom"))
            ac.return_value.__aenter__.return_value = client
            result = await svc.upload_file(None, "a.txt", b"data")
        assert result["status"] == "error"


class TestGoogleDriveServiceSync:
    def _fake_db(self, first_values):
        db = MagicMock()
        db.query().filter_by().first.side_effect = first_values
        return db

    async def test_sync_walk_error(self):
        svc = _drive_svc("tok")
        svc.walk_files = AsyncMock(side_effect=RuntimeError("no token"))
        result = await svc.sync_to_postgres_cache("ws-1", "tok")
        assert result["success"] is False
        assert "cache sync failed" in result["error"]

    async def test_sync_success_new_and_existing(self):
        svc = _drive_svc("tok")
        svc.walk_files = AsyncMock(return_value=[
            {"id": "d1", "mimeType": "application/vnd.google-apps.document"},
            {"id": "s1", "mimeType": "application/vnd.google-apps.spreadsheet"},
            {"id": "p1", "mimeType": "image/png"},
        ])
        existing = MagicMock()
        db = MagicMock()
        db.query().filter_by().first.side_effect = [None, existing, None]
        with patch("core.database.SessionLocal", return_value=db):
            result = await svc.sync_to_postgres_cache("ws-1", "tok")
        assert result["success"] is True
        assert result["metrics_synced"] == 3
        assert db.add.call_count == 2
        assert existing.value == 1.0
        db.commit.assert_called_once()
        db.close.assert_called_once()

    async def test_sync_db_failure(self):
        svc = _drive_svc("tok")
        svc.walk_files = AsyncMock(return_value=[])
        db = MagicMock()
        db.commit.side_effect = RuntimeError("db down")
        with patch("core.database.SessionLocal", return_value=db):
            result = await svc.sync_to_postgres_cache("ws-1", "tok")
        assert result["success"] is False
        assert "Failed to save" in result["error"]
        db.rollback.assert_called_once()
        db.close.assert_called_once()

    async def test_sync_outer_failure(self):
        svc = _drive_svc("tok")
        svc.walk_files = AsyncMock(return_value=[])
        with patch("core.database.SessionLocal", side_effect=RuntimeError("no db")):
            result = await svc.sync_to_postgres_cache("ws-1", "tok")
        assert result["success"] is False
        assert "cache sync failed" in result["error"]

    async def test_full_sync(self):
        svc = _drive_svc("tok")
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True, "metrics_synced": 3})
        result = await svc.full_sync("ws-1", "tok")
        assert result["success"] is True
        assert result["workspace_id"] == "ws-1"
        assert result["postgres_cache"]["metrics_synced"] == 3
        assert "timestamp" in result


def asyncio_run(coro):
    import asyncio

    return asyncio.new_event_loop().run_until_complete(coro)
