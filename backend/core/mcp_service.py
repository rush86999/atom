import logging
import json
import asyncio
import os
import httpx
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class MCPTool(BaseModel):
    """Standardized representation of an MCP Tool"""
    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    server_id: str

class MCPService:
    """
    Core Model Context Protocol (MCP) Service.
    Acts as a hub for multiple MCP servers (local and remote).
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MCPService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.servers = {}
            self.tools_cache: Dict[str, List[MCPTool]] = {}
            self.workspace_tools: Dict[str, List[str]] = {} # workspace_id -> [tool_names]
            
            # Initialize the tool registry for local tools
            try:
                from tools.registry import get_tool_registry
                self.tool_registry = get_tool_registry()
                logger.info("✓ Tool Registry integrated with MCP Service")
            except ImportError:
                self.tool_registry = None
                logger.warning("Tool Registry not found, local-tools discovery will be limited")
                
            logger.info("Core MCP Service initialized")

    def register_tool(self, tool: MCPTool):
        """Manually register a tool to the hub."""
        if tool.server_id not in self.tools_cache:
            self.tools_cache[tool.server_id] = []
        
        # Check if already exists to avoid duplicates
        existing = next((t for t in self.tools_cache[tool.server_id] if t.name == tool.name), None)
        if existing:
            self.tools_cache[tool.server_id].remove(existing)
        
        self.tools_cache[tool.server_id].append(tool)
        logger.debug(f"Registered tool {tool.name} for server {tool.server_id}")

    async def register_server(self, server_id: str, server_config: Dict[str, Any]):
        """Register a new MCP server (stdio or http)"""
        self.servers[server_id] = server_config
        # Refresh tools for this server
        await self.refresh_tools(server_id)

    async def get_active_connections(self) -> List[Dict[str, Any]]:
        """Returns a list of currently connected MCP servers."""
        # For now, bridge to legacy or return from cache
        from integrations.mcp_service import mcp_service as legacy_mcp
        return await legacy_mcp.get_active_connections()

    async def get_server_tools(self, server_id: str) -> List[Dict[str, Any]]:
        """Returns tools for a specific server (legacy format for compatibility)"""
        if server_id in self.tools_cache:
            return [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in self.tools_cache[server_id]]
        
        from integrations.mcp_service import mcp_service as legacy_mcp
        return await legacy_mcp.get_server_tools(server_id)

    async def refresh_tools(self, server_id: str):
        """Fetch/Update tools from a specific server"""
        # For certain servers, we use a bridge to the legacy mcp_service for now
        if server_id in ["google-search", "local-tools", "brightdata"]:
            from integrations.mcp_service import mcp_service as legacy_mcp
            tools = await legacy_mcp.get_server_tools(server_id)
            
            self.tools_cache[server_id] = [
                MCPTool(
                    name=t["name"],
                    description=t.get("description", ""),
                    parameters=t.get("parameters", {}),
                    server_id=server_id
                ) for t in tools
            ]
            
            # Inject Coding Agent tools into local-tools
            if server_id == "local-tools":
                # Primary tool source: Automated Tool Registry
                if self.tool_registry:
                    registry_tools = self.tool_registry.export_all()
                    for t in registry_tools:
                        self.tools_cache[server_id].append(
                            MCPTool(
                                name=t["name"],
                                description=t.get("description", ""),
                                parameters=t.get("parameters", {}),
                                server_id=server_id
                            )
                        )
                    logger.info(f"✓ Registered {len(registry_tools)} tools from Registry to local-tools")
                
                # Secondary: Hardcoded/Legacy overrides (ensure critical tools are always present)
                # Note: Registry might already have these, MCPTool will overwrite below if duplicate in same refresh
                hardcoded_tools = [
                    MCPTool(
                        name="read_codebase",
                        description="Read file content from the tenant's secure codebase workspace.",
                        parameters={"type": "object", "properties": {"file_path": {"type": "string"}}},
                        server_id="local-tools"
                    ),
                    MCPTool(
                        name="write_code_file",
                        description="Write content to a file in the tenant's codebase workspace.",
                        parameters={"type": "object", "properties": {"file_path": {"type": "string"}, "content": {"type": "string"}}},
                        server_id="local-tools"
                    ),
                    MCPTool(
                        name="list_directory_recursive",
                        description="recursively list all files in the tenant's codebase workspace.",
                        parameters={"type": "object", "properties": {"dir_path": {"type": "string", "default": "."}}},
                        server_id="local-tools"
                    ),
                    MCPTool(
                        name="run_local_terminal",
                        description="Execute a command on the user's LOCAL machine via Atom Satellite. Use for 'ls', 'git', etc.",
                        parameters={"type": "object", "properties": {"command": {"type": "string"}}},
                        server_id="local-tools"
                    )
                ]
                
                for ht in hardcoded_tools:
                    # Avoid duplicates
                    if not any(t.name == ht.name for t in self.tools_cache[server_id]):
                        self.tools_cache[server_id].append(ht)

            # Inject Bright Data MCP tools
            if server_id == "brightdata":
                self.tools_cache[server_id].extend([
                    MCPTool(
                        name="brightdata_search",
                        description="Search the web with Bright Data's geo-targeted search",
                        parameters={
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "country": {"type": "string", "default": "us"}
                            },
                            "required": ["query"]
                        },
                        server_id="brightdata"
                    ),
                    MCPTool(
                        name="brightdata_crawl",
                        description="Crawl websites at scale with Bright Data",
                        parameters={
                            "type": "object",
                            "properties": {
                                "url": {"type": "string"},
                                "depth": {"type": "number", "default": 1}
                            },
                            "required": ["url"]
                        },
                        server_id="brightdata"
                    ),
                    MCPTool(
                        name="brightdata_access",
                        description="Access geo-restricted content and bypass CAPTCHAs",
                        parameters={
                            "type": "object",
                            "properties": {
                                "url": {"type": "string"},
                                "country": {"type": "string"}
                            },
                            "required": ["url"]
                        },
                        server_id="brightdata"
                    ),
                    MCPTool(
                        name="brightdata_navigate",
                        description="Automate browser interactions dynamically",
                        parameters={
                            "type": "object",
                            "properties": {
                                "url": {"type": "string"},
                                "actions": {"type": "array", "items": {"type": "object"}}
                            },
                            "required": ["url", "actions"]
                        },
                        server_id="brightdata"
                    )
                ])
        else:
            # Placeholder for real MCP protocol handshake
            logger.warning(f"Server {server_id} refresh not yet implemented for dynamic MCP")

    async def get_available_tools(self, workspace_id: Optional[str] = None) -> List[MCPTool]:
        """
        Get available tools across all servers.
        In the future, this will filter based on workspace_id and enabled integrations.
        """
        all_tools = []
        for server_tools in self.tools_cache.values():
            all_tools.extend(server_tools)
        
        # If no tools in cache, try initializing default servers
        if not all_tools:
            await self.refresh_tools("google-search")
            await self.refresh_tools("local-tools")
            await self.refresh_tools("brightdata")
            for server_tools in self.tools_cache.values():
                all_tools.extend(server_tools)
                
        return all_tools

    async def call_tool(
        self, 
        tool_name: str, 
        arguments: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Standard entry point for agents to call tools."""
        return await self.execute_tool(tool_name, arguments, context)

    async def execute_tool(
        self, 
        tool_name: str, 
        arguments: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Standardized Tool Routing and Execution (MCP Hive Parity)
        Routes to: Coding Agent Service, Satellite, Tool Registry, or Legacy MCP.
        """
        context = context or {}
        server_id = None
        
        # 1. Resolve server_id for the tool
        for sid, tools in self.tools_cache.items():
            if any(t.name == tool_name for t in tools):
                server_id = sid
                break
        
        # 2. Unified Governance Check for Critical Actions
        critical_tools = [
            "read_codebase", "write_code_file", "list_directory_recursive",
            "terminal_command", "propose_command", "run_local_terminal",
            "browser_navigate", "browser_action", "email_send", "whatsapp_send_message"
        ]
        
        if tool_name in critical_tools:
            agent_id = context.get("agent_id")
            if agent_id:
                try:
                    from core.database import SessionLocal
                    from core.agent_governance_service import AgentGovernanceService
                    with SessionLocal() as db:
                        gov_service = AgentGovernanceService(db)
                        check = gov_service.enforce_action(agent_id, tool_name)
                        if not check["proceed"]:
                            logger.warning(f"Governance BLOCK: {agent_id} -> {tool_name}")
                            return {
                                "error": f"Governance Block: {check['reason']}",
                                "status": check["status"],
                                "required_action": check["action_required"]
                            }
                except Exception as e:
                    logger.error(f"Governance failure for {tool_name}: {e}")
                    return {"error": "Security check failed."}

        # 3. Execution: Coding Agent Service
        from core.coding_agent_service import coding_agent_service
        tenant_id = context.get("tenant_id", "default")
        
        coding_tool_map = {
            "read_codebase": lambda: coding_agent_service.read_codebase(tenant_id, arguments.get("file_path")),
            "write_code_file": lambda: coding_agent_service.write_code_file(tenant_id, arguments.get("file_path"), arguments.get("content")),
            "list_directory_recursive": lambda: coding_agent_service.list_directory(tenant_id, arguments.get("dir_path", ".")),
            "terminal_command": lambda: coding_agent_service.execute_terminal_command(tenant_id, arguments.get("command"), arguments.get("canvas_id")),
            "browser_navigate": lambda: coding_agent_service.browser_navigate(tenant_id, arguments.get("canvas_id"), arguments.get("url")),
            "browser_action": lambda: coding_agent_service.execute_browser_action(tenant_id, arguments.get("canvas_id"), arguments.get("action_type"), arguments.get("selector"), arguments.get("value"))
        }

        if tool_name in coding_tool_map:
            logger.info(f"MCP: Executing Coding Tool {tool_name}")
            return await coding_tool_map[tool_name]()

        # 4. Execution: Satellite (Local Device)
        if tool_name == "run_local_terminal":
            from core.satellite_service import satellite_service
            return await satellite_service.execute_local_tool(tenant_id, "run_terminal", arguments)

        # 5. Execution: Tool Registry (Native Plugins)
        if self.tool_registry:
            tool_meta = self.tool_registry.get(tool_name)
            if tool_meta:
                logger.info(f"MCP: Executing Registry Tool {tool_name}")
                call_args = {**arguments, "user_id": context.get("user_id"), "tenant_id": tenant_id, "agent_id": context.get("agent_id")}
                return await tool_meta.function(**{k: v for k, v in call_args.items() if v is not None})

        # 6. Legacy Fallback (Default to multi-server mcp_service)
        from integrations.mcp_service import mcp_service as legacy_mcp
        logger.info(f"MCP: Routing {tool_name} to Legacy MCP on {server_id or 'auto'}")
        return await legacy_mcp.execute_tool(server_id or "local-tools", tool_name, arguments, context)

# Global Instance
mcp_service = MCPService()
