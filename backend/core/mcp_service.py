import logging
import json
import asyncio
import os
import hashlib
import time
import httpx
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field

# P6: real MCP client transport for external servers.
from core.mcp_client import MCPClient, MCPClientError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# R72 Workstream H — read-only tool-result memoization.
#
# Bounded LRU+TTL cache keyed on (tool_name, tenant_id, canonical-args).
# Only idempotent read-only tools participate (ToolMetadata.cacheable or the
# explicit whitelist below). Errors are never cached. The sandbox and
# governance checks always run BEFORE the cache lookup, so a cache hit can
# never bypass a governance block or a sandbox violation.
# ---------------------------------------------------------------------------
_MAX_TOOL_CACHE_ENTRIES = 256

# Coding-agent / hardcoded read-only tools not present in the ToolRegistry
# but safe to memoize. read_codebase + list_directory_recursive are pure
# workspace reads; get_all_tools is a metadata listing. Every mutating tool
# (write_code_file, terminal_command, run_local_terminal, browser_*, ...)
# is deliberately excluded.
_CACHEABLE_READ_ONLY_TOOLS = frozenset(
    {"read_codebase", "list_directory_recursive", "get_all_tools"}
)


def _is_error_result(result: Any) -> bool:
    """True when a tool result is an error dict — never cached."""
    if isinstance(result, dict) and result.get("error"):
        return True
    if isinstance(result, str) and result.strip().lower().startswith("error:"):
        return True
    return False


# ---------------------------------------------------------------------------
# Execution Sandbox Layer (Round 43 / Phase A) — module-level helpers.
#
# Defined at module scope (not as methods) so they can be unit-tested without
# instantiating the MCPService singleton. Kept lazy-imported so the sandbox
# has zero cost when the master switch is off.
# ---------------------------------------------------------------------------
def _sandbox_enabled() -> bool:
    """True if the sandbox layer should intercept this process's tool calls.

    Lazy import keeps the cost zero when ATOM_SANDBOX_ENABLED is false.
    """
    try:
        from core import sandbox_config

        return sandbox_config.is_sandbox_enabled()
    except Exception:  # noqa: BLE001 — sandbox must never break tool dispatch
        return False


def _sandbox_check(
    tool_name: str,
    args: Dict[str, Any],
    context: Dict[str, Any],
):
    """Evaluate the active run's policy against this tool call.

    Returns a ``SandboxDecision`` or ``None`` when no policy is in scope
    (e.g. run not yet issued, sandbox disabled mid-flight). Writes an
    audit row on any non-allowed decision (Phase A scope: tool whitelist
    only; Phase B-E hooks extend this).

    Never raises — failures are caught and return an ALLOWED decision
    with metadata_json.error so the call proceeds and the bug is
    surfaced via audit.
    """
    try:
        from core import sandbox_config
        from core.sandbox_policy import PolicyIssuer, SandboxDecision, ALLOWED
        from core.sandbox_audit import write_violation

        run_id = context.get("run_id") or context.get("execution_id")
        if not run_id:
            # No run context → policy not in scope. Proceed.
            return None

        # Phase A: build a per-call policy from the tier in context. (The
        # full RunSandbox row lookup arrives with Phase B when the FS
        # scope checker needs fs_roots. For Phase A we only need the
        # tier-floor whitelist which PolicyIssuer.issue can derive.)
        tier = (context.get("tier_at_issuance") or context.get("tier") or "").lower()
        if not tier:
            # No tier in context → can't issue. Proceed.
            return None

        issuer = PolicyIssuer()
        policy = issuer.issue(
            run_id=run_id,
            agent_id=context.get("agent_id", "unknown"),
            tier_at_issuance=tier,
            workspace_data_root=context.get("workspace_data_root"),
        )
        decision = issuer.check(
            policy=policy,
            tool_name=tool_name,
            args=args,
            context=context,
            phase="A",
        )

        # Phase B: filesystem scope check (only if Phase A allowed and
        # the FS sub-feature is enabled).
        if decision.is_allowed and sandbox_config.is_sandbox_fs_enabled():
            from core.sandbox_fs import validate as fs_validate

            fs_decision = fs_validate(policy, tool_name, args, context=context)
            if fs_decision.requires_review:
                decision = fs_decision

        # Phase C: tripwires + resource caps.
        # Tripwires run before caps (cheap regex first, then counter
        # increments). Both are independently toggleable.
        if decision.is_allowed and sandbox_config.is_sandbox_tripwires_enabled():
            from core import sandbox_tripwire

            tw_decision = sandbox_tripwire.check(
                tool_name=tool_name,
                args=args,
                args_hash=decision.args_hash,
                context=context,
            )
            if tw_decision.decision != "allowed":
                decision = tw_decision
                # Tripwire hit → fire KillRun (Phase C).
                if decision.killrun_triggered and sandbox_config.is_sandbox_force_enforce_enabled():
                    from core import sandbox_killrun

                    sandbox_killrun.trigger_killrun(
                        run_id,
                        reason=decision.violation_detail or "tripwire",
                        tripwire_id=decision.metadata_json.get("tripwire_id"),
                        execution_id=run_id,
                    )

        if decision.is_allowed and sandbox_config.is_sandbox_caps_enabled():
            from core import sandbox_caps

            cap_decision = sandbox_caps.check_caps(
                policy,
                tool_name=tool_name,
                args=args,
                args_hash=decision.args_hash,
                context=context,
            )
            if cap_decision.requires_review:
                decision = cap_decision

        # KillRun guard — abort if a prior tripwire killed this run.
        from core import sandbox_killrun

        sandbox_killrun.guard(run_id)

        # Audit the decision when it's a violation.
        if decision.requires_review:
            write_violation(
                decision,
                tenant_id=context.get("tenant_id"),
                workspace_id=context.get("workspace_id"),
                agent_id=context.get("agent_id"),
                user_id=context.get("user_id"),
                session_id=context.get("session_id"),
                run_id=run_id,
            )
        return decision
    except Exception as e:  # noqa: BLE001 — sandbox must never break dispatch
        # KillRunAborted must propagate — it's how tripwire kills abort the
        # AgentExecution. All other exceptions fail open (defensive: a
        # broken sandbox should not break agent work).
        from core.sandbox_killrun import KillRunAborted

        if isinstance(e, KillRunAborted):
            raise
        logger.debug("sandbox check failed open for %s: %s", tool_name, e)
        from core.sandbox_policy import SandboxDecision, ALLOWED

        return SandboxDecision(
            decision=ALLOWED,
            phase="A",
            tool_name=tool_name,
            metadata_json={"error": str(e)},
        )


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
            # R72 Workstream H: cache_key -> (expires_monotonic, result)
            self._tool_cache: Dict[str, tuple] = {}
            # P6: live MCPClient instances for external servers (server_id -> MCPClient).
            self.external_clients: Dict[str, Any] = {}

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
            # P6: real MCP protocol handshake via the MCPClient (HTTP+SSE / stdio).
            # Replaces the former "Placeholder for real MCP protocol handshake".
            config = self.servers.get(server_id, {})
            if not config:
                logger.warning(f"Server {server_id} has no config; skipping refresh")
                return
            try:
                client = MCPClient(server_id, config)
                await client.initialize()
                ext_tools = await client.list_tools()
                self.tools_cache[server_id] = [
                    MCPTool(
                        name=t.get("name", ""),
                        description=t.get("description", ""),
                        parameters=t.get("inputSchema") or t.get("parameters") or {},
                        server_id=server_id,
                    )
                    for t in ext_tools
                ]
                # Keep the live client for subsequent tools/call invocations.
                self.external_clients[server_id] = client
                logger.info(
                    "✓ MCP server %s connected: %d tools via %s",
                    server_id, len(self.tools_cache[server_id]), config.get("transport", "http"),
                )
            except MCPClientError as e:
                logger.error("MCP server %s handshake failed: %s", server_id, e)
            except Exception as e:
                logger.error("MCP server %s refresh failed: %s", server_id, e)

    async def call_external_tool(
        self, server_id: str, tool_name: str, arguments: Dict[str, Any]
    ) -> Any:
        """Invoke a tool on a registered external MCP server via its live client.

        Returns the textual tool result. Raises ``MCPClientError`` if the server
        is not connected.
        """
        client = self.external_clients.get(server_id)
        if client is None:
            raise MCPClientError(
                f"Server {server_id} is not connected; call register_server first"
            )
        return await client.call_tool(tool_name, arguments)

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

    # ------------------------------------------------------------------
    # R72 Workstream H — read-only tool-result memoization helpers.
    # ------------------------------------------------------------------
    def _tool_is_cacheable(self, tool_name: str) -> bool:
        """True if this tool's results may be memoized.

        Resolution order: ToolRegistry metadata (authoritative, carries the
        ``cacheable`` flag) → the hardcoded read-only whitelist for tools the
        registry doesn't own (coding-agent workspace reads).
        """
        if self.tool_registry is not None:
            meta = self.tool_registry.get(tool_name)
            if meta is not None:
                return bool(meta.cacheable)
        return tool_name in _CACHEABLE_READ_ONLY_TOOLS

    @staticmethod
    def _tool_cache_key(
        tool_name: str,
        arguments: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """Stable cache key: tool + tenant + canonical-args hash.

        tenant_id is included so two tenants reading the same path never
        share a memoized result (read_codebase content is tenant-scoped).
        """
        tenant_id = context.get("tenant_id", "default")
        payload = json.dumps(
            {"args": arguments, "tenant_id": tenant_id},
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"{tool_name}:{digest}"

    def _tool_cache_get(self, key: str) -> Any:
        """Return a live cache entry or None (expired entries are purged)."""
        item = self._tool_cache.get(key)
        if item is None:
            return None
        expires_at, result = item
        if expires_at < time.monotonic():
            del self._tool_cache[key]
            return None
        return result

    def _tool_cache_put(self, key: str, result: Any) -> None:
        """Store a result under ``key`` with the configured TTL, bounded LRU."""
        from core.hallucination_config import get_tool_cache_ttl

        ttl = get_tool_cache_ttl()
        if ttl <= 0:
            return
        expires_at = time.monotonic() + ttl
        if key not in self._tool_cache and len(self._tool_cache) >= _MAX_TOOL_CACHE_ENTRIES:
            # Evict expired entries first, then the oldest live entry.
            now = time.monotonic()
            expired = [k for k, (e, _) in self._tool_cache.items() if e < now]
            for k in expired:
                del self._tool_cache[k]
            if len(self._tool_cache) >= _MAX_TOOL_CACHE_ENTRIES:
                oldest = min(
                    self._tool_cache,
                    key=lambda k: self._tool_cache[k][0],
                )
                del self._tool_cache[oldest]
        self._tool_cache[key] = (expires_at, result)

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

        # 2b. Execution Sandbox Layer — Round 43 (Phase A, shadow mode)
        #
        # Deterministic blast-radius check. Where the governance block
        # above decides "is this agent *normally* allowed to do this?" the
        # sandbox decides "is this specific call within bounds?" — closing
        # the prompt-injection gap documented in
        # docs/security/TRUST_VS_SANDBOX.md.
        #
        # Shadow mode by default: policy is computed and an audit row is
        # written on any non-allowed decision, but the call proceeds
        # unchanged. Operators flip ATOM_SANDBOX_FORCE_ENFORCE=true after
        # observing violation distributions in staging.
        if _sandbox_enabled():
            decision = _sandbox_check(
                tool_name=tool_name,
                args=arguments,
                context=context,
            )
            if decision is not None and decision.requires_review:
                if decision.enforced:
                    logger.warning(
                        "Sandbox %s: %s -> %s (%s)",
                        decision.decision.upper(),
                        context.get("agent_id", "?"),
                        tool_name,
                        decision.violation_type,
                    )
                    return {
                        "error": f"Sandbox {decision.decision}: {decision.violation_detail}",
                        "status": "sandbox_blocked",
                        "sandbox_phase": decision.phase,
                        "violation_type": decision.violation_type,
                    }

        # 2c. R72 Workstream H — read-only tool-result memoization.
        #
        # Governance + sandbox run BEFORE this lookup (see above), so a cache
        # hit can never bypass a block. Only cacheable read-only tools are
        # considered; the flag defaults ON. Errors are never cached.
        from core.hallucination_config import is_tool_cache_enabled

        tool_cache_key = None
        if is_tool_cache_enabled() and self._tool_is_cacheable(tool_name):
            tool_cache_key = self._tool_cache_key(tool_name, arguments, context)
            cached = self._tool_cache_get(tool_cache_key)
            if cached is not None:
                logger.debug(f"MCP: tool cache HIT {tool_name}")
                return cached

        # 3. Execution: Coding Agent Service
        tenant_id = context.get("tenant_id", "default")

        coding_tool_map = {
            "read_codebase": lambda: coding_agent_service.read_codebase(tenant_id, arguments.get("file_path")),
            "write_code_file": lambda: coding_agent_service.write_code_file(tenant_id, arguments.get("file_path"), arguments.get("content")),
            "list_directory_recursive": lambda: coding_agent_service.list_directory(tenant_id, arguments.get("dir_path", ".")),
            "terminal_command": lambda: coding_agent_service.execute_terminal_command(tenant_id, arguments.get("command"), arguments.get("canvas_id")),
            "browser_navigate": lambda: coding_agent_service.browser_navigate(tenant_id, arguments.get("canvas_id"), arguments.get("url")),
            "browser_action": lambda: coding_agent_service.execute_browser_action(tenant_id, arguments.get("canvas_id"), arguments.get("action_type"), arguments.get("selector"), arguments.get("value"))
        }

        # Bug #8: wrap ALL tool execution in try/except so a single misbehaving
        # tool doesn't crash the dispatch loop or propagate TypeError from
        # await-ing a non-coroutine. Also cap output size (32KB) to prevent
        # context overflow / cost circumvention.
        _MAX_TOOL_OUTPUT = 32 * 1024
        try:
            if tool_name in coding_tool_map:
                # Import lazily: the coding-agent service is an optional
                # Hive-parity module. Importing it unconditionally would
                # raise ModuleNotFoundError for every non-coding tool.
                from core.coding_agent_service import coding_agent_service

                logger.info(f"MCP: Executing Coding Tool {tool_name}")
                result = await coding_tool_map[tool_name]()
            elif tool_name == "run_local_terminal":
                from core.satellite_service import satellite_service
                result = await satellite_service.execute_local_tool(tenant_id, "run_terminal", arguments)
            elif self.tool_registry:
                tool_meta = self.tool_registry.get(tool_name)
                if tool_meta:
                    logger.info(f"MCP: Executing Registry Tool {tool_name}")
                    call_args = {**arguments, "user_id": context.get("user_id"), "tenant_id": tenant_id, "agent_id": context.get("agent_id")}
                    result = await tool_meta.function(**{k: v for k, v in call_args.items() if v is not None})
                else:
                    from integrations.mcp_service import mcp_service as legacy_mcp
                    result = await legacy_mcp.execute_tool(server_id or "local-tools", tool_name, arguments, context)
            else:
                from integrations.mcp_service import mcp_service as legacy_mcp
                result = await legacy_mcp.execute_tool(server_id or "local-tools", tool_name, arguments, context)

            # Cap output size to prevent context overflow.
            if isinstance(result, str) and len(result) > _MAX_TOOL_OUTPUT:
                logger.warning(f"MCP tool {tool_name} returned {len(result)} bytes — truncating to {_MAX_TOOL_OUTPUT}")
                result = result[:_MAX_TOOL_OUTPUT] + "\n... [truncated by MCP output cap]"
            elif isinstance(result, dict):
                for k, v in result.items():
                    if isinstance(v, str) and len(v) > _MAX_TOOL_OUTPUT:
                        logger.warning(f"MCP tool {tool_name} field '{k}' returned {len(v)} bytes — truncating")
                        result[k] = v[:_MAX_TOOL_OUTPUT] + "\n... [truncated]"

            # Memoize successful read-only results only.
            if tool_cache_key is not None and not _is_error_result(result):
                self._tool_cache_put(tool_cache_key, result)

            return result

        except TypeError as te:
            logger.error(f"MCP tool {tool_name} TypeError (likely sync/async mismatch): {te}")
            return {"error": f"Tool {tool_name} failed: internal type error", "status": "error"}
        except Exception as te:
            logger.error(f"MCP tool {tool_name} execution failed: {te}", exc_info=True)
            return {"error": f"Tool {tool_name} failed: {str(te)[:200]}", "status": "error"}

# Global Instance
mcp_service = MCPService()
