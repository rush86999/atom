"""Durable exact replay for the registered Shopify product-create Oracle.

Failure-first control
---------------------
The predecessor source (``0b325c5f1``) honestly reported a *succeeded* durable
claim replay as ``committed_unverified`` because ``TaskOperationRecord`` stored
only the operation identity and payload digest, not the provider resource id.
``test_known_success_replays_exact_resource_without_second_create`` is therefore
written first and fails on that limitation: the same operation + same material
must re-read the exact original resource and return a truthful
``already_applied``/verified result, with no second create.

Scope and seams
---------------
The controls join the REAL registered action, the REAL GenericAgent mutation
consumer (durable claim + Oracle stamp), the REAL product producer/material
normalizer and the REAL postcondition verifier.  Only the external Shopify
transport leaf (``ShopifyService.http``) is doubled.

The store is a real scratch SQLite ``ecommerce_stores`` row using Shopify's
supported ``EcommerceStore.tenant_id == workspace_id`` compatibility, and the
durable claim is the real ``task_operation_records`` row.  Raw SQLite readback
proves the durable receipt; no flag or monkeypatched verdict stands in for it.

Covered twins beyond the positive replay:

* a new process/session reloads the same durable identity;
* the current resource id/material is wrong;
* the current resource is missing or unreadable;
* the workspace store changed after the original success;
* the durable identity receipt is unavailable (old succeeded claim);
* changed material is refused before any readback/create;
* a lost confirmation stays uncertain and never becomes a replayed success.

Deliberately excluded: live provider calls, credential/store configuration,
guest execution, and the other three Shopify mutations.
"""
from __future__ import annotations

import asyncio
import copy
import json
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


SHOP = "scratch-replay.myshopify.com"
OTHER_SHOP = "scratch-replay-other.myshopify.com"
TOKEN = "synthetic-not-a-secret"


# ---------------------------------------------------------------------------
# Scratch world
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _oracle_on(monkeypatch):
    monkeypatch.setenv("ATOM_ORACLE_ENFORCE", "true")
    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")


def _session_factory(path):
    engine = create_engine(f"sqlite:///{path}")
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def _session():
        session = Session()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    return engine, Session, _session


def _bind_scratch(monkeypatch, path):
    engine, Session, _session = _session_factory(path)
    monkeypatch.setattr(ga, "get_db_session", _session)
    monkeypatch.setattr("core.database.SessionLocal", Session)
    return {"path": str(path), "Session": Session, "engine": engine}


@pytest.fixture
def env(tmp_path, monkeypatch):
    from core.models_registration import Base
    import core.models  # noqa: F401 - registers every model on Base

    path = tmp_path / "shopify_replay.db"
    engine, Session, _session = _session_factory(path)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(ga, "get_db_session", _session)
    monkeypatch.setattr("core.database.SessionLocal", Session)
    return {"path": str(path), "Session": Session, "engine": engine}


def _ensure_tenant(session, tenant_id):
    from core.models import Tenant

    if session.get(Tenant, tenant_id) is None:
        session.add(Tenant(
            id=tenant_id, name=f"Tenant {tenant_id}",
            subdomain=f"t-{tenant_id}-{uuid.uuid4().hex[:8]}",
            edition="personal"))


def _add_store(
    env, *, tenant_id="ws-shop", shop=SHOP, token=TOKEN,
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


class FakeShopifyTransport:
    """Doubles ONLY the Shopify HTTP leaf; service methods stay real."""

    def __init__(self, shop=SHOP):
        self.shop = shop
        self.products = {}
        self.posts = []
        self.gets = []
        self.next_id = 500
        self.post_raises_after_create = None

    @staticmethod
    def _slug(title):
        return re.sub(r"[^a-z0-9]+", "-", str(title).lower()).strip("-") or "product"

    @staticmethod
    def _response(status, url, *, method="GET", payload=None):
        return httpx.Response(
            status, json=payload or {},
            request=httpx.Request(method, url))

    def _materialize(self, product, product_id):
        item = copy.deepcopy(dict(product or {}))
        item["id"] = product_id
        item.setdefault("title", "")
        item.setdefault("body_html", "")
        item.setdefault("vendor", "")
        item.setdefault("product_type", "")
        item.setdefault("status", "active")
        item.setdefault("tags", "")
        item.setdefault("handle", self._slug(item.get("title")))
        return item

    async def post(self, integration, url, headers=None, json=None):
        self.posts.append({"url": url, "json": copy.deepcopy(json)})
        product = dict((json or {}).get("product") or {})
        product_id = str(self.next_id)
        self.next_id += 1
        created = self._materialize(product, product_id)
        self.products[product_id] = created
        if self.post_raises_after_create is not None:
            raise self.post_raises_after_create
        return self._response(
            201, url, method="POST", payload={"product": created})

    def _url_shop(self, url):
        from urllib.parse import urlparse

        return urlparse(url).hostname or ""

    async def get(self, integration, url, headers=None, params=None):
        self.gets.append(url)
        if self._url_shop(url) != self.shop:
            return self._response(404, url, payload={"errors": "not found"})
        product_id = url.rsplit("/", 1)[-1].split(".json")[0]
        product = self.products.get(product_id)
        if product is None:
            return self._response(404, url, payload={"errors": "not found"})
        return self._response(200, url, payload={"product": product})


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
    agent.id = "scratch-shopify-replay-agent"
    agent.workspace_id = "ws-shop"
    agent.tenant_id = "tenant-shop"
    agent._custom_actions = {}

    async def registry_leaf(tool_name, arguments, context=None):
        return await action_registry.execute_action(
            tool_name, arguments, context or {})

    agent.mcp = SimpleNamespace(call_tool=registry_leaf)
    return agent


def _context(operation_id, *, workspace="ws-shop", execution="exec-shop"):
    return {
        "operation_id": operation_id,
        "workspace_id": workspace,
        "tenant_id": "tenant-shop",
        "execution_id": execution,
        "user_id": "user-shop",
        "agent_id": "scratch-shopify-replay-agent",
    }


def _call(agent, arguments, context):
    return asyncio.run(agent._step_act_unaudited(
        "shopify_create_product", arguments, context=context,
        pre_approved=True))


def _claim_row(env, operation_id):
    """Read the durable claim; tolerate the predecessor schema for the
    failure-first run (no result_json column yet)."""
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
        status, payload = raw.execute(
            "select status, payload_sha256 from task_operation_records "
            "where operation_id = ?", (operation_id,)).fetchone()
        return status, payload, None


def _product_args(operation_id, **overrides):
    args = {
        "title": "Durable Replay Widget",
        "body_html": "<p>Exact authorized body</p>",
        "vendor": "Scratch Vendor",
        "product_type": "Gadget",
        "tags": ["beta", "alpha"],
        "status": "draft",
        "operation_id": operation_id,
    }
    args.update(overrides)
    return args


# ---------------------------------------------------------------------------
# Failure-first positive: same operation + same material replays exactly
# ---------------------------------------------------------------------------


def test_known_success_replays_exact_resource_without_second_create(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-replay-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _product_args(operation_id)

    first = _call(_agent(), args, context)
    assert first["success"] is True, first
    assert first["action_result"] == "applied", first
    assert first["remote_id"] == "500", first
    assert len(transport.posts) == 1
    row = _claim_row(env, operation_id)
    assert row[0] == "succeeded", row

    gets_before = len(transport.gets)
    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "the replayed operation created a second product"
    assert second["success"] is True, second
    assert len(transport.gets) > gets_before, "the replay did not re-read the resource"
    assert second["action_result"] == "already_applied", second
    assert second.get("already_applied") is True, second
    assert second.get("verified") is True, second
    assert second.get("replayed") is True, second
    assert second.get("idempotent") is True, second
    assert second["oracle_verified"] is True, second
    assert second["remote_id"] == "500", second
    assert second["provider_receipt"]["operation_id"] == operation_id, second
    assert second["provider_receipt"]["shop"] == SHOP, second
    assert second["read_receipt"]["resource_id"] == "500", second
    assert second["read_receipt"]["account_id"] == SHOP, second
    assert _claim_row(env, operation_id)[0] == "succeeded"

    receipt = json.loads(_claim_row(env, operation_id)[2])
    assert receipt["remote_id"] == "500", receipt
    assert receipt["store"] == SHOP, receipt
    assert receipt["authorized_material"]["title"] == "Durable Replay Widget", receipt


def test_restart_fresh_session_reloads_exact_durable_identity(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-restart-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _product_args(operation_id)

    first = _call(_agent(), args, context)
    assert first["success"] is True, first
    assert len(transport.posts) == 1

    # Simulate a process restart: a NEW engine/session factory bound to the same
    # durable scratch DB, a new agent instance, and a fresh context copy.  The
    # external provider keeps the same product (an external system survives our
    # process).
    env["engine"].dispose()
    reborn = _bind_scratch(monkeypatch, env["path"])

    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "a restart resend created a second product"
    assert second["success"] is True, second
    assert second["action_result"] == "already_applied", second
    assert second["oracle_verified"] is True, second
    assert second["remote_id"] == "500", second
    assert _claim_row(reborn, operation_id)[0] == "succeeded"


def test_failed_identity_receipt_is_not_rolled_back_or_resent(
        env, monkeypatch):
    """A provider success whose exact identity receipt cannot be committed is
    genuinely uncertain: it is never labelled rolled back and never re-created."""
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-receipt-fail-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _product_args(operation_id)

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


# ---------------------------------------------------------------------------
# Wrong current resource/material, changed store, unavailable receipt
# ---------------------------------------------------------------------------


def _create_then(env, monkeypatch, transport, operation_id, args, context):
    first = _call(_agent(), args, context)
    assert first["success"] is True, first
    assert len(transport.posts) == 1
    return first


def test_replay_with_wrong_current_resource_material_stays_committed_unverified(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-wrong-material-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _product_args(operation_id)
    _create_then(env, monkeypatch, transport, operation_id, args, context)

    # The exact resource id still exists, but its authoritative material was
    # changed outside this operation.  A title match is not proof.
    transport.products["500"]["body_html"] = "<p>Unapproved later edit</p>"

    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "a changed resource was recreated"
    assert second["success"] is not True, second
    assert second["status"] == "committed_unverified", second
    assert second["action_result"] == "already_applied_unverified", second
    assert second.get("oracle_verified") is False, second
    assert second.get("retryable") is False, second


def test_replay_with_missing_current_resource_stays_committed_unverified(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-missing-resource-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _product_args(operation_id)
    _create_then(env, monkeypatch, transport, operation_id, args, context)

    transport.products.pop("500")

    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "a missing resource was recreated"
    assert second["success"] is not True, second
    assert second["status"] == "committed_unverified", second
    assert second.get("requires_reconciliation") is True, second
    assert second.get("retryable") is False, second


def test_replay_after_store_changed_stays_committed_unverified(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-store-changed-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _product_args(operation_id)
    _create_then(env, monkeypatch, transport, operation_id, args, context)

    from core.models import EcommerceStore

    with env["Session"]() as session:
        store = session.query(EcommerceStore).filter(
            EcommerceStore.tenant_id == "ws-shop").one()
        store.shop_domain = OTHER_SHOP
        session.commit()

    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "a changed store was used to recreate"
    assert second["success"] is not True, second
    assert second["status"] == "committed_unverified", second
    assert second["oracle_verified"] is False, second
    assert second.get("retryable") is False, second


def test_replay_without_durable_identity_receipt_is_committed_unverified(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-no-receipt-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _product_args(operation_id)
    _create_then(env, monkeypatch, transport, operation_id, args, context)

    # The predecessor limitation: a succeeded claim whose provider identity was
    # never persisted.  Replay must stay honestly unverified, never guess from a
    # title and never resend.
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
    assert "no provider identity" in str(second.get("oracle_evidence") or ""), second


def test_replay_with_unavailable_current_readback_is_committed_unverified(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-readback-unavailable-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _product_args(operation_id)
    _create_then(env, monkeypatch, transport, operation_id, args, context)

    async def _unavailable(integration, url, headers=None, params=None):
        raise TimeoutError("provider readback timed out")

    transport.get = _unavailable

    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "unavailable readback triggered a resend"
    assert second["success"] is not True, second
    assert second["status"] == "committed_unverified", second
    assert second.get("retryable") is False, second


# ---------------------------------------------------------------------------
# Changed material and lost confirmation
# ---------------------------------------------------------------------------


def test_same_operation_changed_material_refuses_before_readback(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-changed-replay-{uuid.uuid4().hex}"
    context = _context(operation_id)
    _create_then(
        env, monkeypatch, transport, operation_id,
        _product_args(operation_id), context)
    gets_before = len(transport.gets)

    changed = _product_args(operation_id, title="Changed unapproved title")
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
    operation_id = f"op-lost-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _product_args(operation_id)

    first = _call(_agent(), args, context)
    assert first["success"] is not True, first
    assert first["status"] == "uncertain", first
    assert len(transport.posts) == 1
    assert _claim_row(env, operation_id)[0] == "uncertain_effect"

    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "a lost confirmation was resent"
    assert second["success"] is not True, second
    assert second["status"] == "uncertain", second
    assert second.get("requires_reconciliation") is True, second
    assert "do not retry" in str(second.get("message") or "").lower()
