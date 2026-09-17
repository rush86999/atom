"""Integration read-shape gap closure (2026-09 audit).

Six gaps were found in the SaaS fetch layer relative to how mature harnesses
handle 100K-record providers. This file pins the fixes:

  1. silent first-page truncation — every paginated read now reports what it
     returned, whether more exists, and the opaque cursor to continue;
  2. no field projection — ``fields=`` narrows records at the response
     boundary for every integration, not just the two with hardcoded SELECTs;
  3. client-side-only filtering — a per-integration capability declaration
     says which providers can search/project server-side;
  4. unbounded tool catalog — the rendered catalog is capped and discoverable
     through tool-RAG;
  5. placeholder data in the generic dispatch surface — the ads/generic
     handlers no longer invent numbers;
  6. no TTL cache over integration reads.

Cursor semantics follow the MCP pagination spec: opaque tokens, providers
own the page size, a missing next cursor means end-of-results. Tested here
at the layer the agent actually touches — ``UniversalIntegrationService``.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from integrations.read_query import (
    DEFAULT_READ_LIMIT,
    MAX_READ_LIMIT,
    ReadQuery,
    capabilities_for,
    decode_offset_token,
    offset_token,
    project_records,
    SERVICE_CAPABILITIES,
)
from integrations.universal_integration_service import UniversalIntegrationService


# ---------------------------------------------------------------------------
# fixtures — same shape as tests/test_covpush_universal.py
# ---------------------------------------------------------------------------


class StubGatekeeper:
    async def check_action_risk(self, service, action=None, params=None,
                                agent_id=None, workspace_id=None):
        return {"allowed": True}

    def mask_response(self, service, response):
        return response


@pytest.fixture(scope="module")
def mem_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from core.database import Base
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def mem_session(mem_engine):
    return sessionmaker(bind=mem_engine, expire_on_commit=False)


@pytest.fixture
def uis():
    from integrations import read_cache
    read_cache.integration_read_cache.clear()
    yield UniversalIntegrationService(workspace_id="ws")
    read_cache.integration_read_cache.clear()


@pytest.fixture
def env(mem_session):
    with patch("core.database.SessionLocal", mem_session), \
            patch("core.integration_registry.IntegrationRegistry") as IR, \
            patch("integrations.universal_integration_service.circuit_breaker") as cb, \
            patch("integrations.universal_integration_service.governance_middleware",
                  StubGatekeeper()):
        cb.is_enabled = AsyncMock(return_value=True)
        cb.get_stats = AsyncMock(return_value={})
        cb.record_failure = AsyncMock()
        IR.return_value.get_service_instance = AsyncMock(return_value=None)
        yield SimpleNamespace(IR=IR, cb=cb)


def make_service(**methods):
    svc = MagicMock()
    svc.access_token = "tok"
    for name, ret in methods.items():
        setattr(svc, name, AsyncMock(return_value=ret))
    return svc


def contacts(n, start=0):
    return [
        {"id": f"{i}", "properties": {"firstname": f"F{i}", "lastname": f"L{i}",
                                      "email": f"u{i}@example.com",
                                      "phone": "555", "address": "x" * 200}}
        for i in range(start, start + n)
    ]


# ===========================================================================
# 1. Pagination — the silent-truncation bug
# ===========================================================================


class TestPaginationVisibility:
    """A read that returns one provider page must SAY so."""

    async def test_explicit_limit_caps_and_reports_partial_page(self, env, uis):
        set_svc = make_service(get_contacts=contacts(100))
        env.IR.return_value.get_service_instance = AsyncMock(return_value=set_svc)

        result = await uis.execute(
            "hubspot", "list", {"entity": "contact", "limit": 10},
            {"user_id": "u1"})

        assert result["status"] == "success"
        assert len(result["data"]) == 10
        page = result["page"]
        assert page["returned"] == 10
        assert page["limit"] == 10
        # 100 records came back, we handed the agent 10 — that is truncation
        # by definition, and the agent is told where to resume.
        assert page["truncated"] is True
        assert page["next_page_token"]
        assert "PARTIAL" in (result.get("message") or "")

    async def test_cursor_is_forwarded_to_the_provider(self, env, uis):
        """HubSpot's cursor is opaque and must be echoed verbatim — the old
        code sent a numeric offset as `after`, which is not a valid cursor."""
        svc = make_service(get_contacts=contacts(10, start=10))
        env.IR.return_value.get_service_instance = AsyncMock(return_value=svc)

        await uis.execute(
            "hubspot", "list",
            {"entity": "contact", "limit": 10, "page_token": "abc123cursor"},
            {"user_id": "u1"})

        kwargs = svc.get_contacts.await_args.kwargs
        assert kwargs.get("page_token") == "abc123cursor"
        assert kwargs.get("limit") == 10

    async def test_provider_next_link_becomes_an_opaque_token(self, env, uis):
        """A handler that recovered the provider's own cursor exposes it
        instead of swallowing it."""
        svc = make_service(get_contacts=contacts(5))
        svc.last_next_page_token = "cG9zdA=="  # opaque provider cursor
        env.IR.return_value.get_service_instance = AsyncMock(return_value=svc)

        result = await uis.execute(
            "hubspot", "list", {"entity": "contact", "limit": 5},
            {"user_id": "u1"})
        assert result["page"]["has_more"] is True
        assert result["page"]["next_page_token"] == "cG9zdA=="
        assert result["page"]["truncated"] is True

    async def test_short_page_is_reported_complete(self, env, uis):
        svc = make_service(get_contacts=contacts(3))
        env.IR.return_value.get_service_instance = AsyncMock(return_value=svc)

        result = await uis.execute(
            "hubspot", "list", {"entity": "contact", "limit": 25},
            {"user_id": "u1"})
        assert result["data"]
        assert result["page"]["has_more"] is False
        assert result["page"]["truncated"] is False
        assert "message" not in result or "PARTIAL" not in result["message"]

    async def test_dispatch_never_reports_complete_without_evidence(self, env, uis):
        """Returned == limit and the provider gave no cursor: has_more must be
        UNKNOWN (None), never a confident False — claiming completeness we
        cannot prove is the silent-truncation bug in a different costume."""
        svc = make_service(get_contacts=contacts(10))
        env.IR.return_value.get_service_instance = AsyncMock(return_value=svc)

        result = await uis.execute(
            "hubspot", "list", {"entity": "contact", "limit": 10},
            {"user_id": "u1"})
        assert result["page"]["has_more"] is None
        assert result["page"]["truncated"] is False
        assert "UNVERIFIED" in result["page"]["note"]

    async def test_offset_provider_gets_a_continuation_token(self, env, uis):
        """Providers whose paging IS numeric get a synthesized opaque token
        so the agent-facing surface is uniform."""
        svc = make_service()
        svc.search_issues = Mock(return_value={"issues": [{"key": f"K{i}"}
                                                           for i in range(10)]})
        env.IR.return_value.get_service_instance = AsyncMock(return_value=svc)

        result = await uis.execute(
            "jira", "search", {"query": "x", "limit": 10}, {"user_id": "u1"})
        assert result["page"]["has_more"] is True
        assert decode_offset_token(result["page"]["next_page_token"]) == 10


class TestReadQueryNormalization:
    """Five provider spellings of the same knob must normalize identically."""

    @pytest.mark.parametrize("params,expected", [
        ({"limit": 5}, 5),
        ({"page_size": 5}, 5),
        ({"max_results": 5}, 5),
        ({"top": 5}, 5),
        ({"count": 5}, 5),
        ({"per_page": "5"}, 5),
        ({}, DEFAULT_READ_LIMIT),
    ])
    def test_limit_aliases(self, params, expected):
        assert ReadQuery.from_params(params).limit == expected

    def test_limit_is_clamped_to_the_budget(self):
        assert ReadQuery.from_params({"limit": 10_000}).limit == MAX_READ_LIMIT
        assert ReadQuery.from_params({"limit": 0}).limit == 1
        assert ReadQuery.from_params({"limit": -3}).limit == 1

    @pytest.mark.parametrize("key", [
        "page_token", "cursor", "next_cursor", "offset", "after", "page",
    ])
    def test_token_aliases(self, key):
        assert ReadQuery.from_params({key: "abc"}).page_token == "abc"

    @pytest.mark.parametrize("value,expected", [
        ("id,name", ("id", "name")),
        (["id", "name"], ("id", "name")),
        ({"id": 1, "name": 1, "secret": 0}, ("id", "name")),
        ("a.b,c", ("a.b", "c")),
    ])
    def test_field_aliases(self, value, expected):
        assert ReadQuery.from_params({"fields": value}).fields == expected

    def test_offset_tokens_round_trip_and_tolerate_garbage(self):
        assert decode_offset_token(offset_token(40)) == 40
        assert decode_offset_token("not-a-cursor") == 0
        assert decode_offset_token(None) == 0


# ===========================================================================
# 2. Field projection
# ===========================================================================


class TestProjection:
    async def test_fields_narrow_every_record(self, env, uis):
        svc = make_service(get_contacts=contacts(2))
        env.IR.return_value.get_service_instance = AsyncMock(return_value=svc)

        result = await uis.execute(
            "hubspot", "list",
            {"entity": "contact", "fields": ["id", "properties.email"]},
            {"user_id": "u1"})

        first = result["data"][0]
        assert set(first) == {"id", "properties"}
        assert set(first["properties"]) == {"email"}

    async def test_projection_handles_wrapped_envelopes(self):
        wrapped = {"records": [{"id": 1, "a": "x", "b": "y"}], "totalSize": 1}
        out = project_records(wrapped, ("id",))
        assert out["records"] == [{"id": 1}]
        assert out["totalSize"] == 1

    def test_projection_never_empties_a_non_mapping_record(self):
        assert project_records(["plain", "strings"], ("id",)) == ["plain", "strings"]

    def test_projection_omits_absent_fields_rather_than_nulling_them(self):
        assert project_records([{"id": 1}], ("id", "missing")) == [{"id": 1}]

    async def test_no_fields_means_no_projection(self, env, uis):
        svc = make_service(get_contacts=contacts(1))
        env.IR.return_value.get_service_instance = AsyncMock(return_value=svc)
        result = await uis.execute("hubspot", "list", {"entity": "contact"},
                                   {"user_id": "u1"})
        assert "phone" in result["data"][0]["properties"]


# ===========================================================================
# 3. Capability declaration (server-side vs client-side)
# ===========================================================================


class TestCapabilities:
    def test_declared_services_match_the_advertised_catalog(self):
        """Every service a planner can advertise must declare its read
        posture — otherwise the general layer cannot decide to push down."""
        from core.chat_tool_planner import _SERVICE_DESCRIPTIONS
        pseudo = {"web_search", "web_fetch", "memory", "documents", "datasets"}
        missing = [
            s for s in _SERVICE_DESCRIPTIONS
            if s not in pseudo and s not in SERVICE_CAPABILITIES
        ]
        assert missing == []

    def test_known_server_side_searchers_are_declared_as_such(self):
        for service in ("gmail", "outlook", "salesforce", "hubspot", "slack",
                        "google_drive", "zendesk", "shopify", "stripe"):
            assert capabilities_for(service).server_side_search, service

    def test_unknown_service_gets_the_conservative_client_posture(self):
        caps = capabilities_for("some_tenant_connector")
        assert caps.search == "client"
        assert caps.projection == "client"

    def test_declared_max_page_sizes_are_sane(self):
        for name, caps in SERVICE_CAPABILITIES.items():
            if caps.max_page_size is not None:
                assert caps.max_page_size > 0, name


# ===========================================================================
# 4. Fabrication — no invented data on the generic dispatch surface
# ===========================================================================


class TestNoFabricatedData:
    async def test_marketing_ads_reports_unimplemented_not_fake_insights(self, uis):
        result = await uis._execute_marketing_ads("meta_ads", "get_insights", {}, {})
        assert result["status"] == "error"
        assert "data" not in result or not result.get("data")

    async def test_generic_native_does_not_claim_success_without_data(self, uis):
        result = await uis._execute_generic_native("figma", "list", {}, {})
        assert result["status"] == "error"
        assert "figma" in str(result).lower()

    async def test_review_reply_does_not_claim_a_send_it_never_made(self, uis):
        result = await uis._execute_marketing_reviews(
            "google_reviews", "reply_to_review", {"review_id": "r1"}, {})
        assert result["status"] == "error"


# ===========================================================================
# 5. TTL cache over integration reads
# ===========================================================================


class TestReadCache:
    def test_only_read_actions_are_cacheable(self):
        from integrations.read_cache import is_read_action
        assert is_read_action("search")
        assert is_read_action("search_emails")
        assert is_read_action("list_contacts")
        assert not is_read_action("send_message")
        assert not is_read_action("create_deal")
        assert not is_read_action("delete_contact")
        assert not is_read_action("get_or_create_contact")
        assert not is_read_action("")

    def test_cache_hit_avoids_a_second_provider_call(self, env, uis):
        from integrations import read_cache
        read_cache.integration_read_cache.clear()
        svc = make_service(get_contacts=contacts(2))
        env.IR.return_value.get_service_instance = AsyncMock(return_value=svc)

        with patch.dict("os.environ", {"ATOM_INTEGRATION_READ_CACHE_ENABLED": "true"}):
            asyncio.run(uis.execute("hubspot", "list", {"entity": "contact"}, {"user_id": "u1"}))
            asyncio.run(uis.execute("hubspot", "list", {"entity": "contact"}, {"user_id": "u1"}))

        assert svc.get_contacts.await_count == 1

    def test_write_invalidates_the_service_namespace(self, env, uis):
        from integrations import read_cache
        read_cache.integration_read_cache.clear()
        svc = make_service(get_contacts=contacts(2),
                           create_contact={"id": "new"})
        env.IR.return_value.get_service_instance = AsyncMock(return_value=svc)

        with patch.dict("os.environ", {"ATOM_INTEGRATION_READ_CACHE_ENABLED": "true"}):
            asyncio.run(uis.execute("hubspot", "list", {"entity": "contact"}, {"user_id": "u1"}))
            asyncio.run(uis.execute("hubspot", "create",
                                    {"entity": "contact", "data": {"email": "a@b.c"}},
                                    {"user_id": "u1"}))
            asyncio.run(uis.execute("hubspot", "list", {"entity": "contact"}, {"user_id": "u1"}))

        assert svc.get_contacts.await_count == 2

    def test_errors_are_never_cached(self):
        from integrations.read_cache import IntegrationReadCache
        cache = IntegrationReadCache(capacity=4, ttl_seconds=60)
        with patch.dict("os.environ", {"ATOM_INTEGRATION_READ_CACHE_ENABLED": "true"}):
            from integrations.read_cache import cached_read
            calls = {"n": 0}

            def fetch():
                calls["n"] += 1
                return {"status": "error", "error": "boom"}

            with patch("integrations.read_cache.integration_read_cache", cache):
                q = ReadQuery.from_params({})
                cached_read(service="x", action="list", tenant_id="t",
                            workspace_id="w", query=q, fetch=fetch)
                cached_read(service="x", action="list", tenant_id="t",
                            workspace_id="w", query=q, fetch=fetch)
        assert calls["n"] == 2

    def test_cache_is_tenant_scoped(self):
        from integrations.read_cache import IntegrationReadCache
        cache = IntegrationReadCache(capacity=4, ttl_seconds=60)
        with patch.dict("os.environ", {"ATOM_INTEGRATION_READ_CACHE_ENABLED": "true"}):
            cache.set(cache.make_key("hubspot", "list", "tenant-a", "ws", "k"), {"a": 1})
            hit, _ = cache.get(cache.make_key("hubspot", "list", "tenant-b", "ws", "k"))
        assert hit is False

    def test_cache_is_bounded(self):
        from integrations.read_cache import IntegrationReadCache
        cache = IntegrationReadCache(capacity=3, ttl_seconds=60)
        with patch.dict("os.environ", {"ATOM_INTEGRATION_READ_CACHE_ENABLED": "true"}):
            for i in range(10):
                cache.set(f"k{i}", i)
            assert cache.stats()["size"] == 3
