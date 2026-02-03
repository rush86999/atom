"""
Base Agent Mixin - Provides MCP capabilities to all agent types.
Ensures consistent web search and web access across all agents.
"""

from typing import Any, Dict

from integrations.mcp_service import mcp_service


class MCPCapableMixin:
    """
    Mixin providing MCP (Model Context Protocol) web search and web access to agents.
    
    Usage:
        class MyAgent(MCPCapableMixin):
            async def run(self):
                result = await self.web_search("AI trends 2025")
    """
    
    @property
    def mcp(self):
        """Access to the MCP service singleton."""
        return mcp_service
    
    async def web_search(self, query: str) -> Dict[str, Any]:
        """
        Convenience method for web search.
        
        Args:
            query: Search query string
            
        Returns:
            Search results with 'results' list and 'answer' summary
        """
        return await mcp_service.web_search(query)
    
    async def fetch_url(self, url: str) -> Dict[str, Any]:
        """
        Fetch content from a URL via MCP.
        
        Args:
            url: URL to fetch
            
        Returns:
            Page content and metadata
        """
        return await mcp_service.execute_tool(
            "browser", "fetch_page", {"url": url}
        )
