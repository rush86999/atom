"""
Productivity Tool - Notion Integration

Provides Notion workspace operations with governance integration.

Supports:
- Workspace search (pages, databases)
- Database querying and schema inspection
- Page creation, editing, and content appending
- Read operations for INTERN+ maturity
- Write operations for SUPERVISED+ maturity

Governance:
- Read actions (search, query, get): INTERN+ maturity
- Write actions (create, update, append): SUPERVISED+ maturity
- STUDENT agents blocked from all Notion operations
- Local-only mode enforcement (Notion requires cloud API)
"""

import asyncio
import json
from typing import Any, Dict, List, Optional, Tuple

from core.database import get_db_session
from core.governance_cache import GovernanceCache
from core.models import AgentRegistry
from core.productivity.notion_service import NotionService
from core.privsec.local_only_guard import LocalOnlyGuard
from core.structured_logger import get_logger

logger = get_logger(__name__)

# Initialize governance cache
_governance_cache = GovernanceCache()


class NotionTool:
    """
    Notion workspace tool for AI agents.

    Provides access to Notion workspaces for personal productivity:
    - Search pages and databases
    - Query databases with filters
    - Create and edit pages
    - Add content to pages

    **Governance**:
    - Read operations (search, query, get): INTERN+ maturity
    - Write operations (create, update, append): SUPERVISED+ maturity
    - STUDENT agents blocked from all operations

    **Local-Only Mode**:
    - Notion requires cloud API access
    - Blocked in local-only mode (ATOM_LOCAL_ONLY=true)
    - Suggests local alternatives (markdown files)

    Examples:
    - "Search for pages about project X"
    - "Show me tasks due this week"
    - "Create a new task for tomorrow's meeting"
    - "Mark the meeting task as complete"
    - "Add meeting notes to the project database"
    """

    def __init__(self):
        """Initialize Notion tool with governance cache."""
        # Governance cache for permission checks
        self.governance_cache = GovernanceCache()

        logger.info("NotionTool initialized", tool_available=True)

    async def run(
        self,
        action: str,
        agent_id: Optional[str] = None,
        maturity_level: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Execute Notion operation with governance enforcement.

        Args:
            action: Operation to perform (search, list_databases, etc.)
            agent_id: Agent identifier for governance check
            user_id: User ID for token lookup
            **kwargs: Action-specific parameters

        Returns:
            Dict with operation results

        Raises:
            PermissionError: If maturity level too low
            RuntimeError: If Notion not connected or local-only mode enabled
        """
        # Governance check - maturity requirements by action type
        read_actions = {
            "search",
            "list_databases",
            "query_database",
            "get_schema",
            "get_page",
            "get_blocks"
        }

        write_actions = {
            "create_page",
            "update_page",
            "append_blocks",
        }

        # Determine required maturity level
        if action in read_actions:
            required_maturity = "INTERN"
        elif action in write_actions:
            required_maturity = "SUPERVISED"
        else:
            return {
                "success": False,
                "error": f"Unknown action: {action}",
                "available_actions": sorted(read_actions | write_actions)
            }

        # Check governance permission
        allowed, reason = await self._check_notion_permission(
            agent_id=agent_id,
            user_id=user_id or "default",
            action=action,
            required_maturity=required_maturity
        )

        if not allowed:
            logger.warning(
                "Notion permission denied",
                action=action,
                agent_id=agent_id,
                reason=reason
            )
            raise PermissionError(reason)

        # Execute action
        try:
            result = await self._execute_action(
                action=action,
                user_id=user_id or "default",
                **kwargs
            )

            logger.info(
                "Notion action completed",
                action=action,
                agent_id=agent_id
            )

            return result

        except PermissionError:
            # Re-raise permission errors
            raise
        except Exception as e:
            logger.error(
                "Notion action failed",
                action=action,
                error=str(e),
                kwargs=kwargs
            )
            return {
                "success": False,
                "error": str(e),
                "action": action
            }

    async def _check_notion_permission(
        self,
        agent_id: Optional[str],
        user_id: str,
        action: str,
        required_maturity: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if agent has permission for Notion operation.

        Args:
            agent_id: Agent ID (None if human-triggered)
            user_id: User ID
            action: Action being performed
            required_maturity: Required maturity level (INTERN or SUPERVISED)

        Returns:
            (allowed, reason) tuple
        """
        # If no agent_id, it's a human-triggered action (allow)
        if not agent_id:
            return True, None

        # Check governance cache
        cache_key = f"notion_{action}"
        cached = _governance_cache.get(agent_id, cache_key)
        if cached:
            return cached.get("allowed", False), cached.get("reason")

        # Check agent maturity level from database
        try:
            with get_db_session() as db:
                agent = db.query(AgentRegistry).filter(
                    AgentRegistry.id == agent_id
                ).first()

                if not agent:
                    return False, f"Agent '{agent_id}' not found"

                # Check maturity level
                maturity = agent.maturity_level
                maturity_order = ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]

                try:
                    current_level = maturity_order.index(maturity)
                    required_level = maturity_order.index(required_maturity)
                except ValueError:
                    return False, f"Invalid maturity level: {maturity}"

                allowed = current_level >= required_level
                reason = None

                if not allowed:
                    reason = (
                        f"Notion {action} requires {required_maturity}+ maturity "
                        f"(agent is {maturity})"
                    )

                # Cache decision
                _governance_cache.set(agent_id, cache_key, {
                    "allowed": allowed,
                    "reason": reason,
                    "maturity": maturity
                })

                # Check local-only mode (Notion requires cloud API)
                if allowed:
                    try:
                        guard = LocalOnlyGuard()
                        guard.allow_external_request(
                            service="notion",
                            reason=f"Notion API requires cloud access"
                        )
                    except Exception as e:
                        return False, str(e)

                return allowed, reason

        except Exception as e:
            logger.error("Permission check failed", error=str(e))
            return False, f"Permission check failed: {str(e)}"

    async def _execute_action(
        self,
        action: str,
        user_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute specific Notion action.

        Args:
            action: Action to execute
            user_id: User ID for Notion service
            **kwargs: Action-specific parameters

        Returns:
            Dict with action results
        """
        # Create Notion service
        service = NotionService(user_id)

        # Execute action
        if action == "search":
            query = kwargs.get("query", "")
            if not query:
                return {"success": False, "error": "Query parameter required for search"}

            results = await service.search_workspace(query)
            return {
                "success": True,
                "action": "search",
                "query": query,
                "count": len(results),
                "results": results
            }

        elif action == "list_databases":
            databases = await service.list_databases()
            return {
                "success": True,
                "action": "list_databases",
                "count": len(databases),
                "databases": databases
            }

        elif action == "query_database":
            database_id = kwargs.get("database_id")
            if not database_id:
                return {"success": False, "error": "database_id parameter required"}

            # Parse filter from JSON string if provided
            filter_param = kwargs.get("filter")
            if filter_param:
                if isinstance(filter_param, str):
                    try:
                        filter_param = json.loads(filter_param)
                    except json.JSONDecodeError:
                        return {"success": False, "error": "Invalid filter JSON"}

            pages = await service.query_database(database_id, filter_param)
            return {
                "success": True,
                "action": "query_database",
                "database_id": database_id,
                "count": len(pages),
                "pages": pages
            }

        elif action == "get_schema":
            database_id = kwargs.get("database_id")
            if not database_id:
                return {"success": False, "error": "database_id parameter required"}

            schema = await service.get_database_schema(database_id)
            return {
                "success": True,
                "action": "get_schema",
                "database_id": database_id,
                "schema": schema
            }

        elif action == "get_page":
            page_id = kwargs.get("page_id")
            if not page_id:
                return {"success": False, "error": "page_id parameter required"}

            page = await service.get_page(page_id)
            return {
                "success": True,
                "action": "get_page",
                "page_id": page_id,
                "page": page
            }

        elif action == "get_blocks":
            page_id = kwargs.get("page_id")
            if not page_id:
                return {"success": False, "error": "page_id parameter required"}

            blocks = await service.get_page_blocks(page_id)
            return {
                "success": True,
                "action": "get_blocks",
                "page_id": page_id,
                "count": len(blocks),
                "blocks": blocks
            }

        elif action == "create_page":
            database_id = kwargs.get("database_id")
            properties = kwargs.get("properties")

            if not database_id:
                return {"success": False, "error": "database_id parameter required"}
            if not properties:
                return {"success": False, "error": "properties parameter required"}

            # Parse properties from JSON string if provided
            if isinstance(properties, str):
                try:
                    properties = json.loads(properties)
                except json.JSONDecodeError:
                    return {"success": False, "error": "Invalid properties JSON"}

            page = await service.create_page(database_id, properties)
            return {
                "success": True,
                "action": "create_page",
                "database_id": database_id,
                "page": page
            }

        elif action == "update_page":
            page_id = kwargs.get("page_id")
            properties = kwargs.get("properties")

            if not page_id:
                return {"success": False, "error": "page_id parameter required"}
            if not properties:
                return {"success": False, "error": "properties parameter required"}

            # Parse properties from JSON string if provided
            if isinstance(properties, str):
                try:
                    properties = json.loads(properties)
                except json.JSONDecodeError:
                    return {"success": False, "error": "Invalid properties JSON"}

            page = await service.update_page(page_id, properties)
            return {
                "success": True,
                "action": "update_page",
                "page_id": page_id,
                "page": page
            }

        elif action == "append_blocks":
            page_id = kwargs.get("page_id")
            blocks = kwargs.get("blocks")

            if not page_id:
                return {"success": False, "error": "page_id parameter required"}
            if not blocks:
                return {"success": False, "error": "blocks parameter required"}

            # Parse blocks from JSON string if provided
            if isinstance(blocks, str):
                try:
                    blocks = json.loads(blocks)
                except json.JSONDecodeError:
                    return {"success": False, "error": "Invalid blocks JSON"}

            result = await service.append_page_blocks(page_id, blocks)
            return {
                "success": True,
                "action": "append_blocks",
                "page_id": page_id,
                "result": result
            }

        else:
            return {
                "success": False,
                "error": f"Unknown action: {action}",
                "available_actions": sorted({
                    "search", "list_databases", "query_database", "get_schema",
                    "get_page", "get_blocks", "create_page", "update_page", "append_blocks"
                })
            }


# Tool registration function

def register_notion_tool(tool_registry=None):
    """
    Register NotionTool with tool registry.

    Args:
        tool_registry: ToolRegistry instance (optional)

    Returns:
        Registered NotionTool instance
    """
    from core.tool_registry import ToolRegistry

    if tool_registry is None:
        tool_registry = ToolRegistry()

    notion_tool = NotionTool()

    tool_registry.register_tool(
        tool=notion_tool,
        category="productivity",
        tags=["notion", "knowledge", "database", "tasks", "notes", "workspace"],
        requires_internet=True,
        maturity_levels={
            "read": "INTERN",
            "write": "SUPERVISED"
        }
    )

    logger.info("NotionTool registered with ToolRegistry")

    return notion_tool
