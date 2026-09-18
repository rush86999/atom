"""Service-layer + agent-loop coverage for the 2026-09-16 data-access audit.

The UIS-boundary contracts (read envelope, projection, honest errors, read
cache) are covered by tests/test_integration_read_gaps.py. This file pins
the SERVICE-LAYER halves those branches call into, plus the agent-loop
tool-catalog bounds:

- Outlook: search_emails_paged follows @odata.nextLink, exposes the
  continuation token, and refuses non-Graph tokens (SSRF guard).
- HubSpot: search_content accepts the token/limit/after kwargs the UIS
  passes (this exact call TypeError'd before) and surfaces the cursor.
- Slack: search_messages carries Slack's 1-based page.
- Google Calendar: get_events pushes the query down as ``q``.
- Shopify: cursor paging via page_info + server-side customer search.
- Stripe: server-side charges/search with cursor + has_more.
- GitHub/finance/dev branches: server search used when available.
- agent_tool_budget: bounded session accumulation + bounded prompt render
  (both agent loops route through these functions).
- read_cache.params_fingerprint: the hashlib import regression.
"""
import asyncio
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _graph_page(ids, next_link=None):
    page = {"value": [{"id": i, "subject": f"s-{i}"} for i in ids]}
    if next_link:
        page["@odata.nextLink"] = next_link
    return page


class TestOutlookPagedSearch:
    def test_follows_next_link_when_first_page_short(self):
        from integrations.outlook_service import OutlookService

        svc = OutlookService.__new__(OutlookService)
        calls = []

        async def fake_request(user_id, endpoint, method="GET", data=None,
                               access_token=None, full_url=False):
            calls.append(endpoint)
            if full_url:
                return _graph_page(["c", "d"])
            return _graph_page(["a", "b"],
                               "https://graph.microsoft.com/v1.0/me/messages?$skiptoken=X")

        with patch.object(svc, "_make_graph_request", side_effect=fake_request):
            result = asyncio.run(svc.search_emails_paged(
                "u", "bandsaw", max_results=4, quote=False))

        assert [e["id"] for e in result["emails"]] == ["a", "b", "c", "d"]
        assert result["pages_fetched"] == 2
        assert result["has_more"] is False
        assert result["next_page_token"] is None
        assert len(calls) == 2  # ladder attempt + one continuation

    def test_page_token_resumes_at_the_graph_url(self):
        from integrations.outlook_service import OutlookService

        svc = OutlookService.__new__(OutlookService)
        seen = []

        async def fake_request(user_id, endpoint, **kwargs):
            seen.append((endpoint, kwargs.get("full_url")))
            return _graph_page(["z"], None)

        token = "https://graph.microsoft.com/v1.0/me/messages?$skiptoken=Q"
        with patch.object(svc, "_make_graph_request", side_effect=fake_request):
            result = asyncio.run(svc.search_emails_paged(
                "u", "ignored", max_results=10, page_token=token))

        assert [e["id"] for e in result["emails"]] == ["z"]
        assert seen[0][0] == token and seen[0][1] is True

    def test_non_graph_page_token_is_rejected(self):
        from integrations.outlook_service import OutlookService

        svc = OutlookService.__new__(OutlookService)
        result = asyncio.run(svc.search_emails_paged(
            "u", "q", max_results=10, page_token="https://evil.example.com/x"))
        assert result["emails"] == []
        assert result.get("error") == "invalid page_token"

    def test_search_emails_keeps_the_plain_list_contract(self):
        from integrations.outlook_service import OutlookService

        svc = OutlookService.__new__(OutlookService)

        async def fake_request(user_id, endpoint, **kwargs):
            return _graph_page(["a"])

        with patch.object(svc, "_make_graph_request", side_effect=fake_request):
            emails = asyncio.run(svc.search_emails("u", "q", quote=False))
        assert isinstance(emails, list) and emails[0]["id"] == "a"


class TestHubspotSearchContent:
    def test_accepts_token_limit_after_properties(self):
        from integrations.hubspot_service import HubSpotService

        svc = HubSpotService.__new__(HubSpotService)
        svc.base_url = "https://api.hubapi.com"
        svc.http = MagicMock()
        response = MagicMock()
        response.json.return_value = {
            "results": [{"id": "1"}],
            "paging": {"next": {"after": 42}},
        }
        svc.http.post = AsyncMock(return_value=response)

        res = asyncio.run(svc.search_content(
            "acme", object_type="contact", token="tok", limit=10,
            after=7, properties=["email"]))

        _, args, kwargs = svc.http.post.mock_calls[0]
        assert args[1].endswith("/crm/v3/objects/contact/search")
        assert kwargs["headers"]["Authorization"] == "Bearer tok"
        assert kwargs["json"]["limit"] == 10
        assert kwargs["json"]["after"] == 7
        assert kwargs["json"]["properties"] == ["email"]
        assert res["paging"]["next"]["after"] == 42

    def test_uis_hubspot_search_returns_envelope_with_cursor(self):
        from integrations.universal_integration_service import UniversalIntegrationService

        uis = UniversalIntegrationService()
        hs = SimpleNamespace(search_content=AsyncMock(return_value={
            "results": [{"id": "1"}], "paging": {"next": {"after": 42}},
        }))
        registry = MagicMock()
        registry.get_service_instance = AsyncMock(return_value=hs)

        result = asyncio.run(uis._search_hubspot(
            "acme", None, {"registry": registry, "read_query": None}))

        # Before the fix this branch raised TypeError (token= kwarg) and then
        # returned a BARE list, dropping HubSpot's cursor.
        assert result["status"] == "success"
        assert result["data"] == [{"id": "1"}]
        assert result["_next_page_token"] == "42"


class TestSlackSearchPage:
    def test_page_param_reaches_slack(self):
        from integrations.slack_service_unified import SlackUnifiedService

        svc = SlackUnifiedService.__new__(SlackUnifiedService)
        svc.make_request = AsyncMock(return_value={
            "messages": {"matches": [], "pagination": {"page_count": 3, "page": 2}}})

        res = asyncio.run(svc.search_messages(token="t", query="q", count=20, page=2))
        kwargs = svc.make_request.call_args.kwargs
        assert kwargs["params"]["page"] == 2
        assert kwargs["params"]["count"] == 20
        assert res["messages"]["pagination"]["page_count"] == 3

    def test_uis_slack_branch_derives_next_page(self):
        import integrations.slack_service_unified as slack_mod
        from integrations.universal_integration_service import UniversalIntegrationService
        from integrations.read_query import ReadQuery

        fake = SimpleNamespace(search_messages=AsyncMock(return_value={
            "messages": {"matches": [], "pagination": {"page_count": 3, "page": 1}}}))
        uis = UniversalIntegrationService()
        read = ReadQuery.from_params({"query": "deploy", "limit": 20})
        with patch.object(slack_mod, "slack_unified_service", fake):
            result = asyncio.run(uis._search_communication(
                "slack", "deploy", {"read_query": read}))
        assert result["_next_page_token"] == "2"
        fake.search_messages.assert_awaited_once()


class TestCalendarServerSearch:
    def test_query_is_pushed_down_as_q(self):
        import integrations.google_calendar_service as cal_mod
        from integrations.universal_integration_service import UniversalIntegrationService

        fake = SimpleNamespace(get_events=AsyncMock(return_value=[{"title": "Dentist"}]))
        uis = UniversalIntegrationService()
        with patch.object(cal_mod, "google_calendar_service", fake):
            result = asyncio.run(uis._search_calendar("google_calendar", "Dentist", {}))
        fake.get_events.assert_awaited_once_with(q="Dentist")
        assert result["status"] == "success"
        assert result["data"] == [{"title": "Dentist"}]


class TestShopifyCursor:
    def _uis(self):
        from integrations.universal_integration_service import UniversalIntegrationService
        return UniversalIntegrationService()

    def test_customer_search_goes_server_side(self):
        uis = self._uis()
        with patch("integrations.universal_integration_service.ShopifyService") as SH:
            shop = SH.return_value
            shop.search_customers = AsyncMock(return_value=[{"id": 7}])
            result = asyncio.run(uis._execute_shopify(
                "search", {"entity": "customer", "query": "acme"},
                {"access_token": "t", "shop": "s", "user_id": "u"}))
        assert result["status"] == "success"
        assert result["data"] == [{"id": 7}]
        shop.search_customers.assert_awaited_once()

    def test_product_search_survives_with_cursor(self):
        uis = self._uis()

        async def fake_get(*args, **kwargs):
            meta_out = kwargs.get("meta_out")
            if meta_out is not None:
                meta_out["next_page_info"] = "cur123"
            return [{"id": 1, "title": "WG-350DSAV bandsaw"}]

        with patch("integrations.universal_integration_service.ShopifyService") as SH:
            shop = SH.return_value
            shop.get_products = AsyncMock(side_effect=fake_get)
            result = asyncio.run(uis._execute_shopify(
                "search", {"entity": "product", "query": "wg-350dsav"},
                {"access_token": "t", "shop": "s", "user_id": "u"}))
        assert result["status"] == "success"
        assert result["_next_page_token"] == "cur123"
        assert result["data"][0]["title"].startswith("WG-350DSAV")


class TestStripeServerSearch:
    def test_search_charges_used_when_present(self):
        from integrations.universal_integration_service import UniversalIntegrationService

        uis = UniversalIntegrationService()
        adapter = SimpleNamespace(
            access_token="x",
            search_charges=AsyncMock(return_value={
                "data": [{"id": "ch_1"}], "has_more": True,
                "next_page_token": "ch_1"}),
            get_charges=AsyncMock(return_value=[]),
        )
        registry = MagicMock()
        registry.get_service_instance = AsyncMock(return_value=adapter)
        context = {"registry": registry, "read_query": None}

        result = asyncio.run(uis._search_finance("stripe", "acme@x.com", context))
        adapter.search_charges.assert_awaited_once()
        adapter.get_charges.assert_not_awaited()
        assert result["status"] == "success"
        assert result["_next_page_token"] == "ch_1"

    def test_falls_back_to_recent_list_on_search_failure(self):
        from integrations.universal_integration_service import UniversalIntegrationService

        uis = UniversalIntegrationService()
        adapter = SimpleNamespace(
            access_token="x",
            search_charges=AsyncMock(side_effect=RuntimeError("search api down")),
            get_charges=AsyncMock(return_value=[
                {"id": "ch_9", "description": "acme invoice"},
                {"id": "ch_8", "description": "other"},
            ]),
        )
        registry = MagicMock()
        registry.get_service_instance = AsyncMock(return_value=adapter)

        result = asyncio.run(uis._search_finance("stripe", "acme", {"registry": registry}))
        adapter.get_charges.assert_awaited_once()
        assert result[0]["id"] == "ch_9"


class TestGithubServerSearch:
    def test_server_search_preferred_over_list_filter(self):
        import integrations.github_service as gh_mod
        from integrations.universal_integration_service import UniversalIntegrationService

        uis = UniversalIntegrationService()
        fake = SimpleNamespace(
            search_repositories=MagicMock(return_value=[{"name": "acme-api", "id": 1}]),
            get_user_repositories=MagicMock(return_value=[]),
        )
        with patch.object(gh_mod, "GitHubService", return_value=fake):
            result = asyncio.run(uis._search_dev("github", "acme api", {}))
        fake.search_repositories.assert_called_once()
        assert result["data"][0]["name"] == "acme-api"


class TestAgentToolBudget:
    def test_trim_session_tools_fifo_and_dedupe(self):
        from core.agent_tool_budget import trim_session_tools

        tools = [{"name": f"t{i}"} for i in range(50)]
        tools.append({"name": "t10"})  # dupe — dropped regardless of cap
        trimmed = trim_session_tools(tools)
        assert len(trimmed) == 40
        names = [t["name"] for t in trimmed]
        assert "t49" in names and "t0" not in names  # newest survive

    def test_render_cap_and_hidden_count(self, monkeypatch):
        from core.agent_tool_budget import render_tool_catalog

        monkeypatch.setenv("ATOM_AGENT_TOOL_PROMPT_CAP", "3")
        tools = [{"name": f"t{i}", "description": "d"} for i in range(5)]
        rendered, hidden = render_tool_catalog(tools)
        parsed = json.loads(rendered)
        assert len(parsed) == 3
        assert hidden == 2
        assert parsed[0]["name"] == "t0"

    def test_render_under_cap_is_unchanged(self):
        from core.agent_tool_budget import render_tool_catalog

        rendered, hidden = render_tool_catalog([{"name": "a", "description": "x"}])
        assert hidden == 0
        assert json.loads(rendered)[0]["name"] == "a"

    def test_session_cap_env_override(self, monkeypatch):
        from core.agent_tool_budget import trim_session_tools

        monkeypatch.setenv("ATOM_AGENT_SESSION_TOOLS_CAP", "2")
        trimmed = trim_session_tools([{"name": "a"}, {"name": "b"}, {"name": "c"}])
        assert [t["name"] for t in trimmed] == ["b", "c"]


class TestReadCacheFingerprint:
    def test_fingerprint_import_regression(self):
        # read_cache.params_fingerprint referenced hashlib without importing
        # it — every cached read raised NameError before the fix.
        from integrations.read_cache import params_fingerprint

        a = params_fingerprint({"entity": "contact"})
        b = params_fingerprint({"entity": "deal"})
        assert a != b
        assert params_fingerprint({"entity": "contact"}) == a
