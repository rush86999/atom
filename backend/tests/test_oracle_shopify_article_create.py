"""Registered Shopify article-create Oracle vertical — controlled end-to-end.

Failure-first control
---------------------
The predecessor ``shopify_create_article`` handler returned the provider's raw
response and never re-read the created article.  A transport 201 is not proof
that the authorized title/body/author/tags/published material exists in the
authorized blog on the current store, and the real Generic consumer therefore
reports the unverified mutation as uncertain.  The exact-create control is
written first; all scope/material/readback/replay negatives are twins of the
product and blog verticals.

Scope and seams
---------------
The controls join the REAL registered action, the REAL GenericAgent mutation
consumer (durable claim + Oracle stamp), the REAL ShopifyService methods and the
REAL shared postcondition verifier.  Only the external provider HTTP leaf
(``ShopifyService.http``) is doubled.

The store is a real scratch SQLite ``ecommerce_stores`` row using Shopify's
supported ``EcommerceStore.tenant_id == workspace_id`` compatibility, and the
durable claim is the real ``task_operation_records`` row.  Raw SQLite readback
proves the durable receipt; no flag or monkeypatched verdict stands in.

Official provider contract (Shopify Admin REST 2026-07):

* article resource, create and by-id read:
  https://shopify.dev/docs/api/admin-rest/2026-07/resources/article

Deliberately excluded: live provider calls, credentials/store configuration,
guest execution, blog create, fulfillment and the other Shopify mutations.
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


SHOP = "scratch-article.myshopify.com"
OTHER_SHOP = "scratch-article-other.myshopify.com"
TOKEN = "synthetic-not-a-secret"
BLOG_ID = "blog-700"


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

    path = tmp_path / "shopify_article.db"
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
    env, *, tenant_id="ws-article", shop=SHOP, token=TOKEN,
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
        self.articles = {}
        self.posts = []
        self.gets = []
        self.next_id = 900
        self.create_response = None
        self.read_override = None
        self.post_raises_after_create = None
        self.after_post = None
        self.enforce_shop = True

    @staticmethod
    def _slug(title):
        return re.sub(r"[^a-z0-9]+", "-", str(title).lower()).strip("-") or "article"

    @staticmethod
    def _response(status, url, *, method="GET", payload=None):
        return httpx.Response(
            status, json=payload or {},
            request=httpx.Request(method, url))

    def _materialize(self, blog_id, article, article_id):
        item = copy.deepcopy(dict(article or {}))
        item["id"] = article_id
        item["blog_id"] = blog_id
        item.setdefault("title", "")
        item.setdefault("body_html", "")
        item.setdefault("author", "")
        item.setdefault("tags", "")
        # Official Article REST readbacks expose published_at, not the
        # request-only published boolean.  A requested draft is an observed
        # null timestamp; a requested publication is a real past timestamp.
        requested_published = bool(item.pop("published", True))
        item["published_at"] = (
            "2020-01-01T00:00:00Z" if requested_published else None)
        item.setdefault("handle", self._slug(item.get("title")))
        return item

    async def post(self, integration, url, headers=None, json=None):
        self.posts.append({"url": url, "json": copy.deepcopy(json)})
        match = re.search(r"/blogs/([^/]+)/articles\.json", url)
        blog_id = match.group(1) if match else ""
        article = dict((json or {}).get("article") or {})
        article_id = str(self.next_id)
        self.next_id += 1
        created = self._materialize(blog_id, article, article_id)
        self.articles[article_id] = created
        if self.after_post is not None:
            self.after_post()
        if self.post_raises_after_create is not None:
            raise self.post_raises_after_create
        if callable(self.create_response):
            return self.create_response(created)
        return self._response(
            201, url, method="POST", payload={"article": created})

    def _url_shop(self, url):
        from urllib.parse import urlparse

        return urlparse(url).hostname or ""

    async def get(self, integration, url, headers=None, params=None):
        self.gets.append(url)
        if self.enforce_shop and self._url_shop(url) != self.shop:
            return self._response(404, url, payload={"errors": "not found"})
        match = re.search(
            r"/blogs/([^/]+)/articles/([^/.]+)\.json", url)
        if not match:
            return self._response(404, url, payload={"errors": "not found"})
        blog_id, article_id = match.group(1), match.group(2)
        if callable(self.read_override):
            result = self.read_override(
                blog_id, article_id, self.articles.get(article_id))
            if isinstance(result, Exception):
                raise result
            if result is None:
                return self._response(
                    404, url, payload={"errors": "not found"})
            return self._response(200, url, payload={"article": result})
        article = self.articles.get(article_id)
        if article is None or str(article.get("blog_id")) != blog_id:
            return self._response(404, url, payload={"errors": "not found"})
        return self._response(200, url, payload={"article": article})


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
    agent.id = "scratch-shopify-article-agent"
    agent.workspace_id = "ws-article"
    agent.tenant_id = "tenant-article"
    agent._custom_actions = {}

    async def registry_leaf(tool_name, arguments, context=None):
        return await action_registry.execute_action(
            tool_name, arguments, context or {})

    agent.mcp = SimpleNamespace(call_tool=registry_leaf)
    return agent


def _context(operation_id, *, workspace="ws-article", execution="exec-article"):
    return {
        "operation_id": operation_id,
        "workspace_id": workspace,
        "tenant_id": "tenant-article",
        "execution_id": execution,
        "user_id": "user-article",
        "agent_id": "scratch-shopify-article-agent",
    }


def _call(agent, arguments, context):
    return asyncio.run(agent._step_act_unaudited(
        "shopify_create_article", arguments, context=context,
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


def _article_args(operation_id, **overrides):
    args = {
        "blog_id": BLOG_ID,
        "title": "Scratch Authorized Article",
        "body_html": "<p>Exact authorized article body</p>",
        "author": "Scratch Author",
        "tags": "alpha, beta",
        "published": True,
        "operation_id": operation_id,
    }
    args.update(overrides)
    return args


# ---------------------------------------------------------------------------
# Exact positive / pre-effect negatives
# ---------------------------------------------------------------------------


def test_exact_article_create_is_independently_verified(env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-article-positive-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _article_args(operation_id), _context(operation_id))

    assert result["success"] is True, result
    assert result["action_result"] == "applied", result
    assert result["oracle_verified"] is True, result
    assert result["remote_id"] == "900", result
    assert result["provider_receipt"]["operation_id"] == operation_id, result
    assert result["provider_receipt"]["shop"] == SHOP, result
    assert result["read_receipt"]["resource_id"] == "900", result
    assert result["read_receipt"]["account_id"] == SHOP, result
    fields = result["read_receipt"]["fields"]
    assert fields["blog_id"] == BLOG_ID, fields
    assert fields["title"] == "Scratch Authorized Article", fields
    assert fields["body_html"] == (
        "<p>Exact authorized article body</p>"), fields
    assert fields["author"] == "Scratch Author", fields
    assert fields["tags"] == ["alpha", "beta"], fields
    assert fields["published"] is True, fields
    assert len(transport.posts) == 1
    assert len(transport.gets) == 2  # producer readback + oracle readback
    assert f"/blogs/{BLOG_ID}/articles.json" in transport.posts[0]["url"]
    posted = transport.posts[0]["json"]["article"]
    assert posted["title"] == "Scratch Authorized Article", posted
    assert posted["body_html"] == (
        "<p>Exact authorized article body</p>"), posted
    assert posted["author"] == "Scratch Author", posted
    assert posted["tags"] == "alpha, beta", posted
    assert posted["published"] is True, posted
    assert _claim_row(env, operation_id)[0] == "succeeded"


def test_missing_store_refuses_before_transport(env, monkeypatch):
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-article-missing-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _article_args(operation_id), _context(operation_id))

    assert result["success"] is False, result
    assert result["action_result"] == "proven_not_applied", result
    assert result["status"] == "failed_before_effect", result
    assert transport.posts == []
    assert _claim_row(env, operation_id)[0] == "failed_before_effect"


def test_foreign_store_refuses_before_transport(env, monkeypatch):
    _add_store(env, tenant_id="ws-other", shop=OTHER_SHOP)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-article-foreign-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _article_args(operation_id), _context(operation_id))

    assert result["success"] is False, result
    assert result["action_result"] == "proven_not_applied", result
    assert transport.posts == []


def test_moved_store_metadata_refuses_before_transport(env, monkeypatch):
    _add_store(env, metadata={"workspace_id": "ws-other"})
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-article-moved-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _article_args(operation_id), _context(operation_id))

    assert result["success"] is False, result
    assert result["action_result"] == "proven_not_applied", result
    assert transport.posts == []


def test_inactive_store_refuses_before_transport(env, monkeypatch):
    _add_store(env, active=False)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-article-inactive-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _article_args(operation_id), _context(operation_id))

    assert result["success"] is False, result
    assert result["action_result"] == "proven_not_applied", result
    assert transport.posts == []


def test_ambiguous_store_refuses_before_transport(env, monkeypatch):
    _add_store(env)
    _add_store(env, shop=OTHER_SHOP)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-article-ambiguous-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _article_args(operation_id), _context(operation_id))

    assert result["success"] is False, result
    assert result["action_result"] == "proven_not_applied", result
    assert result["status"] == "failed_before_effect", result
    assert transport.posts == []


@pytest.mark.parametrize("selector", ["shop", "access_token", "tenant_id"])
def test_body_store_selector_refuses_before_transport(
        env, monkeypatch, selector):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-article-selector-{uuid.uuid4().hex}"
    args = _article_args(operation_id)
    args[selector] = "attacker-selected"

    result = _call(_agent(), args, _context(operation_id))

    assert result["success"] is False, result
    assert result["error_kind"] == "store_override_refused", result
    assert result["status"] == "failed_before_effect", result
    assert transport.posts == []


@pytest.mark.parametrize("field", ["blog_id", "title"])
def test_missing_required_target_refuses_before_transport(
        env, monkeypatch, field):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-article-required-{uuid.uuid4().hex}"
    args = _article_args(operation_id, **{field: "   "})

    result = _call(_agent(), args, _context(operation_id))

    assert result["success"] is False, result
    assert result["error_kind"] == "invalid_request", result
    assert transport.posts == []


# ---------------------------------------------------------------------------
# Wrong id / every authorized field / absent or contradictory readback
# ---------------------------------------------------------------------------


def test_same_title_with_different_returned_id_is_not_success(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    transport.read_override = lambda bid, aid, article: {
        **copy.deepcopy(article), "id": "999"}
    _install_transport(monkeypatch, transport)
    operation_id = f"op-article-wrong-id-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _article_args(operation_id), _context(operation_id))

    assert result["success"] is not True, result
    assert result["oracle_verified"] is False, result
    assert "remote_id" in result["verification"]["mismatches"], result
    assert result["remote_id"] == "900", result
    assert len(transport.posts) == 1
    assert _claim_row(env, operation_id)[0] == "uncertain_effect"


@pytest.mark.parametrize("field,value", [
    ("blog_id", "blog-other"),
    ("title", "Unapproved Article"),
    ("body_html", "<p>Unapproved body</p>"),
    ("author", "Unapproved Author"),
    ("tags", "gamma"),
    ("published", False),
])
def test_every_authorized_field_must_match_readback(
        env, monkeypatch, field, value):
    _add_store(env)
    transport = FakeShopifyTransport()
    transport.read_override = lambda bid, aid, article, f=field, v=value: {
        **copy.deepcopy(article), f: v}
    _install_transport(monkeypatch, transport)
    operation_id = f"op-article-field-{field}-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _article_args(operation_id), _context(operation_id))

    assert len(transport.posts) == 1, result
    assert result["success"] is not True, result
    assert result["oracle_verified"] is False, result
    assert field in result["verification"]["mismatches"], result
    assert _claim_row(env, operation_id)[0] == "uncertain_effect"


def test_unavailable_published_at_proof_is_explicitly_unverified(
        env, monkeypatch):
    """A provider that omits the official publication field is unverified."""
    _add_store(env)
    transport = FakeShopifyTransport()

    def _omit_published_at(bid, aid, article):
        item = copy.deepcopy(article)
        item.pop("published_at", None)
        return item

    transport.read_override = _omit_published_at
    _install_transport(monkeypatch, transport)
    operation_id = f"op-article-published-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _article_args(operation_id), _context(operation_id))

    assert len(transport.posts) == 1, result
    assert result["success"] is not True, result
    assert result["oracle_verified"] is False, result
    assert "published" in result["verification"]["mismatches"], result


def test_absent_readback_is_uncertain_not_success(env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    transport.read_override = lambda bid, aid, article: None
    _install_transport(monkeypatch, transport)
    operation_id = f"op-article-absent-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _article_args(operation_id), _context(operation_id))

    assert result["success"] is not True, result
    assert result["status"] == "uncertain", result
    assert result["oracle_verified"] is False, result
    assert "readback" in result["verification"]["missing_fields"], result
    assert len(transport.posts) == 1


def test_unidentifiable_effect_is_uncertain_and_not_recreated(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    transport.create_response = lambda article: httpx.Response(
        201, json={"article": {"title": article["title"]}},
        request=httpx.Request(
            "POST",
            f"https://{SHOP}/admin/api/2026-07/blogs/{BLOG_ID}/articles.json"))
    _install_transport(monkeypatch, transport)
    operation_id = f"op-article-no-id-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _article_args(operation_id)

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
    operation_id = f"op-article-replay-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _article_args(operation_id)
    _create_then(env, monkeypatch, transport, operation_id, args, context)

    gets_before = len(transport.gets)
    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "the replay created a second article"
    assert second["success"] is True, second
    assert second["action_result"] == "already_applied", second
    assert second.get("replayed") is True, second
    assert second["oracle_verified"] is True, second
    assert second["remote_id"] == "900", second
    assert len(transport.gets) > gets_before, "the replay did not re-read"
    with sqlite3.connect(env["path"]) as raw:
        receipt = raw.execute(
            "select result_json from task_operation_records "
            "where operation_id = ?", (operation_id,)).fetchone()[0]
    assert '"remote_id": "900"' in receipt, receipt
    assert '"authorized_material"' in receipt, receipt


def test_restart_fresh_session_reloads_exact_durable_identity(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-article-restart-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _article_args(operation_id)
    _create_then(env, monkeypatch, transport, operation_id, args, context)

    env["engine"].dispose()
    reborn = _bind_scratch(monkeypatch, env["path"])
    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "a restart resend created a second article"
    assert second["success"] is True, second
    assert second["action_result"] == "already_applied", second
    assert second["oracle_verified"] is True, second
    assert second["remote_id"] == "900", second
    assert _claim_row(reborn, operation_id)[0] == "succeeded"


@pytest.mark.parametrize("field,value", [
    ("title", "Changed after create"),
    ("body_html", "<p>Changed body</p>"),
    ("author", "Changed Author"),
    ("tags", "changed"),
    ("published", False),
    ("blog_id", "blog-other"),
])
def test_replay_with_changed_current_material_stays_committed_unverified(
        env, monkeypatch, field, value):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-article-replay-{field}-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _article_args(operation_id)
    _create_then(env, monkeypatch, transport, operation_id, args, context)

    transport.articles["900"][field] = value
    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "a changed article was recreated"
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
    operation_id = f"op-article-missing-resource-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _article_args(operation_id)
    _create_then(env, monkeypatch, transport, operation_id, args, context)

    transport.articles.pop("900")
    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "a missing article was recreated"
    assert second["success"] is not True, second
    assert second["status"] == "committed_unverified", second
    assert second["requires_reconciliation"] is True, second
    assert second["retryable"] is False, second


def test_replay_after_store_changed_stays_committed_unverified(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-article-store-changed-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _article_args(operation_id)
    _create_then(env, monkeypatch, transport, operation_id, args, context)

    from core.models import EcommerceStore

    with env["Session"]() as session:
        store = session.query(EcommerceStore).filter(
            EcommerceStore.tenant_id == "ws-article").one()
        store.shop_domain = OTHER_SHOP
        session.commit()

    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "a changed store recreated the article"
    assert second["success"] is not True, second
    assert second["status"] == "committed_unverified", second
    assert second["oracle_verified"] is False, second


def test_replay_without_durable_identity_receipt_is_committed_unverified(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-article-no-receipt-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _article_args(operation_id)
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
    operation_id = f"op-article-readback-unavailable-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _article_args(operation_id)
    _create_then(env, monkeypatch, transport, operation_id, args, context)

    async def _unavailable(integration, url, headers=None, params=None):
        raise TimeoutError("provider readback timed out")

    transport.get = _unavailable
    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "unavailable readback triggered a resend"
    assert second["success"] is not True, second
    assert second["status"] == "committed_unverified", second
    assert second["retryable"] is False, second


def test_same_operation_changed_material_refuses_before_readback(
        env, monkeypatch):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-article-changed-replay-{uuid.uuid4().hex}"
    context = _context(operation_id)
    _create_then(
        env, monkeypatch, transport, operation_id,
        _article_args(operation_id), context)
    gets_before = len(transport.gets)

    changed = _article_args(operation_id, title="Changed unapproved article")
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
    operation_id = f"op-article-lost-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _article_args(operation_id)

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
    genuinely uncertain: it is never labelled rolled back and never re-created."""
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-article-receipt-fail-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _article_args(operation_id)

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
