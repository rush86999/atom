# -*- coding: utf-8 -*-
"""Coverage wave 94 — integrations/google_calendar_service.py (TDD, fully
mocked Google APIs — no network, no OAuth browser).

Baseline: 98% via older waves; the only uncovered lines were the
ImportError fallback (dummy classes when google libs are missing). This file
drives the whole service standalone: init (config/env), token-passing and
internal-auth service acquisition, the full authenticate matrix (libs
missing, no credentials, token file valid/expired-refresh, client-secrets
file, JSON config, local-server OAuth success / no-auth-code / port-in-use,
token save), calendars/events CRUD + HttpError and no-auth paths, conflict
detection (overlap, none, naive times, all-day date-only events, auth fail,
exception), time parse/convert helpers, Postgres cache sync (create/update/
rollback/outer), full sync, capabilities, health check, and every
execute_operation branch (tenant mismatch, unknown op, exception no-leak).
"""
import asyncio
import importlib
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from integrations import google_calendar_service as gcal_mod
from integrations.google_calendar_service import GoogleCalendarService


def _svc(**config):
    return GoogleCalendarService(tenant_id="t1", config=config)


class _Creds:
    def __init__(self, valid=True, expired=False, refresh_token="rt"):
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token

    def to_json(self):
        return '{"token": "at"}'

    @classmethod
    def from_authorized_user_file(cls, path, scopes):
        return cls()

    @classmethod
    def refresh(cls, request):
        return None

    def refresh_token_value(self):
        return self.refresh_token


class TestInitAndImportFallback:
    def test_import_error_fallback(self):
        """GOOGLE_APIS_AVAILABLE=False + dummy classes when libs missing."""
        saved = sys.modules.get("google.oauth2.credentials")
        sys.modules["google.oauth2.credentials"] = None
        try:
            importlib.reload(gcal_mod)
            assert gcal_mod.GOOGLE_APIS_AVAILABLE is False
            assert gcal_mod.build("calendar", "v3") is None
            assert issubclass(gcal_mod.HttpError, Exception)
            assert callable(gcal_mod.Credentials)
        finally:
            if saved is not None:
                sys.modules["google.oauth2.credentials"] = saved
            else:
                sys.modules.pop("google.oauth2.credentials", None)
            importlib.reload(gcal_mod)
        assert gcal_mod.GOOGLE_APIS_AVAILABLE is True

    def test_init_defaults(self):
        svc = GoogleCalendarService()
        assert svc.token_file == "token.json"
        assert svc.service is None
        assert svc.creds is None
        assert svc.credentials_json is None

    def test_init_from_config(self):
        svc = _svc(credentials_json="{}", token_file="/tmp/t.json")
        assert svc.credentials_json == "{}"
        assert svc.token_file == "/tmp/t.json"

    def test_init_from_env(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CALENDAR_CREDENTIALS", "env-creds")
        svc = GoogleCalendarService()
        assert svc.credentials_json == "env-creds"


class TestServiceAcquisition:
    def test_get_service_with_token(self):
        svc = _svc()
        with patch.object(gcal_mod, "Credentials") as creds_cls, \
             patch.object(gcal_mod, "build", return_value="built-service") as build:
            result = svc._get_service_with_token("tok123")
        assert result == "built-service"
        creds_cls.assert_called_once_with("tok123")
        build.assert_called_once_with("calendar", "v3",
                                      credentials=creds_cls.return_value)

    def test_get_service_uses_internal_authenticated_service(self):
        svc = _svc()
        svc.service = "internal-service"
        with patch.object(svc, "authenticate") as auth:
            assert svc._get_service_with_token() == "internal-service"
        auth.assert_not_called()

    def test_get_service_authenticates_when_missing(self):
        svc = _svc()
        svc.service = None
        with patch.object(svc, "authenticate", return_value=True):
            svc.service = "after-auth"
            assert svc._get_service_with_token() == "after-auth"

    def test_get_service_returns_none_on_auth_failure(self):
        svc = _svc()
        with patch.object(svc, "authenticate", return_value=False):
            assert svc._get_service_with_token() is None


class TestAuthenticate:
    def test_apis_not_available(self):
        svc = _svc()
        with patch.object(gcal_mod, "GOOGLE_APIS_AVAILABLE", False):
            assert svc.authenticate() is False

    def test_no_credentials_returns_false(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GOOGLE_CALENDAR_CREDENTIALS", raising=False)
        svc = _svc(token_file=str(tmp_path / "tok.json"))
        with patch("os.path.exists", return_value=False):
            assert svc.authenticate() is False

    def test_valid_token_file_skips_oauth(self, tmp_path):
        svc = _svc(token_file=str(tmp_path / "tok.json"))
        creds = _Creds(valid=True)
        with patch("os.path.exists", return_value=True), \
             patch.object(gcal_mod.Credentials, "from_authorized_user_file",
                          return_value=creds), \
             patch.object(gcal_mod, "build", return_value="svc") as build:
            assert svc.authenticate() is True
        assert svc.service == "svc"
        build.assert_called_once()

    def test_expired_token_with_refresh_token(self, tmp_path):
        svc = _svc(token_file=str(tmp_path / "tok.json"))
        creds = _Creds(valid=False, expired=True, refresh_token="rt1")
        creds.refresh = Mock()
        with patch("os.path.exists", return_value=True), \
             patch.object(gcal_mod.Credentials, "from_authorized_user_file",
                          return_value=creds), \
             patch.object(gcal_mod, "build", return_value="svc"):
            assert svc.authenticate() is True
        creds.refresh.assert_called_once()
        assert (tmp_path / "tok.json").exists()

    def test_expired_token_without_refresh_token_uses_flow(self, tmp_path):
        svc = _svc(credentials_json=str(tmp_path / "client.json"),
                   token_file=str(tmp_path / "tok.json"))
        creds = _Creds(valid=False, expired=True, refresh_token=None)
        with patch("os.path.exists", return_value=False), \
             patch("os.path.isfile", return_value=True), \
             patch.object(gcal_mod.Credentials, "from_authorized_user_file",
                          return_value=creds), \
             patch.object(gcal_mod.InstalledAppFlow,
                          "from_client_secrets_file") as from_file, \
             patch.object(gcal_mod, "build", return_value="svc"):
            flow = Mock()
            flow.authorization_url.return_value = ("http://auth", "st")
            flow.fetch_token.return_value = None
            flow.credentials = _Creds(valid=True)
            from_file.return_value = flow
            with patch("wsgiref.simple_server.make_server") as make_server, \
                 patch("webbrowser.open"):
                httpd = Mock()
                app = None

                def _capture_app(*args, **kwargs):
                    nonlocal app
                    app = args[2]
                    return httpd
                make_server.side_effect = _capture_app
                httpd.handle_request = Mock(side_effect=lambda: app(
                    {"QUERY_STRING": "code=abc"}, Mock()))
                assert svc.authenticate() is True
        flow.fetch_token.assert_called_once_with(code="abc")
        assert svc.service == "svc"

    def test_client_config_json_string_flow(self, tmp_path):
        svc = _svc(credentials_json='{"installed": {"client_id": "x"}}',
                   token_file=str(tmp_path / "tok.json"))
        with patch("os.path.exists", return_value=False), \
             patch("os.path.isfile", return_value=False), \
             patch.object(gcal_mod.InstalledAppFlow,
                          "from_client_config") as from_config, \
             patch.object(gcal_mod, "build", return_value="svc"):
            flow = Mock()
            flow.authorization_url.return_value = ("http://auth", "st")
            flow.fetch_token.return_value = None
            flow.credentials = _Creds(valid=True)
            from_config.return_value = flow
            with patch("wsgiref.simple_server.make_server") as make_server, \
                 patch("webbrowser.open"):
                httpd = Mock()
                app = None

                def _capture_app(*args, **kwargs):
                    nonlocal app
                    app = args[2]
                    return httpd
                make_server.side_effect = _capture_app
                httpd.handle_request = Mock(side_effect=lambda: app(
                    {"QUERY_STRING": "code=authcode123"}, Mock()))
                assert svc.authenticate() is True
        from_config.assert_called_once()
        assert flow.redirect_uri == "http://localhost:8080"
        environ = {"QUERY_STRING": "nope=1"}
        start = Mock()
        status = None
        def _start(s, h):
            nonlocal status
            status = s
        response = app(environ, _start)
        assert status == "404 Not Found"
        assert response == [b"Not Found"]
        flow.fetch_token.assert_called_once_with(code="authcode123")

    def test_oauth_flow_catches_auth_code(self, tmp_path):
        svc = _svc(credentials_json='{"installed": {}}',
                   token_file=str(tmp_path / "tok.json"))
        with patch("os.path.exists", return_value=False), \
             patch("os.path.isfile", return_value=False), \
             patch.object(gcal_mod.InstalledAppFlow,
                          "from_client_config") as from_config, \
             patch.object(gcal_mod, "build", return_value="svc"):
            flow = Mock()
            flow.authorization_url.return_value = ("http://auth", "st")
            flow.fetch_token.return_value = None
            flow.credentials = _Creds(valid=True)
            from_config.return_value = flow
            with patch("wsgiref.simple_server.make_server") as make_server, \
                 patch("webbrowser.open"):
                httpd = Mock()
                app = None

                def _capture_app(*args, **kwargs):
                    nonlocal app
                    app = args[2]
                    return httpd
                make_server.side_effect = _capture_app
                httpd.handle_request = Mock(side_effect=lambda: app(
                    {"QUERY_STRING": "code=abc"}, Mock()))
                assert svc.authenticate() is True
        flow.fetch_token.assert_called_once_with(code="abc")
        assert (tmp_path / "tok.json").exists()

    def test_oauth_flow_no_auth_code_fails(self, tmp_path):
        svc = _svc(credentials_json='{"installed": {}}',
                   token_file=str(tmp_path / "tok.json"))
        with patch("os.path.exists", return_value=False), \
             patch("os.path.isfile", return_value=False), \
             patch.object(gcal_mod.InstalledAppFlow,
                          "from_client_config") as from_config, \
             patch.object(gcal_mod, "build") as build:
            flow = Mock()
            flow.authorization_url.return_value = ("http://auth", "st")
            from_config.return_value = flow
            with patch("wsgiref.simple_server.make_server") as make_server, \
                 patch("webbrowser.open"):
                make_server.return_value = Mock()
                assert svc.authenticate() is False
        build.assert_not_called()

    def test_oauth_port_in_use_fails(self, tmp_path):
        svc = _svc(credentials_json='{"installed": {}}',
                   token_file=str(tmp_path / "tok.json"))
        with patch("os.path.exists", return_value=False), \
             patch("os.path.isfile", return_value=False), \
             patch.object(gcal_mod.InstalledAppFlow,
                          "from_client_config") as from_config, \
             patch.object(gcal_mod, "build") as build:
            flow = Mock()
            flow.authorization_url.return_value = ("http://auth", "st")
            from_config.return_value = flow
            with patch("wsgiref.simple_server.make_server",
                       side_effect=OSError("port in use")), \
                 patch("webbrowser.open"):
                assert svc.authenticate() is False
        build.assert_not_called()

    def test_authenticate_save_failure_false(self, tmp_path):
        svc = _svc(credentials_json='{"installed": {}}',
                   token_file=str(tmp_path / "tok.json"))
        with patch("os.path.exists", return_value=False), \
             patch("os.path.isfile", return_value=False), \
             patch.object(gcal_mod.InstalledAppFlow,
                          "from_client_config") as from_config, \
             patch.object(gcal_mod, "build") as build:
            flow = Mock()
            flow.authorization_url.return_value = ("http://auth", "st")
            flow.credentials = _Creds(valid=True)
            from_config.return_value = flow
            with patch("wsgiref.simple_server.make_server") as make_server, \
                 patch("webbrowser.open"), \
                 patch("builtins.open", side_effect=OSError("no write")):
                make_server.return_value = Mock()
                assert svc.authenticate() is False
        build.assert_not_called()


class TestCalendarsAndEvents:
    def test_list_calendars_success(self):
        svc = _svc()
        svc.service = Mock()
        svc.service.calendarList.return_value.list.return_value.execute.return_value = {
            "items": [{"id": "primary"}]}
        result = asyncio.run(svc.list_calendars())
        assert result == [{"id": "primary"}]

    def test_list_calendars_no_service(self):
        svc = _svc()
        with patch.object(svc, "_get_service_with_token", return_value=None):
            assert asyncio.run(svc.list_calendars()) == []

    def test_list_calendars_exception(self):
        svc = _svc()
        svc.service = Mock()
        svc.service.calendarList.return_value.list.side_effect = RuntimeError("boom")
        assert asyncio.run(svc.list_calendars()) == []

    def test_get_events_apis_unavailable(self):
        svc = _svc()
        with patch.object(gcal_mod, "GOOGLE_APIS_AVAILABLE", False):
            assert asyncio.run(svc.get_events()) == []

    def test_get_events_no_service(self):
        svc = _svc()
        with patch.object(svc, "_get_service_with_token", return_value=None):
            assert asyncio.run(svc.get_events()) == []

    def test_get_events_aware_datetimes(self):
        svc = _svc()
        service = Mock()
        execute = Mock(return_value={"items": [{"id": "e1", "summary": "Meet",
                                                "start": {"dateTime": "2026-01-01T10:00:00Z"},
                                                "end": {"dateTime": "2026-01-01T11:00:00Z"}}]})
        service.events.return_value.list.return_value.execute = execute
        with patch.object(svc, "_get_service_with_token", return_value=service):
            events = asyncio.run(svc.get_events(
                time_min=datetime(2026, 1, 1, tzinfo=timezone.utc),
                time_max=datetime(2026, 1, 8, tzinfo=timezone.utc)))
        assert events[0]["title"] == "Meet"
        kwargs = service.events.return_value.list.call_args[1]
        assert kwargs["timeMin"] == "2026-01-01T00:00:00Z"
        assert kwargs["timeMax"] == "2026-01-08T00:00:00Z"
        assert kwargs["singleEvents"] is True
        assert kwargs["orderBy"] == "startTime"

    def test_get_events_naive_datetimes_defaults(self):
        svc = _svc()
        service = Mock()
        service.events.return_value.list.return_value.execute.return_value = {"items": []}
        with patch.object(svc, "_get_service_with_token", return_value=service):
            asyncio.run(svc.get_events(time_min=datetime(2026, 1, 1),
                                       time_max=datetime(2026, 1, 2)))
        kwargs = service.events.return_value.list.call_args[1]
        assert kwargs["timeMin"] == "2026-01-01T00:00:00Z"
        assert kwargs["timeMax"] == "2026-01-02T00:00:00Z"

    def test_get_events_defaults_to_week(self):
        svc = _svc()
        service = Mock()
        service.events.return_value.list.return_value.execute.return_value = {"items": []}
        with patch.object(svc, "_get_service_with_token", return_value=service), \
             patch("integrations.google_calendar_service.datetime") as m_dt:
            m_dt.now.return_value = datetime(2026, 1, 1, tzinfo=timezone.utc)
            m_dt.utcnow.return_value = datetime(2026, 1, 1)
            m_dt.timedelta = timedelta
            asyncio.run(svc.get_events())
        kwargs = service.events.return_value.list.call_args[1]
        assert kwargs["timeMin"] == "2026-01-01T00:00:00Z"
        assert kwargs["timeMax"] == "2026-01-08T00:00:00Z"

    def test_get_events_http_error(self):
        svc = _svc()
        service = Mock()
        service.events.return_value.list.side_effect = gcal_mod.HttpError(
            Mock(status=429), b"rate limited", None)
        with patch.object(svc, "_get_service_with_token", return_value=service):
            assert asyncio.run(svc.get_events()) == []

    def test_create_event_success(self):
        svc = _svc()
        service = Mock()
        created = {"id": "e1", "summary": "T", "start": {"dateTime": "X"},
                   "end": {"dateTime": "Y"}}
        service.events.return_value.insert.return_value.execute.return_value = created
        with patch.object(svc, "_get_service_with_token", return_value=service):
            result = asyncio.run(svc.create_event(
                {"title": "T", "start_time": "X", "end_time": "Y"}))
        assert result["id"] == "e1"
        body = service.events.return_value.insert.call_args[1]["body"]
        assert body["summary"] == "T"

    def test_create_event_no_service(self):
        svc = _svc()
        with patch.object(svc, "_get_service_with_token", return_value=None):
            assert asyncio.run(svc.create_event({})) is None

    def test_create_event_http_error(self):
        svc = _svc()
        service = Mock()
        service.events.return_value.insert.side_effect = gcal_mod.HttpError(
            Mock(status=400), b"bad", None)
        with patch.object(svc, "_get_service_with_token", return_value=service):
            assert asyncio.run(svc.create_event({})) is None

    def test_update_event_full(self):
        svc = _svc()
        svc.service = Mock()
        existing = {"id": "e1", "summary": "Old", "start": {"dateTime": "S"},
                    "end": {"dateTime": "E"}}
        svc.service.events.return_value.get.return_value.execute.return_value = existing
        svc.service.events.return_value.update.return_value.execute.return_value = dict(
            existing, summary="New", description="D",
            start={"dateTime": "S2", "timeZone": "UTC"},
            end={"dateTime": "E2", "timeZone": "UTC"})
        result = asyncio.run(svc.update_event(
            "e1", {"title": "New", "description": "D", "start_time": "S2",
                   "end_time": "E2"}))
        assert result["title"] == "New"
        updated_body = svc.service.events.return_value.update.call_args[1]["body"]
        assert updated_body["description"] == "D"
        assert updated_body["start"] == {"dateTime": "S2", "timeZone": "UTC"}

    def test_update_event_no_auth(self):
        svc = _svc()
        with patch.object(svc, "authenticate", return_value=False):
            assert asyncio.run(svc.update_event("e1", {})) is None

    def test_update_event_http_error(self):
        svc = _svc()
        svc.service = Mock()
        svc.service.events.return_value.get.side_effect = gcal_mod.HttpError(
            Mock(status=404), b"nope", None)
        assert asyncio.run(svc.update_event("e1", {})) is None

    def test_delete_event_success(self):
        svc = _svc()
        svc.service = Mock()
        svc.service.events.return_value.delete.return_value.execute.return_value = {}
        assert asyncio.run(svc.delete_event("e1")) is True

    def test_delete_event_no_auth(self):
        svc = _svc()
        with patch.object(svc, "authenticate", return_value=False):
            assert asyncio.run(svc.delete_event("e1")) is False

    def test_delete_event_http_error(self):
        svc = _svc()
        svc.service = Mock()
        svc.service.events.return_value.delete.side_effect = gcal_mod.HttpError(
            Mock(status=500), b"x", None)
        assert asyncio.run(svc.delete_event("e1")) is False


class TestConflicts:
    def test_conflict_found(self):
        svc = _svc()
        svc.service = Mock()
        events = [{"id": "e1", "title": "Busy", "start_time": "2026-01-01T10:00:00Z",
                   "end_time": "2026-01-01T11:00:00Z"}]
        with patch.object(svc, "get_events", return_value=events):
            result = asyncio.run(svc.check_conflicts(
                datetime(2026, 1, 1, 10, 30, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)))
        assert result["has_conflicts"] is True
        assert result["conflict_count"] == 1
        assert result["conflicts"][0]["event_id"] == "e1"

    def test_no_conflict(self):
        svc = _svc()
        svc.service = Mock()
        with patch.object(svc, "get_events", return_value=[]):
            result = asyncio.run(svc.check_conflicts(
                datetime(2026, 1, 1, 10, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 11, tzinfo=timezone.utc)))
        assert result["has_conflicts"] is False
        assert result["success"] is True

    def test_naive_times_coerced_to_utc(self):
        svc = _svc()
        svc.service = Mock()
        events = [{"id": "e1", "title": "B", "start_time": "2026-01-01T09:30:00Z",
                   "end_time": "2026-01-01T10:30:00Z"}]
        with patch.object(svc, "get_events", return_value=events):
            result = asyncio.run(svc.check_conflicts(
                datetime(2026, 1, 1, 10, 0), datetime(2026, 1, 1, 11, 0)))
        assert result["has_conflicts"] is True

    def test_all_day_date_only_events(self):
        svc = _svc()
        svc.service = Mock()
        events = [{"id": "e1", "title": "AllDay", "start_time": "2026-01-01",
                   "end_time": "2026-01-02"}]
        with patch.object(svc, "get_events", return_value=events):
            result = asyncio.run(svc.check_conflicts(
                datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 13, 0, tzinfo=timezone.utc)))
        assert result["has_conflicts"] is True

    def test_not_authenticated(self):
        svc = _svc()
        with patch.object(svc, "authenticate", return_value=False):
            result = asyncio.run(svc.check_conflicts(
                datetime(2026, 1, 1), datetime(2026, 1, 2)))
        assert result == {"has_conflicts": False, "conflicts": [],
                          "error": "Not authenticated"}

    def test_exception_returns_safe_error(self):
        svc = _svc()
        svc.service = Mock()
        with patch.object(svc, "get_events",
                         side_effect=RuntimeError("boom-secret")):
            result = asyncio.run(svc.check_conflicts(
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                datetime(2026, 1, 2, tzinfo=timezone.utc)))
        assert result["success"] is False
        assert result["error"] == "Failed to check conflicts"
        assert "boom-secret" not in str(result)


class TestHelpers:
    def test_parse_event_time_iso(self):
        parsed = gcal_mod.GoogleCalendarService._parse_event_time(
            None, "2026-01-01T09:30:00Z")
        assert parsed == datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)

    def test_parse_event_time_naive(self):
        parsed = gcal_mod.GoogleCalendarService._parse_event_time(
            None, "2026-01-01T09:30:00")
        assert parsed.tzinfo == timezone.utc

    def test_parse_event_time_date_only(self):
        parsed = gcal_mod.GoogleCalendarService._parse_event_time(
            None, "2026-01-01")
        assert parsed == datetime(2026, 1, 1, tzinfo=timezone.utc)

    def test_convert_google_to_unified_date_time(self):
        svc = _svc()
        unified = svc._convert_google_to_unified({
            "id": "e1", "summary": "Meet", "description": "D",
            "start": {"dateTime": "2026-01-01T10:00:00Z"},
            "end": {"dateTime": "2026-01-01T11:00:00Z"},
            "attendees": [{"email": "a@x.com"}], "location": "Room",
            "created": "c", "updated": "u"})
        assert unified["title"] == "Meet"
        assert unified["attendees"] == ["a@x.com"]
        assert unified["platform"] == "google_calendar"

    def test_convert_google_to_unified_all_day(self):
        svc = _svc()
        unified = svc._convert_google_to_unified({
            "id": "e1", "start": {"date": "2026-01-01"},
            "end": {"date": "2026-01-02"}})
        assert unified["start_time"] == "2026-01-01"
        assert unified["title"] == "Untitled Event"

    def test_convert_unified_to_google_full(self):
        svc = _svc()
        g = svc._convert_unified_to_google({
            "title": "T", "description": "D", "start_time": "S", "end_time": "E",
            "location": "L", "attendees": ["a@x.com"]})
        assert g["summary"] == "T"
        assert g["location"] == "L"
        assert g["attendees"] == [{"email": "a@x.com"}]

    def test_convert_unified_to_google_minimal(self):
        svc = _svc()
        g = svc._convert_unified_to_google({"start_time": "S", "end_time": "E"})
        assert g["summary"] == "Untitled Event"
        assert "attendees" not in g


class TestSyncAndCapabilities:
    @pytest.fixture()
    def db_session(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine)()
        yield session
        session.close()

    def test_sync_success_create(self, db_session):
        svc = _svc()
        with patch.object(svc, "get_events", new=AsyncMock(return_value=[{"id": "e1"}])), \
             patch("core.database.SessionLocal", return_value=db_session):
            result = asyncio.run(svc.sync_to_postgres_cache("ws-1"))
        assert result == {"success": True, "metrics_synced": 1}
        from core.models import IntegrationMetric
        rows = db_session.query(IntegrationMetric).all()
        assert len(rows) == 1
        assert rows[0].workspace_id == "ws-1"
        assert rows[0].metric_key == "google_calendar_event_count"
        assert rows[0].value == 1.0

    def test_sync_updates_existing(self, db_session):
        from core.models import IntegrationMetric
        db_session.add(IntegrationMetric(
            workspace_id="ws-1", integration_type="google_calendar",
            metric_key="google_calendar_event_count", value=9.0, unit="count"))
        db_session.commit()
        svc = _svc()
        with patch.object(svc, "get_events", new=AsyncMock(return_value=[])), \
             patch("core.database.SessionLocal", return_value=db_session):
            result = asyncio.run(svc.sync_to_postgres_cache("ws-1"))
        assert result["success"] is True
        row = db_session.query(IntegrationMetric).filter_by(
            metric_key="google_calendar_event_count").first()
        assert row.value == 0.0

    def test_sync_event_fetch_failure_tolerated(self, db_session):
        svc = _svc()
        with patch.object(svc, "get_events",
                          new=AsyncMock(side_effect=RuntimeError("boom"))), \
             patch("core.database.SessionLocal", return_value=db_session):
            result = asyncio.run(svc.sync_to_postgres_cache("ws-1"))
        assert result["success"] is True
        from core.models import IntegrationMetric
        assert db_session.query(IntegrationMetric).first().value == 0.0

    def test_sync_db_error_rollback(self, db_session):
        svc = _svc()
        with patch.object(svc, "get_events", new=AsyncMock(return_value=[])), \
             patch("core.database.SessionLocal", return_value=db_session), \
             patch("core.models.IntegrationMetric",
                   side_effect=RuntimeError("db exploded")):
            result = asyncio.run(svc.sync_to_postgres_cache("ws-1"))
        assert result["success"] is False
        assert "db exploded" not in result["error"]

    def test_sync_outer_error(self, db_session):
        svc = _svc()
        with patch("core.database.SessionLocal",
                   side_effect=RuntimeError("session-secret")), \
             patch.object(svc, "get_events", new=AsyncMock(return_value=[])):
            result = asyncio.run(svc.sync_to_postgres_cache("ws-1"))
        assert result["success"] is False
        assert "session-secret" not in result["error"]

    def test_full_sync(self, db_session):
        svc = _svc()
        with patch.object(svc, "get_events", new=AsyncMock(return_value=[])), \
             patch("core.database.SessionLocal", return_value=db_session):
            result = asyncio.run(svc.full_sync("ws-1"))
        assert result["success"] is True
        assert result["postgres_cache"]["success"] is True

    def test_get_capabilities(self):
        caps = _svc().get_capabilities()
        assert "get_events" in caps["operations"]
        assert caps["authentication"] == "oauth"

    def test_health_check_healthy(self):
        svc = _svc()
        with patch.object(svc, "authenticate", return_value=True):
            result = svc.health_check()
        assert result["status"] == "healthy"

    def test_health_check_unhealthy(self):
        svc = _svc()
        with patch.object(svc, "authenticate", return_value=False):
            result = svc.health_check()
        assert result["status"] == "unhealthy"

    def test_health_check_exception(self):
        svc = _svc()
        with patch.object(svc, "authenticate",
                         side_effect=RuntimeError("boom-secret")):
            result = svc.health_check()
        assert result["status"] == "unhealthy"
        assert "boom-secret" not in str(result)


class TestExecuteOperation:
    def test_execute_get_events(self):
        svc = _svc()
        with patch.object(svc, "get_events", new=AsyncMock(return_value=[])) as m:
            result = asyncio.run(svc.execute_operation(
                "get_events", {"calendar_id": "c1", "max_results": 5}))
        assert result == {"success": True, "data": []}
        assert m.call_args[1]["calendar_id"] == "c1"

    def test_execute_create_event(self):
        svc = _svc()
        with patch.object(svc, "create_event",
                          new=AsyncMock(return_value={"id": "e1"})):
            result = asyncio.run(svc.execute_operation(
                "create_event", {"event_data": {"title": "T"}}))
        assert result["success"] is True

    def test_execute_create_event_failure(self):
        svc = _svc()
        with patch.object(svc, "create_event", new=AsyncMock(return_value=None)):
            result = asyncio.run(svc.execute_operation(
                "create_event", {"event_data": {}}))
        assert result["success"] is False

    def test_execute_update_event(self):
        svc = _svc()
        with patch.object(svc, "update_event",
                          new=AsyncMock(return_value={"id": "e1"})):
            result = asyncio.run(svc.execute_operation(
                "update_event", {"event_id": "e1", "updates": {"title": "T"}}))
        assert result["success"] is True

    def test_execute_delete_event(self):
        svc = _svc()
        with patch.object(svc, "delete_event", new=AsyncMock(return_value=True)):
            result = asyncio.run(svc.execute_operation(
                "delete_event", {"event_id": "e1"}))
        assert result == {"success": True}

    def test_execute_check_conflicts(self):
        svc = _svc()
        with patch.object(svc, "check_conflicts",
                          new=AsyncMock(return_value={"has_conflicts": False})):
            result = asyncio.run(svc.execute_operation(
                "check_conflicts", {"start_time": "S", "end_time": "E"}))
        assert result == {"success": True, "data": {"has_conflicts": False}}

    def test_execute_unknown_operation(self):
        result = asyncio.run(_svc().execute_operation("nuke", {}))
        assert result["success"] is False
        assert "Unknown operation" in result["error"]

    def test_execute_tenant_mismatch(self):
        svc = _svc()
        result = asyncio.run(svc.execute_operation(
            "get_events", {}, context={"tenant_id": "other"}))
        assert result["success"] is False
        assert result["error"] == "Tenant ID mismatch"

    def test_execute_exception_no_leak(self):
        svc = _svc()
        with patch.object(svc, "get_events",
                          new=AsyncMock(side_effect=RuntimeError("secret-73"))):
            result = asyncio.run(svc.execute_operation("get_events", {}))
        assert result["success"] is False
        assert result["error"] == "Google Calendar operation failed"
        assert "secret-73" not in str(result)
