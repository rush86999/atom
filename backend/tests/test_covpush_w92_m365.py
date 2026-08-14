"""Coverage wave 92 — integrations/microsoft365_service.py (13% → 95%+).

Closes the never-wave-tested gaps: Microsoft365Service auth/health/
execute_operation dispatch, Graph request helper (mock bypass, aiohttp
success/error/204 paths), OneDrive/Excel/PowerBI/Teams/Outlook/Planner
action families (every param-validation + success + exception branch),
subscription lifecycle, legacy _send_message/_list_teams/_list_channels,
token-expiry-style error surfaces, and every route (auth, user, teams,
channels, messages, calendar, status, health).

Security: all router endpoints previously had NO auth dependency (anonymous
401). This wave asserts 401 for anonymous callers on every endpoint (RED)
and wires Depends(get_current_user) on the router (GREEN).
"""
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security_dependencies import get_current_user
from integrations import microsoft365_service as m365
from integrations.microsoft365_service import Microsoft365Service

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


# --------------------------------------------------------------------------
# Service unit tests (real instance, _make_graph_request mocked)
# --------------------------------------------------------------------------

def make_service(**kwargs) -> Microsoft365Service:
    return Microsoft365Service(tenant_id="t1", config=kwargs.get("config", {}))


def ok_response(data):
    return {"status": "success", "data": data}


class TestInitAndCapabilities:
    def test_defaults(self):
        svc = Microsoft365Service()
        assert svc.service_name == "microsoft365"
        assert svc.base_url == "https://graph.microsoft.com/v1.0"
        assert svc.required_scopes == m365.MICROSOFT365_SCOPES
        assert svc.config == {}

    def test_capabilities(self):
        caps = make_service().get_capabilities()
        assert "send_message" in caps
        assert "read_files" in caps

    def test_health_with_token(self):
        svc = make_service(config={"access_token": "tok"})
        assert asyncio_run(svc.health_check())["status"] == "healthy"

    def test_health_unconfigured(self):
        svc = make_service()
        assert asyncio_run(svc.health_check())["status"] == "unconfigured"

    def test_health_exception_path(self):
        class ExplodingConfig(dict):
            def __contains__(self, key):
                raise RuntimeError("boom")

        svc = make_service(config=ExplodingConfig())
        result = asyncio_run(svc.health_check())
        assert result["status"] == "unhealthy"
        assert result["error"] == "Health check failed"


class TestExecuteOperation:
    def test_authenticate_dispatch(self):
        svc = make_service()
        with patch.object(svc, "_authenticate", new=AsyncMock(return_value={"ok": 1})):
            assert asyncio_run(svc.execute_operation("authenticate", user_id="u1")) == {"ok": 1}

    def test_send_message_dispatch(self):
        svc = make_service()
        with patch.object(svc, "_send_message", new=AsyncMock(return_value={"ok": 1})):
            assert asyncio_run(svc.execute_operation(
                "send_message", team_id="t", channel_id="c", content="hi")) == {"ok": 1}

    def test_list_teams_dispatch(self):
        svc = make_service()
        with patch.object(svc, "_list_teams", new=AsyncMock(return_value={"ok": 1})):
            assert asyncio_run(svc.execute_operation("list_teams")) == {"ok": 1}

    def test_list_channels_dispatch(self):
        svc = make_service()
        with patch.object(svc, "_list_channels", new=AsyncMock(return_value={"ok": 1})):
            assert asyncio_run(svc.execute_operation("list_channels", team_id="t")) == {"ok": 1}

    def test_unknown_operation(self):
        svc = make_service()
        result = asyncio_run(svc.execute_operation("nope"))
        assert result["status"] == "error"

    def test_exception_tolerated(self):
        svc = make_service()
        with patch.object(svc, "_authenticate", new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = asyncio_run(svc.execute_operation("authenticate", user_id="u"))
        assert result["status"] == "error"
        assert "Microsoft 365 operation failed" in result["message"]


class TestAuth:
    def test_authenticate_success(self):
        svc = make_service()
        with patch.dict(os.environ, {"MICROSOFT_365_CLIENT_ID": "cid",
                                     "MICROSOFT_365_REDIRECT_URI": "http://cb"}):
            result = asyncio_run(svc._authenticate("user_7"))
        assert result["status"] == "success"
        assert "login.microsoftonline.com" in result["auth_url"]
        assert result["state"] == "microsoft365_user_7"
        assert "client_id=cid" in result["auth_url"]
        assert "scope=User.Read" in result["auth_url"]

    def test_authenticate_legacy_alias(self):
        svc = make_service()
        with patch.object(svc, "_authenticate", new=AsyncMock(return_value={"ok": 1})):
            assert asyncio_run(svc.authenticate("u")) == {"ok": 1}

    def test_authenticate_exception(self):
        svc = make_service()
        with patch("urllib.parse.urlencode", side_effect=RuntimeError("boom")):
            result = asyncio_run(svc._authenticate("u"))
        assert result["status"] == "error"
        assert result["message"] == "Authentication failed"


class TestGraphReads:
    @pytest.fixture
    def svc(self):
        return make_service()

    def test_get_user_profile(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(return_value=ok_response({"id": "1"}))) as g:
            result = asyncio_run(svc.get_user_profile("tok"))
        assert result["data"]["id"] == "1"
        assert "/me?$select=" in g.call_args[0][1]

    def test_get_user_profile_error(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = asyncio_run(svc.get_user_profile("tok"))
        assert result["status"] == "error"

    def test_list_teams(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({"value": []}))) as g:
            assert asyncio_run(svc.list_teams("tok"))["data"] == {"value": []}
        assert g.call_args[0][1].endswith("/me/joinedTeams")

    def test_list_teams_error(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert asyncio_run(svc.list_teams("tok"))["status"] == "error"

    def test_list_channels(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({"value": []}))) as g:
            assert asyncio_run(svc.list_channels("tok", "team1"))["status"] == "success"
        assert "/teams/team1/channels" in g.call_args[0][1]

    def test_list_channels_error(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert asyncio_run(svc.list_channels("tok", "t"))["status"] == "error"

    def test_get_outlook_messages(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({"value": []}))) as g:
            assert asyncio_run(svc.get_outlook_messages("tok", "inbox", 5))["status"] == "success"
        assert "mailFolders/inbox/messages?$top=5" in g.call_args[0][1]

    def test_get_outlook_messages_error(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert asyncio_run(svc.get_outlook_messages("tok"))["status"] == "error"

    def test_get_calendar_events(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({"value": []}))) as g:
            assert asyncio_run(svc.get_calendar_events("tok", "2026-01-01", "2026-01-02"))["status"] == "success"
        assert "startDateTime=2026-01-01&endDateTime=2026-01-02" in g.call_args[0][1]

    def test_get_calendar_events_error(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert asyncio_run(svc.get_calendar_events("tok", "a", "b"))["status"] == "error"

    def test_get_planner_tasks(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({"value": []}))) as g:
            assert asyncio_run(svc.get_planner_tasks("tok", 3))["status"] == "success"
        assert "planner/tasks?$top=3" in g.call_args[0][1]

    def test_get_planner_tasks_error(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert asyncio_run(svc.get_planner_tasks("tok"))["status"] == "error"

    def test_get_dynamics_deals(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({"value": []}))) as g:
            assert asyncio_run(svc.get_dynamics_deals("tok"))["status"] == "success"
        assert "insights/trending" in g.call_args[0][1]

    def test_get_dynamics_deals_error(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert asyncio_run(svc.get_dynamics_deals("tok"))["status"] == "error"

    def test_get_dynamics_invoices(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({"value": []}))) as g:
            assert asyncio_run(svc.get_dynamics_invoices("tok"))["status"] == "success"
        assert "insights/used" in g.call_args[0][1]

    def test_get_dynamics_invoices_error(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert asyncio_run(svc.get_dynamics_invoices("tok"))["status"] == "error"

    def test_get_service_status(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({"id": "1"}))):
            assert asyncio_run(svc.get_service_status("tok"))["data"]["id"] == "1"

    def test_get_service_status_error(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert asyncio_run(svc.get_service_status("tok"))["status"] == "error"


class FakeGraphResponse:
    def __init__(self, status=200, payload=None, text="error body"):
        self.status = status
        self._payload = payload if payload is not None else {"value": []}
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self):
        return self._payload

    async def text(self):
        return self._text


class TestMakeGraphRequest:
    def test_fake_token_development_bypass(self):
        svc = make_service()
        with patch.dict(os.environ, {"ATOM_ENV": "development"}):
            result = asyncio_run(svc._make_graph_request("GET", "http://x", "fake_token"))
        assert result["status"] == "success"
        assert result["data"]["id"] == "mock_id_123"

    def test_success_json(self):
        svc = make_service()
        session = MagicMock()
        session.request = MagicMock(return_value=FakeGraphResponse(status=200, payload={"a": 1}))
        session_mgr = MagicMock()
        session_mgr.__aenter__ = AsyncMock(return_value=session)
        session_mgr.__aexit__ = AsyncMock(return_value=False)
        with patch("aiohttp.ClientSession", return_value=session_mgr):
            result = asyncio_run(svc._make_graph_request("GET", "http://x", "tok", {"k": "v"}))
        assert result == {"status": "success", "data": {"a": 1}}
        assert session.request.call_args[0][0] == "GET"
        assert session.request.call_args[1]["json"] == {"k": "v"}
        assert session.request.call_args[1]["headers"]["Authorization"] == "Bearer tok"

    def test_error_status(self):
        svc = make_service()
        session = MagicMock()
        session.request = MagicMock(return_value=FakeGraphResponse(status=429, text="rate limited"))
        session_mgr = MagicMock()
        session_mgr.__aenter__ = AsyncMock(return_value=session)
        session_mgr.__aexit__ = AsyncMock(return_value=False)
        with patch("aiohttp.ClientSession", return_value=session_mgr):
            result = asyncio_run(svc._make_graph_request("GET", "http://x", "tok"))
        assert result == {"status": "error", "code": 429, "message": "rate limited"}

    def test_no_content(self):
        svc = make_service()
        session = MagicMock()
        session.request = MagicMock(return_value=FakeGraphResponse(status=204))
        session_mgr = MagicMock()
        session_mgr.__aenter__ = AsyncMock(return_value=session)
        session_mgr.__aexit__ = AsyncMock(return_value=False)
        with patch("aiohttp.ClientSession", return_value=session_mgr):
            result = asyncio_run(svc._make_graph_request("DELETE", "http://x", "tok"))
        assert result == {"status": "success", "data": None}


class TestOneDriveActions:
    @pytest.fixture
    def svc(self):
        return make_service()

    def test_list_files_root(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc.execute_onedrive_action(
                "tok", "list_files", {}))["status"] == "success"
        assert "/me/drive/root/children" in g.call_args[0][1]

    def test_list_files_folder(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc.execute_onedrive_action(
                "tok", "list_files", {"folder": "docs"}))["status"] == "success"
        assert "root:/docs:/children" in g.call_args[0][1]

    def test_get_content_requires_path(self, svc):
        result = asyncio_run(svc.execute_onedrive_action("tok", "get_content", {}))
        assert result["status"] == "error"

    def test_get_content_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            result = asyncio_run(svc.execute_onedrive_action(
                "tok", "get_content", {"path": "a.txt"}))
        assert result["status"] == "success"
        assert "root:/a.txt:/content" in g.call_args[0][1]

    def test_upload_requires_params(self, svc):
        result = asyncio_run(svc.execute_onedrive_action("tok", "upload", {}))
        assert result["status"] == "error"

    def test_upload_success(self, svc):
        session = MagicMock()
        session.put = MagicMock(return_value=FakeGraphResponse(status=201, payload={"id": "f1"}))
        session_mgr = MagicMock()
        session_mgr.__aenter__ = AsyncMock(return_value=session)
        session_mgr.__aexit__ = AsyncMock(return_value=False)
        with patch("aiohttp.ClientSession", return_value=session_mgr):
            result = asyncio_run(svc.execute_onedrive_action(
                "tok", "upload", {"path": "x.txt", "file_content": b"abc",
                                  "content_type": "text/plain"}))
        assert result["status"] == "success"
        assert result["data"]["id"] == "f1"
        assert session.put.call_args[1]["data"] == b"abc"

    def test_upload_error(self, svc):
        session = MagicMock()
        session.put = MagicMock(return_value=FakeGraphResponse(status=500, text="upload failed"))
        session_mgr = MagicMock()
        session_mgr.__aenter__ = AsyncMock(return_value=session)
        session_mgr.__aexit__ = AsyncMock(return_value=False)
        with patch("aiohttp.ClientSession", return_value=session_mgr):
            result = asyncio_run(svc.execute_onedrive_action(
                "tok", "upload", {"path": "x.txt", "file_content": b"abc"}))
        assert result["status"] == "error"
        assert result["code"] == 500

    def test_delete_requires_item_id(self, svc):
        result = asyncio_run(svc.execute_onedrive_action("tok", "delete", {}))
        assert result["status"] == "error"

    def test_delete_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response(None))) as g:
            result = asyncio_run(svc.execute_onedrive_action(
                "tok", "delete", {"item_id": "i9"}))
        assert result["status"] == "success"
        assert "drive/items/i9" in g.call_args[0][1]
        assert g.call_args[0][0] == "DELETE"

    def test_share_requires_item_id(self, svc):
        result = asyncio_run(svc.execute_onedrive_action("tok", "share", {}))
        assert result["status"] == "error"

    def test_share_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            result = asyncio_run(svc.execute_onedrive_action(
                "tok", "share", {"item_id": "i9", "link_type": "edit"}))
        assert result["status"] == "success"
        assert "createLink" in g.call_args[0][1]
        assert g.call_args[0][3]["type"] == "edit"

    def test_create_folder_requires_name(self, svc):
        result = asyncio_run(svc.execute_onedrive_action("tok", "create_folder", {}))
        assert result["status"] == "error"

    def test_create_folder_root(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            result = asyncio_run(svc.execute_onedrive_action(
                "tok", "create_folder", {"name": "new"}))
        assert result["status"] == "success"
        assert "/me/drive/root/children" in g.call_args[0][1]
        assert g.call_args[0][3]["name"] == "new"

    def test_create_folder_in_folder(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            result = asyncio_run(svc.execute_onedrive_action(
                "tok", "create_folder", {"folder_path": "a/b", "name": "new"}))
        assert result["status"] == "success"
        assert "root:/a/b:/children" in g.call_args[0][1]

    def test_unknown_action(self, svc):
        result = asyncio_run(svc.execute_onedrive_action("tok", "nope", {}))
        assert result["status"] == "error"
        assert "Unknown OneDrive action" in result["message"]

    def test_exception_tolerated(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = asyncio_run(svc.execute_onedrive_action("tok", "list_files", {}))
        assert result["status"] == "error"
        assert result["message"] == "OneDrive action failed"


class TestExcelActions:
    @pytest.fixture
    def svc(self):
        return make_service()

    def test_requires_item_id_or_path(self, svc):
        result = asyncio_run(svc.execute_excel_action("tok", "read_range", {}))
        assert result["status"] == "error"

    def test_path_resolution_failure(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value={"status": "error"})):
            result = asyncio_run(svc.execute_excel_action(
                "tok", "read_range", {"path": "book.xlsx", "range": "A1"}))
        assert result["status"] == "error"
        assert "Could not resolve path" in result["message"]

    def test_path_resolution_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({"id": "item42"}))) as g:
            result = asyncio_run(svc.execute_excel_action(
                "tok", "get_tables", {"path": "book.xlsx"}))
        assert result["status"] == "success"
        assert "items/item42/workbook/tables" in g.call_args[0][1]

    def test_read_range_requires_range(self, svc):
        result = asyncio_run(svc.execute_excel_action(
            "tok", "read_range", {"item_id": "i"}))
        assert result["status"] == "error"

    def test_read_range_with_sheet(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            result = asyncio_run(svc.execute_excel_action(
                "tok", "read_range", {"item_id": "i", "range": "Data!A1:B2"}))
        assert result["status"] == "success"
        assert "worksheets/Data/range(address='A1:B2')" in g.call_args[0][1]

    def test_read_range_default_sheet(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            result = asyncio_run(svc.execute_excel_action(
                "tok", "read_range", {"item_id": "i", "range": "A1"}))
        assert result["status"] == "success"
        assert "worksheets/sheet1/range(address='A1')" in g.call_args[0][1]

    def test_write_range_requires_params(self, svc):
        result = asyncio_run(svc.execute_excel_action(
            "tok", "write_range", {"item_id": "i"}))
        assert result["status"] == "error"

    def test_write_range_with_sheet(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            result = asyncio_run(svc.execute_excel_action(
                "tok", "write_range", {"item_id": "i", "range": "S!A1", "values": [[1]]}))
        assert result["status"] == "success"
        assert g.call_args[0][0] == "PATCH"
        assert g.call_args[0][3] == {"values": [[1]]}

    def test_write_range_default_sheet(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))):
            result = asyncio_run(svc.execute_excel_action(
                "tok", "write_range", {"item_id": "i", "range": "A1", "values": []}))
        assert result["status"] == "success"

    def test_get_tables(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))):
            assert asyncio_run(svc.execute_excel_action(
                "tok", "get_tables", {"item_id": "i"}))["status"] == "success"

    def test_get_columns_requires_table(self, svc):
        result = asyncio_run(svc.execute_excel_action(
            "tok", "get_columns", {"item_id": "i"}))
        assert result["status"] == "error"

    def test_get_columns_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc.execute_excel_action(
                "tok", "get_columns", {"item_id": "i", "table": "T1"}))["status"] == "success"
        assert "tables/T1/columns" in g.call_args[0][1]

    def test_append_row_requires_table(self, svc):
        result = asyncio_run(svc.execute_excel_action(
            "tok", "append_row", {"item_id": "i"}))
        assert result["status"] == "error"

    def test_append_row_mapping_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response([{"name": "A"}, {"name": "B"}]))) as g:
            result = asyncio_run(svc.execute_excel_action(
                "tok", "append_row",
                {"item_id": "i", "table": "T", "mapping": {"A": "x", "B": "y"}}))
        assert result["status"] == "success"
        assert g.call_args[0][3] == {"values": [["x", "y"]]}

    def test_append_row_mapping_failure(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value={"status": "error"})):
            result = asyncio_run(svc.execute_excel_action(
                "tok", "append_row",
                {"item_id": "i", "table": "T", "mapping": {"A": "x"}}))
        assert result["status"] == "error"
        assert "Could not fetch table columns" in result["message"]

    def test_append_row_no_values(self, svc):
        result = asyncio_run(svc.execute_excel_action(
            "tok", "append_row", {"item_id": "i", "table": "T"}))
        assert result["status"] == "error"

    def test_append_row_values(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))):
            assert asyncio_run(svc.execute_excel_action(
                "tok", "append_row",
                {"item_id": "i", "table": "T", "values": [1, 2]}))["status"] == "success"

    def test_create_worksheet_requires_name(self, svc):
        result = asyncio_run(svc.execute_excel_action(
            "tok", "create_worksheet", {"item_id": "i"}))
        assert result["status"] == "error"

    def test_create_worksheet_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc.execute_excel_action(
                "tok", "create_worksheet", {"item_id": "i", "name": "S"}))["status"] == "success"
        assert g.call_args[0][3] == {"name": "S"}

    def test_format_range_requires_range(self, svc):
        result = asyncio_run(svc.execute_excel_action(
            "tok", "format_range", {"item_id": "i"}))
        assert result["status"] == "error"

    def test_format_range_with_sheet(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc.execute_excel_action(
                "tok", "format_range",
                {"item_id": "i", "range": "S!A1", "format": {"bold": True}}))["status"] == "success"
        assert "worksheets/S/range(address='A1')/format" in g.call_args[0][1]
        assert g.call_args[0][3] == {"bold": True}

    def test_format_range_default_sheet(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))):
            assert asyncio_run(svc.execute_excel_action(
                "tok", "format_range", {"item_id": "i", "range": "A1"}))["status"] == "success"

    def test_unknown_action(self, svc):
        result = asyncio_run(svc.execute_excel_action("tok", "nope", {"item_id": "i"}))
        assert result["status"] == "error"

    def test_exception_tolerated(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = asyncio_run(svc.execute_excel_action(
                "tok", "get_tables", {"item_id": "i"}))
        assert result["message"] == "Excel action failed"


class TestPowerBIActions:
    @pytest.fixture
    def svc(self):
        return make_service()

    def test_refresh_dataset_requires_params(self, svc):
        assert asyncio_run(svc.execute_powerbi_action(
            "tok", "refresh_dataset", {}))["status"] == "error"
        assert asyncio_run(svc.execute_powerbi_action(
            "tok", "refresh_dataset", {"group_id": "g"}))["status"] == "error"

    def test_refresh_dataset_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc.execute_powerbi_action(
                "tok", "refresh_dataset",
                {"group_id": "g", "dataset_id": "d"}))["status"] == "success"
        assert "groups/g/datasets/d/refreshes" in g.call_args[0][1]
        assert g.call_args[0][3] == {"notifyOption": "MailOnFailure"}

    def test_get_reports_requires_group(self, svc):
        assert asyncio_run(svc.execute_powerbi_action(
            "tok", "get_reports", {}))["status"] == "error"

    def test_get_reports_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc.execute_powerbi_action(
                "tok", "get_reports", {"group_id": "g"}))["status"] == "success"
        assert "groups/g/reports" in g.call_args[0][1]

    def test_get_dashboards_requires_group(self, svc):
        assert asyncio_run(svc.execute_powerbi_action(
            "tok", "get_dashboards", {}))["status"] == "error"

    def test_get_dashboards_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc.execute_powerbi_action(
                "tok", "get_dashboards", {"group_id": "g"}))["status"] == "success"
        assert "groups/g/dashboards" in g.call_args[0][1]

    def test_export_report_requires_params(self, svc):
        assert asyncio_run(svc.execute_powerbi_action(
            "tok", "export_report", {"group_id": "g"}))["status"] == "error"

    def test_export_report_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc.execute_powerbi_action(
                "tok", "export_report",
                {"group_id": "g", "report_id": "r", "format": "PPTX"}))["status"] == "success"
        assert "reports/r/ExportTo" in g.call_args[0][1]
        assert g.call_args[0][3] == {"format": "PPTX"}

    def test_get_datasets_requires_group(self, svc):
        assert asyncio_run(svc.execute_powerbi_action(
            "tok", "get_datasets", {}))["status"] == "error"

    def test_get_datasets_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))):
            assert asyncio_run(svc.execute_powerbi_action(
                "tok", "get_datasets", {"group_id": "g"}))["status"] == "success"

    def test_unknown_action(self, svc):
        assert asyncio_run(svc.execute_powerbi_action(
            "tok", "nope", {}))["status"] == "error"

    def test_exception_tolerated(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert asyncio_run(svc.execute_powerbi_action(
                "tok", "get_reports", {"group_id": "g"}))["message"] == "Power BI action failed"


class TestTeamsActions:
    @pytest.fixture
    def svc(self):
        return make_service()

    def test_send_message_requires_params(self, svc):
        assert asyncio_run(svc.execute_teams_action(
            "tok", "send_message", {}))["status"] == "error"

    def test_send_message_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc.execute_teams_action(
                "tok", "send_message",
                {"team_id": "t", "channel_id": "c", "message": "hi"}))["status"] == "success"
        assert "teams/t/channels/c/messages" in g.call_args[0][1]
        assert g.call_args[0][3]["body"]["content"] == "hi"

    def test_create_channel_requires_params(self, svc):
        assert asyncio_run(svc.execute_teams_action(
            "tok", "create_channel", {"team_id": "t"}))["status"] == "error"

    def test_create_channel_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc.execute_teams_action(
                "tok", "create_channel",
                {"team_id": "t", "display_name": "D", "description": "desc"}))["status"] == "success"
        assert g.call_args[0][3] == {"displayName": "D", "description": "desc"}

    def test_list_teams_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc.execute_teams_action(
                "tok", "list_teams", {}))["status"] == "success"
        assert "me/joinedTeams" in g.call_args[0][1]

    def test_unknown_action(self, svc):
        assert asyncio_run(svc.execute_teams_action(
            "tok", "nope", {}))["status"] == "error"

    def test_exception_tolerated(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert asyncio_run(svc.execute_teams_action(
                "tok", "list_teams", {}))["message"] == "Teams action failed"


class TestOutlookActions:
    @pytest.fixture
    def svc(self):
        return make_service()

    def test_send_email_requires_to(self, svc):
        assert asyncio_run(svc.execute_outlook_action(
            "tok", "send_email", {}))["status"] == "error"

    def test_send_email_string_to(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc.execute_outlook_action(
                "tok", "send_email", {"to": "a@b.com", "subject": "S"}))["status"] == "success"
        payload = g.call_args[0][3]
        assert payload["message"]["toRecipients"] == [{"emailAddress": {"address": "a@b.com"}}]
        assert payload["saveToSentItems"] == "true"

    def test_send_email_list_cc_bcc(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc.execute_outlook_action(
                "tok", "send_email",
                {"to": ["a@b.com"], "cc": ["c@d.com"], "bcc": ["e@f.com"],
                 "body": "hello"}))["status"] == "success"
        payload = g.call_args[0][3]["message"]
        assert payload["ccRecipients"][0]["emailAddress"]["address"] == "c@d.com"
        assert payload["bccRecipients"][0]["emailAddress"]["address"] == "e@f.com"
        assert payload["body"]["content"] == "hello"

    def test_send_email_string_cc_bcc(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc.execute_outlook_action(
                "tok", "send_email",
                {"to": ["a@b.com"], "cc": "c@d.com", "bcc": "e@f.com"}))["status"] == "success"
        payload = g.call_args[0][3]["message"]
        assert payload["ccRecipients"][0]["emailAddress"]["address"] == "c@d.com"
        assert payload["bccRecipients"][0]["emailAddress"]["address"] == "e@f.com"

    def test_list_messages(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({"value": []}))) as g:
            assert asyncio_run(svc.execute_outlook_action(
                "tok", "list_messages", {"folder_id": "sent", "top": 25}))["status"] == "success"
        assert "mailFolders/sent/messages?$top=25" in g.call_args[0][1]

    def test_create_event_requires_times(self, svc):
        assert asyncio_run(svc.execute_outlook_action(
            "tok", "create_event", {"start_time": "2026-01-01T10:00:00Z"}))["status"] == "error"

    def test_create_event_minimal(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc.execute_outlook_action(
                "tok", "create_event",
                {"start_time": "2026-01-01T10:00:00Z",
                 "end_time": "2026-01-01T11:00:00Z"}))["status"] == "success"
        payload = g.call_args[0][3]
        assert payload["subject"] == "Meeting"
        assert payload["start"]["timeZone"] == "UTC"

    def test_create_event_full(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc.execute_outlook_action(
                "tok", "create_event",
                {"subject": "Review", "start_time": "2026-01-01T10:00:00Z",
                 "end_time": "2026-01-01T11:00:00Z", "body": "notes",
                 "attendees": ["person@corp.com"]}))["status"] == "success"
        payload = g.call_args[0][3]
        assert payload["body"]["content"] == "notes"
        assert payload["attendees"][0]["emailAddress"]["name"] == "person"

    def test_create_event_string_attendees(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))):
            assert asyncio_run(svc.execute_outlook_action(
                "tok", "create_event",
                {"start_time": "2026-01-01T10:00:00Z", "end_time": "2026-01-01T11:00:00Z",
                 "attendees": "x@y.com"}))["status"] == "success"

    def test_unknown_action(self, svc):
        assert asyncio_run(svc.execute_outlook_action(
            "tok", "nope", {}))["status"] == "error"

    def test_exception_tolerated(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert asyncio_run(svc.execute_outlook_action(
                "tok", "send_email", {"to": ["a@b.com"]}))["message"] == "Outlook action failed"


class TestPlannerActions:
    @pytest.fixture
    def svc(self):
        return make_service()

    def test_create_task_requires_params(self, svc):
        assert asyncio_run(svc.execute_planner_action(
            "tok", "create_task", {}))["status"] == "error"

    def test_create_task_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc.execute_planner_action(
                "tok", "create_task",
                {"plan_id": "p", "bucket_id": "b", "title": "T",
                 "assignments": {"u": {}}, "description": "d"}))["status"] == "success"
        payload = g.call_args[0][3]
        assert payload["description"] == "d"
        assert payload["assignments"] == {"u": {}}

    def test_update_task_requires_task_id(self, svc):
        assert asyncio_run(svc.execute_planner_action(
            "tok", "update_task", {}))["status"] == "error"

    def test_update_task_full(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc.execute_planner_action(
                "tok", "update_task",
                {"task_id": "t", "title": "T", "description": "d",
                 "percent_complete": 50}))["status"] == "success"
        assert g.call_args[0][0] == "PATCH"
        assert g.call_args[0][3] == {
            "title": "T", "description": "d", "percentComplete": 50}

    def test_update_task_partial(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc.execute_planner_action(
                "tok", "update_task", {"task_id": "t"}))["status"] == "success"
        assert g.call_args[0][3] == {}

    def test_list_plans_requires_group(self, svc):
        assert asyncio_run(svc.execute_planner_action(
            "tok", "list_plans", {}))["status"] == "error"

    def test_list_plans_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc.execute_planner_action(
                "tok", "list_plans", {"group_id": "g"}))["status"] == "success"
        assert "groups/g/planner/plans" in g.call_args[0][1]

    def test_list_buckets_requires_plan(self, svc):
        assert asyncio_run(svc.execute_planner_action(
            "tok", "list_buckets", {}))["status"] == "error"

    def test_list_buckets_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))):
            assert asyncio_run(svc.execute_planner_action(
                "tok", "list_buckets", {"plan_id": "p"}))["status"] == "success"

    def test_list_tasks_requires_plan(self, svc):
        assert asyncio_run(svc.execute_planner_action(
            "tok", "list_tasks", {}))["status"] == "error"

    def test_list_tasks_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))):
            assert asyncio_run(svc.execute_planner_action(
                "tok", "list_tasks", {"plan_id": "p"}))["status"] == "success"

    def test_unknown_action(self, svc):
        assert asyncio_run(svc.execute_planner_action(
            "tok", "nope", {}))["status"] == "error"

    def test_exception_tolerated(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert asyncio_run(svc.execute_planner_action(
                "tok", "list_plans", {"group_id": "g"}))["message"] == "Planner action failed"


class TestDeleteItem:
    @pytest.fixture
    def svc(self):
        return make_service()

    def test_delete_message(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response(None))) as g:
            assert asyncio_run(svc.delete_item("tok", "message", "m1"))["status"] == "success"
        assert "me/messages/m1" in g.call_args[0][1]

    def test_delete_event(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response(None))) as g:
            assert asyncio_run(svc.delete_item("tok", "event", "e1"))["status"] == "success"
        assert "me/events/e1" in g.call_args[0][1]

    def test_delete_file(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response(None))) as g:
            assert asyncio_run(svc.delete_item("tok", "file", "f1"))["status"] == "success"
        assert "me/drive/items/f1" in g.call_args[0][1]

    def test_delete_team_message_requires_ids(self, svc):
        assert asyncio_run(svc.delete_item(
            "tok", "team_message", "m1"))["status"] == "error"

    def test_delete_team_message_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response(None))) as g:
            assert asyncio_run(svc.delete_item(
                "tok", "team_message", "m1",
                {"team_id": "t", "channel_id": "c"}))["status"] == "success"
        assert "teams/t/channels/c/messages/m1" in g.call_args[0][1]

    def test_unknown_type(self, svc):
        assert asyncio_run(svc.delete_item(
            "tok", "widget", "w1"))["status"] == "error"

    def test_exception_tolerated(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert asyncio_run(svc.delete_item(
                "tok", "file", "f1"))["message"] == "Delete item failed"


class TestSubscriptions:
    @pytest.fixture
    def svc(self):
        return make_service()

    def test_create_subscription_appends_deleted(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            result = asyncio_run(svc.create_subscription(
                "tok", "messages", "created", "https://hook", "2027-01-01T00:00:00Z"))
        assert result["status"] == "success"
        payload = g.call_args[0][3]
        assert payload["changeType"] == "created,deleted"
        assert payload["clientState"] == "secretClientState"

    def test_create_subscription_existing_deleted(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            asyncio_run(svc.create_subscription(
                "tok", "messages", "updated,deleted", "https://hook", "2027-01-01T00:00:00Z"))
        assert g.call_args[0][3]["changeType"] == "updated,deleted"

    def test_create_subscription_error(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert asyncio_run(svc.create_subscription(
                "tok", "m", "created", "u", "d"))["message"] == "Create subscription failed"

    def test_renew_subscription(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc.renew_subscription(
                "tok", "sub1", "2027-01-01T00:00:00Z"))["status"] == "success"
        assert g.call_args[0][0] == "PATCH"
        assert "subscriptions/sub1" in g.call_args[0][1]

    def test_renew_subscription_error(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert asyncio_run(svc.renew_subscription(
                "tok", "sub1", "d"))["message"] == "Renew subscription failed"

    def test_delete_subscription(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response(None))) as g:
            assert asyncio_run(svc.delete_subscription("tok", "sub1"))["status"] == "success"
        assert g.call_args[0][0] == "DELETE"

    def test_delete_subscription_error(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert asyncio_run(svc.delete_subscription(
                "tok", "sub1"))["message"] == "Delete subscription failed"


class TestLegacyInternal:
    @pytest.fixture
    def svc(self):
        return make_service(config={"access_token": "tok"})

    def test_send_message_no_token(self):
        svc = make_service()
        result = asyncio_run(svc._send_message("t", "c", "hi"))
        assert result["status"] == "error"
        assert "No access token configured" in result["message"]

    def test_send_message_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({}))) as g:
            assert asyncio_run(svc._send_message("t", "c", "hi"))["status"] == "success"
        assert g.call_args[0][3] == {"body": {"content": "hi"}}

    def test_send_message_error(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert asyncio_run(svc._send_message("t", "c", "hi"))["message"] == "Send message failed"

    def test_list_teams_no_token(self):
        assert asyncio_run(make_service()._list_teams())["status"] == "error"

    def test_list_teams_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({"value": []}))):
            assert asyncio_run(svc._list_teams())["status"] == "success"

    def test_list_teams_error(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert asyncio_run(svc._list_teams())["message"] == "List teams failed"

    def test_list_channels_no_token(self):
        assert asyncio_run(make_service()._list_channels("t"))["status"] == "error"

    def test_list_channels_success(self, svc):
        with patch.object(svc, "_make_graph_request", new=AsyncMock(
                return_value=ok_response({"value": []}))):
            assert asyncio_run(svc._list_channels("t"))["status"] == "success"

    def test_list_channels_error(self, svc):
        with patch.object(svc, "_make_graph_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert asyncio_run(svc._list_channels("t"))["message"] == "List channels failed"


# --------------------------------------------------------------------------
# Route tests (auth enforced + mocked module-level service singleton)
# --------------------------------------------------------------------------

def asyncio_run(coro):
    import asyncio
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(m365.microsoft365_router)
    return application


@pytest.fixture
def anon_client(app):
    return TestClient(app)


@pytest.fixture
def auth_client(app):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="user_1", tenant_id="t1")
    return TestClient(app)


@pytest.fixture
def mock_svc():
    with patch.object(m365, "microsoft365_service") as m:
        yield m


class TestRouteAuth:
    """Security: every m365 router endpoint rejects anonymous callers."""

    @pytest.mark.parametrize("method,path", [
        ("get", "/microsoft365/auth?user_id=u"),
        ("get", "/microsoft365/user?access_token=t"),
        ("get", "/microsoft365/teams?access_token=t"),
        ("get", "/microsoft365/teams/t1/channels?access_token=t"),
        ("get", "/microsoft365/outlook/messages?access_token=t"),
        ("get", "/microsoft365/calendar/events?access_token=t&start_date=a&end_date=b"),
        ("get", "/microsoft365/services/status?access_token=t"),
        ("get", "/microsoft365/health"),
    ])
    def test_anonymous_rejected(self, anon_client, method, path):
        resp = getattr(anon_client, method)(path)
        assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"


class TestRouteHandlers:
    def test_auth_success(self, auth_client, mock_svc):
        mock_svc.authenticate = AsyncMock(return_value={
            "status": "success", "auth_url": "https://login.microsoftonline.com/...",
            "state": "microsoft365_user_1"})
        resp = auth_client.get("/microsoft365/auth", params={"user_id": "u1"})
        assert resp.status_code == 200
        assert resp.json()["state"] == "microsoft365_user_1"

    def test_auth_error_400(self, auth_client, mock_svc):
        mock_svc.authenticate = AsyncMock(return_value={
            "status": "error", "message": "Authentication failed"})
        resp = auth_client.get("/microsoft365/auth", params={"user_id": "u1"})
        assert resp.status_code == 400

    def test_user_success(self, auth_client, mock_svc):
        mock_svc.get_user_profile = AsyncMock(return_value={"status": "success", "data": {
            "id": "u1", "displayName": "A", "mail": "a@b.com", "userPrincipalName": "a@b.com"}})
        resp = auth_client.get("/microsoft365/user", params={"access_token": "t"})
        assert resp.status_code == 200
        assert resp.json()["displayName"] == "A"

    def test_user_error_400(self, auth_client, mock_svc):
        mock_svc.get_user_profile = AsyncMock(return_value={
            "status": "error", "message": "Failed"})
        resp = auth_client.get("/microsoft365/user", params={"access_token": "t"})
        assert resp.status_code == 400

    def test_teams_success(self, auth_client, mock_svc):
        mock_svc.list_teams = AsyncMock(return_value={
            "status": "success", "data": {"value": [{"id": "t1"}]}})
        resp = auth_client.get("/microsoft365/teams", params={"access_token": "t"})
        assert resp.status_code == 200
        assert resp.json()["teams"] == [{"id": "t1"}]

    def test_teams_error_400(self, auth_client, mock_svc):
        mock_svc.list_teams = AsyncMock(return_value={"status": "error", "message": "x"})
        resp = auth_client.get("/microsoft365/teams", params={"access_token": "t"})
        assert resp.status_code == 400

    def test_channels_success(self, auth_client, mock_svc):
        mock_svc.list_channels = AsyncMock(return_value={
            "status": "success", "data": {"value": [{"id": "c1"}]}})
        resp = auth_client.get("/microsoft365/teams/team9/channels", params={"access_token": "t"})
        assert resp.status_code == 200
        assert resp.json()["channels"] == [{"id": "c1"}]

    def test_channels_error_400(self, auth_client, mock_svc):
        mock_svc.list_channels = AsyncMock(return_value={"status": "error", "message": "x"})
        resp = auth_client.get("/microsoft365/teams/t/channels", params={"access_token": "t"})
        assert resp.status_code == 400

    def test_messages_success(self, auth_client, mock_svc):
        mock_svc.get_outlook_messages = AsyncMock(return_value={
            "status": "success", "data": {"value": [{"id": "m1"}]}})
        resp = auth_client.get("/microsoft365/outlook/messages", params={"access_token": "t"})
        assert resp.status_code == 200
        assert resp.json()["messages"] == [{"id": "m1"}]
        mock_svc.get_outlook_messages.assert_awaited_once_with("t", "inbox", 10)

    def test_messages_error_400(self, auth_client, mock_svc):
        mock_svc.get_outlook_messages = AsyncMock(return_value={"status": "error", "message": "x"})
        resp = auth_client.get("/microsoft365/outlook/messages", params={"access_token": "t"})
        assert resp.status_code == 400

    def test_calendar_success(self, auth_client, mock_svc):
        mock_svc.get_calendar_events = AsyncMock(return_value={
            "status": "success", "data": {"value": [{"id": "e1"}]}})
        resp = auth_client.get("/microsoft365/calendar/events",
                               params={"access_token": "t", "start_date": "a", "end_date": "b"})
        assert resp.status_code == 200
        assert resp.json()["events"] == [{"id": "e1"}]

    def test_calendar_error_400(self, auth_client, mock_svc):
        mock_svc.get_calendar_events = AsyncMock(return_value={"status": "error", "message": "x"})
        resp = auth_client.get("/microsoft365/calendar/events",
                               params={"access_token": "t", "start_date": "a", "end_date": "b"})
        assert resp.status_code == 400

    def test_service_status_success(self, auth_client, mock_svc):
        mock_svc.get_service_status = AsyncMock(return_value={
            "status": "success", "data": {"id": "u1"}})
        resp = auth_client.get("/microsoft365/services/status", params={"access_token": "t"})
        assert resp.status_code == 200
        assert resp.json()["id"] == "u1"

    def test_service_status_error_400(self, auth_client, mock_svc):
        mock_svc.get_service_status = AsyncMock(return_value={"status": "error", "message": "x"})
        resp = auth_client.get("/microsoft365/services/status", params={"access_token": "t"})
        assert resp.status_code == 400

    def test_health(self, auth_client, mock_svc):
        resp = auth_client.get("/microsoft365/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"
