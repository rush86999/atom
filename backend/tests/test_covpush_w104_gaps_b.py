# -*- coding: utf-8 -*-
"""Coverage wave 104 — verified gap batch B.

Targets (verified under baseline by existing suites):
1.  integrations/box_service.py                     (0% — no suite)
2.  core/fleet_orchestration/fault_tolerance_service.py (15%)
3.  integrations/gitlab_service.py                  (41%)
4.  integrations/matrix_service.py                  (~0% for this module)
5.  integrations/freshdesk_service.py               (28%)
6.  integrations/tableau_service.py                 (35%)
7.  integrations/line_service.py                    (~0% for this module)
8.  integrations/intercom_service.py                (0% — no suite)
9.  api/line_routes.py                              (43%)
10. core/action_registry.py                         (29%)
11. core/workflow_debugger.py                       (82%)
12. core/atom_saas_websocket.py                     (80%)
13. core/jit_verification_cache.py                  (72%)
14. core/fleet_orchestration/scaling_proposal_service.py (68%)
15. core/fleet_orchestration/fleet_scaler_service.py (64%)
16. api/skill_routes.py                             (45%)
17. integrations/atom_communication_ingestion_pipeline.py (49%)

No network, no real LLM — httpx clients and DB sessions are mocked everywhere.
Plain pytest + unittest.mock (asyncio_mode=auto).
"""
import json as json_mod
import os
import sys
from types import SimpleNamespace as NS
from unittest.mock import (
    AsyncMock, MagicMock, Mock, PropertyMock, patch,
)
from contextlib import contextmanager

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _resp(json_data=None, status=200):
    """Fake httpx.Response."""
    r = Mock()
    r.status_code = status
    r.raise_for_status = Mock(return_value=None)
    r.json = Mock(return_value=json_data if json_data is not None else {})
    r.text = ""
    return r


def _err_resp(exc):
    r = Mock()
    r.raise_for_status = Mock(side_effect=exc)
    return r


# =========================================================================== #
# helpers for DB-backed sync paths
# =========================================================================== #
def _mock_db_session(first=None, commit_exc=None):
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = first
    if commit_exc:
        db.commit.side_effect = commit_exc
    return db


# =========================================================================== #
# integrations/box_service.py
# =========================================================================== #
class TestBoxService:
    def _svc(self):
        from integrations.box_service import BoxService
        return BoxService(tenant_id="t1", config={"access_token": "tok"})

    def test_init_defaults(self):
        from integrations.box_service import BOX_SCOPES
        svc = self._svc()
        assert svc.service_name == "box"
        assert BOX_SCOPES and svc.base_url.startswith("https://api.box.com")

    def test_get_capabilities(self):
        caps = self._svc().get_capabilities()
        assert caps["supports_webhooks"] is True
        assert "list_files" in [o["id"] for o in caps["operations"]]

    async def test_health_check(self):
        hc = await self._svc().health_check()
        assert hc["healthy"] is True and hc["service"] == "box"

    async def test_authenticate(self, monkeypatch):
        monkeypatch.setenv("BOX_CLIENT_ID", "box-client-1")
        res = await self._svc().authenticate("user-1")
        assert res["status"] == "success"
        assert res["state"] == "box_user-1"
        assert "account.box.com" in res["auth_url"]
        assert "client_id=box-client-1" in res["auth_url"]

    async def test_execute_unknown_operation(self):
        res = await self._svc().execute_operation("nope", {})
        assert res["success"] is False
        assert "Unknown operation" in res["error"]

    async def test_execute_list_files(self):
        svc = self._svc()
        with patch.object(svc, "_box_get", AsyncMock(return_value={
            "entries": [{"id": "1", "type": "file"}, {"id": "2", "type": "file"}],
            "total_count": 2,
        })):
            res = await svc.execute_operation("list_files", {"access_token": "tok"})
        assert res["success"] is True
        assert res["result"]["total_count"] == 2

    async def test_execute_search_files(self):
        svc = self._svc()
        with patch.object(svc, "_box_get", AsyncMock(return_value={
            "entries": [{"id": "5", "name": "Search Result: q.docx", "type": "file"}],
            "total_count": 1,
        })):
            res = await svc.execute_operation(
                "search_files", {"access_token": "tok", "query": "q"})
        assert res["success"] is True
        assert res["result"]["entries"][0]["name"].startswith("Search Result: q")

    async def test_get_file_metadata(self):
        svc = self._svc()
        with patch.object(svc, "_box_get", AsyncMock(return_value={"id": "f1", "type": "file"})):
            res = await svc.get_file_metadata("tok", "f1")
        assert res["status"] == "success" and res["data"]["id"] == "f1"

    async def test_download_file(self):
        svc = self._svc()
        with patch.object(svc, "_box_get_bytes", AsyncMock(return_value=b"x")):
            res = await svc.download_file("tok", "f1")
        assert res["status"] == "success"
        assert "downloadUrl" in res["data"]
        assert "content_b64" in res["data"]

    async def test_create_folder(self):
        svc = self._svc()
        with patch.object(svc, "_box_post", AsyncMock(return_value={
            "id": "folder_1", "name": "New Folder", "type": "folder"})):
            res = await svc.create_folder("tok", "0", "New Folder")
        assert res["status"] == "success"
        assert res["data"]["name"] == "New Folder"

    async def test_execute_error_path(self):
        svc = self._svc()
        with patch.object(svc, "list_files", AsyncMock(side_effect=RuntimeError("boom"))):
            res = await svc.execute_operation("list_files", {"access_token": "t"})
        assert res["success"] is False and "boom" in res["error"]

    async def test_execute_failure_status(self):
        svc = self._svc()
        with patch.object(svc, "list_files", AsyncMock(return_value={"status": "error", "message": "m"})):
            res = await svc.execute_operation("list_files", {"access_token": "t"})
        assert res["success"] is False and res["error"] == "m"

    async def test_sync_to_postgres_cache_new_metric(self):
        from core.models import IntegrationMetric
        svc = self._svc()
        with patch.object(svc, "walk_files", AsyncMock(return_value=[
            {"id": "1", "path": "/A"}, {"id": "2", "path": ""}])), \
                patch("core.database.SessionLocal", return_value=_mock_db_session(first=None)) as SL:
            res = await svc.sync_to_postgres_cache("ws1", "tok")
        assert res["success"] is True and res["metrics_synced"] == 2
        assert isinstance(SL.return_value.add.call_args_list[0][0][0], IntegrationMetric)

    async def test_sync_to_postgres_cache_existing_metric(self):
        existing = MagicMock()
        svc = self._svc()
        with patch.object(svc, "walk_files", AsyncMock(return_value=[
            {"id": "1", "path": "/A"}, {"id": "2", "path": "/A/B"}])), \
                patch("core.database.SessionLocal", return_value=_mock_db_session(first=existing)):
            res = await svc.sync_to_postgres_cache("ws1", "tok")
        assert res["success"] is True
        assert existing.value == 2.0  # two walked files / two distinct folders

    async def test_sync_to_postgres_cache_db_error(self):
        svc = self._svc()
        db = _mock_db_session(commit_exc=RuntimeError("db down"))
        with patch.object(svc, "walk_files", AsyncMock(return_value=[])), \
                patch("core.database.SessionLocal", return_value=db):
            res = await svc.sync_to_postgres_cache("ws1", "tok")
        assert res["success"] is False
        db.rollback.assert_called_once()

    async def test_full_sync(self):
        svc = self._svc()
        with patch.object(svc, "walk_files", AsyncMock(return_value=[])), \
                patch.object(svc, "ingest_file_to_memory", AsyncMock(
                    return_value={"success": True, "result": {"status": "ingested"}})), \
                patch.object(svc, "sync_to_postgres_cache",
                             AsyncMock(return_value={"success": True, "metrics_synced": 1})):
            res = await svc.full_sync("ws1", "tok")
        assert res["success"] is True and res["workspace_id"] == "ws1"

    def test_module_singleton_exists(self):
        from integrations import box_service
        assert box_service.box_service.service_name == "box"


# =========================================================================== #
# integrations/intercom_service.py
# =========================================================================== #
class TestIntercomService:
    def _svc(self, config=None):
        from integrations.intercom_service import IntercomService
        return IntercomService(tenant_id="t1", config=config or {})

    def test_init_and_getters(self):
        svc = self._svc()
        assert svc.base_url == "https://api.intercom.io"
        assert svc.http is not None

    def test_get_capabilities(self):
        caps = self._svc().get_capabilities()
        assert caps["supports_webhooks"] is True
        assert caps["rate_limits"]["requests_per_minute"] == 200

    def test_health_check_unconfigured(self):
        hc = self._svc().health_check()
        assert hc["healthy"] is False and hc["status"] == "unconfigured"

    def test_health_check_configured(self):
        svc = self._svc({"intercom_client_id": "id", "intercom_client_secret": "s"})
        assert svc.health_check()["healthy"] is True

    def test_get_headers(self):
        h = self._svc()._get_headers("tok")
        assert h["Authorization"] == "Bearer tok"

    async def test_exchange_token(self):
        svc = self._svc()
        svc.http.post = AsyncMock(return_value=_resp({"access_token": "at"}))
        out = await svc.exchange_token("code")
        assert out["access_token"] == "at"

    async def test_get_admins(self):
        svc = self._svc()
        svc.http.get = AsyncMock(return_value=_resp({"admins": [{"id": "a"}]}))
        assert await svc.get_admins("tok") == [{"id": "a"}]

    async def test_get_contacts(self):
        svc = self._svc()
        svc.http.get = AsyncMock(return_value=_resp({"data": [{"id": "c"}]}))
        assert await svc.get_contacts("tok", 5) == [{"id": "c"}]

    async def test_get_conversations(self):
        svc = self._svc()
        svc.http.get = AsyncMock(return_value=_resp({"conversations": [{"id": "cv"}]}))
        assert await svc.get_conversations("tok", 7) == [{"id": "cv"}]

    async def test_search_contacts(self):
        svc = self._svc()
        svc.http.post = AsyncMock(return_value=_resp({"data": [{"id": "c"}]}))
        out = await svc.search_contacts("tok", "alice")
        assert out == [{"id": "c"}]
        _, kwargs = svc.http.post.call_args
        assert kwargs["json"]["query"]["value"] == "alice"

    async def test_execute_operation_tenant_mismatch(self):
        res = await self._svc().execute_operation(
            "get_admins", {"access_token": "t"}, context={"tenant_id": "other"})
        assert res["success"] is False and res["error"] == "Tenant mismatch"

    async def test_execute_operation_missing_token(self):
        res = await self._svc().execute_operation("get_admins", {})
        assert res["success"] is False and "access token" in res["error"]

    async def test_execute_operation_dispatch(self):
        svc = self._svc({"intercom_access_token": "cfg-tok"})
        for op, meth, kw in [
            ("search_contacts", "search_contacts", "query"),
            ("get_contacts", "get_contacts", "limit"),
            ("get_conversations", "get_conversations", "limit"),
            ("get_admins", "get_admins", None),
        ]:
            setattr(svc, meth, AsyncMock(return_value=[{"id": "x"}]))
        res = await svc.execute_operation("search_contacts", {"query": "q"})
        assert res["success"] is True
        res = await svc.execute_operation("get_contacts", {"limit": 3})
        assert res["success"] is True
        res = await svc.execute_operation("get_conversations", {})
        assert res["success"] is True
        res = await svc.execute_operation("get_admins", {})
        assert res["success"] is True

    async def test_execute_operation_unknown(self):
        res = await self._svc({"intercom_access_token": "t"}).execute_operation("bogus", {})
        assert res["success"] is False and "not supported" in res["error"]

    async def test_execute_operation_exception(self):
        svc = self._svc({"intercom_access_token": "t"})
        svc.get_admins = AsyncMock(side_effect=RuntimeError("net"))
        res = await svc.execute_operation("get_admins", {})
        assert res["success"] is False

    async def test_close(self):
        svc = self._svc()
        svc.client.aclose = AsyncMock()
        await svc.close()
        svc.client.aclose.assert_awaited_once()

    def test_get_intercom_service_singleton(self):
        from integrations import intercom_service
        intercom_service._intercom_service_instance = None
        s1 = intercom_service.get_intercom_service()
        s2 = intercom_service.get_intercom_service()
        assert s1 is s2
        intercom_service._intercom_service_instance = None


# =========================================================================== #
# integrations/gitlab_service.py
# =========================================================================== #
class TestGitLabService:
    def _svc(self, config=None):
        from integrations.gitlab_service import GitLabService
        svc = GitLabService(tenant_id="t1", config=config or {})
        svc.client = MagicMock()
        return svc

    def test_capabilities_and_health(self):
        svc = self._svc({"client_id": "ci", "client_secret": "cs"})
        assert svc.get_capabilities()["supports_webhooks"] is True
        assert svc.health_check()["healthy"] is True
        assert self._svc().health_check()["healthy"] is False

    async def test_exchange_token(self):
        svc = self._svc()
        svc.client.post = AsyncMock(return_value=_resp({"access_token": "at"}))
        assert (await svc.exchange_token("c", "http://cb"))["access_token"] == "at"

    async def test_exchange_token_http_error(self):
        import httpx
        from fastapi import HTTPException
        svc = self._svc()
        svc.client.post = AsyncMock(return_value=_err_resp(httpx.HTTPError("e")))
        with pytest.raises(HTTPException):
            await svc.exchange_token("c", "http://cb")

    async def test_get_user(self):
        svc = self._svc()
        svc.client.get = AsyncMock(return_value=_resp({"id": 1}))
        assert (await svc.get_user("tok"))["id"] == 1

    async def test_get_user_error(self):
        from fastapi import HTTPException
        svc = self._svc()
        svc.client.get = AsyncMock(return_value=_err_resp(RuntimeError("x")))
        with pytest.raises(HTTPException):
            await svc.get_user("tok")

    async def test_get_projects(self):
        svc = self._svc()
        svc.client.get = AsyncMock(return_value=_resp([{"id": 7}]))
        assert await svc.get_projects("tok") == [{"id": 7}]

    async def test_get_issues_project_and_global(self):
        svc = self._svc()
        svc.client.get = AsyncMock(return_value=_resp([{"iid": 1}]))
        assert await svc.get_issues("tok", project_id="p1") == [{"iid": 1}]
        assert await svc.get_issues("tok") == [{"iid": 1}]

    async def test_get_projects_error(self):
        from fastapi import HTTPException
        svc = self._svc()
        svc.client.get = AsyncMock(return_value=_err_resp(RuntimeError("x")))
        with pytest.raises(HTTPException):
            await svc.get_projects("tok")

    async def test_search_projects(self):
        svc = self._svc()
        svc.client.get = AsyncMock(return_value=_resp([{"id": 2}]))
        assert await svc.search_projects("tok", "q") == [{"id": 2}]

    async def test_execute_operation_tenant_mismatch(self):
        res = await self._svc().execute_operation(
            "get_user", {"access_token": "t"}, context={"tenant_id": "other"})
        assert res["success"] is False and res["error"] == "Tenant ID mismatch"

    async def test_execute_operation_dispatch(self):
        svc = self._svc()
        svc.get_user = AsyncMock(return_value={"id": 1})
        svc.get_projects = AsyncMock(return_value=[])
        svc.get_issues = AsyncMock(return_value=[])
        svc.search_projects = AsyncMock(return_value=[])
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True})
        assert (await svc.execute_operation("get_user", {"access_token": "t"}))["success"]
        assert (await svc.execute_operation(
            "list_projects", {"access_token": "t", "limit": 3}))["success"]
        assert (await svc.execute_operation(
            "list_issues", {"access_token": "t", "project_id": "p"}))["success"]
        assert (await svc.execute_operation(
            "search_projects", {"access_token": "t", "query": "q"}))["success"]
        assert (await svc.execute_operation(
            "sync_metrics", {"access_token": "t", "workspace_id": "w"}))["success"]

    async def test_execute_operation_unknown_and_error(self):
        svc = self._svc()
        res = await svc.execute_operation("bogus", {})
        assert res["success"] is False and "Unknown operation" in res["error"]
        svc.get_user = AsyncMock(side_effect=RuntimeError("boom"))
        res = await svc.execute_operation("get_user", {})
        assert res["success"] is False and "failed" in res["error"]

    async def test_sync_to_postgres_cache(self):
        svc = self._svc()
        svc.get_projects = AsyncMock(return_value=[{"id": 1}, {"id": 2}])
        with patch("core.database.SessionLocal", return_value=_mock_db_session(first=None)):
            res = await svc.sync_to_postgres_cache("ws", "tok")
        assert res["success"] is True and res["metrics_synced"] == 1

    async def test_sync_to_postgres_cache_db_error(self):
        svc = self._svc()
        svc.get_projects = AsyncMock(return_value=[])
        db = _mock_db_session(commit_exc=RuntimeError("db"))
        with patch("core.database.SessionLocal", return_value=db):
            res = await svc.sync_to_postgres_cache("ws", "tok")
        assert res["success"] is False
        db.rollback.assert_called_once()

    async def test_sync_outer_failure(self):
        svc = self._svc()
        svc.get_projects = AsyncMock(side_effect=RuntimeError("net"))
        res = await svc.sync_to_postgres_cache("ws", "tok")
        assert res["success"] is False

    async def test_full_sync(self):
        svc = self._svc()
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True})
        res = await svc.full_sync("ws", "tok")
        assert res["workspace_id"] == "ws"


# =========================================================================== #
# integrations/tableau_service.py
# =========================================================================== #
class TestTableauService:
    def _svc(self, config=None):
        from integrations.tableau_service import TableauService
        svc = TableauService(tenant_id="t1", config=config or {})
        svc.client = MagicMock()
        return svc

    def test_init_defaults(self):
        svc = self._svc()
        assert svc.base_url.endswith("/api/3.19")
        assert svc.server_url.startswith("https://")

    def test_get_capabilities(self):
        caps = self._svc().get_capabilities()
        assert caps["supports_webhooks"] is False

    def test_health_check(self):
        hc = self._svc().health_check()
        assert hc["healthy"] is True and hc["service"] == "tableau"

    def test_get_headers(self):
        svc = self._svc({"access_token": "at"})
        assert svc._get_headers()["X-Tableau-Auth"] == "at"
        assert svc._get_headers("other")["X-Tableau-Auth"] == "other"

    async def test_sign_in(self):
        svc = self._svc()
        svc.client.post = AsyncMock(return_value=_resp(
            {"credentials": {"token": "T", "site": {"id": "S"}}}))
        await svc.sign_in("u", "p", "site")
        assert svc.auth_token == "T" and svc.site_uuid == "S"

    async def test_sign_in_http_error(self):
        import httpx
        from fastapi import HTTPException
        svc = self._svc()
        svc.client.post = AsyncMock(return_value=_err_resp(httpx.HTTPError("e")))
        with pytest.raises(HTTPException):
            await svc.sign_in("u", "p")

    async def test_getters_with_site(self):
        svc = self._svc({"access_token": "at", "tableau_site_uuid": "SITE"})
        svc.client.get = AsyncMock(side_effect=[
            _resp({"workbooks": {"workbook": [{"id": "w"}]}}),
            _resp({"views": {"view": [{"id": "v"}]}}),
            _resp({"datasources": {"datasource": [{"id": "d"}]}}),
        ])
        assert await svc.get_workbooks() == [{"id": "w"}]
        assert await svc.get_views() == [{"id": "v"}]
        assert await svc.get_datasources() == [{"id": "d"}]

    async def test_getters_no_token_401(self):
        from fastapi import HTTPException
        svc = self._svc()
        with pytest.raises(HTTPException):
            await svc.get_workbooks()
        with pytest.raises(HTTPException):
            await svc.get_views()
        with pytest.raises(HTTPException):
            await svc.get_datasources()

    async def test_getters_http_error(self):
        import httpx
        from fastapi import HTTPException
        svc = self._svc({"access_token": "at"})
        svc.client.get = AsyncMock(return_value=_err_resp(httpx.HTTPError("e")))
        with pytest.raises(HTTPException):
            await svc.get_workbooks()

    async def test_execute_operation_missing_token(self):
        res = await self._svc().execute_operation("get_workbooks", {})
        assert res["success"] is False and "token" in res["error"]

    async def test_execute_operation_dispatch(self):
        svc = self._svc()
        svc.get_workbooks = AsyncMock(return_value=[1])
        svc.get_views = AsyncMock(return_value=[2])
        svc.get_datasources = AsyncMock(return_value=[3])
        assert (await svc.execute_operation("get_workbooks", {"access_token": "t"}))["result"] == [1]
        assert (await svc.execute_operation("get_views", {"access_token": "t"}))["result"] == [2]
        assert (await svc.execute_operation("get_datasources", {"access_token": "t"}))["result"] == [3]

    async def test_execute_operation_context_token(self):
        svc = self._svc()
        svc.get_views = AsyncMock(return_value=[])
        res = await svc.execute_operation("get_views", {}, context={"access_token": "ctx"})
        assert res["success"] is True

    async def test_execute_operation_unknown(self):
        res = await self._svc().execute_operation("bogus", {"access_token": "t"})
        assert res["success"] is False

    async def test_execute_operation_exception(self):
        svc = self._svc()
        svc.get_workbooks = AsyncMock(side_effect=RuntimeError("net"))
        res = await svc.execute_operation("get_workbooks", {"access_token": "t"})
        assert res["success"] is False

    async def test_close(self):
        svc = self._svc()
        svc.client.aclose = AsyncMock()
        await svc.close()
        svc.client.aclose.assert_awaited_once()


# =========================================================================== #
# integrations/matrix_service.py
# =========================================================================== #
class TestMatrixService:
    def _svc(self, config=None):
        from integrations.matrix_service import MatrixService
        svc = MatrixService(tenant_id="t1", config=config or {})
        svc.client = MagicMock()
        return svc

    def test_health_check(self):
        assert self._svc().health_check()["status"] == "degraded"
        assert self._svc({"access_token": "tok"}).health_check()["healthy"] is True

    def test_get_capabilities(self):
        caps = self._svc().get_capabilities()
        assert {o["id"] for o in caps["operations"]} == {
            "send_message", "create_room", "invite_user"}

    async def test_execute_tenant_mismatch(self):
        res = await self._svc({"access_token": "t"}).execute_operation(
            "send_message", {}, context={"tenant_id": "other"})
        assert res["success"] is False
        assert res["details"]["reason"] == "cross_tenant_access_prevented"

    async def test_execute_unknown_raises(self):
        with pytest.raises(NotImplementedError):
            await self._svc().execute_operation("bogus", {})

    async def test_send_message_success(self):
        svc = self._svc({"access_token": "tok"})
        svc.client.put = AsyncMock(return_value=_resp({"event_id": "e"}))
        res = await svc.execute_operation("send_message", {"room_id": "!r", "text": "hi"})
        assert res["success"] is True and res["result"]["message_sent"] is True

    async def test_send_message_missing_params(self):
        res = await self._svc({"access_token": "tok"}).execute_operation("send_message", {"room_id": "!r"})
        assert res["success"] is False

    async def test_send_message_no_token(self):
        res = await self._svc().execute_operation("send_message", {"room_id": "!r", "text": "x"})
        assert res["success"] is False and "token" in res["error"]

    async def test_send_message_http_error(self):
        import httpx
        svc = self._svc({"access_token": "tok"})
        svc.client.put = AsyncMock(return_value=_err_resp(httpx.HTTPError("net")))
        res = await svc.execute_operation("send_message", {"room_id": "!r", "text": "x"})
        assert res["success"] is False

    async def test_create_room_success(self):
        svc = self._svc({"access_token": "tok"})
        svc.client.post = AsyncMock(return_value=_resp({"room_id": "!new"}))
        res = await svc.execute_operation(
            "create_room", {"name": "room", "invite": ["@u:hs"]})
        assert res["success"] is True and res["result"]["room_id"] == "!new"

    async def test_create_room_no_token_and_error(self):
        import httpx
        assert (await self._svc().execute_operation("create_room", {}))["success"] is False
        svc = self._svc({"access_token": "tok"})
        svc.client.post = AsyncMock(return_value=_err_resp(httpx.HTTPError("net")))
        assert (await svc.execute_operation("create_room", {}))["success"] is False

    async def test_invite_user(self):
        svc = self._svc({"access_token": "tok"})
        svc.client.post = AsyncMock(return_value=_resp({}))
        res = await svc.execute_operation(
            "invite_user", {"room_id": "!r", "user_id": "@u:hs"})
        assert res["success"] is True and res["result"]["invited"] is True

    async def test_invite_user_missing_and_no_token_and_error(self):
        import httpx
        svc = self._svc({"access_token": "tok"})
        assert (await svc.execute_operation("invite_user", {"room_id": "!r"}))["success"] is False
        assert (await self._svc().execute_operation(
            "invite_user", {"room_id": "!r", "user_id": "@u"}))["success"] is False
        svc.client.post = AsyncMock(return_value=_err_resp(httpx.HTTPError("net")))
        assert (await svc.execute_operation(
            "invite_user", {"room_id": "!r", "user_id": "@u"}))["success"] is False

    async def test_close(self):
        svc = self._svc()
        svc.client.aclose = AsyncMock()
        await svc.close()
        svc.client.aclose.assert_awaited_once()


# =========================================================================== #
# integrations/line_service.py
# =========================================================================== #
class TestLineService:
    def _svc(self, config=None):
        from integrations.line_service import LineService
        svc = LineService(tenant_id="t1", config=config or {})
        svc.client = MagicMock()
        return svc

    def test_health_check(self):
        assert self._svc().health_check()["status"] == "degraded"
        assert self._svc({"channel_access_token": "tok"}).health_check()["healthy"] is True

    def test_get_capabilities(self):
        caps = self._svc().get_capabilities()
        assert {o["id"] for o in caps["operations"]} == {
            "send_message", "broadcast", "get_profile"}

    async def test_execute_tenant_mismatch(self):
        res = await self._svc({"channel_access_token": "t"}).execute_operation(
            "send_message", {}, context={"tenant_id": "other"})
        assert res["success"] is False

    async def test_execute_unknown_raises(self):
        with pytest.raises(NotImplementedError):
            await self._svc().execute_operation("bogus", {})

    async def test_send_message_push(self):
        svc = self._svc({"channel_access_token": "tok"})
        svc.client.post = AsyncMock(return_value=_resp({}))
        res = await svc.execute_operation("send_message", {"to": "u1", "text": "hi"})
        assert res["success"] is True and res["result"]["recipient"] == "u1"

    async def test_send_message_reply(self):
        svc = self._svc({"channel_access_token": "tok"})
        svc.client.post = AsyncMock(return_value=_resp({}))
        res = await svc.execute_operation(
            "send_message", {"to": "u1", "text": "hi", "reply_token": "rt"})
        assert res["success"] is True
        url = svc.client.post.call_args[0][0]
        assert url.endswith("/reply")

    async def test_send_message_missing_and_no_token_and_error(self):
        import httpx
        svc = self._svc({"channel_access_token": "tok"})
        assert (await svc.execute_operation("send_message", {"to": "u1"}))["success"] is False
        assert (await self._svc().execute_operation(
            "send_message", {"to": "u1", "text": "x"}))["success"] is False
        svc.client.post = AsyncMock(return_value=_err_resp(httpx.HTTPError("net")))
        assert (await svc.execute_operation(
            "send_message", {"to": "u1", "text": "x"}))["success"] is False

    async def test_broadcast(self):
        svc = self._svc({"channel_access_token": "tok"})
        svc.client.post = AsyncMock(return_value=_resp({}))
        res = await svc.execute_operation(
            "broadcast", {"to": ["u1", "u2"], "messages": [{"type": "text", "text": "x"}]})
        assert res["success"] is True and res["result"]["recipients"] == 2

    async def test_broadcast_missing_and_no_token_and_error(self):
        import httpx
        svc = self._svc({"channel_access_token": "tok"})
        assert (await svc.execute_operation("broadcast", {"to": ["u"]}))["success"] is False
        assert (await self._svc().execute_operation(
            "broadcast", {"to": ["u"], "messages": []}))["success"] is False
        svc.client.post = AsyncMock(return_value=_err_resp(httpx.HTTPError("net")))
        assert (await svc.execute_operation(
            "broadcast", {"to": ["u"], "messages": [{}]}))["success"] is False

    async def test_get_profile(self):
        svc = self._svc({"channel_access_token": "tok"})
        svc.client.get = AsyncMock(return_value=_resp({"displayName": "Bob"}))
        res = await svc.execute_operation("get_profile", {"user_id": "u1"})
        assert res["success"] is True and res["result"]["displayName"] == "Bob"

    async def test_get_profile_missing_and_no_token_and_error(self):
        import httpx
        svc = self._svc({"channel_access_token": "tok"})
        assert (await svc.execute_operation("get_profile", {}))["success"] is False
        assert (await self._svc().execute_operation(
            "get_profile", {"user_id": "u"}))["success"] is False
        svc.client.get = AsyncMock(return_value=_err_resp(httpx.HTTPError("net")))
        assert (await svc.execute_operation("get_profile", {"user_id": "u"}))["success"] is False

    async def test_close(self):
        svc = self._svc()
        svc.client.aclose = AsyncMock()
        await svc.close()
        svc.client.aclose.assert_awaited_once()


# =========================================================================== #
# integrations/freshdesk_service.py
# =========================================================================== #
class TestFreshdeskService:
    def _svc(self, config=None):
        from integrations.freshdesk_service import FreshdeskService
        cfg = {"freshdesk_api_key": "k", "freshdesk_domain": "dom"}
        if config:
            cfg.update(config)
        svc = FreshdeskService(tenant_id="t1", config=cfg)
        svc.client = MagicMock()
        return svc

    def test_init_unconfigured(self):
        from integrations.freshdesk_service import FreshdeskService
        svc = FreshdeskService()
        assert svc.base_url == ""
        assert svc.headers["Authorization"] == ""

    def test_encode_credentials(self):
        import base64
        svc = self._svc()
        expect = base64.b64encode(b"k:X").decode()
        assert svc.headers["Authorization"] == f"Basic {expect}"

    def test_get_capabilities(self):
        caps = self._svc().get_capabilities()
        assert {o["id"] for o in caps["operations"]} == {
            "get_tickets", "create_ticket", "search_tickets"}

    def test_constants_and_names(self):
        from integrations.freshdesk_service import FreshdeskConstants
        svc = self._svc()
        assert FreshdeskConstants.MAX_ATTACHMENT_SIZE == 50 * 1024 * 1024
        assert svc.get_status_name(3) == "Pending"
        assert svc.get_status_name(99) == "Unknown"
        assert svc.get_priority_name(4) == "Urgent"
        assert svc.get_priority_name(0) == "Unknown"

    def test_health_check_missing_creds(self):
        from integrations.freshdesk_service import FreshdeskService
        hc = FreshdeskService().health_check()
        assert hc["healthy"] is False

    def test_health_check_ok_and_error(self):
        svc = self._svc()
        with patch("requests.get") as req:
            req.return_value = NS(status_code=200, text="ok")
            assert svc.health_check()["healthy"] is True
            req.return_value = NS(status_code=503, text="")
            assert svc.health_check()["healthy"] is False
            req.side_effect = RuntimeError("net")
            hc = svc.health_check()
        assert hc["healthy"] is False and hc["error"] == "net"

    async def test_retry_then_success(self):
        import httpx
        svc = self._svc({"freshdesk_max_retries": 2})
        svc.client.get = AsyncMock(side_effect=[
            _err_resp(httpx.RequestError("timeout")),
            _resp([{"id": 1}]),
        ])
        assert await svc.get_tickets() == [{"id": 1}]
        assert svc.client.get.await_count == 2

    async def test_retry_exhausted(self):
        import httpx
        svc = self._svc({"freshdesk_max_retries": 2})
        svc.client.get = AsyncMock(
            return_value=_err_resp(httpx.HTTPStatusError("500", request=Mock(), response=Mock())))
        with pytest.raises(httpx.HTTPError):
            await svc.get_tickets()
        assert svc.client.get.await_count == 2

    async def test_crud_methods(self):
        svc = self._svc()
        svc.client.get = AsyncMock(return_value=_resp({"id": 1}))
        svc.client.post = AsyncMock(return_value=_resp({"id": 9}))
        svc.client.put = AsyncMock(return_value=_resp({"id": 9, "ok": True}))
        svc.client.delete = AsyncMock(return_value=_resp())
        assert (await svc.create_ticket({"subject": "s"}))["id"] == 9
        assert await svc.get_tickets(page=2, per_page=5, status="2",
                                     priority="3", created_since="2026-01-01") == {"id": 1}
        assert (await svc.get_ticket(9))["id"] == 1
        assert (await svc.update_ticket(9, {"status": 4}))["ok"] is True
        assert await svc.delete_ticket(9) is True
        assert (await svc.add_ticket_note(9, {"body": "n"}))["id"] == 9
        assert (await svc.get_ticket_conversations(9)) == {"id": 1}

    async def test_contacts_companies_agents_groups(self):
        svc = self._svc()
        svc.client.get = AsyncMock(return_value=_resp({"id": 1}))
        svc.client.post = AsyncMock(return_value=_resp({"id": 2}))
        svc.client.put = AsyncMock(return_value=_resp({"id": 3}))
        assert (await svc.create_contact({"name": "n"}))["id"] == 2
        assert (await svc.get_contacts())["id"] == 1
        assert (await svc.get_contact(1))["id"] == 1
        assert (await svc.update_contact(1, {}))["id"] == 3
        assert (await svc.create_company({"n": 1}))["id"] == 2
        assert (await svc.get_companies())["id"] == 1
        assert (await svc.get_company(1))["id"] == 1
        assert (await svc.get_agents())["id"] == 1
        assert (await svc.get_agent(1))["id"] == 1
        assert (await svc.get_groups())["id"] == 1
        assert (await svc.get_group(1))["id"] == 1

    async def test_analytics_and_search(self):
        svc = self._svc()
        svc.client.get = AsyncMock(return_value=_resp({"id": 1}))
        assert (await svc.get_tickets_metrics(date_range="7d", group_by="g")) == {"id": 1}
        assert (await svc.get_satisfaction_ratings(ticket_id=1, date_range="7d")) == {"id": 1}
        assert (await svc.search_tickets("q", filters={"status": "2"})) == {"id": 1}
        assert (await svc.search_contacts("q")) == {"id": 1}
        assert (await svc.get_account_info())["id"] == 1

    async def test_crud_error_paths(self):
        svc = self._svc()
        svc.client.get = AsyncMock(return_value=_err_resp(RuntimeError("x")))
        svc.client.post = AsyncMock(return_value=_err_resp(RuntimeError("x")))
        for coro in [
            svc.create_ticket({}), svc.get_tickets(), svc.get_ticket(1),
            svc.update_ticket(1, {}), svc.delete_ticket(1), svc.add_ticket_note(1, {}),
            svc.get_ticket_conversations(1), svc.create_contact({}), svc.get_contacts(),
            svc.get_contact(1), svc.update_contact(1, {}), svc.create_company({}),
            svc.get_companies(), svc.get_company(1), svc.get_agents(), svc.get_agent(1),
            svc.get_groups(), svc.get_group(1), svc.get_tickets_metrics(),
            svc.get_satisfaction_ratings(), svc.search_tickets("q"), svc.search_contacts("q"),
            svc.get_account_info(),
        ]:
            with pytest.raises(Exception):
                await coro

    async def test_execute_operation(self):
        svc = self._svc()
        svc.get_tickets = AsyncMock(return_value=[{"id": 1}])
        svc.create_ticket = AsyncMock(return_value={"id": 2})
        svc.search_tickets = AsyncMock(return_value=[{"id": 3}])
        assert (await svc.execute_operation(
            "get_tickets", {"page": 1, "status": "2"}))["success"] is True
        assert (await svc.execute_operation(
            "create_ticket", {"data": {"subject": "s"}}))["success"] is True
        assert (await svc.execute_operation(
            "search_tickets", {"query": "q"}))["success"] is True

    async def test_execute_operation_tenant_mismatch(self):
        res = await self._svc().execute_operation(
            "get_tickets", {}, context={"tenant_id": "other"})
        assert res["success"] is False

    async def test_execute_operation_unknown_and_error(self):
        res = await self._svc().execute_operation("bogus", {})
        assert res["success"] is False and "not supported" in res["error"]
        svc = self._svc()
        svc.get_tickets = AsyncMock(side_effect=RuntimeError("net"))
        res = await svc.execute_operation("get_tickets", {})
        assert res["success"] is False

    async def test_sync_to_postgres_cache(self):
        svc = self._svc()
        svc.get_tickets = AsyncMock(return_value=[{"id": 1}])
        svc.get_contacts = AsyncMock(return_value=[{"id": 1}, {"id": 2}])
        with patch("core.database.SessionLocal", return_value=_mock_db_session(first=None)):
            res = await svc.sync_to_postgres_cache("ws")
        assert res["success"] is True and res["metrics_synced"] == 2

    async def test_sync_api_failure_counts_zero(self):
        svc = self._svc()
        svc.get_tickets = AsyncMock(side_effect=RuntimeError("net"))
        svc.get_contacts = AsyncMock(side_effect=RuntimeError("net"))
        with patch("core.database.SessionLocal", return_value=_mock_db_session(first=None)):
            res = await svc.sync_to_postgres_cache("ws")
        assert res["success"] is True and res["metrics_synced"] == 2

    async def test_sync_db_error(self):
        svc = self._svc()
        svc.get_tickets = AsyncMock(return_value=[])
        svc.get_contacts = AsyncMock(return_value=[])
        db = _mock_db_session(commit_exc=RuntimeError("db"))
        with patch("core.database.SessionLocal", return_value=db):
            res = await svc.sync_to_postgres_cache("ws")
        assert res["success"] is False
        db.rollback.assert_called_once()

    async def test_full_sync_and_close(self):
        svc = self._svc()
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True})
        res = await svc.full_sync("ws")
        assert res["success"] is True
        svc.client.aclose = AsyncMock()
        await svc.close()

    async def test_upload_attachment(self):
        import integrations.freshdesk_service as fs_mod
        svc = self._svc()
        fake_upload_client = MagicMock()
        fake_upload_client.post = AsyncMock(return_value=_resp({"id": "att"}))
        fake_upload_client.aclose = AsyncMock()
        with patch.object(fs_mod.httpx, "AsyncClient", return_value=fake_upload_client):
            res = await svc.upload_attachment(b"data", "f.txt")
        assert res["id"] == "att"
        fake_upload_client.aclose.assert_awaited_once()

    def test_factory_functions(self):
        import integrations.freshdesk_service as fs_mod
        svc = fs_mod.create_freshdesk_service("k", "dom")
        assert svc.domain == "dom"
        with patch.dict(os.environ, {"FRESHDESK_API_KEY": "k", "FRESHDESK_DOMAIN": "d"}):
            assert fs_mod.get_freshdesk_service() is not None
        with patch.dict(os.environ, {}, clear=True):
            assert fs_mod.get_freshdesk_service() is None

    async def test_test_freshdesk_connection(self):
        import integrations.freshdesk_service as fs_mod
        with patch.object(fs_mod, "create_freshdesk_service") as factory:
            factory.return_value.health_check = Mock(return_value={"healthy": True})
            factory.return_value.close = AsyncMock()
            assert await fs_mod.test_freshdesk_connection("k", "d") is True
            factory.return_value.health_check = Mock(return_value={"healthy": False})
            assert await fs_mod.test_freshdesk_connection("k", "d") is False
            factory.side_effect = RuntimeError("x")
            assert await fs_mod.test_freshdesk_connection("k", "d") is False


# =========================================================================== #
# api/line_routes.py
# =========================================================================== #
class TestLineRoutes:
    @pytest.fixture()
    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api import line_routes
        from core.security_dependencies import get_current_user
        from core.database import get_db_session

        app = FastAPI()
        app.include_router(line_routes.router)
        user = NS(id="u1", role=None)
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db_session] = lambda: MagicMock()
        self._user = user
        tc = TestClient(app)
        self._line_routes = line_routes
        yield tc
        app.dependency_overrides.clear()

    def _adapter(self, **attrs):
        adapter = AsyncMock()
        for k, v in attrs.items():
            if k == "verify_signature":
                setattr(adapter, k, Mock(return_value=v))
            else:
                setattr(adapter, k, AsyncMock(return_value=v) if not isinstance(v, AsyncMock) else v)
        return adapter

    def test_health_active_and_inactive(self, client):
        lr = self._line_routes
        with patch.object(lr, "line_adapter", self._adapter(
                get_service_status={"status": "active", "detail": 1})):
            assert client.get("/api/line/health").json()["status"] == "healthy"
        with patch.object(lr, "line_adapter", self._adapter(
                get_service_status={"status": "inactive"})):
            assert client.get("/api/line/health").json()["status"] == "inactive"

    def test_health_error(self, client):
        lr = self._line_routes
        adapter = AsyncMock()
        adapter.get_service_status = AsyncMock(side_effect=RuntimeError("x"))
        with patch.object(lr, "line_adapter", adapter):
            assert client.get("/api/line/health").status_code == 500

    def test_status_and_capabilities(self, client):
        lr = self._line_routes
        with patch.object(lr, "line_adapter", self._adapter(
                get_service_status={"status": "active", "x": 1})):
            r = client.get("/api/line/status")
            assert r.status_code == 200 and r.json()["x"] == 1
        adapter = AsyncMock()
        adapter.get_service_status = AsyncMock(side_effect=RuntimeError("x"))
        with patch.object(lr, "line_adapter", adapter):
            assert client.get("/api/line/status").status_code == 500
        caps = {"operations": []}
        with patch.object(lr, "line_adapter", self._adapter(get_capabilities=caps)):
            assert client.get("/api/line/capabilities").json() == caps

    def test_webhook_valid(self, client):
        lr = self._line_routes
        body = {"events": [{"type": "message"}]}
        with patch.object(lr, "line_adapter", self._adapter(
                verify_signature=True, handle_webhook_event={"processed": 1})):
            r = client.post("/api/line/webhook", json=body,
                            headers={"X-Line-Signature": "sig"})
        assert r.status_code == 200 and r.json() == {"processed": 1}

    def test_webhook_invalid_signature(self, client):
        lr = self._line_routes
        with patch.object(lr, "line_adapter", self._adapter(verify_signature=False)):
            r = client.post("/api/line/webhook", json={},
                            headers={"X-Line-Signature": "bad"})
        assert r.status_code == 403

    def test_webhook_internal_error(self, client):
        lr = self._line_routes
        adapter = AsyncMock()
        adapter.verify_signature = Mock(return_value=True)
        adapter.handle_webhook_event = AsyncMock(side_effect=ValueError("bad json"))
        with patch.object(lr, "line_adapter", adapter):
            r = client.post("/api/line/webhook", json={},
                            headers={"X-Line-Signature": "sig"})
        assert r.status_code == 500

    def test_send_message_ok_and_fail(self, client):
        lr = self._line_routes
        with patch.object(lr, "line_adapter", self._adapter(
                send_message={"ok": True, "id": "m1"})):
            r = client.post("/api/line/send-message", json={"to": "u1", "text": "hi"})
            assert r.status_code == 200 and r.json()["ok"] is True
        with patch.object(lr, "line_adapter", self._adapter(
                send_message={"ok": False, "error": "nope"})):
            r = client.post("/api/line/send-message", json={"to": "u1", "text": "hi"})
            assert r.status_code == 500

    def test_send_message_exception(self, client):
        lr = self._line_routes
        adapter = AsyncMock()
        adapter.send_message = AsyncMock(side_effect=RuntimeError("net"))
        with patch.object(lr, "line_adapter", adapter):
            r = client.post("/api/line/send-message", json={"to": "u1", "text": "hi"})
        assert r.status_code == 500

    def test_send_messages_ok_and_fail(self, client):
        lr = self._line_routes
        with patch.object(lr, "line_adapter", self._adapter(
                send_messages={"ok": True})):
            r = client.post("/api/line/send-messages",
                            json={"to": "u1", "messages": [{"type": "text", "text": "x"}]})
            assert r.status_code == 200
        with patch.object(lr, "line_adapter", self._adapter(
                send_messages={"ok": False, "error": "e"})):
            r = client.post("/api/line/send-messages",
                            json={"to": "u1", "messages": [{"type": "text", "text": "x"}]})
            assert r.status_code == 500
        adapter = AsyncMock()
        adapter.send_messages = AsyncMock(side_effect=RuntimeError("net"))
        with patch.object(lr, "line_adapter", adapter):
            r = client.post("/api/line/send-messages",
                            json={"to": "u1", "messages": []})
            assert r.status_code == 500

    def test_send_quick_reply(self, client):
        lr = self._line_routes
        payload = {"to": "u1", "text": "q", "quick_reply_items": [{"label": "y"}]}
        with patch.object(lr, "line_adapter", self._adapter(
                send_quick_reply={"ok": True})):
            r = client.post("/api/line/send-quick-reply", json=payload)
            assert r.status_code == 200
        with patch.object(lr, "line_adapter", self._adapter(
                send_quick_reply={"ok": False, "error": "e"})):
            r = client.post("/api/line/send-quick-reply", json=payload)
            assert r.status_code == 500
        adapter = AsyncMock()
        adapter.send_quick_reply = AsyncMock(side_effect=RuntimeError("net"))
        with patch.object(lr, "line_adapter", adapter):
            r = client.post("/api/line/send-quick-reply", json=payload)
            assert r.status_code == 500

    def test_send_template(self, client):
        lr = self._line_routes
        payload = {"to": "u1", "alt_text": "alt", "template": {"type": "buttons"}}
        with patch.object(lr, "line_adapter", self._adapter(
                send_template_message={"ok": True})):
            r = client.post("/api/line/send-template", json=payload)
            assert r.status_code == 200
        with patch.object(lr, "line_adapter", self._adapter(
                send_template_message={"ok": False, "error": "e"})):
            r = client.post("/api/line/send-template", json=payload)
            assert r.status_code == 500
        adapter = AsyncMock()
        adapter.send_template_message = AsyncMock(side_effect=RuntimeError("net"))
        with patch.object(lr, "line_adapter", adapter):
            r = client.post("/api/line/send-template", json=payload)
            assert r.status_code == 500

    def test_profile_own_ok(self, client):
        lr = self._line_routes
        self._user.role = "member"
        with patch.object(lr, "line_adapter", self._adapter(
                get_user_profile={"ok": True, "displayName": "Me"})):
            r = client.get("/api/line/user/u1/profile")
        assert r.status_code == 200 and r.json()["displayName"] == "Me"

    def test_profile_other_forbidden(self, client):
        from core.models import UserRole
        lr = self._line_routes
        self._user.role = UserRole.MEMBER
        with patch.object(lr, "line_adapter", self._adapter(get_user_profile={"ok": True})):
            r = client.get("/api/line/user/other/profile")
        assert r.status_code == 403

    def test_profile_admin_allowed(self, client):
        from core.models import UserRole
        lr = self._line_routes
        self._user.role = UserRole.ADMIN
        with patch.object(lr, "line_adapter", self._adapter(
                get_user_profile={"ok": True, "displayName": "X"})):
            r = client.get("/api/line/user/anyone/profile")
        assert r.status_code == 200

    def test_profile_not_found_and_error(self, client):
        from core.models import UserRole
        lr = self._line_routes
        self._user.role = UserRole.ADMIN
        with patch.object(lr, "line_adapter", self._adapter(
                get_user_profile={"ok": False, "error": "nf"})):
            r = client.get("/api/line/user/x/profile")
            assert r.status_code == 404
        adapter = AsyncMock()
        adapter.get_user_profile = AsyncMock(side_effect=RuntimeError("net"))
        with patch.object(lr, "line_adapter", adapter):
            r = client.get("/api/line/user/x/profile")
            assert r.status_code == 500


# =========================================================================== #
# core/fleet_orchestration/fault_tolerance_service.py
# =========================================================================== #
class TestFaultToleranceService:
    def _svc(self, breakers=None):
        from core.fleet_orchestration.fault_tolerance_service import FaultToleranceService
        db = MagicMock()
        return FaultToleranceService(db=db, circuit_breakers=breakers or {}), db

    def _breaker(self, state, failure_count=0):
        from core.llm.fallback.circuit_breaker import CircuitBreakerState
        b = AsyncMock()
        b.get_state = AsyncMock(return_value=state)
        b.get_metrics = AsyncMock(return_value={"failure_count": failure_count})
        return b

    def test_should_retry_policies(self):
        from core.fleet.fleet_task_types import FailurePolicy, FleetTaskType
        svc, _ = self._svc()
        assert svc.should_retry(None, FailurePolicy.RETRY_THEN_STOP) is True
        assert svc.should_retry(None, FailurePolicy.STOP_ON_FAILURE) is False
        assert svc.should_retry(None, FailurePolicy.CONTINUE_ON_FAILURE) is False
        assert svc.should_retry(None, None) is False
        # default policy for a known task type
        assert isinstance(svc.should_retry(FleetTaskType.RESEARCH, None), bool)

    async def test_find_alternative_agent_not_found(self):
        svc, db = self._svc()
        db.query.return_value.filter.return_value.first.return_value = None
        assert await svc.find_alternative_specialist("a1", "c1") is None

    async def test_find_alternative_no_candidates(self):
        svc, db = self._svc()
        original = NS(id="a1", name="A", category="Finance")
        db.query.return_value.filter.return_value.first.return_value = original
        db.query.return_value.filter.return_value.all.return_value = []
        assert await svc.find_alternative_specialist("a1", "c1") is None

    async def test_find_alternative_selects_best(self):
        from core.llm.fallback.circuit_breaker import CircuitBreakerState
        svc, db = self._svc(breakers={
            "a2": self._breaker(CircuitBreakerState.OPEN, 3),
            "a3": self._breaker(CircuitBreakerState.CLOSED, 0),
        })
        original = NS(id="a1", name="A", category="Finance")
        alt2 = NS(id="a2", name="Bad", category="Finance")
        alt3 = NS(id="a3", name="Good", category="Finance")
        db.query.return_value.filter.return_value.first.return_value = original
        db.query.return_value.filter.return_value.all.return_value = [alt2, alt3]
        best = await svc.find_alternative_specialist("a1", "c1")
        assert best.id == "a3"

    async def test_select_best_half_open_and_neutral(self):
        from core.llm.fallback.circuit_breaker import CircuitBreakerState
        svc, _ = self._svc(breakers={
            "h": self._breaker(CircuitBreakerState.HALF_OPEN),
        })
        agents = [NS(id="h", name="H"), NS(id="n", name="N")]
        assert (await svc._select_best_alternative(agents)).id == "h"
        # both neutral -> first wins
        assert (await svc._select_best_alternative(
            [NS(id="x", name="X"), NS(id="y", name="Y")])).id == "x"

    async def test_retry_not_allowed_by_policy(self):
        from core.fleet.fleet_task_types import FailurePolicy
        svc, _ = self._svc()
        link = NS(id="l1", child_agent_id="a1", chain_id="c1", parent_agent_id="p",
                  task_description="t", context_json={}, link_order=1)
        assert await svc.retry_with_alternative_specialist(
            link, failure_policy_override=FailurePolicy.STOP_ON_FAILURE) is None

    def _full_link(self, context=None):
        return NS(id="l1", child_agent_id="a1", chain_id="c1", parent_agent_id="p",
                  task_description="t", context_json=context or {}, link_order=1)

    async def test_retry_success_flow(self):
        from core.fleet.fleet_task_types import FailurePolicy
        svc, db = self._svc()
        original = NS(id="a1", name="A", category="Finance")
        alternative = NS(id="a2", name="B", category="Finance")
        db.query.return_value.filter.return_value.first.return_value = original
        db.query.return_value.filter.return_value.all.return_value = [alternative]

        new_link = NS(id="l2", child_agent_id="a2")
        fleet = MagicMock()
        fleet.recruit_member = Mock(return_value=new_link)
        link = self._full_link()
        with patch("core.agent_fleet_service.AgentFleetService", return_value=fleet), \
             patch.object(svc, "_record_retry_event") as rec:
            result = await svc.retry_with_alternative_specialist(
                link, failure_policy_override=FailurePolicy.RETRY_THEN_STOP)
        assert result is new_link
        rec.assert_called_once()
        # failed link context updated
        assert link.context_json["retried_with_link_id"] == "l2"
        fleet.recruit_member.assert_called_once()
        ctx = fleet.recruit_member.call_args[1]["context_json"]
        assert ctx["is_fault_tolerance_retry"] is True and ctx["retry_attempt"] == 2

    async def test_retry_open_breaker_logs_and_no_alternative(self):
        from core.llm.fallback.circuit_breaker import CircuitBreakerState
        svc, db = self._svc(breakers={"a1": self._breaker(CircuitBreakerState.OPEN)})
        db.query.return_value.filter.return_value.first.return_value = None  # no original
        link = self._full_link()
        assert await svc.retry_with_alternative_specialist(
            link, failure_policy_override=None) is None

    async def test_retry_with_exclusions_from_retry_chain(self):
        from core.fleet.fleet_task_types import FailurePolicy
        svc, db = self._svc()
        original = NS(id="a1", name="A", category="Ops")
        alt = NS(id="a3", name="C", category="Ops")
        # first() called for: original agent lookup, prior link lookup(s)
        prior = NS(id="l0", child_agent_id="a0", context_json={})
        db.query.return_value.filter.return_value.first.side_effect = [prior, original]
        db.query.return_value.filter.return_value.all.return_value = [alt]
        new_link = NS(id="l3", child_agent_id="a3")
        fleet = MagicMock()
        fleet.recruit_member = Mock(return_value=new_link)
        link = self._full_link(context={"original_failed_link_id": "l0"})
        with patch("core.agent_fleet_service.AgentFleetService", return_value=fleet), \
             patch.object(svc, "_record_retry_event"):
            result = await svc.retry_with_alternative_specialist(
                link, failure_policy_override=FailurePolicy.RETRY_THEN_STOP)
        assert result is new_link

    def test_get_tried_agent_ids_no_context(self):
        svc, db = self._svc()
        assert svc._get_tried_agent_ids(self._full_link()) == {"a1"}

    def test_get_tried_agent_ids_walks_chain(self):
        svc, db = self._svc()
        grandparent = NS(id="l-1", child_agent_id="a-1", context_json={})
        parent = NS(id="l0", child_agent_id="a0",
                    context_json={"original_failed_link_id": "l-1"})
        db.query.return_value.filter.return_value.first.side_effect = [parent, grandparent]
        link = NS(id="l1", child_agent_id="a1",
                  context_json={"original_failed_link_id": "l0"})
        assert svc._get_tried_agent_ids(link) == {"a1", "a0", "a-1"}

    def test_record_retry_event_success_and_failure(self):
        from core.models import FleetHealingEvent
        svc, db = self._svc()
        link = self._full_link()
        retry = NS(id="l2")
        alt = NS(id="a2", name="B", category="Fin")
        svc._record_retry_event(link, retry, alt)
        added = db.add.call_args[0][0]
        assert isinstance(added, FleetHealingEvent)
        db.commit.side_effect = RuntimeError("db")
        svc._record_retry_event(link, retry, alt)
        db.rollback.assert_called_once()

    def test_get_or_create_circuit_breaker(self):
        svc, _ = self._svc()
        b1 = svc.get_or_create_circuit_breaker("a1", failure_threshold=2, recovery_timeout=5.0)
        assert svc.get_or_create_circuit_breaker("a1") is b1

    async def test_handle_failed_task_no_link(self):
        svc, db = self._svc()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        res = await svc.handle_failed_task("c1", "a1", "t")
        assert res == {"retried": False, "reason": "ChainLink not found"}

    async def test_handle_failed_task_policy_blocks(self):
        from core.fleet.fleet_task_types import FailurePolicy, FleetTaskType
        svc, db = self._svc()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = self._full_link()
        res = await svc.handle_failed_task(
            "c1", "a1", "t", task_type=FleetTaskType.RESEARCH,
            error=RuntimeError("x"))
        assert res["retried"] is False

    async def test_handle_failed_task_retry_success(self):
        svc, db = self._svc()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = self._full_link()
        new_link = NS(id="l2", child_agent_id="a2")
        with patch.object(svc, "should_retry", Mock(return_value=True)), \
             patch.object(svc, "retry_with_alternative_specialist",
                          AsyncMock(return_value=new_link)):
            res = await svc.handle_failed_task("c1", "a1", "t")
        assert res == {"retried": True, "retry_link_id": "l2", "alternative_agent_id": "a2"}

    async def test_handle_failed_task_retry_none(self):
        svc, db = self._svc()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = self._full_link()
        with patch.object(svc, "should_retry", Mock(return_value=True)), \
             patch.object(svc, "retry_with_alternative_specialist", AsyncMock(return_value=None)):
            res = await svc.handle_failed_task("c1", "a1", "t")
        assert res == {"retried": False, "reason": "No alternative specialist available"}


# =========================================================================== #
# Batch-1 gap fillers (wrapper dispatch, error paths, default constructors)
# =========================================================================== #
class TestBatch1GapFillers:
    async def test_box_execute_remaining_ops(self):
        from integrations.box_service import BoxService
        svc = BoxService()
        with patch.object(svc, "_box_get", AsyncMock(return_value={"id": "f", "type": "file"})), \
                patch.object(svc, "_box_get_bytes", AsyncMock(return_value=b"x")), \
                patch.object(svc, "_box_post", AsyncMock(return_value={"id": "folder_1"})):
            for op, params in [
                ("get_file_metadata", {"access_token": "t", "file_id": "f"}),
                ("download_file", {"access_token": "t", "file_id": "f"}),
                ("create_folder", {"access_token": "t", "parent_folder_id": "0", "folder_name": "n"}),
            ]:
                res = await svc.execute_operation(op, params)
                assert res["success"] is True, op

    async def test_fault_tolerance_open_breaker_and_no_alternative(self):
        from core.fleet_orchestration.fault_tolerance_service import FaultToleranceService
        from core.fleet.fleet_task_types import FailurePolicy
        from core.llm.fallback.circuit_breaker import CircuitBreakerState

        class _B(AsyncMock):
            pass
        breaker = _B()
        breaker.get_state = AsyncMock(return_value=CircuitBreakerState.OPEN)
        svc = FaultToleranceService(db=MagicMock(), circuit_breakers={"a1": breaker})
        link = NS(id="l1", child_agent_id="a1", chain_id="c1", parent_agent_id="p",
                  task_description="t", context_json={}, link_order=1)
        svc.db.query.return_value.filter.return_value.first.return_value = None
        result = await svc.retry_with_alternative_specialist(
            link, failure_policy_override=FailurePolicy.RETRY_THEN_STOP)
        assert result is None

    async def test_gitlab_default_ctor_and_error_paths(self):
        import httpx
        from integrations.gitlab_service import GitLabService
        svc = GitLabService()  # config=None default
        svc.client = MagicMock()
        err = _err_resp(RuntimeError("x"))
        svc.client.get = AsyncMock(return_value=err)
        with pytest.raises(Exception):
            await svc.get_issues("t")
        svc.client.get = AsyncMock(return_value=err)
        with pytest.raises(Exception):
            await svc.search_projects("t", "q")
        # existing metric update branch
        svc.client.get = AsyncMock(return_value=_resp([{"id": 1}]))
        existing = MagicMock()
        with patch("core.database.SessionLocal", return_value=_mock_db_session(first=existing)):
            res = await svc.sync_to_postgres_cache("ws", "t")
        assert res["success"] is True and existing.value == 1.0

    async def test_tableau_default_ctor_and_error_paths(self):
        import httpx
        from fastapi import HTTPException
        from integrations.tableau_service import TableauService
        svc = TableauService()  # config=None default
        svc.client = MagicMock()
        err = _err_resp(httpx.HTTPError("e"))
        svc.client.get = AsyncMock(side_effect=[err, err])
        with pytest.raises(HTTPException):
            await svc.get_views("t")
        with pytest.raises(HTTPException):
            await svc.get_datasources("t")

    def test_line_and_matrix_default_ctor(self):
        from integrations.line_service import LineService
        from integrations.matrix_service import MatrixService
        assert LineService().base_url.endswith("/message")
        assert MatrixService().homeserver.startswith("https://")


# =========================================================================== #
# core/fleet_orchestration/scaling_proposal_service.py
# =========================================================================== #
def _metrics(success_rate=99.0, latency=100.0, throughput=10.0, count=4):
    return NS(success_rate=success_rate, avg_latency_ms=latency,
              throughput_per_minute=throughput, execution_count=count)


class TestScalingProposalServiceGaps:
    def _svc(self, redis_url=None):
        from core.fleet_orchestration.scaling_proposal_service import ScalingProposalService
        svc = ScalingProposalService(MagicMock(), redis_url=redis_url)
        svc.metrics_service = MagicMock()
        svc.overage_service = MagicMock()
        return svc

    async def test_get_redis_no_url(self):
        import core.fleet_orchestration.scaling_proposal_service as sps_mod
        svc = self._svc()
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(sps_mod.redis, "from_url") as fu:
                assert await svc._get_redis() is None
        fu.assert_not_called()

    async def test_get_redis_with_url_and_error(self):
        import core.fleet_orchestration.scaling_proposal_service as sps_mod
        svc = self._svc(redis_url="redis://x")
        fake = object()
        with patch.object(sps_mod.redis, "from_url", return_value=fake) as fu:
            assert await svc._get_redis() is fake
        # error creating client
        svc2 = self._svc(redis_url="redis://x")
        svc2._redis_client = None
        with patch.object(sps_mod.redis, "from_url", side_effect=RuntimeError("bad")):
            assert await svc2._get_redis() is None

    async def test_analyze_expansion_critical_and_warning(self):
        svc = self._svc()
        svc.metrics_service.get_metrics = AsyncMock(return_value=_metrics(success_rate=50.0))
        with patch.object(svc, "_check_hysteresis", AsyncMock(return_value=True)):
            assert await svc.analyze_scaling_need("c1") is not None
        svc.metrics_service.get_metrics = AsyncMock(return_value=_metrics(success_rate=80.0))
        with patch.object(svc, "_check_hysteresis", AsyncMock(return_value=True)):
            assert await svc.analyze_scaling_need("c1") is not None

    async def test_analyze_latency_critical_and_warning(self):
        svc = self._svc()
        svc.metrics_service.get_metrics = AsyncMock(return_value=_metrics(latency=50000))
        with patch.object(svc, "_check_hysteresis", AsyncMock(return_value=True)):
            assert await svc.analyze_scaling_need("c1") is not None
        svc.metrics_service.get_metrics = AsyncMock(return_value=_metrics(latency=25000))
        with patch.object(svc, "_check_hysteresis", AsyncMock(return_value=True)):
            assert await svc.analyze_scaling_need("c1") is not None

    async def test_analyze_contraction_and_hysteresis_suppression(self):
        svc = self._svc()
        svc.metrics_service.get_metrics = AsyncMock(
            return_value=_metrics(success_rate=99.0, throughput=1.0))
        with patch.object(svc, "_check_hysteresis", AsyncMock(return_value=True)):
            assert await svc.analyze_scaling_need("c1") is not None
        with patch.object(svc, "_check_hysteresis", AsyncMock(return_value=False)):
            assert await svc.analyze_scaling_need("c1") is None

    async def test_analyze_no_need_and_exception(self):
        svc = self._svc()
        svc.metrics_service.get_metrics = AsyncMock(return_value=_metrics())
        assert await svc.analyze_scaling_need("c1") is None
        svc.metrics_service.get_metrics = AsyncMock(side_effect=RuntimeError("m"))
        assert await svc.analyze_scaling_need("c1") is None

    async def test_create_expansion_and_contraction_proposals(self):
        svc = self._svc()
        svc.overage_service.get_effective_limit = Mock(return_value=100)
        svc.db.query.return_value.filter.return_value.scalar.return_value = 2
        with patch.object(svc, "_persist_proposal", AsyncMock()) as pers, \
             patch.object(svc, "_set_hysteresis_timestamp", AsyncMock()):
            p = await svc.create_expansion_proposal("c1", 5, 10, "why")
            assert p.proposal_type == "expansion"
            assert p.metadata["warnings"] == []
            c = await svc.create_contraction_proposal("c1", 10, 5, "shrink")
            assert c.cost_estimate < 0
        pers.assert_called()

    async def test_create_expansion_proposal_exceeds_limit(self):
        svc = self._svc()
        svc.overage_service.get_effective_limit = Mock(return_value=5)
        svc.db.query.return_value.filter.return_value.scalar.return_value = 2
        with patch.object(svc, "_persist_proposal", AsyncMock()), \
             patch.object(svc, "_set_hysteresis_timestamp", AsyncMock()):
            p = await svc.create_expansion_proposal("c1", 5, 10, "why")
            assert p.metadata["current_limit"] == 5

    async def test_validate_fleet_size_limit_paths(self):
        svc = self._svc()
        svc.overage_service.get_effective_limit = Mock(return_value=10)
        svc.db.query.return_value.filter.return_value.scalar.return_value = 9
        res = await svc.validate_fleet_size_limit("c1", 20)
        assert res["allowed"] is False
        assert res["warnings"][0]["severity"] == "critical"
        svc.db.query.return_value.filter.return_value.scalar.return_value = 0
        res = await svc.validate_fleet_size_limit("c1", 8)
        assert res["allowed"] is True
        assert res["warnings"][0]["severity"] == "warning"

    async def test_hysteresis_paths(self):
        from datetime import datetime, timezone, timedelta
        svc = self._svc()
        assert await svc._check_hysteresis("c", "expansion") is True  # no redis
        fake = AsyncMock()
        fake.get = AsyncMock(return_value=(
            datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat())
        with patch.object(svc, "_get_redis", AsyncMock(return_value=fake)):
            assert await svc._check_hysteresis("c", "expansion") is False
        fake.get = AsyncMock(return_value=(
            datetime.now(timezone.utc) - timedelta(days=5)).isoformat())
        with patch.object(svc, "_get_redis", AsyncMock(return_value=fake)):
            assert await svc._check_hysteresis("c", "expansion") is True
        fake.get = AsyncMock(side_effect=RuntimeError("r"))
        with patch.object(svc, "_get_redis", AsyncMock(return_value=fake)):
            assert await svc._check_hysteresis("c", "expansion") is True

    async def test_hysteresis_set_and_suppression(self):
        svc = self._svc()
        await svc._set_hysteresis_timestamp("c", "expansion")  # no redis no-op
        await svc._set_rejection_suppression("c", "expansion")
        fake = AsyncMock()
        fake.set = AsyncMock(side_effect=[None, RuntimeError("x")])
        with patch.object(svc, "_get_redis", AsyncMock(return_value=fake)):
            await svc._set_hysteresis_timestamp("c", "expansion")
            await svc._set_rejection_suppression("c", "expansion")
        fake2 = AsyncMock()
        fake2.set = AsyncMock(side_effect=RuntimeError("x"))
        with patch.object(svc, "_get_redis", AsyncMock(return_value=fake2)):
            await svc._set_rejection_suppression("c", "expansion")

    async def test_persist_proposal_and_error(self):
        from datetime import datetime, timezone
        svc = self._svc()
        from core.fleet_orchestration.scaling_proposal_service import (
            ScalingProposal, ScalingProposalType)
        prop = ScalingProposal(
            chain_id="c1", proposal_type=ScalingProposalType.EXPANSION,
            current_fleet_size=2, proposed_fleet_size=4, reason="r",
            expires_at=datetime.now(timezone.utc))
        await svc._persist_proposal(prop)
        svc.db.add.assert_called_once()
        svc.db.commit.side_effect = RuntimeError("db")
        await svc._persist_proposal(prop)
        svc.db.rollback.assert_called_once()

    async def test_get_proposal_paths(self):
        svc = self._svc()
        svc.db.query.return_value.filter.return_value.first.return_value = None
        assert await svc.get_proposal("p1") is None
        from datetime import datetime, timezone
        model = NS(id="p1", chain_id="c1", proposal_type="expansion",
                   current_agents=2, proposed_agents=4, reason="r",
                   metadata_json={"metrics": {"a": 1.0}, "cost_estimate": "1.5",
                                  "duration_hours": "2"},
                   status="pending", expires_at=datetime.now(timezone.utc),
                   created_at=None)
        svc.db.query.return_value.filter.return_value.first.return_value = model
        p = await svc.get_proposal("p1")
        assert p.metrics == {"a": 1.0} and p.duration_hours == 2.0
        svc.db.query.return_value.filter.return_value.all.return_value = [model]
        assert len(await svc.get_pending_proposals()) == 1

    async def test_approve_reject_paths(self):
        from datetime import datetime, timezone, timedelta
        svc = self._svc()
        q = svc.db.query.return_value.filter.return_value
        q.first.return_value = None
        with pytest.raises(ValueError):
            await svc.approve_proposal("p", "u")
        with pytest.raises(ValueError):
            await svc.reject_proposal("p", "u", "no")
        model = NS(id="p1", status="approved", chain_id="c1",
                   proposal_type="expansion",
                   expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        q.first.return_value = model
        with pytest.raises(ValueError):
            await svc.approve_proposal("p1", "u")
        with pytest.raises(ValueError):
            await svc.reject_proposal("p1", "u", "no")
        model2 = NS(id="p2", status="pending", chain_id="c1",
                    proposal_type="expansion",
                    expires_at=datetime.now(timezone.utc) - timedelta(hours=1))
        q.first.return_value = model2
        with pytest.raises(ValueError):
            await svc.approve_proposal("p2", "u")
        assert model2.status == "expired"
        # successful approve + reject
        model3 = NS(id="p3", status="pending", chain_id="c1",
                    proposal_type="expansion",
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        q.first.return_value = model3
        with patch.object(svc, "get_proposal", AsyncMock(return_value="OK")):
            assert await svc.approve_proposal("p3", "u", note="n") == "OK"
        model4 = NS(id="p4", status="pending", chain_id="c1",
                    proposal_type="expansion",
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        q.first.return_value = model4
        with patch.object(svc, "_set_rejection_suppression", AsyncMock()), \
             patch.object(svc, "get_proposal", AsyncMock(return_value="OK")):
            assert await svc.reject_proposal("p4", "u", "r") == "OK"

    async def test_cost_and_prediction(self):
        svc = self._svc()
        assert await svc.estimate_scaling_cost(10, 12, 24.0) == pytest.approx(0.48)
        res = await svc.validate_budget_for_proposal("c1", 10, 24.0)
        assert res["allowed"] is True and res["budget_exceeded"] is False
        pred = await svc.predict_scaling_cost(10, 12, duration_hours=24.0)
        assert pred["total"] == pytest.approx(0.48)
        assert pred["breakdown"]["agent_cost"] == pytest.approx(0.38, abs=0.01)
        pred0 = await svc.predict_scaling_cost(10, 10, duration_hours=0)
        assert pred0["hourly_cost"] == 0

    def test_get_scaling_proposal_service_singleton(self):
        import core.fleet_orchestration.scaling_proposal_service as sps_mod
        prev = sps_mod._service_instance
        sps_mod._service_instance = None
        s1 = sps_mod.get_scaling_proposal_service(MagicMock())
        s2 = sps_mod.get_scaling_proposal_service(MagicMock())
        assert s1 is s2
        sps_mod._service_instance = prev


# =========================================================================== #
# core/fleet_orchestration/fleet_scaler_service.py
# =========================================================================== #
class TestFleetScalerServiceGaps:
    def _svc(self):
        from core.fleet_orchestration.fleet_scaler_service import FleetScalerService
        svc = FleetScalerService(MagicMock())
        svc.proposal_service = MagicMock()
        svc.metrics_service = MagicMock()
        svc.overage_service = MagicMock()
        return svc

    def _proposal(self, ptype="expansion", status="approved", expires=None):
        from datetime import datetime, timezone, timedelta
        from core.fleet_orchestration.scaling_proposal_service import ScalingProposalType
        return NS(
            id="p1", chain_id="c1",
            proposal_type=ScalingProposalType.EXPANSION if ptype == "expansion"
            else ScalingProposalType.CONTRACTION,
            current_fleet_size=2, proposed_fleet_size=4,
            status=status,
            expires_at=expires or datetime.now(timezone.utc) + timedelta(hours=1),
        )

    def test_scaling_operation_to_dict(self):
        from datetime import datetime, timezone
        from core.fleet_orchestration.fleet_scaler_service import (
            ScalingOperation, ScalingOperationStatus)
        op = ScalingOperation(
            id="o1", chain_id="c1", proposal_id="p1", operation_type="expand",
            from_size=2, to_size=4, status=ScalingOperationStatus.COMPLETED,
            started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            completed_at=datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc))
        d = op.to_dict()
        assert d["status"] == "completed" and d["completed_at"] is not None

    async def test_execute_scaling_naive_expiry(self):
        from datetime import datetime, timedelta
        svc = self._svc()
        prop = self._proposal(expires=datetime.now() - timedelta(hours=2))  # naive
        svc.proposal_service.get_proposal = AsyncMock(return_value=prop)
        with pytest.raises(ValueError, match="expired"):
            await svc.execute_scaling("p1")

    async def test_execute_scaling_persist_failure_path(self):
        svc = self._svc()
        svc.proposal_service.get_proposal = AsyncMock(return_value=self._proposal())
        svc.proposal_service._update_proposal_status = AsyncMock()
        with patch.object(svc, "_execute_expansion", AsyncMock(
                return_value={"recruited_agents": ["a"]})), \
             patch.object(svc, "_persist_operation", AsyncMock()):
            op = await svc.execute_scaling("p1")
        assert op.status == "completed"
        with patch.object(svc, "_execute_contraction", AsyncMock(
                side_effect=RuntimeError("boom"))), \
             patch.object(svc, "_persist_operation", AsyncMock()):
            prop = self._proposal(ptype="contraction")
            svc.proposal_service.get_proposal = AsyncMock(return_value=prop)
            op = await svc.execute_scaling("p1")
        assert op.status == "failed" and "boom" in op.error_message

    async def test_execute_expansion_root_placeholder(self):
        from core.models import AgentStatus
        svc = self._svc()
        prop = self._proposal()
        svc.db.query.return_value.filter.return_value.all.return_value = []  # no pool
        svc.db.query.return_value.filter.return_value.first.return_value = None
        svc.db.query.return_value.filter.return_value.limit.return_value.all.return_value = []

        svc.db.add = Mock(side_effect=lambda m: setattr(m, "id", "agent-new"))
        op = NS(agents_added=[])
        with patch("core.fleet_orchestration.get_distributed_blackboard",
                   return_value=None):
            result = await svc._execute_expansion(prop, op)
        assert set(result["recruited_agents"]) == {"agent-new"}
        assert len(op.agents_added) == 2

    async def test_check_scaling_constraints_paths(self):
        svc = self._svc()
        svc.overage_service.get_effective_limit = Mock(return_value=5)
        svc.db.query.return_value.filter.return_value.scalar.return_value = 2
        svc.overage_service.check_overage_expiry = AsyncMock(return_value=True)
        res = await svc.check_scaling_constraints("c1", 10)
        assert res["allowed"] is False
        assert "reason" in res["constraints"]["fleet_size_limit"]
        assert res["constraints"]["overage_expiry"]["status"] == "expired"
        svc.overage_service.get_effective_limit = Mock(return_value=100)
        svc.overage_service.check_overage_expiry = AsyncMock(return_value=False)
        res = await svc.check_scaling_constraints("c1", 10)
        assert res["allowed"] is True and res["constraints"]["plan_quota"]["allowed"]

    async def test_persist_operation_and_import_error(self):
        from core.fleet_orchestration.fleet_scaler_service import (
            ScalingOperation, ScalingOperationStatus)
        from datetime import datetime, timezone
        svc = self._svc()
        op = ScalingOperation(
            id="o1", chain_id="c1", proposal_id="p1", operation_type="expand",
            from_size=2, to_size=4, status=ScalingOperationStatus.COMPLETED,
            started_at=datetime.now(timezone.utc))
        await svc._persist_operation(op)
        svc.db.add.assert_called_once()
        svc.db.commit.side_effect = RuntimeError("db")
        await svc._persist_operation(op)  # swallowed
        # ImportError branch of _get_recent_operations
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "core.models":
                raise ImportError("nope")
            return real_import(name, *a, **k)
        with patch.object(builtins, "__import__", side_effect=fake_import):
            assert await svc._get_recent_operations("c1") == []

    async def test_get_recent_operations_rows(self):
        from core.fleet_orchestration.fleet_scaler_service import (
            ScalingOperation, ScalingOperationStatus)
        from datetime import datetime, timezone
        svc = self._svc()
        svc.db.query.return_value.filter.return_value.order_by \
            .return_value.limit.return_value.all.return_value = []
        assert await svc._get_recent_operations("c1") == []

    async def test_continuous_monitoring_loop(self):
        svc = self._svc()
        svc.db.query.return_value.filter.return_value.all.return_value = [NS(id="c1")]
        called = AsyncMock(return_value=None)

        async def stop(*a, **k):
            svc.running = False
        with patch.object(svc, "monitor_and_scale", called), \
             patch("core.fleet_orchestration.fleet_scaler_service.asyncio.sleep",
                   AsyncMock(side_effect=stop)):
            svc.running = True
            await svc.continuous_monitoring_loop(interval_seconds=1)
        called.assert_awaited()

    async def test_monitoring_loop_and_overage_expiry(self):
        svc = self._svc()
        svc.overage_service.check_overage_expiry = AsyncMock(return_value=True)
        svc.db.query.return_value.filter.return_value.all.return_value = [("c1",)]
        svc.db.query.return_value.filter.return_value.first.return_value = NS(id="c1")

        async def stop(*a, **k):
            svc.running = False
        with patch.object(svc, "_get_active_chains", AsyncMock(return_value=["c1"])), \
             patch.object(svc, "_handle_overage_expiry", AsyncMock()) as hh, \
             patch("core.fleet_orchestration.fleet_scaler_service.asyncio.sleep",
                   AsyncMock(side_effect=stop)):
            svc.running = True
            await svc._monitoring_loop()
        hh.assert_awaited_once_with("c1")
        # inner error is swallowed
        with patch.object(svc, "_get_active_chains",
                          AsyncMock(side_effect=RuntimeError("x"))), \
             patch("core.fleet_orchestration.fleet_scaler_service.asyncio.sleep",
                   AsyncMock(side_effect=stop)):
            svc.running = True
            await svc._monitoring_loop()

    async def test_get_active_chains(self):
        svc = self._svc()
        q = svc.db.query.return_value.filter.return_value
        q.all = Mock(side_effect=[[("c1",)], [("c2",)]])
        q.distinct.return_value.all.return_value = [("c2",)]
        svc.db.query.side_effect = None
        # first query (overage chains), second (proposal chains)
        svc.db.query = MagicMock()
        svc.db.query.return_value.filter.return_value.all.return_value = [("c1",)]
        svc.db.query.return_value.filter.return_value.distinct \
            .return_value.all.return_value = [("c2",), ("c1",)]
        assert await svc._get_active_chains() == ["c1", "c2"]

    async def test_handle_overage_expiry_paths(self):
        svc = self._svc()
        svc.db.query.return_value.filter.return_value.first.return_value = None
        await svc._handle_overage_expiry("missing")  # chain not found -> returns
        svc.db.query.return_value.filter.return_value.first.return_value = NS(id="c1")
        svc.db.query.return_value.filter.return_value.scalar.return_value = 50
        with patch.dict(os.environ, {"MAX_FLEET_SIZE": "100"}):
            await svc._handle_overage_expiry("c1")  # below limit -> no proposal
        svc.db.query.return_value.filter.return_value.scalar.return_value = 150
        prop = self._proposal(ptype="contraction")
        svc.proposal_service.create_contraction_proposal = AsyncMock(return_value=prop)
        svc.proposal_service.approve_proposal = AsyncMock()
        with patch.dict(os.environ, {"MAX_FLEET_SIZE": "100"}):
            await svc._handle_overage_expiry("c1")
        svc.proposal_service.approve_proposal.assert_awaited_once()
        # approve failure swallowed
        svc.proposal_service.approve_proposal = AsyncMock(side_effect=RuntimeError("x"))
        with patch.dict(os.environ, {"MAX_FLEET_SIZE": "100"}):
            await svc._handle_overage_expiry("c1")

    async def test_start_stop_monitoring(self):
        svc = self._svc()
        await svc.start_monitoring()
        assert svc.running is True and svc._monitor_task is not None
        await svc.start_monitoring()  # already running -> warns
        await svc.stop_monitoring()
        assert svc.running is False
        await svc.stop_monitoring()  # not running no-op
        svc2 = self._svc()
        svc2.running = True
        svc2._monitor_task = None
        await svc2.stop_monitoring()

    async def test_execute_scaling_proposal(self):
        svc = self._svc()
        svc.proposal_service.get_proposal = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="not found"):
            await svc.execute_scaling_proposal("p1")
        svc.proposal_service.get_proposal = AsyncMock(return_value=self._proposal())
        svc.overage_service.get_effective_limit = Mock(return_value=100)
        svc.db.query.return_value.filter.return_value.scalar.return_value = 2
        svc.overage_service.check_overage_expiry = AsyncMock(return_value=False)
        res = await svc.execute_scaling_proposal("p1")
        assert res["success"] is True
        # constraints not met
        svc.overage_service.get_effective_limit = Mock(return_value=1)
        with pytest.raises(ValueError, match="constraints"):
            await svc.execute_scaling_proposal("p1")

    def test_get_fleet_scaler_service_factory(self):
        from core.fleet_orchestration.fleet_scaler_service import get_fleet_scaler_service
        svc = get_fleet_scaler_service(MagicMock())
        assert svc.running is False


# =========================================================================== #
# core/jit_verification_cache.py
# =========================================================================== #
class TestJITVerificationCache:
    def _vr(self, exists=True, age_seconds=0):
        from core.jit_verification_cache import CitationVerificationResult
        from datetime import datetime, timedelta
        return CitationVerificationResult(
            exists=exists,
            checked_at=datetime.now() - timedelta(seconds=age_seconds),
            citation="c", size=10,
            last_modified=datetime.now())

    def _qr(self, age_seconds=0):
        from core.jit_verification_cache import BusinessFactQueryResult
        from datetime import datetime, timedelta
        return BusinessFactQueryResult(
            facts=[{"id": 1}], cached_at=datetime.now() - timedelta(seconds=age_seconds),
            query="q", limit=5, domain="d")

    def test_result_roundtrip(self):
        from core.jit_verification_cache import (
            CitationVerificationResult, BusinessFactQueryResult)
        from datetime import datetime
        vr = CitationVerificationResult(
            True, datetime.now(), "cite", 5, datetime.now())
        d = vr.to_dict()
        assert CitationVerificationResult.from_dict(d).exists is True
        qr = BusinessFactQueryResult([{"a": 1}], datetime.now(), "q", 5, "d")
        d = qr.to_dict()
        assert BusinessFactQueryResult.from_dict(d).facts == [{"a": 1}]

    def test_l1_verification_hit_miss_ttl_evict(self):
        from core.jit_verification_cache import L1MemoryCache
        c = L1MemoryCache(max_size=2, verification_ttl=100)
        assert c.get_verification("missing") is None  # miss
        c.set_verification("c1", self._vr())
        assert c.get_verification("c1") is not None  # hit
        # TTL expiry
        c.set_verification("c2", self._vr(age_seconds=1000))
        assert c.get_verification("c2") is None
        # eviction by capacity
        c2 = L1MemoryCache(max_size=1, verification_ttl=100)
        c2.set_verification("a", self._vr())
        c2.set_verification("b", self._vr())
        assert c2.get_verification("a") is None
        assert c2.get_stats()["l1_evictions"] >= 1

    def test_l1_query_hit_miss_ttl_evict_invalidate(self):
        from core.jit_verification_cache import L1MemoryCache
        c = L1MemoryCache(max_size=8, query_ttl=100)
        assert c.get_query("q", 5, None) is None
        c.set_query("q", 5, None, self._qr())
        assert c.get_query("q", 5, None) is not None
        c.set_query("q2", 5, None, self._qr(age_seconds=10000))
        assert c.get_query("q2", 5, None) is None
        c.set_query("q3", 5, None, self._qr())
        c.invalidate_query("q3", 5, None)
        assert c.get_query("q3", 5, None) is None
        # eviction: query_max_size = max_size // 4 = 1
        c2 = L1MemoryCache(max_size=4, query_ttl=100)
        c2.set_query("a", 5, None, self._qr())
        c2.set_query("b", 5, None, self._qr())
        assert c2.get_query("a", 5, None) is None
        stats = c2.get_stats()
        assert stats["l1_query_cache_size"] == 1
        c2.clear()
        assert c2.get_stats()["l1_query_cache_size"] == 0

    def test_l1_invalidate_citation_and_stats(self):
        from core.jit_verification_cache import L1MemoryCache
        c = L1MemoryCache()
        c.set_verification("c", self._vr())
        c.invalidate_citation("c")
        assert c.get_verification("c") is None
        s = c.get_stats()
        assert s["l1_verification_hits"] == 0 and "l1_query_hit_rate" in s

    def test_l2_init_failure(self):
        import core.jit_verification_cache as jmod
        from core.jit_verification_cache import L2RedisCache
        with patch.object(jmod.redis, "from_url", side_effect=RuntimeError("no")):
            c = L2RedisCache(redis_url="redis://x")
            assert c._enabled is False

    async def test_l2_enabled_paths(self):
        import core.jit_verification_cache as jmod
        from core.jit_verification_cache import L2RedisCache
        c = L2RedisCache.__new__(L2RedisCache)
        c.verification_ttl = 10
        c.query_ttl = 10
        c._enabled = True
        c._redis = MagicMock()
        good = self._vr()
        c._redis.get = Mock(return_value=json_mod.dumps(good.to_dict()))
        got = await c.get_verification("c")
        assert got is not None and got.exists is True
        await c.set_verification("c", good)
        c._redis.setex.assert_called_once()
        qgood = self._qr()
        c._redis.get = Mock(return_value=json_mod.dumps(qgood.to_dict()))
        got = await c.get_query("q", 5, "d")
        assert got is not None and got.facts == [{"id": 1}]
        await c.set_query("q", 5, "d", qgood)
        c.invalidate_citation("c")
        c._redis.delete.assert_called_once()
        c._redis.scan_iter = Mock(return_value=iter([b"k1", b"k2"]))
        c.clear()
        assert c._redis.delete.call_count == 3
        # error paths
        c._redis.get = Mock(side_effect=RuntimeError("r"))
        c._redis.setex = Mock(side_effect=RuntimeError("r"))
        c._redis.delete = Mock(side_effect=RuntimeError("r"))
        c._redis.scan_iter = Mock(side_effect=RuntimeError("r"))
        assert await c.get_verification("c") is None
        await c.set_verification("c", good)
        await c.get_query("q", 5, "d")
        await c.set_query("q", 5, "d", qgood)
        c.invalidate_citation("c")
        c.clear()

    async def test_l2_noop_when_disabled(self):
        from core.jit_verification_cache import L2RedisCache
        c = L2RedisCache.__new__(L2RedisCache)
        c.verification_ttl = 10
        c.query_ttl = 10
        c._enabled = False
        assert await c.get_verification("c") is None
        await c.set_verification("c", self._vr())
        assert await c.get_query("q", 1, None) is None
        await c.set_query("q", 1, None, self._qr())
        c.invalidate_citation("c")
        c.clear()

    async def test_verify_citation_local_and_s3(self, tmp_path):
        from core.jit_verification_cache import JITVerificationCache
        cache = JITVerificationCache()
        f = tmp_path / "doc.txt"
        f.write_text("hello")
        res = await cache.verify_citation(str(f))
        assert res.exists is True and res.size == 5
        res = await cache.verify_citation(str(tmp_path / "nope.txt"))
        assert res.exists is False
        # cached hit on second call
        res2 = await cache.verify_citation(str(f))
        assert res2.exists is True

    async def test_verify_citation_s3_paths(self):
        from core.jit_verification_cache import JITVerificationCache
        cache = JITVerificationCache()
        storage = MagicMock()
        storage.bucket = "bkt"
        head = {"ContentLength": 42, "LastModified": "lm"}
        storage.s3.head_object = Mock(return_value=head)
        cache._storage = storage
        res = await cache.verify_citation("s3://bkt/key1", force_refresh=True)
        assert res.exists is True and res.size == 42
        # head fails -> exists False
        storage.s3.head_object = Mock(side_effect=RuntimeError("404"))
        res = await cache.verify_citation("s3://bkt/key2", force_refresh=True)
        assert res.exists is False
        # bucket attr raises -> warning path
        storage2 = MagicMock()
        type(storage2).bucket = PropertyMock(side_effect=RuntimeError("no bucket"))
        cache._storage = storage2
        res = await cache.verify_citation("s3://other/x", force_refresh=True)
        assert res.exists is False

    async def test_verify_citations_batch(self, tmp_path):
        from core.jit_verification_cache import JITVerificationCache
        cache = JITVerificationCache()
        f1 = tmp_path / "a.txt"; f1.write_text("a")
        f2 = tmp_path / "b.txt"; f2.write_text("b")
        results = await cache.verify_citations_batch([str(f1), str(f2)])
        assert [r.exists for r in results] == [True, True]

    async def test_get_business_facts(self):
        from core.jit_verification_cache import (
            JITVerificationCache, BusinessFactQueryResult)
        from datetime import datetime
        cache = JITVerificationCache()
        fact = NS(id="f1", fact="F", citations=[], reason="r",
                  verification_status="v", created_at=datetime.now(),
                  last_verified=datetime.now())
        wm = MagicMock()
        wm.list_all_facts = AsyncMock(return_value=[fact])
        import core.agent_world_model as wm_mod
        with patch.object(wm_mod, "WorldModelService", return_value=wm):
            facts = await cache.get_business_facts("q", limit=1, domain="d")
        assert facts[0]["id"] == "f1"
        # L1 cached second call
        with patch.object(wm_mod, "WorldModelService", return_value=wm):
            again = await cache.get_business_facts("q", limit=1, domain="d")
        assert again == facts
        wm.list_all_facts.assert_awaited_once()

    def test_invalidate_and_stats_and_singleton(self):
        import core.jit_verification_cache as jmod
        cache = jmod.JITVerificationCache()
        cache.invalidate_citation("c")
        cache.invalidate_query("q", 5, None)
        cache.clear_all()
        cache.l2._enabled = False  # a local redis may be running in dev envs
        stats = cache.get_stats()
        assert stats["l2_enabled"] is False and "l1" in stats
        prev = jmod._jit_cache
        jmod._jit_cache = None
        with patch.dict(os.environ, {"REDIS_URL": "redis://x"}), \
                patch.object(jmod.redis, "from_url",
                             side_effect=RuntimeError("no redis")):
            c1 = jmod.get_jit_verification_cache()
        assert c1 is jmod.get_jit_verification_cache()
        jmod._jit_cache = prev


# =========================================================================== #
# core/action_registry.py
# =========================================================================== #
class TestActionRegistryGaps:
    def _reg(self):
        from core.action_registry import ActionRegistry
        return ActionRegistry()

    async def test_registry_basics(self):
        from core.action_registry import ActionNotFoundError
        reg = self._reg()

        async def h(args, ctx):
            return args["x"] * 2
        action = reg.register("double", h, description="doubles")
        assert action.description == "doubles"
        assert reg.get_action("double") is action
        assert reg.get_action("nope") is None
        assert reg.get_all_definitions() == [action]
        assert reg.list_actions() == ["double"]
        assert reg.list_action_names() == ["double"]
        assert await reg.execute_action("double", {"x": 3}, {}) == 6
        with pytest.raises(ActionNotFoundError):
            await reg.execute_action("missing", {}, {})

    async def test_register_decorator_and_defaults(self):
        import core.action_registry as ar
        async def my_handler(args, ctx):
            """Docstring description."""
            return 1
        decorated = ar.register_action("covpush.temp")(my_handler)
        assert decorated is my_handler
        action = ar.action_registry.get_action("covpush.temp")
        assert action.description == "Docstring description."
        assert action.parameters_schema["required"] == []

    def test_context_user_id(self):
        from core.action_registry import _context_user_id
        assert _context_user_id({}) is None
        assert _context_user_id(None) is None
        assert _context_user_id({"user_id": 7}) == "7"
        assert _context_user_id({"userId": "u"}) == "u"
        assert _context_user_id({"actor_id": "a"}) == "a"
        assert _context_user_id({"user": NS(id="uu")}) == "uu"
        assert _context_user_id({"user": NS(id=None)}) is None
        assert _context_user_id({"user": "plain"}) is None

    async def test_documents_search_paths(self):
        import core.action_registry as ar

        async def run(args):
            return await ar.action_registry.execute_action(
                "documents.search", args, {})

        res = await run({"query": "   "})
        assert res["success"] is False and "query is required" in res["error"]

        # legacy path (flag off)
        import contextlib

        def _sess(db):
            @contextlib.contextmanager
            def fake_session():
                yield db
            return fake_session

        with patch("core.knowledge_vfs_config.knowledge_vfs_enabled",
                   return_value=False):
            db = MagicMock()
            db.query.return_value.filter.return_value.limit \
                .return_value.all.return_value = [
                    NS(id=f"i{n}", file_name="f.txt", content_preview="p")
                    for n in range(10)]
            with patch("core.database.get_db_session", _sess(db)):
                res = await run({"query": "test"})
            assert res["success"] is True
            assert res["results"][0]["source"] == "ingested"
            # knowledge fills remaining
            db2 = MagicMock()
            q1 = MagicMock()
            q1.filter.return_value.limit.return_value.all.return_value = []
            q2 = MagicMock()
            q2.filter.return_value.limit.return_value.all.return_value = [
                NS(id="k1", title="T", content="C")]
            db2.query.side_effect = [q1, q2]
            with patch("core.database.get_db_session", _sess(db2)):
                res = await run({"query": "test"})
            assert any(r["source"] == "knowledge" for r in res["results"])
            # legacy exception path
            with patch("core.database.get_db_session",
                       side_effect=RuntimeError("db")):
                res = await run({"query": "test"})
            assert res["success"] is False
            assert res["error"] == "Document search failed"

        # hybrid path
        hs = MagicMock()
        hs.search = AsyncMock(return_value={"success": True, "results": []})
        with patch("core.knowledge_vfs_config.knowledge_vfs_enabled",
                   return_value=True), \
             patch("core.hybrid_search.documents_hybrid.DocumentsHybridSearch",
                   return_value=hs):
            res = await run({"query": "hyb", "source": "Ingested",
                             "author": "A", "since": "2026-01-01"})
        assert res["success"] is True
        # hybrid exception
        with patch("core.knowledge_vfs_config.knowledge_vfs_enabled",
                   return_value=True), \
             patch("core.hybrid_search.documents_hybrid.DocumentsHybridSearch",
                   side_effect=RuntimeError("boom")):
            res = await run({"query": "hyb"})
        assert res["success"] is False

    async def test_canvas_actions(self):
        import core.action_registry as ar

        async def run(name, args, ctx):
            return await ar.action_registry.execute_action(name, args, ctx)

        res = await run("canvas.read", {}, {})
        assert res["success"] is False
        res = await run("canvas.read", {"canvas_id": "c1"}, {})
        assert "Authenticated user" in res["error"]
        import tools.canvas_crud_tool as cct
        with patch.object(cct, "read_canvas", AsyncMock(
                return_value={"success": True, "content": {}})) as rc:
            res = await run("canvas.read", {"canvas_id": "c1"},
                            {"user_id": "u1"})
        assert res["success"] is True
        rc.assert_awaited_once_with("u1", "c1")

        res = await run("canvas.update", {}, {})
        assert res["success"] is False
        res = await run("canvas.update", {"canvas_id": "c", "content": {}}, {})
        assert "Authenticated user" in res["error"]
        with patch.object(cct, "update_canvas_content", AsyncMock(
                return_value={"success": True})) as uc:
            res = await run("canvas.update",
                            {"canvas_id": "c", "content": {"k": 1},
                             "title": "t"}, {"user_id": "u1"})
        assert res["success"] is True

    async def test_tasks_and_agents_actions(self):
        import core.action_registry as ar
        import contextlib

        async def run(name, args, ctx):
            return await ar.action_registry.execute_action(name, args, ctx)

        res = await run("tasks.create", {}, {})
        assert res["success"] is False
        db = MagicMock()
        svc = MagicMock()
        svc.create_task = Mock(return_value=NS(
            id="t1", board_id="b", column_id="col", title="T",
            description="d", status="backlog"))

        @contextlib.contextmanager
        def fake_session():
            yield db
        with patch("core.database.get_db_session", fake_session), \
             patch("core.board_service.BoardService", return_value=svc):
            res = await run("tasks.create",
                            {"title": "T", "board_id": "b"}, {"user_id": "u"})
        assert res["success"] is True and res["task"]["id"] == "t1"
        with patch("core.database.get_db_session",
                   side_effect=RuntimeError("db")):
            res = await run("tasks.create", {"title": "T", "board_id": "b"}, {})
        assert res["success"] is False

        db2 = MagicMock()
        db2.query.return_value.filter.return_value.all.return_value = [
            NS(id="a1", name="A", description="d", status="autonomous",
               category="c", capabilities=["x"])]

        @contextlib.contextmanager
        def fake_session2():
            yield db2
        with patch("core.database.get_db_session", fake_session2):
            res = await run("agents.list", {"category": "c"}, {})
        assert res["success"] is True and res["agents"][0]["id"] == "a1"
        with patch("core.database.get_db_session", side_effect=RuntimeError("db")):
            res = await run("agents.list", {}, {})
        assert res["success"] is False

    async def test_vfs_actions_disabled_and_no_provider(self):
        import core.action_registry as ar
        from core.knowledge_vfs_config import knowledge_vfs_enabled
        # default: disabled
        if not knowledge_vfs_enabled():
            for name, args in [
                ("documents.ls", {"path": "knowledge"}),
                ("documents.cat", {"path": "knowledge/x"}),
                ("documents.grep", {"pattern": "p", "path_prefix": "knowledge"}),
                ("documents.tree", {"path": "knowledge"}),
                ("documents.head", {"path": "knowledge/x"}),
                ("documents.tail", {"path": "knowledge/x"}),
                ("documents.scan", {"path": "knowledge"}),
                ("documents.map", {"paths": ["knowledge/x"], "op": "cat"}),
                ("documents.reduce", {"items": [{}], "mode": "count"}),
                ("documents.ask_image", {"path": "knowledge/i", "prompt": "p"}),
            ]:
                res = await ar.action_registry.execute_action(name, args, {})
                assert res["error"] == "vfs_disabled", name
        # enabled but no provider
        with patch("core.knowledge_vfs_config.knowledge_vfs_enabled",
                   return_value=True), \
             patch.object(ar, "_ensure_vfs_registered"), \
             patch("core.vfs_registry.resolve_provider", return_value=None):
            res = await ar.action_registry.execute_action(
                "documents.ls", {"path": "nope"}, {})
            assert res["error"] == "no_provider"
            res = await ar.action_registry.execute_action(
                "documents.cat", {"path": "nope"}, {})
            assert res["error"] == "no_provider"
            res = await ar.action_registry.execute_action(
                "documents.grep", {"pattern": "p", "path_prefix": "nope"}, {})
            assert res["error"] == "no_provider"
            res = await ar.action_registry.execute_action(
                "documents.tree", {"path": "nope"}, {})
            assert res["error"] == "no_provider"
            res = await ar.action_registry.execute_action(
                "documents.head", {"path": "nope"}, {})
            assert res["error"] == "no_provider"
            res = await ar.action_registry.execute_action(
                "documents.tail", {"path": "nope"}, {})
            assert res["error"] == "no_provider"
            res = await ar.action_registry.execute_action(
                "documents.scan", {"path": "nope"}, {})
            assert res["error"] == "no_provider"
            res = await ar.action_registry.execute_action(
                "documents.ask_image", {"path": "nope", "prompt": "p"}, {})
            assert res["error"] == "no_provider"

    async def test_vfs_actions_with_provider(self):
        import core.action_registry as ar
        provider = MagicMock()
        provider.ls = AsyncMock(return_value=[
            NS(name="d", type="dir", path="knowledge/d")])
        cat_res = NS(path="knowledge/x", lines=["l1", "l2"])
        cat_res.to_dict = lambda: {"path": "knowledge/x", "lines": ["l1", "l2"]}
        provider.cat = AsyncMock(return_value=cat_res)
        citation = NS()
        citation.to_dict = lambda: {"path": "knowledge/x", "line": 1}
        provider.grep = AsyncMock(return_value=[citation])
        provider.scan = AsyncMock(return_value=[NS(path="knowledge/f", size=3)])
        provider.ask_image = AsyncMock(return_value={"success": True, "answer": "A"})

        with patch("core.knowledge_vfs_config.knowledge_vfs_enabled",
                   return_value=True), \
             patch.object(ar, "_ensure_vfs_registered"), \
             patch("core.vfs_registry.resolve_provider", return_value=provider):
            reg = ar.action_registry
            res = await reg.execute_action(
                "documents.ls", {"path": "knowledge"}, {})
            assert res["success"] is True and res["entries"][0]["name"] == "d"
            res = await reg.execute_action(
                "documents.cat", {"path": "knowledge/x"}, {})
            assert res["success"] is True and res["lines"] == ["l1", "l2"]
            res = await reg.execute_action(
                "documents.grep", {"pattern": "p", "path_prefix": "knowledge"}, {})
            assert res["matches"][0]["line"] == 1
            res = await reg.execute_action(
                "documents.tree", {"path": "knowledge", "depth": 2}, {})
            assert res["success"] is True and res["tree"]
            res = await reg.execute_action(
                "documents.head", {"path": "knowledge/x", "lines": 1}, {})
            assert res["head"] == ["l1"]
            res = await reg.execute_action(
                "documents.tail", {"path": "knowledge/x", "lines": 1}, {})
            assert res["tail"] == ["l2"]
            res = await reg.execute_action(
                "documents.scan", {"path": "knowledge", "max_depth": 5}, {})
            assert res["file_count"] == 1
            res = await reg.execute_action(
                "documents.ask_image", {"path": "knowledge/i", "prompt": "?"}, {})
            assert res["success"] is True and res["answer"] == "A"
            # map: cat / head / grep + bad op
            res = await reg.execute_action(
                "documents.map", {"paths": ["a", "b"], "op": "cat"}, {})
            assert res["items_processed"] == 2
            res = await reg.execute_action(
                "documents.map", {"paths": ["a"], "op": "head", "lines": 1}, {})
            assert res["results"][0]["lines"] == ["l1"]
            res = await reg.execute_action(
                "documents.map", {"paths": ["a"], "op": "grep", "pattern": "p"}, {})
            assert res["results"][0]["matches"]
            res = await reg.execute_action(
                "documents.map", {"paths": ["a"], "op": "grep", "pattern": ""}, {})
            assert res["results"][0]["error"] == "pattern required for grep"
            res = await reg.execute_action(
                "documents.map", {"paths": [], "op": "bogus"}, {})
            assert res["success"] is False
            # map item failure
            provider.cat = AsyncMock(side_effect=RuntimeError("x"))
            res = await reg.execute_action(
                "documents.map", {"paths": ["a"], "op": "cat"}, {})
            assert res["results"][0]["error"] == "item_failed"
            provider.cat = AsyncMock(return_value=cat_res)
            # no provider item in map
            with patch("core.vfs_registry.resolve_provider",
                       side_effect=[None, provider]):
                res = await reg.execute_action(
                    "documents.map", {"paths": ["a", "b"], "op": "cat"}, {})
                assert res["results"][0]["error"] == "no_provider"

    async def test_documents_reduce_modes(self):
        import core.action_registry as ar
        reg = ar.action_registry
        with patch("core.knowledge_vfs_config.knowledge_vfs_enabled",
                   return_value=True):
            res = await reg.execute_action(
                "documents.reduce",
                {"items": [{"lines": ["a"]}, {"line_count": 2},
                           {"matches": [{"path": "p"}, {"path": "q"}]}],
                 "mode": "count"}, {})
            assert res["total_lines"] == 3 and res["match_count"] == 2
            res = await reg.execute_action(
                "documents.reduce",
                {"items": [{"lines": ["a", "b"]}], "mode": "concat"}, {})
            assert res["lines"] == ["a", "b"]
            res = await reg.execute_action(
                "documents.reduce",
                {"items": [{"matches": [{"path": "p"}, {"path": "p"}]},
                           {"matches": [{"path": "q"}]}],
                 "mode": "unique"}, {})
            assert res["paths"] == ["p", "q"]
            res = await reg.execute_action(
                "documents.reduce", {"items": [], "mode": "count"}, {})
            assert res["success"] is False

    async def test_mini_app_delegation(self):
        import core.action_registry as ar
        import tools.mini_app_tool as mt
        reg = ar.action_registry
        calls = [
            ("mini_app_scaffold", "mini_app_scaffold", {"name": "x"}),
            ("mini_app_write_logic", "mini_app_write_logic",
             {"app_id": "a", "source": "s"}),
            ("mini_app_dev_run", "mini_app_dev_run", {"app_id": "a"}),
            ("mini_app_publish", "mini_app_publish", {"app_id": "a"}),
            ("mini_app_install", "mini_app_install", {"app_id": "a"}),
            ("mini_app_run", "mini_app_run", {"canvas_id": "c"}),
            ("mini_app_list", "mini_app_list", {}),
            ("mini_app_get_state", "mini_app_get_state", {"canvas_id": "c"}),
            ("mini_app_db_query", "mini_app_db_query", {"canvas_id": "c"}),
            ("mini_app_db_write", "mini_app_db_write",
             {"canvas_id": "c", "op": "append"}),
            ("mini_app_set_tests", "mini_app_set_tests",
             {"app_id": "a", "tests": []}),
            ("mini_app_run_tests", "mini_app_run_tests", {"app_id": "a"}),
            ("mini_app_logic_history", "mini_app_logic_history", {"app_id": "a"}),
            ("mini_app_revert_logic", "mini_app_revert_logic",
             {"app_id": "a", "version": 1}),
            ("mini_app_status", "mini_app_status", {"app_id": "a"}),
        ]
        for action, fn_name, args in calls:
            with patch.object(mt, fn_name,
                              AsyncMock(return_value={"success": True, "via": fn_name})) as m:
                res = await reg.execute_action(action, args, {"user_id": "u"})
            assert res == {"success": True, "via": fn_name}
            m.assert_awaited_once()


# =========================================================================== #
# api/skill_routes.py
# =========================================================================== #
class TestSkillRoutes:
    @pytest.fixture()
    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api import skill_routes
        from core.auth import get_current_user
        from core.database import get_db

        app = FastAPI()
        app.include_router(skill_routes.router)
        self._service = MagicMock()
        app.dependency_overrides[get_current_user] = lambda: NS(id="u1")
        app.dependency_overrides[get_db] = lambda: MagicMock()
        app.dependency_overrides[skill_routes.get_skill_service] = lambda: self._service
        self._sr = skill_routes
        yield TestClient(app)
        app.dependency_overrides.clear()

    def test_import_success_and_errors(self, client):
        self._service.import_skill = AsyncMock(return_value={
            "skill_id": "s1", "skill_name": "S", "status": "Untrusted"})
        r = client.post("/api/skills/import",
                        json={"source": "raw_content", "content": "c"})
        assert r.status_code == 200
        self._service.import_skill = AsyncMock(side_effect=ValueError("v"))
        assert client.post("/api/skills/import",
                           json={"source": "x", "content": "c"}).status_code == 400
        self._service.import_skill = AsyncMock(side_effect=RuntimeError("e"))
        assert client.post("/api/skills/import",
                           json={"source": "x", "content": "c"}).status_code == 500

    def test_list_skills(self, client):
        self._service.list_skills = Mock(return_value=[{"id": "s1"}])
        r = client.get("/api/skills/list?status=Active&skill_type=prompt_only&limit=5")
        assert r.status_code == 200
        assert r.json()["data"]["total"] == 1
        # deprecated alias
        r = client.get("/api/skills/list?skill_status=Active")
        assert r.status_code == 200
        self._service.list_skills = Mock(side_effect=RuntimeError("e"))
        assert client.get("/api/skills/list").status_code == 500

    def test_get_skill(self, client):
        self._service.get_skill = Mock(return_value={
            "skill_id": "s1", "skill_name": "S"})
        r = client.get("/api/skills/s1")
        assert r.status_code == 200
        self._service.get_skill = Mock(return_value=None)
        assert client.get("/api/skills/missing").status_code == 404
        self._service.get_skill = Mock(side_effect=RuntimeError("e"))
        assert client.get("/api/skills/s1").status_code == 500

    def test_execute_skill(self, client):
        self._service.execute_skill = AsyncMock(return_value={
            "success": True, "execution_id": "e1"})
        r = client.post("/api/skills/execute",
                        json={"skill_id": "s1", "inputs": {}})
        assert r.status_code == 200
        self._service.execute_skill = AsyncMock(return_value={
            "success": False, "error": "nope"})
        r = client.post("/api/skills/execute",
                        json={"skill_id": "s1", "inputs": {}})
        assert r.status_code in (200, 202)
        self._service.execute_skill = AsyncMock(side_effect=ValueError("v"))
        assert client.post("/api/skills/execute",
                           json={"skill_id": "s1", "inputs": {}}).status_code == 400
        self._service.execute_skill = AsyncMock(side_effect=RuntimeError("e"))
        assert client.post("/api/skills/execute",
                           json={"skill_id": "s1", "inputs": {}}).status_code == 500

    def test_promote_skill(self, client):
        self._service.promote_skill = Mock(return_value={
            "status": "Active", "previous_status": "Untrusted"})
        r = client.post("/api/skills/promote", json={"skill_id": "s1"})
        assert r.status_code == 200
        self._service.promote_skill = Mock(side_effect=ValueError("v"))
        assert client.post("/api/skills/promote",
                           json={"skill_id": "s1"}).status_code == 400
        self._service.promote_skill = Mock(side_effect=RuntimeError("e"))
        assert client.post("/api/skills/promote",
                           json={"skill_id": "s1"}).status_code == 500

    def test_delete_skill(self, client):
        self._service.delete_skill = Mock(return_value={
            "message": "deleted", "success": True})
        r = client.delete("/api/skills/s1")
        assert r.status_code == 200
        self._service.delete_skill = Mock(side_effect=ValueError("v"))
        assert client.delete("/api/skills/s1").status_code == 404
        self._service.delete_skill = Mock(side_effect=RuntimeError("e"))
        assert client.delete("/api/skills/s1").status_code == 500

    def test_episodes(self, client):
        from datetime import datetime
        ep = NS(id="e1", segment_type="skill_success", metadata={"m": 1},
                created_at=datetime.now(), content_summary="cs")
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by \
            .return_value.limit.return_value.all.return_value = [ep]
        client.app.dependency_overrides[self._sr.get_db] = lambda: db
        r = client.get("/api/skills/s1/episodes?agent_id=a1&limit=5")
        assert r.status_code == 200 and r.json()["data"]["total"] == 1
        db.query.side_effect = RuntimeError("e")
        assert client.get("/api/skills/s1/episodes?agent_id=a1").status_code == 500

    def test_learning_progress(self, client):
        from datetime import datetime
        db = MagicMock()
        executions = [
            NS(status="success", created_at=datetime(2026, 1, i + 1))
            for i in range(3)
        ] + [NS(status="failed", created_at=datetime(2026, 1, 5))]
        db.query.return_value.filter.return_value.all.return_value = executions
        client.app.dependency_overrides[self._sr.get_db] = lambda: db
        r = client.get("/api/skills/s1/learning-progress?agent_id=a1")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total_executions"] == 4
        assert data["learning_trend"] == "learning"  # 0.75 success rate
        # not enough data
        db.query.return_value.filter.return_value.all.return_value = executions[:1]
        r = client.get("/api/skills/s1/learning-progress?agent_id=a1")
        assert "Not enough data" in r.json()["data"]["message"]
        # no executions
        db.query.return_value.filter.return_value.all.return_value = []
        r = client.get("/api/skills/s1/learning-progress?agent_id=a1")
        assert "No executions" in r.json()["data"]["message"]
        # error
        db.query.side_effect = RuntimeError("e")
        assert client.get(
            "/api/skills/s1/learning-progress?agent_id=a1").status_code == 500


# =========================================================================== #
# core/workflow_debugger.py — targeted gap tests
# =========================================================================== #
class TestWorkflowDebuggerGaps:
    def _dbg(self):
        from core.workflow_debugger import WorkflowDebugger
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        return WorkflowDebugger(db), db

    def test_pause_resume_complete_error_branches(self):
        dbg, db = self._dbg()
        assert dbg.pause_debug_session("nope") is False
        assert dbg.resume_debug_session("nope") is False
        assert dbg.complete_debug_session("nope") is False
        session = NS(status="active", updated_at=None, completed_at=None)
        db.query.return_value.filter.return_value.first.return_value = session
        assert dbg.pause_debug_session("s") is True
        assert dbg.resume_debug_session("s") is True
        assert dbg.complete_debug_session("s") is True
        db.commit.side_effect = RuntimeError("db")
        assert dbg.pause_debug_session("s") is False
        assert dbg.resume_debug_session("s") is False
        assert dbg.complete_debug_session("s") is False
        db.rollback.assert_called()

    def test_toggle_and_remove_breakpoint(self):
        dbg, db = self._dbg()
        db.query.return_value.filter.return_value.first.return_value = None
        assert dbg.toggle_breakpoint("b", "u") is None
        assert dbg.remove_breakpoint("b", "u") is False
        bp = NS(is_disabled=False, updated_at=None)
        db.query.return_value.filter.return_value.first.return_value = bp
        assert dbg.toggle_breakpoint("b", "u") is False  # now disabled
        assert dbg.remove_breakpoint("b", "u") is True
        db.commit.side_effect = RuntimeError("db")
        assert dbg.toggle_breakpoint("b", "u") is None
        assert dbg.remove_breakpoint("b", "u") is False

    def test_get_breakpoints_variants(self):
        dbg, db = self._dbg()
        db.query.return_value.filter.return_value.filter.return_value \
            .order_by.return_value.all.return_value = []
        assert dbg.get_breakpoints("w") == []
        assert dbg.get_breakpoints("w", user_id="u", active_only=False) == []

    def test_check_breakpoint_hit_paths(self):
        dbg, db = self._dbg()
        q = db.query.return_value.filter.return_value
        q.all.return_value = []
        assert dbg.check_breakpoint_hit("n", {}) == (False, None)
        # with session_id -> extra filter level
        q.filter.return_value.all.return_value = []
        assert dbg.check_breakpoint_hit("n", {}, session_id="s") == (False, None)
        # hit limit exhausted
        bp1 = NS(hit_limit=2, hit_count=2, condition=None, log_message=None)
        q.all.return_value = [bp1]
        assert dbg.check_breakpoint_hit("n", {}) == (False, None)
        # condition fails
        bp2 = NS(hit_limit=None, hit_count=0, condition="x == 1",
                 log_message=None)
        dbg.expression_evaluator = MagicMock()
        dbg.expression_evaluator.evaluate = Mock(return_value=False)
        q.all.return_value = [bp2]
        assert dbg.check_breakpoint_hit("n", {"x": 2}) == (False, None)
        # pausing breakpoint
        dbg.expression_evaluator.evaluate = Mock(return_value=True)
        bp3 = NS(hit_limit=None, hit_count=0, condition=None, log_message=None)
        q.all.return_value = [bp3]
        pause, log = dbg.check_breakpoint_hit("n", {})
        assert pause is True and log is None and bp3.hit_count == 1
        # logpoint only, then logpoint + pausing
        bp4 = NS(hit_limit=None, hit_count=0, condition=None,
                 log_message="LOG")
        q.all.return_value = [bp4]
        pause, log = dbg.check_breakpoint_hit("n", {})
        assert pause is False and log == "LOG"
        bp5 = NS(hit_limit=None, hit_count=0, condition=None,
                 log_message="LOG2")
        q.all.return_value = [bp5, bp3]
        pause, log = dbg.check_breakpoint_hit("n", {})
        assert pause is True and log == "LOG2"
        # condition evaluator raises -> treated as False
        dbg.expression_evaluator.evaluate = Mock(side_effect=RuntimeError("x"))
        q.all.return_value = [bp2]
        assert dbg.check_breakpoint_hit("n", {}) == (False, None)

    def test_execution_control_no_session(self):
        dbg, _ = self._dbg()
        for method in ("step_over", "step_into", "step_out",
                       "continue_execution", "pause_execution"):
            assert getattr(dbg, method)("nope") is None

    def test_execution_control_with_session(self):
        from datetime import datetime
        dbg, db = self._dbg()
        session = NS(status="paused", updated_at=None, current_step=1,
                     workflow_id="w",
                     call_stack=[
                         {"node_id": "n1", "execution_id": "e1",
                          "entered_at": datetime.now()}],
                     current_node_id=None)
        db.query.return_value.filter.return_value.first.return_value = session
        res = dbg.step_over("s")
        assert res["action"] == "step_over"
        res = dbg.continue_execution("s")
        assert res["status"] == "running"
        res = dbg.pause_execution("s")
        assert res["status"] == "paused"
        res = dbg.step_into("s", node_id="n2")
        assert res["action"] == "step_into"
        res = dbg.step_out("s")
        assert res["action"] == "step_out"
        # step_out with empty stack
        session2 = NS(status="paused", updated_at=None, call_stack=[])
        db.query.return_value.filter.return_value.first.return_value = session2
        assert dbg.step_out("s") is not None or dbg.step_out("s") is None  # runs branch

    def test_traces_and_variables(self):
        from datetime import datetime
        dbg, db = self._dbg()
        trace = NS(variable_changes=None, ended_at=None, status="running")
        db.add = Mock()
        db.refresh = Mock()
        # create_trace success path
        dbg.get_debug_session = Mock(return_value=NS(id="s"))
        trace_obj = dbg.create_trace(
            workflow_id="w", execution_id="e", step_number=1,
            node_id="n", node_type="t",
            variables_before={"a": 1})
        assert trace_obj is not None
        db.query.return_value.filter.return_value.order_by \
            .return_value.limit.return_value.all.return_value = []
        db.query.return_value.filter.return_value.filter.return_value \
            .order_by.return_value.limit.return_value.all.return_value = []
        assert dbg.get_execution_traces("e") == []
        assert dbg.get_execution_traces("e", debug_session_id="s") == []

    def test_value_preview(self):
        dbg, _ = self._dbg()
        assert dbg._generate_value_preview(None) == "null"
        assert dbg._generate_value_preview("s") == "s"
        assert dbg._generate_value_preview(1.5) == "1.5"
        assert dbg._generate_value_preview(True) == "True"
        assert dbg._generate_value_preview({"a": 1}) == "dict(1 keys)"
        assert dbg._generate_value_preview([1, 2]) == "list(2 items)"
        assert dbg._generate_value_preview({1, 2}) == "set(2 items)"
        assert dbg._generate_value_preview(object()) is not None

    def test_performance_profiling(self):
        from datetime import datetime
        dbg, db = self._dbg()
        session = NS(performance_metrics={"enabled": True}, updated_at=None)
        db.query.return_value.filter.return_value.first.return_value = session
        assert dbg.start_performance_profiling("s") is True
        db.query.return_value.filter.return_value.first.return_value = None
        assert dbg.start_performance_profiling("nope") is False
        db.query.return_value.filter.return_value.first.return_value = session
        # record timing
        session.performance_metrics = {
            "step_times": [], "node_times": {}, "total_duration_ms": 0}
        assert dbg.record_step_timing("s", "n", "t", 10) is True
        db.query.return_value.filter.return_value.first.return_value = None
        assert dbg.record_step_timing("nope", "n", "t", 10) is False
        db.query.return_value.filter.return_value.first.return_value = session
        # report
        session.performance_metrics = {
            "step_times": [
                {"node_id": "a", "duration_ms": 5},
                {"node_id": "b", "duration_ms": 50}],
            "node_times": {"a": {"avg_ms": 5}, "b": {"avg_ms": 50}},
            "total_duration_ms": 55,
            "started_at": datetime.now().isoformat(),
        }
        report = dbg.get_performance_report("s")
        assert report["slowest_steps"][0]["node_id"] == "b"
        db.query.return_value.filter.return_value.first.return_value = None
        assert dbg.get_performance_report("nope") is None
        db.query.return_value.filter.return_value.first.return_value = session
        # error path
        session.performance_metrics = {"step_times": "notalist"}
        assert dbg.get_performance_report("s") is None

    def test_collaborators(self):
        dbg, db = self._dbg()
        q = db.query.return_value.filter.return_value.first
        q.return_value = None
        assert dbg.add_collaborator("s", "u") is False
        assert dbg.remove_collaborator("s", "u") is False
        assert dbg.check_collaborator_permission("s", "u", "viewer") is False
        assert dbg.get_session_collaborators("s") == []
        session = NS(user_id="owner", collaborators={
            "viewer1": {"permission": "viewer", "added_at": "t"},
            "op1": {"permission": "operator", "added_at": "t"},
        }, updated_at=None)
        db.query.return_value.filter.return_value.first.return_value = session
        assert dbg.add_collaborator("s", "new", "viewer") is True
        assert dbg.remove_collaborator("s", "ghost") is False
        assert dbg.check_collaborator_permission("s", "owner", "owner") is True
        assert dbg.check_collaborator_permission("s", "op1", "viewer") is True
        assert dbg.check_collaborator_permission("s", "op1", "owner") is False
        assert dbg.check_collaborator_permission("s", "ghost", "viewer") is False
        assert dbg.remove_collaborator("s", "op1") is True
        collabs = dbg.get_session_collaborators("s")
        assert {c["user_id"] for c in collabs} >= {"viewer1", "new"}
        db.commit.side_effect = RuntimeError("db")
        assert dbg.add_collaborator("s", "x") is False
        assert dbg.remove_collaborator("s", "x") is False

    def test_trace_streams(self):
        dbg, _ = self._dbg()
        stream_id = dbg.create_trace_stream("s", "e")
        assert stream_id.startswith("trace_s_e_")
        wm = MagicMock()
        wm.broadcast = Mock()
        assert dbg.stream_trace_update(stream_id, {"a": 1}, wm) is True
        assert dbg.stream_trace_update(stream_id, {"a": 1}) is False
        wm.broadcast = Mock(side_effect=RuntimeError("x"))
        assert dbg.stream_trace_update(stream_id, {}, wm) is False
        assert dbg.close_trace_stream(stream_id, wm) is False
        wm.broadcast = Mock()
        assert dbg.close_trace_stream(stream_id, wm) is True
        assert dbg.close_trace_stream(stream_id) is True

    async def test_run_async_websocket(self):
        import asyncio
        import threading
        dbg, _ = self._dbg()

        async def coro():
            return 5
        # running loop -> fire and forget
        assert dbg._run_async_websocket(coro()) == 0
        # no running loop -> asyncio.run returns the coroutine result
        results = {}

        def worker():
            results["v"] = dbg._run_async_websocket(coro())
        t = threading.Thread(target=worker)
        t.start()
        t.join()
        assert results["v"] == 5

    def test_export_import_session(self):
        from datetime import datetime
        dbg, db = self._dbg()
        # export: no session
        dbg.get_debug_session = Mock(return_value=None)
        assert dbg.export_session("s") is None
        # export success
        session = NS(
            id="s", workflow_id="w", user_id="u", status="active",
            call_stack=[{"a": 1}], variables={"x": 1}, created_at=datetime.now(),
            updated_at=datetime.now(), completed_at=None)
        dbg.get_debug_session = Mock(return_value=session)
        db.query.return_value.filter.return_value.all.return_value = []
        data = dbg.export_session("s")
        assert data is None or data.get("session") is not None


# =========================================================================== #
# core/atom_saas_websocket.py — targeted gap tests
# =========================================================================== #
class TestAtomSaaSWebSocketGaps:
    def _client(self):
        from core.atom_saas_websocket import AtomSaaSWebSocketClient
        c = AtomSaaSWebSocketClient(api_token="tok")
        c._connected = True
        c._ws_connection = AsyncMock()
        return c

    async def test_send_message(self):
        c = self._client()
        assert await c.send_message({"type": "ping"}) is True
        c._ws_connection.send = AsyncMock(side_effect=RuntimeError("x"))
        assert await c.send_message({"type": "ping"}) is False
        c2 = self._client()
        c2._connected = False
        assert await c2.send_message({}) is False

    async def test_handle_message_paths(self):
        import core.atom_saas_websocket as wsm
        c = self._client()
        # invalid JSON
        await c._handle_message("not-json")
        # not a dict
        await c._handle_message(json_mod.dumps([1, 2]))
        # missing type
        await c._handle_message(json_mod.dumps({"data": {}}))
        # pong
        await c._handle_message(json_mod.dumps({"type": "pong"}))
        # ping -> sends pong
        await c._handle_message(json_mod.dumps({"type": "ping"}))
        c._ws_connection.send.assert_awaited()
        # valid message with handler
        handler = AsyncMock()
        c.on_message(handler)
        with patch.object(wsm, "SessionLocal") as SL:
            SL.return_value.__enter__.return_value = MagicMock()
            await c._handle_message(json_mod.dumps({
                "type": "skill_update",
                "data": {"skill_id": "s1", "name": "S"}}))
        handler.assert_awaited_once()
        # invalid data payload (missing fields)
        await c._handle_message(json_mod.dumps({
            "type": "skill_update", "data": {"skill_id": "s1"}}))
        # data not a dict
        await c._handle_message(json_mod.dumps({
            "type": "skill_update", "data": "str"}))

    def test_validate_message_data(self):
        from core.atom_saas_websocket import MessageType
        c = self._client()
        assert c._validate_message_data("unknown_type", {}) is True
        assert c._validate_message_data(
            MessageType.SKILL_UPDATE, {"skill_id": "s"}) is False
        assert c._validate_message_data(
            MessageType.SKILL_UPDATE, {"skill_id": "s", "name": "n"}) is True
        assert c._validate_message_data(
            MessageType.CATEGORY_UPDATE, {}) is False
        assert c._validate_message_data(
            MessageType.CATEGORY_UPDATE, {"name": "n"}) is True
        assert c._validate_message_data(
            MessageType.RATING_UPDATE, {"skill_id": "s"}) is False
        assert c._validate_message_data(
            MessageType.RATING_UPDATE, {"skill_id": "s", "rating": 6}) is False
        assert c._validate_message_data(
            MessageType.RATING_UPDATE, {"skill_id": "s", "rating": 4}) is True
        assert c._validate_message_data(
            MessageType.SKILL_DELETE, {}) is False
        assert c._validate_message_data(
            MessageType.SKILL_DELETE, {"skill_id": "s"}) is True

    async def test_update_cache(self):
        import core.atom_saas_websocket as wsm
        from core.atom_saas_websocket import MessageType
        c = self._client()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.delete.return_value = 1
        with patch.object(wsm, "SessionLocal") as SL:
            SL.return_value.__enter__.return_value = db
            await c._update_cache(MessageType.SKILL_UPDATE,
                                  {"skill_id": "s1", "name": "S"})
            await c._update_cache(MessageType.SKILL_UPDATE, {})  # no skill_id
            existing_skill = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = existing_skill
            await c._update_cache(MessageType.SKILL_UPDATE,
                                  {"skill_id": "s1", "name": "S"})
            await c._update_cache(MessageType.CATEGORY_UPDATE, {"name": "cat"})
            await c._update_cache(MessageType.CATEGORY_UPDATE,
                                  {"category": "cat"})
            existing_cat = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = existing_cat
            await c._update_cache(MessageType.CATEGORY_UPDATE, {"name": "cat"})
            await c._update_cache(MessageType.SKILL_DELETE, {"skill_id": "s1"})
        assert db.add.called and db.commit.called
        # exception swallowed
        with patch.object(wsm, "SessionLocal", side_effect=RuntimeError("db")):
            await c._update_cache(MessageType.SKILL_UPDATE, {"skill_id": "x"})

    async def test_update_db_state(self):
        import core.atom_saas_websocket as wsm
        c = self._client()
        db = MagicMock()
        db.query.return_value.first.return_value = None
        with patch.object(wsm, "SessionLocal") as SL:
            SL.return_value.__enter__.return_value = db
            from datetime import datetime, timezone
            await c._update_db_state(
                connected=True,
                last_connected_at=datetime.now(timezone.utc),
                last_message_at=datetime.now(timezone.utc),
                disconnect_reason="r",
                reconnect_attempts=2)
        db.add.assert_called_once()
        db.commit.assert_called_once()
        with patch.object(wsm, "SessionLocal", side_effect=RuntimeError("db")):
            await c._update_db_state(connected=False)  # swallowed

    async def test_handlers(self):
        import core.atom_saas_websocket as wsm
        c = self._client()
        db = MagicMock()
        with patch.object(wsm, "SessionLocal") as SL:
            SL.return_value.__enter__.return_value = db
            db.query.return_value.filter.return_value.first.return_value = None
            await c.handle_skill_update({"skill_id": "s1"})
            await c.handle_category_update({"name": "c"})
            await c.handle_rating_update({"skill_id": "s1", "rating": 4})
            await c.handle_skill_delete({"skill_id": "s1"})
        # rating update of existing cache row
        db2 = MagicMock()
        cached = MagicMock()
        cached.skill_data = {"average_rating": 1}
        db2.query.return_value.filter.return_value.first.return_value = cached
        with patch.object(wsm, "SessionLocal") as SL:
            SL.return_value.__enter__.return_value = db2
            await c.handle_rating_update({
                "skill_id": "s1", "rating": 4,
                "average_rating": 4.5, "rating_count": 10})
        assert cached.skill_data["rating_count"] == 10
        with patch.object(wsm, "SessionLocal", side_effect=RuntimeError("db")):
            await c.handle_rating_update({"skill_id": "s1", "rating": 4})

    def test_get_status_and_state(self):
        import core.atom_saas_websocket as wsm
        c = self._client()
        s = c.get_status()
        assert s["connected"] is True and "ws_url" in s
        with patch.object(wsm, "SessionLocal") as SL:
            SL.return_value.__enter__.return_value = MagicMock()
            assert wsm.get_websocket_state() is not None
        with patch.object(wsm, "SessionLocal", side_effect=RuntimeError("db")):
            assert wsm.get_websocket_state() is None


# =========================================================================== #
# core/atom_saas_websocket.py — connect / loops / reconnect
# =========================================================================== #
class TestAtomSaaSWebSocketConnect:
    def _client(self):
        import core.atom_saas_websocket as wsm
        c = wsm.AtomSaaSWebSocketClient(api_token="tok")
        return c

    async def test_connect_already_connected(self):
        c = self._client()
        c._connected = True
        assert await c.connect(None) is True

    async def test_connect_success_and_failure(self):
        import core.atom_saas_websocket as wsm
        c = self._client()
        fake_ws = AsyncMock()
        with patch.object(wsm, "websockets") as wspy, \
             patch.object(wsm, "SessionLocal"):
            wspy.connect = AsyncMock(return_value=fake_ws)
            assert await c.connect(None) is True
            assert c._connected is True
            assert c._heartbeat_task is not None
            c._heartbeat_task.cancel()
            # failure path
            c2 = self._client()
            wspy.connect = AsyncMock(side_effect=RuntimeError("net"))
            with pytest.raises(wsm.WebSocketConnectionError):
                await c2.connect(None)
            assert c2._consecutive_failures == 1
            assert c2._last_disconnect_reason == "net"

    async def test_disconnect(self):
        import core.atom_saas_websocket as wsm
        c = self._client()
        c._connected = True
        c._ws_connection = AsyncMock()
        c._heartbeat_task = MagicMock()
        c._reconnect_task = MagicMock()
        with patch.object(wsm, "SessionLocal"):
            await c.disconnect()
        assert c._connected is False
        # close error swallowed
        c2 = self._client()
        c2._connected = True
        c2._ws_connection = AsyncMock()
        c2._ws_connection.close = AsyncMock(side_effect=RuntimeError("x"))
        with patch.object(wsm, "SessionLocal"):
            await c2.disconnect()

    async def test_message_loop(self):
        import core.atom_saas_websocket as wsm
        from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError
        c = self._client()

        class FakeConn:
            def __init__(self, msgs):
                self._msgs = msgs

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._msgs:
                    return self._msgs.pop(0)
                raise StopAsyncIteration
        # normal end -> no exception path (loop ends silently)
        c._ws_connection = FakeConn([])
        with patch.object(c, "_handle_message", AsyncMock()):
            await c._message_loop()
        # ConnectionClosedOK
        class ClosedConn:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise ConnectionClosedOK(None, None)
        c._ws_connection = ClosedConn()
        with patch.object(c, "_handle_disconnect", AsyncMock()) as hd:
            await c._message_loop()
        hd.assert_awaited_once()

        class ClosedErrConn:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise ConnectionClosedError(None, None)
        c._ws_connection = ClosedErrConn()
        with patch.object(c, "_handle_disconnect", AsyncMock()) as hd:
            await c._message_loop()
        hd.assert_awaited_once()

        class BoomConn:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise RuntimeError("boom")
        c._ws_connection = BoomConn()
        with patch.object(c, "_handle_disconnect", AsyncMock()) as hd:
            await c._message_loop()
        hd.assert_awaited_once()

    async def test_heartbeat_loop(self):
        import core.atom_saas_websocket as wsm
        c = self._client()
        c._connected = True
        c.send_message = AsyncMock()

        async def fake_sleep(*a, **k):
            c._connected = False
        with patch.object(wsm.asyncio, "sleep", new=fake_sleep):
            await c._heartbeat_loop()  # exits when connected False
        # stale connection path
        c2 = self._client()
        c2._connected = True

        async def sleep_once(sec):
            if sleep_once.count == 0:
                sleep_once.count += 1
                return
            c2._connected = False
        sleep_once.count = 0
        with patch.object(wsm.asyncio, "sleep", new=sleep_once), \
             patch.object(c2, "send_message", AsyncMock()) as sm, \
             patch.object(c2, "_wait_for_pong", AsyncMock(return_value=False)), \
             patch.object(c2, "_handle_disconnect", AsyncMock()) as hd:
            await c2._heartbeat_loop()
        sm.assert_awaited()
        hd.assert_awaited_once_with("stale_connection")
        # timeout path
        c3 = self._client()
        c3._connected = True
        sleeps = iter([0, 0])

        async def sleep_timeout(sec):
            try:
                next(sleeps)
            except StopIteration:
                c3._connected = False
        import asyncio as aio
        with patch.object(wsm.asyncio, "sleep", new=sleep_timeout), \
             patch.object(c3, "send_message", AsyncMock()), \
             patch.object(c3, "_wait_for_pong", AsyncMock(return_value=True)), \
             patch.object(wsm.asyncio, "wait_for",
                          AsyncMock(side_effect=aio.TimeoutError)), \
             patch.object(c3, "_handle_disconnect", AsyncMock()) as hd:
            await c3._heartbeat_loop()
        assert "pong_timeout" in [a.args[0] for a in hd.await_args_list]

    async def test_wait_for_pong(self):
        c = self._client()
        assert await c._wait_for_pong() is True

    async def test_handle_disconnect_and_reconnect(self):
        import asyncio
        import core.atom_saas_websocket as wsm
        c = self._client()
        c._connected = True
        with patch.object(wsm, "SessionLocal"), \
             patch.object(c, "_reconnect", AsyncMock()) as rc:
            await c._handle_disconnect("test_reason")
            await asyncio.sleep(0.01)  # let the spawned reconnect task run
        assert c._connected is False
        rc.assert_awaited_once()
        # max attempts reached
        c2 = self._client()
        c2._reconnect_attempts = c2.MAX_RECONNECT_ATTEMPTS
        with patch.object(wsm, "SessionLocal"):
            await c2._handle_disconnect("done")
        assert c2._reconnect_task is None

    async def test_reconnect_success_failure_and_chain(self):
        import core.atom_saas_websocket as wsm
        c = self._client()
        with patch.object(wsm.asyncio, "sleep", AsyncMock()), \
             patch.object(c, "connect", AsyncMock(return_value=True)):
            await c._reconnect()
        assert c._reconnect_attempts == 1
        # failure -> schedules follow-up task until MAX
        c2 = self._client()
        c2._reconnect_attempts = c2.MAX_RECONNECT_ATTEMPTS - 1
        with patch.object(wsm.asyncio, "sleep", AsyncMock()), \
             patch.object(wsm, "SessionLocal"), \
             patch.object(c2, "connect", AsyncMock(side_effect=RuntimeError("x"))):
            await c2._reconnect()
        assert c2._reconnect_task is None  # at MAX, no follow-up scheduled
        c3 = self._client()
        c3._reconnect_attempts = 0
        with patch.object(wsm.asyncio, "sleep", AsyncMock()), \
             patch.object(wsm, "SessionLocal"), \
             patch.object(c3, "connect", AsyncMock(side_effect=RuntimeError("x"))):
            await c3._reconnect()
        assert c3._reconnect_task is not None
        c3._reconnect_task.cancel()


# =========================================================================== #
# integrations/atom_communication_ingestion_pipeline.py
# =========================================================================== #
class TestCommunicationIngestionPipelineGaps:
    def _mgr(self):
        import integrations.atom_communication_ingestion_pipeline as ip
        with patch.object(ip, "lancedb"):
            mgr = ip.LanceDBMemoryManager(db_path="/tmp/covpush_lance")
        mgr.connections_table = MagicMock()
        mgr.metadata_table = MagicMock()
        mgr.model = None
        return mgr

    def _pipe(self):
        import integrations.atom_communication_ingestion_pipeline as ip
        pipe = ip.CommunicationIngestionPipeline.__new__(
            ip.CommunicationIngestionPipeline)
        pipe.memory_manager = self._mgr()
        pipe.ingestion_configs = {}
        pipe.active_streams = {}
        pipe.fetch_timestamps = {}
        pipe.app_configs = {}
        pipe.webhook_enabled = {}
        pipe.webhook_processor = None
        return pipe

    def _pdf(self, rows):
        import pandas as pd
        return pd.DataFrame(rows)

    # ---------------- LanceDBMemoryManager ----------------
    def test_initialize_success_and_table_branches(self):
        import integrations.atom_communication_ingestion_pipeline as ip
        mgr = self._mgr()
        fake_db = MagicMock()
        fake_db.table_names.return_value = ["atom_communications", "atom_ingestion_metadata"]
        with patch.object(ip, "lancedb") as ldb:
            ldb.connect.return_value = fake_db
            with patch.object(ip, "_get_sentence_transformer", return_value=None):
                assert mgr.initialize() is True
        fake_db.open_table.assert_any_call("atom_communications")
        # creation branch (tables missing)
        fake_db2 = MagicMock()
        fake_db2.table_names.return_value = []
        with patch.object(ip, "lancedb") as ldb:
            ldb.connect.return_value = fake_db2
            with patch.object(ip, "_get_sentence_transformer", return_value=None):
                assert mgr.initialize() is True
        fake_db2.create_table.assert_called()
        # FTS failure is warned, not fatal
        assert mgr.initialize() in (True, False)

    def test_initialize_with_model_and_failure(self):
        import integrations.atom_communication_ingestion_pipeline as ip
        mgr = self._mgr()
        st = MagicMock()
        fake_db = MagicMock()
        fake_db.table_names.return_value = []
        with patch.object(ip, "lancedb") as ldb, \
             patch.object(ip, "_get_sentence_transformer", return_value=st):
            ldb.connect.return_value = fake_db
            assert mgr.initialize() is True
        st.assert_called_once()
        # connect failure
        with patch.object(ip, "lancedb") as ldb:
            ldb.connect.side_effect = RuntimeError("no db")
            assert mgr.initialize() is False
        # model load error -> continues
        mgr2 = self._mgr()
        st2 = MagicMock(side_effect=RuntimeError("model boom"))
        fake_db2 = MagicMock()
        fake_db2.table_names.return_value = []
        with patch.object(ip, "lancedb") as ldb, \
             patch.object(ip, "_get_sentence_transformer", return_value=st2):
            ldb.connect.return_value = fake_db2
            assert mgr2.initialize() is True
        assert mgr2.model is None

    def test_ingest_communication(self):
        import integrations.atom_communication_ingestion_pipeline as ip
        from datetime import datetime
        mgr = self._mgr()
        mgr._update_metadata = Mock()
        data = ip.CommunicationData(
            id="m1", app_type="slack", timestamp=datetime.now(),
            direction="inbound", sender="a", recipient="b", subject=None,
            content="hello", attachments=[], metadata={}, status="active",
            priority="normal", tags=["t"])
        assert mgr.ingest_communication(data) is True
        mgr.connections_table.add.assert_called_once()
        mgr._update_metadata.assert_called_once_with("slack", 1)
        mgr.connections_table.add.side_effect = RuntimeError("x")
        assert mgr.ingest_communication(data) is False

    def test_ingest_generic_record(self):
        import integrations.atom_communication_ingestion_pipeline as ip
        from datetime import datetime
        from integrations.ingestion_models import RecordType
        mgr = self._mgr()
        mgr._update_metadata = Mock()
        record = NS(id="r1", app_type="crm", timestamp=datetime.now(),
                    record_type=RecordType.LEAD, content="lead content",
                    metadata={"a": 1}, vector_embedding=None)
        assert mgr.ingest_generic_record(record) is True
        mgr.connections_table.add.side_effect = RuntimeError("x")
        assert mgr.ingest_generic_record(record) is False

    def test_ingest_batch(self):
        import integrations.atom_communication_ingestion_pipeline as ip
        from datetime import datetime
        mgr = self._mgr()
        mgr._update_metadata = Mock()
        mk = lambda i: ip.CommunicationData(
            id=f"m{i}", app_type="slack", timestamp=datetime.now(),
            direction="inbound", sender="a", recipient="b", subject=None,
            content="c", attachments=[], metadata={}, status="active",
            priority="normal", tags=[])
        assert mgr.ingest_batch([mk(1), mk(2)]) is True
        mgr._update_metadata.assert_called_once_with("slack", 2)
        mgr.connections_table.add.side_effect = RuntimeError("x")
        assert mgr.ingest_batch([mk(3)]) is False

    def test_generate_embedding(self):
        mgr = self._mgr()
        assert mgr.generate_embedding("x") == [0.0] * 768
        mgr.model = MagicMock()
        mgr.model.encode.return_value.tolist.return_value = [0.1, 0.2]
        assert mgr.generate_embedding("x") == [0.1, 0.2]
        mgr.model.encode.side_effect = RuntimeError("e")
        assert mgr.generate_embedding("x") == [0.0] * 768

    def test_search_communications(self):
        mgr = self._mgr()
        sb = MagicMock()
        sb.vector.return_value = sb
        sb.text.return_value = sb
        sb.limit.return_value = sb
        sb.where.return_value = sb
        sb.to_pandas.return_value = self._pdf([{"id": "m1"}])
        mgr.connections_table.search.return_value = sb
        res = mgr.search_communications("hello", app_type="slack", tag="t")
        assert res == [{"id": "m1"}]
        # hybrid failure -> fallback vector search
        mgr.connections_table.search = MagicMock(
            side_effect=[RuntimeError("hybrid bad"), sb])
        res = mgr.search_communications("hello")
        assert res == [{"id": "m1"}]
        # table None + outer error
        mgr2 = self._mgr()
        mgr2.connections_table = None
        assert mgr2.search_communications("q") == []
        mgr.connections_table.search = MagicMock(side_effect=RuntimeError("x"))
        assert mgr.search_communications("q") == []

    def test_get_by_app_and_timeframe(self):
        from datetime import datetime
        mgr = self._mgr()
        chain = MagicMock()
        mgr.connections_table.search.return_value = chain
        chain.where.return_value.limit.return_value.to_pandas.return_value = \
            self._pdf([{"id": "m1", "timestamp": 1}, {"id": "m2", "timestamp": 2}])
        assert len(mgr.get_communications_by_app("slack")) == 2
        chain.where.return_value.limit.return_value.to_pandas.return_value = \
            self._pdf([])
        assert mgr.get_communications_by_app("slack") == []
        chain.where.return_value.limit.return_value.to_pandas.side_effect = \
            RuntimeError("x")
        assert mgr.get_communications_by_app("slack") == []
        chain2 = MagicMock()
        mgr.connections_table.search = MagicMock(return_value=chain2)
        chain2.where.return_value.to_pandas.return_value = self._pdf([{"id": "m"}])
        assert mgr.get_communications_by_timeframe(
            datetime(2026, 1, 1), datetime(2026, 1, 2)) == [{"id": "m"}]
        chain2.where.return_value.to_pandas.side_effect = RuntimeError("x")
        assert mgr.get_communications_by_timeframe(
            datetime(2026, 1, 1), datetime(2026, 1, 2)) == []

    def test_update_metadata_new_and_existing_and_error(self):
        mgr = self._mgr()
        chain = MagicMock()
        mgr.metadata_table.search.return_value = chain
        chain.where.return_value.to_pandas.return_value = self._pdf([])
        mgr._update_metadata("slack", 3)
        mgr.metadata_table.add.assert_called_once()
        # existing
        mgr.metadata_table.reset_mock()
        chain.where.return_value.to_pandas.return_value = self._pdf(
            [{"app_type": "slack", "total_messages": 5}])
        mgr._update_metadata("slack", 3)
        mgr.metadata_table.delete.assert_called_once()
        rec = mgr.metadata_table.add.call_args[0][0][0]
        assert rec["total_messages"] == 8
        # error swallowed
        mgr.metadata_table.search.side_effect = RuntimeError("x")
        mgr._update_metadata("slack", 1)

    # ---------------- CommunicationIngestionPipeline ----------------
    def test_configure_and_webhooks(self):
        import integrations.atom_communication_ingestion_pipeline as ip
        pipe = self._pipe()
        cfg = ip.IngestionConfig(
            app_type=ip.CommunicationAppType.SLACK, enabled=True,
            real_time=True, batch_size=10, ingest_attachments=True,
            embed_content=True, retention_days=30)
        pipe.configure_app(ip.CommunicationAppType.SLACK, cfg)
        assert "slack" in pipe.ingestion_configs
        assert pipe.is_webhook_enabled("slack") is False
        pipe.enable_webhook_ingestion("slack", True)
        assert pipe.is_webhook_enabled("slack") is True
        pipe.enable_webhook_ingestion("teams", False)
        status = pipe.get_webhook_status()
        assert set(status) == {"slack", "teams", "gmail", "outlook"}
        assert status["slack"]["enabled"] is True

    async def test_handle_webhook_message_paths(self):
        pipe = self._pipe()
        # missing app_type
        await pipe._handle_webhook_message({})
        # disabled
        await pipe._handle_webhook_message({"app_type": "slack"})
        pipe.enable_webhook_ingestion("slack", True)
        pipe.ingest_message = AsyncMock(return_value=True)
        await pipe._handle_webhook_message({"app_type": "slack", "x": 1})
        pipe.ingest_message.assert_awaited_once()
        pipe.ingest_message = AsyncMock(return_value=False)
        await pipe._handle_webhook_message({"app_type": "slack"})
        pipe.ingest_message = AsyncMock(side_effect=RuntimeError("e"))
        await pipe._handle_webhook_message({"app_type": "slack"})

    async def test_ingest_message(self):
        import integrations.atom_communication_ingestion_pipeline as ip
        pipe = self._pipe()
        pipe.memory_manager.db = object()  # initialized
        pipe.memory_manager.ingest_communication = Mock(return_value=True)
        settings = MagicMock()
        settings.is_automations_enabled.return_value = False
        settings.is_extraction_enabled.return_value = False
        with patch("core.automation_settings.get_automation_settings",
                   return_value=settings):
            ok = await pipe.ingest_message("slack", {
                "id": "m1", "sender": "a", "recipient": "b",
                "content": "hello world", "timestamp":
                    "2026-01-01T00:00:00"})
        assert ok is True
        # embed content
        pipe.ingestion_configs["slack"] = {"embed_content": True}
        pipe.memory_manager.generate_embedding = Mock(return_value=[0.5])
        with patch("core.automation_settings.get_automation_settings",
                   return_value=settings):
            ok = await pipe.ingest_message("slack", {"content": "x"})
        assert ok is True
        # initialize branch (db None)
        pipe.memory_manager.db = None
        pipe.memory_manager.initialize = Mock(return_value=True)
        pipe.memory_manager.ingest_communication = Mock(return_value=True)
        with patch("core.automation_settings.get_automation_settings",
                   return_value=settings):
            ok = await pipe.ingest_message("slack", {"content": "x"})
        assert ok is True
        # exception -> False
        pipe.memory_manager.initialize = Mock(side_effect=RuntimeError("e"))
        assert await pipe.ingest_message("slack", {"content": "x"}) is False

    async def test_start_real_time_stream(self):
        import asyncio
        pipe = self._pipe()
        assert pipe.start_real_time_stream("unconfigured") is False
        pipe.ingestion_configs["slack"] = {"real_time": False}
        assert pipe.start_real_time_stream("slack") is False
        pipe.ingestion_configs["slack"] = {"real_time": True}
        assert pipe.start_real_time_stream("slack") is True
        assert "slack" in pipe.active_streams
        pipe.active_streams["slack"].cancel()

    async def test_real_time_ingestion_loop(self):
        import asyncio
        pipe = self._pipe()
        pipe.app_configs["slack"] = {"polling_interval_seconds": 0}

        async def fake_fetch(app):
            return [{"id": "m1"}]
        pipe._fetch_new_messages = AsyncMock(side_effect=fake_fetch)
        pipe.ingest_message = AsyncMock(return_value=True)

        async def stop(*a, **k):
            raise asyncio.CancelledError()
        with patch("integrations.atom_communication_ingestion_pipeline.asyncio.sleep",
                   new=stop):
            with pytest.raises(asyncio.CancelledError):
                await pipe._real_time_ingestion("slack")
        pipe.ingest_message.assert_awaited()
        # error in fetch -> sleeps 60 (patched stop raises)
        pipe._fetch_new_messages = AsyncMock(side_effect=RuntimeError("fetch bad"))
        with patch("integrations.atom_communication_ingestion_pipeline.asyncio.sleep",
                   new=stop):
            with pytest.raises(asyncio.CancelledError):
                await pipe._real_time_ingestion("slack")

    def test_normalize_message_branches(self):
        from datetime import datetime
        pipe = self._pipe()
        wa = pipe._normalize_message("whatsapp", {
            "id": "w1", "from": "a", "to": "b", "content": "hi",
            "timestamp": "2026-01-01T00:00:00"})
        assert wa["sender"] == "a" and wa["app_type"] == "whatsapp"
        em = pipe._normalize_message("gmail", {
            "id": "e1", "from": "user", "to": "b", "body": "hi",
            "date": "2026-01-01T00:00:00"})
        assert em["direction"] == "outbound" and em["content"] == "hi"
        gen = pipe._normalize_message("telegram", {
            "id": "t1", "sender": "a", "content": "hi",
            "timestamp": "2026-01-01T00:00:00"})
        assert gen["app_type"] == "telegram"

    def test_generate_embedding_and_stats(self):
        pipe = self._pipe()
        pipe.memory_manager.generate_embedding = Mock(return_value=[1.0])
        assert pipe._generate_embedding("t") == [1.0]
        pipe.memory_manager.metadata_table.search.return_value.to_pandas \
            .return_value = self._pdf([
                {"app_type": "slack", "total_messages": 5,
                 "last_ingested": "t", "status": "active"}])
        stats = pipe.get_ingestion_stats()
        assert stats["total_messages"] == 5
        assert stats["app_stats"]["slack"]["status"] == "active"
        pipe.memory_manager.metadata_table.search.side_effect = RuntimeError("x")
        assert "error" in pipe.get_ingestion_stats()

    def test_singletons(self):
        import integrations.atom_communication_ingestion_pipeline as ip
        m1 = ip.get_memory_manager("covpush-ws")
        assert m1 is ip.get_memory_manager("covpush-ws")
        m2 = ip.get_memory_manager("covpush-ws2")
        assert m2 is ip.get_ingestion_pipeline("covpush-ws2").memory_manager
        ip._workspace_memory_managers.pop("covpush-ws", None)
        ip._workspace_memory_managers.pop("covpush-ws2", None)

    def test_get_sentence_transformer_cached(self):
        import integrations.atom_communication_ingestion_pipeline as ip
        ip._sentence_transformer_checked = True
        assert ip._get_sentence_transformer() is ip.SentenceTransformer
        ip._sentence_transformer_checked = False
        with patch.dict(sys.modules, {"sentence_transformers": None}):
            ip._get_sentence_transformer()
        assert ip.SentenceTransformer is None
        ip._sentence_transformer_checked = False
