"""Registered Shopify fulfillment-create Oracle vertical — controlled end-to-end.

Failure-first control
---------------------
The predecessor ``shopify_create_fulfillment`` handler returned the raw
create response and never re-read the fulfillment.  It also had no durable
claim projection, no exact by-id readback, and no verification that the
returned fulfillment belonged to the authorized order/location/tracking or to
the server-resolved fulfillment-order line items it dispatched.  The exact
create control is written first; the real Generic consumer therefore reports
the unverified mutation honestly as uncertain until the producer/verifier path
is added.

Scope and seams
---------------
The controls join the REAL registered action, the REAL GenericAgent mutation
consumer (durable claim + Oracle stamp), the REAL ShopifyService methods and
the REAL shared postcondition verifier.  Only the external provider HTTP leaf
(``ShopifyService.http``) is doubled.

The store is a real scratch SQLite ``ecommerce_stores`` row using Shopify's
supported ``EcommerceStore.tenant_id == workspace_id`` compatibility, and the
durable claim is the real ``task_operation_records`` row.  Raw SQLite readback
proves the durable receipt; no flag or monkeypatched verdict stands in.

Official provider contract (Shopify Admin REST 2026-07):

* create fulfillment (current endpoint, NOT the retired order-scoped write):
  ``POST /admin/api/{version}/fulfillments.json``
* exact fulfillment readback:
  ``GET /admin/api/{version}/fulfillments/{fulfillment_id}.json``
* order fulfillment orders:
  ``GET /admin/api/{version}/orders/{order_id}/fulfillment_orders.json``
  https://shopify.dev/docs/api/admin-rest/2026-07/resources/fulfillment

The registry authorizes ``order_id`` plus optional ``location_id``,
``tracking_number``, ``tracking_company`` and ``notify_customer``.  It does
not authorize fulfillment-order/line-item/quantity ids; those are derived
server-side from the order's fulfillment orders and verified against the
returned fulfillment as dispatch material.

Deliberately excluded: live provider calls, credentials/store configuration,
guest execution, order writes and the other Shopify mutations.
"""
from __future__ import annotations

import asyncio
import copy
import re
import sqlite3
import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.generic_agent as ga
from core.action_registry import action_registry
from core.generic_agent import GenericAgent


SHOP = "scratch-fulfillment.myshopify.com"
OTHER_SHOP = "scratch-fulfillment-other.myshopify.com"
TOKEN = "synthetic-not-a-secret"
ORDER_ID = "order-500"
LOCATION_ID = "loc-1"


@contextmanager
def _session_factory(path):
    engine = create_engine(f"sqlite:///{path}")
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
        session.commit()
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _oracle_on(monkeypatch):
    monkeypatch.setenv("ATOM_ORACLE_ENFORCE", "true")
    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")


@pytest.fixture
def env(tmp_path, monkeypatch):
    from core.models_registration import Base
    import core.models  # noqa: F401 - registers every model on Base

    path = tmp_path / "shopify_fulfillment.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def _session():
        return _session_factory(path)

    monkeypatch.setattr(ga, "get_db_session", _session)
    monkeypatch.setattr("core.database.SessionLocal", Session)
    monkeypatch.setattr("core.database.get_db_session", _session)
    return {"path": str(path), "Session": Session, "engine": engine,
            "_session": _session}


def _bind_scratch(monkeypatch, path):
    engine = create_engine(f"sqlite:///{path}")
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def _session():
        return _session_factory(path)

    monkeypatch.setattr(ga, "get_db_session", _session)
    monkeypatch.setattr("core.database.SessionLocal", Session)
    monkeypatch.setattr("core.database.get_db_session", _session)
    return {"path": str(path), "Session": Session, "engine": engine,
            "_session": _session}


def _ensure_tenant(session, tenant_id):
    from core.models import Tenant

    if session.get(Tenant, tenant_id) is None:
        session.add(Tenant(
            id=tenant_id, name=f"Tenant {tenant_id}",
            subdomain=f"t-{tenant_id}-{uuid.uuid4().hex[:8]}",
            edition="personal"))


def _add_store(
    env, *, tenant_id="ws-fulfillment", shop=SHOP, token=TOKEN,
    active=True, metadata=None, store_id=None,
):
    from core.models import EcommerceStore

    with env["Session"]() as session:
        _ensure_tenant(session, tenant_id)
        session.add(EcommerceStore(
            id=store_id or f"store-{uuid.uuid4().hex[:8]}",
            tenant_id=tenant_id,
            platform="shopify",
            shop_domain=shop,
            access_token=token,
            is_active=active,
            metadata_json=(
                metadata if metadata is not None
                else {"workspace_id": tenant_id}),
        ))
        session.commit()


def _default_fulfillment_orders(location=LOCATION_ID):
    return [
        {
            "id": "fo-1",
            "order_id": ORDER_ID,
            "status": "open",
            "assigned_location_id": location,
            "line_items": [
                {"id": "foli-1", "line_item_id": "line-1",
                 "quantity": 2, "fulfillable_quantity": 2,
                 "remaining_quantity": 2},
            ],
        },
        {
            "id": "fo-2",
            "order_id": ORDER_ID,
            "status": "open",
            "assigned_location_id": location,
            "line_items": [
                {"id": "foli-2", "line_item_id": "line-2",
                 "quantity": 1, "fulfillable_quantity": 1,
                 "remaining_quantity": 1},
            ],
        },
    ]


class FakeShopifyTransport:
    """Doubles ONLY the Shopify HTTP leaf; service methods stay real."""

    def __init__(self, shop=SHOP):
        self.shop = shop
        self.fulfillment_orders = _default_fulfillment_orders()
        self.fulfillments = {}
        self.fulfillment_links = {}
        self.posts = []
        self.gets = []
        self.next_id = 1100
        self.create_response = None
        self.read_override = None
        self.fo_override = None
        self.fo_fulfillments_override = None
        self.post_raises_after_create = None
        self.after_post = None
        self.enforce_shop = True

    @staticmethod
    def _response(status, url, *, method="GET", payload=None):
        return httpx.Response(
            status, json=payload or {},
            request=httpx.Request(method, url))

    def _url_shop(self, url):
        from urllib.parse import urlparse

        return urlparse(url).hostname or ""

    def _materialize(self, payload):
        fulfillment_id = str(self.next_id)
        self.next_id += 1
        by_fo = payload.get("line_items_by_fulfillment_order") or []
        line_items = []
        fo_ids = []
        location_ids = set()
        for entry in by_fo:
            fo_id = str(entry.get("fulfillment_order_id") or "")
            fo_ids.append(fo_id)
            fo = next(
                (item for item in self.fulfillment_orders
                 if str(item.get("id")) == fo_id), None)
            if fo is None:
                continue
            if fo.get("assigned_location_id") is not None:
                location_ids.add(str(fo["assigned_location_id"]))
            for line in fo.get("line_items") or []:
                quantity = line.get("remaining_quantity")
                if quantity is None:
                    quantity = line.get("fulfillable_quantity")
                if quantity is None:
                    quantity = line.get("quantity")
                line_item_id = str(line.get("line_item_id") or "")
                line_items.append({
                    "id": line_item_id,
                    "line_item_id": line_item_id,
                    "quantity": quantity,
                    # Official Fulfillment line items expose the fulfilled and
                    # currently fulfillable quantity; the latter is commonly 0
                    # after completion and is not the completed quantity.
                    "fulfillable_quantity": 0,
                })
        tracking_info = payload.get("tracking_info") or {}
        fulfillment = {
            "id": fulfillment_id,
            "order_id": ORDER_ID,
            "status": "success",
            "location_id": (
                sorted(location_ids)[0] if len(location_ids) == 1 else ""),
            "line_items": line_items,
        }
        if tracking_info.get("number") is not None:
            fulfillment["tracking_number"] = tracking_info.get("number")
            fulfillment["tracking_numbers"] = [tracking_info.get("number")]
        if tracking_info.get("company") is not None:
            fulfillment["tracking_company"] = tracking_info.get("company")
        return fulfillment

    async def post(self, integration, url, headers=None, json=None):
        self.posts.append({"url": url, "json": copy.deepcopy(json)})
        fulfillment = self._materialize((json or {}).get("fulfillment") or {})
        self.fulfillments[fulfillment["id"]] = fulfillment
        for entry in ((json or {}).get("fulfillment") or {}).get(
                "line_items_by_fulfillment_order") or []:
            fo_id = str(entry.get("fulfillment_order_id") or "")
            if fo_id:
                self.fulfillment_links.setdefault(fo_id, set()).add(
                    fulfillment["id"])
        if self.after_post is not None:
            self.after_post()
        if self.post_raises_after_create is not None:
            raise self.post_raises_after_create
        if callable(self.create_response):
            return self.create_response(fulfillment)
        return self._response(
            201, url, method="POST", payload={"fulfillment": fulfillment})

    async def get(self, integration, url, headers=None, params=None):
        self.gets.append(url)
        if self.enforce_shop and self._url_shop(url) != self.shop:
            return self._response(404, url, payload={"errors": "not found"})
        # Exact read must be the documented order-scoped resource.  The old
        # overbroad global ``/fulfillments/{id}.json`` match is deliberately
        # gone so a regression to that path fails the endpoint control.
        match = re.search(
            r"/orders/([^/]+)/fulfillments/([^/.]+)\.json", url)
        if match:
            parent_order_id, fulfillment_id = match.groups()
            fulfillment = self.fulfillments.get(fulfillment_id)
            if fulfillment is not None and str(
                    fulfillment.get("order_id") or "") != parent_order_id:
                return self._response(
                    404, url, payload={"errors": "not found"})
            if callable(self.read_override):
                result = self.read_override(fulfillment_id, fulfillment)
                if isinstance(result, Exception):
                    raise result
                if result is None:
                    return self._response(
                        404, url, payload={"errors": "not found"})
                return self._response(
                    200, url, payload={"fulfillment": result})
            if fulfillment is None:
                return self._response(
                    404, url, payload={"errors": "not found"})
            return self._response(
                200, url, payload={"fulfillment": fulfillment})
        # Official FO-scoped association read.
        fo_link = re.search(
            r"/fulfillment_orders/([^/.]+)/fulfillments\.json", url)
        if fo_link:
            fo_id = fo_link.group(1)
            linked_ids = sorted(self.fulfillment_links.get(fo_id, set()))
            items = [
                copy.deepcopy(self.fulfillments[fid])
                for fid in linked_ids if fid in self.fulfillments
            ]
            if callable(self.fo_fulfillments_override):
                result = self.fo_fulfillments_override(fo_id, items)
                if isinstance(result, Exception):
                    raise result
                items = result
            return self._response(
                200, url, payload={"fulfillments": items})
        if re.search(r"/orders/[^/]+/fulfillment_orders\.json", url):
            orders = self.fulfillment_orders
            if callable(self.fo_override):
                result = self.fo_override(orders)
                if isinstance(result, Exception):
                    raise result
                orders = result
            return self._response(
                200, url, payload={"fulfillment_orders": orders})
        return self._response(404, url, payload={"errors": "not found"})


def _install_transport(monkeypatch, transport):
    from integrations import shopify_service as shopify_module

    real_service = shopify_module.ShopifyService

    def _factory(*args, **kwargs):
        service = real_service(*args, **kwargs)
        service.http = transport
        return service

    monkeypatch.setattr(shopify_module, "ShopifyService", _factory)


def _agent():
    agent = GenericAgent.__new__(GenericAgent)
    agent.id = "scratch-shopify-fulfillment-agent"
    agent.workspace_id = "ws-fulfillment"
    agent.tenant_id = "tenant-fulfillment"
    agent._custom_actions = {}

    async def registry_leaf(tool_name, arguments, context=None):
        return await action_registry.execute_action(
            tool_name, arguments, context or {})

    agent.mcp = SimpleNamespace(call_tool=registry_leaf)
    return agent


def _context(operation_id, *, workspace="ws-fulfillment",
             execution="exec-fulfillment"):
    return {
        "operation_id": operation_id,
        "workspace_id": workspace,
        "tenant_id": "tenant-fulfillment",
        "execution_id": execution,
        "user_id": "user-fulfillment",
        "agent_id": "scratch-shopify-fulfillment-agent",
    }


def _call(agent, arguments, context):
    return asyncio.run(agent._step_act_unaudited(
        "shopify_create_fulfillment", arguments, context=context,
        pre_approved=True))


def _claim_row(env, operation_id):
    with sqlite3.connect(env["path"]) as raw:
        columns = {
            row[1] for row in raw.execute(
                "pragma table_info(task_operation_records)")
        }
        if "result_json" in columns:
            return raw.execute(
                "select status, payload_sha256, result_json "
                "from task_operation_records where operation_id = ?",
                (operation_id,)).fetchone()
        return raw.execute(
            "select status, payload_sha256 from task_operation_records "
            "where operation_id = ?", (operation_id,)).fetchone()


def _fulfillment_args(operation_id, **overrides):
    args = {
        "order_id": ORDER_ID,
        "tracking_number": "TRACK-123",
        "tracking_company": "UPS",
        "notify_customer": True,
        "operation_id": operation_id,
    }
    args.update(overrides)
    return args


# ---------------------------------------------------------------------------
# Exact positive / contract and pre-effect negatives
# ---------------------------------------------------------------------------


def test_exact_fulfillment_create_is_independently_verified(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-positive-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _fulfillment_args(operation_id), _context(operation_id))

    assert result["success"] is True, result
    assert result["action_result"] == "applied", result
    assert result["oracle_verified"] is True, result
    assert result["remote_id"] == "1100", result
    assert result["provider_receipt"]["operation_id"] == operation_id, result
    assert result["provider_receipt"]["shop"] == SHOP, result
    assert result["read_receipt"]["resource_id"] == "1100", result
    assert result["read_receipt"]["account_id"] == SHOP, result
    fields = result["read_receipt"]["fields"]
    assert fields["order_id"] == ORDER_ID, fields
    assert fields["tracking_number"] == "TRACK-123", fields
    assert fields["tracking_company"] == "UPS", fields
    assert fields["location_id"] == LOCATION_ID, fields
    assert fields["status"] == "success", fields
    assert fields["fulfillment_order_ids"] == ["fo-1", "fo-2"], fields
    # The official Fulfillment resource reports completed ``quantity`` but no
    # fulfillment-order id on its line items; association comes from the
    # documented FO-scoped collection read.
    assert fields["line_items"] == [
        {"line_item_id": "line-1", "quantity": "2"},
        {"line_item_id": "line-2", "quantity": "1"},
    ], fields
    assert len(transport.posts) == 1
    posted = transport.posts[0]
    assert posted["url"].endswith("/fulfillments.json"), posted
    assert f"/orders/{ORDER_ID}/fulfillments.json" not in posted["url"], posted
    # Current contract readbacks: order-scoped fulfillment orders, the exact
    # parent-order-scoped fulfillment (producer + Oracle), and the authoritative
    # FO association collections.
    assert any(
        url.endswith(f"/orders/{ORDER_ID}/fulfillment_orders.json")
        for url in transport.gets), transport.gets
    assert sum(
        url.endswith(f"/orders/{ORDER_ID}/fulfillments/1100.json")
        for url in transport.gets) == 2, transport.gets
    assert any(
        url.endswith("/fulfillment_orders/fo-1/fulfillments.json")
        for url in transport.gets), transport.gets
    assert any(
        url.endswith("/fulfillment_orders/fo-2/fulfillments.json")
        for url in transport.gets), transport.gets
    body = posted["json"]["fulfillment"]
    assert body["line_items_by_fulfillment_order"] == [
        {"fulfillment_order_id": "fo-1"},
        {"fulfillment_order_id": "fo-2"},
    ], body
    assert body["tracking_info"] == {
        "number": "TRACK-123", "company": "UPS"}, body
    assert body["notify_customer"] is True, body
    assert _claim_row(env, operation_id)[0] == "succeeded"


def test_missing_store_refuses_before_transport(env, monkeypatch):
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-missing-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _fulfillment_args(operation_id), _context(operation_id))

    assert result["success"] is False, result
    assert result["action_result"] == "proven_not_applied", result
    assert result["status"] == "failed_before_effect", result
    assert transport.posts == []
    assert _claim_row(env, operation_id)[0] == "failed_before_effect"


def test_foreign_store_refuses_before_transport(env, monkeypatch):
    _add_store(env, tenant_id="ws-other", shop=OTHER_SHOP)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-foreign-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _fulfillment_args(operation_id), _context(operation_id))

    assert result["success"] is False, result
    assert result["action_result"] == "proven_not_applied", result
    assert transport.posts == []


def test_moved_store_metadata_refuses_before_transport(env, monkeypatch):
    _add_store(env, metadata={"workspace_id": "ws-other"})
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-moved-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _fulfillment_args(operation_id), _context(operation_id))

    assert result["success"] is False, result
    assert result["action_result"] == "proven_not_applied", result
    assert transport.posts == []


def test_inactive_store_refuses_before_transport(env, monkeypatch):
    _add_store(env, active=False)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-inactive-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _fulfillment_args(operation_id), _context(operation_id))

    assert result["success"] is False, result
    assert result["action_result"] == "proven_not_applied", result
    assert transport.posts == []


def test_ambiguous_store_refuses_before_transport(env, monkeypatch):
    _add_store(env)
    _add_store(env, shop=OTHER_SHOP)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-ambiguous-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _fulfillment_args(operation_id), _context(operation_id))

    assert result["success"] is False, result
    assert result["action_result"] == "proven_not_applied", result
    assert transport.posts == []


@pytest.mark.parametrize("selector", ["shop", "access_token", "tenant_id"])
def test_body_store_selector_refuses_before_transport(
        env, monkeypatch, selector):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-selector-{uuid.uuid4().hex}"
    args = _fulfillment_args(operation_id)
    args[selector] = "attacker-selected"

    result = _call(_agent(), args, _context(operation_id))

    assert result["success"] is False, result
    assert result["error_kind"] == "store_override_refused", result
    assert result["status"] == "failed_before_effect", result
    assert transport.posts == []


def test_missing_order_id_refuses_before_transport(env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-order-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _fulfillment_args(operation_id, order_id="   "),
        _context(operation_id))

    assert result["success"] is False, result
    assert result["error_kind"] == "invalid_request", result
    assert transport.posts == []


def test_no_fulfillable_orders_refuses_before_post(env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    transport.fulfillment_orders = [
        {**copy.deepcopy(fo), "status": "closed"}
        for fo in _default_fulfillment_orders()
    ]
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-none-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _fulfillment_args(operation_id), _context(operation_id))

    assert result["success"] is False, result
    assert result["action_result"] == "proven_not_applied", result
    assert result["status"] == "failed_before_effect", result
    assert transport.posts == []


def test_multi_location_requires_location_before_post(env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    transport.fulfillment_orders = _default_fulfillment_orders()
    transport.fulfillment_orders[1]["assigned_location_id"] = "loc-2"
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-multi-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _fulfillment_args(operation_id), _context(operation_id))

    assert result["success"] is False, result
    assert result["action_result"] == "proven_not_applied", result
    assert result["status"] == "failed_before_effect", result
    assert transport.posts == []


def test_location_filter_selects_exact_fulfillment_order(env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    transport.fulfillment_orders = _default_fulfillment_orders()
    transport.fulfillment_orders[1]["assigned_location_id"] = "loc-2"
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-location-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _fulfillment_args(operation_id, location_id="loc-2"),
        _context(operation_id))

    assert result["success"] is True, result
    assert result["oracle_verified"] is True, result
    assert result["read_receipt"]["fields"]["fulfillment_order_ids"] == [
        "fo-2"], result
    assert result["read_receipt"]["fields"]["line_items"] == [
        {"line_item_id": "line-2", "quantity": "1"},
    ], result
    assert transport.posts[0]["json"]["fulfillment"][
        "line_items_by_fulfillment_order"] == [
            {"fulfillment_order_id": "fo-2"}]


# ---------------------------------------------------------------------------
# Returned id / authorized fields / dispatch material negatives
# ---------------------------------------------------------------------------


def test_same_order_with_different_returned_id_is_not_success(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    transport.read_override = lambda fid, fulfillment: {
        **copy.deepcopy(fulfillment), "id": "999"}
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-wrong-id-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _fulfillment_args(operation_id), _context(operation_id))

    assert result["success"] is not True, result
    assert result["oracle_verified"] is False, result
    assert "remote_id" in result["verification"]["mismatches"], result
    assert result["remote_id"] == "1100", result
    assert _claim_row(env, operation_id)[0] == "uncertain_effect"


@pytest.mark.parametrize("field,value,expected_mismatch", [
    ("order_id", "order-other", "order_id"),
    ("tracking_number", "TRACK-OTHER", "tracking_number"),
    ("tracking_company", "FedEx", "tracking_company"),
    ("location_id", "loc-other", "location_id"),
])
def test_authorized_fields_must_match_readback(
        env, monkeypatch, field, value, expected_mismatch):
    _add_store(env)
    transport = FakeShopifyTransport()

    def _corrupt(fid, fulfillment, f=field, v=value):
        item = copy.deepcopy(fulfillment)
        item[f] = v
        return item

    transport.read_override = _corrupt
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-field-{field}-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _fulfillment_args(operation_id), _context(operation_id))

    assert result["success"] is not True, result
    assert result["oracle_verified"] is False, result
    assert expected_mismatch in result["verification"]["mismatches"], result


@pytest.mark.parametrize("change", [
    "fulfillment_order_id",
    "line_item_id",
    "line_item_quantity",
    "drop_line_item",
])
def test_dispatch_material_must_match_readback(env, monkeypatch, change):
    _add_store(env)
    transport = FakeShopifyTransport()

    def _corrupt(fid, fulfillment, mode=change):
        item = copy.deepcopy(fulfillment)
        if mode == "fulfillment_order_id":
            return item
        if mode == "line_item_id":
            item["line_items"][0]["id"] = "line-other"
            item["line_items"][0]["line_item_id"] = "line-other"
        elif mode == "line_item_quantity":
            item["line_items"][0]["quantity"] = 99
        else:
            item["line_items"] = item["line_items"][1:]
        return item

    transport.read_override = _corrupt
    if change == "fulfillment_order_id":
        # The official read has no FO id; the authoritative association is the
        # FO-scoped collection.  Make fo-1's collection omit this fulfillment.
        transport.fo_fulfillments_override = (
            lambda fo_id, items: [] if fo_id == "fo-1" else items)
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-plan-{change}-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _fulfillment_args(operation_id), _context(operation_id))

    assert result["success"] is not True, result
    assert result["oracle_verified"] is False, result


def test_missing_tracking_proof_is_explicitly_unverified(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()

    def _drop_tracking(fid, fulfillment):
        item = copy.deepcopy(fulfillment)
        item.pop("tracking_number", None)
        item.pop("tracking_numbers", None)
        return item

    transport.read_override = _drop_tracking
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-no-tracking-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _fulfillment_args(operation_id), _context(operation_id))

    assert result["success"] is not True, result
    assert result["oracle_verified"] is False, result
    assert "tracking_number" in result["verification"]["mismatches"], result


@pytest.mark.parametrize("status", ["pending", "open", "failure", "cancelled"])
def test_non_success_fulfillment_status_is_not_business_success(
        env, monkeypatch, status):
    _add_store(env)
    transport = FakeShopifyTransport()

    def _status(fid, fulfillment, value=status):
        item = copy.deepcopy(fulfillment)
        item["status"] = value
        return item

    transport.read_override = _status
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-status-{status}-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _fulfillment_args(operation_id), _context(operation_id))

    assert len(transport.posts) == 1, result
    assert result["success"] is not True, result
    assert result["oracle_verified"] is not True, result


def test_absent_readback_is_uncertain_not_success(env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    transport.read_override = lambda fid, fulfillment: None
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-absent-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _fulfillment_args(operation_id), _context(operation_id))

    assert result["success"] is not True, result
    assert result["status"] == "uncertain", result
    assert result["oracle_verified"] is False, result
    assert "readback" in result["verification"]["missing_fields"], result
    assert len(transport.posts) == 1


def test_unidentifiable_effect_is_uncertain_and_not_recreated(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    transport.create_response = lambda fulfillment: httpx.Response(
        201, json={"fulfillment": {"status": "success"}},
        request=httpx.Request(
            "POST", f"https://{SHOP}/admin/api/2026-07/fulfillments.json"))
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-no-id-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _fulfillment_args(operation_id)

    first = _call(_agent(), args, context)
    assert first["success"] is not True, first
    assert first["status"] == "uncertain", first
    assert first["remote_id"] == "", first
    assert len(transport.posts) == 1
    assert _claim_row(env, operation_id)[0] == "uncertain_effect"

    second = _call(_agent(), args, dict(context))
    assert second["success"] is not True, second
    assert second["status"] == "uncertain", second
    assert len(transport.posts) == 1, "an unidentifiable effect was recreated"


# ---------------------------------------------------------------------------
# Durable same-operation replay / changed current material
# ---------------------------------------------------------------------------


def _create_then(env, monkeypatch, transport, operation_id, args, context):
    first = _call(_agent(), args, context)
    assert first["success"] is True, first
    assert len(transport.posts) == 1
    return first


def test_known_success_replays_exact_resource_without_second_create(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-replay-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _fulfillment_args(operation_id)
    _create_then(env, monkeypatch, transport, operation_id, args, context)

    gets_before = len(transport.gets)
    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "the replay created a second fulfillment"
    assert second["success"] is True, second
    assert second["action_result"] == "already_applied", second
    assert second.get("replayed") is True, second
    assert second["oracle_verified"] is True, second
    assert second["remote_id"] == "1100", second
    assert len(transport.gets) > gets_before, "the replay did not re-read"
    with sqlite3.connect(env["path"]) as raw:
        receipt = raw.execute(
            "select result_json from task_operation_records "
            "where operation_id = ?", (operation_id,)).fetchone()[0]
    assert '"remote_id": "1100"' in receipt, receipt
    assert '"authorized_material"' in receipt, receipt
    assert '"dispatch_plan"' in receipt, receipt


def test_restart_fresh_session_reloads_exact_durable_identity(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-restart-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _fulfillment_args(operation_id)
    _create_then(env, monkeypatch, transport, operation_id, args, context)

    env["engine"].dispose()
    reborn = _bind_scratch(monkeypatch, env["path"])
    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "a restart resend created a fulfillment"
    assert second["success"] is True, second
    assert second["action_result"] == "already_applied", second
    assert second["oracle_verified"] is True, second
    assert second["remote_id"] == "1100", second
    assert _claim_row(reborn, operation_id)[0] == "succeeded"


@pytest.mark.parametrize("change", [
    "order_id",
    "tracking_number",
    "tracking_company",
    "location_id",
    "fulfillment_order_id",
    "line_item_quantity",
])
def test_replay_with_changed_current_material_stays_committed_unverified(
        env, monkeypatch, change):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-replay-{change}-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _fulfillment_args(operation_id)
    _create_then(env, monkeypatch, transport, operation_id, args, context)

    item = transport.fulfillments["1100"]
    if change == "fulfillment_order_id":
        transport.fulfillment_links["fo-1"] = {"999"}
    elif change == "line_item_quantity":
        item["line_items"][0]["quantity"] = 99
    elif change == "tracking_number":
        item["tracking_number"] = "TRACK-CHANGED"
        item["tracking_numbers"] = ["TRACK-CHANGED"]
    else:
        item[change] = "changed-value"

    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "a changed fulfillment was recreated"
    assert second["success"] is not True, second
    assert second["status"] == "committed_unverified", second
    assert second["action_result"] == "already_applied_unverified", second
    assert second["oracle_verified"] is False, second
    assert second["retryable"] is False, second


def test_replay_with_missing_current_resource_stays_committed_unverified(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-missing-resource-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _fulfillment_args(operation_id)
    _create_then(env, monkeypatch, transport, operation_id, args, context)

    transport.fulfillments.pop("1100")
    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "a missing fulfillment was recreated"
    assert second["success"] is not True, second
    assert second["status"] == "committed_unverified", second
    assert second["requires_reconciliation"] is True, second
    assert second["retryable"] is False, second


def test_replay_after_store_changed_stays_committed_unverified(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-store-changed-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _fulfillment_args(operation_id)
    _create_then(env, monkeypatch, transport, operation_id, args, context)

    from core.models import EcommerceStore

    with env["Session"]() as session:
        store = session.query(EcommerceStore).filter(
            EcommerceStore.tenant_id == "ws-fulfillment").one()
        store.shop_domain = OTHER_SHOP
        session.commit()

    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "a changed store recreated the effect"
    assert second["success"] is not True, second
    assert second["status"] == "committed_unverified", second
    assert second["oracle_verified"] is False, second


def test_replay_without_durable_identity_receipt_is_committed_unverified(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-no-receipt-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _fulfillment_args(operation_id)
    _create_then(env, monkeypatch, transport, operation_id, args, context)

    with sqlite3.connect(env["path"]) as raw:
        raw.execute(
            "update task_operation_records set result_json = null "
            "where operation_id = ?", (operation_id,))
        raw.commit()

    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "a receipt-less success was resent"
    assert second["success"] is not True, second
    assert second["status"] == "committed_unverified", second
    assert second["action_result"] == "already_applied_unverified", second


def test_replay_with_unavailable_readback_is_committed_unverified(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-readback-unavailable-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _fulfillment_args(operation_id)
    _create_then(env, monkeypatch, transport, operation_id, args, context)

    async def _unavailable(integration, url, headers=None, params=None):
        raise TimeoutError("provider readback timed out")

    transport.get = _unavailable
    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "unavailable readback triggered a resend"
    assert second["success"] is not True, second
    assert second["status"] == "committed_unverified", second
    assert second["retryable"] is False, second


@pytest.mark.parametrize("change", [
    {"tracking_number": "TRACK-CHANGED"},
    {"order_id": "order-other"},
    {"notify_customer": False},
])
def test_same_operation_changed_material_refuses_before_readback(
        env, monkeypatch, change):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-changed-replay-{uuid.uuid4().hex}"
    context = _context(operation_id)
    _create_then(
        env, monkeypatch, transport, operation_id,
        _fulfillment_args(operation_id), context)
    gets_before = len(transport.gets)

    changed = _fulfillment_args(operation_id, **change)
    second = _call(_agent(), changed, dict(context))

    assert len(transport.posts) == 1, "changed material reached the provider"
    assert len(transport.gets) == gets_before, "changed material was reconciled"
    assert second.get("status") == "conflict", second
    assert second["success"] is not True, second


def test_lost_confirmation_stays_uncertain_and_never_replays_as_success(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    transport.post_raises_after_create = TimeoutError("confirmation timed out")
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-lost-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _fulfillment_args(operation_id)

    first = _call(_agent(), args, context)
    assert first["success"] is not True, first
    assert first["status"] == "uncertain", first
    assert len(transport.posts) == 1
    assert _claim_row(env, operation_id)[0] == "uncertain_effect"

    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "a lost confirmation was resent"
    assert second["success"] is not True, second
    assert second["status"] == "uncertain", second
    assert second["requires_reconciliation"] is True, second
    assert "do not retry" in str(second.get("message") or "").lower()


def test_failed_identity_receipt_is_not_rolled_back_or_resent(
        env, monkeypatch):
    """A provider success whose exact identity receipt cannot be committed is
    genuinely uncertain: never labelled rolled back and never re-created."""
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-fulfillment-receipt-fail-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _fulfillment_args(operation_id)

    from core import outbound_operation_claim as claims

    real_mark_status = claims.mark_status

    def _fail_success_receipt(record_id, status, **kwargs):
        if status == claims.SUCCEEDED:
            return False
        return real_mark_status(record_id, status, **kwargs)

    monkeypatch.setattr(claims, "mark_status", _fail_success_receipt)
    first = _call(_agent(), args, context)

    assert first["success"] is not True, first
    assert first["status"] == "uncertain", first
    assert first.get("identity_receipt_persisted") is False, first
    assert first.get("retryable") is False, first
    assert "not rolled back" in str(first.get("message") or "").lower()
    assert len(transport.posts) == 1
    assert _claim_row(env, operation_id)[0] == "uncertain_effect"

    monkeypatch.setattr(claims, "mark_status", real_mark_status)
    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "a failed identity receipt was resent"
    assert second["success"] is not True, second
    assert second["status"] == "uncertain", second
    assert second.get("requires_reconciliation") is True, second
