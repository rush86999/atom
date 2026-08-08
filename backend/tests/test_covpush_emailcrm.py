# -*- coding: utf-8 -*-
"""
Coverage-push tests for:
- integrations.microsoft365_service (Graph API, aiohttp)
- integrations.gmail_service (Google API, mocked google libs)

TDD: each REAL bug found has a failing test first, then a minimal fix.
"""
import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import aiohttp

import integrations.microsoft365_service as m365
import integrations.gmail_service as gs


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
    assert result == {"status": "success", "data": {"id": "mock_id_123"}}


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

    session = FakeAioSession(FakeAioResponse(200, data={"id": "f1"}))
    monkeypatch.setattr(aiohttp, "ClientSession", lambda *a, **k: session)
    result = await svc.execute_onedrive_action("real_token", "upload", {"path": "x", "file_content": b"data", "content_type": "text/plain"})
    assert result["status"] == "success"
    assert result["data"]["id"] == "f1"

    monkeypatch.setattr(aiohttp, "ClientSession", lambda *a, **k: FakeAioSession(FakeAioResponse(400, body="upload rejected")))
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
    result = await svc.create_subscription("fake_token", "created", "http://hook", "2026-12-31T00:00:00Z")
    assert result["status"] == "success"
    result = await svc.create_subscription("fake_token", "updated", "http://hook", "2026-12-31T00:00:00Z")
    assert result["status"] == "success"


async def test_m365_subscriptions_exception(monkeypatch):
    svc = make_service()

    async def boom(*a, **k):
        raise RuntimeError("sub-leak")

    monkeypatch.setattr(svc, "_make_graph_request", boom)
    result = await svc.create_subscription("t", "created", "h", "d")
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


async def test_gmail_get_labels(gmail_env):
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
    def __init__(self, existing=None, commit_error=None):
        self.existing = existing
        self.commit_error = commit_error
        self.added = []
        self.closed = False

    def query(self, model):
        return self

    def filter_by(self, **kw):
        return self

    def first(self):
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

    db2 = FakeHubDB(existing=FakeMetric(value=0))
    monkeypatch.setattr("core.database.SessionLocal", lambda: db2)
    result = await svc.sync_to_postgres_cache(user_id="u1")
    assert result["success"] is True
    assert db2.existing.value == 10.0


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
    async def fake_sync(**kw):
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

    async def fake_get_message(mid):
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
