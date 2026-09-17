"""MCP ``tools/list`` pagination (gap #4, protocol side).

The audit's finding: the tool catalog grew without a cap — ~52 registry
tools + ~94 local tools + ontology actions + one entry per tenant connector
operation — and every one of them was rendered into context. At the MCP
boundary, ``tools/list`` returned the ENTIRE catalog in a single response
with no ``nextCursor``, so a spec-compliant client had no way to pull it in
bounded pages and no way to know the list was complete.

Contract pinned here is the MCP pagination spec
(https://modelcontextprotocol.io/specification/2025-11-25/server/utilities/pagination):
page size is server-determined, the cursor is OPAQUE, a missing
``nextCursor`` means end-of-results, and an invalid cursor is -32602.

The last-page case gets its own test on purpose: returning a non-advancing
``nextCursor`` on the final page is a documented real-world bug that makes
spec-compliant clients paginate forever, inflating the catalog instead of
bounding it.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from core.mcp_server import handler as mcp_handler


def _list(params=None):
    req = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    if params is not None:
        req["params"] = params
    return asyncio.run(mcp_handler.handle_jsonrpc(req))


def _drain(page_size):
    """Walk the whole catalog the way a spec-compliant client must."""
    names, cursor, guard = [], None, 0
    while True:
        guard += 1
        assert guard < 100, "pagination did not terminate"
        params = {"cursor": cursor} if cursor else {}
        result = _list(params)["result"]
        names.extend(t["name"] for t in result["tools"])
        cursor = result.get("nextCursor")
        if not cursor:
            return names


@pytest.fixture
def small_pages(monkeypatch):
    monkeypatch.setenv("ATOM_MCP_TOOLS_PAGE_SIZE", "2")


class TestToolsListPagination:
    def test_page_is_bounded_by_the_server_page_size(self, small_pages):
        result = _list()["result"]
        assert len(result["tools"]) == 2

    def test_next_cursor_present_while_more_remain(self, small_pages):
        result = _list()["result"]
        assert result["nextCursor"]

    def test_last_page_has_no_next_cursor(self, small_pages):
        """A non-advancing cursor on the final page = infinite client loop."""
        cursor = None
        last_page = None
        for _ in range(50):
            params = {"cursor": cursor} if cursor else {}
            result = _list(params)["result"]
            last_page = result
            cursor = result.get("nextCursor")
            if not cursor:
                break
        else:
            pytest.fail("never reached the final page")

        assert "nextCursor" not in last_page
        # And the page before it must NOT have pointed back at itself.
        assert last_page["tools"], "final page should carry the tail of the catalog"

    def test_walking_every_page_yields_the_full_catalog_exactly_once(self, small_pages):
        walked = _drain(2)
        expected = [t.name for t in mcp_handler.get_all_tools()]
        assert walked == expected
        assert len(walked) == len(set(walked))

    def test_single_page_catalog_returns_no_cursor(self, monkeypatch):
        monkeypatch.setenv("ATOM_MCP_TOOLS_PAGE_SIZE", "10000")
        result = _list()["result"]
        assert "nextCursor" not in result
        assert len(result["tools"]) == len(mcp_handler.get_all_tools())

    def test_cursor_is_opaque_not_an_offset(self, small_pages):
        cursor = _list()["result"]["nextCursor"]
        assert cursor != "2"
        # Opaque means clients must not parse it — so we are free to encode.
        import base64
        decoded = json.loads(base64.urlsafe_b64decode(cursor + "=="))
        assert decoded["i"] == 2


class TestInvalidCursors:
    def test_garbage_cursor_is_invalid_params_not_a_silent_restart(self, small_pages):
        resp = _list({"cursor": "not-a-real-cursor"})
        assert resp["error"]["code"] == -32602
        assert "Invalid params" in resp["error"]["message"]

    def test_empty_cursor_is_treated_as_the_first_page(self, small_pages):
        """Spec: clients should support both paginated and non-paginated
        flows — an empty cursor means "start", not "error" (many clients
        serialize an absent cursor as "")."""
        resp = _list({"cursor": ""})
        assert resp["result"]["tools"] == _list()["result"]["tools"]

    def test_cursor_from_a_different_catalog_is_rejected(self, small_pages, monkeypatch):
        """Tools changing under a cursor must not silently SKIP entries."""
        cursor = _list()["result"]["nextCursor"]

        original = mcp_handler._all_tool_entries

        def shifted():
            entries = original()
            return entries + [{"name": "brand_new_tool", "description": "",
                               "inputSchema": {}}]

        monkeypatch.setattr(mcp_handler, "_all_tool_entries", shifted)
        resp = _list({"cursor": cursor})
        assert resp["error"]["code"] == -32602
        assert "catalog" in resp["error"]["message"]


class TestPageSizeConfig:
    def test_default_page_size_is_bounded(self):
        assert mcp_handler.tools_page_size() >= 1

    def test_bad_env_value_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("ATOM_MCP_TOOLS_PAGE_SIZE", "not-an-int")
        assert mcp_handler.tools_page_size() == mcp_handler.DEFAULT_TOOLS_PAGE_SIZE
        monkeypatch.setenv("ATOM_MCP_TOOLS_PAGE_SIZE", "0")
        assert mcp_handler.tools_page_size() >= 1


class TestBackwardsCompatibility:
    def test_no_params_still_returns_a_tools_array(self, monkeypatch):
        monkeypatch.setenv("ATOM_MCP_TOOLS_PAGE_SIZE", "10000")
        result = _list()["result"]
        assert isinstance(result["tools"], list) and result["tools"]
        assert "name" in result["tools"][0]
