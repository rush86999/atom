# -*- coding: utf-8 -*-
"""Coverage wave 96 batch 6 — integrations services/routes:

- integrations/notion_routes.py
- integrations/plaid_service.py
- integrations/auth_handler_salesforce.py
- integrations/trello_routes.py
- integrations/linkedin_service.py
- integrations/figma_routes.py
- integrations/zoho_workdrive_service.py
- integrations/shopify_routes.py
- integrations/plaid_routes.py

Standalone: each module reaches >=80% line coverage from this file alone.
No network / no LLM / no real DB: httpx/requests/aiohttp boundaries and DB
sessions mocked, FastAPI TestClient + dependency_overrides for routes.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def _hresp(status=200, json_data=None, content=b""):
    r = httpx.Response(status, json=json_data if json_data is not None else {},
                       request=httpx.Request("GET", "http://x"))
    if content:
        r._content = content
    return r


def _ok(json_data=None):
    return _hresp(200, json_data if json_data is not None else {})


def _db(first=None):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = first
    db.query.return_value.filter_by.return_value.first.return_value = first
    return db


# ============================================================================
# integrations/notion_routes.py
# ============================================================================

from core.auth import get_current_user
from core.database import get_db
from integrations import notion_routes as nr


@pytest.fixture
def notion_app():
    app = FastAPI()
    app.include_router(nr.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    app.dependency_overrides[get_db] = lambda: _db(first=SimpleNamespace(id="u1"))
    return app


@pytest.fixture
def notion_client(notion_app):
    return TestClient(notion_app)


class TestNotionRoutes:
    def test_root_and_health(self, notion_client):
        assert notion_client.get("/api/notion/").status_code == 200
        assert notion_client.get("/api/notion/health").json()["ok"] is True

    def test_auth_url(self, notion_client, monkeypatch):
        monkeypatch.delenv("NOTION_CLIENT_ID", raising=False)
        assert notion_client.get("/api/notion/auth/url").status_code == 500
        monkeypatch.setenv("NOTION_CLIENT_ID", "cid")
        r = notion_client.get("/api/notion/auth/url")
        assert r.status_code == 200 and "url" in r.json()

    def test_callback_error_param(self, notion_client):
        r = notion_client.get("/api/notion/callback",
                              params={"code": "c", "error": "denied"})
        assert r.status_code == 400

    def test_callback_unconfigured(self, notion_client, monkeypatch):
        monkeypatch.delenv("NOTION_CLIENT_ID", raising=False)
        monkeypatch.delenv("NOTION_CLIENT_SECRET", raising=False)
        r = notion_client.get("/api/notion/callback", params={"code": "c"})
        assert r.status_code == 500

    def test_callback_success_and_failures(self, notion_app, monkeypatch):
        monkeypatch.setenv("NOTION_CLIENT_ID", "cid")
        monkeypatch.setenv("NOTION_CLIENT_SECRET", "cs")
        db = _db(first=SimpleNamespace(id="u1"))
        notion_app.dependency_overrides[get_db] = lambda: db
        c = TestClient(notion_app)
        with patch("requests.post") as rp:
            rp.return_value = SimpleNamespace(status_code=200, json=lambda: {
                "access_token": "tok", "workspace_id": "ws",
                "workspace_name": "W", "workspace_icon": "i", "bot_id": "b",
                "owner": {"type": "user"}})
            r = c.get("/api/notion/callback",
                      params={"code": "c", "state": "u1"})
            assert r.status_code == 200 and r.json()["success"] is True
            assert db.add.called and db.commit.called
        # non-200 token exchange
        with patch("requests.post") as rp:
            rp.return_value = SimpleNamespace(status_code=400, text="bad")
            assert c.get("/api/notion/callback",
                         params={"code": "c", "state": "u1"}).status_code == 400
        # unexpected exception -> 500
        with patch("requests.post", side_effect=RuntimeError("x")):
            assert c.get("/api/notion/callback",
                         params={"code": "c", "state": "u1"}).status_code == 500

    def test_callback_no_state_and_no_user(self, notion_app, monkeypatch):
        monkeypatch.setenv("NOTION_CLIENT_ID", "cid")
        monkeypatch.setenv("NOTION_CLIENT_SECRET", "cs")
        c = TestClient(notion_app)
        with patch("requests.post") as rp:
            rp.return_value = SimpleNamespace(status_code=200, json=lambda: {
                "access_token": "t", "workspace_id": "w"})
            assert c.get("/api/notion/callback",
                         params={"code": "c"}).status_code == 400
        # user not found -> 404
        notion_app.dependency_overrides[get_db] = lambda: _db(first=None)
        with patch("requests.post") as rp:
            rp.return_value = SimpleNamespace(status_code=200, json=lambda: {
                "access_token": "t", "workspace_id": "w"})
            assert c.get("/api/notion/callback",
                         params={"code": "c", "state": "ghost"}).status_code == 404

    def test_token_dependency_header(self, notion_client):
        with patch("requests.get") as rg:
            rg.return_value = SimpleNamespace(status_code=200,
                                              json=lambda: {"id": "me"})
            r = notion_client.get("/api/notion/status",
                                  headers={"Authorization": "Bearer tk"})
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_token_dependency_db_paths(self, notion_app):
        # valid stored token
        tok = SimpleNamespace(access_token="dbtok", status="active",
                              expires_at=datetime.now(timezone.utc)
                              + timedelta(days=1), last_used=None)
        notion_app.dependency_overrides[get_db] = lambda: _db(first=tok)
        c = TestClient(notion_app)
        with patch("requests.get") as rg:
            rg.return_value = SimpleNamespace(status_code=200,
                                              json=lambda: {"id": "me"})
            r = c.get("/api/notion/status")
        assert r.status_code == 200 and r.json()["success"] is True
        # expired token -> 401
        tok2 = SimpleNamespace(access_token="dbtok", status="active",
                               expires_at=datetime.now(timezone.utc)
                               - timedelta(days=1), last_used=None)
        notion_app.dependency_overrides[get_db] = lambda: _db(first=tok2)
        assert c.get("/api/notion/status").status_code == 401
        # no token -> 401
        notion_app.dependency_overrides[get_db] = lambda: _db(first=None)
        assert c.get("/api/notion/status").status_code == 401

    def test_status_disconnected_and_error(self, notion_client):
        with patch("requests.get") as rg:
            rg.return_value = SimpleNamespace(status_code=401, json=lambda: {})
            r = notion_client.get("/api/notion/status",
                                  headers={"Authorization": "Bearer tk"})
            assert r.json()["success"] is False
        with patch("requests.get", side_effect=RuntimeError("net")):
            r = notion_client.get("/api/notion/status",
                                  headers={"Authorization": "Bearer tk"})
            assert r.status_code == 200 and r.json()["status"] == "error"

    def test_search(self, notion_client):
        hdr = {"Authorization": "Bearer tk"}
        with patch("requests.post") as rp:
            rp.return_value = SimpleNamespace(
                status_code=200, text="", json=lambda: {"results": [{
                    "object": "page", "id": "abc123", "url": "u",
                    "last_edited_time": "t",
                    "properties": {"Name": {"type": "title",
                                            "title": [{"plain_text": "T"}]}}}]})
            r = notion_client.post("/api/notion/search",
                                   json={"query": "q"}, headers=hdr)
            assert r.status_code == 200 and r.json()["results"][0]["title"] == "T"
        with patch("requests.post") as rp:
            rp.return_value = SimpleNamespace(status_code=400, text="bad",
                                              json=lambda: {})
            assert notion_client.post("/api/notion/search",
                                      json={"query": "q"},
                                      headers=hdr).status_code == 400
        with patch("requests.post", side_effect=RuntimeError("x")):
            assert notion_client.post("/api/notion/search",
                                      json={"query": "q"},
                                      headers=hdr).status_code == 500

    def test_get_page(self, notion_client):
        hdr = {"Authorization": "Bearer tk"}
        pid = "a" * 32
        with patch("requests.get") as rg:
            rg.return_value = SimpleNamespace(
                status_code=200, text="", json=lambda: {
                    "properties": {"Name": {"type": "title",
                                            "title": [{"plain_text": "P"}]}}})
            r = notion_client.get(f"/api/notion/pages/{pid}", headers=hdr)
            assert r.status_code == 200 and r.json()["title"] == "P"
            # untitled path
            rg.return_value = SimpleNamespace(
                status_code=200, text="", json=lambda: {"properties": {}})
            r = notion_client.get("/api/notion/pages/xyz", headers=hdr)
            assert r.json()["title"] == "Untitled"
        with patch("requests.get") as rg:
            rg.return_value = SimpleNamespace(status_code=404, text="nf",
                                              json=lambda: {})
            assert notion_client.get("/api/notion/pages/x",
                                     headers=hdr).status_code == 404
        with patch("requests.get", side_effect=RuntimeError("x")):
            assert notion_client.get("/api/notion/pages/x",
                                     headers=hdr).status_code == 500


# ============================================================================
# integrations/plaid_service.py
# ============================================================================

from integrations.plaid_service import PlaidService


def _plaid_svc(**cfg):
    return PlaidService(tenant_id="t1", config=dict(
        plaid_client_id="ci", plaid_secret="cs", **cfg))


class TestPlaidService:
    def test_static(self):
        svc = _plaid_svc()
        assert svc.base_url.endswith("sandbox.plaid.com")
        assert _plaid_svc(plaid_environment="production").base_url \
            .endswith("production.plaid.com")
        assert _plaid_svc(plaid_environment="weird").base_url \
            .endswith("sandbox.plaid.com")
        assert svc._get_headers()["Content-Type"] == "application/json"
        assert svc._get_auth_payload() == {"client_id": "ci", "secret": "cs"}
        assert svc.get_capabilities()["supports_webhooks"] is True

    async def test_close(self):
        svc = _plaid_svc()
        svc.client.aclose = AsyncMock()
        await svc.close()
        svc.client.aclose.assert_awaited()

    async def test_cred_errors(self):
        for meth, args in [
            ("create_link_token", ("u",)), ("exchange_public_token", ("pt",)),
            ("get_accounts", ("t",)), ("get_balance", ("t",)),
            ("get_transactions", ("t", "s", "e")), ("get_identity", ("t",)),
            ("remove_item", ("t",)),
        ]:
            svc = PlaidService(tenant_id="t", config={})
            with pytest.raises(HTTPException) as ei:
                await getattr(svc, meth)(*args)
            assert ei.value.status_code == 401, meth

    async def test_http_methods(self):
        cases = [
            ("create_link_token", ("u",), {"link_token": "lt"}),
            ("exchange_public_token", ("pt",), {"access_token": "at"}),
            ("get_accounts", ("t",), {"accounts": [{"id": "a"}]}),
            ("get_balance", ("t",), {"accounts": []}),
            ("get_transactions", ("t", "s", "e"), {"transactions": [1]}),
            ("get_identity", ("t",), {"identity": {}}),
            ("remove_item", ("t",), {"removed": True}),
        ]
        for name, args, payload in cases:
            svc = _plaid_svc()
            svc.http.post = AsyncMock(return_value=_ok(payload))
            r = await getattr(svc, name)(*args)
            assert r is not None, name
            svc.http.post = AsyncMock(return_value=_hresp(500, {}))
            with patch.object(httpx.Response, "raise_for_status",
                              side_effect=httpx.HTTPError("x")):
                with pytest.raises(HTTPException):
                    await getattr(svc, name)(*args)

    async def test_health_check(self):
        svc = PlaidService(tenant_id="t", config={})
        h = await svc.health_check()
        assert h["healthy"] is False and h["ok"] is False
        svc = _plaid_svc()
        with patch("requests.post", return_value=SimpleNamespace(status_code=200)):
            assert (await svc.health_check())["healthy"] is True
        with patch("requests.post", return_value=SimpleNamespace(status_code=500)):
            assert (await svc.health_check())["healthy"] is False
        with patch("requests.post", side_effect=RuntimeError("net")):
            h = await svc.health_check()
            assert h["healthy"] is False

    async def test_execute_operation(self):
        svc = _plaid_svc()
        # cross-tenant prevention
        r = await svc.execute_operation("get_accounts", {"access_token": "t"},
                                        context={"tenant_id": "other"})
        assert r["success"] is False
        # missing token
        r = await svc.execute_operation("get_accounts", {})
        assert r["success"] is False
        for op, extra in [("get_accounts", {}), ("get_balance", {}),
                          ("get_transactions", {"start_date": "s",
                                                "end_date": "e"}),
                          ("get_identity", {})]:
            svc2 = _plaid_svc()
            svc2.get_accounts = AsyncMock(return_value=[1])
            svc2.get_balance = AsyncMock(return_value={})
            svc2.get_transactions = AsyncMock(return_value={})
            svc2.get_identity = AsyncMock(return_value={})
            r = await svc2.execute_operation(op, {"access_token": "t", **extra})
            assert r["success"] is True, op
        # unsupported + failure
        r = await svc.execute_operation("nope", {"access_token": "t"})
        assert r["success"] is False
        svc.get_accounts = AsyncMock(side_effect=RuntimeError("x"))
        r = await svc.execute_operation("get_accounts", {"access_token": "t"})
        assert r["success"] is False

    async def test_sync_and_full_sync(self, monkeypatch):
        svc = _plaid_svc()
        svc.get_accounts = AsyncMock(return_value=[
            {"balances": {"current": 10, "available": 5}},
            {"balances": {}}])
        db = _db(first=None)
        monkeypatch.setattr("core.database.SessionLocal",
                            MagicMock(return_value=db))
        assert (await svc.sync_to_postgres_cache("ws", "t")) == \
            {"success": True, "metrics_synced": 3}
        db.query.return_value.filter_by.return_value.first.return_value = \
            MagicMock()
        assert (await svc.sync_to_postgres_cache("ws", "t"))[
            "metrics_synced"] == 3
        db.commit = MagicMock(side_effect=RuntimeError("x"))
        r = await svc.sync_to_postgres_cache("ws", "t")
        assert r["success"] is False and db.rollback.called
        svc.get_accounts = AsyncMock(side_effect=RuntimeError("api"))
        assert (await svc.sync_to_postgres_cache("ws", "t"))["success"] is False
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True})
        r = await svc.full_sync("ws", "t")
        assert r["success"] and r["workspace_id"] == "ws"


# ============================================================================
# integrations/plaid_routes.py
# ============================================================================

from integrations import plaid_routes as pr


@pytest.fixture
def plaid_client():
    app = FastAPI()
    app.include_router(pr.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    return TestClient(app)


class TestPlaidRoutes:
    def test_create_link_token(self, plaid_client):
        with patch.object(pr, "plaid_service") as svc:
            svc.create_link_token = AsyncMock(return_value={"link_token": "lt"})
            r = plaid_client.post("/api/plaid/link/token/create",
                                  json={"user_id": "u"})
            assert r.status_code == 200 and r.json()["ok"] is True
            svc.create_link_token = AsyncMock(side_effect=RuntimeError("x"))
            assert plaid_client.post("/api/plaid/link/token/create",
                                     json={"user_id": "u"}).status_code == 500

    def test_exchange_and_accounts(self, plaid_client):
        with patch.object(pr, "plaid_service") as svc:
            svc.exchange_public_token = AsyncMock(
                return_value={"access_token": "at"})
            r = plaid_client.post("/api/plaid/item/public_token/exchange",
                                  json={"public_token": "pt"})
            assert r.status_code == 200 and r.json()["ok"] is True
            svc.exchange_public_token = AsyncMock(side_effect=RuntimeError("x"))
            assert plaid_client.post(
                "/api/plaid/item/public_token/exchange",
                json={"public_token": "pt"}).status_code == 500
            svc.get_accounts = AsyncMock(return_value={"accounts": []})
            r = plaid_client.post("/api/plaid/accounts/get",
                                  json={"access_token": "t"})
            assert r.status_code == 200
            svc.get_accounts = AsyncMock(side_effect=RuntimeError("x"))
            assert plaid_client.post("/api/plaid/accounts/get",
                                     json={"access_token": "t"}
                                     ).status_code == 500

    def test_balance_transactions_identity_remove(self, plaid_client):
        with patch.object(pr, "plaid_service") as svc:
            svc.get_balance = AsyncMock(return_value={"accounts": []})
            assert plaid_client.post("/api/plaid/accounts/balance/get",
                                     json={"access_token": "t"}).status_code == 200
            svc.get_transactions = AsyncMock(return_value={"transactions": []})
            r = plaid_client.post("/api/plaid/transactions/get", json={
                "access_token": "t", "start_date": "s", "end_date": "e"})
            assert r.status_code == 200
            svc.get_transactions = AsyncMock(side_effect=RuntimeError("x"))
            assert plaid_client.post("/api/plaid/transactions/get", json={
                "access_token": "t", "start_date": "s",
                "end_date": "e"}).status_code == 500
            svc.get_identity = AsyncMock(return_value={"identity": {}})
            assert plaid_client.post("/api/plaid/identity/get",
                                     json={"access_token": "t"}).status_code == 200
            svc.get_identity = AsyncMock(side_effect=RuntimeError("x"))
            assert plaid_client.post("/api/plaid/identity/get",
                                     json={"access_token": "t"}
                                     ).status_code == 500
            svc.remove_item = AsyncMock(return_value={"removed": True})
            assert plaid_client.post("/api/plaid/item/remove",
                                     json={"access_token": "t"}).status_code == 200
            svc.remove_item = AsyncMock(side_effect=RuntimeError("x"))
            assert plaid_client.post("/api/plaid/item/remove",
                                     json={"access_token": "t"}
                                     ).status_code == 500

    def test_status_health_and_legacy(self, plaid_client):
        with patch.object(pr, "plaid_service") as svc:
            svc.client_id = "ci"
            svc.environment = "sandbox"
            svc.health_check = AsyncMock(return_value={"ok": True})
            assert plaid_client.get("/api/plaid/status").json()["ok"] is True
            svc.health_check = AsyncMock(return_value={"ok": False})
            assert plaid_client.get("/api/plaid/health").json()[
                "status"] == "unhealthy"
        assert plaid_client.get("/api/plaid/auth/url").status_code == 200
        with patch.object(pr, "plaid_service") as svc:
            svc.exchange_public_token = AsyncMock(
                return_value={"access_token": "at"})
            r = plaid_client.get("/api/plaid/callback",
                                 params={"public_token": "pt"})
            assert r.json()["ok"] is True
            svc.exchange_public_token = AsyncMock(side_effect=RuntimeError("x"))
            r = plaid_client.get("/api/plaid/callback",
                                 params={"public_token": "pt"})
            assert r.json()["ok"] is False


# ============================================================================
# integrations/auth_handler_salesforce.py
# ============================================================================

import integrations.auth_handler_salesforce as ahs
from integrations.auth_handler_salesforce import SalesforceAuthHandler


class _Ctx:
    def __init__(self, value):
        self._v = value

    async def __aenter__(self):
        return self._v

    async def __aexit__(self, *a):
        return False


class _Resp:
    def __init__(self, status=200, payload=None, text="err"):
        self.status = status
        self._payload = payload or {}

    async def text(self):
        return "err"

    async def json(self):
        return self._payload


class _Session:
    def __init__(self, resp):
        self._resp = resp

    def post(self, *a, **k):
        return _Ctx(self._resp)

    def get(self, *a, **k):
        return _Ctx(self._resp)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


def _sf_handler():
    with patch.object(ahs, "get_secret_manager") as gsm:
        gsm.return_value = MagicMock()
        gsm.return_value.get_secret.return_value = None
        return SalesforceAuthHandler()


class TestSalesforceAuthHandler:
    def test_init_and_auth_url(self):
        h = _sf_handler()
        url = h.get_authorization_url("st")
        assert "state=st" in url and "scope=" in url
        assert "state=" in h.get_authorization_url()

    async def test_exchange_code_for_token(self):
        h = _sf_handler()
        resp = _Resp(200, {"access_token": "at", "refresh_token": "rt",
                           "instance_url": "https://inst", "expires_in": 100})
        with patch.object(ahs.aiohttp, "ClientSession", return_value=_Session(resp)):
            r = await h.exchange_code_for_token("code")
        assert r["access_token"] == "at" and h.access_token == "at"
        assert h.token_expires_at is not None
        h2 = _sf_handler()
        with patch.object(ahs.aiohttp, "ClientSession",
                          return_value=_Session(_Resp(400))):
            with pytest.raises(HTTPException) as ei:
                await h2.exchange_code_for_token("code")
            assert ei.value.status_code == 400
        with patch.object(ahs.aiohttp, "ClientSession",
                          side_effect=RuntimeError("net")):
            with pytest.raises(HTTPException) as ei:
                await h2.exchange_code_for_token("code")
            assert ei.value.status_code == 500

    async def test_refresh_access_token(self):
        h = _sf_handler()
        with pytest.raises(HTTPException) as ei:
            await h.refresh_access_token()
        assert ei.value.status_code == 400
        h.refresh_token = "rt"
        resp = _Resp(200, {"access_token": "at2", "instance_url": "https://i2"})
        with patch.object(ahs.aiohttp, "ClientSession",
                          return_value=_Session(resp)):
            r = await h.refresh_access_token()
        assert r["access_token"] == "at2" and h.refresh_token == "rt"
        h2 = _sf_handler()
        h2.refresh_token = "rt"
        with patch.object(ahs.aiohttp, "ClientSession",
                          return_value=_Session(_Resp(401))):
            with pytest.raises(HTTPException):
                await h2.refresh_access_token()
        with patch.object(ahs.aiohttp, "ClientSession",
                          side_effect=RuntimeError("net")):
            with pytest.raises(HTTPException) as ei:
                await h2.refresh_access_token()
            assert ei.value.status_code == 500

    async def test_get_user_info(self):
        h = _sf_handler()
        with pytest.raises(HTTPException) as ei:
            await h.get_user_info()
        assert ei.value.status_code == 401
        h.access_token = "at"
        h.instance_url = "https://inst"
        resp = _Resp(200, {"user_id": "me"})
        with patch.object(ahs.aiohttp, "ClientSession",
                          return_value=_Session(resp)):
            r = await h.get_user_info()
        assert r == {"user_id": "me"} and h.user_info == {"user_id": "me"}
        h2 = _sf_handler()
        h2.access_token = "at"
        h2.instance_url = "https://inst"
        with patch.object(ahs.aiohttp, "ClientSession",
                          return_value=_Session(_Resp(401))):
            with pytest.raises(HTTPException):
                await h2.get_user_info()
        with patch.object(ahs.aiohttp, "ClientSession",
                          side_effect=RuntimeError("net")):
            with pytest.raises(HTTPException) as ei:
                await h2.get_user_info()
            assert ei.value.status_code == 500

    async def test_revoke_token(self):
        h = _sf_handler()
        assert await h.revoke_token() is True  # no token
        h.access_token = "at"
        h.refresh_token = "rt"
        with patch.object(ahs.aiohttp, "ClientSession",
                          return_value=_Session(_Resp(200))):
            assert await h.revoke_token() is True
            assert h.access_token is None and h.refresh_token is None
        h2 = _sf_handler()
        h2.access_token = "at"
        with patch.object(ahs.aiohttp, "ClientSession",
                          return_value=_Session(_Resp(400))):
            assert await h2.revoke_token() is False
        with patch.object(ahs.aiohttp, "ClientSession",
                          side_effect=RuntimeError("net")):
            assert await h2.revoke_token() is False

    def test_token_validity_and_status(self):
        h = _sf_handler()
        assert h.is_token_valid() is False
        h.access_token = "at"
        assert h.is_token_valid() is False  # no expiry
        h.token_expires_at = datetime.now() + timedelta(hours=1)
        assert h.is_token_valid() is True
        h.token_expires_at = datetime.now() - timedelta(minutes=1)
        assert h.is_token_valid() is False
        s = h.get_connection_status()
        assert s["has_access_token"] is True and s["connected"] is False

    async def test_ensure_valid_token(self):
        h = _sf_handler()
        with pytest.raises(HTTPException) as ei:
            await h.ensure_valid_token()
        assert ei.value.status_code == 401
        h.refresh_token = "rt"
        h.refresh_access_token = AsyncMock()
        await h.ensure_valid_token()
        h.refresh_access_token.assert_awaited()
        h.access_token = "at"
        h.token_expires_at = datetime.now() + timedelta(hours=1)
        assert await h.ensure_valid_token() == "at"


# ============================================================================
# integrations/trello_routes.py
# ============================================================================

from integrations import trello_routes as tr


@pytest.fixture
def trello_client():
    app = FastAPI()
    app.include_router(tr.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    return TestClient(app)


@pytest.fixture
def tsvc():
    with patch.object(tr, "trello_service") as m:
        m.get_service_info = AsyncMock(return_value={"ok": True})
        m.get_boards = AsyncMock(return_value=[{"id": "b"}])
        m.get_board = AsyncMock(return_value={"id": "b"})
        m.get_lists = AsyncMock(return_value=[{"id": "l"}])
        m.get_cards = AsyncMock(return_value=[{"id": "c"}])
        m.create_card = AsyncMock(return_value={"id": "c"})
        m.get_card = AsyncMock(return_value={"id": "c"})
        m.update_card = AsyncMock(return_value={"id": "c"})
        m.delete_card = AsyncMock(return_value=True)
        m.get_members = AsyncMock(return_value=[{"id": "m"}])
        m.search_cards = AsyncMock(return_value=[1])
        m.get_board_activities = AsyncMock(return_value=[1])
        yield m


class TestTrelloRoutes:
    def test_auth_url_and_callback(self, trello_client):
        assert trello_client.get("/api/trello/auth/url").status_code == 200
        r = trello_client.get("/api/trello/callback", params={"token": "tk"})
        assert r.json()["ok"] is True

    def test_health_status_info(self, trello_client):
        r = trello_client.get("/api/trello/health")
        assert r.status_code == 200 and r.json()["status"] == "healthy"
        assert trello_client.get("/api/trello/status").status_code == 200
        assert trello_client.get("/api/trello/info").json()["ok"] is True
        with patch.object(tr, "trello_service") as m:
            m.get_service_info = AsyncMock(side_effect=RuntimeError("x"))
            assert trello_client.get("/api/trello/health").status_code == 503
            assert trello_client.get("/api/trello/info").status_code == 500

    def test_boards(self, trello_client, tsvc):
        r = trello_client.post("/api/trello/boards", json={"user_id": "u"})
        assert r.status_code == 200 and r.json()["data"]["total_count"] == 1
        r = trello_client.post("/api/trello/boards/b1", json={"user_id": "u"})
        assert r.status_code == 200
        tsvc.get_boards = AsyncMock(side_effect=RuntimeError("x"))
        assert trello_client.post("/api/trello/boards",
                                  json={"user_id": "u"}).status_code == 500
        tsvc.get_board = AsyncMock(side_effect=RuntimeError("x"))
        assert trello_client.post("/api/trello/boards/b1",
                                  json={"user_id": "u"}).status_code == 500

    def test_lists_cards(self, trello_client, tsvc):
        r = trello_client.post("/api/trello/lists",
                               json={"user_id": "u", "board_id": "b"})
        assert r.status_code == 200
        r = trello_client.post("/api/trello/cards",
                               json={"user_id": "u", "board_id": "b"})
        assert r.status_code == 200 and r.json()["data"]["total_count"] == 1
        tsvc.get_lists = AsyncMock(side_effect=RuntimeError("x"))
        assert trello_client.post("/api/trello/lists",
                                  json={"user_id": "u",
                                        "board_id": "b"}).status_code == 500
        tsvc.get_cards = AsyncMock(side_effect=RuntimeError("x"))
        assert trello_client.post("/api/trello/cards",
                                  json={"user_id": "u"}).status_code == 500

    def test_card_crud(self, trello_client, tsvc):
        r = trello_client.post("/api/trello/cards/create", json={
            "user_id": "u", "name": "n", "id_list": "l"})
        assert r.status_code == 200
        # card_type formatting branch
        tsvc.card_types = {"bug": "bug"}
        r = trello_client.post("/api/trello/cards/create", json={
            "user_id": "u", "name": "n", "id_list": "l", "card_type": "bug"})
        assert r.status_code == 200
        cd = tsvc.create_card.call_args[1]["card_data"]
        assert cd["name"] == "[BUG] n"
        tsvc.create_card = AsyncMock(side_effect=RuntimeError("x"))
        assert trello_client.post("/api/trello/cards/create", json={
            "user_id": "u", "name": "n", "id_list": "l"}).status_code == 500
        assert trello_client.post("/api/trello/cards/c1",
                                  json={"user_id": "u"}).status_code == 200
        tsvc.get_card = AsyncMock(side_effect=RuntimeError("x"))
        assert trello_client.post("/api/trello/cards/c1",
                                  json={"user_id": "u"}).status_code == 500
        r = trello_client.put("/api/trello/cards/c1", json={
            "user_id": "u", "name": "n2", "desc": "d", "due": "x",
            "id_list": "l2", "labels": ["lb"]})
        assert r.status_code == 200
        tsvc.update_card = AsyncMock(side_effect=RuntimeError("x"))
        assert trello_client.put("/api/trello/cards/c1",
                                 json={"user_id": "u"}).status_code == 500
        r = trello_client.request("DELETE", "/api/trello/cards/c1",
                                  json={"user_id": "u"})
        assert r.status_code == 200
        tsvc.delete_card = AsyncMock(side_effect=RuntimeError("x"))
        assert trello_client.request("DELETE", "/api/trello/cards/c1",
                                     json={"user_id": "u"}).status_code == 500

    def test_members_profile_search_activities(self, trello_client, tsvc):
        r = trello_client.post("/api/trello/members",
                               json={"user_id": "u", "board_id": "b"})
        assert r.status_code == 200
        r = trello_client.post("/api/trello/user/profile",
                               json={"user_id": "u"})
        assert r.status_code == 200
        r = trello_client.post("/api/trello/search",
                               json={"user_id": "u", "query": "q"})
        assert r.status_code == 200 and r.json()["data"]["total_count"] == 1
        r = trello_client.post("/api/trello/activities",
                               json={"user_id": "u", "board_id": "b"})
        assert r.status_code == 200
        tsvc.get_members = AsyncMock(side_effect=RuntimeError("x"))
        assert trello_client.post("/api/trello/members",
                                  json={"user_id": "u",
                                        "board_id": "b"}).status_code == 500
        tsvc.search_cards = AsyncMock(side_effect=RuntimeError("x"))
        assert trello_client.post("/api/trello/search",
                                  json={"user_id": "u",
                                        "query": "q"}).status_code == 500
        tsvc.get_board_activities = AsyncMock(side_effect=RuntimeError("x"))
        assert trello_client.post("/api/trello/activities",
                                  json={"user_id": "u",
                                        "board_id": "b"}).status_code == 500


# ============================================================================
# integrations/linkedin_service.py
# ============================================================================

from integrations.linkedin_service import LinkedInService


def _li_svc(**cfg):
    base = {"linkedin_client_id": "ci", "linkedin_client_secret": "cs",
            "access_token": "tok"}
    base.update(cfg)
    return LinkedInService(tenant_id="t1", config=base)


class TestLinkedInService:
    def test_static(self):
        svc = _li_svc()
        assert svc._get_headers("t")["Authorization"] == "Bearer t"
        assert "state=st" in svc.get_authorization_url("http://cb", state="st")
        assert "state=" not in svc.get_authorization_url("http://cb")
        assert svc.get_capabilities()["supports_webhooks"] is False
        assert svc.health_check()["healthy"] is True

    async def test_close_and_exchange(self):
        svc = _li_svc()
        svc.client.aclose = AsyncMock()
        await svc.close()
        svc.client.post = AsyncMock(return_value=_ok({"access_token": "at"}))
        r = await svc.exchange_token("c", "http://cb")
        assert r["access_token"] == "at" and svc.access_token == "at"
        svc.client.post = AsyncMock(return_value=_hresp(500, {}))
        with patch.object(httpx.Response, "raise_for_status",
                          side_effect=httpx.HTTPError("x")):
            with pytest.raises(HTTPException):
                await svc.exchange_token("c", "http://cb")

    async def test_get_profile_and_email(self):
        svc = _li_svc(access_token=None)
        with pytest.raises(HTTPException) as ei:
            await svc.get_profile()
        assert ei.value.status_code == 401
        with pytest.raises(HTTPException):
            await svc.get_email()
        svc = _li_svc()
        svc.client.get = AsyncMock(return_value=_ok({"id": "me"}))
        assert (await svc.get_profile())["id"] == "me"
        svc.client.get = AsyncMock(return_value=_ok({"elements": [1]}))
        assert (await svc.get_email()) == {"elements": [1]}
        for meth in ("get_profile", "get_email"):
            svc.client.get = AsyncMock(return_value=_hresp(500, {}))
            with patch.object(httpx.Response, "raise_for_status",
                              side_effect=httpx.HTTPError("x")):
                with pytest.raises(HTTPException):
                    await getattr(svc, meth)()

    async def test_share_update(self):
        svc = _li_svc(access_token=None)
        with pytest.raises(HTTPException):
            await svc.share_update("hi")
        svc = _li_svc()
        svc.client.get = AsyncMock(return_value=_ok({"id": "urn1"}))
        svc.client.post = AsyncMock(return_value=_ok({"id": "post"}))
        r = await svc.share_update("hello", visibility="CONNECTIONS")
        assert r["id"] == "post"
        assert "urn1" in svc.client.post.call_args[1]["json"]["author"]
        svc.client.post = AsyncMock(return_value=_hresp(500, {}))
        with patch.object(httpx.Response, "raise_for_status",
                          side_effect=httpx.HTTPError("x")):
            with pytest.raises(HTTPException):
                await svc.share_update("hi")

    async def test_execute_operation(self):
        svc = _li_svc()
        svc.share_update = AsyncMock(return_value={"id": "p"})
        assert (await svc.execute_operation(
            "post_share", {"text": "t"}))["success"] is True
        svc.get_profile = AsyncMock(return_value={"id": "me"})
        assert (await svc.execute_operation(
            "get_profile", {}, context={"access_token": "t"}))["success"]
        svc.get_email = AsyncMock(return_value={})
        assert (await svc.execute_operation(
            "get_email", {"access_token": "t"}))["success"] is True
        r = await svc.execute_operation("get_connections", {})
        assert r["success"] is True
        r = await svc.execute_operation("nope", {})
        assert r["success"] is False
        svc.share_update = AsyncMock(side_effect=RuntimeError("x"))
        assert (await svc.execute_operation(
            "post_share", {"text": "t"}))["success"] is False

    async def test_sync_and_full_sync(self, monkeypatch):
        svc = _li_svc()
        db = _db(first=None)
        monkeypatch.setattr("core.database.SessionLocal",
                            MagicMock(return_value=db))
        assert (await svc.sync_to_postgres_cache("ws")) == \
            {"success": True, "metrics_synced": 1}
        # verify BUG FIX: filter keyed on workspace_id, not tenant_id
        kwargs = db.query.return_value.filter_by.call_args[1]
        assert "workspace_id" in kwargs and "tenant_id" not in kwargs
        db.query.return_value.filter_by.return_value.first.return_value = \
            MagicMock()
        assert (await svc.sync_to_postgres_cache("ws"))[
            "metrics_synced"] == 1
        db.commit = MagicMock(side_effect=RuntimeError("x"))
        assert (await svc.sync_to_postgres_cache("ws"))["success"] is False
        monkeypatch.setattr("core.database.SessionLocal",
                            MagicMock(side_effect=RuntimeError("db")))
        assert (await svc.sync_to_postgres_cache("ws"))["success"] is False
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True})
        r = await svc.full_sync("ws")
        assert r["success"] and r["workspace_id"] == "ws"


# ============================================================================
# integrations/figma_routes.py
# ============================================================================

from integrations import figma_routes as fr


@pytest.fixture
def figma_client():
    app = FastAPI()
    app.include_router(fr.router)
    return TestClient(app)


@pytest.fixture
def fsvc():
    svc = MagicMock()
    svc.get_authorization_url = MagicMock(return_value="https://fig.ma/auth")
    svc.exchange_token = AsyncMock(return_value={"user_id": "u",
                                                 "expires_in": 100})
    svc.get_connection_status = MagicMock(return_value={"connected": True})
    svc.ensure_valid_token = AsyncMock(return_value="t")
    svc.get_user_info = AsyncMock(return_value={"id": "me"})
    svc.get_team_projects = AsyncMock(return_value=[
        {"id": "p1", "name": "P1"}])
    svc.get_project_files = AsyncMock(return_value=[{"id": "f1"}])
    svc.search_files = AsyncMock(return_value=[{"id": "f1"}])
    svc.health_check = MagicMock(return_value={"healthy": True})
    with patch.object(fr, "get_figma_service", return_value=svc):
        yield svc


class TestFigmaRoutes:
    def test_oauth_url(self, figma_client, fsvc):
        r = figma_client.get("/api/figma/oauth/url", params={"state": "s"})
        assert r.status_code == 200 and r.json()["ok"] is True
        fsvc.get_authorization_url = MagicMock(side_effect=RuntimeError("x"))
        assert figma_client.get("/api/figma/oauth/url").status_code == 500

    def test_oauth_callback(self, figma_client, fsvc):
        r = figma_client.get("/api/figma/oauth/callback",
                             params={"code": "c"})
        assert r.status_code == 200 and r.json()["ok"] is True
        fsvc.exchange_token = AsyncMock(side_effect=HTTPException(401))
        assert figma_client.get("/api/figma/oauth/callback",
                                params={"code": "c"}).status_code == 401
        fsvc.exchange_token = AsyncMock(side_effect=RuntimeError("x"))
        assert figma_client.get("/api/figma/oauth/callback",
                                params={"code": "c"}).status_code == 500

    def test_oauth_status_and_status(self, figma_client, fsvc):
        assert figma_client.get("/api/figma/oauth/status").json()["ok"] is True
        fsvc.get_connection_status = MagicMock(side_effect=RuntimeError("x"))
        assert figma_client.get("/api/figma/oauth/status").status_code == 500
        fsvc.get_connection_status = MagicMock(return_value={"connected": True})
        assert figma_client.get("/api/figma/status").json()[
            "status"] == "connected"
        fsvc.get_connection_status = MagicMock(return_value={"connected": False})
        r = figma_client.get("/api/figma/status")
        assert r.json()["status"] == "disconnected"

    def test_user(self, figma_client, fsvc):
        r = figma_client.get("/api/figma/user")
        assert r.status_code == 200 and r.json()["id"] == "me"
        fsvc.ensure_valid_token = AsyncMock(side_effect=HTTPException(401))
        assert figma_client.get("/api/figma/user").status_code == 401
        fsvc.ensure_valid_token = AsyncMock(side_effect=RuntimeError("x"))
        assert figma_client.get("/api/figma/user").status_code == 500

    def test_files(self, figma_client, fsvc):
        r = figma_client.get("/api/figma/files", params={"team_id": "t"})
        assert r.status_code == 200 and r.json()["count"] == 1
        assert r.json()["files"][0]["project_id"] == "p1"
        r = figma_client.get("/api/figma/files", params={"project_id": "p"})
        assert r.status_code == 200 and r.json()["source"] == "project"
        r = figma_client.get("/api/figma/files")
        assert r.json()["ok"] is False and r.json()["error"] == "missing_context"
        fsvc.ensure_valid_token = AsyncMock(side_effect=HTTPException(401))
        assert figma_client.get("/api/figma/files",
                                params={"team_id": "t"}).status_code == 401
        fsvc.ensure_valid_token = AsyncMock(side_effect=RuntimeError("x"))
        assert figma_client.get("/api/figma/files",
                                params={"project_id": "p"}).status_code == 500

    def test_search_items_health(self, figma_client, fsvc):
        r = figma_client.post("/api/figma/search",
                              json={"query": "q"}, params={"team_id": "t"})
        assert r.status_code == 200 and r.json()["ok"] is True
        fsvc.search_files = AsyncMock(side_effect=RuntimeError("x"))
        assert figma_client.post("/api/figma/search",
                                 json={"query": "q"}).status_code == 500
        r = figma_client.get("/api/figma/items")
        assert r.status_code == 200 and len(r.json()["items"]) == 5
        fsvc.ensure_valid_token = AsyncMock(side_effect=HTTPException(401))
        assert figma_client.get("/api/figma/items").status_code == 401
        fsvc.ensure_valid_token = AsyncMock(side_effect=RuntimeError("x"))
        assert figma_client.get("/api/figma/items").status_code == 500
        assert figma_client.get("/api/figma/health").json()["healthy"] is True


# ============================================================================
# integrations/zoho_workdrive_service.py
# ============================================================================

from integrations import zoho_workdrive_service as zwd
from integrations.zoho_workdrive_service import ZohoWorkDriveService


def _zwd_svc(**cfg):
    return ZohoWorkDriveService(tenant_id="t1", config=dict(
        client_id="ci", client_secret="cs", **cfg))


def _conn_patch(connections=None, creds=None, error=None):
    cs = MagicMock()
    if error:
        cs.get_connections.side_effect = error
    else:
        cs.get_connections.return_value = connections or []
    cs.get_connection_credentials = AsyncMock(
        return_value=creds, side_effect=error)
    return patch.object(zwd, "connection_service", cs)


class TestZohoWorkDriveService:
    def test_regional_bases(self, monkeypatch):
        monkeypatch.setenv("ZOHO_CRM_ACCOUNTS_URL", "https://accounts.zoho.in")
        assert _zwd_svc().base_url.startswith("https://workdrive.zoho.in")
        monkeypatch.setenv("ZOHO_CRM_ACCOUNTS_URL", "https://accounts.zoho.eu")
        assert _zwd_svc().base_url.startswith("https://workdrive.zoho.eu")
        monkeypatch.setenv("ZOHO_CRM_ACCOUNTS_URL",
                           "https://accounts.zoho.com.au")
        assert _zwd_svc().base_url.startswith("https://workdrive.zoho.com.au")
        monkeypatch.setenv("ZOHO_CRM_ACCOUNTS_URL",
                           "https://accounts.zoho.com")
        assert _zwd_svc().base_url.startswith("https://workdrive.zoho.com/api")

    async def test_get_access_token(self):
        svc = _zwd_svc()
        with _conn_patch():
            assert await svc.get_access_token("u") is None
        with _conn_patch(connections=[{"id": "c1"}], creds={"access_token": "t"}):
            assert await svc.get_access_token("u") == "t"
        with _conn_patch(connections=[], creds={}):
            assert await svc.get_access_token("u") is None
        with _conn_patch(connections=[{"id": "c1"}], creds=None):
            assert await svc.get_access_token("u") is None
        with _conn_patch(error=RuntimeError("db")):
            assert await svc.get_access_token("u") is None

    async def test_get_teams(self):
        svc = _zwd_svc()
        with patch.object(svc, "get_access_token", AsyncMock(return_value=None)):
            assert await svc.get_teams("u") == []
        with patch.object(svc, "get_access_token", AsyncMock(return_value="t")):
            svc.client.get = AsyncMock(return_value=_ok({"data": [
                {"id": "tm1", "type": "teams",
                 "attributes": {"name": "Team", "status": "ok",
                                "role": "admin"}}]}))
            r = await svc.get_teams("u")
            assert r == [{"id": "tm1", "name": "Team", "type": "teams",
                          "status": "ok", "role": "admin"}]
            svc.client.get = AsyncMock(side_effect=RuntimeError("net"))
            assert await svc.get_teams("u") == []

    async def test_list_files_and_download(self):
        svc = _zwd_svc()
        with patch.object(svc, "get_access_token", AsyncMock(return_value=None)):
            assert await svc.list_files("u") == []
            assert await svc.download_file("u", "f") is None
        with patch.object(svc, "get_access_token", AsyncMock(return_value="t")):
            svc.client.get = AsyncMock(return_value=_ok({"data": [
                {"id": "f1", "type": "files",
                 "attributes": {"name": "a.csv", "extension": "csv",
                                "size": 5,
                                "modified_time_in_iso8601": "t"}}]}))
            r = await svc.list_files("u", "root")
            assert r[0]["name"] == "a.csv"
            svc.client.get = AsyncMock(side_effect=RuntimeError("net"))
            assert await svc.list_files("u") == []
            svc.client.get = AsyncMock(return_value=_hresp(200, {}, b"bytes"))
            assert await svc.download_file("u", "f") == b"bytes"
            svc.client.get = AsyncMock(side_effect=RuntimeError("net"))
            assert await svc.download_file("u", "f") is None

    async def test_ingest_file_to_memory(self):
        svc = _zwd_svc()
        with patch.object(svc, "get_access_token", AsyncMock(return_value=None)):
            r = await svc.ingest_file_to_memory("u", "f")
            assert r["success"] is False
        with patch.object(svc, "get_access_token", AsyncMock(return_value="t")):
            with patch.object(svc, "download_file",
                              AsyncMock(return_value=None)):
                r = await svc.ingest_file_to_memory("u", "f")
                assert r["success"] is False
            with patch.object(svc, "download_file",
                              AsyncMock(return_value=b"data")):
                svc.client.get = AsyncMock(return_value=_ok({"data": {
                    "attributes": {"name": "doc.pdf"}}}))
                ingestor = MagicMock()
                ingestor.process_file_bytes = AsyncMock(
                    return_value={"ok": True})
                with patch("core.auto_document_ingestion"
                           ".AutoDocumentIngestionService",
                           return_value=ingestor):
                    r = await svc.ingest_file_to_memory("u", "f")
                assert r["success"] is True
                svc.client.get = AsyncMock(side_effect=RuntimeError("net"))
                r = await svc.ingest_file_to_memory("u", "f")
                assert r["success"] is False

    async def test_sync_and_full_sync(self, monkeypatch):
        svc = _zwd_svc()
        svc.list_files = AsyncMock(return_value=[{"id": "f1"}])
        db = _db(first=None)
        monkeypatch.setattr("core.database.SessionLocal",
                            MagicMock(return_value=db))
        assert (await svc.sync_to_postgres_cache("u")) == \
            {"success": True, "metrics_synced": 1}
        db.query.return_value.filter_by.return_value.first.return_value = \
            MagicMock()
        assert (await svc.sync_to_postgres_cache("u"))["metrics_synced"] == 1
        db.commit = MagicMock(side_effect=RuntimeError("x"))
        assert (await svc.sync_to_postgres_cache("u"))["success"] is False
        svc.list_files = AsyncMock(side_effect=RuntimeError("x"))
        assert (await svc.sync_to_postgres_cache("u"))["success"] is False

        # full_sync: parseable + non-parseable + errors + import failure
        svc.list_files = AsyncMock(return_value=[
            {"id": "f1", "name": "a.pdf"}, {"id": "f2", "name": "b.pdf"},
            {"id": "f3", "name": "c.png"}])
        svc.sync_to_postgres_cache = AsyncMock(
            return_value={"success": True})
        svc.ingest_file_to_memory = AsyncMock(
            side_effect=[{"success": True},
                         {"success": False, "error": "e"}])
        r = await svc.full_sync("u", "ws")
        assert r["success"] and r["files_ingested"] == 1
        assert r["errors"] == ["b.pdf: e"]
        svc.ingest_file_to_memory = AsyncMock(side_effect=RuntimeError("boom"))
        r = await svc.full_sync("u")
        assert r["errors"] and r["files_ingested"] == 0
        with patch("core.auto_document_ingestion"
                   ".AutoDocumentIngestionService",
                   side_effect=RuntimeError("no module")):
            r = await svc.full_sync("u")
        assert r["success"] is True and r["errors"]

    def test_static_and_ops(self):
        svc = _zwd_svc()
        assert svc.get_capabilities()["supports_webhooks"] is False

    async def test_health_and_execute_operation(self):
        svc = _zwd_svc()
        assert (await svc.health_check())["healthy"] is True
        assert isinstance(zwd.zoho_workdrive_service, ZohoWorkDriveService)
        svc.list_files = AsyncMock(return_value=[1])
        assert (await svc.execute_operation(
            "list_files", {"user_id": "u"}))["success"] is True
        svc.get_teams = AsyncMock(return_value=[1])
        assert (await svc.execute_operation(
            "get_teams", {}, context={"user_id": "u"}))["success"] is True
        svc.download_file = AsyncMock(return_value=b"x")
        assert (await svc.execute_operation(
            "download_file", {"user_id": "u", "file_id": "f"}))["success"]
        svc.ingest_file_to_memory = AsyncMock(return_value={"success": True})
        assert (await svc.execute_operation(
            "ingest_file_to_memory", {"user_id": "u", "file_id": "f"}
        ))["success"] is True
        svc.full_sync = AsyncMock(return_value={"success": True})
        assert (await svc.execute_operation(
            "full_sync", {"user_id": "u"}))["success"] is True
        r = await svc.execute_operation("nope", {})
        assert r["success"] is False
        svc.list_files = AsyncMock(side_effect=RuntimeError("x"))
        r = await svc.execute_operation("list_files", {})
        assert r["success"] is False


# ============================================================================
# integrations/shopify_routes.py
# ============================================================================

from integrations import shopify_routes as sr


@pytest.fixture
def shopify_client():
    app = FastAPI()
    app.include_router(sr.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    db = _db(first=None)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture
def ssvc():
    svc = MagicMock()
    svc.exchange_token = AsyncMock(return_value={"access_token": "at",
                                                 "scope": "read"})
    svc.get_shop_info = AsyncMock(return_value={"id": "sh"})
    svc.get_products = AsyncMock(return_value=[{"id": "p"}])
    svc.get_orders = AsyncMock(return_value=[{"id": "o"}])
    svc.get_customers = AsyncMock(return_value=[{"id": "c"}])
    svc.search_customers = AsyncMock(return_value=[{"id": "c"}])
    svc.get_customer = AsyncMock(return_value={"id": "c"})
    svc.get_fulfillments = AsyncMock(return_value=[{"id": "f"}])
    svc.create_fulfillment = AsyncMock(return_value={"id": "f"})
    svc.get_refunds = AsyncMock(return_value=[])
    svc.get_draft_orders = AsyncMock(return_value=[{"id": "d"}])
    svc.complete_draft_order = AsyncMock(return_value={"id": "o"})
    svc.get_transactions = AsyncMock(return_value=[{"id": "t"}])
    svc.get_shop_analytics = AsyncMock(return_value={"revenue": 1})
    svc.get_inventory_levels = AsyncMock(return_value=[{"id": "i"}])
    svc.get_locations = AsyncMock(return_value=[{"id": "l"}])
    svc.register_webhooks = AsyncMock(return_value=[{"ok": True}])
    with patch.object(sr, "shopify_service", svc):
        yield svc


class TestShopifyRoutes:
    def test_auth_url_and_status_root(self, shopify_client):
        assert shopify_client.get("/api/shopify/auth/url").status_code == 200
        assert shopify_client.get("/api/shopify/status").json()["ok"] is True
        assert shopify_client.get("/api/shopify/").json()["service"] == "shopify"

    def test_auth_callback(self, shopify_client, ssvc):
        r = shopify_client.post("/api/shopify/auth/callback",
                                json={"code": "c", "shop": "s.myshopify.com"})
        assert r.status_code == 200 and r.json()["ok"] is True
        ssvc.exchange_token = AsyncMock(side_effect=RuntimeError("x"))
        assert shopify_client.post("/api/shopify/auth/callback",
                                   json={"code": "c",
                                         "shop": "s"}).status_code == 400

    def test_shop_products_orders(self, shopify_client, ssvc):
        q = {"access_token": "t", "shop": "s.myshopify.com"}
        assert shopify_client.get("/api/shopify/shop",
                                  params=q).json()["data"]["id"] == "sh"
        r = shopify_client.get("/api/shopify/products", params=q)
        assert r.json()["count"] == 1
        r = shopify_client.get("/api/shopify/orders", params=q)
        assert r.json()["count"] == 1

    def test_webhooks_setup(self, shopify_client, ssvc):
        q = {"access_token": "t", "shop": "s",
             "webhook_base_url": "https://example.com/hook"}
        with patch("core.ssrf_guard.validate_url"):
            r = shopify_client.post("/api/shopify/webhooks/setup", params=q)
            assert r.status_code == 200 and r.json()["ok"] is True
        from core.ssrf_guard import SSRFError
        with patch("core.ssrf_guard.validate_url",
                   side_effect=SSRFError("bad")):
            r = shopify_client.post("/api/shopify/webhooks/setup", params=q)
            assert r.status_code == 400

    def test_customers(self, shopify_client, ssvc):
        q = {"access_token": "t", "shop": "s"}
        assert shopify_client.get("/api/shopify/customers",
                                  params=q).json()["count"] == 1
        r = shopify_client.get("/api/shopify/customers/search",
                               params={**q, "query": "a@b.c"})
        assert r.json()["count"] == 1
        r = shopify_client.get("/api/shopify/customers/c1", params=q)
        assert r.json()["data"]["id"] == "c"

    def test_fulfillments_refunds_drafts_tx(self, shopify_client, ssvc):
        q = {"access_token": "t", "shop": "s"}
        r = shopify_client.get("/api/shopify/fulfillments/o1", params=q)
        assert r.json()["count"] == 1
        r = shopify_client.post("/api/shopify/fulfillments/o1",
                                params={**q, "location_id": "loc"})
        assert r.json()["ok"] is True
        r = shopify_client.get("/api/shopify/refunds/o1", params=q)
        assert r.json()["count"] == 0
        r = shopify_client.get("/api/shopify/draft-orders", params=q)
        assert r.json()["count"] == 1
        r = shopify_client.post("/api/shopify/draft-orders/d1/complete",
                                params=q)
        assert r.json()["data"]["id"] == "o"
        r = shopify_client.get("/api/shopify/transactions/o1", params=q)
        assert r.json()["count"] == 1

    def test_analytics_inventory_locations(self, shopify_client, ssvc):
        q = {"access_token": "t", "shop": "s"}
        r = shopify_client.get("/api/shopify/analytics", params=q)
        assert r.json()["data"]["revenue"] == 1
        r = shopify_client.get("/api/shopify/inventory", params=q)
        assert r.json()["count"] == 1
        r = shopify_client.get("/api/shopify/locations", params=q)
        assert r.json()["count"] == 1
