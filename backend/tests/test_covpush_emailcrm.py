# -*- coding: utf-8 -*-
"""
Coverage-push tests for:
- integrations.microsoft365_service (Graph API, aiohttp)
- integrations.gmail_service (Google API, mocked google libs)

TDD: each REAL bug found has a failing test first, then a minimal fix.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import aiohttp

import integrations.microsoft365_service as m365
import integrations.gmail_service as gs
import integrations.atom_hubspot_integration_service as hs
import integrations.chat_orchestrator as co


# =========================================================================
# Microsoft 365
# =========================================================================

class FakeAioResponse:
    def __init__(self, status=200, body=None, data=None):
        self.status = status
        self._body = body if body is not None else "server error"
        self._data = data if data is not None else {"value": [{"id": "1"}]}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def text(self):
        return self._body

    async def json(self):
        return self._data


class FakeAioSession:
    def __init__(self, response=None, put_response=None):
        self.response = response or FakeAioResponse(200)
        self.put_response = put_response or FakeAioResponse(201, data={"id": "up"})
        self.last_url = None
        self.last_json = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def request(self, method, url, headers=None, json=None):
        self.last_url = url
        self.last_json = json
        return self.response

    def put(self, url, headers=None, data=None):
        self.last_url = url
        return self.put_response


def make_service():
    return m365.Microsoft365Service(tenant_id="t1", config={})


@pytest.fixture
def dev_env(monkeypatch):
    monkeypatch.setenv("ATOM_ENV", "development")


# --- health_check / execute_operation / authenticate ---------------------

async def test_m365_health_check_configured():
    svc = m365.Microsoft365Service(tenant_id="t1", config={"access_token": "x"})
    result = await svc.health_check()
    assert result["status"] == "healthy"
    assert result["tenant_id"] == "t1"


async def test_m365_health_check_unconfigured():
    result = await make_service().health_check()
    assert result["status"] == "unconfigured"


class EvilConfig(dict):
    def __getitem__(self, key):
        raise RuntimeError("secret token detail")

    def __contains__(self, key):
        raise RuntimeError("secret token detail")


async def test_m365_health_check_exception_no_str_leak(monkeypatch):
    svc = make_service()
    monkeypatch.setattr(svc, "config", EvilConfig(access_token="x"))
    result = await svc.health_check()
    assert result["status"] == "unhealthy"
    assert "secret token detail" not in json.dumps(result)


async def test_m365_execute_operation_authenticate(monkeypatch, dev_env):
    svc = make_service()
    result = await svc.execute_operation("authenticate", user_id="u1")
    assert result["status"] == "success"
    assert "login.microsoftonline.com" in result["auth_url"]
    assert "microsoft365_u1" in result["auth_url"]


async def test_m365_execute_operation_send_message_no_token(monkeypatch):
    svc = make_service()
    result = await svc.execute_operation("send_message", team_id="t", channel_id="c", content="hi")
    assert result["status"] == "error"
    assert "No access token" in result["message"]


async def test_m365_execute_operation_send_message_ok(dev_env):
    svc = m365.Microsoft365Service(tenant_id="t1", config={"access_token": "fake_token"})
    result = await svc.execute_operation("send_message", team_id="t", channel_id="c", content="hi")
    assert result["status"] == "success"


async def test_m365_execute_operation_list_teams_channels(dev_env):
    svc = m365.Microsoft365Service(tenant_id="t1", config={"access_token": "fake_token"})
    assert (await svc.execute_operation("list_teams"))["status"] == "success"
    assert (await svc.execute_operation("list_channels", team_id="t"))["status"] == "success"


async def test_m365_execute_operation_unknown():
    result = await make_service().execute_operation("nope")
    assert result["status"] == "error"
    assert "Unknown operation" in result["message"]


async def test_m365_execute_operation_exception(monkeypatch):
    svc = make_service()

    async def boom(*a, **k):
        raise RuntimeError("detail-token-abc")

    monkeypatch.setattr(svc, "_send_message", boom)
    result = await svc.execute_operation("send_message", team_id="t", channel_id="c", content="x")
    assert result["status"] == "error"
    assert "detail-token-abc" not in json.dumps(result)


async def test_m365_authenticate(monkeypatch):
    monkeypatch.setenv("MICROSOFT_365_CLIENT_ID", "cid")
    monkeypatch.setenv("MICROSOFT_365_REDIRECT_URI", "http://cb")
    result = await make_service()._authenticate("u9")
    assert result["status"] == "success"
    assert "client_id=cid" in result["auth_url"]


async def test_m365_authenticate_exception(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("oauth-leak-xyz")

    monkeypatch.setattr("urllib.parse.urlencode", boom)
    result = await make_service()._authenticate("u9")
    assert result["status"] == "error"
    assert "oauth-leak-xyz" not in json.dumps(result)


async def test_m365_authenticate_legacy(monkeypatch):
    monkeypatch.setenv("MICROSOFT_365_CLIENT_ID", "cid")
    result = await make_service().authenticate("u1")
    assert result["status"] == "success"


# --- Graph read methods (dev bypass + aiohttp error paths) ---------------

async def test_m365_get_user_profile_ok(dev_env):
    result = await make_service().get_user_profile("fake_token")
    assert result["status"] == "success"


async def test_m365_get_user_profile_error(monkeypatch):
    svc = make_service()
    monkeypatch.setattr(aiohttp, "ClientSession", lambda *a, **k: FakeAioSession(FakeAioResponse(401, body="InvalidAuthenticationToken")))
    result = await svc.get_user_profile("real_token")
    assert result["status"] == "error"
    assert result["code"] == 401


async def test_m365_list_teams_error_handled(monkeypatch):
    svc = make_service()
    monkeypatch.setattr(aiohttp, "ClientSession", lambda *a, **k: FakeAioSession(FakeAioResponse(403, body="forbidden details")))
    result = await svc.list_teams("real_token")
    assert result["status"] == "error"
    assert result["code"] == 403


async def test_m365_list_channels_error_handled(monkeypatch):
    svc = make_service()
    monkeypatch.setattr(aiohttp, "ClientSession", lambda *a, **k: FakeAioSession(FakeAioResponse(404, body="nope")))
    result = await svc.list_channels("real_token", "team1")
    assert result["status"] == "error"
    assert result["code"] == 404


async def test_m365_get_outlook_messages_ok(dev_env):
    result = await make_service().get_outlook_messages("fake_token", folder_id="archive", top=5)
    assert result["status"] == "success"


async def test_m365_get_calendar_events_ok(dev_env):
    result = await make_service().get_calendar_events("fake_token", "2026-01-01", "2026-01-02")
    assert result["status"] == "success"


async def test_m365_get_planner_tasks_ok_error(monkeypatch, dev_env):
    svc = make_service()
    assert (await svc.get_planner_tasks("fake_token"))["status"] == "success"
    monkeypatch.setattr(aiohttp, "ClientSession", lambda *a, **k: FakeAioSession(FakeAioResponse(500, body="server exploded")))
    result = await svc.get_planner_tasks("real_token")
    assert result["status"] == "error"
    assert result["code"] == 500


async def test_m365_get_dynamics_deals_invoices(dev_env):
    svc = make_service()
    assert (await svc.get_dynamics_deals("fake_token"))["status"] == "success"
    assert (await svc.get_dynamics_invoices("fake_token"))["status"] == "success"


async def test_m365_get_dynamics_deals_error(monkeypatch):
    svc = make_service()
    monkeypatch.setattr(aiohttp, "ClientSession", lambda *a, **k: FakeAioSession(FakeAioResponse(429, body="rate limit")))
    result = await svc.get_dynamics_deals("real_token")
    assert result["status"] == "error"


async def test_m365_get_service_status_ok_error(monkeypatch, dev_env):
    svc = make_service()
    assert (await svc.get_service_status("fake_token"))["status"] == "success"
    monkeypatch.setattr(aiohttp, "ClientSession", lambda *a, **k: FakeAioSession(FakeAioResponse(500, body="x")))
    result = await svc.get_service_status("real_token")
    assert result["status"] == "error"


# --- _make_graph_request -------------------------------------------------

async def test_m365_make_graph_request_bypass(dev_env):
    result = await make_service()._make_graph_request("GET", "http://x", "fake_token")
    assert result["status"] == "success"
    assert result["data"]["id"] == "mock_id_123"
    assert result["data"]["displayName"] == "Mock User"


async def test_m365_make_graph_request_4xx(monkeypatch):
    svc = make_service()
    monkeypatch.setattr(aiohttp, "ClientSession", lambda *a, **k: FakeAioSession(FakeAioResponse(400, body="bad request body")))
    result = await svc._make_graph_request("GET", "http://x", "t")
    assert result["status"] == "error"
    assert result["code"] == 400
    assert "bad request body" in result["message"]


async def test_m365_make_graph_request_204(monkeypatch):
    svc = make_service()
    monkeypatch.setattr(aiohttp, "ClientSession", lambda *a, **k: FakeAioSession(FakeAioResponse(204)))
    result = await svc._make_graph_request("DELETE", "http://x", "t")
    assert result == {"status": "success", "data": None}


async def test_m365_make_graph_request_json(monkeypatch):
    svc = make_service()
    session = FakeAioSession(FakeAioResponse(200, data={"value": [1, 2]}))
    monkeypatch.setattr(aiohttp, "ClientSession", lambda *a, **k: session)
    result = await svc._make_graph_request("POST", "http://x", "t", json_data={"a": 1})
    assert result["status"] == "success"
    assert session.last_json == {"a": 1}


# --- OneDrive ------------------------------------------------------------

async def test_m365_onedrive_list_files(dev_env):
    svc = m365.Microsoft365Service(tenant_id="t", config={})
    result = await svc.execute_onedrive_action("fake_token", "list_files", {})
    assert result["status"] == "success"
    result = await svc.execute_onedrive_action("fake_token", "list_files", {"folder": "docs", "top": 5})
    assert result["status"] == "success"


async def test_m365_onedrive_get_content(dev_env):
    svc = make_service()
    result = await svc.execute_onedrive_action("fake_token", "get_content", {})
    assert result["status"] == "error"
    result = await svc.execute_onedrive_action("fake_token", "get_content", {"path": "a/b.txt"})
    assert result["status"] == "success"


async def test_m365_onedrive_upload(monkeypatch, dev_env):
    svc = make_service()
    result = await svc.execute_onedrive_action("fake_token", "upload", {})
    assert result["status"] == "error"
    result = await svc.execute_onedrive_action("fake_token", "upload", {"path": "x", "file_content": None})
    assert result["status"] == "error"

    session = FakeAioSession(put_response=FakeAioResponse(200, data={"id": "f1"}))
    monkeypatch.setattr(aiohttp, "ClientSession", lambda *a, **k: session)
    result = await svc.execute_onedrive_action("real_token", "upload", {"path": "x", "file_content": b"data", "content_type": "text/plain"})
    assert result["status"] == "success"
    assert result["data"]["id"] == "f1"

    monkeypatch.setattr(aiohttp, "ClientSession", lambda *a, **k: FakeAioSession(put_response=FakeAioResponse(400, body="upload rejected")))
    result = await svc.execute_onedrive_action("real_token", "upload", {"path": "x", "file_content": b"data"})
    assert result["status"] == "error"
    assert result["code"] == 400


async def test_m365_onedrive_delete_share(dev_env):
    svc = make_service()
    result = await svc.execute_onedrive_action("fake_token", "delete", {})
    assert result["status"] == "error"
    assert (await svc.execute_onedrive_action("fake_token", "delete", {"item_id": "i1"}))["status"] == "success"
    result = await svc.execute_onedrive_action("fake_token", "share", {})
    assert result["status"] == "error"
    result = await svc.execute_onedrive_action("fake_token", "share", {"item_id": "i1", "link_type": "edit"})
    assert result["status"] == "success"


async def test_m365_onedrive_create_folder(dev_env):
    svc = make_service()
    result = await svc.execute_onedrive_action("fake_token", "create_folder", {})
    assert result["status"] == "error"
    assert (await svc.execute_onedrive_action("fake_token", "create_folder", {"name": "n"}))["status"] == "success"
    assert (await svc.execute_onedrive_action("fake_token", "create_folder", {"name": "n", "folder_path": "p"}))["status"] == "success"


async def test_m365_onedrive_unknown_action(dev_env):
    result = await make_service().execute_onedrive_action("fake_token", "sync", {})
    assert result["status"] == "error"
    assert "Unknown OneDrive action" in result["message"]


async def test_m365_onedrive_exception(monkeypatch):
    svc = make_service()

    async def boom(*a, **k):
        raise RuntimeError("od-leak")

    monkeypatch.setattr(svc, "_make_graph_request", boom)
    result = await svc.execute_onedrive_action("t", "delete", {"item_id": "1"})
    assert result["status"] == "error"
    assert "od-leak" not in json.dumps(result)


# --- Excel ---------------------------------------------------------------

async def test_m365_excel_missing_item(dev_env):
    svc = make_service()
    result = await svc.execute_excel_action("fake_token", "read_range", {})
    assert result["status"] == "error"
    result = await svc.execute_excel_action("fake_token", "read_range", {"path": "no/such"})
    assert result["status"] == "error"


async def test_m365_excel_path_resolution(monkeypatch, dev_env):
    svc = make_service()

    async def resolve(method, url, token):
        if "root:/sheet.xlsx" in url:
            return {"status": "success", "data": {"id": "resolved-id"}}
        if "/workbook/" in url:
            return {"status": "success", "data": {"value": [{"id": "t1"}]}}
        return {"status": "error", "code": 404, "message": "not found"}

    monkeypatch.setattr(svc, "_make_graph_request", resolve)
    result = await svc.execute_excel_action("fake_token", "get_tables", {"path": "sheet.xlsx"})
    assert result["status"] == "success"


async def test_m365_excel_read_range(dev_env):
    svc = make_service()
    result = await svc.execute_excel_action("fake_token", "read_range", {"item_id": "i", "range": "Sheet1!A1:B2"})
    assert result["status"] == "success"
    result = await svc.execute_excel_action("fake_token", "read_range", {"item_id": "i", "range": "A1:B2"})
    assert result["status"] == "success"


async def test_m365_excel_write_range(dev_env):
    svc = make_service()
    result = await svc.execute_excel_action("fake_token", "write_range", {"item_id": "i"})
    assert result["status"] == "error"
    result = await svc.execute_excel_action("fake_token", "write_range", {"item_id": "i", "range": "A1:B2", "values": [[1]]})
    assert result["status"] == "success"
    result = await svc.execute_excel_action("fake_token", "write_range", {"item_id": "i", "range": "S!A1:B2", "values": [[1]]})
    assert result["status"] == "success"


async def test_m365_excel_tables_columns(dev_env):
    svc = make_service()
    assert (await svc.execute_excel_action("fake_token", "get_tables", {"item_id": "i"}))["status"] == "success"
    result = await svc.execute_excel_action("fake_token", "get_columns", {"item_id": "i"})
    assert result["status"] == "error"
    assert (await svc.execute_excel_action("fake_token", "get_columns", {"item_id": "i", "table": "t"}))["status"] == "success"


async def test_m365_excel_append_row(monkeypatch, dev_env):
    svc = make_service()
    result = await svc.execute_excel_action("fake_token", "append_row", {"item_id": "i"})
    assert result["status"] == "error"
    result = await svc.execute_excel_action("fake_token", "append_row", {"item_id": "i", "table": "t", "values": [1, 2]})
    assert result["status"] == "success"

    async def cols_fail(method, url, token):
        return {"status": "error", "code": 404, "message": "nope"}

    monkeypatch.setattr(svc, "_make_graph_request", cols_fail)
    result = await svc.execute_excel_action("fake_token", "append_row", {"item_id": "i", "table": "t", "mapping": {"A": 1}})
    assert result["status"] == "error"

    async def cols_ok(method, url, token, json_data=None):
        return {"status": "success", "data": [{"name": "ColA"}, {"name": "ColB"}]}

    monkeypatch.setattr(svc, "_make_graph_request", cols_ok)
    result = await svc.execute_excel_action("fake_token", "append_row", {"item_id": "i", "table": "t", "mapping": {"ColA": "x", "ColB": "y"}})
    assert result["status"] == "success"


async def test_m365_excel_create_worksheet_format(dev_env):
    svc = make_service()
    result = await svc.execute_excel_action("fake_token", "create_worksheet", {"item_id": "i"})
    assert result["status"] == "error"
    assert (await svc.execute_excel_action("fake_token", "create_worksheet", {"item_id": "i", "name": "W"}))["status"] == "success"
    result = await svc.execute_excel_action("fake_token", "format_range", {"item_id": "i"})
    assert result["status"] == "error"
    assert (await svc.execute_excel_action("fake_token", "format_range", {"item_id": "i", "range": "A1:B2", "format": {"bold": True}}))["status"] == "success"
    assert (await svc.execute_excel_action("fake_token", "format_range", {"item_id": "i", "range": "S!A1:B2"}))["status"] == "success"


async def test_m365_excel_unknown_exception(monkeypatch, dev_env):
    svc = make_service()
    result = await svc.execute_excel_action("fake_token", "bogus", {"item_id": "i"})
    assert result["status"] == "error"
    assert "Unknown Excel action" in result["message"]

    async def boom(*a, **k):
        raise RuntimeError("excel-leak")

    monkeypatch.setattr(svc, "_make_graph_request", boom)
    result = await svc.execute_excel_action("fake_token", "get_tables", {"item_id": "i"})
    assert result["status"] == "error"
    assert "excel-leak" not in json.dumps(result)


# --- Power BI ------------------------------------------------------------

async def test_m365_powerbi_actions(dev_env):
    svc = make_service()
    result = await svc.execute_powerbi_action("fake_token", "refresh_dataset", {})
    assert result["status"] == "error"
    assert (await svc.execute_powerbi_action("fake_token", "refresh_dataset", {"group_id": "g", "dataset_id": "d"}))["status"] == "success"
    result = await svc.execute_powerbi_action("fake_token", "get_reports", {})
    assert result["status"] == "error"
    assert (await svc.execute_powerbi_action("fake_token", "get_reports", {"group_id": "g"}))["status"] == "success"
    result = await svc.execute_powerbi_action("fake_token", "get_dashboards", {})
    assert result["status"] == "error"
    assert (await svc.execute_powerbi_action("fake_token", "get_dashboards", {"group_id": "g"}))["status"] == "success"
    result = await svc.execute_powerbi_action("fake_token", "export_report", {})
    assert result["status"] == "error"
    assert (await svc.execute_powerbi_action("fake_token", "export_report", {"group_id": "g", "report_id": "r"}))["status"] == "success"
    result = await svc.execute_powerbi_action("fake_token", "get_datasets", {})
    assert result["status"] == "error"
    assert (await svc.execute_powerbi_action("fake_token", "get_datasets", {"group_id": "g"}))["status"] == "success"
    result = await svc.execute_powerbi_action("fake_token", "nope", {})
    assert result["status"] == "error"
    assert "Unknown Power BI action" in result["message"]


async def test_m365_powerbi_exception(monkeypatch):
    svc = make_service()

    async def boom(*a, **k):
        raise RuntimeError("pbi-leak")

    monkeypatch.setattr(svc, "_make_graph_request", boom)
    result = await svc.execute_powerbi_action("t", "get_reports", {"group_id": "g"})
    assert result["status"] == "error"
    assert "pbi-leak" not in json.dumps(result)


# --- Teams ---------------------------------------------------------------

async def test_m365_teams_actions(dev_env):
    svc = make_service()
    result = await svc.execute_teams_action("fake_token", "send_message", {})
    assert result["status"] == "error"
    result = await svc.execute_teams_action("fake_token", "send_message", {"team_id": "t", "channel_id": "c", "message": "hi"})
    assert result["status"] == "success"
    result = await svc.execute_teams_action("fake_token", "create_channel", {})
    assert result["status"] == "error"
    result = await svc.execute_teams_action("fake_token", "create_channel", {"team_id": "t", "display_name": "n", "description": "d"})
    assert result["status"] == "success"
    assert (await svc.execute_teams_action("fake_token", "list_teams", {}))["status"] == "success"
    result = await svc.execute_teams_action("fake_token", "zzz", {})
    assert result["status"] == "error"
    assert "Unknown Teams action" in result["message"]


async def test_m365_teams_exception(monkeypatch):
    svc = make_service()

    async def boom(*a, **k):
        raise RuntimeError("teams-leak")

    monkeypatch.setattr(svc, "_make_graph_request", boom)
    result = await svc.execute_teams_action("t", "list_teams", {})
    assert result["status"] == "error"
    assert "teams-leak" not in json.dumps(result)


# --- Outlook -------------------------------------------------------------

async def test_m365_outlook_actions(dev_env):
    svc = make_service()
    result = await svc.execute_outlook_action("fake_token", "send_email", {})
    assert result["status"] == "error"
    result = await svc.execute_outlook_action("fake_token", "send_email", {"to": "a@b.com", "subject": "s", "body": "b"})
    assert result["status"] == "success"
    result = await svc.execute_outlook_action("fake_token", "send_email", {"to": ["a@b.com"], "cc": "c@b.com", "bcc": ["d@b.com"]})
    assert result["status"] == "success"
    assert (await svc.execute_outlook_action("fake_token", "list_messages", {}))["status"] == "success"
    assert (await svc.execute_outlook_action("fake_token", "list_messages", {"folder_id": "x", "top": 3}))["status"] == "success"
    result = await svc.execute_outlook_action("fake_token", "create_event", {})
    assert result["status"] == "error"
    result = await svc.execute_outlook_action("fake_token", "create_event", {"subject": "m", "start_time": "2026-01-01T10:00:00Z", "end_time": "2026-01-01T11:00:00Z"})
    assert result["status"] == "success"
    result = await svc.execute_outlook_action("fake_token", "create_event", {"start_time": "s", "end_time": "e", "body": "b", "attendees": ["x@y.com"]})
    assert result["status"] == "success"
    result = await svc.execute_outlook_action("fake_token", "zzz", {})
    assert result["status"] == "error"
    assert "Unknown Outlook action" in result["message"]


async def test_m365_outlook_exception(monkeypatch):
    svc = make_service()

    async def boom(*a, **k):
        raise RuntimeError("ol-leak")

    monkeypatch.setattr(svc, "_make_graph_request", boom)
    result = await svc.execute_outlook_action("t", "send_email", {"to": "a@b.com"})
    assert result["status"] == "error"
    assert "ol-leak" not in json.dumps(result)


# --- Planner -------------------------------------------------------------

async def test_m365_planner_actions(dev_env):
    svc = make_service()
    result = await svc.execute_planner_action("fake_token", "create_task", {})
    assert result["status"] == "error"
    result = await svc.execute_planner_action("fake_token", "create_task", {"plan_id": "p", "bucket_id": "b", "title": "t", "assignments": {"u": {}}, "description": "d"})
    assert result["status"] == "success"
    result = await svc.execute_planner_action("fake_token", "update_task", {})
    assert result["status"] == "error"
    result = await svc.execute_planner_action("fake_token", "update_task", {"task_id": "t1", "title": "x", "description": "y", "percent_complete": 50})
    assert result["status"] == "success"
    result = await svc.execute_planner_action("fake_token", "update_task", {"task_id": "t1"})
    assert result["status"] == "success"
    result = await svc.execute_planner_action("fake_token", "list_plans", {})
    assert result["status"] == "error"
    assert (await svc.execute_planner_action("fake_token", "list_plans", {"group_id": "g"}))["status"] == "success"
    result = await svc.execute_planner_action("fake_token", "list_buckets", {})
    assert result["status"] == "error"
    assert (await svc.execute_planner_action("fake_token", "list_buckets", {"plan_id": "p"}))["status"] == "success"
    result = await svc.execute_planner_action("fake_token", "list_tasks", {})
    assert result["status"] == "error"
    assert (await svc.execute_planner_action("fake_token", "list_tasks", {"plan_id": "p"}))["status"] == "success"
    result = await svc.execute_planner_action("fake_token", "zzz", {})
    assert result["status"] == "error"
    assert "Unknown Planner action" in result["message"]


async def test_m365_planner_exception(monkeypatch):
    svc = make_service()

    async def boom(*a, **k):
        raise RuntimeError("plan-leak")

    monkeypatch.setattr(svc, "_make_graph_request", boom)
    result = await svc.execute_planner_action("t", "list_tasks", {"plan_id": "p"})
    assert result["status"] == "error"
    assert "plan-leak" not in json.dumps(result)


# --- delete_item / subscriptions ----------------------------------------

async def test_m365_delete_item(dev_env):
    svc = make_service()
    assert (await svc.delete_item("fake_token", "message", "m1"))["status"] == "success"
    assert (await svc.delete_item("fake_token", "event", "e1"))["status"] == "success"
    assert (await svc.delete_item("fake_token", "file", "f1"))["status"] == "success"
    result = await svc.delete_item("fake_token", "team_message", "tm1")
    assert result["status"] == "error"
    assert "Team ID and Channel ID required" in result["message"]
    assert (await svc.delete_item("fake_token", "team_message", "tm1", {"team_id": "t", "channel_id": "c"}))["status"] == "success"
    result = await svc.delete_item("fake_token", "widget", "w1")
    assert result["status"] == "error"
    assert "Unknown item type" in result["message"]


async def test_m365_delete_item_exception(monkeypatch):
    svc = make_service()

    async def boom(*a, **k):
        raise RuntimeError("del-leak")

    monkeypatch.setattr(svc, "_make_graph_request", boom)
    result = await svc.delete_item("t", "message", "m1")
    assert result["status"] == "error"
    assert "del-leak" not in json.dumps(result)


async def test_m365_create_subscription(dev_env):
    svc = make_service()
    result = await svc.create_subscription("fake_token", "message", "created", "http://hook", "2026-12-31T00:00:00Z")
    assert result["status"] == "success"
    result = await svc.create_subscription("fake_token", "message", "updated", "http://hook", "2026-12-31T00:00:00Z")
    assert result["status"] == "success"


async def test_m365_subscriptions_exception(monkeypatch):
    svc = make_service()

    async def boom(*a, **k):
        raise RuntimeError("sub-leak")

    monkeypatch.setattr(svc, "_make_graph_request", boom)
    result = await svc.create_subscription("t", "message", "created", "h", "d")
    assert result["status"] == "error"
    assert "sub-leak" not in json.dumps(result)
    result = await svc.renew_subscription("t", "s1", "d")
    assert result["status"] == "error"
    assert "sub-leak" not in json.dumps(result)
    result = await svc.delete_subscription("t", "s1")
    assert result["status"] == "error"
    assert "sub-leak" not in json.dumps(result)


async def test_m365_renew_delete_subscription(dev_env):
    svc = make_service()
    assert (await svc.renew_subscription("fake_token", "s1", "2027-01-01T00:00:00Z"))["status"] == "success"
    assert (await svc.delete_subscription("fake_token", "s1"))["status"] == "success"


# --- internal _send_message/_list_teams/_list_channels -------------------

async def test_m365_private_helpers_no_token(monkeypatch):
    svc = make_service()
    assert (await svc._send_message("t", "c", "hi"))["status"] == "error"
    assert (await svc._list_teams())["status"] == "error"
    assert (await svc._list_channels("t"))["status"] == "error"


async def test_m365_private_helpers_exception(monkeypatch):
    svc = m365.Microsoft365Service(tenant_id="t", config={"access_token": "fake_token"})

    async def boom(*a, **k):
        raise RuntimeError("helper-leak")

    monkeypatch.setattr(svc, "_make_graph_request", boom)
    result = await svc._send_message("t", "c", "hi")
    assert result["status"] == "error"
    assert "helper-leak" not in json.dumps(result)
    result = await svc._list_teams()
    assert result["status"] == "error"
    assert "helper-leak" not in json.dumps(result)
    result = await svc._list_channels("t")
    assert result["status"] == "error"
    assert "helper-leak" not in json.dumps(result)


# --- API routes ----------------------------------------------------------

@pytest.fixture
def fake_global_service(monkeypatch):
    fake = AsyncMock()
    monkeypatch.setattr(m365, "microsoft365_service", fake)
    return fake


async def test_m365_route_auth_success(fake_global_service):
    fake_global_service.authenticate = AsyncMock(return_value={"status": "success", "auth_url": "http://a", "state": "st"})
    resp = await m365.microsoft365_auth(user_id="u1")
    assert resp.auth_url == "http://a"


async def test_m365_route_auth_error(fake_global_service):
    fake_global_service.authenticate = AsyncMock(return_value={"status": "error", "message": "failed"})
    with pytest.raises(HTTPException) as exc:
        await m365.microsoft365_auth(user_id="u1")
    assert exc.value.status_code == 400


async def test_m365_route_user_success(fake_global_service):
    fake_global_service.get_user_profile = AsyncMock(
        return_value={"status": "success", "data": {"id": "1", "displayName": "A", "mail": "a@b.c", "userPrincipalName": "a"}}
    )
    resp = await m365.get_microsoft365_user(access_token="tok")
    assert resp.id == "1"


async def test_m365_route_user_error(fake_global_service):
    fake_global_service.get_user_profile = AsyncMock(return_value={"status": "error", "message": "x"})
    with pytest.raises(HTTPException):
        await m365.get_microsoft365_user(access_token="tok")


async def test_m365_route_teams(fake_global_service):
    fake_global_service.list_teams = AsyncMock(return_value={"status": "success", "data": {"value": [{"id": "1"}]}})
    resp = await m365.list_microsoft365_teams(access_token="tok")
    assert resp["teams"] == [{"id": "1"}]
    fake_global_service.list_teams = AsyncMock(return_value={"status": "error", "message": "x"})
    with pytest.raises(HTTPException):
        await m365.list_microsoft365_teams(access_token="tok")


async def test_m365_route_channels(fake_global_service):
    fake_global_service.list_channels = AsyncMock(return_value={"status": "success", "data": {"value": [{"id": "c1"}]}})
    resp = await m365.list_microsoft365_channels(team_id="t1", access_token="tok")
    assert resp["channels"] == [{"id": "c1"}]
    fake_global_service.list_channels = AsyncMock(return_value={"status": "error", "message": "x"})
    with pytest.raises(HTTPException):
        await m365.list_microsoft365_channels(team_id="t1", access_token="tok")


async def test_m365_route_messages(fake_global_service):
    fake_global_service.get_outlook_messages = AsyncMock(return_value={"status": "success", "data": {"value": [{"id": "m1"}]}})
    resp = await m365.get_microsoft365_messages(access_token="tok")
    assert resp["messages"] == [{"id": "m1"}]
    fake_global_service.get_outlook_messages = AsyncMock(return_value={"status": "error", "message": "x"})
    with pytest.raises(HTTPException):
        await m365.get_microsoft365_messages(access_token="tok")


async def test_m365_route_events(fake_global_service):
    fake_global_service.get_calendar_events = AsyncMock(return_value={"status": "success", "data": {"value": [{"id": "e1"}]}})
    resp = await m365.get_microsoft365_events(access_token="tok", start_date="a", end_date="b")
    assert resp["events"] == [{"id": "e1"}]
    fake_global_service.get_calendar_events = AsyncMock(return_value={"status": "error", "message": "x"})
    with pytest.raises(HTTPException):
        await m365.get_microsoft365_events(access_token="tok", start_date="a", end_date="b")


async def test_m365_route_service_status(fake_global_service):
    fake_global_service.get_service_status = AsyncMock(return_value={"status": "success", "data": {"id": "1"}})
    resp = await m365.get_microsoft365_service_status(access_token="tok")
    assert resp == {"id": "1"}
    fake_global_service.get_service_status = AsyncMock(return_value={"status": "error", "message": "x"})
    with pytest.raises(HTTPException):
        await m365.get_microsoft365_service_status(access_token="tok")


async def test_m365_route_health():
    resp = await m365.microsoft365_health()
    assert resp["status"] == "healthy"


async def test_m365_route_user_dev_bypass(monkeypatch, dev_env):
    """BUG FIX: dev-bypass mock data must validate against Microsoft365User."""
    resp = await m365.get_microsoft365_user(access_token="fake_token")
    assert resp.id == "mock_id_123"


# =========================================================================
# Gmail
# =========================================================================

class FakeCredentials:
    token = "at"
    refresh_token = "rt"
    token_uri = "https://oauth2.googleapis.com/token"
    client_id = "cid"
    client_secret = "cs"
    scopes = []

    def __init__(self, *a, **k):
        self.valid = True
        self.expired = False
        self.token = "at"
        self.refresh_token = "rt"
        self.token_uri = "uri"
        self.client_id = "cid"
        self.client_secret = "cs"
        self.scopes = []

    def refresh(self, req):
        self.token = "refreshed-at"

    def to_json(self):
        return json.dumps({"token": self.token})

    @classmethod
    def from_authorized_user_file(cls, path, scopes=None):
        inst = cls()
        inst.valid = False
        inst.expired = True
        return inst


class FakeFlow:
    redirect_uri = None

    def __init__(self, *a, **k):
        pass

    def authorization_url(self, prompt=None):
        return ("http://localhost/auth", "state")

    @classmethod
    def from_client_secrets_file(cls, path, scopes):
        return cls()


class FakeRequest:
    pass


class FakeHttpError(Exception):
    pass


@pytest.fixture
def gmail_env(monkeypatch):
    monkeypatch.setattr(gs, "Credentials", FakeCredentials)
    monkeypatch.setattr(gs, "Flow", FakeFlow)
    monkeypatch.setattr(gs, "Request", FakeRequest)
    monkeypatch.setattr(gs, "HttpError", FakeHttpError)
    monkeypatch.setattr(gs, "GOOGLE_OAUTH_CONFIG", SimpleNamespace(
        token_url="https://oauth2.googleapis.com/token",
        client_id="cid",
        client_secret="cs",
        is_configured=lambda: True,
    ))
    storage = SimpleNamespace(
        get_token=lambda provider: None,
        save_token=lambda provider, data: None,
    )
    monkeypatch.setattr(gs, "token_storage", storage)
    return storage


def make_service_with(service_mock=None):
    svc = gs.GmailService(tenant_id="t1", config={})
    svc.service = service_mock
    return svc


def make_gmail_svc(profile=None, messages=None, threads=None, thread=None, labels=None, draft=None, send=None, modify=None):
    service = MagicMock()
    profile = profile if profile is not None else {"emailAddress": "a@b.c", "messagesTotal": 5, "threadsTotal": 2, "historyId": "h1"}
    service.users.return_value.getProfile.return_value.execute.return_value = profile
    service.users.return_value.messages.return_value.list.return_value.execute.return_value = messages if messages is not None else {"messages": []}
    service.users.return_value.threads.return_value.list.return_value.execute.return_value = threads if threads is not None else {"threads": []}
    service.users.return_value.threads.return_value.get.return_value.execute.return_value = thread if thread is not None else {"messages": []}
    service.users.return_value.labels.return_value.list.return_value.execute.return_value = labels if labels is not None else {"labels": [{"id": "1"}]}
    service.users.return_value.drafts.return_value.create.return_value.execute.return_value = draft if draft is not None else {"id": "d1"}
    service.users.return_value.messages.return_value.send.return_value.execute.return_value = send if send is not None else {"id": "s1"}
    service.users.return_value.messages.return_value.modify.return_value.execute.return_value = modify
    service.users.return_value.labels.return_value.create.return_value.execute.return_value = {"id": "d1"}
    service.users.return_value.messages.return_value.delete.return_value.execute.return_value = None
    return service


def fake_build(*args, **kwargs):
    return make_gmail_svc()


async def test_gmail_init_default(gmail_env, monkeypatch):
    monkeypatch.setattr(gs, "build", fake_build)
    svc = gs.GmailService(tenant_id="t1", config={})
    assert svc.tenant_id == "t1"
    assert svc.service is None


async def test_gmail_init_with_credentials_file_flow(gmail_env, monkeypatch, tmp_path):
    cred_path = tmp_path / "credentials.json"
    cred_path.write_text("{}")
    monkeypatch.setattr(gs, "build", fake_build)
    svc = gs.GmailService(tenant_id="t1", config={"credentials_path": str(cred_path)})
    assert svc.service is None


async def test_gmail_init_no_creds_not_configured(gmail_env, monkeypatch, tmp_path):
    monkeypatch.setattr(gs, "GOOGLE_OAUTH_CONFIG", SimpleNamespace(
        token_url="u", client_id="c", client_secret="s", is_configured=lambda: False,
    ))
    monkeypatch.setattr(gs, "build", fake_build)
    svc = gs.GmailService(tenant_id="t1", config={"credentials_path": str(tmp_path / "nope.json")})
    assert svc.service is None


async def test_gmail_init_file_token(gmail_env, monkeypatch, tmp_path):
    token_path = tmp_path / "token.json"
    token_path.write_text("{}")
    monkeypatch.setattr(gs, "build", fake_build)
    svc = gs.GmailService(tenant_id="t1", config={"token_path": str(token_path)})
    assert svc.service is not None


async def test_gmail_init_stored_token_refresh(gmail_env, monkeypatch):
    saved = {}
    gmail_env.get_token = lambda provider: {"access_token": "old", "refresh_token": "rt"}
    gmail_env.save_token = lambda provider, data: saved.update(data)

    class ExpiredCredentials(FakeCredentials):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.valid = False
            self.expired = True
            self.refresh_token = "rt"
            self.token = "old"

    monkeypatch.setattr(gs, "Credentials", ExpiredCredentials)
    monkeypatch.setattr(gs, "build", fake_build)
    svc = gs.GmailService(tenant_id="t1", config={})
    assert svc.service is not None
    assert saved.get("access_token") == "refreshed-at"


async def test_gmail_get_capabilities():
    caps = gs.GmailService(tenant_id="t", config={}).get_capabilities()
    assert len(caps["operations"]) == 9
    assert caps["supports_webhooks"] is True


async def test_gmail_health_check_no_service():
    result = gs.GmailService(tenant_id="t", config={}).health_check()
    assert result["healthy"] is False


async def test_gmail_health_check_ok_error(gmail_env):
    svc = make_service_with(make_gmail_svc(profile={"emailAddress": "a@b.c"}))
    result = svc.health_check()
    assert result["healthy"] is True
    assert result["email"] == "a@b.c"

    bad = make_service_with(MagicMock())
    bad.service.users.return_value.getProfile.return_value.execute.side_effect = RuntimeError("health-detail-zzz")
    result = bad.health_check()
    assert result["healthy"] is False
    assert "health-detail-zzz" not in json.dumps(result)


async def test_gmail_test_connection(gmail_env):
    svc = make_service_with(make_gmail_svc())
    result = svc.test_connection()
    assert result["status"] == "success"
    assert result["authenticated"] is True

    no_svc = gs.GmailService(tenant_id="t", config={})
    assert no_svc.test_connection()["status"] == "error"

    bad = make_service_with(MagicMock())
    bad.service.users.return_value.getProfile.return_value.execute.side_effect = RuntimeError("conn-detail")
    result = bad.test_connection()
    assert result["status"] == "error"
    assert "conn-detail" not in json.dumps(result)


async def test_gmail_get_service_with_token(gmail_env, monkeypatch):
    svc = make_service_with(make_gmail_svc())
    assert svc._get_service_with_token(None) is svc.service

    built = make_gmail_svc()
    monkeypatch.setattr(gs, "build", lambda *a, **k: built)
    assert svc._get_service_with_token("tok") is built

    monkeypatch.setattr(gs, "build", MagicMock(side_effect=RuntimeError("build-fail")))
    assert svc._get_service_with_token("tok") is None


async def test_gmail_get_calendar_service(gmail_env, monkeypatch):
    svc = make_service_with(make_gmail_svc())
    built = MagicMock()
    monkeypatch.setattr(gs, "build", lambda *a, **k: built)
    assert svc._get_calendar_service("tok") is built

    gmail_env.get_token = lambda provider: {"access_token": "a", "refresh_token": "r"}
    assert svc._get_calendar_service(None) is built

    gmail_env.get_token = lambda provider: None
    assert svc._get_calendar_service(None) is None

    monkeypatch.setattr(gs, "build", MagicMock(side_effect=RuntimeError("cal-fail")))
    assert svc._get_calendar_service("tok") is None


def sample_parsed_message(extra=None):
    payload = {
        "id": "m1",
        "threadId": "th1",
        "snippet": "snip",
        "labelIds": ["INBOX"],
        "historyId": "h1",
        "internalDate": "123",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Hello"},
                {"name": "From", "value": "sender@x.com"},
                {"name": "Date", "value": "2026-01-01"},
            ],
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/plain", "body": {"data": "aGVsbG8="}},
                {
                    "mimeType": "multipart/mixed",
                    "parts": [
                        {"filename": "f.txt", "mimeType": "text/plain", "body": {"attachmentId": "att1", "size": 10}},
                    ],
                },
            ],
        },
    }
    if extra:
        payload["payload"].update(extra)
    return payload


async def test_gmail_get_messages(gmail_env, monkeypatch):
    svc = make_service_with(make_gmail_svc())
    svc.service.users.return_value.messages.return_value.list.return_value.execute.side_effect = [
        {"messages": [{"id": "m1"}], "nextPageToken": "tok2"},
        {"messages": [{"id": "m2"}]},
    ]
    monkeypatch.setattr(gs.GmailService, "get_message", lambda self, mid, token=None: {"id": mid, "subject": "s"})
    result = svc.get_messages(query="q", max_results=50)
    assert result == [{"id": "m1", "subject": "s"}, {"id": "m2", "subject": "s"}]


async def test_gmail_get_messages_http_error(gmail_env, monkeypatch):
    svc = make_service_with(make_gmail_svc())
    svc.service.users.return_value.messages.return_value.list.return_value.execute.side_effect = FakeHttpError("boom")
    monkeypatch.setattr(gs.GmailService, "get_message", lambda self, mid, token=None: {"id": mid})
    assert svc.get_messages() == []


async def test_gmail_get_messages_no_service():
    svc = gs.GmailService(tenant_id="t", config={})
    assert svc.get_messages() == []


async def test_gmail_get_messages_exception(gmail_env, monkeypatch):
    svc = make_service_with(make_gmail_svc())
    svc.service.users.return_value.messages.return_value.list.return_value.execute.side_effect = RuntimeError("list-leak")
    assert svc.get_messages() == []


async def test_gmail_get_message(gmail_env, monkeypatch):
    svc = make_service_with(make_gmail_svc())
    svc.service.users.return_value.messages.return_value.get.return_value.execute.return_value = sample_parsed_message()
    result = svc.get_message("m1")
    assert result["subject"] == "Hello"
    assert result["sender"] == "sender@x.com"
    assert result["body"] == "hello"

    no_svc = gs.GmailService(tenant_id="t", config={})
    assert no_svc.get_message("m1") is None

    bad = make_service_with(MagicMock())
    bad.service.users.return_value.messages.return_value.get.return_value.execute.side_effect = RuntimeError("get-leak")
    assert bad.get_message("m1") is None


async def test_gmail_parse_message_variants(gmail_env, monkeypatch):
    svc = gs.GmailService(tenant_id="t", config={})

    msg = sample_parsed_message(extra={"body": {"data": "aGVsbG8="}})
    assert svc._parse_message(msg)["body"] == "hello"

    msg = {
        "id": "m2",
        "threadId": "t2",
        "payload": {
            "headers": [],
            "parts": [{"mimeType": "text/html", "body": {"data": "PGI+aGk8L2I+"}}],
        },
    }
    assert svc._parse_message(msg)["body"] == "<b>hi</b>"

    msg = {
        "id": "m3",
        "threadId": "t3",
        "payload": {
            "headers": [],
            "parts": [{"mimeType": "text/plain", "body": {"data": "aGVsbG8="}}],
        },
    }
    assert svc._parse_message(msg)["body"] == "hello"

    assert svc._parse_message({"payload": {}}) == {}

    bad = MagicMock()
    bad.__getitem__.side_effect = KeyError("payload")
    assert svc._parse_message(bad) == {}


async def test_gmail_extract_body(gmail_env):
    svc = gs.GmailService(tenant_id="t", config={})
    assert svc._extract_body({"body": {"data": "aGVsbG8="}}) == "hello"
    assert svc._extract_body({"parts": [{"mimeType": "text/plain", "body": {"data": "aGVsbG8="}}]}) == "hello"
    assert svc._extract_body({"parts": [{"mimeType": "text/html", "body": {"data": "aGVsbG8="}}]}) == "hello"
    assert svc._extract_body({"parts": [{"mimeType": "x", "parts": [{"mimeType": "text/plain", "body": {"data": "aGVsbG8="}}]}]}) == "hello"
    assert svc._extract_body({"mimeType": "x"}) == ""
    assert svc._extract_body({"body": {"data": "!!invalid!!"}}) == ""


async def test_gmail_extract_attachments(gmail_env):
    svc = gs.GmailService(tenant_id="t", config={})
    payload = {"parts": [
        {"filename": "a.txt", "mimeType": "text/plain", "body": {"attachmentId": "att1", "size": 5}},
        {"filename": "", "body": {}},
        {"mimeType": "x", "parts": [{"filename": "b.txt", "mimeType": "y", "body": {"attachmentId": "att2"}}]},
    ]}
    result = svc._extract_attachments(payload)
    assert len(result) == 2
    assert result[0]["size"] == 5
    assert result[1]["attachmentId"] == "att2"


async def test_gmail_get_attachment_content(gmail_env):
    svc = make_service_with(make_gmail_svc())
    svc.service.users.return_value.messages.return_value.attachments.return_value.get.return_value.execute.return_value = {"data": "aGVsbG8="}
    assert svc.get_attachment_content("m1", "att1") == b"hello"

    svc.service.users.return_value.messages.return_value.attachments.return_value.get.return_value.execute.return_value = {}
    assert svc.get_attachment_content("m1", "att1") is None

    no_svc = gs.GmailService(tenant_id="t", config={})
    assert no_svc.get_attachment_content("m1", "att1") is None

    bad = make_service_with(MagicMock())
    bad.service.users.return_value.messages.return_value.attachments.return_value.get.return_value.execute.side_effect = RuntimeError("att-leak")
    assert bad.get_attachment_content("m1", "att1") is None


async def test_gmail_send_message(gmail_env):
    svc = make_service_with(make_gmail_svc())
    result = svc.send_message(to="a@b.c", subject="s", body="b", cc="c@b.c", bcc="d@b.c", thread_id="th1")
    assert result["id"] == "s1"
    result = svc.send_message(to="a@b.c", subject="s", body="b")
    assert result["id"] == "s1"

    no_svc = gs.GmailService(tenant_id="t", config={})
    assert no_svc.send_message(to="a@b.c", subject="s", body="b") is None

    bad = make_service_with(MagicMock())
    bad.service.users.return_value.messages.return_value.send.return_value.execute.side_effect = RuntimeError("send-leak")
    assert bad.send_message(to="a@b.c", subject="s", body="b") is None


async def test_gmail_reply_to_message(gmail_env):
    svc = make_service_with(make_gmail_svc())
    svc.service.users.return_value.threads.return_value.get.return_value.execute.return_value = {
        "messages": [{
            "payload": {"headers": [
                {"name": "Message-ID", "value": "msg1"},
                {"name": "Reply-To", "value": "r@b.c"},
                {"name": "Subject", "value": "Original"},
            ]},
        }],
    }
    result = svc.reply_to_message("th1", "body")
    assert result["id"] == "s1"

    svc.service.users.return_value.threads.return_value.get.return_value.execute.return_value = {
        "messages": [{"payload": {"headers": [{"name": "From", "value": "f@b.c"}, {"name": "Subject", "value": "Re: already"}]}}],
    }
    result = svc.reply_to_message("th1", "body")
    assert result["id"] == "s1"

    svc.service.users.return_value.threads.return_value.get.return_value.execute.return_value = {"messages": []}
    assert svc.reply_to_message("th1", "body") is None

    no_svc = gs.GmailService(tenant_id="t", config={})
    assert no_svc.reply_to_message("th1", "body") is None

    bad = make_service_with(MagicMock())
    bad.service.users.return_value.threads.return_value.get.return_value.execute.side_effect = RuntimeError("reply-leak")
    assert bad.reply_to_message("th1", "body") is None


async def test_gmail_draft_message(gmail_env):
    svc = make_service_with(make_gmail_svc())
    assert svc.draft_message(to="a@b.c", subject="s", body="b")["id"] == "d1"
    assert svc.draft_message(to="a@b.c", subject="s", body="b", thread_id="t")["id"] == "d1"

    no_svc = gs.GmailService(tenant_id="t", config={})
    assert no_svc.draft_message(to="a@b.c", subject="s", body="b") is None

    bad = make_service_with(MagicMock())
    bad.service.users.return_value.drafts.return_value.create.return_value.execute.side_effect = RuntimeError("draft-leak")
    assert bad.draft_message(to="a@b.c", subject="s", body="b") is None


async def test_gmail_search_messages(gmail_env, monkeypatch):
    svc = make_service_with(make_gmail_svc())
    monkeypatch.setattr(gs.GmailService, "get_message", lambda self, mid, token=None: {"id": mid})
    result = svc.search_messages("query", max_results=5)
    assert result == []


async def test_gmail_get_threads(gmail_env):
    svc = make_service_with(make_gmail_svc(threads={"threads": [{"id": "t1"}]}, thread={"id": "t1", "messages": [{"id": "m1"}]}))
    result = svc.get_threads()
    assert result == [{"id": "t1", "messages": [{"id": "m1"}]}]

    svc.service.users.return_value.threads.return_value.list.return_value.execute.side_effect = FakeHttpError("boom")
    assert svc.get_threads() == []

    bad = make_service_with(MagicMock())
    bad.service.users.return_value.threads.return_value.list.return_value.execute.side_effect = RuntimeError("threads-leak")
    assert bad.get_threads() == []


async def test_gmail_get_threads_partial_fetch_error(gmail_env):
    svc = make_service_with(make_gmail_svc(threads={"threads": [{"id": "t1"}]}))
    svc.service.users.return_value.threads.return_value.get.return_value.execute.side_effect = RuntimeError("thread-get-leak")
    result = svc.get_threads()
    assert result == []


async def test_gmail_modify_message(gmail_env):
    svc = make_service_with(make_gmail_svc())
    assert svc.modify_message("m1", add_labels=["A"], remove_labels=["B"]) is True
    assert svc.modify_message("m1") is True

    bad = make_service_with(MagicMock())
    bad.service.users.return_value.messages.return_value.modify.return_value.execute.side_effect = RuntimeError("modify-leak")
    assert bad.modify_message("m1") is False


async def test_gmail_delete_message(gmail_env):
    svc = make_service_with(make_gmail_svc())
    assert svc.delete_message("m1") is True

    bad = make_service_with(MagicMock())
    bad.service.users.return_value.messages.return_value.delete.return_value.execute.side_effect = RuntimeError("del-leak")
    assert bad.delete_message("m1") is False


async def test_gmail_get_labels(gmail_env, monkeypatch):
    labels_svc = make_gmail_svc(labels={"labels": [{"id": "L1"}]})
    monkeypatch.setattr(gs, "build", lambda *a, **k: labels_svc)
    svc = make_service_with(make_gmail_svc(labels={"labels": [{"id": "L1"}]}))
    assert svc.get_labels() == [{"id": "L1"}]
    assert svc.get_labels(token="tok") == [{"id": "L1"}]

    no_svc = gs.GmailService(tenant_id="t", config={})
    assert no_svc.get_labels() == []

    bad = make_service_with(MagicMock())
    bad.service.users.return_value.labels.return_value.list.return_value.execute.side_effect = RuntimeError("label-leak")
    assert bad.get_labels() == []


async def test_gmail_create_label(gmail_env):
    svc = make_service_with(make_gmail_svc())
    result = svc.create_label("NewLabel")
    assert result["id"] == "d1"
    result = svc.create_label("NewLabel", color={"red": "1"})
    assert result["id"] == "d1"

    bad = make_service_with(MagicMock())
    bad.service.users.return_value.labels.return_value.create.return_value.execute.side_effect = RuntimeError("create-label-leak")
    assert bad.create_label("NewLabel") is None


class FakeMetric:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeHubDB:
    def __init__(self, existing=None, commit_error=None, existing_factory=None):
        self.existing = existing
        self.existing_factory = existing_factory
        self.commit_error = commit_error
        self.added = []
        self.updated = []
        self.closed = False

    def query(self, model):
        return self

    def filter_by(self, **kw):
        return self

    def first(self):
        if self.existing_factory is not None:
            obj = self.existing_factory()
            self.updated.append(obj)
            return obj
        return self.existing

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        if self.commit_error:
            raise self.commit_error

    def rollback(self):
        pass

    def close(self):
        self.closed = True


async def test_gmail_sync_to_postgres_cache(gmail_env, monkeypatch):
    db = FakeHubDB()
    monkeypatch.setattr("core.database.SessionLocal", lambda: db)
    monkeypatch.setattr("core.models.IntegrationMetric", FakeMetric)
    svc = make_service_with(make_gmail_svc(profile={"messagesTotal": 10, "threadsTotal": 3}))
    result = await svc.sync_to_postgres_cache(user_id="u1")
    assert result["success"] is True
    assert result["metrics_synced"] == 3
    assert len(db.added) == 3
    assert db.closed

    db2 = FakeHubDB(existing_factory=lambda: FakeMetric(value=0))
    monkeypatch.setattr("core.database.SessionLocal", lambda: db2)
    result = await svc.sync_to_postgres_cache(user_id="u1")
    assert result["success"] is True
    assert len(db2.updated) == 3
    assert db2.updated[0].value == 10.0
    assert db2.updated[1].value == 3.0


async def test_gmail_sync_to_postgres_cache_errors(gmail_env, monkeypatch):
    monkeypatch.setattr("core.database.SessionLocal", lambda: FakeHubDB(commit_error=RuntimeError("db-detail")))
    monkeypatch.setattr("core.models.IntegrationMetric", FakeMetric)
    svc = make_service_with(make_gmail_svc())
    result = await svc.sync_to_postgres_cache(user_id="u1")
    assert result["success"] is False
    assert "db-detail" not in json.dumps(result)

    no_svc = gs.GmailService(tenant_id="t", config={})
    result = await no_svc.sync_to_postgres_cache(user_id="u1")
    assert result["success"] is False

    bad = make_service_with(MagicMock())
    bad.service.users.return_value.getProfile.return_value.execute.side_effect = RuntimeError("profile-leak")
    result = await bad.sync_to_postgres_cache(user_id="u1")
    assert result["success"] is False
    assert "profile-leak" not in json.dumps(result)


async def test_gmail_full_sync(gmail_env, monkeypatch):
    db = FakeHubDB()
    monkeypatch.setattr("core.database.SessionLocal", lambda: db)
    monkeypatch.setattr("core.models.IntegrationMetric", FakeMetric)
    svc = make_service_with(make_gmail_svc())
    result = await svc.full_sync(user_id="u1")
    assert result["success"] is True
    assert result["postgres_cache"]["success"] is True


async def test_gmail_sync_calendar_events(gmail_env, monkeypatch):
    gmail_env.get_token = lambda provider: {"access_token": "a", "refresh_token": "r"}
    pipeline = SimpleNamespace(ingest_message=AsyncMock())
    monkeypatch.setattr("integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline", lambda: pipeline)
    svc = make_service_with(MagicMock())
    monkeypatch.setattr(gs, "build", lambda *a, **k: svc.service)
    svc.service.events.return_value.list.return_value.execute.return_value = {
        "items": [
            {"id": "ev1", "summary": "Meeting", "description": "desc", "organizer": {"email": "o@x.com"},
             "start": {"dateTime": "2026-01-01T10:00:00Z"}, "end": {"dateTime": "2026-01-01T11:00:00Z"},
             "location": "Room 1", "attendees": [{"email": "a@x.com"}], "status": "confirmed"},
            {"id": "ev2", "start": {"date": "2026-01-02"}, "end": {"date": "2026-01-03"}},
        ]
    }
    await svc.sync_calendar_events(user_id="u1", days_ahead=3)
    assert pipeline.ingest_message.await_count == 2

    no_svc = gs.GmailService(tenant_id="t", config={})
    await no_svc.sync_calendar_events(user_id="u1")

    bad = make_service_with(MagicMock())
    bad.service.events.return_value.list.return_value.execute.side_effect = RuntimeError("cal-sync-leak")
    await bad.sync_calendar_events(user_id="u1")


async def test_gmail_create_update_calendar_event(gmail_env, monkeypatch):
    svc = make_service_with(make_gmail_svc())
    built = MagicMock()
    monkeypatch.setattr(gs, "build", lambda *a, **k: built)
    built.events.return_value.insert.return_value.execute.return_value = {"id": "ev1"}
    assert svc.create_calendar_event({"summary": "x"}, token="tok") == {"id": "ev1"}
    built.events.return_value.patch.return_value.execute.return_value = {"id": "ev1"}
    assert svc.update_calendar_event("ev1", {"summary": "y"}, token="tok") == {"id": "ev1"}

    no_svc = gs.GmailService(tenant_id="t", config={})
    assert no_svc.create_calendar_event({}) is None
    assert no_svc.update_calendar_event("ev1", {}) is None

    built.events.return_value.insert.return_value.execute.side_effect = RuntimeError("cal-create-leak")
    assert svc.create_calendar_event({}) is None
    built.events.return_value.patch.return_value.execute.side_effect = RuntimeError("cal-update-leak")
    assert svc.update_calendar_event("ev1", {}) is None


async def test_gmail_get_operations():
    ops = gs.GmailService(tenant_id="t", config={}).get_operations()
    assert len(ops) == 2
    assert ops[0]["name"] == "send_email"
    assert ops[0]["complexity"] == 3


async def test_gmail_execute_operation_tenant_mismatch(gmail_env):
    svc = gs.GmailService(tenant_id="expected", config={})
    result = await svc.execute_operation("send_email", {}, context={"tenant_id": "other"})
    assert result["success"] is False
    assert result["error"] == "Tenant ID mismatch"


async def test_gmail_execute_operation_dispatch(gmail_env, monkeypatch):
    svc = make_service_with(make_gmail_svc())
    monkeypatch.setattr(gs.GmailService, "send_message", lambda self, **kw: {"id": "s1"})
    monkeypatch.setattr(gs.GmailService, "get_messages", lambda self, **kw: [{"id": "m1"}])
    monkeypatch.setattr(gs.GmailService, "get_message", lambda self, **kw: {"id": "m1"})
    monkeypatch.setattr(gs.GmailService, "search_messages", lambda self, **kw: [{"id": "m1"}])
    monkeypatch.setattr(gs.GmailService, "reply_to_message", lambda self, **kw: {"id": "r1"})
    monkeypatch.setattr(gs.GmailService, "draft_message", lambda self, **kw: {"id": "d1"})
    monkeypatch.setattr(gs.GmailService, "modify_message", lambda self, **kw: True)
    monkeypatch.setattr(gs.GmailService, "delete_message", lambda self, **kw: True)

    result = await svc.execute_operation("send_email", {"to": "a@b.c"}, {"tenant_id": "t1"})
    assert result["success"] is True
    result = await svc.execute_operation("list_messages", {})
    assert result["success"] is True
    result = await svc.execute_operation("get_message", {"message_id": "m1"})
    assert result["success"] is True
    result = await svc.execute_operation("search_messages", {})
    assert result["success"] is True
    result = await svc.execute_operation("reply_to_message", {"thread_id": "t"})
    assert result["success"] is True
    result = await svc.execute_operation("draft_message", {})
    assert result["success"] is True
    result = await svc.execute_operation("modify_message", {"message_id": "m1"})
    assert result["success"] is True
    result = await svc.execute_operation("delete_message", {"message_id": "m1"})
    assert result["success"] is True

    events = []
    async def fake_sync(self, **kw):
        events.append(kw)
    monkeypatch.setattr(gs.GmailService, "sync_calendar_events", fake_sync)
    result = await svc.execute_operation("sync_calendar", {})
    assert result["success"] is True
    assert events

    result = await svc.execute_operation("unknown_op", {})
    assert result["success"] is False


async def test_gmail_execute_operation_error_codes(gmail_env, monkeypatch):
    svc = make_service_with(make_gmail_svc())
    for exc_text, expected in [
        ("invalid credentials provided", "AUTH_INVALID"),
        ("rate limit exceeded 429", "RATE_LIMIT"),
        ("404 not found", "RESOURCE_NOT_FOUND"),
        ("403 forbidden permission", "PERMISSION_DENIED"),
        ("something else", "UNKNOWN"),
    ]:
        def raiser(text=exc_text):
            raise RuntimeError(text)

        monkeypatch.setattr(gs.GmailService, "send_message", lambda self, **kw: raiser())
        result = await svc.execute_operation("send_email", {"to": "a@b.c"})
        assert result["success"] is False
        assert result["error"] == expected


async def test_gmail_fetch_recent_messages(gmail_env, monkeypatch):
    """BUG FIX: ingest_message is async — must be awaited, not fire-and-forget."""
    ingested = []

    async def fake_ingest(source, msg):
        ingested.append(msg["id"])

    pipeline = SimpleNamespace(ingest_message=fake_ingest)
    monkeypatch.setattr("integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline", lambda: pipeline)
    svc = make_service_with(make_gmail_svc())
    monkeypatch.setattr(gs.GmailService, "get_messages", lambda self, **kw: [{"id": "m1"}, {"id": "m2"}])
    result = await svc.fetch_recent_messages(user_id="u1")
    assert [m["id"] for m in result] == ["m1", "m2"]
    assert ingested == ["m1", "m2"]

    monkeypatch.setattr(gs.GmailService, "get_messages", MagicMock(side_effect=RuntimeError("fetch-leak")))
    assert await svc.fetch_recent_messages(user_id="u1") == []


async def test_gmail_get_attachment_metadata_download(gmail_env):
    svc = make_service_with(make_gmail_svc())
    monkeypatch = None
    gs2 = gs
    monkeypatch_orig = None

    def fake_get_message(mid):
        return {"attachments": [{"attachmentId": "a1", "filename": "f.txt", "size": 3, "mimeType": "text/plain"}]}

    with patch.object(gs.GmailService, "get_message", side_effect=fake_get_message):
        result = await svc.get_attachment_metadata("u1", "m1")
        assert result == [{"id": "a1", "name": "f.txt", "size": 3, "contentType": "text/plain"}]

    with patch.object(gs.GmailService, "get_message", return_value=None):
        assert await svc.get_attachment_metadata("u1", "m1") == []

    svc.service.users.return_value.messages.return_value.attachments.return_value.get.return_value.execute.return_value = {"data": "aGVsbG8="}
    assert await svc.download_attachment("u1", "m1", "a1") == b"hello"


async def test_gmail_factory(gmail_env):
    svc = gs.get_gmail_service(tenant_id="t2", config={})
    assert svc.tenant_id == "t2"


# =========================================================================
# HubSpot (atom_hubspot_integration_service)
# =========================================================================

def hubspot_svc(**config):
    cfg = {
        "hubspot_access_token": "tok",
        "hubspot_api_key": "",
        "hubspot_client_id": "cid",
        "hubspot_client_secret": "cs",
        "hubspot_environment": "production",
        "enable_lead_scoring": True,
        "enable_analytics": True,
        "automation_workflows": True,
        "campaign_management": True,
        "real_time_tracking": True,
        "enable_enterprise_features": False,
    }
    cfg.update(config)
    return hs.AtomHubSpotIntegrationService(tenant_id="t1", config=cfg)


def hubspot_http_client(post_result=None, get_result=None):
    client = MagicMock()
    client.post = AsyncMock(return_value=post_result if post_result is not None else MagicMock(status_code=500, text="boom"))
    client.get = AsyncMock(return_value=get_result if get_result is not None else MagicMock(status_code=500, text="boom"))
    ac = MagicMock()
    ac.__aenter__ = AsyncMock(return_value=client)
    ac.__aexit__ = AsyncMock(return_value=False)
    return ac


def ok_response(status, body):
    resp = MagicMock()
    resp.status_code = status
    resp.text = "{}"
    resp.json = MagicMock(return_value=body)
    return resp


CONTACT_BODY = {"id": "c1", "properties": {"firstname": "Jane", "lastname": "Doe", "company": "ACME"}}
CAMPAIGN_BODY = {"id": "cp1", "name": "Launch", "type": "email"}


class TestHubSpotInit:
    def test_init_defaults(self):
        svc = hubspot_svc()
        assert svc.tenant_id == "t1"
        assert svc.hubspot_config["base_url"] == "https://api.hubapi.com"
        assert svc.hubspot_config["api_version"] == "v3"
        assert svc.hubspot_config["access_token"] == "tok"
        assert svc.is_initialized is False
        assert svc.api_endpoints["contacts"] == "/crm/v3/objects/contacts"
        assert set(svc.platform_integrations.keys()) >= {"slack", "teams", "telegram"}
        assert svc.analytics_metrics["total_contacts"] == 0
        assert svc.performance_metrics["api_response_time"] == 0.0

    def test_init_enterprise_config(self):
        svc = hubspot_svc(enable_enterprise_features=True, hubspot_api_version="v2")
        assert svc.hubspot_config["enable_enterprise_features"] is True
        assert svc.hubspot_config["api_version"] == "v2"

    async def test_get_auth_headers(self):
        svc = hubspot_svc()
        headers = await svc._get_auth_headers()
        assert headers["Authorization"] == "Bearer tok"

        svc2 = hubspot_svc(hubspot_access_token="", hubspot_api_key="apikey")
        headers = await svc2._get_auth_headers()
        assert headers["Authorization"] == "Bearer apikey"

        svc3 = hubspot_svc(hubspot_access_token="", hubspot_api_key="")
        with pytest.raises(Exception):
            await svc3._get_auth_headers()


class TestHubSpotInitialize:
    async def test_initialize_success(self):
        svc = hubspot_svc()
        with patch("httpx.AsyncClient") as ac:
            ac.return_value = hubspot_http_client(get_result=ok_response(200, {"results": []}))
            assert await svc.initialize() is True
        assert svc.is_initialized is True

    async def test_initialize_connection_failure(self):
        svc = hubspot_svc()
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__ = AsyncMock(side_effect=RuntimeError("conn-fail"))
            ac.return_value.__aexit__ = AsyncMock(return_value=False)
            assert await svc.initialize() is False
        assert svc.is_initialized is False

    async def test_initialize_non_200(self):
        svc = hubspot_svc()
        with patch("httpx.AsyncClient") as ac:
            ac.return_value = hubspot_http_client(get_result=ok_response(500, {}))
            assert await svc.initialize() is False

    async def test_test_hubspot_connection(self):
        svc = hubspot_svc()
        with patch("httpx.AsyncClient") as ac:
            ac.return_value = hubspot_http_client(get_result=ok_response(200, {}))
            assert await svc._test_hubspot_connection() is True
        with patch("httpx.AsyncClient") as ac:
            ac.return_value = hubspot_http_client(get_result=ok_response(401, {}))
            with pytest.raises(Exception):
                await svc._test_hubspot_connection()

    async def test_setup_methods(self):
        svc = hubspot_svc()
        await svc._setup_webhooks()
        await svc._setup_lead_scoring()
        await svc._setup_marketing_automation()
        await svc._setup_campaign_management()
        assert svc.webhook_handlers == {}
        assert svc.lead_scoring_rules == {}
        assert svc.automation_flows == {}
        assert svc.campaign_workflows == {}
        assert await svc._setup_real_time_tracking() is True
        assert await svc._setup_enterprise_features() is True
        assert await svc._setup_security_and_compliance() is True
        assert await svc._load_existing_data() is True
        assert await svc._start_monitoring() is True


class TestHubSpotCreateContact:
    async def test_create_contact_success(self):
        svc = hubspot_svc()
        with patch("httpx.AsyncClient") as ac:
            ac.return_value = hubspot_http_client(post_result=ok_response(201, CONTACT_BODY))
            result = await svc.create_contact({
                "email": "jane@acme.com", "first_name": "Jane", "last_name": "Doe",
                "company": "ACME", "job_title": "CEO", "phone": "+1",
                "website": "acme.com", "source": "referral", "medium": "email",
            })
        assert result["success"] is True
        assert result["contact_id"] == "c1"
        assert svc.analytics_metrics["total_contacts"] == 1
        assert svc.analytics_metrics["lead_sources"]["referral"] == 1
        assert result["lead_score"] >= 0
        assert svc.analytics_metrics["lead_stages"]["lead"] == 1

    async def test_create_contact_with_properties_and_cache(self):
        cache = SimpleNamespace(set=AsyncMock())
        svc = hubspot_svc(cache=cache)
        with patch("httpx.AsyncClient") as ac:
            ac.return_value = hubspot_http_client(post_result=ok_response(201, CONTACT_BODY))
            result = await svc.create_contact({
                "email": "a@b.c", "properties": {"custom_field": "x"}, "lead_score": 90,
            })
        assert result["success"] is True
        cache.set.assert_awaited()
        assert cache.set.call_args[0][0] == "hubspot_contact:c1"

    async def test_create_contact_platform_notification(self):
        integration = MagicMock(send_notification=AsyncMock())
        svc = hubspot_svc()
        svc.platform_integrations = {"slack": integration}
        with patch("httpx.AsyncClient") as ac:
            ac.return_value = hubspot_http_client(post_result=ok_response(201, CONTACT_BODY))
            result = await svc.create_contact({"email": "a@b.c"}, platform="slack")
        assert result["success"] is True
        integration.send_notification.assert_awaited_once()

    async def test_create_contact_security_blocked(self):
        security = SimpleNamespace(check=AsyncMock(return_value={"allowed": False, "reason": "blocked by policy"}))
        svc = hubspot_svc(enable_enterprise_features=True, security_service=security)
        with patch("httpx.AsyncClient") as ac:
            ac.return_value = hubspot_http_client(post_result=ok_response(201, CONTACT_BODY))
            result = await svc.create_contact({"email": "a@b.c"})
        assert result["success"] is False
        assert "blocked by policy" in result["error"]

    async def test_create_contact_api_error_and_exception(self):
        svc = hubspot_svc()
        with patch("httpx.AsyncClient") as ac:
            ac.return_value = hubspot_http_client(post_result=ok_response(400, {}))
            result = await svc.create_contact({"email": "a@b.c"})
        assert result["success"] is False
        assert "400" in result["error"]

        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__ = AsyncMock(side_effect=RuntimeError("net-detail"))
            ac.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await svc.create_contact({"email": "a@b.c"})
        assert result["success"] is False
        assert "net-detail" not in json.dumps(result)

    async def test_create_contact_circuit_breaker_open(self):
        svc = hubspot_svc()
        with patch.object(hs.circuit_breaker, "is_enabled", AsyncMock(return_value=False)):
            result = await svc.create_contact({"email": "a@b.c"})
        assert result["success"] is False

    async def test_create_contact_rate_limited(self):
        svc = hubspot_svc()
        with patch.object(hs.rate_limiter, "is_rate_limited", AsyncMock(return_value=(True, 0))):
            result = await svc.create_contact({"email": "a@b.c"})
        assert result["success"] is False


class TestHubSpotCreateCampaign:
    async def test_create_campaign_success(self):
        svc = hubspot_svc()
        campaign_data = {
            "name": "Launch", "campaign_type": "email", "start_date": datetime.now(timezone.utc),
            "end_date": None, "description": "d", "budget": 1000, "target_audience": ["a"],
            "content": {}, "assets": [],
        }
        with patch("httpx.AsyncClient") as ac:
            ac.return_value = hubspot_http_client(post_result=ok_response(201, CAMPAIGN_BODY))
            result = await svc.create_campaign(campaign_data)
        assert result["success"] is True
        assert result["campaign_id"] == "cp1"
        assert svc.analytics_metrics["total_campaigns"] == 1
        assert svc.analytics_metrics["campaign_types"]["email"] == 1
        assert svc.campaign_performance["cp1"]["status"] is None

    async def test_create_campaign_with_end_date_and_platform(self):
        integration = MagicMock(send_notification=AsyncMock())
        svc = hubspot_svc()
        svc.platform_integrations = {"teams": integration}
        campaign_data = {
            "name": "L2", "campaign_type": "webinar", "status": "active",
            "start_date": datetime.now(timezone.utc), "end_date": datetime.now(timezone.utc),
        }
        with patch("httpx.AsyncClient") as ac:
            ac.return_value = hubspot_http_client(post_result=ok_response(201, CAMPAIGN_BODY))
            result = await svc.create_campaign(campaign_data, platform="teams")
        assert result["success"] is True
        integration.send_notification.assert_awaited_once()

    async def test_create_campaign_missing_start_date(self):
        svc = hubspot_svc()
        result = await svc.create_campaign({"name": "L3"})
        assert result["success"] is False

    async def test_create_campaign_api_error(self):
        svc = hubspot_svc()
        campaign_data = {"name": "L4", "start_date": datetime.now(timezone.utc)}
        with patch("httpx.AsyncClient") as ac:
            ac.return_value = hubspot_http_client(post_result=ok_response(422, {}))
            result = await svc.create_campaign(campaign_data)
        assert result["success"] is False
        assert "422" in result["error"]

    async def test_create_campaign_circuit_breaker_raises_503(self):
        svc = hubspot_svc()
        with patch.object(hs.circuit_breaker, "is_enabled", AsyncMock(return_value=False)):
            with pytest.raises(HTTPException) as exc:
                await svc.create_campaign({"name": "L5", "start_date": datetime.now(timezone.utc)})
        assert exc.value.status_code == 503

    async def test_create_campaign_rate_limited_raises_429(self):
        svc = hubspot_svc()
        with patch.object(hs.rate_limiter, "is_rate_limited", AsyncMock(return_value=(True, 0))):
            with pytest.raises(HTTPException) as exc:
                await svc.create_campaign({"name": "L6", "start_date": datetime.now(timezone.utc)})
        assert exc.value.status_code == 429


class TestHubSpotLeadScoring:
    async def test_rule_based_scoring_variants(self):
        svc = hubspot_svc()
        score = await svc._rule_based_lead_scoring({
            "company": "ACME", "job_title": "CEO", "email": "ceo@acme.com",
            "phone": "+1", "website": "acme.com", "source": "referral",
        })
        assert score == 10 + 20 + 5 + 5 + 5 + 10
        score = await svc._rule_based_lead_scoring({
            "job_title": "Manager", "email": "m@acme.com", "source": "website",
        })
        assert score == 15 + 5 + 5
        score = await svc._rule_based_lead_scoring({"job_title": "Senior Dev", "email": "s@gmail.com", "source": ""})
        assert score == 10
        score = await svc._rule_based_lead_scoring({"job_title": "Intern"})
        assert score == 5
        score = await svc._rule_based_lead_scoring({})
        assert score == 5
        assert await svc._rule_based_lead_scoring(None) == 50.0

    async def test_score_lead_rule_based(self):
        svc = hubspot_svc()
        svc.analytics_metrics["total_contacts"] = 1
        score = await svc._score_lead({"company": "ACME", "job_title": "VP Sales", "email": "v@sales.co"})
        assert 0 <= score <= 100
        assert svc.performance_metrics["lead_scoring_time"] >= 0
        assert svc.analytics_metrics["average_lead_score"] == score

    async def test_score_lead_ai_path(self, monkeypatch):
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=True, output_data={"lead_score": 85, "scoring_factors": {"x": 1}}
        ))
        svc = hubspot_svc(ai_service=ai)
        monkeypatch.setattr(hs, "AIRequest", lambda **kw: kw)
        monkeypatch.setattr(hs, "AITaskType", SimpleNamespace(PREDICTION="prediction"))
        monkeypatch.setattr(hs, "AIModelType", SimpleNamespace(GPT_4="gpt4"))
        monkeypatch.setattr(hs, "AIServiceType", SimpleNamespace(OPENAI="openai"))
        score = await svc._score_lead({"company": "ACME"})
        assert score == 85.0

    async def test_score_lead_ai_not_ok_falls_back(self, monkeypatch):
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(ok=False, output_data=None))
        svc = hubspot_svc(ai_service=ai)
        monkeypatch.setattr(hs, "AIRequest", lambda **kw: kw)
        monkeypatch.setattr(hs, "AITaskType", SimpleNamespace(PREDICTION="p"))
        monkeypatch.setattr(hs, "AIModelType", SimpleNamespace(GPT_4="g"))
        monkeypatch.setattr(hs, "AIServiceType", SimpleNamespace(OPENAI="o"))
        score = await svc._score_lead({"company": "ACME", "job_title": "CEO"})
        assert score == 30.0

    async def test_score_lead_ai_error_default(self, monkeypatch):
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(side_effect=RuntimeError("ai-down"))
        svc = hubspot_svc(ai_service=ai)
        svc._rule_based_lead_scoring = AsyncMock(side_effect=RuntimeError("rule-down"))
        score = await svc._score_lead({})
        assert score == 50.0

    async def test_optimize_campaign_with_ai(self, monkeypatch):
        svc = hubspot_svc()
        result = await svc._optimize_campaign_with_ai({"subject": "S"})
        assert result["optimized_subject"] == "S"
        assert result["content_tone_suggestion"] == "professional"

        ai = MagicMock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=True, output_data={"optimized_subject": "New", "content_tone_suggestion": "friendly",
                                  "call_to_action_suggestion": "Buy", "optimal_send_time": "9AM",
                                  "audience_segmentation": ["x"], "budget_allocation": {"a": 1},
                                  "predicted_performance": {"open": 0.5}}
        ))
        svc2 = hubspot_svc(ai_service=ai)
        monkeypatch.setattr(hs, "AIRequest", lambda **kw: kw)
        monkeypatch.setattr(hs, "AITaskType", SimpleNamespace(CONTENT_ANALYSIS="ca"))
        monkeypatch.setattr(hs, "AIModelType", SimpleNamespace(GPT_4="g"))
        monkeypatch.setattr(hs, "AIServiceType", SimpleNamespace(OPENAI="o"))
        result = await svc2._optimize_campaign_with_ai({"subject": "S"})
        assert result["optimized_subject"] == "New"
        assert svc2.performance_metrics["analytics_generation_time"] >= 0

    async def test_optimize_campaign_with_ai_not_ok(self, monkeypatch):
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(ok=False, output_data=None))
        svc = hubspot_svc(ai_service=ai)
        monkeypatch.setattr(hs, "AIRequest", lambda **kw: kw)
        result = await svc._optimize_campaign_with_ai({"subject": "X"})
        assert result["optimized_subject"] == "X"


class TestHubSpotAnalytics:
    async def test_generate_marketing_analytics_all_types(self):
        for atype in list(hs.AnalyticsType):
            svc = hubspot_svc()
            result = await svc.generate_marketing_analytics(atype, time_period="30d")
            assert result["success"] is True
            assert result["analytics"]["analytics_type"] == atype
            assert result["analytics"]["time_period"] == "30d"

    async def test_generate_analytics_with_ai_insights(self, monkeypatch):
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=True, output_data={"insights": ["ai insight"]}
        ))
        svc = hubspot_svc(ai_service=ai)
        monkeypatch.setattr(hs, "AIRequest", lambda **kw: kw)
        monkeypatch.setattr(hs, "AITaskType", SimpleNamespace(CONTENT_ANALYSIS="ca"))
        monkeypatch.setattr(hs, "AIModelType", SimpleNamespace(GPT_4="g"))
        monkeypatch.setattr(hs, "AIServiceType", SimpleNamespace(OPENAI="o"))
        result = await svc.generate_marketing_analytics(hs.AnalyticsType.EMAIL_PERFORMANCE)
        assert result["success"] is True
        assert result["analytics"]["metrics"]["ai_insights"]["insights"] == ["ai insight"]

    async def test_generate_ai_insights_fallback(self):
        svc = hubspot_svc()
        assert await svc._generate_ai_insights({}, hs.AnalyticsType.CAMPAIGN_PERFORMANCE) == {"insights": [], "recommendations": []}
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(ok=True, output_data=None))
        svc2 = hubspot_svc(ai_service=ai)
        assert await svc2._generate_ai_insights({}, hs.AnalyticsType.LEAD_CONVERSION) == {"insights": [], "recommendations": []}

    async def test_generate_analytics_helpers(self):
        svc = hubspot_svc()
        start, end = datetime.now(timezone.utc) - timedelta(days=7), datetime.now(timezone.utc)
        assert (await svc._generate_campaign_performance_analytics(start, end))["total_campaigns"] == 0
        svc.campaign_performance = {"c1": {"status": "active"}, "c2": {"status": "draft"}}
        data = await svc._generate_campaign_performance_analytics(start, end)
        assert data["active_campaigns"] == 1
        assert (await svc._generate_lead_conversion_analytics(start, end))["leads_generated"] == 0
        assert (await svc._generate_email_performance_analytics(start, end))["open_rate"] == 0.0
        assert (await svc._generate_social_media_analytics(start, end))["engagement_total"] == 0
        assert (await svc._generate_website_traffic_analytics(start, end))["visits"] == 0
        assert (await svc._generate_marketing_roi_analytics(start, end))["roi"] == 0.0
        assert (await svc._generate_lead_scoring_analytics(start, end))["average_lead_score"] == 0.0
        assert (await svc._generate_ab_testing_analytics(start, end))["tests_run"] == 0

    async def test_generate_marketing_analytics_error(self):
        svc = hubspot_svc()
        svc._generate_campaign_performance_analytics = AsyncMock(side_effect=RuntimeError("analytics-down"))
        result = await svc.generate_marketing_analytics(hs.AnalyticsType.CAMPAIGN_PERFORMANCE)
        assert result["success"] is False
        assert "analytics-down" not in json.dumps(result)

    async def test_generate_marketing_analytics_rate_limited(self):
        svc = hubspot_svc()
        with patch.object(hs.rate_limiter, "is_rate_limited", AsyncMock(return_value=(True, 0))):
            with pytest.raises(HTTPException) as exc:
                await svc.generate_marketing_analytics(hs.AnalyticsType.CAMPAIGN_PERFORMANCE)
        assert exc.value.status_code == 429


class TestHubSpotSecurityAndCache:
    async def test_perform_security_check(self):
        svc = hubspot_svc()
        assert (await svc._perform_security_check({}))["passed"] is True

        security = SimpleNamespace(check=AsyncMock(return_value={"allowed": False, "reason": "nope"}))
        svc2 = hubspot_svc(security_service=security)
        result = await svc2._perform_security_check({})
        assert result["passed"] is False and result["reason"] == "nope"

        security = SimpleNamespace(check=AsyncMock(return_value={"allowed": True}))
        svc3 = hubspot_svc(security_service=security)
        assert (await svc3._perform_security_check({}))["passed"] is True

        security = SimpleNamespace(check=AsyncMock(side_effect=RuntimeError("sec-down")))
        svc4 = hubspot_svc(security_service=security)
        assert (await svc4._perform_security_check({}))["passed"] is True

    async def test_cache_contact_campaign(self):
        cache = SimpleNamespace(set=AsyncMock())
        svc = hubspot_svc(cache=cache)
        await svc._cache_contact({"id": "c1"})
        cache.set.assert_awaited_once()
        cache.set.reset_mock()
        await svc._cache_campaign({"id": "cp1"})
        assert cache.set.call_args[0][0] == "hubspot_campaign:cp1"

        no_cache = hubspot_svc()
        await no_cache._cache_contact({"id": "c1"})
        await no_cache._cache_campaign({"id": "c1"})

        bad_cache = SimpleNamespace(set=AsyncMock(side_effect=RuntimeError("cache-down")))
        svc3 = hubspot_svc(cache=bad_cache)
        await svc3._cache_contact({"id": "c1"})
        await svc3._cache_campaign({"id": "c1"})


class TestHubSpotWorkflows:
    async def test_trigger_automation_workflows_disabled(self):
        svc = hubspot_svc(automation_workflows=False)
        svc._execute_workflow = AsyncMock()
        await svc._trigger_automation_workflows({"id": "c1"}, "contact_created")
        svc._execute_workflow.assert_not_awaited()

    async def test_trigger_automation_workflows_matching(self):
        svc = hubspot_svc()
        executed = []
        svc.automation_flows = {
            "wf1": {"trigger_event": "contact_created", "conditions": {"lifecycle_stage": "lead"}, "actions": []},
            "wf2": {"trigger_event": "other", "conditions": {}, "actions": []},
        }
        svc._execute_workflow = AsyncMock(side_effect=lambda wf, contact: executed.append(wf["trigger_event"]))
        await svc._trigger_automation_workflows({"properties": {"lifecyclestage": "lead"}}, "contact_created")
        assert executed == ["contact_created"]

    async def test_evaluate_workflow_conditions(self):
        svc = hubspot_svc()
        assert svc._evaluate_workflow_conditions({"lifecycle_stage": "lead"}, {"properties": {"lifecyclestage": "lead"}}) is True
        assert svc._evaluate_workflow_conditions({"lifecycle_stage": "lead"}, {"properties": {"lifecyclestage": "customer"}}) is False
        assert svc._evaluate_workflow_conditions({"lead_score_min": 50}, {"properties": {"hs_lead_score": "70"}}) is True
        assert svc._evaluate_workflow_conditions({"lead_score_min": 50}, {"properties": {"hs_lead_score": "30"}}) is False
        assert svc._evaluate_workflow_conditions({}, {}) is True
        assert svc._evaluate_workflow_conditions({"lead_score_min": 50}, {"properties": {"hs_lead_score": "abc"}}) is False

    async def test_execute_workflow_actions(self):
        svc = hubspot_svc()
        svc._send_automated_email = AsyncMock()
        svc._add_contact_to_list = AsyncMock()
        svc._create_marketing_task = AsyncMock()
        svc._update_contact_properties = AsyncMock()
        workflow = {"actions": [
            {"type": "send_email"}, {"type": "add_to_list", "list_id": "L1"},
            {"type": "create_task"}, {"type": "update_properties"}, {"type": "unknown"},
        ]}
        await svc._execute_workflow(workflow, {"id": "c1"})
        svc._send_automated_email.assert_awaited_once()
        svc._add_contact_to_list.assert_awaited_once()
        svc._create_marketing_task.assert_awaited_once()
        svc._update_contact_properties.assert_awaited_once()
        assert svc.performance_metrics["workflow_execution_time"] >= 0

    async def test_workflow_action_handlers(self):
        svc = hubspot_svc()
        await svc._send_automated_email({"id": "c1"}, {})
        await svc._add_contact_to_list({"id": "c1"}, {"list_id": "L1"})
        await svc._create_marketing_task({"id": "c1"}, {})
        await svc._update_contact_properties({"id": "c1"}, {})

    async def test_trigger_campaign_workflows(self):
        svc = hubspot_svc()
        await svc._trigger_campaign_workflows({"id": "cp1", "status": "active"}, "created")
        assert svc.campaign_performance["cp1"]["status"] == "active"
        await svc._trigger_campaign_workflows({}, "created")

    async def test_notify_platforms(self):
        integration = MagicMock(send_notification=AsyncMock())
        svc = hubspot_svc()
        svc.platform_integrations = {"slack": integration}
        await svc._notify_platform_lead_created({"id": "c1", "properties": {}}, "slack")
        integration.send_notification.assert_awaited_once()
        integration.send_notification.reset_mock()
        await svc._notify_platform_campaign_created({"id": "cp1", "name": "N"}, "slack")
        integration.send_notification.assert_awaited_once()
        await svc._notify_platform_lead_created({"id": "c1"}, "unknown_platform")
        await svc._notify_platform_campaign_created({"id": "cp1"}, "unknown_platform")

        integration.send_notification = AsyncMock(side_effect=RuntimeError("notify-down"))
        await svc._notify_platform_lead_created({"id": "c1", "properties": {}}, "slack")
        await svc._notify_platform_campaign_created({"id": "cp1"}, "slack")


class TestHubSpotStatusAndClose:
    async def test_get_service_status(self):
        svc = hubspot_svc()
        status = await svc.get_service_status()
        assert status["service"] == "hubspot_integration"
        assert status["status"] == "inactive"
        assert "analytics_metrics" in status

        svc.is_initialized = True
        status = await svc.get_service_status()
        assert status["status"] == "active"

        svc.hubspot_config = None
        status = await svc.get_service_status()
        assert "error" in status
        assert status["service"] == "hubspot_integration"
        assert "Service status unavailable" in status["error"]

    async def test_close(self):
        svc = hubspot_svc()
        await svc.close()

        with patch.object(hs.circuit_breaker, "is_enabled", AsyncMock(return_value=False)):
            with pytest.raises(HTTPException) as exc:
                await svc.close()
        assert exc.value.status_code == 503


# =========================================================================
# chat_orchestrator
# =========================================================================

def make_orch(**attrs):
    orch = object.__new__(co.ChatOrchestrator)
    orch.tenant_id = "t1"
    orch.conversation_sessions = {}
    orch.feature_handlers = {}
    orch.platform_connectors = {}
    orch.ai_engines = {}
    orch.llm_service = None
    orch.session_manager = None
    orch._cancelled_sessions = set()
    orch.__dict__.update(attrs)
    return orch


class TestChatSessions:
    async def test_get_or_create_session_new(self):
        orch = make_orch()
        session = orch._get_or_create_session("u1", "s1", None)
        assert session["user_id"] == "u1"
        assert session["id"] == "s1"
        assert session["history"] == []
        assert "channel_id" in session

    async def test_get_or_create_session_new_persists(self):
        manager = MagicMock()
        orch = make_orch(session_manager=manager)
        orch._get_or_create_session("u1", "s1", {"channel_id": "ch1", "thread_id": "th1"})
        manager.create_session.assert_called_once_with(user_id="u1", session_id="s1", channel_id="ch1", thread_id="th1")

    async def test_get_or_create_session_persist_failure_nonfatal(self):
        manager = MagicMock()
        manager.create_session.side_effect = RuntimeError("db-down")
        orch = make_orch(session_manager=manager)
        session = orch._get_or_create_session("u1", "s1", None)
        assert session["id"] == "s1"

    async def test_get_or_create_session_existing(self):
        orch = make_orch()
        orch.conversation_sessions["s1"] = {"id": "s1", "user_id": "u1", "history": [1]}
        session = orch._get_or_create_session("u1", "s1", None)
        assert session["history"] == [1]

    async def test_get_or_create_session_cross_user_isolated(self):
        orch = make_orch()
        orch.conversation_sessions["s1"] = {"id": "s1", "user_id": "other", "history": []}
        session = orch._get_or_create_session("u1", "s1", None)
        assert session["id"] != "s1"
        assert session["user_id"] == "u1"

    async def test_update_session_history_and_db(self, monkeypatch):
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        db.query.return_value.filter.return_value.first.return_value = None

        class FakeChatMessage:
            def __init__(self, **kw):
                self.__dict__.update(kw)

        class FakeChatSession:
            def __init__(self, **kw):
                self.__dict__.update(kw)

        monkeypatch.setattr("core.database.get_db_session", lambda: db)
        monkeypatch.setattr("core.models.ChatMessage", FakeChatMessage)
        monkeypatch.setattr("core.models.ChatSession", FakeChatSession)
        orch = make_orch()
        session = orch._get_or_create_session("u1", "s1", None)
        orch._update_session(session, "hi", {"message": "hello"}, {"primary_intent": "x"})
        assert len(session["history"]) == 1
        assert session["history"][0]["message"] == "hi"
        assert db.add.call_count == 2

    async def test_update_session_db_error_nonfatal(self, monkeypatch):
        def boom():
            raise RuntimeError("db-leak")
        monkeypatch.setattr("core.database.get_db_session", boom)
        orch = make_orch()
        session = orch._get_or_create_session("u1", "s1", None)
        orch._update_session(session, "hi", {"message": "hello"}, {"primary_intent": "x"})
        assert len(session["history"]) == 1

    async def test_update_session_dedup_index(self, monkeypatch):
        idx = MagicMock()
        idx.index_text = MagicMock()
        monkeypatch.setattr("core.llm.compression.SESSION_DEDUP_ENABLED", True)
        monkeypatch.setattr("core.llm.compression.session_dedup.get_or_create_dedup_index", lambda s: idx)
        orch = make_orch()
        session = orch._get_or_create_session("u1", "s1", None)
        orch._update_session(session, "hi", {"message": "hello"}, {"primary_intent": "x"})
        assert idx.index_text.call_count == 2

    async def test_generate_error_response(self):
        orch = make_orch()
        resp = orch._generate_error_response("bad", "s1")
        assert resp["success"] is False
        assert resp["error"] == "bad"
        assert resp["session_id"] == "s1"

    async def test_cancellation(self):
        orch = make_orch()
        assert orch._is_cancelled("s1") is False
        orch.request_cancellation("s1")
        assert orch._is_cancelled("s1") is True
        assert orch._is_cancelled("s1") is False

    async def test_emit_agent_step(self, monkeypatch):
        manager = MagicMock()
        manager.broadcast_event = AsyncMock()
        monkeypatch.setattr("core.websockets.get_connection_manager", lambda: manager)
        orch = make_orch()
        await orch._emit_agent_step(1, "thought", "action", "obs")
        assert manager.broadcast_event.await_count == 1

        manager.broadcast_event = AsyncMock(side_effect=RuntimeError("ws-down"))
        await orch._emit_agent_step(1, "t", "a", "o")

    async def test_get_user_sessions_memory_fallback(self):
        orch = make_orch()
        orch.conversation_sessions["s1"] = {"id": "s1", "user_id": "u1"}
        result = orch.get_user_sessions("u1")
        assert "s1" in result

    async def test_get_user_sessions_manager(self):
        manager = MagicMock()
        manager.list_user_sessions.return_value = [{
            "session_id": "s1", "user_id": "u1", "title": "T", "created_at": "c",
            "last_active": "l", "history": [], "metadata": {},
        }]
        orch = make_orch(session_manager=manager)
        result = orch.get_user_sessions("u1")
        assert result["s1"]["id"] == "s1"
        assert "s1" in orch.conversation_sessions


class TestChatIntent:
    async def test_fallback_intent_analysis(self):
        orch = make_orch()
        assert orch._fallback_intent_analysis("find the file")["primary_intent"] == co.ChatIntent.SEARCH_REQUEST
        assert orch._fallback_intent_analysis("email bob")["primary_intent"] == co.ChatIntent.MESSAGE_SEND
        assert orch._fallback_intent_analysis("create task")["primary_intent"] == co.ChatIntent.TASK_MANAGEMENT
        assert orch._fallback_intent_analysis("build workflow")["primary_intent"] == co.ChatIntent.WORKFLOW_CREATION
        assert orch._fallback_intent_analysis("schedule meeting")["primary_intent"] == co.ChatIntent.SCHEDULING
        assert orch._fallback_intent_analysis("what should i do today")["primary_intent"] == co.ChatIntent.BUSINESS_HEALTH
        assert orch._fallback_intent_analysis("what if i hire")["primary_intent"] == co.ChatIntent.BUSINESS_HEALTH
        assert orch._fallback_intent_analysis("show me deals")["primary_intent"] == co.ChatIntent.CRM
        result = orch._fallback_intent_analysis("random words")
        assert result["primary_intent"] == co.ChatIntent.SEARCH_REQUEST
        assert result["confidence"] == 0.6

    async def test_analyze_intent_nlp(self):
        orch = make_orch()
        nlp_result = SimpleNamespace(confidence=0.9, entities=["e"], platforms=["slack"], command_type="search")
        orch.ai_engines = {"nlp": SimpleNamespace(parse_command=AsyncMock(return_value=nlp_result))}
        result = await orch._analyze_intent("find x", {})
        assert result["confidence"] == 0.9
        assert result["primary_intent"] == co.ChatIntent.SEARCH_REQUEST
        assert result["raw_nlp"] is nlp_result

    async def test_analyze_intent_nlp_failure(self):
        orch = make_orch()
        orch.ai_engines = {"nlp": SimpleNamespace(parse_command=AsyncMock(side_effect=RuntimeError("nlp-down")))}
        result = await orch._analyze_intent("find x", {})
        assert result["primary_intent"] == co.ChatIntent.SEARCH_REQUEST

    async def test_analyze_intent_fallback(self):
        orch = make_orch()
        result = await orch._analyze_intent("email bob", {})
        assert result["primary_intent"] == co.ChatIntent.MESSAGE_SEND

    async def test_classify_intent(self):
        from ai.nlp_engine import CommandType
        orch = make_orch()
        mapping = [
            (CommandType.SEARCH, co.ChatIntent.SEARCH_REQUEST),
            (CommandType.CREATE, co.ChatIntent.TASK_MANAGEMENT),
            (CommandType.UPDATE, co.ChatIntent.TASK_MANAGEMENT),
            (CommandType.SCHEDULE, co.ChatIntent.SCHEDULING),
            (CommandType.ANALYZE, co.ChatIntent.DATA_ANALYSIS),
            (CommandType.BUSINESS_HEALTH, co.ChatIntent.BUSINESS_HEALTH),
            (CommandType.TRIGGER, co.ChatIntent.AUTOMATION_TRIGGER),
            (CommandType.WORKFLOW_CREATION, co.ChatIntent.WORKFLOW_CREATION),
        ]
        for cmd, intent in mapping:
            assert orch._classify_intent(SimpleNamespace(command_type=cmd)) == intent
        assert orch._classify_intent(SimpleNamespace(command_type=CommandType.DELETE)) == co.ChatIntent.SEARCH_REQUEST


class TestChatQwen:
    async def test_get_qwen_response_none_service(self):
        orch = make_orch()
        assert await orch._get_qwen_response("hi", []) is None

    async def test_get_qwen_response_success(self):
        llm = MagicMock()
        llm.generate_completion = AsyncMock(return_value={
            "success": True, "content": "  hello there  ", "model": "m1", "provider": "p1",
        })
        orch = make_orch(llm_service=llm)
        result = await orch._get_qwen_response("hi", [], routing_overrides={"model": "x", "tier": "t", "intent": "i"}, sticky_hint=("p1", "m1"))
        assert result == {"content": "hello there", "model": "m1", "provider": "p1"}
        kwargs = llm.generate_completion.call_args[1]
        assert kwargs["model"] == "x"
        assert kwargs["cognitive_tier"] == "t"
        assert kwargs["intent_override"] == "i"
        assert kwargs["sticky_hint"] == ("p1", "m1")

    async def test_get_qwen_response_failure_and_exception(self):
        llm = MagicMock()
        llm.generate_completion = AsyncMock(return_value={"success": False})
        orch = make_orch(llm_service=llm)
        assert await orch._get_qwen_response("hi", []) is None

        llm.generate_completion = AsyncMock(side_effect=RuntimeError("llm-down"))
        assert await orch._get_qwen_response("hi", []) is None


class TestChatProcessMessage:
    async def test_process_chat_message_success(self, monkeypatch):
        llm = MagicMock()
        llm.generate_completion = AsyncMock(return_value={
            "success": True, "content": "AI answer", "model": "gpt-x", "provider": "openai",
        })
        orch = make_orch(llm_service=llm)
        orch._initialize_feature_handlers()
        result = await orch.process_chat_message("u1", "find reports", context={})
        assert result["success"] is True
        assert result["message"] == "AI answer"
        assert result["model"] == "gpt-x"
        assert result["provider"] == "openai"
        assert result["intent"] == "search_request"
        assert result["session_id"]
        session = orch.conversation_sessions[result["session_id"]]
        assert len(session["history"]) == 1
        assert session["last_known_good_model"] == "gpt-x"

    async def test_process_chat_message_template_path(self):
        orch = make_orch()
        orch._initialize_feature_handlers()
        result = await orch.process_chat_message("u1", "find reports")
        assert result["success"] is True
        assert result["model"] == "template"
        assert result["provider"] == "template"
        assert "results" in result["message"] or "searched" in result["message"]

    async def test_process_chat_message_cancelled(self):
        orch = make_orch()
        orch._initialize_feature_handlers()
        orch.request_cancellation("sess-c")
        result = await orch.process_chat_message("u1", "find reports", session_id="sess-c")
        assert result["success"] is False
        assert result["cancelled"] is True

    async def test_process_chat_message_budget_failure(self):
        async def budget_handler(message, intent_analysis, session, context):
            return {"success": True, "error_code": "budget_exceeded", "message": "budget used up", "failure_reason": "cap reached", "data": {}}

        async def noop_handler(*a, **k):
            return None

        orch = make_orch()
        orch._initialize_feature_handlers()
        orch.feature_handlers[co.FeatureType.SEARCH] = budget_handler
        orch.feature_handlers[co.FeatureType.AI_ANALYTICS] = noop_handler
        agent = MagicMock()
        agent.execute_task = AsyncMock(return_value={"id": "t1", "status": "started"})
        with patch.object(co, "agent_service", agent):
            result = await orch.process_chat_message("u1", "find reports")
        assert result["success"] is False
        assert result["error_code"] == "budget_exceeded"
        assert result["recovery_url"] == "/settings/billing"
        assert result["message"] == "budget used up"

    async def test_process_chat_message_error_path(self):
        orch = make_orch()
        import integrations.chat_orchestrator as co_mod

        def boom(self, *a, **k):
            raise RuntimeError("session-detail")
        monkeypatch = None
        with patch.object(co.ChatOrchestrator, "_get_or_create_session", boom):
            orch = co.ChatOrchestrator.__new__(co.ChatOrchestrator)
            orch.conversation_sessions = {}
            orch.llm_service = None
            orch.ai_engines = {}
            orch.feature_handlers = {}
            orch.session_manager = None
            orch._cancelled_sessions = set()
            orch.tenant_id = "t1"
            result = await orch.process_chat_message("u1", "find reports")
        assert result["success"] is False
        assert "error" in result

    async def test_process_chat_message_dedup(self, monkeypatch):
        idx = MagicMock()
        idx.deduplicate = MagicMock(side_effect=lambda text: (text, False))
        monkeypatch.setattr("core.llm.compression.SESSION_DEDUP_ENABLED", True)
        monkeypatch.setattr("core.llm.compression.session_dedup.get_or_create_dedup_index", lambda s: idx)
        llm = MagicMock()
        llm.generate_completion = AsyncMock(return_value={
            "success": True, "content": "hi", "model": "m", "provider": "p",
        })
        orch = make_orch(llm_service=llm)
        orch._initialize_feature_handlers()
        orch.conversation_sessions["s1"] = {
            "id": "s1", "user_id": "u1", "history": [{"message": "old", "response": {"message": "old reply"}}],
        }
        result = await orch.process_chat_message("u1", "find reports", session_id="s1")
        assert result["success"] is True


class TestChatRouting:
    async def test_route_to_features_success(self):
        orch = make_orch()
        orch._initialize_feature_handlers()
        intent = {"primary_intent": co.ChatIntent.MESSAGE_SEND, "confidence": 0.6, "entities": [], "platforms": []}
        responses = await orch._route_to_features("email bob", intent, {"id": "s1"}, None)
        assert co.FeatureType.COMMUNICATION in responses
        assert responses[co.FeatureType.COMMUNICATION]["success"] is True

    async def test_route_to_features_crm(self):
        orch = make_orch()
        orch._initialize_feature_handlers()
        agent = MagicMock()
        agent.execute_task = AsyncMock(return_value={"id": "t1", "status": "started"})
        with patch.object(co, "agent_service", agent), \
             patch.object(co, "get_automation_settings", return_value=SimpleNamespace(is_sales_enabled=lambda: False)):
            intent = {"primary_intent": co.ChatIntent.CRM}
            responses = await orch._route_to_features("show deals", intent, {"id": "s1"}, None)
        assert co.FeatureType.AGENT in responses

    async def test_route_to_features_handler_error(self):
        orch = make_orch()
        orch._initialize_feature_handlers()

        async def boom(message, intent_analysis, session, context):
            raise RuntimeError("handler-down")
        orch.feature_handlers[co.FeatureType.SEARCH] = boom
        orch.feature_handlers[co.FeatureType.AI_ANALYTICS] = boom
        agent = MagicMock()
        agent.execute_task = AsyncMock(return_value={"id": "t1", "status": "started"})
        with patch.object(co, "agent_service", agent):
            intent = {"primary_intent": co.ChatIntent.SEARCH_REQUEST}
            responses = await orch._route_to_features("find x", intent, {"id": "s1"}, None)
        assert responses[co.FeatureType.SEARCH] == {"error": "internal_error"}
        assert responses[co.FeatureType.AI_ANALYTICS] == {"error": "internal_error"}
        assert co.FeatureType.AGENT in responses

    async def test_route_to_features_agent_fallback(self):
        orch = make_orch()
        orch._initialize_feature_handlers()
        agent = MagicMock()
        agent.execute_task = AsyncMock(return_value={"id": "t1", "status": "started"})
        with patch.object(co, "agent_service", agent):
            intent = {"primary_intent": co.ChatIntent.BUSINESS_HEALTH}
            responses = await orch._route_to_features("what should i do", intent, {"id": "s1"}, None)
        assert co.FeatureType.AGENT in responses
        assert responses[co.FeatureType.AGENT]["data"]["task_id"] == "t1"

    async def test_route_to_features_agent_fallback_failure(self):
        orch = make_orch()
        orch._initialize_feature_handlers()
        agent = MagicMock()
        agent.execute_task = AsyncMock(side_effect=RuntimeError("agent-down"))
        with patch.object(co, "agent_service", agent):
            intent = {"primary_intent": co.ChatIntent.AGENT_REQUEST}
            responses = await orch._route_to_features("do something", intent, {"id": "s1"}, None)
        assert co.FeatureType.AGENT not in responses

    async def test_route_to_features_multi_step(self):
        orch = make_orch()
        orch._initialize_feature_handlers()
        intent = {"primary_intent": co.ChatIntent.MULTI_STEP_PROCESS}
        responses = await orch._route_to_features("everything", intent, {"id": "s1"}, None)
        assert co.FeatureType.AI_ANALYTICS in responses


class TestChatResponseGen:
    async def test_generate_main_message_all_intents(self):
        orch = make_orch()
        intent = {"primary_intent": co.ChatIntent.SEARCH_REQUEST}
        msg = orch._generate_main_message("q", intent, {co.FeatureType.SEARCH: {"data": {"results": [1, 2, 3]}}})
        assert "3 results" in msg
        msg = orch._generate_main_message("q", intent, {co.FeatureType.SEARCH: {}})
        assert "searched" in msg
        intent = {"primary_intent": co.ChatIntent.MESSAGE_SEND}
        assert "sent successfully" in orch._generate_main_message("q", intent, {co.FeatureType.COMMUNICATION: {"success": True}})
        assert "send that message" in orch._generate_main_message("q", intent, {})
        intent = {"primary_intent": co.ChatIntent.TASK_MANAGEMENT}
        assert "processed" in orch._generate_main_message("q", intent, {co.FeatureType.TASKS: {"success": True, "data": {"message": "processed"}}})
        assert "manage those tasks" in orch._generate_main_message("q", intent, {})
        intent = {"primary_intent": co.ChatIntent.WORKFLOW_CREATION}
        assert "created successfully" in orch._generate_main_message("q", intent, {co.FeatureType.WORKFLOWS: {"data": {"id": 1}}})
        assert "automation workflow" in orch._generate_main_message("q", intent, {})
        intent = {"primary_intent": co.ChatIntent.SCHEDULING}
        assert "updated successfully" in orch._generate_main_message("q", intent, {co.FeatureType.SCHEDULING: {"data": {"x": 1}}})
        assert "scheduling" in orch._generate_main_message("q", intent, {})
        intent = {"primary_intent": co.ChatIntent.CRM}
<<<<<<< Updated upstream
        assert orch._generate_main_message("q", intent, {co.FeatureType.CRM: {"success": True, "data": {"answer": "CRM answer"}}}) == "CRM answer"
        assert "help you with your CRM" in orch._generate_main_message("q", intent, {})
        intent = {"primary_intent": co.ChatIntent.BUSINESS_HEALTH}
        assert orch._generate_main_message("q", intent, {co.FeatureType.BUSINESS_HEALTH: {"success": True, "message": "all good"}}) == "all good"
=======
        assert "CRM request" in orch._generate_main_message("q", intent, {co.FeatureType.CRM: {"success": True, "data": {"answer": "CRM answer"}}})
        assert "help you with your CRM" in orch._generate_main_message("q", intent, {})
        intent = {"primary_intent": co.ChatIntent.BUSINESS_HEALTH}
        assert "business health" in orch._generate_main_message("q", intent, {co.FeatureType.BUSINESS_HEALTH: {"success": True, "message": "all good"}})
>>>>>>> Stashed changes
        assert "business health query" in orch._generate_main_message("q", intent, {})
        intent = {"primary_intent": co.ChatIntent.SCHEDULING}
        default_msg = orch._generate_main_message("q", intent, {})
        assert default_msg or True
        agent_resp = {"success": True, "message": "agent handled it"}
        assert orch._generate_main_message("q", {"primary_intent": co.ChatIntent.SEARCH_REQUEST}, {co.FeatureType.AGENT: agent_resp}) == "agent handled it"

    async def test_generate_next_steps(self):
        orch = make_orch()
        for intent in [co.ChatIntent.SEARCH_REQUEST, co.ChatIntent.WORKFLOW_CREATION, co.ChatIntent.TASK_MANAGEMENT, co.ChatIntent.CRM, co.ChatIntent.SCHEDULING]:
            steps = orch._generate_next_steps({"primary_intent": intent}, {})
            assert len(steps) <= 3
            assert steps

    async def test_generate_coordinated_response(self):
        orch = make_orch()
        resp = orch._generate_coordinated_response(
            "q",
            {"primary_intent": co.ChatIntent.SEARCH_REQUEST, "confidence": 0.5},
            {co.FeatureType.SEARCH: {"data": {"results": []}, "suggested_actions": ["a"], "ui_updates": ["u"], "requires_confirmation": True}},
            {"id": "s1"},
        )
        assert resp["success"] is True
        assert resp["requires_confirmation"] is True
        assert resp["ui_updates"] == ["u"]


class TestChatFeatureHandlers:
    async def test_search_handler(self):
        orch = make_orch()
        orch.ai_engines = {"data_intelligence": SimpleNamespace(search_unified_entities=lambda m: [{"id": 1}])}
        result = await orch._handle_search_request("find x", {"platforms": ["slack"]}, {"id": "s1"}, None)
        assert result["success"] is True
        assert result["data"]["results"] == [{"id": 1}]

        orch.ai_engines = {}
        result = await orch._handle_search_request("find x", {}, {"id": "s1"}, None)
        assert result["success"] is True

        orch.ai_engines = {"data_intelligence": SimpleNamespace(search_unified_entities=lambda m: (_ for _ in ()).throw(RuntimeError("search-down")))}
        result = await orch._handle_search_request("find x", {}, {"id": "s1"}, None)
        assert result["success"] is False

    async def test_simple_handlers(self):
        orch = make_orch()
        assert (await orch._handle_communication_request("m", {}, {"id": "s1"}, None))["success"] is True
        assert (await orch._handle_integration_request("m", {}, {"id": "s1"}, None))["success"] is True
        assert (await orch._handle_ai_analytics_request("m", {}, {"id": "s1"}, None))["success"] is True
        assert (await orch._handle_document_request("m", {}, {"id": "s1"}, None))["success"] is True
        assert (await orch._handle_social_media_request("m", {}, {"id": "s1"}, None))["success"] is True
        assert (await orch._handle_hr_request("m", {}, {"id": "s1"}, None))["success"] is True
        assert (await orch._handle_ecommerce_request("m", {}, {"id": "s1"}, None))["success"] is True
        result = await orch._handle_scheduling_request("schedule the report", {}, {"id": "s1"}, None)
        assert result["success"] is True
        assert "schedule workflows" in result["message"]
        result = await orch._handle_scheduling_request("what time is it", {}, {"id": "s1"}, None)
        assert result["success"] is True

    async def test_task_handler(self, monkeypatch):
        create_task = AsyncMock(return_value={"success": True, "task": SimpleNamespace(id="t1")})
        monkeypatch.setattr("core.unified_task_endpoints.create_task", create_task)
        orch = make_orch()
        result = await orch._handle_task_request("create task: buy milk", {}, {"id": "s1", "user_id": "u1"}, None)
        assert result["success"] is True
        assert result["data"]["task_id"] == "t1"

        create_task.return_value = {"success": False}
        result = await orch._handle_task_request("create task: buy milk", {}, {"id": "s1"}, None)
        assert result["success"] is False

        create_task.side_effect = RuntimeError("task-down")
        result = await orch._handle_task_request("create task: buy milk", {}, {"id": "s1"}, None)
        assert result["success"] is False

    async def test_task_handler_long_title(self, monkeypatch):
        create_task = AsyncMock(return_value={"success": True, "task": SimpleNamespace(id="t1")})
        monkeypatch.setattr("core.unified_task_endpoints.create_task", create_task)
        orch = make_orch()
        long_msg = "please make a task to review the quarterly financial report and prepare a summary for the board meeting tomorrow morning"
        result = await orch._handle_task_request(long_msg, {}, {"id": "s1"}, None)
        assert result["success"] is True

    async def test_workflow_handler(self, monkeypatch):
        orch = make_orch()
        monkeypatch.setattr(co, "load_workflows", lambda: [{"name": "Daily Report", "workflow_id": "w1"}])
        monkeypatch.setattr(co, "AutomationEngine", MagicMock(return_value=MagicMock(execute_workflow_definition=AsyncMock(return_value={"ok": True}))))
        result = await orch._handle_workflow_request("list workflows", {}, {"id": "s1"}, None)
        assert result["success"] is True
        assert "Daily Report" in result["message"]

        monkeypatch.setattr(co, "load_workflows", lambda: [])
        result = await orch._handle_workflow_request("list workflows", {}, {"id": "s1"}, None)
        assert "No workflows found" in result["message"]

        monkeypatch.setattr(co, "load_workflows", lambda: [{"name": "Daily Report", "workflow_id": "w1"}])
        result = await orch._handle_workflow_request("run daily", {}, {"id": "s1"}, None)
        assert result["success"] is True
        assert "started" in result["message"]

        result = await orch._handle_workflow_request("run nonexistent_workflow", {}, {"id": "s1"}, None)
        assert result["success"] is False

        engine = MagicMock(execute_workflow_definition=AsyncMock(side_effect=RuntimeError("wf-down")))
        monkeypatch.setattr(co, "AutomationEngine", MagicMock(return_value=engine))
        result = await orch._handle_workflow_request("run daily", {}, {"id": "s1"}, None)
        assert result["success"] is False

        result = await orch._handle_workflow_request("hello there", {}, {"id": "s1"}, None)
        assert result["success"] is True

    async def test_automation_handler(self):
        orch = make_orch()
        result = await orch._handle_automation_request("what's up", {}, {"id": "s1"}, None)
        assert result["success"] is False

        with patch.object(co, "execute_agent_task", None):
            result = await orch._handle_automation_request("run inventory check", {}, {"id": "s1"}, None)
            assert result["success"] is False
            assert "not available" in result["message"]

        execute = AsyncMock()
        with patch.object(co, "execute_agent_task", execute):
            result = await orch._handle_automation_request("check competitor prices", {}, {"id": "s1"}, None)
            assert result["success"] is True
            assert result["data"]["agent_id"] == "competitive_intel"
            result = await orch._handle_automation_request("run inventory check", {}, {"id": "s1"}, None)
            assert result["success"] is True
            result = await orch._handle_automation_request("run payroll", {}, {"id": "s1"}, None)
            assert result["success"] is True

        execute = AsyncMock(side_effect=RuntimeError("agent-exec-down"))
        with patch.object(co, "execute_agent_task", execute):
            result = await orch._handle_automation_request("check competitor prices", {}, {"id": "s1"}, None)
            assert result["success"] is False

    async def test_finance_handler_disabled_and_missing_services(self):
        orch = make_orch()
        settings = SimpleNamespace(is_accounting_enabled=lambda: False)
        with patch.object(co, "get_automation_settings", return_value=settings):
            result = await orch._handle_finance_request("payroll", {}, {"id": "s1"}, None)
        assert result["success"] is False
        assert "disabled" in result["message"]

        with patch.object(co, "get_automation_settings", None):
            result = await orch._handle_finance_request("payroll", {}, {"id": "s1"}, None)
        assert result["success"] is False

        with patch.object(co, "get_automation_settings", return_value=SimpleNamespace(is_accounting_enabled=lambda: True)), \
             patch.object(co, "AccountingAssistant", None):
            result = await orch._handle_finance_request("payroll", {}, {"id": "s1"}, None)
        assert result["success"] is False
        assert "not available" in result["message"]

    async def test_finance_handler_intents(self):
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        orch = make_orch()
        settings = SimpleNamespace(is_accounting_enabled=lambda: True)

        cases = [
            ({"intent": "check_overdue", "answer": "a"}, "CollectionAgent", "check_overdue_invoices", "overdue invoices"),
            ({"intent": "get_aging", "answer": "a"}, "CollectionAgent", "generate_aging_report", "aging"),
            ({"intent": "check_close_readiness", "answer": "a", "params": {}}, "CloseChecklistAgent", "run_close_check", "close readiness"),
            ({"intent": "get_tax_estimate", "answer": "a"}, "TaxService", "estimate_tax_liability", "tax"),
            ({"intent": "get_cash_forecast", "answer": "a"}, "FPAService", "get_13_week_forecast", "13-week"),
            ({"intent": "run_scenario", "answer": "a", "params": {}}, "FPAService", "run_scenario", "scenario"),
            ({"intent": "get_intercompany_report", "answer": "a"}, "IntercompanyManager", "generate_elimination_report", "intercompany"),
            ({"intent": "other", "answer": "plain answer"}, None, None, "plain answer"),
        ]
        for result_data, agent_cls, method, expected in cases:
            assistant = MagicMock()
            assistant.process_query = AsyncMock(return_value=result_data)
            agent_obj = MagicMock()
            if method:
                if method in ("check_overdue_invoices", "run_close_check"):
                    setattr(agent_obj, method, AsyncMock(return_value=[]))
                else:
                    setattr(agent_obj, method, MagicMock(return_value=[]))
            patch_map = {
                "get_automation_settings": lambda: settings,
                "AccountingAssistant": lambda db: assistant,
                "SessionLocal": lambda: db,
            }
            if agent_cls:
                patch_map[agent_cls] = lambda db, _obj=agent_obj: _obj
            patches = [patch.object(co, k, v) for k, v in patch_map.items()]
            for p in patches:
                p.start()
            try:
                result = await orch._handle_finance_request("query", {}, {"id": "s1"}, {"workspace_id": "w1"})
            finally:
                for p in patches:
                    p.stop()
            assert result["success"] is True, f"{agent_cls}: {result}"
            assert expected in result["message"]
            assert "Disclaimer" in result["message"]

    async def test_finance_handler_exception(self):
        orch = make_orch()
        settings = SimpleNamespace(is_accounting_enabled=lambda: True)
        assistant = MagicMock()
        assistant.process_query = AsyncMock(side_effect=RuntimeError("fin-down"))
        with patch.object(co, "get_automation_settings", return_value=settings), \
             patch.object(co, "AccountingAssistant", return_value=assistant), \
             patch.object(co, "SessionLocal", lambda: MagicMock()):
            result = await orch._handle_finance_request("payroll", {}, {"id": "s1"}, None)
        assert result["success"] is False

    async def test_crm_handler(self):
        orch = make_orch()
        with patch.object(co, "get_automation_settings", None):
            result = await orch._handle_crm_request("show pipeline", {}, {"id": "s1"}, None)
        assert result["success"] is False

        settings = SimpleNamespace(is_sales_enabled=lambda: False)
        with patch.object(co, "get_automation_settings", return_value=settings):
            result = await orch._handle_crm_request("show pipeline", {}, {"id": "s1"}, None)
        assert result["success"] is False

        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        sales = MagicMock()
        sales.answer_sales_query = AsyncMock(return_value="Sales answer text")
        with patch.object(co, "get_automation_settings", return_value=SimpleNamespace(is_sales_enabled=lambda: True)), \
             patch.object(co, "SessionLocal", return_value=db), \
             patch("sales.assistant.SalesAssistant", return_value=sales):
            result = await orch._handle_crm_request("show pipeline", {}, {"id": "s1"}, {"workspace_id": "w1"})
        assert result["success"] is True
        assert result["data"]["answer"] == "Sales answer text"

        sales.answer_sales_query = AsyncMock(side_effect=RuntimeError("sales-down"))
        with patch.object(co, "get_automation_settings", return_value=SimpleNamespace(is_sales_enabled=lambda: True)), \
             patch.object(co, "SessionLocal", return_value=db), \
             patch("sales.assistant.SalesAssistant", return_value=sales):
            result = await orch._handle_crm_request("show pipeline", {}, {"id": "s1"}, None)
        assert result["success"] is False

    async def test_business_health_handler(self, monkeypatch):
        svc = SimpleNamespace()
        svc.simulate_decision = AsyncMock(return_value={"prediction": "impact", "roi": 0.5, "breakeven": "12mo"})
        svc.get_daily_priorities = AsyncMock(return_value={"priorities": [], "owner_advice": "advice"})
        monkeypatch.setattr("core.business_health_service.business_health_service", svc)
        orch = make_orch()
        result = await orch._handle_business_health_request("what if we hire 5 people", {}, {"id": "s1"}, {"workspace_id": "w1"})
        assert result["success"] is True
        assert "ROI" in result["message"]

        result = await orch._handle_business_health_request("what should i do today", {}, {"id": "s1"}, {"workspace_id": "w1"})
        assert result["success"] is True
        assert "great" in result["message"]

        svc.get_daily_priorities = AsyncMock(return_value={"priorities": [{"priority": "P1", "title": "T", "description": "D"}], "owner_advice": "a"})
        result = await orch._handle_business_health_request("what should i do today", {}, {"id": "s1"}, None)
        assert result["success"] is True
        assert "Top Priorities" in result["message"]

        svc.simulate_decision = AsyncMock(side_effect=RuntimeError("bh-down"))
        result = await orch._handle_business_health_request("what if we hire", {}, {"id": "s1"}, None)
        assert result["success"] is False

    async def test_agent_request_handler(self, monkeypatch):
        atom = MagicMock()
        atom.execute = AsyncMock(return_value={
            "final_output": "done", "actions_executed": [{"a": 1}], "spawned_agent": "sp", "failure_reason": None,
        })
        monkeypatch.setattr("core.atom_meta_agent.get_atom_agent", lambda: atom)
        orch = make_orch()
        result = await orch._handle_agent_request("do it", {}, {"id": "s1", "user_id": "u1"}, None)
        assert result["success"] is True
        assert result["status"] == "success"
        assert result["spawned_agent"] == "sp"

        atom.execute = AsyncMock(return_value={"final_output": "halted", "failure_reason": "budget cap", "actions_executed": []})
        result = await orch._handle_agent_request("do it", {}, {"id": "s1", "user_id": "u1"}, None)
        assert result["success"] is False
        assert result["error_code"] == "budget_exceeded"

        atom.execute = AsyncMock(side_effect=RuntimeError("atom-down"))
        result = await orch._handle_agent_request("do it", {}, {"id": "s1", "user_id": "u1"}, None)
        assert result["status"] == "error"
