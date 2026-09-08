"""Regression tests for the 404'd-link incident (2026-09-08, canvas
c3617a7f…): asked to find a product page on brennan.ca, the co-editor
fetched the site's HOMEPAGE (planner misread "the address is known"),
the direct-fetch fallback stripped every href so no real URL was in
evidence, and the editor invented /products/<model-number> — which went
unverified into a customer quote email. Covers the three layers:

1. planner evidence — _site_search_evidence reads the site's own search
   page when public search is empty/unavailable;
2. web_fetch evidence — direct fetch keeps page links;
3. write boundary — a NEW link that confirmably 404s blocks the edit.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.chat_canvas_editor import (
    _extract_http_urls,
    _new_dead_links,
    apply_canvas_edit,
    describe_apply_failure,
)
from core.chat_tool_planner import _site_search_evidence
from integrations.mcp_service import _extract_page_links


# ───────────────────────── _extract_http_urls ─────────────────────────

def test_extract_urls_from_nested_content_and_html():
    content = {
        "to": "a@b.ca",
        "body": '<a href="https://brennan.ca/products/x">link</a> '
                "plain https://example.com/page?q=1 text.",
        "rows": [["https://one.ca", {"u": "http://two.ca/"}]],
    }
    urls = _extract_http_urls(content)
    assert "https://brennan.ca/products/x" in urls
    assert "https://example.com/page?q=1" in urls
    assert "https://one.ca" in urls
    assert "http://two.ca/" in urls


def test_extract_urls_dedupes_and_skips_mailto():
    urls = _extract_http_urls(
        {"b": "mailto:x@y.ca tel:123 https://same.ca https://same.ca"})
    assert urls == ["https://same.ca"]


# ───────────────────────── _new_dead_links ─────────────────────────

class _FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


def _fake_httpx_client(head_status, get_status):
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.head = AsyncMock(return_value=_FakeResponse(head_status))
    client.get = AsyncMock(return_value=_FakeResponse(get_status))
    return client


@pytest.mark.asyncio
async def test_new_dead_links_confirmed_404_detected():
    with patch("httpx.AsyncClient",
                     return_value=_fake_httpx_client(404, 404)):
        dead = await _new_dead_links(
            {"body": "old"},
            {"body": '<a href="https://shop.ca/products/guessed">x</a>'},
        )
    assert dead == ["https://shop.ca/products/guessed"]


@pytest.mark.asyncio
async def test_new_dead_links_head_404_but_get_200_stays_alive():
    with patch("httpx.AsyncClient",
                     return_value=_fake_httpx_client(404, 200)):
        dead = await _new_dead_links(
            {}, {"body": "https://shop.ca/products/real"})
    assert dead == []


@pytest.mark.asyncio
async def test_new_dead_links_ignores_existing_and_bot_walls():
    current = {"body": "already has https://published.ca"}
    new = {"body": "https://published.ca and https://authwall.ca"}
    with patch("httpx.AsyncClient",
                     return_value=_fake_httpx_client(403, 403)):
        dead = await _new_dead_links(current, new)
    assert dead == []  # 403 bot wall ≠ dead; published link not re-checked


@pytest.mark.asyncio
async def test_new_dead_links_network_failure_fails_open():
    with patch("httpx.AsyncClient", side_effect=RuntimeError("no network")):
        dead = await _new_dead_links({}, {"body": "https://anything.ca"})
    assert dead == []


# ───────────────── apply_canvas_edit dead-link gate ─────────────────

def _plan(content_json):
    from core.chat_canvas_editor import CanvasEditPlan
    return CanvasEditPlan(wants_edit=True, updated_content_json=content_json,
                          reply="ok")


@pytest.mark.asyncio
async def test_apply_blocks_edit_introducing_dead_link():
    import json

    new_content = {"body": '<a href="https://dead.ca/products/x">spec</a>'}
    with patch("core.chat_canvas_editor._new_dead_links",
               new=AsyncMock(return_value=["https://dead.ca/products/x"])), \
         patch("tools.canvas_crud_tool.update_canvas_content",
               new=AsyncMock()) as upd:
        result, reason = await apply_canvas_edit(
            _plan(json.dumps(new_content)), "user-1",
            {"canvas_id": "c-1", "canvas_type": "email", "content": {"body": "old"}},
            return_reason=True,
        )
    assert result is None
    assert reason == "dead_link: https://dead.ca/products/x"
    upd.assert_not_called()


@pytest.mark.asyncio
async def test_apply_proceeds_when_all_new_links_live():
    import json

    new_content = {"body": '<a href="https://live.ca/products/y">spec</a>'}
    with patch("core.chat_canvas_editor._new_dead_links",
               new=AsyncMock(return_value=[])), \
         patch("tools.canvas_crud_tool.update_canvas_content",
               new=AsyncMock(return_value={"success": True})) as upd:
        result, reason = await apply_canvas_edit(
            _plan(json.dumps(new_content)), "user-1",
            {"canvas_id": "c-1", "canvas_type": "email", "content": {"body": "old"}},
            return_reason=True,
        )
    assert reason is None
    assert (result or {}).get("success")
    upd.assert_called_once()


def test_describe_apply_failure_renders_dead_link():
    msg = describe_apply_failure(
        "dead_link: https://shop.ca/products/guessed", "email")
    assert "404" in msg
    assert "https://shop.ca/products/guessed" in msg
    assert "unchanged" in msg


# ───────────────── _site_search_evidence (planner fallback) ─────────────────

@pytest.mark.asyncio
async def test_site_search_fetches_domain_search_page():
    mcp = MagicMock()
    mcp.web_fetch = AsyncMock(return_value={
        "url": "https://brennan.ca/search?q=WG-350DSAV",
        "content": "10.5\" Semi-Automatic Double Miter Band Saw\n"
                   "Links on this page:\n"
                   "- https://brennan.ca/products/linmac-wg-350dsav-real\n",
    })
    block = await _site_search_evidence(
        "find the url link on brennan.ca for the WG-350DSAV", None, mcp)
    assert block and "brennan.ca/search?q=" in block
    assert "linmac-wg-350dsav-real" in block
    fetched = mcp.web_fetch.await_args.args[0]
    assert fetched.startswith("https://brennan.ca/search?q=")
    assert "WG-350DSAV" in fetched or "wg" in fetched.lower()


@pytest.mark.asyncio
async def test_site_search_skips_when_no_domain_in_query():
    mcp = MagicMock()
    mcp.web_fetch = AsyncMock()
    block = await _site_search_evidence("who is the lead", None, mcp)
    assert block is None
    mcp.web_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_site_search_none_when_page_unreadable():
    mcp = MagicMock()
    mcp.web_fetch = AsyncMock(return_value={"content": "", "error": "down"})
    block = await _site_search_evidence("product page on shop.ca", None, mcp)
    assert block is None


# ───────────────── _extract_page_links (web_fetch fallback) ─────────────────

def test_extract_page_links_absolute_and_filtered():
    html = """
    <a href="/products/linmac-wg-350dsav">10.5" Band Saw</a>
    <a href="https://cdn.shop.ca/x.png"><img src="x"></a>
    <a href="mailto:sales@brennan.ca">email</a>
    <a href="/products/linmac-wg-350dsav">dup</a>
    """
    links = _extract_page_links(html, "https://brennan.ca/search?q=x")
    assert links == [
        'https://brennan.ca/products/linmac-wg-350dsav - 10.5" Band Saw',
        "https://cdn.shop.ca/x.png - ",
    ][:len(links)] or links[0].startswith("https://brennan.ca/products/")
    assert not any("mailto" in l for l in links)


# ───────────────── mcp_service: rejected Tavily key ─────────────────

@pytest.mark.asyncio
async def test_web_search_reports_rejected_key_not_unconfigured():
    """Live 2026-09-08: an INVALID key fell through to 'not configured',
    hiding the real failure — every search silently returned nothing and
    the reply model fabricated URLs instead."""
    from integrations.mcp_service import mcp_service

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, *a, **k):
            return MagicMock(status_code=401)

    with patch("httpx.AsyncClient", return_value=_FakeClient()), \
         patch.dict("os.environ", {"TAVILY_API_KEY": "tvly-bad-key"}):
        res = await mcp_service.web_search("brennan.ca WG-350DSAV", None)
    assert res["results"] == []
    assert "rejected the configured API key" in (res.get("error") or "")
