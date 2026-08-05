"""
MCP client config routes — P6 (Cloudflare OS G6).

Admin surface to register and manage external MCP servers that Atom connects TO
(as a client), reviving ``core.mcp_service.register_server`` (previously never
called). Distinct from ``api/mcp_server_routes.py`` (the outbound MCP SERVER
surface Atom exposes). Mounted at ``/api/mcp/servers``.

Auth: ``Permission.SYSTEM_ADMIN`` (admin-only) for register/delete; GET is
admin-gated too so the server list isn't enumerable.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import User, get_current_user
from core.database import get_db
from core.rbac_service import Permission
from core.security_dependencies import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp/servers", tags=["mcp-client"])


class MCPServerConfig(BaseModel):
    """Configuration for an external MCP server connection."""
    name: str
    transport: str = "http"  # http | sse | stdio
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    command: Optional[str] = None     # stdio only
    args: Optional[List[str]] = None  # stdio only
    env: Optional[Dict[str, str]] = None  # stdio only


@router.get("")
@router.get("/")
async def list_servers(
    user: User = Depends(require_permission(Permission.SYSTEM_ADMIN)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List registered external MCP servers and their cached tool counts."""
    from core.mcp_service import mcp_service
    out = []
    for server_id, tools in mcp_service.tools_cache.items():
        if server_id in ("google-search", "local-tools", "brightdata"):
            continue  # built-in hardcoded servers, not external
        out.append({
            "server_id": server_id,
            "tool_count": len(tools),
            "connected": server_id in mcp_service.external_clients,
        })
    return {"success": True, "data": out, "count": len(out)}


@router.post("")
@router.post("/")
async def register_server(
    config: MCPServerConfig,
    user: User = Depends(require_permission(Permission.SYSTEM_ADMIN)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Register and connect an external MCP server. Performs the handshake + tools/list."""
    from core.mcp_service import mcp_service

    server_config: Dict[str, Any] = {
        "transport": config.transport,
        "url": config.url,
        "headers": config.headers or {},
    }
    if config.command:
        server_config["command"] = config.command
    if config.args:
        server_config["args"] = config.args
    if config.env:
        server_config["env"] = config.env

    try:
        await mcp_service.register_server(config.name, server_config)
    except Exception as e:
        logger.error("Failed to register MCP server %s: %s", config.name, e)
        raise HTTPException(status_code=502, detail=f"Failed to connect to MCP server: {config.name}")

    tool_count = len(mcp_service.tools_cache.get(config.name, []))
    return {
        "success": True,
        "data": {
            "server_id": config.name,
            "connected": config.name in mcp_service.external_clients,
            "tool_count": tool_count,
        },
        "message": f"MCP server {config.name} connected ({tool_count} tools)",
    }


@router.delete("/{server_id}")
async def unregister_server(
    server_id: str,
    user: User = Depends(require_permission(Permission.SYSTEM_ADMIN)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disconnect and remove an external MCP server."""
    from core.mcp_service import mcp_service

    client = mcp_service.external_clients.pop(server_id, None)
    if client is not None:
        try:
            await client.close()
        except Exception as e:
            logger.warning("Error closing MCP client %s: %s", server_id, e)
    mcp_service.tools_cache.pop(server_id, None)
    mcp_service.servers.pop(server_id, None)
    return {"success": True, "message": f"MCP server {server_id} disconnected"}
