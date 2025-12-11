"""
MCP (Model Context Protocol) Integration Routes
Comprehensive MCP server management API endpoints
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import os

from integrations.mcp_service import mcp_service

logger = logging.getLogger(__name__)

# Create FastAPI router
router = APIRouter(prefix="/api/mcp", tags=["mcp"])


class MCPConnectRequest(BaseModel):
    server_id: str
    user_id: str = "default_user"


class MCPDisconnectRequest(BaseModel):
    server_id: str
    user_id: str = "default_user"


class MCPExecuteToolRequest(BaseModel):
    server_id: str
    tool_name: str
    arguments: Dict[str, Any] = {}
    user_id: str = "default_user"


class MCPAddCustomServerRequest(BaseModel):
    server_id: str
    command: str
    args: List[str] = []
    description: str = "Custom MCP server"
    category: str = "custom"
    icon: str = "⚙️"
    user_id: str = "default_user"


@router.get("/status")
async def mcp_status(user_id: str = "default_user"):
    """Get MCP integration status"""
    logger.info(f"Getting MCP status for user: {user_id}")

    status = await mcp_service.health_check()

    return {
        "ok": True,
        "service": "mcp",
        "user_id": user_id,
        **status
    }


@router.get("/health")
async def mcp_health(user_id: str = "default_user"):
    """Health check endpoint (alias for status)"""
    return await mcp_status(user_id)


@router.get("/servers")
async def get_mcp_servers(user_id: str = "default_user"):
    """Get list of available MCP servers"""
    logger.info(f"Getting MCP servers for user: {user_id}")

    servers = await mcp_service.get_available_servers()

    return {
        "ok": True,
        "servers": servers,
        "total_servers": len(servers),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/servers/{server_id}")
async def get_mcp_server(server_id: str, user_id: str = "default_user"):
    """Get specific MCP server information"""
    logger.info(f"Getting MCP server: {server_id} for user: {user_id}")

    servers = await mcp_service.get_available_servers()
    server = next((s for s in servers if s["id"] == server_id), None)

    if not server:
        raise HTTPException(status_code=404, detail=f"Server {server_id} not found")

    # Check if connected
    connections = await mcp_service.get_active_connections()
    is_connected = any(c["server_id"] == server_id for c in connections)

    if is_connected:
        tools = await mcp_service.get_server_tools(server_id)
        server["tools"] = tools
        server["tools_count"] = len(tools)
        server["status"] = "connected"

    return {
        "ok": True,
        "server": server,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/servers/connect")
async def connect_mcp_server(request: MCPConnectRequest):
    """Connect to an MCP server"""
    logger.info(f"Connecting to MCP server: {request.server_id} for user: {request.user_id}")

    result = await mcp_service.connect_to_server(request.server_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return {
        "ok": True,
        "connection": result,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/servers/disconnect")
async def disconnect_mcp_server(request: MCPDisconnectRequest):
    """Disconnect from an MCP server"""
    logger.info(f"Disconnecting from MCP server: {request.server_id} for user: {request.user_id}")

    result = await mcp_service.disconnect_from_server(request.server_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return {
        "ok": True,
        "disconnection": result,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/connections")
async def get_active_connections(user_id: str = "default_user"):
    """Get list of active MCP server connections"""
    logger.info(f"Getting active MCP connections for user: {user_id}")

    connections = await mcp_service.get_active_connections()

    return {
        "ok": True,
        "connections": connections,
        "total_connections": len(connections),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/connections/{server_id}/tools")
async def get_server_tools(server_id: str, user_id: str = "default_user"):
    """Get available tools from a connected MCP server"""
    logger.info(f"Getting tools for MCP server: {server_id} for user: {user_id}")

    tools = await mcp_service.get_server_tools(server_id)

    return {
        "ok": True,
        "server_id": server_id,
        "tools": tools,
        "tools_count": len(tools),
        "timestamp": datetime.now().isoformat()
    }


@router.post("/connections/{server_id}/tools/{tool_name}/execute")
async def execute_server_tool(
    server_id: str,
    tool_name: str,
    request: MCPExecuteToolRequest = None
):
    """Execute a tool on a connected MCP server"""
    if request is None:
        request = MCPExecuteToolRequest(server_id=server_id, tool_name=tool_name)

    logger.info(f"Executing tool {tool_name} on MCP server: {server_id} for user: {request.user_id}")

    result = await mcp_service.execute_tool(
        server_id=server_id,
        tool_name=tool_name,
        arguments=request.arguments
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return {
        "ok": True,
        "execution": result,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/servers/custom")
async def add_custom_server(request: MCPAddCustomServerRequest):
    """Add a custom MCP server configuration"""
    logger.info(f"Adding custom MCP server: {request.server_id} for user: {request.user_id}")

    config = {
        "command": request.command,
        "args": request.args,
        "description": request.description,
        "category": request.category,
        "icon": request.icon
    }

    result = await mcp_service.add_custom_server(request.server_id, config)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return {
        "ok": True,
        "server": {
            "id": request.server_id,
            **config
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/categories")
async def get_server_categories(user_id: str = "default_user"):
    """Get MCP server categories with counts"""
    logger.info(f"Getting MCP server categories for user: {user_id}")

    servers = await mcp_service.get_available_servers()
    categories = {}

    for server in servers:
        category = server["category"]
        if category not in categories:
            categories[category] = {
                "name": category.replace("-", " ").title(),
                "count": 0,
                "servers": []
            }

        categories[category]["count"] += 1
        categories[category]["servers"].append({
            "id": server["id"],
            "name": server["name"],
            "description": server["description"],
            "icon": server["icon"],
            "status": server["status"]
        })

    return {
        "ok": True,
        "categories": categories,
        "total_categories": len(categories),
        "total_servers": len(servers),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/tools/all")
async def get_all_available_tools(user_id: str = "default_user"):
    """Get all available tools from all connected servers"""
    logger.info(f"Getting all available tools for user: {user_id}")

    connections = await mcp_service.get_active_connections()
    all_tools = []

    for connection in connections:
        server_id = connection["server_id"]
        tools = await mcp_service.get_server_tools(server_id)

        all_tools.extend([
            {
                "name": tool["name"],
                "description": tool["description"],
                "schema": tool["schema"],
                "server_id": server_id,
                "server_name": connection["config"].get("description", server_id),
                "category": connection["config"].get("category", "unknown")
            }
            for tool in tools
        ])

    return {
        "ok": True,
        "tools": all_tools,
        "total_tools": len(all_tools),
        "connected_servers": len(connections),
        "timestamp": datetime.now().isoformat()
    }