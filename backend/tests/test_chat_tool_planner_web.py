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
    # memory is ALWAYS available (queries the workspace's own ingested data,
    # no external key); web tools stay Tavily-key-gated.
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert _available_platform_services() == ["memory"]
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    assert _available_platform_services() == ["web_search", "web_fetch", "memory"]


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
    assert block and "LIVE TOOL RESULTS (web_search" in block
    # LOCAL KNOWLEDGE (GraphRAG) may prefix the block when the workspace
    # graph holds matching entities — substring assert covers both.
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


# ── invalid-service recovery rungs ─────────────────────────────────────


@pytest.mark.asyncio
async def test_invalid_service_with_no_history_falls_back_to_memory():
    """Regression (2026-09-03): planner emitted use_tool=true with
    service=None for a file-contents question; with no history to recover
    from, the plan was dropped and the model answered "I don't have that
    file" while the document sat fully indexed in ingested memory.
    memory is always available and read-only — the correct last rung."""
    from core.chat_tool_planner import ToolPlan, plan_tool_use

    llm = MagicMock()
    llm.generate_structured_response = AsyncMock(
        return_value=ToolPlan(use_tool=True, service=None, intent="search",
                              query=None, reason="needs file contents")
    )
    with patch("core.chat_tool_planner.get_connected_services", return_value=[]):
        result = await plan_tool_use(
            "What products and prices are listed in the Consolidated Price List 2019 file?",
            [], "user-1", llm,
        )
    assert result is not None and result.service == "memory"
    assert result.intent == "search"
    assert "Consolidated Price List 2019" in (result.query or "")


@pytest.mark.asyncio
async def test_named_unavailable_service_still_dead_ends(monkeypatch):
    """A NAMED but unavailable service (web_search without a Tavily key,
    an unconnected integration) must keep the existing dead-end: the plan is
    dropped so the missing dependency stays visible — memory is not
    substituted for it."""
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    from core.chat_tool_planner import plan_tool_use

    llm = MagicMock()
    llm.generate_structured_response = AsyncMock(return_value=_plan("web_search"))
    with patch("core.chat_tool_planner.get_connected_services", return_value=[]):
        result = await plan_tool_use("check the lead website", [], "user-1", llm)
    assert result is None


@pytest.mark.asyncio
async def test_retry_repaired_to_history_service_over_memory():
    """New contract: routing repairs are LLM-owned. When the first pass
    emits a null service, the corrective pass sees the conversation (which
    mentions outlook) and re-plans outlook — preferred over the constant
    memory default because the model, not a pattern scan, made the call."""
    from core.chat_tool_planner import plan_tool_use

    llm = MagicMock()
    llm.generate_structured_response = AsyncMock(side_effect=[
        _plan(None),
        _plan("outlook"),
    ])
    history = [{"message": "search outlook for the Acme quote"}]
    with patch("core.chat_tool_planner.get_connected_services", return_value=["outlook"]):
        result = await plan_tool_use("try again", history, "user-1", llm)
    assert result is not None and result.service == "outlook"
    assert llm.generate_structured_response.await_count == 2


# ── query-anchored excerpts for single-row documents ───────────────────


def test_best_content_excerpt_centers_on_query_terms():
    from core.chat_tool_planner import _best_content_excerpt

    filler = "Exchange rates row " * 400  # head region, no query terms
    target = "Full Cost 1.6989830000000001 [=B4*B5*B6*B7] Dealer 2.65 [=D9/B10]"
    content = filler + " ||| " + target + " ||| " + ("Trailer text " * 400)
    excerpt = _best_content_excerpt(content, "full cost formula", width=600)
    assert "Full Cost" in excerpt and "[=B4*B5*B6*B7]" in excerpt


def test_best_content_excerpt_short_content_untouched():
    from core.chat_tool_planner import _best_content_excerpt

    assert _best_content_excerpt("short", "anything") == "short"


def test_best_content_excerpt_marks_skipped_regions():
    from core.chat_tool_planner import _best_content_excerpt

    content = ("head " * 200) + ("body " * 200)
    excerpt = _best_content_excerpt(content, "body", width=300)
    assert excerpt.startswith("[…earlier content skipped…]")


@pytest.mark.asyncio
async def test_empty_integration_search_falls_back_to_memory():
    """Live 2026-09-03: a price-book question routed to
    zoho_workdrive.search, matched no filenames, and the model answered
    "I can't confirm…" while the workbook sat fully ingested. An empty live
    integration result must get a second source: the ingested workspace."""
    from core.chat_tool_planner import ToolPlan, execute_tool_plan

    plan = ToolPlan(use_tool=True, service="zoho_workdrive", intent="search",
                    query="Full Cost formula Consolidated Price List 2019",
                    reason="file contents")
    empty = AsyncMock(return_value={"status": "success", "data": None})
    hit = {
        "id": "doc-not-in-store",
        "title": "Consolidated Price List 2019.xlsx",
        "preview": "=== Sheet: MULT SCOTCH TOOLING === Full Cost 1.69 [=B4*B5*B6*B7]",
        "source": "vector",
    }
    with patch("integrations.universal_integration_service.UniversalIntegrationService.execute", empty), \
         patch("core.hybrid_search.documents_hybrid.DocumentsHybridSearch.search",
               AsyncMock(return_value={"results": [hit], "label": "hybrid"})):
        block = await execute_tool_plan(plan, "user-1", "default", {})
    assert block is not None
    assert "Ingested-workspace matches" in block
    assert "Consolidated Price List 2019" in block


def test_doc_hit_excerpt_joins_chunk_family(monkeypatch):
    """Chunked documents ({doc_id}::c{i} rows) must be excerpted as one
    document — joined in chunk order, then query-anchored."""
    import re

    import lancedb
    import pandas as pd

    from core.chat_tool_planner import _doc_hit_excerpt
    from core.vector_upsert import _split_into_chunks

    filler = "Exchange rates row " * 300
    target = "Full Cost 1.69 [=B4*B5*B6*B7] " + "detail " * 120
    text = filler + "|||" + target + "|||" + "trailer " * 300
    chunks = _split_into_chunks(text, 500, 100)
    rows = [
        {"id": f"docX::c{i}", "text": c, "metadata": "{}"}
        for i, c in enumerate(chunks)
    ]

    class FakeArrow:
        def to_pandas(self):
            return pd.DataFrame(rows)

    class FakeTable:
        def to_arrow(self):
            return FakeArrow()

    class FakeDB:
        def open_table(self, name):
            return FakeTable()

    monkeypatch.setattr(lancedb, "connect", lambda path: FakeDB())
    out = _doc_hit_excerpt("docX", "full cost formula", "short fallback")
    excerpt, ingested_on = out
    assert "fallback" != excerpt and len(excerpt) > 300
    assert "Full Cost" in excerpt
    # every joined chunk id sorts in document order (c2 before c10)
    ids = [r["id"] for r in rows]
    assert re.findall(r"::c(\d+)$", "|".join(ids)) is not None
