"""
Coverage-push unit tests for the SaaS-pair integrations:
Freshdesk, Trello, Shopify, Jira.

All HTTP layers are faked (no network). Tests cover success/error/edge paths,
retry behavior, tenant-context enforcement, sync-to-Postgres cache, and the
regression bugs fixed in this round (each bug test first, then minimal fix).
"""

import json
import sys
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import HTTPException

from integrations import freshdesk_service as fds_mod
from integrations.freshdesk_service import (
    FreshdeskService,
    FreshdeskConfig,
    FreshdeskConstants,
    DEFAULT_FRESHDESK_CONFIG,
    create_freshdesk_service,
)
from integrations.trello_service import TrelloService
from integrations.shopify_service import ShopifyService
from integrations.jira_service import JiraService, get_jira_service


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text="", headers=None):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code} for fake request",
                request=httpx.Request("GET", "http://fake"),
                response=httpx.Response(self.status_code),
            )


class FakeHttpClient:
    """Async httpx-like client with a per-verb scripted queue."""

    def __init__(self, script=None, max_retries=1):
        self._script = {k: list(v) for k, v in (script or {}).items()}
        self.calls = []
        self.closed = False

    def _next(self, verb):
        items = self._script.get(verb, [])
        item = items.pop(0) if items else FakeResponse()
        if isinstance(item, Exception):
            raise item
        return item

    async def get(self, *args, **kwargs):
        self.calls.append(("get", args, kwargs))
        return self._next("get")

    async def post(self, *args, **kwargs):
        self.calls.append(("post", args, kwargs))
        return self._next("post")

    async def put(self, *args, **kwargs):
        self.calls.append(("put", args, kwargs))
        return self._next("put")

    async def delete(self, *args, **kwargs):
        self.calls.append(("delete", args, kwargs))
        return self._next("delete")

    async def aclose(self):
        self.closed = True


class FakeSession:
    """Sync requests-like session with a per-verb scripted queue."""

    def __init__(self, script=None):
        self._script = {k: list(v) for k, v in (script or {}).items()}
        self.calls = []
        self.headers = {"User-Agent": "test"}

    def _next(self, verb):
        items = self._script.get(verb, [])
        item = items.pop(0) if items else FakeResponse()
        if isinstance(item, Exception):
            raise item
        return item

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self._next(method)

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self._next("GET")


class FakeShopifyHTTP:
    """Fake IntegrationHTTP for ShopifyService."""

    def __init__(self, script=None):
        self._script = {k: list(v) for k, v in (script or {}).items()}
        self.calls = []

    def _next(self, verb):
        items = self._script.get(verb, [])
        item = items.pop(0) if items else FakeResponse()
        if isinstance(item, Exception):
            raise item
        return item

    async def get(self, integration, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self._next("GET")

    async def post(self, integration, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self._next("POST")

    async def put(self, integration, url, **kwargs):
        self.calls.append(("PUT", url, kwargs))
        return self._next("PUT")


def make_freshdesk(script=None, config=None):
    cfg = {"freshdesk_api_key": "k", "freshdesk_domain": "acme", "freshdesk_max_retries": 1} if config is None else config
    if config is not None:
        cfg = dict(config)
        cfg.setdefault("freshdesk_max_retries", 1)
    svc = FreshdeskService(config=cfg)
    svc.client = FakeHttpClient(script)
    return svc


def make_trello(script=None):
    svc = TrelloService(config={"api_key": "k", "token": "t"})
    svc.session = FakeSession(script)
    return svc


def make_shopify(script=None, config=None):
    cfg = {"api_key": "k", "shop_name": "acme", "access_token": "t"} if config is None else config
    svc = ShopifyService(config=cfg)
    svc.http = FakeShopifyHTTP(script)
    return svc


def make_jira(script=None, config=None):
    cfg = config or {"access_token": "tok", "cloud_id": "CLOUD1"}
    svc = JiraService(config=cfg)
    svc.session = FakeSession(script)
    return svc


def make_db_session(first_results):
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.side_effect = first_results
    return db


@pytest.fixture
def patch_session_local(monkeypatch):
    def _patch(db):
        monkeypatch.setattr("core.database.SessionLocal", lambda: db)
    return _patch


# ---------------------------------------------------------------------------
# Freshdesk
# ---------------------------------------------------------------------------

FRESHDESK_SIMPLE = [
    ("get_ticket", (123,), "get"),
    ("update_ticket", (123, {"subject": "x"}), "put"),
    ("add_ticket_note", (123, {"body": "n"}), "post"),
    ("get_ticket_conversations", (123,), "get"),
    ("create_contact", ({"name": "n"}), "post"),
    ("get_contacts", (), "get"),
    ("get_contact", (1,), "get"),
    ("update_contact", (1, {"name": "n"}), "put"),
    ("create_company", ({"name": "c"}), "post"),
    ("get_companies", (), "get"),
    ("get_company", (1,), "get"),
    ("get_agents", (), "get"),
    ("get_agent", (1,), "get"),
    ("get_groups", (), "get"),
    ("get_group", (1,), "get"),
    ("get_account_info", (), "get"),
    ("search_contacts", ("acme",), "get"),
]


@pytest.mark.parametrize("attr,args,verb", FRESHDESK_SIMPLE)
async def test_freshdesk_simple_ops_success(attr, args, verb):
    svc = make_freshdesk(script={verb: [FakeResponse(json_data={"id": 1})]})
    result = await getattr(svc, attr)(*args)
    assert result == {"id": 1}
    assert svc.client.calls[0][0] == verb


async def test_freshdesk_delete_ticket():
    svc = make_freshdesk(script={"delete": [FakeResponse(json_data={})]})
    assert await svc.delete_ticket(123) is True
    assert svc.client.calls[0][0] == "delete"


@pytest.mark.parametrize("attr,args,verb", FRESHDESK_SIMPLE)
async def test_freshdesk_simple_ops_http_error(attr, args, verb):
    svc = make_freshdesk(script={verb: [FakeResponse(status_code=500)]})
    with pytest.raises(Exception):
        await getattr(svc, attr)(*args)


@pytest.mark.parametrize("attr,args,verb", FRESHDESK_SIMPLE)
async def test_freshdesk_simple_ops_network_error(attr, args, verb):
    svc = make_freshdesk(script={verb: [httpx.ConnectError("boom")]})
    with pytest.raises(httpx.RequestError):
        await getattr(svc, attr)(*args)


async def test_freshdesk_get_tickets_params():
    svc = make_freshdesk(script={"get": [FakeResponse(json_data=[{"id": 1}])]})
    result = await svc.get_tickets(page=2, per_page=10, status="open", priority=3, created_since="2026-01-01")
    assert result == [{"id": 1}]
    params = svc.client.calls[0][2]["params"]
    assert params == {"page": 2, "per_page": 10, "status": "open", "priority": 3, "created_since": "2026-01-01"}


async def test_freshdesk_get_tickets_no_filters():
    svc = make_freshdesk(script={"get": [FakeResponse(json_data=[])]})
    await svc.get_tickets()
    params = svc.client.calls[0][2]["params"]
    assert params == {"page": 1, "per_page": 30}


async def test_freshdesk_metrics_params():
    svc = make_freshdesk(script={"get": [FakeResponse(json_data={"count": 1})]})
    await svc.get_tickets_metrics(date_range="30d", group_by="status")
    params = svc.client.calls[0][2]["params"]
    assert params == {"date_range": "30d", "group_by": "status"}

    svc2 = make_freshdesk(script={"get": [FakeResponse(json_data={"count": 1})]})
    await svc2.get_tickets_metrics()
    assert svc2.client.calls[0][2]["params"] == {}


async def test_freshdesk_satisfaction_ratings_params():
    svc = make_freshdesk(script={"get": [FakeResponse(json_data=[])]})
    await svc.get_satisfaction_ratings(ticket_id=5, date_range="7d")
    params = svc.client.calls[0][2]["params"]
    assert params == {"ticket_id": 5, "date_range": "7d"}


async def test_freshdesk_search_tickets():
    svc = make_freshdesk(script={"get": [FakeResponse(json_data=[{"id": 1}])]})
    result = await svc.search_tickets("urgent", filters={"status": 2})
    assert result == [{"id": 1}]
    params = svc.client.calls[0][2]["params"]
    assert params == {"query": "urgent", "status": 2}

    svc2 = make_freshdesk(script={"get": [FakeResponse(json_data=[])]})
    await svc2.search_tickets("q")
    assert svc2.client.calls[0][2]["params"] == {"query": "q"}


async def test_freshdesk_handle_request_retries_http_error_then_success():
    svc = make_freshdesk(script={"get": [FakeResponse(status_code=500), FakeResponse(json_data=[{"id": 1}])]})
    svc.max_retries = 3
    result = await svc._handle_request(svc.client.get, "http://x")
    assert result == [{"id": 1}]
    assert len(svc.client.calls) == 2


async def test_freshdesk_handle_request_retries_network_error_then_success():
    svc = make_freshdesk(script={"get": [httpx.ConnectError("boom"), FakeResponse(json_data=[{"id": 1}])]})
    svc.max_retries = 3
    result = await svc._handle_request(svc.client.get, "http://x")
    assert result == [{"id": 1}]
    assert len(svc.client.calls) == 2


async def test_freshdesk_handle_request_raises_after_all_retries():
    svc = make_freshdesk(script={"get": [FakeResponse(status_code=500), FakeResponse(status_code=500), FakeResponse(status_code=500)]})
    svc.max_retries = 3
    with pytest.raises(httpx.HTTPStatusError):
        await svc._handle_request(svc.client.get, "http://x")
    assert len(svc.client.calls) == 3


async def test_freshdesk_handle_request_network_error_raises_last():
    svc = make_freshdesk(script={"get": [httpx.ConnectError("boom"), httpx.ConnectError("boom"), httpx.ConnectError("boom")]})
    svc.max_retries = 3
    with pytest.raises(httpx.RequestError):
        await svc._handle_request(svc.client.get, "http://x")
    assert len(svc.client.calls) == 3


async def test_freshdesk_retry_does_not_create_throwaway_clients(monkeypatch):
    """Regression: each retry must not instantiate a fresh httpx.AsyncClient."""
    svc = make_freshdesk(script={"get": [httpx.ConnectError("boom"), FakeResponse(json_data=[{"id": 1}])]})
    svc.max_retries = 3
    created = []
    real_ctor = httpx.AsyncClient

    def spy_ctor(*a, **kw):
        created.append(1)
        return real_ctor(*a, **kw)

    monkeypatch.setattr(httpx, "AsyncClient", spy_ctor)
    result = await svc._handle_request(svc.client.get, "http://x")
    assert result == [{"id": 1}]
    assert created == []


async def test_freshdesk_execute_operation_get_tickets():
    svc = make_freshdesk(script={"get": [FakeResponse(json_data=[{"id": 1}])]})
    out = await svc.execute_operation("get_tickets", {"page": 2, "per_page": 5}, context={"tenant_id": "default"})
    assert out["success"] is True
    assert out["result"] == [{"id": 1}]
    params = svc.client.calls[0][2]["params"]
    assert params == {"page": 2, "per_page": 5}


async def test_freshdesk_execute_operation_get_tickets_passes_filters():
    """Regression: advertised status/priority/created_since filters must reach the API."""
    svc = make_freshdesk(script={"get": [FakeResponse(json_data=[])]})
    out = await svc.execute_operation(
        "get_tickets",
        {"page": 1, "per_page": 30, "status": "open", "priority": 2, "created_since": "2026-08-01T00:00:00Z"},
        context={"tenant_id": "default"},
    )
    assert out["success"] is True
    params = svc.client.calls[0][2]["params"]
    assert params["status"] == "open"
    assert params["priority"] == 2
    assert params["created_since"] == "2026-08-01T00:00:00Z"


async def test_freshdesk_execute_operation_create_ticket():
    svc = make_freshdesk(script={"post": [FakeResponse(json_data={"id": 99})]})
    out = await svc.execute_operation("create_ticket", {"data": {"subject": "s"}}, context={"tenant_id": "default"})
    assert out["success"] is True
    assert out["result"] == {"id": 99}
    assert svc.client.calls[0][2]["json"] == {"subject": "s"}


async def test_freshdesk_execute_operation_search_tickets():
    svc = make_freshdesk(script={"get": [FakeResponse(json_data=[])]})
    out = await svc.execute_operation("search_tickets", {"query": "bug"}, context={"tenant_id": "default"})
    assert out["success"] is True
    assert svc.client.calls[0][2]["params"] == {"query": "bug"}


async def test_freshdesk_execute_operation_tenant_mismatch():
    svc = make_freshdesk()
    out = await svc.execute_operation("get_tickets", {}, context={"tenant_id": "other"})
    assert out["success"] is False
    assert out["error"] == "Tenant mismatch"


async def test_freshdesk_execute_operation_unknown_op():
    svc = make_freshdesk()
    out = await svc.execute_operation("nope", {}, context={"tenant_id": "default"})
    assert out["success"] is False
    assert "not supported" in out["error"]


async def test_freshdesk_execute_operation_error_does_not_leak():
    """Regression: transient failure details must not leak into the envelope."""
    svc = make_freshdesk(script={"get": [httpx.ConnectError("connection refused to 10.0.0.8:443")]})
    out = await svc.execute_operation("get_tickets", {}, context={"tenant_id": "default"})
    assert out["success"] is False
    assert "10.0.0.8" not in out["error"]
    assert "connection refused" not in out["error"]


def test_freshdesk_credentials_encoding():
    svc = make_freshdesk()
    import base64
    assert svc._encode_credentials() == base64.b64encode(b"k:X").decode()


def test_freshdesk_no_credentials():
    svc = FreshdeskService(config={})
    assert svc.base_url == ""
    assert svc.headers["Authorization"] == ""


def test_freshdesk_health_check_missing_credentials():
    svc = FreshdeskService(config={})
    result = svc.health_check()
    assert result["healthy"] is False
    assert result["message"] == "Missing credentials"


def test_freshdesk_health_check_success(monkeypatch):
    svc = make_freshdesk()
    monkeypatch.setattr("requests.get", lambda *a, **kw: FakeResponse(status_code=200, text="ok"))
    result = svc.health_check()
    assert result["healthy"] is True
    assert result["status"] == "healthy"


def test_freshdesk_health_check_unhealthy(monkeypatch):
    svc = make_freshdesk()
    monkeypatch.setattr("requests.get", lambda *a, **kw: FakeResponse(status_code=503, text="down"))
    result = svc.health_check()
    assert result["healthy"] is False
    assert result["api_response"] is None


def test_freshdesk_health_check_exception(monkeypatch):
    svc = make_freshdesk()

    def boom(*a, **kw):
        raise RuntimeError("network down")

    monkeypatch.setattr("requests.get", boom)
    result = svc.health_check()
    assert result["healthy"] is False
    assert result["status"] == "unhealthy"


def test_freshdesk_status_and_priority_names():
    svc = make_freshdesk()
    assert svc.get_status_name(2) == "Open"
    assert svc.get_status_name(3) == "Pending"
    assert svc.get_status_name(4) == "Resolved"
    assert svc.get_status_name(5) == "Closed"
    assert svc.get_status_name(99) == "Unknown"
    assert svc.get_priority_name(1) == "Low"
    assert svc.get_priority_name(2) == "Medium"
    assert svc.get_priority_name(3) == "High"
    assert svc.get_priority_name(4) == "Urgent"
    assert svc.get_priority_name(99) == "Unknown"


def test_freshdesk_capabilities():
    svc = make_freshdesk()
    caps = svc.get_capabilities()
    assert len(caps["operations"]) == 3
    assert caps["supports_webhooks"] is True
    assert caps["rate_limits"]["requests_per_minute"] == 100


def test_freshdesk_close():
    svc = make_freshdesk()
    async def run():
        await svc.close()
    import asyncio
    asyncio.run(run())
    assert svc.client.closed


async def test_freshdesk_upload_attachment(monkeypatch):
    svc = make_freshdesk()
    fake_client = FakeHttpClient({"post": [FakeResponse(json_data={"attachment": {"id": 1}})]})
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: fake_client)
    result = await svc.upload_attachment(b"data", "file.txt")
    assert result == {"attachment": {"id": 1}}
    assert fake_client.closed


async def test_freshdesk_sync_to_postgres_cache_create(patch_session_local):
    svc = make_freshdesk(script={"get": [FakeResponse(json_data=[{"id": 1}, {"id": 2}]), FakeResponse(json_data=[{"id": 3}])]})
    db = make_db_session([None, None])
    patch_session_local(db)
    result = await svc.sync_to_postgres_cache("ws1")
    assert result["success"] is True
    assert result["metrics_synced"] == 2
    assert db.commit.called
    assert db.close.called
    assert db.add.call_count == 2


async def test_freshdesk_sync_to_postgres_cache_update(patch_session_local):
    svc = make_freshdesk(script={"get": [FakeResponse(json_data=[]), FakeResponse(json_data=[])]})
    existing = SimpleNamespace(value=0, last_synced_at=None)
    db = make_db_session([existing, None])
    patch_session_local(db)
    result = await svc.sync_to_postgres_cache("ws1")
    assert result["success"] is True
    assert existing.value == 0.0


async def test_freshdesk_sync_counts_zero_on_api_error(patch_session_local):
    svc = make_freshdesk(script={"get": [httpx.ConnectError("boom"), FakeResponse(json_data=[])]})
    db = make_db_session([None, None])
    patch_session_local(db)
    result = await svc.sync_to_postgres_cache("ws1")
    assert result["success"] is True
    added = [c.args[0] for c in db.add.call_args_list]
    assert added[0].value == 0.0
    assert added[1].value == 0.0


async def test_freshdesk_sync_commit_failure_no_leak(patch_session_local):
    svc = make_freshdesk(script={"get": [FakeResponse(json_data=[]), FakeResponse(json_data=[])]})
    db = make_db_session([None, None])
    db.commit.side_effect = ValueError("sqlite disk I/O error at /var/data")
    patch_session_local(db)
    result = await svc.sync_to_postgres_cache("ws1")
    assert result["success"] is False
    assert "disk I/O" not in result["error"]
    assert db.rollback.called


async def test_freshdesk_full_sync(patch_session_local):
    svc = make_freshdesk(script={"get": [FakeResponse(json_data=[]), FakeResponse(json_data=[])]})
    db = make_db_session([None, None])
    patch_session_local(db)
    result = await svc.full_sync("ws1")
    assert result["success"] is True
    assert result["workspace_id"] == "ws1"
    assert result["postgres_cache"]["success"] is True


def test_freshdesk_factory():
    svc = create_freshdesk_service("k2", "beta", freshdesk_timeout=10)
    assert svc.api_key == "k2"
    assert svc.domain == "beta"
    assert svc.timeout == 10


async def test_freshdesk_connection_test_success(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **kw: FakeResponse(status_code=200, text="ok"))
    assert await fds_mod.test_freshdesk_connection("k", "acme") is True


async def test_freshdesk_connection_test_failure(monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("nope")

    monkeypatch.setattr("requests.get", boom)
    assert await fds_mod.test_freshdesk_connection("k", "acme") is False


def test_freshdesk_constants_and_config():
    assert FreshdeskConstants.STATUS_OPEN == 2
    assert FreshdeskConstants.PRIORITY_URGENT == 4
    assert FreshdeskConstants.MAX_TICKETS_PER_PAGE == 100
    cfg = FreshdeskConfig(api_key="k", domain="d")
    assert cfg.api_version == "v2"
    assert cfg.timeout == 30
    assert cfg.max_retries == 3
    assert DEFAULT_FRESHDESK_CONFIG["api_version"] == "v2"


# ---------------------------------------------------------------------------
# Trello
# ---------------------------------------------------------------------------

TRELLO_GET_LIST = [
    ("get_boards", ("open", None, 50)),
    ("get_lists", ("b1", "open", None, 50)),
    ("get_members", ("b1", None)),
    ("get_labels", ("b1",)),
    ("get_checklists", ("c1",)),
    ("get_comments", ("c1",)),
    ("get_activities", ("b1", 50, None)),
    ("get_cards", ("l1", None, "open", None, 50)),
]


@pytest.mark.parametrize("attr,args", TRELLO_GET_LIST)
def test_trello_list_ops_success(attr, args):
    svc = make_trello(script={"GET": [FakeResponse(json_data=[{"id": 1}])]})
    result = getattr(svc, attr)(*args)
    assert result == [{"id": 1}]


@pytest.mark.parametrize("attr,args", TRELLO_GET_LIST)
def test_trello_list_ops_error_returns_empty(attr, args):
    svc = make_trello(script={"GET": [FakeResponse(status_code=500)]})
    result = getattr(svc, attr)(*args)
    assert result == []


@pytest.mark.parametrize("attr,args", [
    ("get_board", ("b1",)),
    ("get_card", ("c1",)),
    ("create_board", ("name",)),
    ("create_list", ("b1", "list")),
    ("create_card", ("card", "l1")),
    ("update_card", ("c1", {"name": "x"})),
    ("add_comment", ("c1", "hi")),
    ("create_checklist", ("c1", "cl")),
    ("add_checklist_item", ("cl1", "item")),
    ("move_card", ("c1", "l2")),
    ("add_member_to_card", ("c1", "m1")),
    ("add_label_to_card", ("c1", "lab1")),
    ("create_label", ("b1", "urgent")),
    ("get_user_profile", ()),
])
def test_trello_single_ops_success(attr, args):
    svc = make_trello(script={"GET": [FakeResponse(json_data={"id": 1})], "POST": [FakeResponse(json_data={"id": 1})], "PUT": [FakeResponse(json_data={"id": 1})], "DELETE": [FakeResponse(json_data={})]})
    result = getattr(svc, attr)(*args)
    assert result == {"id": 1} or result is True


@pytest.mark.parametrize("attr,args", [
    ("get_board", ("b1",)),
    ("get_card", ("c1",)),
    ("create_board", ("name",)),
    ("create_list", ("b1", "list")),
    ("update_card", ("c1", {"name": "x"})),
    ("add_comment", ("c1", "hi")),
    ("create_checklist", ("c1", "cl")),
    ("add_checklist_item", ("cl1", "item")),
    ("move_card", ("c1", "l2")),
    ("add_member_to_card", ("c1", "m1")),
    ("add_label_to_card", ("c1", "lab1")),
    ("create_label", ("b1", "urgent")),
    ("get_user_profile", ()),
])
def test_trello_single_ops_error(attr, args):
    svc = make_trello(script={"GET": [FakeResponse(status_code=500)], "POST": [FakeResponse(status_code=500)], "PUT": [FakeResponse(status_code=500)], "DELETE": [FakeResponse(status_code=500)]})
    result = getattr(svc, attr)(*args)
    assert result is None


def test_trello_bool_ops_success():
    svc = make_trello(script={"PUT": [FakeResponse(json_data={})], "DELETE": [FakeResponse(json_data={})]})
    assert svc.archive_card("c1") is True
    assert svc.delete_card("c1") is True
    assert svc.remove_member_from_card("c1", "m1") is True


def test_trello_bool_ops_error():
    svc = make_trello(script={"PUT": [FakeResponse(status_code=500)], "DELETE": [FakeResponse(status_code=500), FakeResponse(status_code=500)]})
    assert svc.archive_card("c1") is False
    assert svc.delete_card("c1") is False
    assert svc.remove_member_from_card("c1", "m1") is False


def test_trello_create_card_full_options():
    svc = make_trello(script={"POST": [FakeResponse(json_data={"id": 1})]})
    result = svc.create_card("name", "l1", description="d", pos="top", due="2026-09-01",
                             labels=["l1", "l2"], members=["m1"])
    assert result == {"id": 1}
    body = svc.session.calls[0][2]["json"]
    assert body["due"] == "2026-09-01"
    assert body["idLabels"] == "l1,l2"
    assert body["idMembers"] == "m1"


def test_trello_create_card_error_returns_none():
    svc = make_trello(script={"POST": [FakeResponse(status_code=500)]})
    assert svc.create_card("name", "l1") is None


def test_trello_get_cards_by_board_and_default():
    svc = make_trello(script={"GET": [FakeResponse(json_data=[]), FakeResponse(json_data=[])]})
    assert svc.get_cards(board_id="b1") == []
    assert svc.get_cards() == []
    assert svc.session.calls[0][1].endswith("/boards/b1/cards")
    assert svc.session.calls[1][1].endswith("/members/me/cards")


def test_trello_get_boards_fields_and_search():
    svc = make_trello(script={"GET": [FakeResponse(json_data=[]), FakeResponse(json_data={"cards": [{"id": 1}]})]})
    assert svc.get_boards(fields=["id", "name"]) == []
    params = svc.session.calls[0][2]["params"]
    assert params["fields"] == "id,name"
    assert params["key"] == "k"
    assert params["token"] == "t"
    assert svc.search("widgets", board_id="b1", limit=5) == [{"id": 1}]
    params = svc.session.calls[1][2]["params"]
    assert params["idBoards"] == "b1"
    assert params["modelTypes"] == "cards"
    assert params["limit"] == 5


def test_trello_search_error_empty():
    svc = make_trello(script={"GET": [FakeResponse(status_code=500)]})
    assert svc.search("q") == []


def test_trello_get_activities_since():
    svc = make_trello(script={"GET": [FakeResponse(json_data=[])]})
    svc.get_activities("b1", since="2026-01-01T00:00:00Z")
    params = svc.session.calls[0][2]["params"]
    assert params["since"] == "2026-01-01T00:00:00Z"


async def test_trello_disabled_service():
    svc = TrelloService(config={})
    assert svc.enabled is False
    with pytest.raises(ValueError):
        svc._make_request("GET", "/members/me")
    info = await svc.get_service_info()
    assert info["status"] == "disabled"
    health = svc.health_check()
    assert health["healthy"] is False


def test_trello_connection_success():
    svc = make_trello(script={"GET": [FakeResponse(json_data={"username": "u", "fullName": "U Name"})]})
    result = svc.test_connection()
    assert result["status"] == "success"
    assert result["authenticated"] is True
    assert result["user"] == "u"


def test_trello_connection_auth_failure():
    svc = make_trello(script={"GET": [FakeResponse(status_code=401)]})
    result = svc.test_connection()
    assert result["status"] == "error"
    assert result["authenticated"] is False
    assert "401" in result["message"]


def test_trello_connection_exception_no_leak():
    """Regression: exception internals must not leak into the result message."""
    svc = make_trello(script={"GET": [httpx.ConnectError("connection refused to api.trello.com:443")]})
    result = svc.test_connection()
    assert result["status"] == "error"
    assert result["authenticated"] is False
    assert "api.trello.com" not in result["message"]
    assert "connection refused" not in result["message"]


def test_trello_health_check():
    svc = make_trello(script={"GET": [FakeResponse(json_data={"username": "u"})]})
    result = svc.health_check()
    assert result["healthy"] is True
    assert result["service"] == "trello"
    assert result["details"]["status"] == "success"


def test_trello_capabilities():
    svc = make_trello()
    caps = svc.get_capabilities()
    assert len(caps["operations"]) == 5
    assert caps["required_params"] == ["api_key", "access_token"]


async def test_trello_execute_operation_tenant_mismatch():
    svc = make_trello()
    out = await svc.execute_operation("get_boards", {}, context={"tenant_id": "other"})
    assert out["success"] is False
    assert out["error"] == "Tenant ID mismatch"


async def test_trello_execute_operation_unknown():
    svc = make_trello()
    out = await svc.execute_operation("nope", {}, None)
    assert out["success"] is False
    assert "Unknown operation" in out["error"]


async def test_trello_execute_operation_create_card_success():
    svc = make_trello(script={"POST": [FakeResponse(json_data={"id": 1})]})
    out = await svc.execute_operation("create_card", {"name": "c", "list_id": "l1", "desc": "d"}, context={"tenant_id": "default"})
    assert out["success"] is True
    assert out["result"] == {"id": 1}
    assert out["details"]["tenant_id"] == "default"


async def test_trello_execute_operation_create_card_failure_envelope():
    svc = make_trello(script={"POST": [FakeResponse(status_code=500)]})
    out = await svc.execute_operation("create_card", {"name": "c", "list_id": "l1"}, context={"tenant_id": "default"})
    assert out["success"] is False
    assert out["operation"] == "create_card"


def test_trello_op_update_card_excludes_token():
    """Regression: the auth token must not be sent inside the card payload."""
    svc = make_trello(script={"PUT": [FakeResponse(json_data={"id": 1})]})
    out = svc._op_update_card({"card_id": "c1", "name": "new", "token": "SECRET", "context": "x"}, None)
    assert out == {"id": 1}
    body = svc.session.calls[0][2]["json"]
    assert "token" not in body
    assert "card_id" not in body
    assert body["name"] == "new"


def test_trello_op_get_cards_and_boards():
    svc = make_trello(script={"GET": [FakeResponse(json_data=[]), FakeResponse(json_data=[])]})
    assert svc._op_get_cards({"list_id": "l1"}, None) == []
    assert svc._op_get_boards({"filter": "all"}, None) == []


def test_trello_op_add_comment_failure():
    svc = make_trello(script={"POST": [FakeResponse(status_code=500)]})
    with pytest.raises(Exception):
        svc._op_add_comment({"card_id": "c1", "text": "hi"}, None)


def test_trello_make_request_full_url_and_token_override():
    svc = make_trello(script={"GET": [FakeResponse(json_data={})]})
    svc._make_request("GET", "https://api.trello.com/1/custom", token="tk2")
    assert svc.session.calls[0][1] == "https://api.trello.com/1/custom"
    params = svc.session.calls[0][2]["params"]
    assert params["token"] == "tk2"


def test_trello_sync_to_postgres_cache_create(patch_session_local):
    svc = make_trello(script={"GET": [FakeResponse(json_data=[{"id": 1}])]})
    db = make_db_session([None])
    patch_session_local(db)
    result = svc.sync_to_postgres_cache("ws1")
    assert result["success"] is True
    assert result["metrics_synced"] == 1
    assert db.commit.called


def test_trello_sync_to_postgres_cache_update(patch_session_local):
    svc = make_trello(script={"GET": [FakeResponse(json_data=[])]})
    existing = SimpleNamespace(value=1, last_synced_at=None)
    db = make_db_session([existing])
    patch_session_local(db)
    result = svc.sync_to_postgres_cache("ws1")
    assert result["success"] is True
    assert existing.value == 0.0


def test_trello_sync_commit_failure_no_leak(patch_session_local):
    svc = make_trello(script={"GET": [FakeResponse(json_data=[])]})
    db = make_db_session([None])
    db.commit.side_effect = ValueError("postgres connection reset")
    patch_session_local(db)
    result = svc.sync_to_postgres_cache("ws1")
    assert result["success"] is False
    assert "postgres connection reset" not in result["error"]
    assert db.rollback.called


def test_trello_sync_session_failure_no_leak(monkeypatch):
    svc = make_trello(script={"GET": [FakeResponse(json_data=[])]})

    def boom():
        raise RuntimeError("db unreachable")

    monkeypatch.setattr("core.database.SessionLocal", boom)
    result = svc.sync_to_postgres_cache("ws1")
    assert result["success"] is False
    assert "db unreachable" not in result["error"]


def test_trello_full_sync(patch_session_local):
    svc = make_trello(script={"GET": [FakeResponse(json_data=[])]})
    db = make_db_session([None])
    patch_session_local(db)
    result = svc.full_sync("ws1")
    assert result["success"] is True
    assert result["workspace_id"] == "ws1"


# ---------------------------------------------------------------------------
# Shopify
# ---------------------------------------------------------------------------

async def test_shopify_base_url_and_headers():
    svc = make_shopify()
    assert svc._get_base_url("acme") == "https://acme.myshopify.com/admin/api/2023-10"
    assert svc._get_base_url("acme.myshopify.com") == "https://acme.myshopify.com/admin/api/2023-10"
    headers = svc._get_headers("tok")
    assert headers["X-Shopify-Access-Token"] == "tok"
    assert headers["Content-Type"] == "application/json"


async def test_shopify_exchange_token():
    svc = make_shopify(script={"POST": [FakeResponse(json_data={"access_token": "t"})]})
    result = await svc.exchange_token("code1", "acme.myshopify.com")
    assert result == {"access_token": "t"}
    url = svc.http.calls[0][1]
    assert url == "https://acme.myshopify.com/admin/oauth/access_token"


async def test_shopify_exchange_token_http_error():
    svc = make_shopify(script={"POST": [httpx.HTTPError("bad gateway")]})
    with pytest.raises(HTTPException) as exc:
        await svc.exchange_token("code1", "acme.myshopify.com")
    assert exc.value.status_code == 400


SHOPIFY_LIST_GETS = [
    ("get_products", ("t", "acme", 5), "products"),
    ("get_orders", ("t", "acme", 5), "orders"),
    ("get_customers", ("t", "acme", 5), "customers"),
    ("get_locations", ("t", "acme"), "locations"),
    ("get_draft_orders", ("t", "acme", 5), "draft_orders"),
]


@pytest.mark.parametrize("attr,args,key", SHOPIFY_LIST_GETS)
async def test_shopify_list_gets_success(attr, args, key):
    svc = make_shopify(script={"GET": [FakeResponse(json_data={key: [{"id": 1}]})]})
    result = await getattr(svc, attr)(*args)
    assert result == [{"id": 1}]


@pytest.mark.parametrize("attr,args,key", SHOPIFY_LIST_GETS)
async def test_shopify_list_gets_error(attr, args, key):
    svc = make_shopify(script={"GET": [FakeResponse(status_code=500)]})
    with pytest.raises(HTTPException) as exc:
        await getattr(svc, attr)(*args)
    assert exc.value.status_code == 500


async def test_shopify_get_shop_info():
    svc = make_shopify(script={"GET": [FakeResponse(json_data={"shop": {"name": "Acme"}})]})
    result = await svc.get_shop_info("t", "acme")
    assert result == {"name": "Acme"}
    assert "X-Shopify-Access-Token" in svc.http.calls[0][2]["headers"]


async def test_shopify_register_webhooks():
    svc = make_shopify(script={"POST": [FakeResponse(json_data={"webhook": {"id": 1}}), FakeResponse(status_code=422), FakeResponse(status_code=500)]})
    results = await svc.register_webhooks("t", "acme", "https://hooks.example.com/shopify")
    assert results[0]["status"] == "registered"
    assert results[1]["status"] == "already_exists"
    assert results[2]["status"] == "failed"


async def test_shopify_register_webhook_failure_no_leak():
    svc = make_shopify(script={"POST": [FakeResponse(status_code=500)]})
    results = await svc.register_webhooks("t", "acme", "https://hooks.example.com")
    assert results[0]["status"] == "failed"
    assert "hooks.example.com" not in results[0]["error"]


async def test_shopify_inventory_levels():
    svc = make_shopify(script={"GET": [FakeResponse(json_data={"inventory_levels": [{"id": 1}]})]})
    assert await svc.get_inventory_levels("t", "acme", "loc1") == [{"id": 1}]
    assert svc.http.calls[0][2]["params"] == {"location_ids": "loc1"}
    svc2 = make_shopify(script={"GET": [FakeResponse(json_data={"inventory_levels": []})]})
    await svc2.get_inventory_levels("t", "acme")
    assert svc2.http.calls[0][2]["params"] == {}


async def test_shopify_get_customer_and_search():
    svc = make_shopify(script={"GET": [FakeResponse(json_data={"customer": {"id": 1}}), FakeResponse(json_data={"customers": [{"id": 2}]})]})
    assert await svc.get_customer("t", "acme", "1") == {"id": 1}
    assert await svc.search_customers("t", "acme", "bob@example.com") == [{"id": 2}]
    assert svc.http.calls[1][2]["params"] == {"query": "bob@example.com"}


async def test_shopify_fulfillments():
    svc = make_shopify(script={"GET": [FakeResponse(json_data={"fulfillments": [{"id": 1}]})], "POST": [FakeResponse(json_data={"fulfillment": {"id": 2}})]})
    assert await svc.get_fulfillments("t", "acme", "o1") == [{"id": 1}]
    result = await svc.create_fulfillment("t", "acme", "o1", "loc1", tracking_number="TN1", tracking_company="FedEx")
    assert result == {"id": 2}
    body = svc.http.calls[1][2]["json"]
    assert body["fulfillment"]["tracking_number"] == "TN1"
    assert body["fulfillment"]["tracking_company"] == "FedEx"
    assert body["fulfillment"]["notify_customer"] is True


async def test_shopify_create_fulfillment_minimal():
    svc = make_shopify(script={"POST": [FakeResponse(json_data={"fulfillment": {"id": 2}})]})
    await svc.create_fulfillment("t", "acme", "o1", "loc1")
    body = svc.http.calls[0][2]["json"]
    assert "tracking_number" not in body["fulfillment"]


async def test_shopify_refunds():
    svc = make_shopify(script={"GET": [FakeResponse(json_data={"refunds": [{"id": 1}]})], "POST": [FakeResponse(json_data={"refund": {"id": 2}})]})
    assert await svc.get_refunds("t", "acme", "o1") == [{"id": 1}]
    assert await svc.calculate_refund("t", "acme", "o1", [{"line_item_id": 5}]) == {"id": 2}


async def test_shopify_draft_orders():
    svc = make_shopify(script={"POST": [FakeResponse(json_data={"draft_order": {"id": 1}}), FakeResponse(json_data={"draft_order": {"id": 2}})], "PUT": [FakeResponse(json_data={"draft_order": {"id": 3}})]})
    result = await svc.create_draft_order("t", "acme", [{"variant_id": 1}], customer_id="c1")
    assert result == {"id": 1}
    body = svc.http.calls[0][2]["json"]
    assert body["draft_order"]["customer"] == {"id": "c1"}
    result2 = await svc.create_draft_order("t", "acme", [{"variant_id": 2}])
    assert result2 == {"id": 2}
    body2 = svc.http.calls[1][2]["json"]
    assert "customer" not in body2["draft_order"]
    assert await svc.complete_draft_order("t", "acme", "d1") == {"id": 3}


async def test_shopify_transactions():
    svc = make_shopify(script={"GET": [FakeResponse(json_data={"transactions": [{"id": 1}]})]})
    assert await svc.get_transactions("t", "acme", "o1") == [{"id": 1}]


async def test_shopify_counts():
    svc = make_shopify(script={"GET": [FakeResponse(json_data={"count": 7}), FakeResponse(json_data={"count": 3}), FakeResponse(json_data={"count": 2})]})
    assert await svc.get_order_count("t", "acme") == 7
    assert await svc.get_product_count("t", "acme") == 3
    assert await svc.get_customer_count("t", "acme") == 2


async def test_shopify_counts_error_returns_zero():
    svc = make_shopify(script={"GET": [FakeResponse(status_code=500), FakeResponse(status_code=500), FakeResponse(status_code=500)]})
    assert await svc.get_order_count("t", "acme") == 0
    assert await svc.get_product_count("t", "acme") == 0
    assert await svc.get_customer_count("t", "acme") == 0


async def test_shopify_analytics():
    svc = make_shopify(script={"GET": [
        FakeResponse(json_data={"count": 10}),
        FakeResponse(json_data={"count": 4}),
        FakeResponse(json_data={"count": 6}),
        FakeResponse(json_data={"shop": {"name": "Acme", "domain": "acme.myshopify.com", "currency": "USD", "plan_name": "pro"}}),
    ]})
    result = await svc.get_shop_analytics("t", "acme")
    assert result["shop_name"] == "Acme"
    assert result["metrics"] == {"total_orders": 10, "total_products": 4, "total_customers": 6}
    assert result["plan"] == "pro"


async def test_shopify_analytics_error():
    svc = make_shopify(script={"GET": [FakeResponse(status_code=500)]})
    with pytest.raises(HTTPException) as exc:
        await svc.get_shop_analytics("t", "acme")
    assert exc.value.status_code == 500


async def test_shopify_capabilities_and_health():
    svc = make_shopify()
    caps = svc.get_capabilities()
    assert len(caps["operations"]) == 4
    assert caps["supports_webhooks"] is True
    result = await svc.health_check()
    assert result["healthy"] is True
    missing = ShopifyService(config={})
    result2 = await missing.health_check()
    assert result2["healthy"] is False
    assert "Missing API key" in result2["message"]


async def test_shopify_execute_operation_get_products():
    svc = make_shopify(script={"GET": [FakeResponse(json_data={"products": [{"id": 1}]})]})
    out = await svc.execute_operation("get_products", {"access_token": "t", "shop": "acme", "limit": 3}, None)
    assert out["success"] is True
    assert out["result"] == [{"id": 1}]
    assert svc.http.calls[0][2]["params"] == {"limit": 3}


async def test_shopify_execute_operation_unknown_returns_envelope():
    """Regression: unknown operations must return an error envelope, not raise."""
    svc = make_shopify()
    out = await svc.execute_operation("does_not_exist", {}, None)
    assert out["success"] is False
    assert "Unknown operation" in out["error"]


async def test_shopify_execute_operation_http_error_returns_envelope():
    """Regression: API failures must return an error envelope, not a raw HTTPException."""
    svc = make_shopify(script={"GET": [FakeResponse(status_code=500)]})
    out = await svc.execute_operation("get_products", {"access_token": "t", "shop": "acme"}, None)
    assert out["success"] is False


async def test_shopify_execute_operation_full_sync(patch_session_local):
    svc = make_shopify(script={"GET": [
        FakeResponse(json_data={"count": 10}),
        FakeResponse(json_data={"count": 4}),
        FakeResponse(json_data={"count": 6}),
        FakeResponse(json_data={"shop": {"name": "Acme"}}),
    ]})
    db = make_db_session([None, None, None])
    patch_session_local(db)
    out = await svc.execute_operation("full_sync", {"workspace_id": "ws9"}, None)
    assert out["success"] is True
    assert out["result"]["workspace_id"] == "ws9"


async def test_shopify_handle_webhook_orders_create():
    svc = make_shopify(config={"api_key": "k", "shop_name": "acme"})
    payload = {"customer": {"email": "a@b.com"}, "order_number": 1234, "id": "o1"}
    out = await svc.execute_operation("handle_webhook_event", {"payload": payload, "topic": "orders/create"}, None)
    assert out["success"] is True
    result = out["result"]
    assert result["sender_id"] == "a@b.com"
    assert result["recipient_id"] == "acme"
    assert "1234" in result["text"]
    assert result["metadata"]["order_id"] == "o1"


async def test_shopify_handle_webhook_other_topic():
    svc = make_shopify(config={"api_key": "k", "shop_name": "acme"})
    out = await svc.execute_operation("handle_webhook_event", {"payload": {}, "topic": "products/update"}, None)
    assert out["success"] is True
    assert out["result"] is None


async def test_shopify_sync_missing_credentials():
    svc = make_shopify(config={})
    result = await svc.sync_to_postgres_cache("ws1")
    assert result["success"] is False
    assert "Missing Shopify credentials" in result["error"]


async def test_shopify_sync_success(patch_session_local):
    svc = make_shopify(script={"GET": [
        FakeResponse(json_data={"count": 10}),
        FakeResponse(json_data={"count": 4}),
        FakeResponse(json_data={"count": 6}),
        FakeResponse(json_data={"shop": {"name": "Acme"}}),
    ]})
    db = make_db_session([None, None, None])
    patch_session_local(db)
    result = await svc.sync_to_postgres_cache("ws1")
    assert result["success"] is True
    assert result["metrics_synced"] == 3
    assert db.commit.called


async def test_shopify_sync_commit_failure_no_leak(patch_session_local):
    svc = make_shopify(script={"GET": [
        FakeResponse(json_data={"count": 1}),
        FakeResponse(json_data={"count": 1}),
        FakeResponse(json_data={"count": 1}),
        FakeResponse(json_data={"shop": {"name": "Acme"}}),
    ]})
    db = make_db_session([None, None, None])
    db.commit.side_effect = ValueError("too many connections")
    patch_session_local(db)
    result = await svc.sync_to_postgres_cache("ws1")
    assert result["success"] is False
    assert "too many connections" not in result["error"]


async def test_shopify_full_sync(patch_session_local):
    svc = make_shopify(script={"GET": [
        FakeResponse(json_data={"count": 1}),
        FakeResponse(json_data={"count": 1}),
        FakeResponse(json_data={"count": 1}),
        FakeResponse(json_data={"shop": {"name": "Acme"}}),
    ]})
    db = make_db_session([None, None, None])
    patch_session_local(db)
    result = await svc.full_sync("ws1")
    assert result["success"] is True
    assert result["workspace_id"] == "ws1"
    assert result["postgres_cache"]["success"] is True


# ---------------------------------------------------------------------------
# Jira
# ---------------------------------------------------------------------------

def test_jira_init_oauth():
    svc = JiraService(config={"access_token": "tok", "cloud_id": "CLOUD1"})
    assert svc.base_url == "https://api.atlassian.com/ex/jira/CLOUD1"
    assert svc.session.headers["Authorization"] == "Bearer tok"


def test_jira_init_basic_auth():
    svc = JiraService(config={"base_url": "https://myjira.example.invalid", "username": "u", "api_token": "t"})
    assert svc.base_url == "https://myjira.example.invalid"
    assert svc.session.headers["Authorization"].startswith("Basic ")


def test_jira_init_instance_url_as_cloud_id():
    svc = JiraService(config={"access_token": "tok", "instance_url": "CLOUD9"})
    assert svc.base_url == "https://api.atlassian.com/ex/jira/CLOUD9"


def test_jira_init_no_credentials():
    svc = JiraService(config={})
    assert svc.base_url is None
    assert "Authorization" not in svc.session.headers


def test_jira_init_ssrf_blocked():
    with pytest.raises(ValueError):
        JiraService(config={"base_url": "http://169.254.169.254/latest", "username": "u", "api_token": "t"})


def test_jira_make_request_oauth_cloud_id_url():
    """Regression: OAuth cloud_id requests must keep the /ex/jira/{cloud_id} path."""
    svc = make_jira(script={"GET": [FakeResponse(json_data=[])]})
    svc._make_request("GET", "/rest/api/3/project")
    url = svc.session.calls[0][1]
    assert url == "https://api.atlassian.com/ex/jira/CLOUD1/rest/api/3/project"


def test_jira_make_request_basic_url_and_token_override():
    svc = make_jira(script={"GET": [FakeResponse(json_data=[])]})
    svc._make_request("GET", "/rest/api/3/project", token="tk2")
    url = svc.session.calls[0][1]
    assert url == "https://api.atlassian.com/ex/jira/CLOUD1/rest/api/3/project"
    assert svc.session.calls[0][2]["headers"]["Authorization"] == "Bearer tk2"


def test_jira_test_connection_success():
    svc = make_jira(script={"GET": [FakeResponse(json_data={"displayName": "Bob", "emailAddress": "b@x.com"})]})
    result = svc.test_connection()
    assert result["status"] == "success"
    assert result["user"] == "Bob"
    assert result["email"] == "b@x.com"


def test_jira_test_connection_auth_failure():
    svc = make_jira(script={"GET": [FakeResponse(status_code=403)]})
    result = svc.test_connection()
    assert result["status"] == "error"
    assert "403" in result["message"]


def test_jira_test_connection_exception_no_leak():
    """Regression: exception internals must not leak into the result message."""
    svc = make_jira(script={"GET": [httpx.ConnectError("connection refused to api.atlassian.com:443")]})
    result = svc.test_connection()
    assert result["status"] == "error"
    assert "api.atlassian.com" not in result["message"]


def test_jira_get_projects_and_project():
    svc = make_jira(script={"GET": [FakeResponse(json_data=[{"key": "P1"}]), FakeResponse(json_data={"key": "P1"})]})
    assert svc.get_projects(start_at=5, max_results=10) == [{"key": "P1"}]
    params = svc.session.calls[0][2]["params"]
    assert params["startAt"] == 5
    assert params["maxResults"] == 10
    assert svc.get_project("P1") == {"key": "P1"}


def test_jira_get_projects_error_empty():
    svc = make_jira(script={"GET": [FakeResponse(status_code=500)]})
    assert svc.get_projects() == []
    assert svc.get_project("P1") is None


def test_jira_search_issues():
    svc = make_jira(script={"GET": [FakeResponse(json_data={"issues": [{"id": 1}], "total": 1})]})
    result = svc.search_issues("project = X", max_results=25)
    assert result["issues"] == [{"id": 1}]
    params = svc.session.calls[0][2]["params"]
    assert params["jql"] == "project = X"
    assert params["fields"] == "summary,status,assignee,reporter,priority,created,updated,issuetype,project"


def test_jira_search_issues_custom_fields_and_error():
    svc = make_jira(script={"GET": [FakeResponse(json_data={"issues": []}), FakeResponse(status_code=500)]})
    svc.search_issues("jql", fields=["summary", "status"])
    assert svc.session.calls[0][2]["params"]["fields"] == "summary,status"
    result = svc.search_issues("jql")
    assert result == {"issues": [], "total": 0, "startAt": 0, "maxResults": 0}


def test_jira_get_issue_and_create():
    svc = make_jira(script={"GET": [FakeResponse(json_data={"key": "P1-1"})], "POST": [FakeResponse(json_data={"id": "10001"})]})
    assert svc.get_issue("P1-1") == {"key": "P1-1"}
    result = svc.create_issue("P1", "Summary", "Bug", description="desc", priority="High", assignee="bob")
    assert result == {"id": "10001"}
    body = svc.session.calls[1][2]["json"]
    assert body["fields"]["project"] == {"key": "P1"}
    assert body["fields"]["priority"] == {"name": "High"}
    assert body["fields"]["assignee"] == {"name": "bob"}
    assert body["fields"]["issuetype"] == {"name": "Bug"}


def test_jira_create_issue_minimal_and_error():
    svc = make_jira(script={"POST": [FakeResponse(json_data={"id": "1"}), FakeResponse(status_code=500)]})
    result = svc.create_issue("P1", "S", "Task")
    assert result == {"id": "1"}
    body = svc.session.calls[0][2]["json"]
    assert "priority" not in body["fields"]
    assert "assignee" not in body["fields"]
    assert svc.create_issue("P1", "S", "Task") is None


def test_jira_update_and_assign():
    svc = make_jira(script={"PUT": [FakeResponse(json_data={}), FakeResponse(json_data={}), FakeResponse(status_code=500), FakeResponse(status_code=500)]})
    assert svc.update_issue("P1-1", {"fields": {"summary": "x"}}) is True
    assert svc.assign_issue("P1-1", "bob") is True
    assert svc.update_issue("P1-1", {}) is False
    assert svc.assign_issue("P1-1", "bob") is False


def test_jira_comments():
    svc = make_jira(script={"POST": [FakeResponse(json_data={"id": "c1"})], "GET": [FakeResponse(json_data={"comments": [{"id": "c1"}]})]})
    assert svc.add_comment("P1-1", "hello") == {"id": "c1"}
    assert svc.get_comments("P1-1") == [{"id": "c1"}]


def test_jira_comments_error():
    svc = make_jira(script={"POST": [FakeResponse(status_code=500)], "GET": [FakeResponse(status_code=500)]})
    assert svc.add_comment("P1-1", "hello") is None
    assert svc.get_comments("P1-1") == []


def test_jira_transition_success_with_comment():
    svc = make_jira(script={"GET": [FakeResponse(json_data={"transitions": [{"id": "11", "name": "In Progress"}, {"id": "21", "name": "Done"}]})], "POST": [FakeResponse(json_data={})]})
    assert svc.transition_issue("P1-1", "in progress", comment="moving") is True
    body = svc.session.calls[1][2]["json"]
    assert body["transition"]["id"] == "11"
    assert body["update"]["comment"][0]["add"]["body"]["content"][0]["content"][0]["text"] == "moving"


def test_jira_transition_not_found_and_error():
    svc = make_jira(script={"GET": [FakeResponse(json_data={"transitions": [{"id": "11", "name": "In Progress"}]}), FakeResponse(status_code=500)]})
    assert svc.transition_issue("P1-1", "Done") is False
    assert svc.transition_issue("P1-1", "Done") is False


def test_jira_get_users_and_statuses():
    svc = make_jira(script={"GET": [FakeResponse(json_data=[{"name": "bob"}]), FakeResponse(json_data=[{"name": "bob"}]), FakeResponse(json_data=[{"id": "1"}])]})
    assert svc.get_users(project_key="P1") == [{"name": "bob"}]
    assert svc.get_users() == [{"name": "bob"}]
    assert svc.get_statuses("P1") == [{"id": "1"}]


def test_jira_issue_types_both_branches():
    svc = make_jira(script={"GET": [FakeResponse(json_data=[{"name": "Bug"}]), FakeResponse(json_data=[{"name": "Bug"}]), FakeResponse(status_code=500)]})
    assert svc.get_issue_types("P1") == [{"name": "Bug"}]
    assert svc.get_issue_types() == [{"name": "Bug"}]
    assert svc.get_issue_types("P1") == []


def test_jira_worklogs():
    svc = make_jira(script={"GET": [FakeResponse(json_data={"worklogs": [{"id": "w1"}]})], "POST": [FakeResponse(json_data={"id": "w2"}), FakeResponse(json_data={"id": "w3"})]})
    assert svc.get_worklogs("P1-1") == [{"id": "w1"}]
    assert svc.add_worklog("P1-1", "2h") == {"id": "w2"}
    assert svc.add_worklog("P1-1", "1h", started="2026-08-01") == {"id": "w3"}


def test_jira_components():
    svc = make_jira(script={"GET": [FakeResponse(json_data=[{"id": "c1"}]), FakeResponse(status_code=500)]})
    assert svc.get_project_components("P1") == [{"id": "c1"}]
    assert svc.get_project_components("P1") == []


def test_jira_capabilities():
    svc = make_jira()
    caps = svc.get_capabilities()
    assert len(caps["operations"]) == 5
    assert caps["required_params"] == ["base_url"]


def test_jira_health_no_base_url():
    svc = JiraService(config={})
    result = svc.health_check()
    assert result["healthy"] is False
    assert "No base URL" in result["message"]


def test_jira_health_success():
    svc = make_jira(script={"GET": [FakeResponse(json_data={"displayName": "Bob"})]})
    result = svc.health_check()
    assert result["healthy"] is True
    assert result["user"] == "Bob"


def test_jira_health_auth_failure():
    svc = make_jira(script={"GET": [FakeResponse(status_code=401)]})
    result = svc.health_check()
    assert result["healthy"] is False
    assert "401" in result["message"]


def test_jira_health_exception_no_leak():
    svc = make_jira(script={"GET": [httpx.ConnectError("connection refused to jira.internal:8443")]})
    result = svc.health_check()
    assert result["healthy"] is False
    assert "jira.internal" not in result["message"]


async def test_jira_entity_operation_unsupported_entity():
    svc = make_jira()
    out = await svc.execute_entity_operation("get", "project", {}, None)
    assert out["success"] is False
    assert "not yet support" in out["error"]


async def test_jira_entity_operation_create():
    svc = make_jira(script={"POST": [FakeResponse(json_data={"id": "1"})]})
    out = await svc.execute_entity_operation("create", "issue", {"project": "P1", "summary": "s", "priority": "High"}, None)
    assert out["success"] is True
    assert out["result"] == {"id": "1"}


async def test_jira_entity_operation_get():
    svc = make_jira(script={"GET": [FakeResponse(json_data={"key": "P1-1"})]})
    out = await svc.execute_entity_operation("get", "issue", {"key": "P1-1"}, None)
    assert out["success"] is True
    out2 = await svc.execute_entity_operation("get", "issue", {"id": "P1-2"}, None)
    assert out2["success"] is True


async def test_jira_entity_operation_get_missing_key():
    svc = make_jira()
    out = await svc.execute_entity_operation("get", "issue", {}, None)
    assert out["success"] is False
    assert "required" in out["error"]


async def test_jira_entity_operation_list_variants():
    svc = make_jira(script={"GET": [FakeResponse(json_data={"issues": [], "total": 0}), FakeResponse(json_data={"issues": [], "total": 0}), FakeResponse(json_data={"issues": [], "total": 0})]})
    out1 = await svc.execute_entity_operation("list", "issue", {"jql": "project = P1"}, None)
    assert out1["success"] is True
    out2 = await svc.execute_entity_operation("list", "issue", {"project_key": "P2"}, None)
    assert out2["success"] is True
    assert "P2" in svc.session.calls[1][2]["params"]["jql"]
    out3 = await svc.execute_entity_operation("list", "issue", {}, None)
    assert out3["success"] is True
    assert "order by created" in svc.session.calls[2][2]["params"]["jql"]


async def test_jira_entity_operation_unknown():
    svc = make_jira()
    out = await svc.execute_entity_operation("delete", "issue", {}, None)
    assert out["success"] is False
    assert "not supported" in out["error"]


async def test_jira_execute_operation_tenant_mismatch():
    svc = make_jira()
    out = await svc.execute_operation("get_projects", {}, context={"tenant_id": "other"})
    assert out["success"] is False
    assert out["error"] == "Tenant ID mismatch"


async def test_jira_execute_operation_unknown():
    svc = make_jira()
    out = await svc.execute_operation("nope", {}, None)
    assert out["success"] is False
    assert "Unknown operation" in out["error"]


async def test_jira_execute_operation_create_issue():
    svc = make_jira(script={"POST": [FakeResponse(json_data={"id": "1"})]})
    out = await svc.execute_operation("create_issue", {"project_key": "P1", "summary": "s", "issue_type": "Task"}, context={"tenant_id": "default"})
    assert out["success"] is True
    assert out["result"] == {"id": "1"}


async def test_jira_execute_operation_create_issue_failure_envelope():
    svc = make_jira(script={"POST": [FakeResponse(status_code=500)]})
    out = await svc.execute_operation("create_issue", {"project_key": "P1", "summary": "s", "issue_type": "Task"}, context={"tenant_id": "default"})
    assert out["success"] is False
    assert out["operation"] == "create_issue"


async def test_jira_execute_operation_search():
    svc = make_jira(script={"GET": [FakeResponse(json_data={"issues": [], "total": 0})]})
    out = await svc.execute_operation("search_issues", {"jql": "x"}, context={"tenant_id": "default"})
    assert out["success"] is True


async def test_jira_execute_operation_update_and_projects_and_comment():
    svc = make_jira(script={"PUT": [FakeResponse(json_data={})], "GET": [FakeResponse(json_data=[])], "POST": [FakeResponse(json_data={"id": "c1"})]})
    out1 = await svc.execute_operation("update_issue", {"issue_key": "P1-1", "update_data": {"fields": {}}}, context={"tenant_id": "default"})
    assert out1["success"] is True
    assert out1["result"]["updated"] is True
    out2 = await svc.execute_operation("get_projects", {}, context={"tenant_id": "default"})
    assert out2["success"] is True
    out3 = await svc.execute_operation("add_comment", {"issue_key": "P1-1", "body": "hi"}, context={"tenant_id": "default"})
    assert out3["success"] is True


async def test_jira_sync_success(patch_session_local):
    svc = make_jira(script={"GET": [FakeResponse(json_data={"total": 10}), FakeResponse(json_data={"total": 4}), FakeResponse(json_data={"total": 6})]})
    db = make_db_session([None, None, None])
    patch_session_local(db)
    result = await svc.sync_to_postgres_cache("P1")
    assert result["success"] is True
    assert result["metrics_synced"] == 3
    assert "P1" in svc.session.calls[0][2]["params"]["jql"]


async def test_jira_sync_update_and_jql_quoting(patch_session_local):
    svc = make_jira(script={"GET": [FakeResponse(json_data={"total": 1}), FakeResponse(json_data={"total": 0}), FakeResponse(json_data={"total": 0})]})
    existing = SimpleNamespace(value=1, last_synced_at=None)
    db = make_db_session([existing, None, None])
    patch_session_local(db)
    result = await svc.sync_to_postgres_cache('P"ROJ')
    assert result["success"] is True
    assert existing.value == 1.0
    assert '\\"' in svc.session.calls[0][2]["params"]["jql"]


async def test_jira_sync_commit_failure_no_leak(patch_session_local):
    svc = make_jira(script={"GET": [FakeResponse(json_data={"total": 1}), FakeResponse(json_data={"total": 0}), FakeResponse(json_data={"total": 0})]})
    db = make_db_session([None, None, None])
    db.commit.side_effect = ValueError("disk full at /var/lib/postgresql")
    patch_session_local(db)
    result = await svc.sync_to_postgres_cache("P1")
    assert result["success"] is False
    assert "disk full" not in result["error"]
    assert db.rollback.called


async def test_jira_sync_session_failure_no_leak(monkeypatch):
    svc = make_jira(script={"GET": [FakeResponse(json_data={"total": 1}), FakeResponse(json_data={"total": 0}), FakeResponse(json_data={"total": 0})]})

    def boom():
        raise RuntimeError("jdbc failure")

    monkeypatch.setattr("core.database.SessionLocal", boom)
    result = await svc.sync_to_postgres_cache("P1")
    assert result["success"] is False
    assert "jdbc" not in result["error"]


async def test_jira_full_sync(patch_session_local):
    svc = make_jira(script={"GET": [FakeResponse(json_data={"total": 1}), FakeResponse(json_data={"total": 0}), FakeResponse(json_data={"total": 0})]})
    db = make_db_session([None, None, None])
    patch_session_local(db)
    result = await svc.full_sync("P1")
    assert result["success"] is True
    assert result["project_key"] == "P1"


def test_jira_singleton_unconfigured(monkeypatch):
    monkeypatch.setattr("integrations.jira_service._jira_service_singleton", None)
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    monkeypatch.delenv("JIRA_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("JIRA_CLOUD_ID", raising=False)
    monkeypatch.delenv("JIRA_BASE_URL", raising=False)
    monkeypatch.delenv("JIRA_INSTANCE_URL", raising=False)
    assert get_jira_service() is None


def test_jira_singleton_cached(monkeypatch):
    svc = make_jira()
    monkeypatch.setattr("integrations.jira_service._jira_service_singleton", svc)
    assert get_jira_service() is svc


def test_jira_singleton_configured(monkeypatch):
    monkeypatch.setattr("integrations.jira_service._jira_service_singleton", None)
    monkeypatch.setenv("JIRA_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("JIRA_CLOUD_ID", "CID")
    svc = get_jira_service()
    assert svc is not None
    assert svc.base_url == "https://api.atlassian.com/ex/jira/CID"
    monkeypatch.setattr("integrations.jira_service._jira_service_singleton", None)
