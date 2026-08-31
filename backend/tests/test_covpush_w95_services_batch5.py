# -*- coding: utf-8 -*-
"""Coverage wave 95 batch 5 — integrations services/routes:

- integrations/outlook_routes.py
- integrations/figma_service.py
- integrations/zendesk_service.py
- integrations/chat_routes.py
- integrations/zoho_inventory_service.py
- integrations/freshdesk_routes.py
- integrations/zoom_service.py
- integrations/whatsapp_service_manager.py

Standalone: each module reaches >=80% line coverage from this file alone.
No network / no LLM / no real DB: httpx/requests boundaries and DB sessions
mocked, FastAPI TestClient + dependency_overrides for routes.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def _hresp(status=200, json_data=None, content=b''):
    r = httpx.Response(status, json=json_data if json_data is not None else {},
                       request=httpx.Request('GET', 'http://x'))
    if content:
        r._content = content
    return r


def _ok(json_data=None):
    return _hresp(200, json_data if json_data is not None else {})


# ============================================================================
# integrations/outlook_routes.py
# ============================================================================

from core.security_dependencies import get_current_user
from integrations import outlook_routes as orr


@pytest.fixture
def outlook_app():
    app = FastAPI()
    # R80: match the real app mount (main_api_app.py registers outlook at
    # /api/integrations/outlook; the router itself declares prefix="")
    app.include_router(orr.router, prefix="/api/integrations/outlook")
    return app


@pytest.fixture
def outlook_client(outlook_app):
    outlook_app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="user_1", tenant_id="t1")
    return TestClient(outlook_app)


@pytest.fixture
def osvc():
    with patch.object(orr, "outlook_service") as m:
        yield m


class TestOutlookRoutesAuth:
    @pytest.mark.parametrize("method,path,kwargs", [
        ("get", "/api/integrations/outlook/auth/url", {}),
        ("get", "/api/integrations/outlook/callback", {"params": {"code": "c"}}),
        ("post", "/api/integrations/outlook/emails", {"json": {"user_id": "u"}}),
        ("get", "/api/integrations/outlook/emails/unread", {"params": {"user_id": "u"}}),
        ("get", "/api/integrations/outlook/health", {}),
    ])
    def test_anonymous_rejected(self, outlook_app, method, path, kwargs):
        c = TestClient(outlook_app)
        assert getattr(c, method)(path, **kwargs).status_code == 401


class TestOutlookRoutes:
    def test_auth_url_and_callback(self, outlook_client):
        r = outlook_client.get("/api/integrations/outlook/auth/url")
        assert r.status_code == 200 and "url" in r.json()
        r = outlook_client.get("/api/integrations/outlook/callback", params={"code": "c1"})
        assert r.status_code == 200 and r.json()["ok"] is True

    def test_list_emails(self, outlook_client, osvc):
        osvc.get_user_emails = AsyncMock(return_value=[{"id": "m1"}])
        r = outlook_client.post("/api/integrations/outlook/emails", json={"user_id": "u"})
        assert r.status_code == 200 and r.json()["count"] == 1
        osvc.get_user_emails = AsyncMock(side_effect=RuntimeError("x"))
        assert outlook_client.post("/api/integrations/outlook/emails",
                                   json={"user_id": "u"}).status_code == 500

    def test_send_email(self, outlook_client, osvc):
        osvc.send_email = AsyncMock(return_value={"id": "m"})
        r = outlook_client.post("/api/integrations/outlook/emails/send", json={
            "user_id": "u", "to_recipients": ["a@b.c"], "subject": "s",
            "body": "b"})
        assert r.status_code == 200
        osvc.send_email = AsyncMock(return_value=None)
        assert outlook_client.post("/api/integrations/outlook/emails/send", json={
            "user_id": "u", "to_recipients": ["a@b.c"], "subject": "s",
            "body": "b"}).status_code == 500
        osvc.send_email = AsyncMock(side_effect=RuntimeError("x"))
        assert outlook_client.post("/api/integrations/outlook/emails/send", json={
            "user_id": "u", "to_recipients": ["a"], "subject": "s",
            "body": "b"}).status_code == 500

    def test_draft_email(self, outlook_client, osvc):
        osvc.create_draft_email = AsyncMock(return_value={"id": "d"})
        r = outlook_client.post("/api/integrations/outlook/emails/draft", json={
            "user_id": "u", "to_recipients": ["a@b.c"], "subject": "s",
            "body": "b"})
        assert r.status_code == 200
        osvc.create_draft_email = AsyncMock(return_value=None)
        assert outlook_client.post("/api/integrations/outlook/emails/draft", json={
            "user_id": "u", "to_recipients": ["a"], "subject": "s",
            "body": "b"}).status_code == 500
        osvc.create_draft_email = AsyncMock(side_effect=RuntimeError("x"))
        assert outlook_client.post("/api/integrations/outlook/emails/draft", json={
            "user_id": "u", "to_recipients": ["a"], "subject": "s",
            "body": "b"}).status_code == 500

    def test_unread(self, outlook_client, osvc):
        osvc.get_unread_emails = AsyncMock(return_value=[1, 2])
        r = outlook_client.get("/api/integrations/outlook/emails/unread", params={"user_id": "u"})
        assert r.status_code == 200 and r.json()["count"] == 2
        osvc.get_unread_emails = AsyncMock(side_effect=RuntimeError("x"))
        assert outlook_client.get("/api/integrations/outlook/emails/unread",
                                  params={"user_id": "u"}).status_code == 500

    def test_get_email(self, outlook_client, osvc):
        osvc.get_email_by_id = AsyncMock(return_value={"id": "m1"})
        r = outlook_client.get("/api/integrations/outlook/emails/m1", params={"user_id": "u"})
        assert r.status_code == 200
        osvc.get_email_by_id = AsyncMock(return_value=None)
        assert outlook_client.get("/api/integrations/outlook/emails/m1",
                                  params={"user_id": "u"}).status_code == 404
        osvc.get_email_by_id = AsyncMock(side_effect=RuntimeError("x"))
        assert outlook_client.get("/api/integrations/outlook/emails/m1",
                                  params={"user_id": "u"}).status_code == 500

    def test_delete_email(self, outlook_client, osvc):
        osvc.delete_email = AsyncMock(return_value=True)
        r = outlook_client.delete("/api/integrations/outlook/emails/m1", params={"user_id": "u"})
        assert r.status_code == 200
        osvc.delete_email = AsyncMock(return_value=False)
        assert outlook_client.delete("/api/integrations/outlook/emails/m1",
                                     params={"user_id": "u"}).status_code == 500
        osvc.delete_email = AsyncMock(side_effect=RuntimeError("x"))
        assert outlook_client.delete("/api/integrations/outlook/emails/m1",
                                     params={"user_id": "u"}).status_code == 500

    def test_calendar(self, outlook_client, osvc):
        osvc.get_calendar_events = AsyncMock(return_value=[{"id": "e"}])
        r = outlook_client.post("/api/integrations/outlook/calendar/events", json={"user_id": "u"})
        assert r.status_code == 200 and r.json()["count"] == 1
        osvc.get_calendar_events = AsyncMock(side_effect=RuntimeError("x"))
        assert outlook_client.post("/api/integrations/outlook/calendar/events",
                                   json={"user_id": "u"}).status_code == 500
        osvc.create_calendar_event = AsyncMock(return_value={"id": "e"})
        r = outlook_client.post("/api/integrations/outlook/calendar/events/create",
                                json={"user_id": "u", "subject": "s"})
        assert r.status_code == 200
        osvc.create_calendar_event = AsyncMock(return_value=None)
        assert outlook_client.post("/api/integrations/outlook/calendar/events/create",
                                   json={"user_id": "u", "subject": "s"}
                                   ).status_code == 500
        osvc.create_calendar_event = AsyncMock(side_effect=RuntimeError("x"))
        assert outlook_client.post("/api/integrations/outlook/calendar/events/create",
                                   json={"user_id": "u", "subject": "s"}
                                   ).status_code == 500

    def test_contacts(self, outlook_client, osvc):
        osvc.get_user_contacts = AsyncMock(return_value=[{"id": "c"}])
        r = outlook_client.post("/api/integrations/outlook/contacts", json={"user_id": "u"})
        assert r.status_code == 200
        osvc.get_user_contacts = AsyncMock(side_effect=RuntimeError("x"))
        assert outlook_client.post("/api/integrations/outlook/contacts",
                                   json={"user_id": "u"}).status_code == 500
        osvc.create_contact = AsyncMock(return_value={"id": "c"})
        r = outlook_client.post("/api/integrations/outlook/contacts/create",
                                json={"user_id": "u", "display_name": "N"})
        assert r.status_code == 200
        osvc.create_contact = AsyncMock(return_value=None)
        assert outlook_client.post("/api/integrations/outlook/contacts/create",
                                   json={"user_id": "u", "display_name": "N"}
                                   ).status_code == 500
        osvc.create_contact = AsyncMock(side_effect=RuntimeError("x"))
        assert outlook_client.post("/api/integrations/outlook/contacts/create",
                                   json={"user_id": "u", "display_name": "N"}
                                   ).status_code == 500

    def test_tasks(self, outlook_client, osvc):
        osvc.get_user_tasks = AsyncMock(return_value=[{"id": "t"}])
        r = outlook_client.post("/api/integrations/outlook/tasks", json={"user_id": "u"})
        assert r.status_code == 200
        osvc.get_user_tasks = AsyncMock(side_effect=RuntimeError("x"))
        assert outlook_client.post("/api/integrations/outlook/tasks",
                                   json={"user_id": "u"}).status_code == 500
        osvc.create_task = AsyncMock(return_value={"id": "t"})
        r = outlook_client.post("/api/integrations/outlook/tasks/create",
                                json={"user_id": "u", "subject": "s"})
        assert r.status_code == 200
        osvc.create_task = AsyncMock(return_value=None)
        assert outlook_client.post("/api/integrations/outlook/tasks/create",
                                   json={"user_id": "u", "subject": "s"}
                                   ).status_code == 500
        osvc.create_task = AsyncMock(side_effect=RuntimeError("x"))
        assert outlook_client.post("/api/integrations/outlook/tasks/create",
                                   json={"user_id": "u", "subject": "s"}
                                   ).status_code == 500

    def test_search_and_profile(self, outlook_client, osvc):
        osvc.search_emails = AsyncMock(return_value=[1])
        r = outlook_client.post("/api/integrations/outlook/search",
                                json={"user_id": "u", "query": "q"})
        assert r.status_code == 200 and r.json()["query"] == "q"
        osvc.search_emails = AsyncMock(side_effect=RuntimeError("x"))
        assert outlook_client.post("/api/integrations/outlook/search",
                                   json={"user_id": "u", "query": "q"}
                                   ).status_code == 500
        osvc.get_user_profile = AsyncMock(return_value={"id": "u"})
        r = outlook_client.get("/api/integrations/outlook/profile", params={"user_id": "u"})
        assert r.status_code == 200
        osvc.get_user_profile = AsyncMock(return_value=None)
        # R80: GET/POST /profile now share a handler that falls back to a
        # synthesized current-user profile instead of 404ing on None.
        assert outlook_client.get("/api/integrations/outlook/profile",
                                  params={"user_id": "u"}).status_code == 200
        osvc.get_user_profile = AsyncMock(side_effect=RuntimeError("x"))
        assert outlook_client.get("/api/integrations/outlook/profile",
                                  params={"user_id": "u"}).status_code == 500

    def test_health(self, outlook_client):
        r = outlook_client.get("/api/integrations/outlook/health")
        assert r.status_code == 200 and r.json()["status"] == "healthy"

    def test_memory_backfill(self, outlook_client):
        with patch("integrations.outlook_integration.outlook_integration") as oi:
            oi.backfill_to_memory = AsyncMock(return_value={"job_id": "j1"})
            r = outlook_client.post("/api/integrations/outlook/memory/backfill",
                                    params={"start_date": "2026-01-01T00:00:00Z",
                                            "end_date": "2026-01-02",
                                            "limit": 10})
            assert r.status_code == 200 and r.json()["success"] is True
            oi.backfill_to_memory = AsyncMock(side_effect=RuntimeError("x"))
            assert outlook_client.post(
                "/api/integrations/outlook/memory/backfill").status_code == 500
        # invalid date -> 500
        assert outlook_client.post(
            "/api/integrations/outlook/memory/backfill",
            params={"start_date": "not-a-date"}).status_code == 500

    def test_backfill_status(self, outlook_client):
        with patch("core.memory_integration_mixin.MemoryIntegrationMixin"
                   ".get_job_status", return_value={"status": "running"}):
            r = outlook_client.get("/api/integrations/outlook/memory/backfill/status/j1")
            assert r.status_code == 200
        with patch("core.memory_integration_mixin.MemoryIntegrationMixin"
                   ".get_job_status", return_value=None):
            assert outlook_client.get(
                "/api/integrations/outlook/memory/backfill/status/j1").status_code == 404
        with patch("core.memory_integration_mixin.MemoryIntegrationMixin"
                   ".get_job_status", side_effect=RuntimeError("x")):
            assert outlook_client.get(
                "/api/integrations/outlook/memory/backfill/status/j1").status_code == 500


# ============================================================================
# integrations/figma_service.py
# ============================================================================

import integrations.figma_service as fig
from integrations.figma_service import FigmaService, get_figma_service


def _fig_svc(**cfg):
    return FigmaService(tenant_id="t1", config=dict(cfg))


class TestFigmaService:
    def test_init_and_helpers(self):
        svc = _fig_svc(access_token="tok", refresh_token="rt",
                       figma_client_id="ci")
        assert svc.base_url.endswith("/v1")
        assert svc._get_headers()["Authorization"] == "Bearer tok"
        assert svc._get_headers("other")["Authorization"] == "Bearer other"
        assert "state=st" in svc.get_authorization_url("st")
        assert "state=" in svc.get_authorization_url()
        assert svc.get_capabilities()["supports_webhooks"] is False
        status = svc.get_connection_status()
        assert status["has_access_token"] and status["has_refresh_token"]

    def test_token_validity(self):
        svc = _fig_svc()
        assert svc.is_token_valid() is False
        svc = _fig_svc(access_token="t")
        assert svc.is_token_valid() is True
        svc.token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        assert svc.is_token_valid() is False
        svc.token_expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
        assert svc.is_token_valid() is True

    async def test_ensure_valid_token(self):
        svc = _fig_svc()
        with pytest.raises(HTTPException) as ei:
            await svc.ensure_valid_token()
        assert ei.value.status_code == 401
        svc = _fig_svc(access_token="t", refresh_token="r")
        svc.token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        svc.refresh_access_token = AsyncMock()
        assert await svc.ensure_valid_token() == "t"
        svc.refresh_access_token.assert_awaited()
        svc2 = _fig_svc(access_token="t")
        assert await svc2.ensure_valid_token() == "t"

    async def test_exchange_token(self):
        svc = _fig_svc()
        svc.client.post = AsyncMock(return_value=_ok({
            "access_token": "at", "refresh_token": "rt", "expires_in": 100}))
        r = await svc.exchange_token("code")
        assert r["access_token"] == "at" and svc.access_token == "at"
        assert svc.token_expires_at is not None
        svc.client.post = AsyncMock(
            return_value=_hresp(500, {}))
        with patch.object(httpx.Response, "raise_for_status",
                          side_effect=httpx.HTTPError("x")):
            with pytest.raises(HTTPException):
                await svc.exchange_token("code")

    async def test_refresh_access_token(self):
        svc = _fig_svc()
        with pytest.raises(HTTPException):
            await svc.refresh_access_token()
        svc = _fig_svc(refresh_token="r")
        svc.client.post = AsyncMock(return_value=_ok(
            {"access_token": "at2", "refresh_token": "rt2"}))
        r = await svc.refresh_access_token()
        assert svc.access_token == "at2" and svc.refresh_token == "rt2"
        svc.client.post = AsyncMock(return_value=_hresp(500, {}))
        with patch.object(httpx.Response, "raise_for_status",
                          side_effect=httpx.HTTPError("x")):
            with pytest.raises(HTTPException):
                await svc.refresh_access_token()

    async def test_get_user_info(self):
        svc = _fig_svc()
        with pytest.raises(HTTPException) as ei:
            await svc.get_user_info()
        assert ei.value.status_code == 401
        svc = _fig_svc(access_token="t")
        svc.client.get = AsyncMock(return_value=_ok({"id": "me"}))
        assert (await svc.get_user_info())["id"] == "me"
        assert svc.user_info == {"id": "me"}
        svc.client.get = AsyncMock(return_value=_hresp(401, {}))
        with patch.object(httpx.Response, "raise_for_status",
                          side_effect=httpx.HTTPError("x")):
            with pytest.raises(HTTPException):
                await svc.get_user_info()

    async def test_getters_and_errors(self):
        svc = _fig_svc(access_token="t")
        cases = [
            ("get_file", (svc.get_file, ("fk",), {}, {"f": 1})),
            ("get_file_nodes", (svc.get_file_nodes, ("fk", ["1", "2"]), {},
                                {"nodes": {}})),
            ("get_team_projects", (svc.get_team_projects, ("tm",), {},
                                   {"projects": [{"id": "p"}]})),
            ("get_project_files", (svc.get_project_files, ("p",), {},
                                   {"files": [{"id": "f"}]})),
            ("get_comments", (svc.get_comments, ("fk",), {}, {"comments": [1]})),
        ]
        for name, (meth, args, kw, payload) in cases:
            svc.client.get = AsyncMock(return_value=_ok(payload))
            assert await meth(*args, **kw) is not None, name
            svc.client.get = AsyncMock(return_value=_hresp(500, {}))
            with patch.object(httpx.Response, "raise_for_status",
                              side_effect=httpx.HTTPError("x")):
                with pytest.raises(HTTPException):
                    await meth(*args, **kw)

    async def test_search_files(self):
        svc = _fig_svc(access_token="t")
        assert await svc.search_files("", "tm") == []
        assert await svc.search_files("q", None) == []
        svc.get_team_projects = AsyncMock(
            return_value=[{"id": "p1"}, {"id": "p2"}])
        svc.get_project_files = AsyncMock(
            side_effect=[[{"name": "App Design"}], [{"name": "other"}]])
        r = await svc.search_files("design", "tm")
        assert len(r) == 1 and r[0]["project_id"] == "p1"

    def test_health_check(self):
        svc = _fig_svc()
        h = svc.health_check()
        assert h["healthy"] is False and h["ok"] is False
        svc = _fig_svc(access_token="t")
        with patch("requests.get", return_value=SimpleNamespace(status_code=200)):
            assert svc.health_check()["healthy"] is True
        with patch("requests.get", return_value=SimpleNamespace(status_code=500)):
            assert svc.health_check()["healthy"] is False
        with patch("requests.get", side_effect=RuntimeError("net")):
            h = svc.health_check()
            assert h["healthy"] is False and "error" in h

    async def test_execute_operation(self):
        svc = _fig_svc(access_token="t")
        svc.get_file = AsyncMock(return_value={"f": 1})
        assert (await svc.execute_operation(
            "get_file", {"file_key": "k"}))["success"] is True
        svc.get_file_nodes = AsyncMock(return_value={"n": 1})
        assert (await svc.execute_operation(
            "get_file_nodes", {"file_key": "k", "node_ids": ["1"]}))["success"]
        svc.get_team_projects = AsyncMock(return_value=[1])
        assert (await svc.execute_operation(
            "get_team_projects", {"team_id": "t"}))["success"]
        r = await svc.execute_operation("nope", {})
        assert r["success"] is False
        svc.get_file = AsyncMock(side_effect=RuntimeError("x"))
        assert (await svc.execute_operation(
            "get_file", {"file_key": "k"}))["success"] is False

    async def test_sync_and_full_sync(self, monkeypatch):
        svc = _fig_svc(access_token="t")
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        monkeypatch.setattr("core.database.SessionLocal",
                            MagicMock(return_value=db))
        assert (await svc.sync_to_postgres_cache("ws")) == \
            {"success": True, "metrics_synced": 1}
        db.query.return_value.filter_by.return_value.first.return_value = \
            MagicMock()
        assert (await svc.sync_to_postgres_cache("ws"))[
            "metrics_synced"] == 1
        db.commit = MagicMock(side_effect=RuntimeError("x"))
        assert (await svc.sync_to_postgres_cache("ws"))["success"] is False
        monkeypatch.setattr("core.database.SessionLocal",
                            MagicMock(side_effect=RuntimeError("x")))
        assert (await svc.sync_to_postgres_cache("ws"))["success"] is False
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True})
        r = await svc.full_sync("ws")
        assert r["success"] and r["workspace_id"] == "ws"

    async def test_close_and_singleton(self):
        svc = _fig_svc()
        svc.client.aclose = AsyncMock()
        await svc.close()
        svc.client.aclose.assert_awaited()
        s1 = get_figma_service()
        assert get_figma_service() is s1


# ============================================================================
# integrations/zendesk_service.py
# ============================================================================

import integrations.zendesk_service as zd
from integrations.zendesk_service import ZendeskService


def _zd_svc(**cfg):
    return ZendeskService(tenant_id="t1", config=dict(
        subdomain="acme", access_token="tok", **cfg))


class TestZendeskService:
    def test_init_and_static(self):
        svc = _zd_svc()
        assert svc.base_url.startswith("https://acme.")
        assert svc._get_headers("t")["Authorization"] == "Bearer t"
        assert svc.get_capabilities()["supports_webhooks"] is True
        url = svc.get_authorization_url("http://cb", state="st")
        assert "state=st" in url
        assert "state" not in svc.get_authorization_url("http://cb")

    async def test_close_and_health(self):
        svc = _zd_svc()
        svc.client.aclose = AsyncMock()
        await svc.close()
        assert (await svc.health_check())["ok"] is True

    async def test_exchange_token(self):
        svc = _zd_svc()
        svc.http.post = AsyncMock(return_value=_ok({"access_token": "nt"}))
        r = await svc.exchange_token("code", "http://cb")
        assert r["access_token"] == "nt" and svc.access_token == "nt"
        svc.http.post = AsyncMock(return_value=_hresp(500, {}))
        with patch.object(httpx.Response, "raise_for_status",
                          side_effect=httpx.HTTPError("x")):
            with pytest.raises(HTTPException):
                await svc.exchange_token("code", "http://cb")

    async def test_get_tickets(self):
        svc = _zd_svc()
        svc.http.get = AsyncMock(return_value=_ok({"tickets": [{"id": 1}]}))
        assert await svc.get_tickets() == [{"id": 1}]
        assert await svc.get_tickets(access_token="x", per_page=5,
                                     sort_by="status", sort_order="asc") == [{"id": 1}]
        bare = ZendeskService(tenant_id="t", config={"subdomain": "a"})
        with pytest.raises(HTTPException) as ei:
            await bare.get_tickets()
        assert ei.value.status_code == 401
        svc.http.get = AsyncMock(return_value=_hresp(500, {}))
        with patch.object(httpx.Response, "raise_for_status",
                          side_effect=httpx.HTTPError("x")):
            with pytest.raises(HTTPException):
                await svc.get_tickets()

    async def test_get_ticket(self):
        svc = _zd_svc()
        svc.http.get = AsyncMock(return_value=_ok({"ticket": {"id": 7}}))
        assert await svc.get_ticket(7) == {"id": 7}
        bare = ZendeskService(tenant_id="t", config={"subdomain": "a"})
        with pytest.raises(HTTPException):
            await bare.get_ticket(7)
        svc.http.get = AsyncMock(return_value=_hresp(404, {}))
        with patch.object(httpx.Response, "raise_for_status",
                          side_effect=httpx.HTTPError("x")):
            with pytest.raises(HTTPException):
                await svc.get_ticket(7)

    async def test_create_ticket(self):
        svc = _zd_svc()
        svc.http.post = AsyncMock(return_value=_ok({"ticket": {"id": 1}}))
        r = await svc.create_ticket("sub", "body", priority="urgent",
                                    requester_name="N", requester_email="e@x")
        assert r["id"] == 1
        svc.http.post = AsyncMock(return_value=_hresp(422, {}))
        with patch.object(httpx.Response, "raise_for_status",
                          side_effect=httpx.HTTPError("x")):
            with pytest.raises(HTTPException):
                await svc.create_ticket("s", "b")
        bare = ZendeskService(tenant_id="t", config={"subdomain": "a"})
        with pytest.raises(HTTPException):
            await bare.create_ticket("s", "b")

    async def test_search_and_users(self):
        svc = _zd_svc()
        svc.http.get = AsyncMock(return_value=_ok({"results": [1]}))
        assert await svc.search_tickets("broken") == [1]
        svc.http.get = AsyncMock(return_value=_ok({"users": [2]}))
        assert await svc.get_users() == [2]
        bare = ZendeskService(tenant_id="t", config={"subdomain": "a"})
        with pytest.raises(HTTPException):
            await bare.search_tickets("q")
        with pytest.raises(HTTPException):
            await bare.get_users()
        svc.http.get = AsyncMock(return_value=_hresp(500, {}))
        with patch.object(httpx.Response, "raise_for_status",
                          side_effect=httpx.HTTPError("x")):
            with pytest.raises(HTTPException):
                await svc.search_tickets("q")
            with pytest.raises(HTTPException):
                await svc.get_users()

    async def test_execute_operation(self):
        svc = _zd_svc()
        svc.get_tickets = AsyncMock(return_value=[1])
        assert (await svc.execute_operation("get_tickets", {}))["success"]
        svc.get_ticket = AsyncMock(return_value={"id": 1})
        assert (await svc.execute_operation(
            "get_ticket", {"ticket_id": 1}))["success"]
        svc.create_ticket = AsyncMock(return_value={"id": 1})
        assert (await svc.execute_operation(
            "create_ticket", {"subject": "s", "comment_body": "b"}))["success"]
        svc.search_tickets = AsyncMock(return_value=[1])
        assert (await svc.execute_operation(
            "search_tickets", {"query": "q"}))["success"]
        svc.get_users = AsyncMock(return_value=[1])
        assert (await svc.execute_operation("get_users", {}))["success"]
        r = await svc.execute_operation("nope", {})
        assert r["success"] is False
        svc.get_tickets = AsyncMock(side_effect=RuntimeError("x"))
        r = await svc.execute_operation("get_tickets", {})
        assert r["success"] is False


# ============================================================================
# integrations/chat_routes.py
# ============================================================================

from integrations import chat_routes as cr


@pytest.fixture
def chat_app():
    app = FastAPI()
    app.include_router(cr.router)
    return app


@pytest.fixture
def chat_client(chat_app):
    chat_app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="user_1", tenant_id="t1")
    return TestClient(chat_app)


@pytest.fixture
def orch():
    with patch.object(cr, "chat_orchestrator") as m:
        m.session_manager = MagicMock()
        yield m


def _chat_session(sid="s1", owner="user_1"):
    return {"id": sid, "session_id": sid, "user_id": owner, "title": "T",
            "created_at": "2026-01-01", "last_updated": "2026-01-02",
            "history": [], "context": {}}


class TestChatAuth:
    @pytest.mark.parametrize("method,path,kwargs", [
        ("patch", "/api/chat/sessions/s1", {"json": {"title": "x", "user_id": "u"}}),
        ("get", "/api/chat/sessions/s1", {"params": {"user_id": "u"}}),
        ("post", "/api/chat/message", {"json": {"message": "hi", "user_id": "u"}}),
        ("post", "/api/chat/cancel/s1", {}),
        ("post", "/api/chat/feedback",
         {"json": {"message_id": "m", "feedback": "thumbs_up"}}),
        ("get", "/api/chat/routing-stats", {}),
        ("get", "/api/chat/harness-evolution", {}),
        ("get", "/api/chat/history/s1", {"params": {"user_id": "u"}}),
        ("get", "/api/chat/sessions", {"params": {"user_id": "u"}}),
    ])
    def test_anonymous_rejected(self, chat_app, method, path, kwargs):
        c = TestClient(chat_app)
        assert getattr(c, method)(path, **kwargs).status_code == 401


class TestChatRenameSession:
    def test_success(self, chat_client, orch):
        orch.conversation_sessions = {"s1": _chat_session()}
        orch.rename_session.return_value = True
        r = chat_client.patch("/api/chat/sessions/s1",
                              json={"title": "New", "user_id": "u"})
        assert r.status_code == 200 and r.json()["title"] == "New"

    def test_not_found(self, chat_client, orch):
        orch.conversation_sessions = {}
        orch.session_manager.get_session.return_value = None
        assert chat_client.patch(
            "/api/chat/sessions/x",
            json={"title": "n", "user_id": "u"}).status_code == 404

    def test_lazy_managed(self, chat_client, orch):
        orch.conversation_sessions = {}
        orch.session_manager.get_session.return_value = _chat_session()
        orch.rename_session.return_value = True
        assert chat_client.patch(
            "/api/chat/sessions/s1",
            json={"title": "n", "user_id": "u"}).status_code == 200

    def test_idor_denied(self, chat_client, orch):
        orch.conversation_sessions = {"s1": _chat_session(owner="other")}
        assert chat_client.patch(
            "/api/chat/sessions/s1",
            json={"title": "n", "user_id": "u"}).status_code == 403

    def test_legacy_reclaim_and_rollback(self, chat_client, orch):
        orch.conversation_sessions = {"s1": _chat_session(owner="anonymous")}
        orch.session_manager.rebind_session_owner.return_value = True
        orch.rename_session.return_value = True
        assert chat_client.patch(
            "/api/chat/sessions/s1",
            json={"title": "n", "user_id": "u"}).status_code == 200
        # rollback: durable rebind fails -> 403 and owner restored
        orch.conversation_sessions = {"s2": _chat_session(sid="s2",
                                                          owner="guest")}
        orch.session_manager.rebind_session_owner.return_value = False
        assert chat_client.patch(
            "/api/chat/sessions/s2",
            json={"title": "n2", "user_id": "u"}).status_code == 403
        assert orch.conversation_sessions["s2"]["user_id"] == "guest"

    def test_rename_failed_and_500(self, chat_client, orch):
        orch.conversation_sessions = {"s1": _chat_session()}
        orch.session_manager.rename_session.return_value = False
        assert chat_client.patch(
            "/api/chat/sessions/s1",
            json={"title": "n", "user_id": "u"}).status_code == 404
        orch.session_manager.rename_session.side_effect = RuntimeError("x")
        assert chat_client.patch(
            "/api/chat/sessions/s1",
            json={"title": "n", "user_id": "u"}).status_code == 500


class TestChatSessionDetails:
    def test_success(self, chat_client, orch):
        orch.conversation_sessions = {"s1": _chat_session()}
        r = chat_client.get("/api/chat/sessions/s1", params={"user_id": "u"})
        assert r.status_code == 200 and r.json()["session_id"] == "s1"

    def test_not_found_and_lazy(self, chat_client, orch):
        orch.conversation_sessions = {}
        orch.session_manager.get_session.return_value = None
        assert chat_client.get("/api/chat/sessions/x",
                               params={"user_id": "u"}).status_code == 404
        orch.session_manager.get_session.return_value = _chat_session()
        assert chat_client.get("/api/chat/sessions/s1",
                               params={"user_id": "u"}).status_code == 200

    def test_denied_and_500(self, chat_client, orch):
        orch.conversation_sessions = {"s1": _chat_session(owner="other")}
        assert chat_client.get("/api/chat/sessions/s1",
                               params={"user_id": "u"}).status_code == 403

        class Boom(dict):
            def get(self, *a, **k):
                raise RuntimeError("x")

        orch.conversation_sessions = Boom()
        assert chat_client.get("/api/chat/sessions/s1",
                               params={"user_id": "u"}).status_code == 500


class TestChatMessage:
    def test_success(self, chat_client, orch):
        orch.process_chat_message = AsyncMock(return_value={
            "success": True, "message": "hi there", "session_id": "s1",
            "intent": "chat", "confidence": 0.9, "suggested_actions": [],
            "requires_confirmation": False, "next_steps": [],
            "timestamp": "ts", "data": {"a": 1}, "model": "m", "provider": "p"})
        r = chat_client.post("/api/chat/message",
                             json={"message": "q", "user_id": "u",
                                   "session_id": "s1"})
        assert r.status_code == 200
        body = r.json()
        assert body["session_id"] == "s1" and body["metadata"] == {"a": 1}

    def test_new_session_and_override_headers(self, chat_client, orch):
        orch.process_chat_message = AsyncMock(return_value={
            "message": "ok", "session_id": "fresh", "success": True})
        with patch.object(cr, "parse_routing_overrides",
                          return_value={"tier": "advanced"}):
            r = chat_client.post("/api/chat/message",
                                 json={"message": "q", "user_id": "u",
                                       "session_id": "new"},
                                 headers={"x-atom-tier": "advanced"})
        assert r.status_code == 200
        kwargs = orch.process_chat_message.call_args[1]
        assert kwargs["session_id"] is None
        assert kwargs["routing_overrides"] is not None

    def test_override_parse_failure(self, chat_client, orch):
        orch.process_chat_message = AsyncMock(return_value={"message": "ok"})
        with patch.object(cr, "parse_routing_overrides",
                          side_effect=RuntimeError("bad headers")):
            r = chat_client.post("/api/chat/message",
                                 json={"message": "q", "user_id": "u"})
        assert r.status_code == 200
        assert orch.process_chat_message.call_args[1][
            "routing_overrides"] is None

    def test_no_provider_sentinel(self, chat_client, orch):
        orch.process_chat_message = AsyncMock(return_value={
            "message": "LLM client not initialized", "session_id": "s1"})
        r = chat_client.post("/api/chat/message",
                             json={"message": "q", "user_id": "u"})
        body = r.json()
        assert body["error_code"] == "no_llm_provider"
        assert body["recovery_url"] == "/settings/ai"

    def test_budget_exceeded(self, chat_client, orch):
        orch.process_chat_message = AsyncMock(return_value={
            "message": "Budget limit reached", "session_id": "s1",
            "error_code": "budget_exceeded", "recovery_url": "/billing"})
        r = chat_client.post("/api/chat/message",
                             json={"message": "q", "user_id": "u"})
        body = r.json()
        assert body["error_code"] == "budget_exceeded"
        assert body["recovery_url"] == "/billing"

    def test_exception_500(self, chat_client, orch):
        orch.process_chat_message = AsyncMock(side_effect=RuntimeError("x"))
        r = chat_client.post("/api/chat/message",
                             json={"message": "q", "user_id": "u"})
        assert r.status_code == 500


class TestChatCancel:
    def test_cancel(self, chat_client, orch):
        orch.request_cancellation = MagicMock()
        r = chat_client.post("/api/chat/cancel/s1")
        assert r.status_code == 200 and r.json()["cancelled"] is True
        orch.request_cancellation.assert_called_once_with("s1")


class TestChatFeedback:
    def test_invalid_value(self, chat_client):
        r = chat_client.post("/api/chat/feedback",
                             json={"message_id": "m", "feedback": "meh"})
        assert r.status_code == 422

    def test_router_disabled(self, chat_client):
        with patch.object(cr, "_get_learning_router", return_value=None):
            r = chat_client.post("/api/chat/feedback",
                                 json={"message_id": "m",
                                       "feedback": "thumbs_up"})
        assert r.json() == {"success": True, "recorded": False,
                            "reason": "learning_router_disabled"}

    def test_thumbs_up(self, chat_client):
        router = MagicMock()
        router.resolve_feedback_context.return_value = ("coding", "rid")
        router.record_feedback = AsyncMock()
        fake_fb = object()
        with patch.object(cr, "_get_learning_router", return_value=router), \
             patch("core.learning_llm_router.LearningBasedRouter") as lbr:
            lbr.build_feedback.return_value = fake_fb
            r = chat_client.post("/api/chat/feedback", json={
                "message_id": "m", "feedback": "thumbs_up", "model": "gpt-x"})
        assert r.json()["recorded"] is True
        lbr.build_feedback.assert_called_once()
        kwargs = lbr.build_feedback.call_args[1]
        assert kwargs["task_type"] == "coding"
        assert kwargs["routing_result_id"] == "rid"
        router.record_feedback.assert_awaited_once_with(fake_fb)

    def test_thumbs_down_with_comment(self, chat_client):
        router = MagicMock()
        router.resolve_feedback_context.return_value = (None, None)
        router.record_feedback = AsyncMock()
        with patch.object(cr, "_get_learning_router", return_value=router), \
             patch("core.learning_llm_router.LearningBasedRouter") as lbr:
            lbr.build_feedback.return_value = object()
            r = chat_client.post("/api/chat/feedback", json={
                "message_id": "m", "feedback": "thumbs_down",
                "comment": "bad", "model": None})
        assert r.json()["recorded"] is True
        kwargs = lbr.build_feedback.call_args[1]
        assert kwargs["task_type"] == "question_answering"
        assert kwargs["model_id"] == "unknown"

    def test_recording_failure(self, chat_client):
        router = MagicMock()
        router.resolve_feedback_context.return_value = (None, None)
        router.record_feedback = AsyncMock(side_effect=RuntimeError("db"))
        with patch.object(cr, "_get_learning_router", return_value=router), \
             patch("core.learning_llm_router.LearningBasedRouter") as lbr:
            lbr.build_feedback.return_value = object()
            r = chat_client.post("/api/chat/feedback",
                                 json={"message_id": "m",
                                       "feedback": "thumbs_up"})
        body = r.json()
        assert body["recorded"] is False and "db" in body["reason"]


class TestRoutingStats:
    def test_disabled(self, chat_client):
        with patch.object(cr, "_learning_router_enabled", return_value=False), \
             patch.object(cr, "_ema_router_enabled", return_value=False):
            r = chat_client.get("/api/chat/routing-stats")
        assert r.json()["enabled"] is False

    def test_enabled_no_router(self, chat_client):
        with patch.object(cr, "_learning_router_enabled", return_value=True), \
             patch.object(cr, "_ema_router_enabled", return_value=True), \
             patch.object(cr, "_get_learning_router", return_value=None):
            r = chat_client.get("/api/chat/routing-stats")
        assert r.json()["enabled"] is True

    def test_stats_and_error(self, chat_client):
        router = MagicMock()
        router.get_routing_statistics = AsyncMock(
            return_value={"feedback_samples": 3})
        with patch.object(cr, "_learning_router_enabled", return_value=True), \
             patch.object(cr, "_ema_router_enabled", return_value=False), \
             patch.object(cr, "_get_learning_router", return_value=router):
            r = chat_client.get("/api/chat/routing-stats")
            assert r.json()["stats"]["feedback_samples"] == 3
            router.get_routing_statistics = AsyncMock(
                side_effect=RuntimeError("x"))
            r = chat_client.get("/api/chat/routing-stats")
            assert "error" in r.json()["stats"]


class TestHarnessEvolution:
    def test_harness_evolution(self, chat_client):
        db = MagicMock()
        agent = SimpleNamespace(
            id="a1", name="Agent",
            configuration={"harness_patches": [{
                "patch_id": "p1", "target_component": "c",
                "mutation_payload": {}, "model_scope": "all"}]})
        db.query.return_value.filter.return_value.all.return_value = [agent]
        svc = MagicMock()
        svc.mine_weaknesses = AsyncMock(return_value=[{"w": 1}])
        with patch("core.database.get_db", return_value=iter([db])), \
             patch("core.harness_evolution_service.HarnessEvolutionService",
                   return_value=svc):
            r = chat_client.get("/api/chat/harness-evolution")
        body = r.json()
        assert body["success"] is True
        assert body["mined_weaknesses"] == [{"w": 1}]
        assert body["active_patches"][0]["patch_id"] == "p1"

    def test_mining_and_patches_failures(self, chat_client):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.side_effect = \
            RuntimeError("q")
        svc = MagicMock()
        svc.mine_weaknesses = AsyncMock(side_effect=RuntimeError("m"))
        with patch("core.database.get_db", return_value=iter([db])), \
             patch("core.harness_evolution_service.HarnessEvolutionService",
                   return_value=svc):
            r = chat_client.get("/api/chat/harness-evolution")
        body = r.json()
        assert body["success"] is True
        assert body["mined_weaknesses"] == [] and body["active_patches"] == []


class TestChatHistoryAndSessions:
    def test_history_in_memory(self, chat_client, orch):
        s = _chat_session()
        s["history"] = [{"message": "hi"}]
        orch.conversation_sessions = {"s1": s}
        # Durable store is read FIRST now — mock an empty DB so the
        # in-memory fallback engages instead of reading ambient rows.
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value \
            .all.return_value = []

        class _Empty:
            def __enter__(self):
                return db

            def __exit__(self, *a):
                return False

        with patch("core.database.get_db_session", return_value=_Empty()):
            r = chat_client.get("/api/chat/history/s1", params={"user_id": "u"})
        assert r.status_code == 200 and r.json()["messages"] == [{"message": "hi"}]

    def test_history_lazy_and_db_fallback(self, chat_client, orch):
        orch.conversation_sessions = {}
        lazy = _chat_session()
        orch._get_or_create_session = MagicMock(return_value=lazy)
        row_user = SimpleNamespace(id="m1", role="user", content="q",
                                   created_at=datetime(2026, 1, 1))
        row_asst = SimpleNamespace(id="m2", role="assistant", content="a",
                                   created_at=datetime(2026, 1, 1))
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value \
            .all.return_value = [row_user, row_asst]

        class _Ctx:
            def __enter__(self):
                return db

            def __exit__(self, *a):
                return False

        with patch("core.database.get_db_session", return_value=_Ctx()):
            r = chat_client.get("/api/chat/history/s1", params={"user_id": "u"})
        msgs = r.json()["messages"]
        assert msgs[0]["message"] == "q"
        assert msgs[1]["response"] == {"message": "a"}
        # DB fallback blows up -> warning swallowed, empty history
        with patch("core.database.get_db_session",
                   side_effect=RuntimeError("db")):
            r = chat_client.get("/api/chat/history/s1", params={"user_id": "u"})
        assert r.status_code == 200 and r.json()["messages"] == []

    def test_history_denied_and_500(self, chat_client, orch):
        orch.conversation_sessions = {"s1": _chat_session(owner="other")}
        assert chat_client.get("/api/chat/history/s1",
                               params={"user_id": "u"}).status_code == 403
        orch._get_or_create_session = MagicMock(side_effect=RuntimeError("x"))
        orch.conversation_sessions = {}
        assert chat_client.get("/api/chat/history/s1",
                               params={"user_id": "u"}).status_code == 500

    def test_sessions_list(self, chat_client, orch):
        orch.get_user_sessions = MagicMock(
            return_value={"s1": _chat_session()})
        r = chat_client.get("/api/chat/sessions", params={"user_id": "u"})
        assert r.status_code == 200 and r.json()["total_sessions"] == 1
        orch.get_user_sessions = MagicMock(side_effect=RuntimeError("x"))
        assert chat_client.get("/api/chat/sessions",
                               params={"user_id": "u"}).status_code == 500

    def test_chat_memory_helper(self, orch):
        # get_chat_memory is defined but not routed; call it directly
        s = _chat_session()
        s["context"] = {"k": "v"}
        orch.conversation_sessions.__contains__ = lambda _, k: k == "s1"
        orch.conversation_sessions.__getitem__ = lambda _, k: s
        user = SimpleNamespace(id="user_1")
        import asyncio
        resp = asyncio.run(cr.get_chat_memory("s1", "u", current_user=user))
        assert resp.memory_context == {"k": "v"}
        # 404 branch
        orch2 = MagicMock()
        orch2.conversation_sessions = {}
        with patch.object(cr, "chat_orchestrator", orch2):
            with pytest.raises(HTTPException) as ei:
                asyncio.run(cr.get_chat_memory("nope", "u", current_user=user))
            assert ei.value.status_code == 404
        # 403 branch
        orch3 = MagicMock()
        orch3.conversation_sessions = {"s1": _chat_session(owner="other")}
        with patch.object(cr, "chat_orchestrator", orch3):
            with pytest.raises(HTTPException) as ei:
                asyncio.run(cr.get_chat_memory("s1", "u", current_user=user))
            assert ei.value.status_code == 403

    def test_health_and_root(self, chat_app):
        c = TestClient(chat_app)
        r = c.get("/api/chat/health")
        assert r.status_code == 200 and r.json()["service"] == "atom_chat_system"
        r = c.get("/api/chat/")
        assert r.status_code == 200 and r.json()["service"] == "chat_integration"

    def test_health_degraded_and_unhealthy(self, chat_app):
        c = TestClient(chat_app)
        real = cr.chat_orchestrator
        with patch.object(real, "feature_handlers", {}):
            r = c.get("/api/chat/health")
            assert r.json()["status"] == "degraded"

        class Boom:
            def __len__(self):
                raise RuntimeError("x")

        with patch.object(real, "feature_handlers", Boom()):
            r = c.get("/api/chat/health")
            assert r.json()["status"] == "unhealthy"


# ============================================================================
# integrations/zoho_inventory_service.py
# ============================================================================

import integrations.zoho_inventory_service as zis
from integrations.zoho_inventory_service import (
    ZohoInventoryService,
    get_zoho_inventory_service,
)


def _zo_svc(**cfg):
    base = {"access_token": "tok", "organization_id": "org1"}
    base.update(cfg)
    return ZohoInventoryService(tenant_id="t1", config=base)


class TestZohoInventory:
    def test_static(self):
        svc = _zo_svc()
        assert svc.get_capabilities()["supports_webhooks"] is False
        h = svc.health_check()
        assert h["healthy"] is True
        assert ZohoInventoryService(
            tenant_id="t", config={}).health_check()["healthy"] is False
        assert get_zoho_inventory_service({"client_id": "c"}).client_id == "c"
        assert isinstance(zis.zoho_inventory_service, ZohoInventoryService)

    async def test_get_items(self):
        svc = _zo_svc()
        svc.client.get = AsyncMock(return_value=_ok({"items": [{"sku": "s"}]}))
        assert await svc.get_items() == [{"sku": "s"}]
        svc.client.get = AsyncMock(return_value=_hresp(500, {}))
        with patch.object(httpx.Response, "raise_for_status",
                          side_effect=httpx.HTTPError("x")):
            assert await svc.get_items() == []
        with pytest.raises(HTTPException):
            await _zo_svc(access_token=None).get_items()
        with pytest.raises(HTTPException):
            await _zo_svc(organization_id=None).get_items()

    async def test_check_stock(self):
        svc = _zo_svc()
        svc.client.get = AsyncMock(return_value=_ok({"item": {
            "name": "Widget", "stock_on_hand": 5, "available_stock": 4}}))
        r = await svc.check_stock("i1")
        assert r["stock_on_hand"] == 5 and r["name"] == "Widget"
        svc.client.get = AsyncMock(side_effect=RuntimeError("net"))
        assert (await svc.check_stock("i1"))["error"] == "Failed to check stock"
        with pytest.raises(HTTPException):
            await _zo_svc(access_token=None).check_stock("i1")
        with pytest.raises(HTTPException):
            await _zo_svc(organization_id=None).check_stock("i1")

    async def test_get_inventory_levels(self):
        svc = _zo_svc()
        svc.get_items = AsyncMock(return_value=[
            {"sku": "s1", "name": "A", "stock_on_hand": 3}])
        r = await svc.get_inventory_levels()
        assert r == [{"sku": "s1", "name": "A", "available": 3,
                      "platform": "zoho"}]
        svc.get_items = AsyncMock(side_effect=RuntimeError("x"))
        assert await svc.get_inventory_levels() == []

    async def test_refresh_token(self):
        svc = _zo_svc()
        svc.client.post = AsyncMock(
            return_value=_ok({"access_token": "nt", "expires_in": 3600}))
        assert (await svc.refresh_token("r"))["access_token"] == "nt"
        svc.client.post = AsyncMock(side_effect=RuntimeError("x"))
        assert await svc.refresh_token("r") is None

    async def test_get_active_token_no_tenant(self):
        svc = _zo_svc()
        svc.tenant_id = None
        svc.session_id = None
        assert await svc._get_active_token(None) == "tok"
        svc2 = ZohoInventoryService(tenant_id=None, config={})
        svc2.session_id = None
        with patch.dict("os.environ", {"ZOHO_INVENTORY_ACCESS_TOKEN": "envt"}):
            assert await svc2._get_active_token(None) == "envt"

    async def test_get_active_token_db_paths(self, monkeypatch):
        svc = _zo_svc()
        # no record
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        monkeypatch.setattr("core.database.SessionLocal",
                            MagicMock(return_value=db))
        assert await svc._get_active_token("t1") is None
        # valid unexpired token -> decrypted
        rec = SimpleNamespace(
            access_token="enc", refresh_token=None,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        db2 = MagicMock()
        db2.query.return_value.filter.return_value.first.return_value = rec
        monkeypatch.setattr("core.database.SessionLocal",
                            MagicMock(return_value=db2))
        with patch("core.privsec.token_encryption.decrypt_token",
                   return_value="dec") as d:
            assert await svc._get_active_token("t1") == "dec"
            d.assert_called_once()
        # naive expires_at normalized
        rec2 = SimpleNamespace(
            access_token="enc", refresh_token=None,
            expires_at=datetime.utcnow() + timedelta(hours=1))
        db2.query.return_value.filter.return_value.first.return_value = rec2
        with patch("core.privsec.token_encryption.decrypt_token",
                   return_value="dec"):
            assert await svc._get_active_token("t1") == "dec"
        # expired with refresh_token -> refresh flow succeeds and commits
        rec3 = SimpleNamespace(
            access_token="enc", refresh_token="renc",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1))
        db2.query.return_value.filter.return_value.first.return_value = rec3
        svc.refresh_token = AsyncMock(
            return_value={"access_token": "new", "expires_in": 100})
        with patch("core.privsec.token_encryption.decrypt_token",
                   return_value="rplain"), \
             patch("core.privsec.token_encryption.encrypt_token",
                   return_value="enc2"), \
             patch("core.privsec.token_encryption.stamp_credential_metadata"):
            tok = await svc._get_active_token("t1")
        assert tok == "enc2"
        assert db2.commit.called
        # expired without refresh token -> None
        rec3.refresh_token = None
        assert await svc._get_active_token("t1") is None
        # refresh returns nothing -> None
        rec3.refresh_token = "renc"
        svc.refresh_token = AsyncMock(return_value=None)
        with patch("core.privsec.token_encryption.decrypt_token",
                   return_value="rplain"):
            assert await svc._get_active_token("t1") is None
        # exception -> None
        monkeypatch.setattr("core.database.SessionLocal",
                            MagicMock(side_effect=RuntimeError("db")))
        assert await svc._get_active_token("t1") is None

    async def test_execute_operation(self):
        svc = _zo_svc()
        svc.get_items = AsyncMock(return_value=[1])
        assert (await svc.execute_operation("get_items", {}))["success"]
        svc.get_inventory_levels = AsyncMock(return_value=[1])
        assert (await svc.execute_operation("get_inventory_levels",
                                            {}))["success"]
        r = await svc.execute_operation("check_stock", {})
        assert r["success"] is False
        svc.get_items = AsyncMock(side_effect=RuntimeError("x"))
        assert (await svc.execute_operation("get_items", {}))["success"] is False

    async def test_sync_and_full_sync(self, monkeypatch):
        svc = _zo_svc()
        svc.get_items = AsyncMock(return_value=[1, 2])
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        monkeypatch.setattr("core.database.SessionLocal",
                            MagicMock(return_value=db))
        assert (await svc.sync_to_postgres_cache("u", "t", "o")) == \
            {"success": True, "metrics_synced": 1}
        db.query.return_value.filter_by.return_value.first.return_value = \
            MagicMock()
        assert (await svc.sync_to_postgres_cache("u", "t", "o"))[
            "metrics_synced"] == 1
        db.commit = MagicMock(side_effect=RuntimeError("x"))
        r = await svc.sync_to_postgres_cache("u", "t", "o")
        assert r["success"] is False and db.rollback.called
        svc.get_items = AsyncMock(side_effect=RuntimeError("x"))
        assert (await svc.sync_to_postgres_cache(
            "u", "t", "o"))["success"] is False
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True})
        r = await svc.full_sync("u", "t", "o")
        assert r["success"] and r["user_id"] == "u"


# ============================================================================
# integrations/freshdesk_routes.py
# ============================================================================

from integrations import freshdesk_routes as fr


@pytest.fixture
def fd_client():
    app = FastAPI()
    app.include_router(fr.router)
    # R80c: freshdesk data/write routes now require authentication.
    from core.auth import get_current_user
    user = MagicMock()
    user.id = "w95-fd-user"
    user.email = "fd@x.com"
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.fixture
def fd_svc():
    svc = MagicMock()
    svc.health_check = AsyncMock(
        return_value={"status": "healthy"})
    svc.get_tickets = AsyncMock(return_value=[{"id": 1}])
    svc.create_ticket = AsyncMock(return_value={"id": 2})
    svc.get_ticket = AsyncMock(return_value={"id": 3})
    svc.update_ticket = AsyncMock(return_value={"id": 4})
    svc.get_contacts = AsyncMock(return_value=[{"id": 5}])
    svc.get_agents = AsyncMock(return_value=[{"id": 6}])
    svc.search_tickets = AsyncMock(return_value=[{"id": 7}])
    with patch.object(fr, "get_freshdesk_service", return_value=svc):
        yield svc


class TestFreshdeskRoutes:
    def test_auth_url(self, fd_client):
        r = fd_client.get("/freshdesk/auth/url")
        assert r.status_code == 200 and "docs_url" in r.json()

    def test_status(self, fd_client):
        with patch.object(fr, "get_freshdesk_service", return_value=None):
            r = fd_client.get("/freshdesk/status")
            assert r.json()["configured"] is False
        with patch.object(fr, "get_freshdesk_service", return_value=MagicMock()):
            assert fd_client.get("/freshdesk/status").json()["configured"]

    def test_health(self, fd_client, fd_svc):
        r = fd_client.get("/freshdesk/health")
        assert r.status_code == 200 and r.json()["ok"] is True
        fd_svc.health_check = AsyncMock(side_effect=RuntimeError("x"))
        r = fd_client.get("/freshdesk/health")
        assert r.json()["ok"] is False and r.json()["status"] == "unhealthy"

    def test_tickets(self, fd_client, fd_svc):
        r = fd_client.get("/freshdesk/tickets", params={"page": 1, "per_page": 10,
                                                        "status": 2})
        assert r.status_code == 200 and r.json()["ok"] is True
        fd_svc.get_tickets = AsyncMock(side_effect=RuntimeError("x"))
        assert fd_client.get("/freshdesk/tickets").status_code == 500

    def test_create_ticket(self, fd_client, fd_svc):
        r = fd_client.post("/freshdesk/tickets", json={
            "subject": "s", "description": "d", "email": "a@b.c"})
        assert r.status_code == 200 and r.json()["ticket"]["id"] == 2
        fd_svc.create_ticket = AsyncMock(side_effect=RuntimeError("x"))
        assert fd_client.post("/freshdesk/tickets", json={
            "subject": "s", "description": "d", "email": "a@b.c"}
        ).status_code == 500

    def test_get_ticket(self, fd_client, fd_svc):
        r = fd_client.get("/freshdesk/tickets/3")
        assert r.status_code == 200
        fd_svc.get_ticket = AsyncMock(side_effect=RuntimeError("x"))
        assert fd_client.get("/freshdesk/tickets/3").status_code == 500

    def test_update_ticket(self, fd_client, fd_svc):
        r = fd_client.put("/freshdesk/tickets/3",
                          json={"status": 3, "priority": 2})
        assert r.status_code == 200
        fd_svc.update_ticket = AsyncMock(side_effect=RuntimeError("x"))
        assert fd_client.put("/freshdesk/tickets/3",
                             json={"status": 3}).status_code == 500

    def test_contacts_and_agents(self, fd_client, fd_svc):
        assert fd_client.get("/freshdesk/contacts").status_code == 200
        fd_svc.get_contacts = AsyncMock(side_effect=RuntimeError("x"))
        assert fd_client.get("/freshdesk/contacts").status_code == 500
        assert fd_client.get("/freshdesk/agents").status_code == 200
        fd_svc.get_agents = AsyncMock(side_effect=RuntimeError("x"))
        assert fd_client.get("/freshdesk/agents").status_code == 500

    def test_search(self, fd_client, fd_svc):
        r = fd_client.post("/freshdesk/search/tickets", json={"query": "q"})
        assert r.status_code == 200 and r.json()["query"] == "q"
        fd_svc.search_tickets = AsyncMock(side_effect=RuntimeError("x"))
        assert fd_client.post("/freshdesk/search/tickets",
                              json={"query": "q"}).status_code == 500

    @pytest.mark.parametrize("method,path,kwargs", [
        ("get", "/freshdesk/tickets", {}),
        ("post", "/freshdesk/tickets",
         {"json": {"subject": "s", "description": "d", "email": "a@b.c"}}),
        ("get", "/freshdesk/tickets/1", {}),
        ("put", "/freshdesk/tickets/1", {"json": {"status": 3}}),
        ("get", "/freshdesk/contacts", {}),
        ("get", "/freshdesk/agents", {}),
        ("post", "/freshdesk/search/tickets", {"json": {"query": "q"}}),
    ])
    def test_not_configured_503(self, fd_client, method, path, kwargs):
        with patch.object(fr, "get_freshdesk_service", return_value=None):
            r = getattr(fd_client, method)(path, **kwargs)
            assert r.status_code == 503, f"{method} {path}"


# ============================================================================
# integrations/zoom_service.py
# ============================================================================

from integrations.zoom_service import ZoomService


def _zoom_svc(**cfg):
    return ZoomService(tenant_id="t1", config=dict(
        client_id="ci", client_secret="cs", access_token="tok", **cfg))


class TestZoomService:
    def test_static(self):
        svc = _zoom_svc()
        assert svc._get_headers("t")["Authorization"] == "Bearer t"
        assert svc.get_capabilities()["supports_webhooks"] is True
        url = svc.get_authorization_url("http://cb", state="st")
        assert "state=st" in url
        assert "state" not in svc.get_authorization_url("http://cb")

    async def test_close_and_health(self):
        svc = _zoom_svc()
        svc.client.aclose = AsyncMock()
        await svc.close()
        assert (await svc.health_check())["healthy"] is True
        assert not (await ZoomService(tenant_id="t", config={})
                    .health_check())["healthy"]

    async def test_exchange_token(self):
        svc = _zoom_svc()
        svc.http.post = AsyncMock(return_value=_ok({"access_token": "nt"}))
        r = await svc.exchange_token("code", "http://cb")
        assert r["access_token"] == "nt" and svc.access_token == "nt"
        bare = ZoomService(tenant_id="t", config={})
        with pytest.raises(HTTPException) as ei:
            await bare.exchange_token("c", "http://cb")
        assert ei.value.status_code == 400
        svc.http.post = AsyncMock(return_value=_hresp(500, {}))
        with patch.object(httpx.Response, "raise_for_status",
                          side_effect=httpx.HTTPError("x")):
            with pytest.raises(HTTPException):
                await svc.exchange_token("code", "http://cb")

    async def test_get_user(self):
        svc = _zoom_svc()
        svc.http.get = AsyncMock(return_value=_ok({"id": "me"}))
        assert await svc.get_user() == {"id": "me"}
        bare = ZoomService(tenant_id="t", config={})
        with pytest.raises(HTTPException):
            await bare.get_user()
        svc.http.get = AsyncMock(return_value=_hresp(404, {}))
        with patch.object(httpx.Response, "raise_for_status",
                          side_effect=httpx.HTTPError("x")):
            with pytest.raises(HTTPException):
                await svc.get_user()

    async def test_list_meetings(self):
        svc = _zoom_svc()
        svc.http.get = AsyncMock(return_value=_ok({"meetings": [1]}))
        assert await svc.list_meetings() == {"meetings": [1]}
        bare = ZoomService(tenant_id="t", config={})
        with pytest.raises(HTTPException):
            await bare.list_meetings()
        svc.http.get = AsyncMock(return_value=_hresp(500, {}))
        with patch.object(httpx.Response, "raise_for_status",
                          side_effect=httpx.HTTPError("x")):
            with pytest.raises(HTTPException):
                await svc.list_meetings()

    async def test_create_and_delete_meeting(self):
        svc = _zoom_svc()
        svc.http.post = AsyncMock(return_value=_ok({"id": 9}))
        r = await svc.create_meeting("T", start_time="2026-01-01T10:00:00Z",
                                     agenda="a", duration=30)
        assert r["id"] == 9
        svc.http.delete = AsyncMock(return_value=_hresp(204))
        assert (await svc.delete_meeting("9"))["ok"] is True
        bare = ZoomService(tenant_id="t", config={})
        with pytest.raises(HTTPException):
            await bare.create_meeting("T")
        with pytest.raises(HTTPException):
            await bare.delete_meeting("9")
        svc.http.post = AsyncMock(return_value=_hresp(500, {}))
        with patch.object(httpx.Response, "raise_for_status",
                          side_effect=httpx.HTTPError("x")):
            with pytest.raises(HTTPException):
                await svc.create_meeting("T")
            svc.http.delete = AsyncMock(return_value=_hresp(500, {}))
            with pytest.raises(HTTPException):
                await svc.delete_meeting("9")

    async def test_list_users_and_recordings(self):
        svc = _zoom_svc()
        svc.http.get = AsyncMock(return_value=_ok({"users": [1]}))
        assert await svc.list_users(status="pending", page_size=5,
                                    page_number=2) == {"users": [1]}
        svc.http.get = AsyncMock(return_value=_ok({"meetings": [1]}))
        assert await svc.list_recordings("me", from_date="2026-01-01",
                                         to_date="2026-01-31") == {"meetings": [1]}
        bare = ZoomService(tenant_id="t", config={})
        with pytest.raises(HTTPException):
            await bare.list_users()
        with pytest.raises(HTTPException):
            await bare.list_recordings()
        svc.http.get = AsyncMock(return_value=_hresp(500, {}))
        with patch.object(httpx.Response, "raise_for_status",
                          side_effect=httpx.HTTPError("x")):
            with pytest.raises(HTTPException):
                await svc.list_users()
            with pytest.raises(HTTPException):
                await svc.list_recordings()

    async def test_execute_operation(self):
        svc = _zoom_svc()
        svc.create_meeting = AsyncMock(return_value={"id": 1})
        assert (await svc.execute_operation(
            "create_meeting", {"topic": "T"}))["success"]
        svc.list_meetings = AsyncMock(return_value={})
        assert (await svc.execute_operation("list_meetings", {}))["success"]
        svc.delete_meeting = AsyncMock(return_value={"ok": True})
        assert (await svc.execute_operation(
            "delete_meeting", {"meeting_id": "1"}))["success"]
        svc.list_users = AsyncMock(return_value={})
        assert (await svc.execute_operation("list_users", {}))["success"]
        svc.list_recordings = AsyncMock(return_value={})
        assert (await svc.execute_operation("list_recordings", {}))["success"]
        r = await svc.execute_operation("nope", {})
        assert r["success"] is False
        svc.list_meetings = AsyncMock(side_effect=RuntimeError("x"))
        r = await svc.execute_operation("list_meetings", {})
        assert r["success"] is False


# ============================================================================
# integrations/whatsapp_service_manager.py
# ============================================================================

from integrations.whatsapp_service_manager import (
    WhatsAppServiceManager,
    get_whatsapp_service_metrics,
    get_whatsapp_service_status,
    initialize_whatsapp_service,
)


@pytest.fixture()
def manager():
    m = WhatsAppServiceManager()
    m.integration = MagicMock()
    return m


def _wa_demo_config():
    return {"access_token": "demo", "phone_number_id": "123",
            "status": "demo_configured"}


class TestWhatsAppManagerLoadConfig:
    def test_demo(self, manager):
        with patch("integrations.whatsapp_configuration_setup"
                   ".get_or_create_configuration",
                   return_value=_wa_demo_config()), \
             patch("integrations.whatsapp_configuration_setup"
                   ".validate_configuration",
                   return_value={"is_demo": True, "is_valid": False,
                                 "missing_required": [], "errors": [],
                                 "warnings": [], "configuration_type":
                                 "demo"}):
            cfg = manager.load_configuration()
        assert cfg["service_manager"] is True
        assert cfg["validation"]["is_demo"] is True
        assert manager.config is cfg

    def test_valid(self, manager):
        with patch("integrations.whatsapp_configuration_setup"
                   ".get_or_create_configuration",
                   return_value=dict(_wa_demo_config(), status="configured")), \
             patch("integrations.whatsapp_configuration_setup"
                   ".validate_configuration",
                   return_value={"is_demo": False, "is_valid": True,
                                 "missing_required": [], "errors": [],
                                 "warnings": [], "configuration_type":
                                 "real"}):
            cfg = manager.load_configuration()
        assert cfg["validation"]["is_valid"] is True

    def test_incomplete(self, manager):
        with patch("integrations.whatsapp_configuration_setup"
                   ".get_or_create_configuration",
                   return_value=dict(_wa_demo_config(), status="configured")), \
             patch("integrations.whatsapp_configuration_setup"
                   ".validate_configuration",
                   return_value={"is_demo": False, "is_valid": False,
                                 "missing_required": ["access_token"],
                                 "errors": [], "warnings": [],
                                 "configuration_type": "real"}):
            manager.load_configuration()

    def test_exception_fallback(self, manager):
        with patch("integrations.whatsapp_configuration_setup"
                   ".get_or_create_configuration",
                   side_effect=RuntimeError("boom")), \
             patch("integrations.whatsapp_configuration_setup"
                   ".setup_demo_configuration",
                   return_value=_wa_demo_config()) as demo:
            cfg = manager.load_configuration()
        assert cfg["validation"]["is_demo"] is True
        demo.assert_called_once()


class TestWhatsAppManagerInit:
    def test_error_status(self, manager):
        manager.load_configuration = MagicMock(
            return_value={"status": "error", "error": "bad"})
        r = manager.initialize_service()
        assert r["success"] is False and r["status"] == "configuration_error"

    def test_incomplete_status(self, manager):
        manager.load_configuration = MagicMock(
            return_value={"status": "incomplete"})
        r = manager.initialize_service()
        assert r["status"] == "incomplete_configuration"

    def test_success(self, manager):
        manager.load_configuration = MagicMock(return_value={
            "status": "configured", "features": {"auto_reply_enabled": True}})
        manager.integration.initialize = MagicMock(return_value=True)
        manager._register_with_service_registry = MagicMock()
        r = manager.initialize_service()
        assert r["success"] is True and manager.status == "connected"
        manager._register_with_service_registry.assert_called_once()

    def test_init_failure(self, manager):
        manager.load_configuration = MagicMock(
            return_value={"status": "configured"})
        manager.integration.initialize = MagicMock(return_value=False)
        r = manager.initialize_service()
        assert r["success"] is False and manager.status == "failed"

    def test_init_exception(self, manager):
        manager.load_configuration = MagicMock(
            side_effect=RuntimeError("x"))
        r = manager.initialize_service()
        assert r["success"] is False and r["status"] == "initialization_error"


class TestWhatsAppManagerHealth:
    def test_not_configured(self, manager):
        manager.config = {}
        r = manager.health_check()
        assert r["status"] == "unhealthy"

    def test_healthy_degraded_unhealthy(self, manager):
        manager.config = {"status": "configured"}
        manager._test_api_connectivity = lambda: {"status": "healthy"}
        manager._test_database_connectivity = lambda: {"status": "healthy"}
        # two prior failures -> score 0.8 -> degraded
        manager.health_metrics["consecutive_failures"] = 2
        assert manager.health_check()["status"] == "degraded"
        # all healthy -> resets failures -> healthy
        manager.health_metrics["consecutive_failures"] = 0
        assert manager.health_check()["status"] == "healthy"
        manager._test_api_connectivity = lambda: {"status": "failed"}
        r = manager.health_check()
        assert r["status"] == "unhealthy"
        assert r["consecutive_failures"] >= 1

    def test_exception(self, manager):
        manager.config = {"status": "configured"}
        manager._test_api_connectivity = MagicMock(
            side_effect=RuntimeError("x"))
        r = manager.health_check()
        assert r["status"] == "unhealthy" and "error" in r


class TestWhatsAppManagerMetrics:
    def test_no_analytics(self, manager):
        del manager.integration.get_analytics
        r = manager.get_service_metrics()
        assert r["status"] == "unavailable"

    def test_full_metrics(self, manager):
        manager.config = {"features": {"auto_reply_enabled": True,
                                       "business_hours_enabled": True,
                                       "message_retention_days": 7}}
        manager.integration.get_analytics = MagicMock(return_value={"n": 1})
        manager.integration.get_conversations = MagicMock(return_value=[1, 2])
        r = manager.get_service_metrics()
        assert r["service_id"] == "whatsapp_business"
        assert r["performance"]["active_conversations"] == 2
        assert r["configuration"]["auto_reply_enabled"] is True

    def test_metrics_exception(self, manager):
        manager.integration.get_analytics = MagicMock(
            side_effect=RuntimeError("x"))
        r = manager.get_service_metrics()
        assert r["status"] == "error"


class TestWhatsAppManagerInternals:
    def test_api_connectivity(self, manager):
        manager.integration = None
        assert manager._test_api_connectivity()["status"] == "failed"
        manager.integration = MagicMock(access_token=None)
        assert manager._test_api_connectivity()["status"] == "failed"
        manager.integration = MagicMock(
            access_token="t", base_url="https://graph.facebook.com/v18.0")
        resp = SimpleNamespace(status_code=200,
                               elapsed=SimpleNamespace(
                                   total_seconds=lambda: 0.05))
        with patch("requests.get", return_value=resp):
            r = manager._test_api_connectivity()
            assert r["status"] == "healthy"
        resp500 = SimpleNamespace(status_code=500, text="boom" * 100)
        with patch("requests.get", return_value=resp500):
            r = manager._test_api_connectivity()
            assert r["status"] == "failed" and len(r["response_text"]) <= 200
        with patch("requests.get", side_effect=RuntimeError("net")):
            assert manager._test_api_connectivity()["status"] == "failed"

    def test_db_connectivity(self, manager):
        manager.integration = None
        assert manager._test_database_connectivity()["status"] == "failed"
        conn = MagicMock()
        conn.cursor.return_value.__enter__ = lambda s: s
        conn.cursor.return_value.__exit__ = lambda s, *a: False
        manager.integration = MagicMock(db_connection=conn)
        assert manager._test_database_connectivity()["status"] == "healthy"
        manager.integration = MagicMock(
            db_connection=MagicMock())
        manager.integration.db_connection.cursor.side_effect = RuntimeError("x")
        assert manager._test_database_connectivity()["status"] == "failed"

    def test_health_score(self, manager):
        assert manager._calculate_health_score(
            {"status": "healthy"}, {"status": "healthy"}) == pytest.approx(1.0)
        assert manager._calculate_health_score(
            {"status": "failed"}, {"status": "failed"}) == pytest.approx(0.1)
        manager.health_metrics["consecutive_failures"] = 10
        assert manager._calculate_health_score(
            {"status": "failed"}, {"status": "failed"}) == pytest.approx(0.0)

    def test_placeholders(self, manager):
        assert manager._calculate_average_response_time() == 2.5
        assert manager._get_peak_usage_hours()
        assert manager._get_top_templates()

    def test_active_conversations(self, manager):
        manager.integration = MagicMock()
        manager.integration.get_conversations = MagicMock(return_value=[1])
        assert manager._get_active_conversation_count() == 1
        del manager.integration.get_conversations
        assert manager._get_active_conversation_count() == 0
        manager.integration = None
        assert manager._get_active_conversation_count() == 0

    def test_register(self, manager, tmp_path):
        manager.service_id = "wa_test_svc"
        with patch("builtins.open", create=True) as o:
            o.return_value.__enter__ = lambda s: s
            o.return_value.__exit__ = lambda s, *a: False
            manager._register_with_service_registry()
            assert o.called
        # exception swallowed
        with patch("builtins.open", side_effect=OSError("x")):
            manager._register_with_service_registry()

    def test_module_helpers(self):
        with patch("integrations.whatsapp_service_manager"
                   ".whatsapp_service_manager") as inst:
            inst.initialize_service.return_value = {"success": True}
            inst.health_check.return_value = {"status": "healthy"}
            inst.get_service_metrics.return_value = {"status": "ok"}
            assert initialize_whatsapp_service() == {"success": True}
            assert get_whatsapp_service_status() == {"status": "healthy"}
            assert get_whatsapp_service_metrics() == {"status": "ok"}
