# -*- coding: utf-8 -*-
"""
Coverage-push tests for integrations.{figma,line,intercom}_{service,routes}.

TDD targets (RED first):

- figma_routes imports ``get_figma_service`` which does not exist in
  figma_service -> ImportError -> the figma router is dead in the lazy
  integration registry (``load_integration("figma")`` returns None).
- intercom_routes imports ``get_intercom_service`` which does not exist in
  intercom_service -> same dead-router bug for intercom.
- line_routes: ``import asyncio`` and ``_bg_tasks`` are trapped inside the
  module docstring, so every text-message webhook event raises NameError.
- line_routes.line_health awaits a synchronous dict -> TypeError -> 500.
- figma_routes.search calls ``service.search_files`` which does not exist on
  FigmaService -> AttributeError -> 500.
- figma_service.health_check and intercom_routes.intercom_health leak str(e)
  to clients (repo standard: generic message + server-side log).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from integrations.figma_service import FigmaService
from integrations.line_service import LineService
from integrations.intercom_service import IntercomService

FIGMA_CONFIG = {
    "figma_client_id": "client_1",
    "figma_client_secret": "secret_1",
    "figma_redirect_uri": "http://localhost/cb",
    "access_token": "figma_access",
    "refresh_token": "figma_refresh",
}


def ok_response(payload=None):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    resp.json.return_value = payload if payload is not None else {}
    return resp


def err_response(status_code=400):
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        f"error {status_code}", request=MagicMock(), response=resp
    )
    return resp


def make_client(router):
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def line_signature(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


# ---------------------------------------------------------------------------
# FigmaService
# ---------------------------------------------------------------------------

class TestFigmaService:
    def _svc(self):
        svc = FigmaService(tenant_id="t1", config=dict(FIGMA_CONFIG))
        svc.client = AsyncMock()
        return svc

    def test_authorization_url_with_state(self):
        url = self._svc().get_authorization_url(state="st-1")
        assert url.startswith("https://www.figma.com/oauth?")
        assert "client_id=client_1" in url
        assert "state=st-1" in url
        assert "scope=file_read" in url
        assert "response_type=code" in url

    def test_authorization_url_auto_state(self):
        svc = self._svc()
        url1 = svc.get_authorization_url()
        url2 = svc.get_authorization_url()
        assert url1 != url2
        assert "state=" in url1

    async def test_exchange_token_success(self):
        svc = self._svc()
        svc.client.post.return_value = ok_response({
            "access_token": "at2", "refresh_token": "rt2", "expires_in": 3600,
            "user_id": "u1",
        })
        data = await svc.exchange_token("code-1", "http://cb2")
        assert data["access_token"] == "at2"
        assert svc.access_token == "at2"
        assert svc.refresh_token == "rt2"
        assert svc.token_expires_at is not None
        svc.client.post.assert_called_once()
        posted = svc.client.post.call_args.kwargs["data"]
        assert posted["code"] == "code-1"
        assert posted["redirect_uri"] == "http://cb2"
        assert posted["grant_type"] == "authorization_code"

    async def test_exchange_token_default_redirect_and_error(self):
        svc = self._svc()
        svc.client.post.return_value = ok_response({"access_token": "at3"})
        await svc.exchange_token("code-2")
        assert svc.client.post.call_args.kwargs["data"]["redirect_uri"] == "http://localhost/cb"

        svc.client.post.side_effect = httpx.ConnectError("boom")
        with pytest.raises(HTTPException) as exc:
            await svc.exchange_token("code-3")
        assert exc.value.status_code == 400

    async def test_refresh_access_token_no_refresh(self):
        svc = self._svc()
        svc.refresh_token = None
        with pytest.raises(HTTPException) as exc:
            await svc.refresh_access_token()
        assert exc.value.status_code == 400

    async def test_refresh_access_token_success_with_new_refresh(self):
        svc = self._svc()
        svc.client.post.return_value = ok_response({
            "access_token": "at4", "refresh_token": "rt4", "expires_in": 100,
        })
        data = await svc.refresh_access_token()
        assert data["access_token"] == "at4"
        assert svc.access_token == "at4"
        assert svc.refresh_token == "rt4"
        assert svc.token_expires_at is not None

    async def test_refresh_access_token_success_keeps_refresh(self):
        svc = self._svc()
        svc.client.post.return_value = ok_response({"access_token": "at5"})
        await svc.refresh_access_token()
        assert svc.access_token == "at5"
        assert svc.refresh_token == "figma_refresh"

    async def test_refresh_access_token_error(self):
        svc = self._svc()
        svc.client.post.side_effect = httpx.ConnectError("boom")
        with pytest.raises(HTTPException) as exc:
            await svc.refresh_access_token()
        assert exc.value.status_code == 400

    async def test_get_user_info_no_token(self):
        svc = self._svc()
        svc.access_token = None
        with pytest.raises(HTTPException) as exc:
            await svc.get_user_info()
        assert exc.value.status_code == 401

    async def test_get_user_info_success_and_error(self):
        svc = self._svc()
        svc.client.get.return_value = ok_response({"id": "u1", "email": "a@b.c"})
        info = await svc.get_user_info()
        assert info["email"] == "a@b.c"
        assert svc.user_info == info

        svc.client.get.side_effect = httpx.ConnectError("boom")
        with pytest.raises(HTTPException) as exc:
            await svc.get_user_info()
        assert exc.value.status_code == 400

    def test_is_token_valid(self):
        svc = self._svc()
        svc.access_token = None
        assert not svc.is_token_valid()
        svc.access_token = "tok"
        svc.token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        assert svc.is_token_valid()
        svc.token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        assert not svc.is_token_valid()

    async def test_ensure_valid_token_valid(self):
        svc = self._svc()
        svc.token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        assert await svc.ensure_valid_token() == "figma_access"

    async def test_ensure_valid_token_refreshes(self):
        svc = self._svc()
        svc.token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        svc.client.post.return_value = ok_response({"access_token": "fresh"})
        assert await svc.ensure_valid_token() == "fresh"

    async def test_ensure_valid_token_no_credentials(self):
        svc = self._svc()
        svc.access_token = None
        svc.refresh_token = None
        with pytest.raises(HTTPException) as exc:
            await svc.ensure_valid_token()
        assert exc.value.status_code == 401

    def test_get_connection_status(self):
        svc = self._svc()
        svc.token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        svc.user_info = {"id": "u1"}
        status = svc.get_connection_status()
        assert status["connected"] is True
        assert status["has_access_token"] is True
        assert status["has_refresh_token"] is True
        assert status["user_info_available"] is True
        assert status["client_id_configured"] is True
        assert status["client_secret_configured"] is True
        assert status["token_expires_at"] is not None

    async def test_get_file(self):
        svc = self._svc()
        svc.client.get.return_value = ok_response({"document": {"name": "f"}})
        assert (await svc.get_file("k1"))["document"]["name"] == "f"
        svc.client.get.assert_called_once_with(
            "https://api.figma.com/v1/files/k1",
            headers={"Authorization": "Bearer figma_access", "Content-Type": "application/json"},
        )

        svc.client.get.side_effect = httpx.ConnectError("boom")
        with pytest.raises(HTTPException) as exc:
            await svc.get_file("k1")
        assert exc.value.status_code == 400

    async def test_get_file_nodes(self):
        svc = self._svc()
        svc.client.get.return_value = ok_response({"nodes": {"a": 1}})
        assert await svc.get_file_nodes("k1", ["a", "b"])
        svc.client.get.assert_called_once()
        assert svc.client.get.call_args.kwargs["params"] == {"ids": "a,b"}

        svc.client.get.side_effect = httpx.ConnectError("boom")
        with pytest.raises(HTTPException) as exc:
            await svc.get_file_nodes("k1", ["a"])
        assert exc.value.status_code == 400

    async def test_get_team_projects(self):
        svc = self._svc()
        svc.client.get.return_value = ok_response({"projects": [{"id": "p1"}]})
        assert await svc.get_team_projects("t1") == [{"id": "p1"}]

        svc.client.get.side_effect = httpx.ConnectError("boom")
        with pytest.raises(HTTPException) as exc:
            await svc.get_team_projects("t1")
        assert exc.value.status_code == 400

    async def test_get_project_files(self):
        svc = self._svc()
        svc.client.get.return_value = ok_response({"files": [{"name": "f1"}]})
        assert await svc.get_project_files("p1") == [{"name": "f1"}]

        svc.client.get.side_effect = httpx.ConnectError("boom")
        with pytest.raises(HTTPException) as exc:
            await svc.get_project_files("p1")
        assert exc.value.status_code == 400

    async def test_get_comments(self):
        svc = self._svc()
        svc.client.get.return_value = ok_response({"comments": [{"id": "c1"}]})
        assert await svc.get_comments("k1") == [{"id": "c1"}]

        svc.client.get.side_effect = httpx.ConnectError("boom")
        with pytest.raises(HTTPException) as exc:
            await svc.get_comments("k1")
        assert exc.value.status_code == 400

    def test_health_check_no_token(self):
        svc = self._svc()
        svc.access_token = None
        result = svc.health_check()
        assert result["ok"] is False
        assert result["status"] == "unhealthy"

    def test_health_check_ok(self):
        svc = self._svc()
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            result = svc.health_check()
        assert result["ok"] is True
        assert result["status"] == "healthy"

    def test_health_check_error_no_leak(self):
        svc = self._svc()
        with patch("requests.get", side_effect=RuntimeError("secret detail 12345")) as mock_get:
            result = svc.health_check()
        assert result["ok"] is False
        assert "secret detail" not in str(result)
        assert result["error"] != "secret detail 12345"

    def test_get_capabilities(self):
        caps = self._svc().get_capabilities()
        ids = [op["id"] for op in caps["operations"]]
        assert ids == ["get_file", "get_file_nodes", "get_team_projects"]

    async def test_execute_operation(self):
        svc = self._svc()
        svc.client.get.return_value = ok_response({"projects": []})
        assert (await svc.execute_operation("get_file", {"file_key": "k1"}))["success"] is True
        assert (await svc.execute_operation("get_file_nodes", {"file_key": "k1", "node_ids": ["a"]}))["success"] is True
        assert (await svc.execute_operation("get_team_projects", {"team_id": "t1"}))["success"] is True
        unsupported = await svc.execute_operation("nope", {})
        assert unsupported["success"] is False
        missing = await svc.execute_operation("get_file", {})
        assert missing["success"] is False

    async def test_sync_to_postgres_cache_new_and_existing(self):
        svc = self._svc()
        with patch("core.database.SessionLocal") as session_cls, \
                patch("core.models.IntegrationMetric") as metric_cls:
            db = MagicMock()
            db.query.return_value.filter_by.return_value.first.return_value = None
            session_cls.return_value = db
            result = await svc.sync_to_postgres_cache("ws1")
        assert result["success"] is True
        assert result["metrics_synced"] == 1
        assert db.commit.called
        assert db.add.called

        with patch("core.database.SessionLocal") as session_cls, \
                patch("core.models.IntegrationMetric") as metric_cls:
            db = MagicMock()
            existing = MagicMock()
            db.query.return_value.filter_by.return_value.first.return_value = existing
            session_cls.return_value = db
            result = await svc.sync_to_postgres_cache("ws1")
        assert result["success"] is True
        assert existing.value == float(1)

    async def test_sync_to_postgres_cache_db_error(self):
        svc = self._svc()
        with patch("core.database.SessionLocal") as session_cls, \
                patch("core.models.IntegrationMetric") as metric_cls:
            db = MagicMock()
            db.commit.side_effect = RuntimeError("db down")
            session_cls.return_value = db
            result = await svc.sync_to_postgres_cache("ws1")
        assert result["success"] is False
        assert db.rollback.called

    async def test_close(self):
        svc = self._svc()
        await svc.close()
        svc.client.aclose.assert_awaited_once()

    async def test_sync_to_postgres_cache_outer_error(self):
        svc = self._svc()
        with patch("core.database.SessionLocal", side_effect=RuntimeError("no db")):
            result = await svc.sync_to_postgres_cache("ws1")
        assert result["success"] is False

    async def test_search_files_empty_inputs(self):
        svc = self._svc()
        assert await svc.search_files("") == []
        assert await svc.search_files("q") == []
        assert not svc.client.get.called

    async def test_search_files_success_and_error(self):
        svc = self._svc()
        responses = [
            ok_response({"projects": [{"id": "p1", "name": "Proj"}, {"id": "p2", "name": "Other"}]}),
            ok_response({"files": [{"name": "Design System"}, {"name": "Docs"}]}),
            ok_response({"files": [{"name": "Landing Page Design"}]}),
        ]
        svc.client.get.side_effect = responses
        results = await svc.search_files("design", team_id="t1")
        assert [f["name"] for f in results] == ["Design System", "Landing Page Design"]
        assert results[0]["project_id"] == "p1"

        svc.get_team_projects = AsyncMock(side_effect=httpx.ConnectError("boom"))
        with pytest.raises(HTTPException) as exc:
            await svc.search_files("design", team_id="t1")
        assert exc.value.status_code == 400

    async def test_full_sync(self):
        svc = self._svc()
        with patch("core.database.SessionLocal") as session_cls, \
                patch("core.models.IntegrationMetric") as metric_cls:
            db = MagicMock()
            db.query.return_value.filter_by.return_value.first.return_value = None
            session_cls.return_value = db
            result = await svc.full_sync("ws1")
        assert result["success"] is True
        assert result["workspace_id"] == "ws1"
        assert result["postgres_cache"]["success"] is True


# ---------------------------------------------------------------------------
# FigmaRoutes
# ---------------------------------------------------------------------------

class TestFigmaRoutes:
    def _svc(self):
        svc = MagicMock()
        svc.get_authorization_url.return_value = "https://figma/oauth?x=1"
        svc.exchange_token = AsyncMock(return_value={"user_id": "u1", "expires_in": 3600})
        svc.get_connection_status.return_value = {"connected": True}
        svc.ensure_valid_token = AsyncMock(return_value="tok")
        svc.get_user_info = AsyncMock(return_value={"id": "u1"})
        svc.get_team_projects = AsyncMock(return_value=[
            {"id": "p1", "name": "Proj A"},
        ])
        svc.get_project_files = AsyncMock(return_value=[
            {"name": "f1", "id": "f1"},
        ])
        svc.search_files = AsyncMock(return_value=[{"name": "hit"}])
        svc.health_check.return_value = {"ok": True, "status": "healthy"}
        return svc

    def _client(self):
        from integrations.figma_routes import router
        return make_client(router)

    def test_oauth_url(self):
        with patch("integrations.figma_routes.get_figma_service", return_value=self._svc()) as mock_get:
            resp = self._client().get("/api/figma/oauth/url", params={"state": "s1"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert resp.json()["authorization_url"] == "https://figma/oauth?x=1"
        assert mock_get.return_value.get_authorization_url.call_args.args == ("s1",)

    def test_oauth_url_error_500(self):
        svc = self._svc()
        svc.get_authorization_url.side_effect = RuntimeError("boom")
        with patch("integrations.figma_routes.get_figma_service", return_value=svc):
            resp = self._client().get("/api/figma/oauth/url")
        assert resp.status_code == 500

    def test_oauth_callback(self):
        with patch("integrations.figma_routes.get_figma_service", return_value=self._svc()):
            resp = self._client().get("/api/figma/oauth/callback", params={"code": "c1"})
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "u1"

    def test_oauth_callback_http_error_re_raised(self):
        svc = self._svc()
        svc.exchange_token = AsyncMock(side_effect=HTTPException(status_code=400, detail="Internal error"))
        with patch("integrations.figma_routes.get_figma_service", return_value=svc):
            resp = self._client().get("/api/figma/oauth/callback", params={"code": "c1"})
        assert resp.status_code == 400

    def test_oauth_callback_other_error_500(self):
        svc = self._svc()
        svc.exchange_token = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("integrations.figma_routes.get_figma_service", return_value=svc):
            resp = self._client().get("/api/figma/oauth/callback", params={"code": "c1"})
        assert resp.status_code == 500

    def test_oauth_status(self):
        with patch("integrations.figma_routes.get_figma_service", return_value=self._svc()):
            resp = self._client().get("/api/figma/oauth/status")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert resp.json()["connected"] is True

    def test_oauth_status_error_500(self):
        svc = self._svc()
        svc.get_connection_status.side_effect = RuntimeError("boom")
        with patch("integrations.figma_routes.get_figma_service", return_value=svc):
            resp = self._client().get("/api/figma/oauth/status")
        assert resp.status_code == 500

    def test_status_connected(self):
        with patch("integrations.figma_routes.get_figma_service", return_value=self._svc()):
            resp = self._client().get("/api/figma/status", params={"user_id": "u1"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "connected"

    def test_status_disconnected(self):
        svc = self._svc()
        svc.get_connection_status.return_value = {"connected": False}
        with patch("integrations.figma_routes.get_figma_service", return_value=svc):
            resp = self._client().get("/api/figma/status")
        assert resp.json()["status"] == "disconnected"

    def test_user(self):
        with patch("integrations.figma_routes.get_figma_service", return_value=self._svc()):
            resp = self._client().get("/api/figma/user")
        assert resp.status_code == 200
        assert resp.json()["id"] == "u1"

    def test_user_http_error_re_raised(self):
        svc = self._svc()
        svc.ensure_valid_token = AsyncMock(side_effect=HTTPException(status_code=401, detail="No valid token available"))
        with patch("integrations.figma_routes.get_figma_service", return_value=svc):
            resp = self._client().get("/api/figma/user")
        assert resp.status_code == 401

    def test_user_other_error_500(self):
        svc = self._svc()
        svc.get_user_info = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("integrations.figma_routes.get_figma_service", return_value=svc):
            resp = self._client().get("/api/figma/user")
        assert resp.status_code == 500

    def test_files_by_team(self):
        with patch("integrations.figma_routes.get_figma_service", return_value=self._svc()):
            resp = self._client().get("/api/figma/files", params={"team_id": "t1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["count"] == 1
        assert body["files"][0]["project_id"] == "p1"
        assert body["files"][0]["project_name"] == "Proj A"
        assert body["source"] == "team_projects"

    def test_files_by_project(self):
        with patch("integrations.figma_routes.get_figma_service", return_value=self._svc()):
            resp = self._client().get("/api/figma/files", params={"project_id": "p1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["source"] == "project"
        assert body["count"] == 1

    def test_files_missing_context(self):
        with patch("integrations.figma_routes.get_figma_service", return_value=self._svc()):
            resp = self._client().get("/api/figma/files")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert body["error"] == "missing_context"

    def test_files_http_error_re_raised(self):
        svc = self._svc()
        svc.ensure_valid_token = AsyncMock(side_effect=HTTPException(status_code=401, detail="No valid token available"))
        with patch("integrations.figma_routes.get_figma_service", return_value=svc):
            resp = self._client().get("/api/figma/files", params={"team_id": "t1"})
        assert resp.status_code == 401

    def test_files_other_error_500(self):
        svc = self._svc()
        svc.get_team_projects = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("integrations.figma_routes.get_figma_service", return_value=svc):
            resp = self._client().get("/api/figma/files", params={"team_id": "t1"})
        assert resp.status_code == 500

    def test_search_with_real_service(self):
        svc = FigmaService(tenant_id="t1", config=dict(FIGMA_CONFIG))
        svc.client = AsyncMock()
        svc.client.get.return_value = ok_response({"projects": [{"id": "p1", "name": "Des"}]})
        svc.client.get.side_effect = None
        responses = [ok_response({"projects": [{"id": "p1", "name": "Des"}]}), ok_response({"files": [{"name": "Design System", "id": "f1"}]})]
        svc.client.get.side_effect = responses
        with patch("integrations.figma_routes.get_figma_service", return_value=svc):
            resp = self._client().post("/api/figma/search", json={"query": "design"}, params={"team_id": "t1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["query"] == "design"
        assert body["results"] == [{"name": "Design System", "id": "f1", "project_id": "p1"}]

    def test_search_with_mock_service(self):
        with patch("integrations.figma_routes.get_figma_service", return_value=self._svc()):
            resp = self._client().post("/api/figma/search", json={"query": "q"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert resp.json()["results"] == [{"name": "hit"}]

    def test_search_other_error_500(self):
        svc = self._svc()
        svc.search_files = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("integrations.figma_routes.get_figma_service", return_value=svc):
            resp = self._client().post("/api/figma/search", json={"query": "q"})
        assert resp.status_code == 500

    def test_search_http_error_re_raised(self):
        svc = self._svc()
        svc.ensure_valid_token = AsyncMock(side_effect=HTTPException(status_code=401, detail="No valid token available"))
        with patch("integrations.figma_routes.get_figma_service", return_value=svc):
            resp = self._client().post("/api/figma/search", json={"query": "q"})
        assert resp.status_code == 401

    def test_items(self):
        with patch("integrations.figma_routes.get_figma_service", return_value=self._svc()):
            resp = self._client().get("/api/figma/items")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 5

    def test_items_other_error_500(self):
        svc = self._svc()
        svc.ensure_valid_token = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("integrations.figma_routes.get_figma_service", return_value=svc):
            resp = self._client().get("/api/figma/items")
        assert resp.status_code == 500

    def test_items_http_error_re_raised(self):
        svc = self._svc()
        svc.ensure_valid_token = AsyncMock(side_effect=HTTPException(status_code=401, detail="No valid token available"))
        with patch("integrations.figma_routes.get_figma_service", return_value=svc):
            resp = self._client().get("/api/figma/items")
        assert resp.status_code == 401

    def test_health(self):
        with patch("integrations.figma_routes.get_figma_service", return_value=self._svc()):
            resp = self._client().get("/api/figma/health")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


# ---------------------------------------------------------------------------
# LineService
# ---------------------------------------------------------------------------

class TestLineService:
    def _svc(self, token="line_token"):
        svc = LineService(tenant_id="t1", config={"channel_access_token": token})
        svc.client = AsyncMock()
        return svc

    def test_capabilities(self):
        caps = self._svc().get_capabilities()
        assert [op["id"] for op in caps["operations"]] == ["send_message", "broadcast", "get_profile"]
        assert caps["supports_webhooks"] is True
        assert caps["required_params"] == ["channel_access_token"]

    def test_health_check(self):
        assert self._svc("tok").health_check()["healthy"] is True
        assert self._svc(None).health_check()["healthy"] is False
        assert self._svc(None).health_check()["status"] == "degraded"

    async def test_close(self):
        svc = self._svc()
        await svc.close()
        svc.client.aclose.assert_awaited_once()

    async def test_execute_operation_tenant_mismatch(self):
        svc = self._svc()
        result = await svc.execute_operation("send_message", {"to": "u", "text": "hi"}, context={"tenant_id": "other"})
        assert result["success"] is False
        assert "cross_tenant" in result["details"]["reason"]

    async def test_execute_operation_unsupported(self):
        with pytest.raises(NotImplementedError):
            await self._svc().execute_operation("nope", {})

    async def test_send_message_missing_params(self):
        svc = self._svc()
        result = await svc.execute_operation("send_message", {"to": "u1"})
        assert result["success"] is False
        assert "to and text" in result["error"]

    async def test_send_message_no_token(self):
        svc = self._svc(token=None)
        result = await svc.execute_operation("send_message", {"to": "u1", "text": "hi"})
        assert result["success"] is False
        assert "not configured" in result["error"]

    async def test_send_message_push(self):
        svc = self._svc()
        svc.client.post.return_value = ok_response()
        result = await svc.execute_operation("send_message", {"to": "u1", "text": "hi"})
        assert result["success"] is True
        assert result["result"]["message_sent"] is True
        url = svc.client.post.call_args.args[0]
        assert url.endswith("/push")
        assert svc.client.post.call_args.kwargs["json"]["to"] == "u1"

    async def test_send_message_reply(self):
        svc = self._svc()
        svc.client.post.return_value = ok_response()
        result = await svc.execute_operation(
            "send_message", {"to": "u1", "text": "hi", "reply_token": "rt1"}
        )
        assert result["success"] is True
        url = svc.client.post.call_args.args[0]
        assert url.endswith("/reply")
        payload = svc.client.post.call_args.kwargs["json"]
        assert payload["replyToken"] == "rt1"
        assert "to" not in payload

    async def test_send_message_error(self):
        svc = self._svc()
        svc.client.post.side_effect = httpx.ConnectError("boom")
        result = await svc.execute_operation("send_message", {"to": "u1", "text": "hi"})
        assert result["success"] is False

    async def test_broadcast_missing_params(self):
        svc = self._svc()
        result = await svc.execute_operation("broadcast", {"to": ["u1"]})
        assert result["success"] is False
        assert "to and messages" in result["error"]

    async def test_broadcast_no_token(self):
        svc = self._svc(token=None)
        result = await svc.execute_operation("broadcast", {"to": ["u1"], "messages": [{"type": "text", "text": "x"}]})
        assert result["success"] is False

    async def test_broadcast_success(self):
        svc = self._svc()
        svc.client.post.return_value = ok_response()
        result = await svc.execute_operation(
            "broadcast", {"to": ["u1", "u2"], "messages": [{"type": "text", "text": "x"}]}
        )
        assert result["success"] is True
        assert result["result"]["recipients"] == 2
        assert svc.client.post.call_args.args[0].endswith("/multicast")

    async def test_broadcast_error(self):
        svc = self._svc()
        svc.client.post.side_effect = httpx.ConnectError("boom")
        result = await svc.execute_operation("broadcast", {"to": ["u1"], "messages": [{"type": "text", "text": "x"}]})
        assert result["success"] is False

    async def test_get_profile_missing_user(self):
        svc = self._svc()
        result = await svc.execute_operation("get_profile", {})
        assert result["success"] is False
        assert "user_id" in result["error"]

    async def test_get_profile_no_token(self):
        svc = self._svc(token=None)
        result = await svc.execute_operation("get_profile", {"user_id": "u1"})
        assert result["success"] is False

    async def test_get_profile_success(self):
        svc = self._svc()
        svc.client.get.return_value = ok_response({"userId": "u1", "displayName": "Bob"})
        result = await svc.execute_operation("get_profile", {"user_id": "u1"})
        assert result["success"] is True
        assert result["result"]["displayName"] == "Bob"
        assert svc.client.get.call_args.args[0].endswith("/bot/profile/u1")

    async def test_get_profile_error(self):
        svc = self._svc()
        svc.client.get.side_effect = httpx.ConnectError("boom")
        result = await svc.execute_operation("get_profile", {"user_id": "u1"})
        assert result["success"] is False


# ---------------------------------------------------------------------------
# LineRoutes
# ---------------------------------------------------------------------------

class TestLineRoutes:
    def _client(self):
        from integrations.line_routes import router
        return make_client(router)

    def test_webhook_fail_closed_no_secret(self, monkeypatch):
        monkeypatch.delenv("LINE_CHANNEL_SECRET", raising=False)
        client = self._client()
        body = json.dumps({"events": []}).encode()
        resp = client.post(
            "/api/line/webhook",
            content=body,
            headers={"x-line-signature": line_signature(body, "")},
        )
        assert resp.status_code == 503

    def test_webhook_missing_signature(self, monkeypatch):
        monkeypatch.setenv("LINE_CHANNEL_SECRET", "secret-1")
        client = self._client()
        resp = client.post("/api/line/webhook", json={"events": []})
        assert resp.status_code == 401

    def test_webhook_invalid_signature(self, monkeypatch):
        monkeypatch.setenv("LINE_CHANNEL_SECRET", "secret-1")
        client = self._client()
        resp = client.post(
            "/api/line/webhook",
            json={"events": []},
            headers={"x-line-signature": "AAAAAAAAAAAA"},
        )
        assert resp.status_code == 401

    def test_webhook_valid_signature_non_message(self, monkeypatch):
        monkeypatch.setenv("LINE_CHANNEL_SECRET", "secret-1")
        client = self._client()
        body = json.dumps({"events": [{"type": "follow"}]}).encode()
        resp = client.post(
            "/api/line/webhook",
            content=body,
            headers={"x-line-signature": line_signature(body, "secret-1")},
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "OK"}

    def test_webhook_valid_signature_text_message(self, monkeypatch):
        monkeypatch.setenv("LINE_CHANNEL_SECRET", "secret-1")
        with patch("integrations.line_routes.universal_webhook_bridge") as bridge:
            bridge.process_incoming_message = AsyncMock(return_value={"status": "ok"})
            client = self._client()
            event = {
                "type": "message",
                "message": {"type": "text", "text": "hello"},
                "replyToken": "rt1",
                "source": {"userId": "u1"},
            }
            body = json.dumps({"events": [event]}).encode()
            resp = client.post(
                "/api/line/webhook",
                content=body,
                headers={"x-line-signature": line_signature(body, "secret-1")},
            )
        assert resp.status_code == 200
        bridge.process_incoming_message.assert_called_once_with("line", event)

    def test_webhook_ignores_non_text_message(self, monkeypatch):
        monkeypatch.setenv("LINE_CHANNEL_SECRET", "secret-1")
        with patch("integrations.line_routes.universal_webhook_bridge") as bridge:
            bridge.process_incoming_message = AsyncMock()
            client = self._client()
            event = {"type": "message", "message": {"type": "image"}, "source": {"userId": "u1"}}
            body = json.dumps({"events": [event]}).encode()
            resp = client.post(
                "/api/line/webhook",
                content=body,
                headers={"x-line-signature": line_signature(body, "secret-1")},
            )
        assert resp.status_code == 200
        bridge.process_incoming_message.assert_not_called()

    def test_health(self):
        client = self._client()
        resp = client.get("/api/line/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "line"


# ---------------------------------------------------------------------------
# IntercomService
# ---------------------------------------------------------------------------

class TestIntercomService:
    def _svc(self, token="ic_token"):
        svc = IntercomService(tenant_id="t1", config={"intercom_access_token": token})
        svc.client = AsyncMock()
        svc.http = AsyncMock()
        svc.http.post.return_value = None
        svc.http.get.return_value = None
        return svc

    def test_capabilities(self):
        caps = self._svc().get_capabilities()
        ids = [op["id"] for op in caps["operations"]]
        assert ids == ["search_contacts", "get_contacts", "get_conversations", "get_admins"]
        assert caps["required_params"] == ["access_token"]

    async def test_execute_operation_tenant_mismatch(self):
        result = await self._svc().execute_operation(
            "get_contacts", {"access_token": "x"}, context={"tenant_id": "other"}
        )
        assert result["success"] is False
        assert result["error"] == "Tenant mismatch"

    async def test_execute_operation_missing_token(self):
        svc = IntercomService(tenant_id="t1", config={})
        result = await svc.execute_operation("get_contacts", {})
        assert result["success"] is False
        assert result["error"] == "Missing access token"

    async def test_execute_operation_unsupported(self):
        svc = self._svc()
        result = await svc.execute_operation("nope", {"access_token": "x"})
        assert result["success"] is False

    async def test_execute_operation_error_propagates(self):
        svc = self._svc()
        svc.search_contacts = AsyncMock(side_effect=RuntimeError("boom"))
        result = await svc.execute_operation("search_contacts", {"access_token": "x"})
        assert result["success"] is False

    async def test_execute_operation_all_ops(self):
        svc = self._svc()
        svc.search_contacts = AsyncMock(return_value=[{"id": "c1"}])
        svc.get_contacts = AsyncMock(return_value=[{"id": "c1"}])
        svc.get_conversations = AsyncMock(return_value=[{"id": "cv1"}])
        svc.get_admins = AsyncMock(return_value=[{"id": "a1"}])
        assert (await svc.execute_operation("search_contacts", {"access_token": "x", "query": "q"}))["success"] is True
        assert (await svc.execute_operation("get_contacts", {"access_token": "x", "limit": 5}))["success"] is True
        assert (await svc.execute_operation("get_conversations", {"access_token": "x", "limit": 5}))["success"] is True
        assert (await svc.execute_operation("get_admins", {"access_token": "x"}))["success"] is True

    async def test_exchange_token_success(self):
        svc = self._svc()
        svc.http.post = AsyncMock(return_value=ok_response({"access_token": "t"}))
        data = await svc.exchange_token("code-1")
        assert data["access_token"] == "t"
        url = svc.http.post.call_args.args[1]
        assert url.endswith("/auth/eagle/token")
        assert svc.http.post.call_args.kwargs["json"]["code"] == "code-1"

    async def test_exchange_token_error(self):
        svc = self._svc()
        svc.http.post = AsyncMock(return_value=err_response(400))
        with pytest.raises(httpx.HTTPStatusError):
            await svc.exchange_token("code-1")

    async def test_get_admins(self):
        svc = self._svc()
        svc.http.get = AsyncMock(return_value=ok_response({"admins": [{"id": "a1"}]}))
        assert await svc.get_admins("tok") == [{"id": "a1"}]
        assert svc.http.get.call_args.args[1].endswith("/admins")

        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("boom"))
        with pytest.raises(httpx.ConnectError):
            await svc.get_admins("tok")

    async def test_get_contacts(self):
        svc = self._svc()
        svc.http.get = AsyncMock(return_value=ok_response({"data": [{"id": "c1"}]}))
        assert await svc.get_contacts("tok", 5) == [{"id": "c1"}]
        assert svc.http.get.call_args.kwargs["params"] == {"per_page": 5}
        assert "Authorization" in svc.http.get.call_args.kwargs["headers"]

    async def test_get_conversations(self):
        svc = self._svc()
        svc.http.get = AsyncMock(return_value=ok_response({"conversations": [{"id": "cv1"}]}))
        assert await svc.get_conversations("tok", 3) == [{"id": "cv1"}]

    async def test_search_contacts(self):
        svc = self._svc()
        svc.http.post = AsyncMock(return_value=ok_response({"data": [{"id": "c1"}]}))
        assert await svc.search_contacts("tok", "bob") == [{"id": "c1"}]
        payload = svc.http.post.call_args.kwargs["json"]
        assert payload["query"]["value"] == "bob"
        assert payload["query"]["field"] == "name"

    async def test_close(self):
        svc = self._svc()
        await svc.close()
        svc.client.aclose.assert_awaited_once()

    def test_health_check(self):
        svc = self._svc()
        svc.client_id = "cid"
        svc.client_secret = "cs"
        assert svc.health_check()["healthy"] is True
        svc2 = self._svc()
        svc2.client_id = None
        svc2.client_secret = None
        assert svc2.health_check()["healthy"] is False
        assert svc2.health_check()["status"] == "unconfigured"


# ---------------------------------------------------------------------------
# IntercomRoutes
# ---------------------------------------------------------------------------

class TestIntercomRoutes:
    def _svc(self):
        svc = MagicMock()
        svc.client_id = "cid"
        svc.client_secret = "cs"
        svc.exchange_token = AsyncMock(return_value={"access_token": "t"})
        svc.get_contacts = AsyncMock(return_value=[{"id": "c1"}])
        svc.get_conversations = AsyncMock(return_value=[{"id": "cv1"}])
        svc.get_admins = AsyncMock(return_value=[{"id": "a1"}])
        svc.search_contacts = AsyncMock(return_value=[{"id": "c1"}])
        svc.health_check.return_value = {"healthy": True, "status": "healthy"}
        return svc

    def _client(self):
        from integrations.intercom_routes import router
        return make_client(router)

    def test_auth_url(self):
        with patch("integrations.intercom_routes.get_intercom_service", return_value=self._svc()):
            resp = self._client().get("/intercom/auth/url")
        assert resp.status_code == 200
        assert "client_id=cid" in resp.json()["url"]

    def test_auth_url_placeholder_client_id(self):
        svc = self._svc()
        svc.client_id = None
        with patch("integrations.intercom_routes.get_intercom_service", return_value=svc):
            resp = self._client().get("/intercom/auth/url")
        assert "client_id=INSERT_CLIENT_ID" in resp.json()["url"]

    def test_auth_callback(self):
        with patch("integrations.intercom_routes.get_intercom_service", return_value=self._svc()):
            resp = self._client().post("/intercom/auth/callback", json={"code": "c1"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_auth_callback_error_400(self):
        svc = self._svc()
        svc.exchange_token = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("integrations.intercom_routes.get_intercom_service", return_value=svc):
            resp = self._client().post("/intercom/auth/callback", json={"code": "c1"})
        assert resp.status_code == 400

    def test_get_contacts(self):
        with patch("integrations.intercom_routes.get_intercom_service", return_value=self._svc()):
            resp = self._client().get("/intercom/contacts", params={"access_token": "t", "limit": 5})
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_get_contacts_error_500(self):
        svc = self._svc()
        svc.get_contacts = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("integrations.intercom_routes.get_intercom_service", return_value=svc):
            resp = self._client().get("/intercom/contacts", params={"access_token": "t"})
        assert resp.status_code == 500

    def test_get_conversations(self):
        with patch("integrations.intercom_routes.get_intercom_service", return_value=self._svc()):
            resp = self._client().get("/intercom/conversations", params={"access_token": "t"})
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_get_conversations_error_500(self):
        svc = self._svc()
        svc.get_conversations = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("integrations.intercom_routes.get_intercom_service", return_value=svc):
            resp = self._client().get("/intercom/conversations", params={"access_token": "t"})
        assert resp.status_code == 500

    def test_get_admins(self):
        with patch("integrations.intercom_routes.get_intercom_service", return_value=self._svc()):
            resp = self._client().get("/intercom/admins", params={"access_token": "t"})
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_get_admins_error_500(self):
        svc = self._svc()
        svc.get_admins = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("integrations.intercom_routes.get_intercom_service", return_value=svc):
            resp = self._client().get("/intercom/admins", params={"access_token": "t"})
        assert resp.status_code == 500

    def test_search(self):
        with patch("integrations.intercom_routes.get_intercom_service", return_value=self._svc()):
            resp = self._client().post("/intercom/search", json={"query": "bob"}, params={"access_token": "t"})
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_search_error_500(self):
        svc = self._svc()
        svc.search_contacts = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("integrations.intercom_routes.get_intercom_service", return_value=svc):
            resp = self._client().post("/intercom/search", json={"query": "bob"}, params={"access_token": "t"})
        assert resp.status_code == 500

    def test_status(self):
        with patch("integrations.intercom_routes.get_intercom_service", return_value=self._svc()):
            resp = self._client().get("/intercom/status")
        assert resp.status_code == 200
        assert resp.json()["configured"] is True

    def test_health(self):
        with patch("integrations.intercom_routes.get_intercom_service", return_value=self._svc()):
            resp = self._client().get("/intercom/health")
        assert resp.status_code == 200
        assert resp.json()["healthy"] is True

    def test_health_error_no_leak(self):
        svc = self._svc()
        svc.health_check.side_effect = RuntimeError("intercom secret detail 999")
        with patch("integrations.intercom_routes.get_intercom_service", return_value=svc):
            resp = self._client().get("/intercom/health")
        assert resp.status_code == 200
        assert "secret detail" not in resp.text

    def test_contacts_missing_token_422(self):
        with patch("integrations.intercom_routes.get_intercom_service", return_value=self._svc()):
            resp = self._client().get("/intercom/contacts")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Router availability (lazy registry)
# ---------------------------------------------------------------------------

class TestRouterAvailability:
    def test_figma_router_importable(self):
        from integrations.figma_routes import router
        paths = [r.path for r in router.routes]
        assert "/api/figma/search" in paths
        assert "/api/figma/health" in paths

    def test_intercom_router_importable(self):
        from integrations.intercom_routes import router
        paths = [r.path for r in router.routes]
        assert "/intercom/search" in paths

    def test_line_router_importable(self):
        from integrations.line_routes import router
        paths = [r.path for r in router.routes]
        assert "/api/line/webhook" in paths

    def test_load_integration_figma(self):
        from core.lazy_integration_registry import load_integration
        router = load_integration("figma")
        assert router is not None
        paths = [r.path for r in router.routes]
        assert "/api/figma/search" in paths

    def test_load_integration_intercom(self):
        from core.lazy_integration_registry import load_integration
        router = load_integration("intercom")
        assert router is not None
        paths = [r.path for r in router.routes]
        assert "/intercom/search" in paths

    def test_get_figma_service_returns_instance(self):
        from integrations.figma_service import get_figma_service
        svc = get_figma_service()
        assert isinstance(svc, FigmaService)
        assert get_figma_service() is svc

    def test_get_intercom_service_returns_instance(self):
        from integrations.intercom_service import get_intercom_service
        svc = get_intercom_service()
        assert isinstance(svc, IntercomService)
        assert get_intercom_service() is svc
