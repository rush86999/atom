"""MCP JSON-RPC 2.0 protocol handler.

Dispatches incoming JSON-RPC requests to the registered MCP tools.
Implements: initialize, tools/list, tools/call, ping.

``tools/list`` is PAGINATED per the MCP spec
(https://modelcontextprotocol.io/specification/2025-11-25/server/utilities/pagination):
the server owns the page size, hands back an OPAQUE ``nextCursor`` while
more tools remain, and a missing ``nextCursor`` means end-of-results. A
cursor this server did not issue (or one issued against a different tool
catalog) is rejected with -32602 Invalid params rather than silently
restarting from page one.

Two failure modes this closes, both observed in the wild on other servers:
an unpaginated ``tools/list`` that dumps the whole catalog into a model's
context in one shot, and a "nextCursor" returned on the LAST page (a
non-advancing cursor makes a spec-compliant client paginate forever).
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from core.mcp_server import MCP_PROTOCOL_VERSION, MCP_SERVER_NAME, MCP_SERVER_VERSION
from core.mcp_server.tools import get_all_tools

logger = logging.getLogger(__name__)

# Build the tool lookup once (tools are stateless).
_tools_by_name = {t.name: t for t in get_all_tools()}

#: Tools per ``tools/list`` page. The spec leaves page size to the server;
#: 50 keeps a discovery page small while making the common catalog one page.
DEFAULT_TOOLS_PAGE_SIZE = 50

#: Cursor format version — bump when the payload shape changes so old
#: cursors are rejected instead of misread.
_CURSOR_VERSION = 1


class InvalidCursorError(ValueError):
    """Raised for a cursor this server did not issue (JSON-RPC -32602)."""


def _catalog_fingerprint(names: List[str]) -> str:
    """Fingerprint of the catalog a cursor was minted against.

    A cursor is only meaningful for the exact tool set it came from; if the
    catalog shifted (server restarted with more tools, a tenant connector
    was added), continuing from a stale offset would silently SKIP tools.
    Mismatch -> invalid cursor -> clean restart from page one.
    """
    material = "\n".join(names).encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:16]


def _encode_cursor(offset: int, fingerprint: str) -> str:
    payload = json.dumps(
        {"v": _CURSOR_VERSION, "i": offset, "f": fingerprint},
        separators=(",", ":"),
    )
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str, fingerprint: str) -> int:
    """Offset carried by ``cursor``. Raises :class:`InvalidCursorError`."""
    if not isinstance(cursor, str) or not cursor.strip():
        raise InvalidCursorError("cursor must be a non-empty string")
    text = cursor.strip()
    padding = "=" * (-len(text) % 4)
    try:
        raw = base64.urlsafe_b64decode(text + padding).decode("utf-8")
        payload = json.loads(raw)
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise InvalidCursorError(f"malformed cursor: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("v") != _CURSOR_VERSION:
        raise InvalidCursorError("unsupported cursor version")
    if payload.get("f") != fingerprint:
        raise InvalidCursorError("cursor was issued for a different tool catalog")
    offset = payload.get("i")
    if not isinstance(offset, int) or offset < 0:
        raise InvalidCursorError("cursor offset out of range")
    return offset


def tools_page_size() -> int:
    """Server-owned page size, overridable for tests/operators."""
    try:
        size = int(os.getenv("ATOM_MCP_TOOLS_PAGE_SIZE", "") or DEFAULT_TOOLS_PAGE_SIZE)
    except (TypeError, ValueError):
        return DEFAULT_TOOLS_PAGE_SIZE
    return max(1, size)


async def handle_jsonrpc(request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle a single JSON-RPC 2.0 request and return a response.

    Returns None for notifications (requests without an ``id``).
    """
    method = request.get("method", "")
    params = request.get("params", {}) or {}
    req_id = request.get("id")
    is_notification = req_id is None

    try:
        if method == "initialize":
            result = _handle_initialize(params)
        elif method == "initialized" or method == "notifications/initialized":
            # Notification — no response needed
            return None
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = _handle_tools_list(params)
        elif method == "tools/call":
            result = await _handle_tools_call(params)
        else:
            return _error_response(req_id, -32601, f"Method not found: {method}")

        if is_notification:
            return None
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result,
        }
    except InvalidCursorError as e:
        # Spec: an invalid cursor SHOULD produce -32602 Invalid params.
        if is_notification:
            return None
        return _error_response(req_id, -32602, f"Invalid params: {e}")
    except Exception as e:
        logger.error(f"MCP handler error for {method}: {e}", exc_info=True)
        if is_notification:
            return None
        return _error_response(req_id, -32603, f"Internal error: {e}")


def _handle_initialize(params: Dict[str, Any]) -> Dict[str, Any]:
    """Respond to the MCP initialize handshake."""
    return {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "capabilities": {
            "tools": {},
        },
        "serverInfo": {
            "name": MCP_SERVER_NAME,
            "version": MCP_SERVER_VERSION,
        },
    }


def _all_tool_entries() -> List[Dict[str, Any]]:
    return [t.to_dict() for t in _tools_by_name.values()]


def _handle_tools_list(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """One page of available MCP tools, with an opaque ``nextCursor``.

    The result is ``{"tools": [...]}`` plus ``nextCursor`` only while more
    tools remain — never on the final page, so a spec-compliant client that
    loops until the cursor is absent terminates.
    """
    params = params or {}
    entries = _all_tool_entries()
    names = [t["name"] for t in entries]
    fingerprint = _catalog_fingerprint(names)

    cursor = params.get("cursor")
    offset = _decode_cursor(cursor, fingerprint) if cursor else 0

    page_size = tools_page_size()
    page = entries[offset:offset + page_size]
    result: Dict[str, Any] = {"tools": page}

    next_offset = offset + len(page)
    if next_offset < len(entries):
        result["nextCursor"] = _encode_cursor(next_offset, fingerprint)
    return result


async def _handle_tools_call(params: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch a tools/call request to the matching tool handler."""
    name = params.get("name", "")
    arguments = params.get("arguments", {}) or {}

    tool = _tools_by_name.get(name)
    if tool is None:
        raise ValueError(f"Unknown tool: {name}")

    result = await tool.handler(arguments)

    # MCP tools/call returns content blocks.
    # If the handler returned an error, surface it as an MCP error content block.
    if isinstance(result, dict) and "error" in result:
        return {
            "content": [
                {"type": "text", "text": f"Error: {result['error']}"},
            ],
            "isError": True,
        }

    return {
        "content": [
            {"type": "text", "text": _format_result(result)},
        ],
        "isError": False,
    }


def _format_result(result: Any) -> str:
    """Format a tool result as a text string for the MCP content block."""
    import json
    try:
        return json.dumps(result, indent=2, default=str)
    except Exception:
        return str(result)


def _error_response(req_id: Optional[Any], code: int, message: str) -> Dict[str, Any]:
    """Build a JSON-RPC error response."""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }
