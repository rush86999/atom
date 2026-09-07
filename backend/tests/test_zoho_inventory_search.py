# -*- coding: utf-8 -*-
"""Live-search fix for Zoho Inventory (2026-09-03).

Root cause (evidence: logs/uvicorn_8001_restart.log ~line 79002 +
agent_reasoning_steps rows 286/295/296): the chat tool planner planned
zoho_inventory.search, but UniversalIntegrationService._execute_finance
handled only list_items — the search action matched no branch, returned
success-without-data, and every "is it in stock?" answer was really the
ingested-file memory search. Live case: WG-350DSAV sat in stock in Zoho
while the agent told the user "no live stock records".

Covers, fully mocked (zero network, zero real DB):
- ZohoInventoryService.search_items: query building (search_text,
  organization_id, per_page, page) against the datacenter-correct host,
  pagination + limit, slim item projection, fail-closed empties
  (no token / no org / HTTP error / empty query).
- _datacenter_suffix: env override parsing (incl. multi-label TLDs) and
  the canonical-'zoho'-row fallback (callback stamps api_domain there
  only).
- _resolve_organization: config short-circuit, live lookup + process
  cache.
- execute_operation dispatch for search/search_items.
- _INTENT_ACTIONS mapping (planner intent -> real action names).
- UniversalIntegrationService._execute_finance routing of
  zoho_inventory.search_items.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

import integrations.zoho_inventory_service as zis
from integrations.zoho_inventory_service import (
    ZohoInventoryService,
    _ORG_CACHE,
)
from core.chat_tool_planner import _INTENT_ACTIONS


def _svc(config=None):
    return ZohoInventoryService(tenant_id="t1", config=config or {})


def _resp(status=200, payload=None):
    return httpx.Response(status, json=payload if payload is not None else {},
                          request=httpx.Request("GET", "http://x"))


@pytest.fixture(autouse=True)
def _clean_caches(monkeypatch):
    monkeypatch.delenv("ZOHO_ORG_ID", raising=False)
    monkeypatch.delenv("ZOHO_INVENTORY_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("ZOHO_API_DOMAIN", raising=False)
    monkeypatch.delenv("ZOHO_INVENTORY_API_DOMAIN", raising=False)
    _ORG_CACHE.clear()
    yield
    _ORG_CACHE.clear()


class TestSearchItems:
    async def test_builds_live_query_on_datacenter_host(self):
        svc = _svc({"access_token": "tok"})
        svc._inventory_base = AsyncMock(return_value="https://www.zohoapis.ca/inventory/v1")
        svc._resolve_organization = AsyncMock(return_value="org123")
        svc.client.get = AsyncMock(return_value=_resp(200, {
            "items": [{"item_id": "i1", "name": "WG-350DSAV", "sku": "wg-350dsav",
                       "stock_on_hand": 1, "available_stock": 1, "rate": 14145.0}],
            "page_context": {"has_more_page": False},
        }))
        out = await svc.search_items("wg-350")
        assert [i["name"] for i in out] == ["WG-350DSAV"]
        # The FIRST attempt is the plain search_text pass on the
        # datacenter-correct host; the ladder then widens (see
        # TestMultiStrategySearch). CA DC: <api_domain>/inventory/v1 — the
        # api_domain Zoho's own OAuth response carries (www.zohoapis.ca);
        # inventory.zoho.ca has no DNS.
        first = svc.client.get.call_args_list[0]
        assert first.args[0] == "https://www.zohoapis.ca/inventory/v1/items"
        assert first.kwargs["params"]["search_text"] == "wg-350"
        assert first.kwargs["params"]["organization_id"] == "org123"
        assert first.kwargs["params"]["per_page"] == 100
        assert first.kwargs["params"]["page"] == 1
        assert first.kwargs["headers"]["Authorization"].startswith("Zoho-oauthtoken ")

    async def test_ladder_widens_to_name_contains(self):
        # search_text matches name/description tokens only — the second
        # ladder rung tries name_contains with the same value (live
        # 2026-09-04: search_text 'bandsaw' matched 42 accessory items while
        # name_contains reaches exact-name substrings).
        svc = _svc({"access_token": "tok"})
        svc._inventory_base = AsyncMock(return_value="https://inventory.zoho.com/api/v1")
        svc._resolve_organization = AsyncMock(return_value="org1")
        svc.client.get = AsyncMock(side_effect=[
            _resp(200, {"items": [{"item_id": "a", "name": "saw blade"},
                                  {"item_id": "b", "name": "saw guide"}],
                        "page_context": {"has_more_page": True}}),
            _resp(200, {"items": [{"item_id": "c", "name": "BANDSAW pro"}],
                        "page_context": {"has_more_page": False}}),
        ])
        out = await svc.search_items("saw", limit=5)
        assert [i["item_id"] for i in out][:2] == ["a", "b"]
        assert "c" in [i["item_id"] for i in out]
        assert svc.client.get.call_count >= 2
        second = svc.client.get.call_args_list[1]
        assert second.kwargs["params"]["name_contains"] == "saw"

    async def test_stops_at_limit(self):
        svc = _svc({"access_token": "tok"})
        svc._inventory_base = AsyncMock(return_value="https://inventory.zoho.com/api/v1")
        svc._resolve_organization = AsyncMock(return_value="org1")
        # Attempt 1 returns a full page; later attempts find nothing new.
        svc.client.get = AsyncMock(side_effect=[
            _resp(200, {"items": [{"item_id": str(n), "name": f"saw {n}"} for n in range(50)],
                        "page_context": {"has_more_page": True}}),
            _resp(200, {"items": [], "page_context": {"has_more_page": False}}),
        ])
        out = await svc.search_items("saw", limit=3)
        assert len(out) == 3
        assert svc.client.get.call_count <= svc._MAX_SEARCH_CALLS

    async def test_slim_projection(self):
        slim = ZohoInventoryService._slim_item({
            "item_id": "i1", "name": "Saw", "sku": "WG-350DSAV",
            "rate": 14145.0, "description": "x" * 500,
        })
        assert slim["stock_on_hand"] == 0
        assert slim["available_stock"] == 0
        assert len(slim["description"]) == 160
        assert slim["sku"] == "WG-350DSAV"
        assert "rate" in slim

    async def test_no_token_returns_empty_without_http(self):
        svc = _svc()
        svc._get_active_token = AsyncMock(return_value=None)
        svc.client.get = AsyncMock()
        assert await svc.search_items("wg-350") == []
        svc.client.get.assert_not_called()

    async def test_no_org_returns_empty(self):
        svc = _svc({"access_token": "tok"})
        svc._inventory_base = AsyncMock(return_value="https://inventory.zoho.com/api/v1")
        svc._resolve_organization = AsyncMock(return_value=None)
        svc.client.get = AsyncMock()
        assert await svc.search_items("wg-350") == []
        svc.client.get.assert_not_called()

    async def test_http_error_returns_empty(self):
        svc = _svc({"access_token": "tok", "organization_id": "org9"})
        svc._inventory_base = AsyncMock(return_value="https://inventory.zoho.com/api/v1")
        svc.client.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.search_items("wg-350") == []

    async def test_empty_query_short_circuits(self):
        svc = _svc({"access_token": "tok"})
        svc.client.get = AsyncMock()
        assert await svc.search_items("   ") == []
        svc.client.get.assert_not_called()

    async def test_config_org_short_circuits_live_lookup(self):
        svc = _svc({"access_token": "tok", "organization_id": "cfg-org"})
        svc._inventory_base = AsyncMock(return_value="https://inventory.zoho.com/api/v1")
        svc.client.get = AsyncMock(return_value=_resp(200, {
            "items": [], "page_context": {"has_more_page": False}}))
        assert await svc.search_items("saw") == []
        params = svc.client.get.call_args.kwargs["params"]
        assert params["organization_id"] == "cfg-org"


class TestMultiStrategySearch:
    """Zoho item search is word-exact (live 2026-09-04): search_text ANDs
    its tokens, 'wg350dsav' never matches the name 'WG-350DSAV', and a
    generic noun buries the model code past the limit cut. The ladder must
    recover the item from prose queries and foreign spellings."""

    async def test_multiword_query_recovers_identifier_token(self):
        # 'Linmac WG-350DSAV' ANDs to zero on Zoho; the per-token rung
        # name_contains '350DSAV' finds the stocked saw.
        svc = _svc({"access_token": "tok"})
        svc._inventory_base = AsyncMock(return_value="https://inventory.zoho.com/api/v1")
        svc._resolve_organization = AsyncMock(return_value="org1")

        async def _route(url, headers=None, params=None):
            value = params.get("name_contains") or params.get("search_text")
            if value == "350DSAV":
                return _resp(200, {"items": [
                    {"item_id": "real", "name": "WG-350DSAV",
                     "stock_on_hand": 1, "available_stock": 1},
                ], "page_context": {"has_more_page": False}})
            return _resp(200, {"items": [],
                               "page_context": {"has_more_page": False}})

        svc.client.get = AsyncMock(side_effect=_route)
        out = await svc.search_items("Linmac WG-350DSAV")
        assert [i["name"] for i in out] == ["WG-350DSAV"]
        assert out[0]["stock_on_hand"] == 1
        assert svc.client.get.call_count <= svc._MAX_SEARCH_CALLS

    async def test_hyphenless_price_book_spelling_recovers(self):
        # 'wg350dsav' (the price-book row spelling) matches nothing on
        # Zoho; the alpha-prefix-stripped variant '350dsav' is a substring
        # of 'WG-350DSAV' and the skeleton comparison then scores it exact.
        svc = _svc({"access_token": "tok"})
        svc._inventory_base = AsyncMock(return_value="https://inventory.zoho.com/api/v1")
        svc._resolve_organization = AsyncMock(return_value="org1")

        async def _route(url, headers=None, params=None):
            value = params.get("name_contains") or params.get("search_text")
            if value == "350dsav":
                return _resp(200, {"items": [
                    {"item_id": "real", "name": "WG-350DSAV",
                     "stock_on_hand": 1, "available_stock": 1},
                ], "page_context": {"has_more_page": False}})
            return _resp(200, {"items": [],
                               "page_context": {"has_more_page": False}})

        svc.client.get = AsyncMock(side_effect=_route)
        out = await svc.search_items("wg350dsav")
        assert [i["name"] for i in out] == ["WG-350DSAV"]

    async def test_exact_hit_stops_ladder_after_first_call(self):
        svc = _svc({"access_token": "tok"})
        svc._inventory_base = AsyncMock(return_value="https://inventory.zoho.com/api/v1")
        svc._resolve_organization = AsyncMock(return_value="org1")
        svc.client.get = AsyncMock(return_value=_resp(200, {
            "items": [
                {"item_id": "r", "name": "WG-350DSAV", "stock_on_hand": 1},
                {"item_id": "v1", "name": "WG-350DSAV-1", "stock_on_hand": 0},
                {"item_id": "v5", "name": "WG-350DSAV-5", "stock_on_hand": 0},
            ],
            "page_context": {"has_more_page": False},
        }))
        out = await svc.search_items("wg-350dsav")
        assert svc.client.get.call_count == 1
        assert out[0]["name"] == "WG-350DSAV"
        assert out[0]["stock_on_hand"] == 1

    async def test_ranking_puts_exact_name_match_first(self):
        # Zoho's own ordering puts the -1 variant first; the skeleton
        # comparison must rank the exact name above it.
        svc = _svc({"access_token": "tok"})
        svc._inventory_base = AsyncMock(return_value="https://inventory.zoho.com/api/v1")
        svc._resolve_organization = AsyncMock(return_value="org1")
        svc.client.get = AsyncMock(return_value=_resp(200, {
            "items": [
                {"item_id": "v1", "name": "WG-350DSAV-1", "stock_on_hand": 0},
                {"item_id": "real", "name": "WG-350DSAV", "stock_on_hand": 1},
            ],
            "page_context": {"has_more_page": False},
        }))
        out = await svc.search_items("wg-350dsav")
        assert out[0]["name"] == "WG-350DSAV"
        assert out[0]["stock_on_hand"] == 1

    async def test_ladder_caps_api_calls_on_generic_noun(self):
        # A generic term matching a huge catalog must not walk the whole
        # ladder at full depth forever: hard cap of _MAX_SEARCH_CALLS.
        svc = _svc({"access_token": "tok"})
        svc._inventory_base = AsyncMock(return_value="https://inventory.zoho.com/api/v1")
        svc._resolve_organization = AsyncMock(return_value="org1")
        svc.client.get = AsyncMock(return_value=_resp(200, {
            "items": [{"item_id": str(n), "name": f"part {n}"}
                      for n in range(100)],
            "page_context": {"has_more_page": True},
        }))
        out = await svc.search_items("bandsaw", limit=8)
        # 'bandsaw' tokenizes to a single token whose rungs duplicate the
        # two full-query attempts — the assertion is the hard ceiling, not
        # the exact count.
        assert svc.client.get.call_count <= svc._MAX_SEARCH_CALLS
        assert len(out) == 8

    async def test_first_attempt_failure_fails_fast(self):
        # Attempt 1 down = API unreachable: no ladder hammering.
        svc = _svc({"access_token": "tok"})
        svc._inventory_base = AsyncMock(return_value="https://inventory.zoho.com/api/v1")
        svc._resolve_organization = AsyncMock(return_value="org1")
        svc.client.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.search_items("wg-350dsav") == []
        assert svc.client.get.call_count == 1

    async def test_identifier_tokens_outrank_prose_in_attempt_order(self):
        # The per-token rungs must try the model code before the brand word.
        svc = _svc({"access_token": "tok"})
        svc._inventory_base = AsyncMock(return_value="https://inventory.zoho.com/api/v1")
        svc._resolve_organization = AsyncMock(return_value="org1")
        order = []

        async def _route(url, headers=None, params=None):
            value = params.get("name_contains") or params.get("search_text")
            order.append(value)
            return _resp(200, {"items": [],
                               "page_context": {"has_more_page": False}})

        svc.client.get = AsyncMock(side_effect=_route)
        await svc.search_items("Linmac WG-350DSAV")
        # attempt1 full search_text, attempt2 full name_contains, then the
        # identifier-shaped 'WG-350DSAV' token before the prose 'Linmac'.
        # 'WG' and '350DSAV' both come out of tokenization; the ladder
        # carries identifier-shaped ones first.
        assert order[2] in ("WG", "350DSAV")
        assert order.index("Linmac") > order.index("350DSAV")


class TestDatacenterSuffix:
    async def test_api_domain_drives_inventory_base(self):
        svc = _svc()
        svc._api_domain = AsyncMock(return_value="https://www.zohoapis.ca")
        assert await svc._inventory_base() == "https://www.zohoapis.ca/inventory/v1"

    async def test_no_api_domain_falls_back_to_classic_host(self):
        svc = _svc()
        svc._api_domain = AsyncMock(return_value=None)
        svc._datacenter_suffix = AsyncMock(return_value="com")
        assert await svc._inventory_base() == "https://inventory.zoho.com/api/v1"

    async def test_no_api_domain_ca_special_case(self):
        svc = _svc()
        svc._api_domain = AsyncMock(return_value=None)
        svc._datacenter_suffix = AsyncMock(return_value="ca")
        assert await svc._inventory_base() == "https://www.zohoapis.ca/inventory/v1"

    async def test_env_override_multi_label_tld(self, monkeypatch):
        monkeypatch.setenv("ZOHO_API_DOMAIN", "https://www.zohoapis.com.au")
        assert await _svc()._datacenter_suffix() == "com.au"

    async def test_canonical_zoho_row_fallback(self, monkeypatch):
        monkeypatch.delenv("ZOHO_API_DOMAIN", raising=False)
        inventory_row = SimpleNamespace(instance_url=None)
        canonical_row = SimpleNamespace(instance_url="https://www.zohoapis.ca")

        class _Q:
            def __init__(self, rows):
                self._rows = rows

            def filter(self, *a, **k):
                return self

            def first(self):
                return self._rows.pop(0) if self._rows else None

        class _DB:
            def __init__(self):
                self._rows = [inventory_row, canonical_row]

            def query(self, model):
                return _Q(self._rows)

            def close(self):
                pass

        monkeypatch.setattr("core.database.SessionLocal", lambda: _DB())
        assert await _svc()._datacenter_suffix() == "ca"

    async def test_default_com_when_nothing_known(self, monkeypatch):
        monkeypatch.delenv("ZOHO_API_DOMAIN", raising=False)

        class _Q:
            def filter(self, *a, **k):
                return self

            def first(self):
                return None

        class _DB:
            def query(self, model):
                return _Q()

            def close(self):
                pass

        monkeypatch.setattr("core.database.SessionLocal", lambda: _DB())
        assert await _svc()._datacenter_suffix() == "com"


class TestResolveOrganization:
    async def test_live_lookup_then_cached(self):
        svc = _svc()
        svc.client.get = AsyncMock(return_value=_resp(200, {
            "organizations": [{"organization_id": "700123"}]}))
        base = "https://www.zohoapis.ca/inventory/v1"
        assert await svc._resolve_organization(token="tok", base_url=base) == "700123"
        assert svc.client.get.call_args.args[0].endswith("/organizations")
        # second call: served from the process cache, no extra HTTP
        assert await svc._resolve_organization(token="tok", base_url=base) == "700123"
        assert svc.client.get.call_count == 1

    async def test_falls_back_to_legacy_orgs_path(self):
        svc = _svc()
        svc.client.get = AsyncMock(side_effect=[
            _resp(404, {"code": 5, "message": "Invalid URL Passed"}),
            _resp(200, {"organizations": [{"organization_id": "42"}]}),
        ])
        assert await svc._resolve_organization(
            token="tok", base_url="https://inventory.zoho.com/api/v1") == "42"
        assert svc.client.get.call_args.args[0].endswith("/orgganizations")


class TestDispatchAndRouting:
    async def test_execute_operation_search(self):
        svc = _svc()
        svc.search_items = AsyncMock(return_value=[{"name": "Saw"}])
        out = await svc.execute_operation("search", {"query": "saw", "limit": 3})
        assert out == {"success": True, "result": [{"name": "Saw"}]}
        svc.search_items.assert_awaited_once_with("saw", limit=3)

    async def test_capabilities_include_search_items(self):
        assert "search_items" in _svc().get_capabilities()["operations"]

    async def test_planner_intent_maps_to_search_items(self):
        assert _INTENT_ACTIONS["zoho_inventory"]["search"] == "search_items"
        assert _INTENT_ACTIONS["zoho_inventory"]["list"] == "list_items"

    async def test_execute_finance_routes_search_items(self):
        from integrations.universal_integration_service import UniversalIntegrationService

        svc = UniversalIntegrationService(workspace_id="default")
        fake_fin = SimpleNamespace(
            access_token=None,
            search_items=AsyncMock(return_value=[{"name": "WG-350DSAV"}]),
        )
        fake_registry = SimpleNamespace(
            get_service_instance=AsyncMock(return_value=fake_fin))
        out = await svc._execute_finance(
            "zoho_inventory", "search_items",
            {"query": "wg-350", "limit": 8},
            {"registry": fake_registry, "tenant_id": "t1"},
        )
        assert out == {"status": "success", "data": [{"name": "WG-350DSAV"}]}
        # user_id rides along since the per-user token fix (2026-09-03) —
        # token rows are user-keyed, agent turns resolve nothing without it.
        fake_fin.search_items.assert_awaited_once_with(
            "wg-350", limit=8, user_id=None)


def test_module_cache_isolated_per_tenant():
    _ORG_CACHE.clear()
    _ORG_CACHE["t1"] = "a"
    _ORG_CACHE["t2"] = "b"
    assert zis._ORG_CACHE["t1"] == "a"
    assert zis._ORG_CACHE["t2"] == "b"
