"""MCP server HTTP+SSE routes.

Exposes the MCP JSON-RPC handler over HTTP POST (for request/response) and
SSE (for streaming). Mounted at /mcp in main_api_app.py alongside the gateway.

Default ON (MCP_SERVER_ENABLED=true). Requires authentication via the same
get_current_user dependency as other API routes.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from core.models import User
from core.security_dependencies import get_current_user
from core.mcp_server import MCP_SERVER_ENABLED
from core.mcp_server.handler import handle_jsonrpc

router = APIRouter(prefix="/mcp", tags=["MCP Server"])
logger = logging.getLogger(__name__)


def _require_mcp_enabled() -> None:
    """Gate the MCP server behind MCP_SERVER_ENABLED."""
    if not MCP_SERVER_ENABLED:
        raise HTTPException(status_code=503, detail="MCP server is disabled")


@router.post("/")
@router.post("")
async def mcp_jsonrpc(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """Handle a single JSON-RPC 2.0 request over HTTP POST.

    This is the primary MCP endpoint. Clients send a JSON-RPC request body;
    the response is a JSON-RPC response (or empty for notifications).
    """
    _require_mcp_enabled()

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Handle batch requests (array of requests)
    if isinstance(body, list):
        responses = []
        for req in body:
            resp = await handle_jsonrpc(req)
            if resp is not None:
                responses.append(resp)
        return JSONResponse(content=responses if responses else {})

    response = await handle_jsonrpc(body)
    if response is None:
        return JSONResponse(content={}, status_code=202)  # notification accepted
    return JSONResponse(content=response)


@router.get("/sse")
async def mcp_sse(
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """SSE stream for MCP server-to-client messages.

    Currently a minimal keepalive stream. Full bidirectional MCP-over-SSE
    would use this for server-initiated notifications (resource updates,
    log messages). Most MCP clients use the HTTP POST endpoint above for
    request/response and this SSE stream for server pushes.
    """
    _require_mcp_enabled()

    async def event_stream():
        import asyncio
        # Send an initial endpoint event so the client knows where to POST.
        yield f"event: endpoint\ndata: /\n\n"
        # Keepalive ping every 30s
        while True:
            await asyncio.sleep(30)
            yield f"event: ping\ndata: {json.dumps({'timestamp': 'keepalive'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
