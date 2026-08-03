"""MCP JSON-RPC 2.0 protocol handler.

Dispatches incoming JSON-RPC requests to the registered MCP tools.
Implements: initialize, tools/list, tools/call, ping.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.mcp_server import MCP_PROTOCOL_VERSION, MCP_SERVER_NAME, MCP_SERVER_VERSION
from core.mcp_server.tools import get_all_tools

logger = logging.getLogger(__name__)

# Build the tool lookup once (tools are stateless).
_tools_by_name = {t.name: t for t in get_all_tools()}


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
            result = _handle_tools_list()
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


def _handle_tools_list() -> Dict[str, Any]:
    """List all available MCP tools."""
    return {
        "tools": [t.to_dict() for t in _tools_by_name.values()],
    }


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
