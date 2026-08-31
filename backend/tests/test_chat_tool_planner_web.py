"""
Tests for the platform web tools in the chat tool planner + mcp_service
web_fetch (Tavily-backed URL reading).

Regression context (Aug 30): the planner catalog only listed OAuth-connected
integrations, so for website questions it concluded "no web access exists"
and the reply model fabricated research findings ("based on the research,
WFS Ltd appears to be an end user") with zero lookups performed. These tests
pin the new behavior: web tools appear when a key is configured, the plan
gate admits them, and execution formats real results.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.chat_tool_planner import (
    ToolPlan,
    _catalog_line,
    _available_platform_services,
    execute_tool_plan,
)


@pytest.fixture(autouse=True)
def _tavily_key(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test-key")


# ── catalog + availability ──────────────────────────────────────────────


def test_platform_services_present_with_key(monkeypatch):
    assert _available_platform_services() == ["web_search", "web_fetch"]
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert _available_platform_services() == []


def test_catalog_includes_web_tools_without_oauth():
    catalog = _catalog_line([])  # no connected integrations at all
    assert "web_search:" in catalog
    assert "web_fetch:" in catalog
    assert "(none connected)" not in catalog


def test_catalog_lists_connected_and_platform():
    catalog = _catalog_line(["outlook"])
    assert catalog.index("outlook:") < catalog.index("web_search:")


# ── plan gate ───────────────────────────────────────────────────────────


def _plan(service, use_tool=True):
    return ToolPlan(
        use_tool=use_tool,
        service=service,
        intent="search",
        query="WFS Ltd website",
        reason="needs fresh data",
    )


@pytest.mark.asyncio
async def test_plan_gate_admits_platform_service():
    from core.chat_tool_planner import plan_tool_use

    llm = MagicMock()
    llm.generate_structured_response = AsyncMock(return_value=_plan("web_search"))
    with patch("core.chat_tool_planner.get_connected_services", return_value=[]):
        result = await plan_tool_use("check the lead website", [], "user-1", llm)
    assert result is not None and result.service == "web_search"


@pytest.mark.asyncio
async def test_plan_gate_rejects_platform_service_without_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    from core.chat_tool_planner import plan_tool_use

    llm = MagicMock()
    llm.generate_structured_response = AsyncMock(return_value=_plan("web_search"))
    with patch("core.chat_tool_planner.get_connected_services", return_value=[]):
        assert await plan_tool_use("check the lead website", [], "user-1", llm) is None


# ── execution legs ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_web_search_formats_results():
    payload = {
        "answer": "WFS Ltd is a welding supply store.",
        "results": [
            {"title": "WFS Ltd — About", "url": "https://wfsltd.ca/about", "content": "Supplier of welding consumables."},
        ],
    }
    with patch("integrations.mcp_service.mcp_service.web_search", new=AsyncMock(return_value=payload)):
        block = await execute_tool_plan(_plan("web_search"), "user-1")
    assert block and block.startswith("LIVE TOOL RESULTS (web_search")
    assert "welding supply store" in block
    assert "https://wfsltd.ca/about" in block


@pytest.mark.asyncio
async def test_execute_web_search_surfaces_configuration_error():
    payload = {"results": [], "answer": None, "error": "Web search is not configured."}
    with patch("integrations.mcp_service.mcp_service.web_search", new=AsyncMock(return_value=payload)):
        block = await execute_tool_plan(_plan("web_search"), "user-1")
    assert block and "unavailable" in block and "not configured" in block


@pytest.mark.asyncio
async def test_execute_web_fetch_injects_page_content():
    payload = {"url": "https://wfsltd.ca", "content": "WFS Ltd — welding fabricators supply store.", "source": "tavily_extract"}
    with patch("integrations.mcp_service.mcp_service.web_fetch", new=AsyncMock(return_value=payload)):
        block = await execute_tool_plan(_plan("web_fetch"), "user-1")
    assert block and block.startswith("LIVE TOOL RESULTS (web_fetch")
    assert "supply store" in block


@pytest.mark.asyncio
async def test_execute_web_fetch_falls_back_to_search_when_site_blocked():
    fetch_payload = {"url": "https://wfsltd.ca", "content": "", "error": "Could not fetch: 403"}
    search_payload = {
        "answer": "WFS Ltd is a supply chain solutions provider.",
        "results": [
            {"title": "WFS Ltd", "url": "https://wfsltd.ca", "content": "Industry's Supply Partner"},
        ],
    }
    with patch("integrations.mcp_service.mcp_service.web_fetch", new=AsyncMock(return_value=fetch_payload)), \
         patch("integrations.mcp_service.mcp_service.web_search", new=AsyncMock(return_value=search_payload)):
        block = await execute_tool_plan(_plan("web_fetch"), "user-1")
    assert block and "web_fetch→web_search fallback" in block
    assert "supply chain solutions provider" in block
    assert "403" in block  # the failure is reported, not hidden


@pytest.mark.asyncio
async def test_execute_web_fetch_dead_ends_when_search_also_empty():
    fetch_payload = {"url": "https://example.com", "content": "", "error": "Could not fetch"}
    search_payload = {"answer": None, "results": []}
    with patch("integrations.mcp_service.mcp_service.web_fetch", new=AsyncMock(return_value=fetch_payload)), \
         patch("integrations.mcp_service.mcp_service.web_search", new=AsyncMock(return_value=search_payload)):
        block = await execute_tool_plan(_plan("web_fetch"), "user-1")
    assert block and "page unreadable" in block


# ── web_fetch helpers ───────────────────────────────────────────────────


def test_extract_first_url_full_and_bare():
    from integrations.mcp_service import _extract_first_url

    assert _extract_first_url("check https://wfsltd.ca/about page") == "https://wfsltd.ca/about"
    assert _extract_first_url("look at wfsltd.ca please") == "https://wfsltd.ca"
    # Email addresses are NOT website references — no URL is ripped out of
    # them (use web_search for "who is this email domain" questions).
    assert _extract_first_url("email me at mark@wfsltd.ca") is None
    assert _extract_first_url("no url here") is None
    assert _extract_first_url("site wfsltd.ca.") == "https://wfsltd.ca"


def test_html_to_text_strips_scripts_and_tags():
    from integrations.mcp_service import _html_to_text

    html = "<html><head><style>x{}</style></head><body><script>evil()</script><h1>WFS Ltd</h1><p>Supply&nbsp;store &amp; dealer</p></body></html>"
    text = _html_to_text(html)
    assert "WFS Ltd" in text and "Supply store & dealer" in text
    assert "evil" not in text and "x{}" not in text and "<" not in text
