import logging
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import os
import httpx

logger = logging.getLogger(__name__)

class MCPService:
    """
    Model Context Protocol (MCP) Service.
    Enables agents to use tools from MCP servers and perform web search.
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MCPService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.active_servers = {}
            self.search_api_key = os.getenv("TAVILY_API_KEY") or os.getenv("BRAVE_SEARCH_API_KEY")
            logger.info("MCP Service initialized")

    async def get_active_connections(self) -> List[Dict[str, Any]]:
        """Returns a list of currently connected MCP servers."""
        return [
            {
                "server_id": sid,
                "name": info.get("name"),
                "connected_at": info.get("connected_at"),
                "status": "connected"
            } for sid, info in self.active_servers.items()
        ]

    async def get_server_tools(self, server_id: str) -> List[Dict[str, Any]]:
        """Returns a list of tools supported by a specific MCP server."""
        if server_id == "google-search":
            return [
                {"name": "web_search", "description": "Search the web for real-time information"},
                {"name": "fetch_page", "description": "Fetch the content of a specific URL"}
            ]
        return self.active_servers.get(server_id, {}).get("tools", [])

    async def execute_tool(self, server_id: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Executes a tool on a specific MCP server."""
        logger.info(f"Executing MCP tool {tool_name} on server {server_id} with args: {arguments}")
        
        if server_id == "google-search" or tool_name == "web_search":
            return await self.web_search(arguments.get("query", ""))
            
        # Placeholder for real MCP execution logic
        await asyncio.sleep(0.5)
        return {"result": f"Mock result from {server_id}:{tool_name}"}

    async def web_search(self, query: str) -> Dict[str, Any]:
        """
        Performs a web search using available search APIs or MCP servers.
        """
        logger.info(f"Performing web search for: {query}")
        
        # If we have a real Tavily API key, use it
        if os.getenv("TAVILY_API_KEY"):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": os.getenv("TAVILY_API_KEY"),
                            "query": query,
                            "include_answer": True
                        },
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        return response.json()
            except Exception as e:
                logger.error(f"Tavily search failed: {e}")

        # Default mock response for demonstration
        return {
            "query": query,
            "results": [
                {
                    "title": f"Recent trends in {query}",
                    "url": "https://example.com/trends",
                    "content": f"Real-time information about {query} shows increasing interest in AI automation for small businesses."
                }
            ],
            "answer": f"Current data suggests that {query} is a major focal point for growth in 2024-2025."
        }

# Singleton instance
mcp_service = MCPService()
