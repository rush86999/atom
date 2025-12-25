from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any, List
from integrations.mcp_service import mcp_service
import logging

router = APIRouter(prefix="/api/mcp", tags=["mcp"])
logger = logging.getLogger(__name__)

@router.get("/servers")
async def list_mcp_servers():
    """Returns all active MCP servers."""
    return await mcp_service.get_active_connections()

@router.get("/servers/{server_id}/tools")
async def list_server_tools(server_id: str):
    """Returns tools for a specific MCP server."""
    tools = await mcp_service.get_server_tools(server_id)
    if not tools and server_id != "google-search":
        raise HTTPException(status_code=404, detail="Server not found or no tools available")
    return tools

@router.post("/execute")
async def execute_mcp_action(
    server_id: str = Body(...),
    tool_name: str = Body(...),
    arguments: Dict[str, Any] = Body({})
):
    """Executes an action on an MCP server."""
    try:
        result = await mcp_service.execute_tool(server_id, tool_name, arguments)
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(f"MCP Tool Execution Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search")
async def perform_search(query: str):
    """Convenience endpoint specifically for web search via MCP."""
    try:
        result = await mcp_service.web_search(query)
        return result
    except Exception as e:
        logger.error(f"MCP Search Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
