"""
ATOM MCP Server Service
Provides integration with Model Context Protocol (MCP) servers
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import subprocess
import tempfile
from datetime import datetime, timezone
from loguru import logger

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    logger.warning("MCP SDK not available. Install with: pip install mcp")
    MCP_AVAILABLE = False

class MCPServerService:
    """Service for managing MCP server connections"""

    def __init__(self):
        self.mcp_config_path = os.getenv("MCP_CONFIG_PATH", ".mcp.json")
        self.mcp_servers: Dict[str, Any] = {}
        self.active_connections: Dict[str, Any] = {}
        self._load_mcp_config()

        # Popular MCP server configurations
        self.builtin_servers = {
            "filesystem": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-filesystem", "/tmp"],
                "description": "File system operations - read, write, navigate directories",
                "category": "storage",
                "icon": "📁"
            },
            "database": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-postgres", "postgresql://localhost/atom"],
                "description": "Database connectivity - SQL queries, schema management",
                "category": "database",
                "icon": "🗄️"
            },
            "web-search": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-brave-search"],
                "description": "Web search capabilities - real-time information retrieval",
                "category": "search",
                "icon": "🔍"
            },
            "git": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-git", "--repository", "."],
                "description": "Git repository operations - commit, branch, diff management",
                "category": "development",
                "icon": "🔧"
            },
            "memory": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-memory"],
                "description": "Memory/knowledge graph - persistent information storage",
                "category": "memory",
                "icon": "🧠"
            },
            "fetch": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-fetch"],
                "description": "Web content fetching - HTTP requests, API calls",
                "category": "network",
                "icon": "🌐"
            },
            "slack": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-slack"],
                "description": "Slack integration - messages, channels, user management",
                "category": "communication",
                "icon": "💬"
            },
            "github": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-github"],
                "description": "GitHub integration - repositories, issues, pull requests",
                "category": "development",
                "icon": "🐙"
            },
            "google-drive": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-gdrive"],
                "description": "Google Drive access - files, folders, documents",
                "category": "storage",
                "icon": "📂"
            },
            "kubernetes": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-kubernetes"],
                "description": "Kubernetes management - pods, services, deployments",
                "category": "infrastructure",
                "icon": "☸️"
            }
        }

    def _load_mcp_config(self):
        """Load MCP configuration from file"""
        try:
            if os.path.exists(self.mcp_config_path):
                with open(self.mcp_config_path, 'r') as f:
                    self.mcp_servers = json.load(f)
                logger.info(f"Loaded MCP configuration from {self.mcp_config_path}")
            else:
                logger.info("No MCP configuration file found, using builtin servers")
                self.mcp_servers = {"mcpServers": {}}
        except Exception as e:
            logger.error(f"Error loading MCP configuration: {e}")
            self.mcp_servers = {"mcpServers": {}}

    async def health_check(self) -> Dict[str, Any]:
        """Check MCP service health and available servers"""
        servers = await self.get_available_servers()
        active_count = len(self.active_connections)

        return {
            "status": "healthy",
            "service": "mcp_servers",
            "mcp_available": MCP_AVAILABLE,
            "total_servers": len(servers),
            "active_connections": active_count,
            "config_loaded": bool(self.mcp_servers),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def get_available_servers(self) -> List[Dict[str, Any]]:
        """Get list of available MCP servers"""
        servers = []

        # Add builtin servers
        for server_id, config in self.builtin_servers.items():
            servers.append({
                "id": server_id,
                "name": server_id.replace("-", " ").title(),
                "command": config["command"],
                "args": config["args"],
                "description": config["description"],
                "category": config["category"],
                "icon": config["icon"],
                "status": "available" if MCP_AVAILABLE else "mcp_unavailable",
                "type": "builtin"
            })

        # Add configured servers from .mcp.json
        configured_servers = self.mcp_servers.get("mcpServers", {})
        for server_id, config in configured_servers.items():
            servers.append({
                "id": server_id,
                "name": server_id.replace("-", " ").title(),
                "command": config.get("command", "npx"),
                "args": config.get("args", []),
                "description": config.get("description", "Custom MCP server"),
                "category": config.get("category", "custom"),
                "icon": config.get("icon", "⚙️"),
                "status": "configured",
                "type": "custom"
            })

        return servers

    async def connect_to_server(self, server_id: str) -> Dict[str, Any]:
        """Connect to an MCP server"""
        if not MCP_AVAILABLE:
            return {"error": "MCP SDK not available"}

        # Find server configuration
        server_config = self.builtin_servers.get(server_id)
        if not server_config:
            configured_servers = self.mcp_servers.get("mcpServers", {})
            server_config = configured_servers.get(server_id)

        if not server_config:
            return {"error": f"Server {server_id} not found"}

        try:
            # Create server parameters
            server_params = StdioServerParameters(
                command=server_config["command"],
                args=server_config["args"],
                env=None
            )

            # Create client session and connect
            session = ClientSession()
            transport = await stdio_client(server_params)
            await session.connect(transport)

            # Store connection
            self.active_connections[server_id] = {
                "session": session,
                "transport": transport,
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "config": server_config
            }

            # Get available tools from server
            tools_result = await session.list_tools()
            tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "schema": tool.inputSchema
                }
                for tool in tools_result.tools
            ]

            return {
                "success": True,
                "server_id": server_id,
                "connected_at": self.active_connections[server_id]["connected_at"],
                "tools_count": len(tools),
                "tools": tools
            }

        except Exception as e:
            logger.error(f"Error connecting to MCP server {server_id}: {e}")
            return {"error": str(e)}

    async def disconnect_from_server(self, server_id: str) -> Dict[str, Any]:
        """Disconnect from an MCP server"""
        if server_id not in self.active_connections:
            return {"error": f"Not connected to server {server_id}"}

        try:
            connection = self.active_connections[server_id]
            await connection["session"].close()
            await connection["transport"].close()
            del self.active_connections[server_id]

            return {"success": True, "server_id": server_id}

        except Exception as e:
            logger.error(f"Error disconnecting from MCP server {server_id}: {e}")
            return {"error": str(e)}

    async def get_server_tools(self, server_id: str) -> List[Dict[str, Any]]:
        """Get available tools from a connected server"""
        if server_id not in self.active_connections:
            return []

        try:
            session = self.active_connections[server_id]["session"]
            tools_result = await session.list_tools()

            return [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "schema": tool.inputSchema
                }
                for tool in tools_result.tools
            ]

        except Exception as e:
            logger.error(f"Error getting tools from server {server_id}: {e}")
            return []

    async def execute_tool(self, server_id: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool on a connected MCP server"""
        if server_id not in self.active_connections:
            return {"error": f"Not connected to server {server_id}"}

        try:
            session = self.active_connections[server_id]["session"]
            result = await session.call_tool(tool_name, arguments)

            return {
                "success": True,
                "result": result.content,
                "tool_name": tool_name,
                "server_id": server_id
            }

        except Exception as e:
            logger.error(f"Error executing tool {tool_name} on server {server_id}: {e}")
            return {"error": str(e)}

    async def get_active_connections(self) -> List[Dict[str, Any]]:
        """Get list of active MCP server connections"""
        connections = []

        for server_id, connection in self.active_connections.items():
            tools = await self.get_server_tools(server_id)
            connections.append({
                "server_id": server_id,
                "connected_at": connection["connected_at"],
                "tools_count": len(tools),
                "config": connection["config"]
            })

        return connections

    async def add_custom_server(self, server_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Add a custom MCP server configuration"""
        try:
            if "mcpServers" not in self.mcp_servers:
                self.mcp_servers["mcpServers"] = {}

            self.mcp_servers["mcpServers"][server_id] = config

            # Save to file
            with open(self.mcp_config_path, 'w') as f:
                json.dump(self.mcp_servers, f, indent=2)

            logger.info(f"Added custom MCP server: {server_id}")
            return {"success": True, "server_id": server_id}

        except Exception as e:
            logger.error(f"Error adding custom MCP server {server_id}: {e}")
            return {"error": str(e)}


# Create global service instance
mcp_service = MCPServerService()