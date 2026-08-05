"""
Unified Action Registry — P1 (Cloudflare OS foundation).

A single decorator-based registry of named actions that BOTH the agent MCP
dispatch (``integrations/mcp_service.py:840,1105,1108``) AND the frontend RPC
endpoint (``api/rpc_routes.py``) route through. This closes the RPC split and
gives Phase 2 (capability bindings), Phase 3 (gatekeeper), and Phase 9 (sandbox
default-on) a single enforcement point.

Resolves the previously-latent ``ImportError`` in ``integrations/mcp_service.py``::

    from core.action_registry import action_registry   # was a dead seam
    action_registry.get_action(tool_name)
    await action_registry.execute_action(tool_name, arguments, context)

Interface (derived from the call sites above):
- ``action_registry.get_all_definitions()`` -> Iterable[ActionDefinition]
- ``action_registry.get_action(name)`` -> Optional[ActionDefinition]
- ``action_registry.list_actions()`` -> List[str] of registered names
- ``await action_registry.execute_action(name, args, context)`` -> Any
- ``execute_action`` raises ``ActionNotFoundError`` for unknown actions

Each ``ActionDefinition`` exposes ``.name``, ``.description``, and
``.parameters_schema`` (a JSON-schema-shaped dict with ``properties`` and
``required`` keys) so ``mcp_service.get_all_tools`` can render tool definitions
for the agent loop.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


class ActionNotFoundError(LookupError):
    """Raised when executing a registered action by an unknown name.

    Subclasses :class:`LookupError` so existing call sites that guard with
    ``except LookupError`` (e.g. the RPC route) keep working unchanged.
    """


# Action handler signature: async (args, context) -> result
ActionHandler = Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[Any]]


class ActionDefinition:
    """A named, invokable action registered in the registry."""

    __slots__ = ("name", "description", "handler", "parameters_schema")

    def __init__(
        self,
        name: str,
        handler: ActionHandler,
        description: str = "",
        parameters_schema: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.name = name
        self.handler = handler
        self.description = description or handler.__doc__ or f"Action {name}"
        # Default schema: an empty object accepting anything. mcp_service.py:843
        # reads .get("properties", {}) and .get("required", []).
        self.parameters_schema = parameters_schema or {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<ActionDefinition {self.name}>"


class ActionRegistry:
    """Registry of named actions shared by frontend RPC + agent MCP dispatch."""

    def __init__(self) -> None:
        self._actions: Dict[str, ActionDefinition] = {}

    def register(
        self,
        name: str,
        handler: ActionHandler,
        description: str = "",
        parameters_schema: Optional[Dict[str, Any]] = None,
    ) -> ActionDefinition:
        """Register an action. Overwrites an existing action with the same name."""
        action = ActionDefinition(name, handler, description, parameters_schema)
        self._actions[name] = action
        logger.debug("Registered action %s", name)
        return action

    def get_action(self, name: str) -> Optional[ActionDefinition]:
        """Return the action for ``name`` or ``None`` if not registered."""
        return self._actions.get(name)

    def get_all_definitions(self) -> List[ActionDefinition]:
        """Return all registered action definitions (for agent tool listing)."""
        return list(self._actions.values())

    def list_actions(self) -> List[str]:
        """Return all registered action names (sorted)."""
        return sorted(self._actions.keys())

    def list_action_names(self) -> List[str]:
        """Alias for :meth:`list_actions` (kept for backward compatibility)."""
        return self.list_actions()

    async def execute_action(
        self,
        name: str,
        arguments: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Any:
        """Execute a registered action by name.

        Raises:
            ActionNotFoundError: if the action is not registered.
        """
        action = self._actions.get(name)
        if action is None:
            raise ActionNotFoundError(f"Action '{name}' is not registered")
        return await action.handler(arguments, context)


# Module-level singleton — the symbol imported by mcp_service.py and rpc_routes.py.
action_registry = ActionRegistry()


def register_action(
    name: str,
    description: str = "",
    parameters_schema: Optional[Dict[str, Any]] = None,
):
    """Decorator that registers an async handler as a named action.

    Example::

        @register_action("documents.search", parameters_schema={...})
        async def search(args, context):
            return {...}
    """
    def decorator(func: ActionHandler) -> ActionHandler:
        action_registry.register(name, func, description, parameters_schema)
        return func

    return decorator


# ============================================================================
# Seed actions — shared by frontend RPC + agent MCP dispatch.
# Each wraps an existing service call. Kept deliberately thin: enforcement
# (capability gating P2, gatekeeper P3, sandbox P9) is layered above this.
# ============================================================================

_DOCUMENTS_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Search query"},
        "limit": {"type": "integer", "description": "Max results (optional)"},
    },
    "required": ["query"],
}

_CANVAS_READ_SCHEMA = {
    "type": "object",
    "properties": {
        "canvas_id": {"type": "string", "description": "Canvas ID to read"},
    },
    "required": ["canvas_id"],
}

_CANVAS_UPDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "canvas_id": {"type": "string"},
        "content": {"type": "object", "description": "New canvas content"},
        "canvas_type": {"type": "string"},
        "title": {"type": "string"},
    },
    "required": ["canvas_id", "content"],
}

_TASKS_CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "board_id": {"type": "string", "description": "Board (Kanban) ID to create the task in"},
        "column_id": {"type": "string", "description": "Destination column ID within the board"},
        "priority": {"type": "string", "description": "low|normal|high|urgent (default normal)"},
        "status": {"type": "string", "description": "Board status (default backlog)"},
    },
    "required": ["title", "board_id"],
}

_AGENTS_LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "description": "Filter by agent category (optional)"},
    },
    "required": [],
}


def _context_user_id(context: Dict[str, Any]) -> Optional[str]:
    """Best-effort user_id extraction from a dispatch context."""
    if not context:
        return None
    for key in ("user_id", "userId", "actor_id"):
        val = context.get(key)
        if val:
            return str(val)
    user = context.get("user")
    if user is not None:
        uid = getattr(user, "id", None)
        if uid:
            return str(uid)
    return None


@register_action(
    "documents.search",
    description="Search ingested and knowledge documents by query.",
    parameters_schema=_DOCUMENTS_SEARCH_SCHEMA,
)
async def _documents_search(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    query = (args.get("query") or "").strip()
    limit = int(args.get("limit", 10))
    if not query:
        return {"success": False, "error": "query is required", "results": []}
    try:
        from core.database import get_db_session
        from core.models import IngestedDocument, KnowledgeDocument
        from sqlalchemy import or_

        results: List[Dict[str, Any]] = []
        with get_db_session() as db:
            ingested = (
                db.query(IngestedDocument)
                .filter(
                    or_(
                        IngestedDocument.file_name.ilike(f"%{query}%"),
                        IngestedDocument.content_preview.ilike(f"%{query}%"),
                    )
                )
                .limit(limit)
                .all()
            )
            for d in ingested:
                results.append({
                    "source": "ingested",
                    "id": d.id,
                    "title": d.file_name,
                    "preview": (d.content_preview or "")[:200],
                })

            remaining = max(0, limit - len(results))
            if remaining:
                knowledge = (
                    db.query(KnowledgeDocument)
                    .filter(
                        or_(
                            KnowledgeDocument.title.ilike(f"%{query}%"),
                            KnowledgeDocument.content.ilike(f"%{query}%"),
                        )
                    )
                    .limit(remaining)
                    .all()
                )
                for d in knowledge:
                    results.append({
                        "source": "knowledge",
                        "id": d.id,
                        "title": d.title,
                        "preview": (d.content or "")[:200],
                    })

        return {"success": True, "query": query, "results": results}
    except Exception as e:
        logger.error("documents.search failed: %s", e)
        return {"success": False, "error": "Document search failed", "results": []}


@register_action(
    "canvas.read",
    description="Read the current content/state of a canvas by ID.",
    parameters_schema=_CANVAS_READ_SCHEMA,
)
async def _canvas_read(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from tools.canvas_crud_tool import read_canvas

    canvas_id = args.get("canvas_id")
    if not canvas_id:
        return {"success": False, "error": "canvas_id is required"}
    user_id = _context_user_id(context)
    if not user_id:
        return {"success": False, "error": "Authenticated user is required to read a canvas"}
    return await read_canvas(user_id, str(canvas_id))


@register_action(
    "canvas.update",
    description="Update the content of an existing canvas.",
    parameters_schema=_CANVAS_UPDATE_SCHEMA,
)
async def _canvas_update(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from tools.canvas_crud_tool import update_canvas_content

    canvas_id = args.get("canvas_id")
    content = args.get("content")
    if not canvas_id or content is None:
        return {"success": False, "error": "canvas_id and content are required"}
    user_id = _context_user_id(context)
    if not user_id:
        return {"success": False, "error": "Authenticated user is required to update a canvas"}
    return await update_canvas_content(
        user_id=user_id,
        canvas_id=str(canvas_id),
        content=content,
        canvas_type=args.get("canvas_type", "generic"),
        title=args.get("title"),
    )


@register_action(
    "tasks.create",
    description="Create a task (Kanban board item).",
    parameters_schema=_TASKS_CREATE_SCHEMA,
)
async def _tasks_create(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    title = (args.get("title") or "").strip()
    board_id = args.get("board_id")
    if not title or not board_id:
        return {"success": False, "error": "title and board_id are required"}
    try:
        from core.board_service import BoardService, TaskCreate
        from core.database import get_db_session

        user_id = _context_user_id(context)
        with get_db_session() as db:
            svc = BoardService(db)
            payload = TaskCreate(
                title=title,
                description=args.get("description"),
                column_id=args.get("column_id", ""),
                priority=args.get("priority", "normal"),
                status=args.get("status", "backlog"),
            )
            task = svc.create_task(
                board_id=str(board_id),
                created_by_user_id=user_id,
                payload=payload,
            )
            return {
                "success": True,
                "task": {
                    "id": task.id,
                    "board_id": task.board_id,
                    "column_id": task.column_id,
                    "title": task.title,
                    "description": task.description,
                    "status": task.status,
                },
            }
    except Exception as e:
        logger.error("tasks.create failed: %s", e)
        return {"success": False, "error": "Task creation failed"}


@register_action(
    "agents.list",
    description="List available registered agents.",
    parameters_schema=_AGENTS_LIST_SCHEMA,
)
async def _agents_list(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from core.database import get_db_session
        from core.models import AgentRegistry

        category = args.get("category")
        with get_db_session() as db:
            q = db.query(AgentRegistry)
            if category:
                q = q.filter(AgentRegistry.category == category)
            agents = q.all()
            return {
                "success": True,
                "agents": [
                    {
                        "id": a.id,
                        "name": a.name,
                        "description": a.description,
                        "status": a.status,
                        "category": a.category,
                        "capabilities": a.capabilities or [],
                    }
                    for a in agents
                ],
            }
    except Exception as e:
        logger.error("agents.list failed: %s", e)
        return {"success": False, "error": "Agent listing failed", "agents": []}
