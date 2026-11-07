"""Shopify product-create Oracle vertical — controlled end-to-end controls.

Scope and seams
---------------
These controls join the REAL registered action, the REAL GenericAgent
mutation consumer (durable claim + Oracle stamp), the REAL product producer
material/readback comparison, and the REAL postcondition verifier.  Only the
external provider transport is doubled (``ShopifyService.http``), so no HTTP
request, live store, token, credential or account is touched.

The store is a real scratch SQLite ``ecommerce_stores`` row (Shopify's
supported ``EcommerceStore.tenant_id == workspace_id`` producer compatibility)
and the durable claim is the real ``task_operation_records`` row.  Raw
``sqlite3`` readback is used where the test needs to prove the durable effect,
not a flag.

Covered negative/positive matrix:

* missing / foreign / moved / inactive store + body store-selector override
  refuse before transport;
* exact positive with exact id, current shop, and accepted material;
* same title but wrong id / wrong material / moved store authority is not
  success;
* absent and contradictory readback is uncertain, never applied;
* unidentifiable effect (no returned id) remains uncertain and is not recreated;
* same operation + same material has one effect with no resend;
* same operation + changed material is refused;
* a lost confirmation after acceptance retains operation identity and does not
  resend.

Deliberately excluded: live provider calls, credential/store configuration,
guest execution, and the other three Shopify mutations (owned follow-ons).
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
from core.assignment_executor import _action_registry_adapter
from core.generic_agent import GenericAgent


SHOP = "scratch-shop.myshopify.com"
TOKEN = "synthetic-not-a-secret"


# ---------------------------------------------------------------------------
# Scratch world
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _oracle_on(monkeypatch):
    monkeypatch.setenv("ATOM_ORACLE_ENFORCE", "true")
    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")


@pytest.fixture
def env(tmp_path, monkeypatch):
    from core.models_registration import Base
    import core.models  # noqa: F401 - registers every model on Base

    db_path = tmp_path / "shopify_oracle.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def _session():
        session = Session()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    # The Generic durable claim and the action's store lookup both read the
    # same scratch system of record; only the provider HTTP is doubled.
    monkeypatch.setattr(ga, "get_db_session", _session)
    monkeypatch.setattr("core.database.SessionLocal", Session)
    return {"path": str(db_path), "Session": Session, "engine": engine}


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
        self.create_response = None  # callable(product) -> httpx.Response
        self.read_override = None    # callable(pid, product) -> dict|None|Exception
        self.post_raises_after_create = None
        self.after_post = None
        self.enforce_shop = True

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
        if self.after_post is not None:
            self.after_post()
        if self.post_raises_after_create is not None:
            raise self.post_raises_after_create
        if callable(self.create_response):
            return self.create_response(created)
        return self._response(
            201, url, method="POST", payload={"product": created})

    def _url_shop(self, url):
        from urllib.parse import urlparse

        return urlparse(url).hostname or ""

    async def get(self, integration, url, headers=None, params=None):
        self.gets.append(url)
        if self.enforce_shop and self._url_shop(url) != self.shop:
            return self._response(404, url, payload={"errors": "not found"})
        product_id = url.rsplit("/", 1)[-1].split(".json")[0]
        if callable(self.read_override):
            result = self.read_override(
                product_id, self.products.get(product_id))
            if isinstance(result, Exception):
                raise result
            if result is None:
                return self._response(
                    404, url, payload={"errors": "not found"})
            return self._response(200, url, payload={"product": result})
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
    agent.id = "scratch-shopify-agent"
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
        "agent_id": "scratch-shopify-agent",
    }


def _call(agent, arguments, context):
    return asyncio.run(agent._step_act_unaudited(
        "shopify_create_product", arguments, context=context,
        pre_approved=True))


def _claim_row(env, operation_id):
    with sqlite3.connect(env["path"]) as raw:
        return raw.execute(
            "select status, payload_sha256 from task_operation_records "
            "where operation_id = ?", (operation_id,)).fetchone()


def _product_args(operation_id, **overrides):
    args = {
        "title": "Controlled Widget",
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
# Exact positive
# ---------------------------------------------------------------------------


def test_exact_product_create_is_independently_verified(env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-positive-{uuid.uuid4().hex}"
    args = _product_args(operation_id)

    result = _call(_agent(), args, _context(operation_id))

    assert result["success"] is True, result
    assert result["action_result"] == "applied", result
    assert result["status"] == "success", result
    assert result["oracle_verified"] is True, result
    assert result["remote_id"] == "500", result
    assert len(result["payload_sha256"]) == 64
    assert result["provider_receipt"]["operation_id"] == operation_id
    assert result["provider_receipt"]["shop"] == SHOP
    assert result["read_receipt"]["resource_id"] == "500"
    assert result["read_receipt"]["account_id"] == SHOP
    assert result["read_receipt"]["fields"]["title"] == "Controlled Widget"
    assert result["read_receipt"]["fields"]["status"] == "draft"
    assert result["read_receipt"]["fields"]["tags"] == ["alpha", "beta"]

    # Exactly one effect, and the Oracle performed its own read (the producer
    # also read back, so two fresh GETs are expected; no extra POST).
    assert len(transport.posts) == 1
    assert len(transport.gets) == 2
    posted = transport.posts[0]["json"]["product"]
    assert "operation_id" not in posted
    assert "access_token" not in posted
    assert posted["tags"] == "alpha, beta"
    assert _claim_row(env, operation_id)[0] == "succeeded"


# ---------------------------------------------------------------------------
# Store / authority negatives (all before transport)
# ---------------------------------------------------------------------------


def test_missing_store_refuses_before_transport(env, monkeypatch):
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-missing-{uuid.uuid4().hex}"

    result = _call(_agent(), _product_args(operation_id), _context(operation_id))

    assert result["success"] is False, result
    assert result["action_result"] == "proven_not_applied", result
    assert result["status"] == "failed_before_effect", result
    assert transport.posts == []
    assert _claim_row(env, operation_id)[0] == "failed_before_effect"


def test_foreign_store_refuses_before_transport(env, monkeypatch):
    _add_store(env, tenant_id="ws-other", shop="other-shop.myshopify.com")
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-foreign-{uuid.uuid4().hex}"

    result = _call(_agent(), _product_args(operation_id), _context(operation_id))

    assert result["success"] is False, result
    assert result["action_result"] == "proven_not_applied", result
    assert transport.posts == []


def test_moved_store_metadata_refuses_before_transport(env, monkeypatch):
    _add_store(env, metadata={"workspace_id": "ws-other"})
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-moved-{uuid.uuid4().hex}"

    result = _call(_agent(), _product_args(operation_id), _context(operation_id))

    assert result["success"] is False, result
    assert result["action_result"] == "proven_not_applied", result
    assert transport.posts == []


def test_inactive_store_refuses_before_transport(env, monkeypatch):
    _add_store(env, active=False)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-inactive-{uuid.uuid4().hex}"

    result = _call(_agent(), _product_args(operation_id), _context(operation_id))

    assert result["success"] is False, result
    assert result["action_result"] == "proven_not_applied", result
    assert transport.posts == []


@pytest.mark.parametrize("selector", ["shop", "access_token", "tenant_id"])
def test_body_store_selector_refuses_before_transport(
        env, monkeypatch, selector):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-selector-{uuid.uuid4().hex}"
    args = _product_args(operation_id)
    args[selector] = "attacker-selected"

    result = _call(_agent(), args, _context(operation_id))

    assert result["success"] is False, result
    assert result["error_kind"] == "store_override_refused", result
    assert result["status"] == "failed_before_effect", result
    assert transport.posts == []


# ---------------------------------------------------------------------------
# Wrong id / shop / material with the same title
# ---------------------------------------------------------------------------


def test_same_title_with_different_returned_id_is_not_success(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    transport.read_override = lambda pid, product: {
        **copy.deepcopy(product), "id": "999"}
    _install_transport(monkeypatch, transport)
    operation_id = f"op-wrong-id-{uuid.uuid4().hex}"

    result = _call(_agent(), _product_args(operation_id), _context(operation_id))

    assert result["success"] is not True, result
    assert result["oracle_verified"] is False, result
    assert "remote_id" in result["verification"]["mismatches"], result
    assert result["remote_id"] == "500", result
    assert len(transport.posts) == 1
    assert _claim_row(env, operation_id)[0] == "uncertain_effect"


def test_same_title_with_wrong_material_is_not_success(env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    transport.read_override = lambda pid, product: {
        **copy.deepcopy(product),
        "body_html": "<p>Different unapproved body</p>",
    }
    _install_transport(monkeypatch, transport)
    operation_id = f"op-wrong-material-{uuid.uuid4().hex}"

    result = _call(_agent(), _product_args(operation_id), _context(operation_id))

    assert result["success"] is not True, result
    assert result["oracle_verified"] is False, result
    assert "body_html" in result["verification"]["mismatches"], result
    assert len(transport.posts) == 1
    assert _claim_row(env, operation_id)[0] == "uncertain_effect"


def test_store_moved_before_verification_refutes_original_authority(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()

    def _move_store_after_dispatch():
        from core.models import EcommerceStore

        with env["Session"]() as session:
            _ensure_tenant(session, "ws-other")
            store = session.query(EcommerceStore).filter(
                EcommerceStore.tenant_id == "ws-shop").one()
            store.tenant_id = "ws-other"
            session.commit()

    transport.after_post = _move_store_after_dispatch
    _install_transport(monkeypatch, transport)
    operation_id = f"op-moved-after-{uuid.uuid4().hex}"

    result = _call(_agent(), _product_args(operation_id), _context(operation_id))

    assert result["success"] is not True, result
    assert result["oracle_verified"] is False, result
    assert "no current workspace store authority" in str(
        result.get("oracle_evidence") or "")
    assert len(transport.posts) == 1
    assert _claim_row(env, operation_id)[0] == "uncertain_effect"


# ---------------------------------------------------------------------------
# Absent / contradictory / unidentifiable readback
# ---------------------------------------------------------------------------


def test_absent_readback_is_uncertain_not_success(env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    transport.read_override = lambda pid, product: None
    _install_transport(monkeypatch, transport)
    operation_id = f"op-absent-{uuid.uuid4().hex}"

    result = _call(_agent(), _product_args(operation_id), _context(operation_id))

    assert result["success"] is not True, result
    assert result["status"] == "uncertain", result
    assert result["oracle_verified"] is False, result
    assert "readback" in result["verification"]["missing_fields"], result
    assert len(transport.posts) == 1
    assert _claim_row(env, operation_id)[0] == "uncertain_effect"


def test_contradictory_readback_is_uncertain_not_success(env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    transport.read_override = lambda pid, product: {
        **copy.deepcopy(product),
        "title": "Controlled Widget",
        "vendor": "Unapproved Vendor",
    }
    _install_transport(monkeypatch, transport)
    operation_id = f"op-contradictory-{uuid.uuid4().hex}"

    result = _call(_agent(), _product_args(operation_id), _context(operation_id))

    assert result["success"] is not True, result
    assert result["oracle_verified"] is False, result
    assert "vendor" in result["verification"]["mismatches"], result
    assert _claim_row(env, operation_id)[0] == "uncertain_effect"


def test_unidentifiable_effect_remains_uncertain_and_is_not_recreated(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    transport.create_response = lambda product: httpx.Response(
        201, json={"product": {"title": product["title"]}},
        request=httpx.Request(
            "POST", f"https://{SHOP}/admin/api/2026-07/products.json"))
    _install_transport(monkeypatch, transport)
    operation_id = f"op-no-id-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _product_args(operation_id)

    first = _call(_agent(), args, context)
    assert first["success"] is not True, first
    assert first["status"] == "uncertain", first
    assert first["remote_id"] == "", first
    assert len(transport.posts) == 1
    assert _claim_row(env, operation_id)[0] == "uncertain_effect"

    second = _call(_agent(), args, dict(context))
    assert second["success"] is not True, second
    assert second["status"] == "uncertain", second
    assert second.get("idempotent") is True, second
    assert len(transport.posts) == 1, "an unidentifiable effect was recreated"


# ---------------------------------------------------------------------------
# Durable operation identity: one effect / changed material / lost confirm
# ---------------------------------------------------------------------------


def test_same_operation_same_material_has_one_effect(env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-durable-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _product_args(operation_id)

    first = _call(_agent(), args, context)
    assert first["success"] is True, first
    assert len(transport.posts) == 1

    second = _call(_agent(), dict(args), dict(context))
    assert len(transport.posts) == 1, "the same operation dispatched twice"
    assert second.get("replayed") is True, second
    assert second.get("idempotent") is True, second
    assert second.get("operation_id") == operation_id, second
    assert second["success"] is True, second
    assert second["action_result"] == "already_applied", second
    assert second["remote_id"] == "500", second
    assert second["oracle_verified"] is True, second
    assert _claim_row(env, operation_id)[0] == "succeeded"


def test_same_operation_changed_material_is_refused(env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-changed-{uuid.uuid4().hex}"
    context = _context(operation_id)

    first = _call(_agent(), _product_args(operation_id), context)
    assert first["success"] is True, first
    assert len(transport.posts) == 1

    changed = _product_args(operation_id, title="Changed unapproved title")
    second = _call(_agent(), changed, dict(context))

    assert len(transport.posts) == 1, "changed material reached the provider"
    assert second.get("status") == "conflict", second
    assert second["success"] is not True, second
    assert "different material" in str(second.get("message") or "").lower()


def test_lost_confirmation_retains_identity_and_never_resends(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    transport.post_raises_after_create = TimeoutError("confirmation timed out")
    _install_transport(monkeypatch, transport)
    operation_id = f"op-timeout-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _product_args(operation_id)

    first = _call(_agent(), args, context)
    assert first["success"] is not True, first
    assert first["status"] == "uncertain", first
    assert first["operation_id"] == operation_id, first
    assert "try once more" not in str(first).lower(), first
    assert len(transport.posts) == 1
    assert _claim_row(env, operation_id)[0] == "uncertain_effect"

    second = _call(_agent(), dict(args), dict(context))
    assert len(transport.posts) == 1, "the lost confirmation was resent"
    assert second["success"] is not True, second
    assert second["status"] == "uncertain", second
    assert second.get("requires_reconciliation") is True, second
    assert "do not retry" in str(second.get("message") or "").lower()


# ---------------------------------------------------------------------------
# Frozen request binding at the assignment-adapter boundary
# ---------------------------------------------------------------------------


def test_supplied_payload_digest_mismatch_refuses_before_transport(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-digest-{uuid.uuid4().hex}"
    args = _product_args(operation_id, payload_sha256="0" * 64)

    result = asyncio.run(_action_registry_adapter(
        {"action": "shopify_create_product", "arguments": args},
        {
            "workspace_id": "ws-shop",
            "tenant_id": "tenant-shop",
            "employee_id": "user-shop",
            "run_id": "run-shop",
            "assignment_id": "assignment-shop",
            "step": {"effect": "external", "operation_id": operation_id},
        },
    ))

    assert result["status"] == "failed", result
    assert result["error_class"] == "payload_binding_mismatch", result
    assert transport.posts == []
