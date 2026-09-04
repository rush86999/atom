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
    """A named, invokable action registered in the registry.

    Action contracts (gap B4, OWL-S-inspired): ``preconditions`` are
    structured facts that must hold in the execution context before the
    action may run (checked by :meth:`check_preconditions`); ``effects``
    declare what the action produces/changes, letting planners select
    actions by outcome and goal criteria reference action results. Both
    are optional and backward compatible.
    """

    __slots__ = ("name", "description", "handler", "parameters_schema",
                 "preconditions", "effects")

    def __init__(
        self,
        name: str,
        handler: ActionHandler,
        description: str = "",
        parameters_schema: Optional[Dict[str, Any]] = None,
        preconditions: Optional[List[Dict[str, Any]]] = None,
        effects: Optional[List[Dict[str, Any]]] = None,
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
        # Structured contracts: [{"fact": "workspace_id", "op": "exists"}, ...]
        self.preconditions = list(preconditions or [])
        # [{"effect": "graph_updated"}, {"effect": "goal_evaluated", "goal_id": "$args.goal_id"}]
        self.effects = list(effects or [])

    def check_preconditions(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Evaluate preconditions against ``context``.

        Each precondition: {"fact": "dotted.path", "op": "exists"|"eq"|"ne"|
        "in"|"true", "value": ...}. Returns the list of *failed* checks
        (empty list = all satisfied). Never raises.
        """
        failures: List[Dict[str, Any]] = []
        for pre in self.preconditions:
            fact = pre.get("fact", "")
            actual = _dig(context, fact)
            op = pre.get("op", "exists")
            expected = pre.get("value")
            ok = True
            if op == "exists":
                ok = actual is not None
            elif op == "true":
                ok = bool(actual)
            elif op == "eq":
                ok = actual == expected
            elif op == "ne":
                ok = actual != expected
            elif op == "in":
                ok = actual in (expected or [])
            if not ok:
                failures.append({"precondition": pre, "actual": actual})
        return failures

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<ActionDefinition {self.name}>"


def _dig(data: Dict[str, Any], dotted_path: str) -> Any:
    """Resolve 'a.b.c' against nested dicts; None when any hop is missing."""
    current: Any = data
    for part in str(dotted_path).split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


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
        preconditions: Optional[List[Dict[str, Any]]] = None,
        effects: Optional[List[Dict[str, Any]]] = None,
    ) -> ActionDefinition:
        """Register an action. Overwrites an existing action with the same name."""
        action = ActionDefinition(name, handler, description, parameters_schema,
                                  preconditions, effects)
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
    preconditions: Optional[List[Dict[str, Any]]] = None,
    effects: Optional[List[Dict[str, Any]]] = None,
):
    """Decorator that registers an async handler as a named action.

    Example::

        @register_action("documents.search", parameters_schema={...})
        async def search(args, context):
            return {...}
    """
    def decorator(func: ActionHandler) -> ActionHandler:
        action_registry.register(name, func, description, parameters_schema,
                                 preconditions, effects)
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
        "since": {"type": "string", "description": "Only documents modified at/after this ISO datetime"},
        "source": {"type": "string", "description": "Restrict to one store: 'ingested' | 'knowledge'"},
        "author": {"type": "string", "description": "Only documents from this author/integration (e.g. a drive integration id)"},
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

_CANVAS_LIST_VERSIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "canvas_id": {"type": "string", "description": "Canvas ID to list versions of"},
        "limit": {"type": "integer", "description": "Max versions to return (default 20, max 50)"},
        "include_content": {
            "type": "boolean",
            "description": "Include each version's full content (default false: short preview only)",
        },
    },
    "required": ["canvas_id"],
}

_CANVAS_RESTORE_VERSION_SCHEMA = {
    "type": "object",
    "properties": {
        "canvas_id": {"type": "string", "description": "Canvas ID to revert"},
        "audit_id": {
            "type": "string",
            "description": "Version to revert to (the audit_id from canvas.list_versions)",
        },
    },
    "required": ["canvas_id", "audit_id"],
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
    description="Hybrid (BM25 + vector) search over ingested and knowledge documents. "
                "Semantic: finds docs about a concept even without exact word overlap. "
                "Honors since/source/author filters. Returns ranked, VFS-citable results.",
    parameters_schema=_DOCUMENTS_SEARCH_SCHEMA,
)
async def _documents_search(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    query = (args.get("query") or "").strip()
    limit = int(args.get("limit", 10))
    if not query:
        return {"success": False, "error": "query is required", "results": []}
    try:
        from core.knowledge_vfs_config import knowledge_vfs_enabled

        # Kill-switch parity: flag OFF → exact legacy ILIKE behavior.
        if not knowledge_vfs_enabled():
            return await _documents_search_legacy(args, context)

        # Flag ON → real hybrid (BM25 FTS5/tsvector + LanceDB vector → RRF k=60).
        from core.hybrid_search.documents_hybrid import DocumentsHybridSearch
        since = args.get("since")
        source = (args.get("source") or "").strip().lower() or None
        author = (args.get("author") or "").strip().lower() or None

        svc = DocumentsHybridSearch()
        resp = await svc.search(
            query=query, limit=limit, since=since, source=source, author=author,
        )
        # DocumentsHybridSearch.search already returns the {success, query, results,
        # hybrid, stats} envelope matching this action's contract.
        return resp
    except Exception as e:
        logger.error("documents.search failed: %s", e)
        return {"success": False, "error": "Document search failed", "results": []}


_SEARCH_COMMUNICATIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "What to search conversation memory for (emails, Slack/WhatsApp/Teams/Telegram messages)"},
        "limit": {"type": "integer", "description": "Max results (default 5)"},
    },
    "required": ["query"],
}


@register_action(
    "search_communications",
    description="Search conversation memory (ingested emails + chat messages) "
                "with hybrid vector+FTS search. Use for 'what did X say about Y' "
                "questions. Results include app, timestamp, and content.",
    parameters_schema=_SEARCH_COMMUNICATIONS_SCHEMA,
)
async def _search_communications(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    query = (args.get("query") or "").strip()
    limit = int(args.get("limit", 5))
    if not query:
        return {"success": False, "error": "query is required", "results": []}
    try:
        import asyncio

        from integrations.atom_communication_ingestion_pipeline import (
            get_ingestion_pipeline,
        )

        pipeline = get_ingestion_pipeline("default")
        manager = getattr(pipeline, "memory_manager", pipeline)

        def _search():
            if getattr(manager, "connections_table", None) is None and hasattr(manager, "initialize"):
                manager.initialize()
            if getattr(manager, "connections_table", None) is None:
                return []
            return manager.search_communications(query[:500], limit)

        records = await asyncio.to_thread(_search)
        results = []
        for rec in records or []:
            content = str(rec.get("content") or rec.get("text") or "").strip()
            if not content:
                continue
            results.append({
                "id": str(rec.get("id") or ""),
                "app_type": rec.get("app_type"),
                "timestamp": str(rec.get("timestamp") or ""),
                "content": content[:400],
            })
        return {"success": True, "query": query, "results": results}
    except Exception as e:
        logger.error("search_communications failed: %s", e)
        return {"success": False, "error": "Communication search failed", "results": []}


_RECALL_EPISODES_SCHEMA = {
    "type": "object",
    "properties": {
        "task": {"type": "string", "description": "The current task/question to find similar past episodes for"},
        "mode": {"type": "string", "description": "contextual (default) | semantic | similar_failures"},
        "canvas_id": {"type": "string", "description": "Canvas-aware recall: boost episodes from this canvas"},
        "limit": {"type": "integer", "description": "Max episodes (default 3)"},
    },
    "required": ["task"],
}


@register_action(
    "recall_episodes",
    description="Recall past learning episodes (prior agent work sessions) relevant "
                "to a task — what was done, the outcome, and how the user judged it. "
                "Use before attempting a task similar to past work, or to answer "
                "'have we handled this before' questions. Pass canvas_id for "
                "canvas-aware recall (episodes from the same canvas are boosted).",
    parameters_schema=_RECALL_EPISODES_SCHEMA,
)
async def _recall_episodes(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    task = (args.get("task") or "").strip()
    mode = (args.get("mode") or "contextual").strip()
    limit = int(args.get("limit", 3))
    canvas_id = (args.get("canvas_id") or "").strip() or None
    if not task:
        return {"success": False, "error": "task is required", "episodes": []}
    try:
        # Canvas-aware mode: route through WorldModelService.recall_episodes,
        # which applies canvas (+0.3 same / -0.05 different) and feedback
        # boosts over BOTH the canonical episodes table and the mirror.
        if canvas_id:
            from core.agent_world_model import WorldModelService

            world_model = WorldModelService(workspace_id=str(context.get("workspace_id") or "default"))
            rows = await world_model.recall_episodes(
                task_description=task,
                agent_role=str(context.get("agent_role") or "agent"),
                agent_id=str(context.get("agent_id")) if context.get("agent_id") else None,
                canvas_id=canvas_id,
                limit=limit,
            )
            episodes = [{
                "id": str(r.get("episode_id") or ""),
                "task": r.get("task_description") or "",
                "outcome": r.get("outcome"),
                "canvas_id": r.get("canvas_id"),
                "final_score": r.get("final_score"),
            } for r in rows or []]
            return {"success": True, "mode": "canvas_aware", "episodes": episodes}

        from core.database import SessionLocal
        from core.episode_retrieval_service import EpisodeRetrievalService

        agent_id = str(context.get("agent_id") or "atom_main")
        db = SessionLocal()
        try:
            service = EpisodeRetrievalService(db)
            if mode == "semantic":
                result = await service.retrieve_semantic(agent_id, task, limit=limit)
            elif mode == "similar_failures":
                result = await service.retrieve_failed_similar(agent_id, task, limit=limit)
            else:
                result = await service.retrieve_contextual(agent_id, task, limit=limit)
        finally:
            db.close()
        episodes = []
        for ep in (result or {}).get("episodes", []) or []:
            episodes.append({
                "id": str(ep.get("id") or ""),
                "task": ep.get("task_description") or ep.get("summary") or "",
                "outcome": ep.get("outcome"),
                "created_at": str(ep.get("created_at") or ""),
            })
        return {"success": True, "mode": mode, "episodes": episodes}
    except Exception as e:
        logger.error("recall_episodes failed: %s", e)
        return {"success": False, "error": "Episode recall failed", "episodes": []}


async def _documents_search_legacy(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """The pre-P2 ILIKE implementation — flag-off parity path."""
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


# ============================================================================
# P2c (W1): Agent-native knowledge VFS actions (ls/cat/grep).
# Behind ATOM_KNOWLEDGE_VFS_ENABLED (default false). Kill-switch: returns a
# disabled note when off, never raises.
# ============================================================================

_DOCUMENTS_LS_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "VFS path to list (e.g. 'knowledge/documents')"},
    },
    "required": ["path"],
}

_DOCUMENTS_CAT_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "VFS leaf path (e.g. 'knowledge/documents/<id>/content.lines')"},
    },
    "required": ["path"],
}

_DOCUMENTS_GREP_SCHEMA = {
    "type": "object",
    "properties": {
        "pattern": {"type": "string", "description": "Regex pattern to search for"},
        "path_prefix": {"type": "string", "description": "VFS directory to search under (e.g. 'knowledge/documents')"},
    },
    "required": ["pattern", "path_prefix"],
}

_DOCUMENTS_TREE_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "VFS directory to render as a tree (e.g. 'knowledge/documents')"},
        "depth": {"type": "integer", "description": "Maximum tree depth (default 2)"},
    },
    "required": ["path"],
}

_DOCUMENTS_HEAD_TAIL_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "VFS leaf path (e.g. 'knowledge/documents/<id>/content.lines')"},
        "lines": {"type": "integer", "description": "Number of lines to return (default 20)"},
    },
    "required": ["path"],
}

_DOCUMENTS_SCAN_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "VFS directory to scan recursively"},
        "max_depth": {"type": "integer", "description": "Maximum recursion depth (default 10)"},
    },
    "required": ["path"],
}

_DOCUMENTS_MAP_SCHEMA = {
    "type": "object",
    "properties": {
        "paths": {"type": "array", "items": {"type": "string"},
                  "description": "VFS leaf paths to process, one item per path"},
        "op": {"type": "string", "description": "Operation to apply per path: 'cat' | 'head' | 'grep'"},
        "pattern": {"type": "string", "description": "Regex pattern when op='grep'"},
        "lines": {"type": "integer", "description": "Line limit when op='head'"},
        "max_items": {"type": "integer", "description": "Bounded fan-out cap (default 10, max 50)"},
    },
    "required": ["paths", "op"],
}

_DOCUMENTS_REDUCE_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {"type": "array", "description": "List of per-item map results ({'path', ...})"},
        "mode": {"type": "string", "description": "Aggregation: 'count' | 'concat' | 'unique'"},
    },
    "required": ["items", "mode"],
}

_DOCUMENTS_ASK_IMAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "VFS leaf path of an image"},
        "prompt": {"type": "string", "description": "Natural-language question about the image"},
    },
    "required": ["path", "prompt"],
}


def _vfs_disabled():
    return {
        "success": False, "error": "vfs_disabled",
        "message": "Knowledge VFS is disabled (ATOM_KNOWLEDGE_VFS_ENABLED=false).",
    }


def _vfs_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """Build the VFS context (workspace scoping) from the action context."""
    return {
        "workspace_id": (context.get("user") and context["user"].__dict__.get("workspace_id"))
        or context.get("workspace_id"),
        "user_id": context.get("user_id"),
    }


def _ensure_vfs_registered():
    """Lazily register the knowledge VFS provider (idempotent)."""
    from core.vfs_registry import get_provider
    if get_provider("knowledge") is None:
        try:
            from integrations.vfs.knowledge_vfs import KnowledgeVFSProvider
            from core.vfs_registry import register_provider
            register_provider(KnowledgeVFSProvider())
        except Exception:
            pass  # provider optional; actions degrade to empty results


@register_action(
    "documents.ls",
    description=(
        "List children of the knowledge VFS. args: path — start at "
        "'knowledge/documents' (one dir per ingested document) or "
        "'knowledge/conversations'. Returns entries [{name, type, path}]."
    ),
    parameters_schema=_DOCUMENTS_LS_SCHEMA,
)
async def _documents_ls(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from core.knowledge_vfs_config import knowledge_vfs_enabled
    if not knowledge_vfs_enabled():
        return _vfs_disabled()
    _ensure_vfs_registered()
    from core.vfs_registry import resolve_provider
    path = (args.get("path") or "").strip()
    provider = resolve_provider(path)
    if provider is None:
        return {"success": False, "error": "no_provider", "message": f"No VFS provider for path '{path}'"}
    nodes = await provider.ls(path, _vfs_context(context))
    return {"success": True, "path": path, "entries": [n.__dict__ for n in nodes]}


@register_action(
    "documents.cat",
    description=(
        "Read a document's FULL text as line-numbered lines (L1: …, L2: …) "
        "for precise citation. args: path — e.g. "
        "'knowledge/documents/<id>/content.lines' using an id from "
        "documents.ls or a path from documents.grep."
    ),
    parameters_schema=_DOCUMENTS_CAT_SCHEMA,
)
async def _documents_cat(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from core.knowledge_vfs_config import knowledge_vfs_enabled
    if not knowledge_vfs_enabled():
        return _vfs_disabled()
    _ensure_vfs_registered()
    from core.vfs_registry import resolve_provider
    path = (args.get("path") or "").strip()
    provider = resolve_provider(path)
    if provider is None:
        return {"success": False, "error": "no_provider", "message": f"No VFS provider for path '{path}'"}
    res = await provider.cat(path, _vfs_context(context))
    return {"success": True, **res.to_dict()}


@register_action(
    "documents.grep",
    description=(
        "Regex-search ALL knowledge content (documents and conversations). "
        "args: pattern (regex, case-insensitive), path_prefix ('knowledge'). "
        "Returns matches [{path, line, snippet}] — read a hit's full text "
        "with documents.cat(path=path + '/content.lines')."
    ),
    parameters_schema=_DOCUMENTS_GREP_SCHEMA,
)
async def _documents_grep(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from core.knowledge_vfs_config import knowledge_vfs_enabled
    if not knowledge_vfs_enabled():
        return _vfs_disabled()
    _ensure_vfs_registered()
    from core.vfs_registry import resolve_provider
    pattern = (args.get("pattern") or "").strip()
    prefix = (args.get("path_prefix") or "").strip()
    provider = resolve_provider(prefix)
    if provider is None:
        return {"success": False, "error": "no_provider", "message": f"No VFS provider for prefix '{prefix}'"}
    citations = await provider.grep(pattern, prefix, _vfs_context(context))
    return {"success": True, "pattern": pattern, "matches": [c.to_dict() for c in citations]}


@register_action(
    "documents.tree",
    description="Render a VFS directory as an indented tree (ls recursively, depth-limited).",
    parameters_schema=_DOCUMENTS_TREE_SCHEMA,
)
async def _documents_tree(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from core.knowledge_vfs_config import knowledge_vfs_enabled
    if not knowledge_vfs_enabled():
        return _vfs_disabled()
    _ensure_vfs_registered()
    from core.vfs_registry import resolve_provider
    path = (args.get("path") or "").strip()
    depth = max(1, min(int(args.get("depth", 2)), 6))
    provider = resolve_provider(path)
    if provider is None:
        return {"success": False, "error": "no_provider", "message": f"No VFS provider for path '{path}'"}
    lines: List[str] = []
    try:
        frontier = await provider.ls(path, _vfs_context(context))
    except Exception as e:
        logger.warning(f"documents.tree ls failed: {e}")
        frontier = []
    lines.append(path or "/")
    for _level in range(depth):
        if not frontier:
            break
        next_level: List[Any] = []
        for node in frontier:
            lines.append(f"  {'└─' if _level == 0 else '  '}{node.name}/" if node.type == "dir" else f"  {node.name}")
            if node.type == "dir":
                try:
                    next_level.extend(await provider.ls(node.path, _vfs_context(context)))
                except Exception:
                    pass
        frontier = next_level
    return {"success": True, "path": path, "tree": lines}


@register_action(
    "documents.head",
    description="Read the first N lines of a VFS leaf (for skimming large documents).",
    parameters_schema=_DOCUMENTS_HEAD_TAIL_SCHEMA,
)
async def _documents_head(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from core.knowledge_vfs_config import knowledge_vfs_enabled
    if not knowledge_vfs_enabled():
        return _vfs_disabled()
    _ensure_vfs_registered()
    from core.vfs_registry import resolve_provider
    path = (args.get("path") or "").strip()
    count = max(1, int(args.get("lines", 20)))
    provider = resolve_provider(path)
    if provider is None:
        return {"success": False, "error": "no_provider", "message": f"No VFS provider for path '{path}'"}
    res = await provider.cat(path, _vfs_context(context))
    return {"success": True, "path": res.path, "head": res.lines[:count], "line_count": len(res.lines)}


@register_action(
    "documents.tail",
    description="Read the last N lines of a VFS leaf (for skimming large documents).",
    parameters_schema=_DOCUMENTS_HEAD_TAIL_SCHEMA,
)
async def _documents_tail(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from core.knowledge_vfs_config import knowledge_vfs_enabled
    if not knowledge_vfs_enabled():
        return _vfs_disabled()
    _ensure_vfs_registered()
    from core.vfs_registry import resolve_provider
    path = (args.get("path") or "").strip()
    count = max(1, int(args.get("lines", 20)))
    provider = resolve_provider(path)
    if provider is None:
        return {"success": False, "error": "no_provider", "message": f"No VFS provider for path '{path}'"}
    res = await provider.cat(path, _vfs_context(context))
    return {"success": True, "path": res.path, "tail": res.lines[-count:], "line_count": len(res.lines)}


@register_action(
    "documents.scan",
    description="Recursively enumerate every file under a VFS directory (path + size).",
    parameters_schema=_DOCUMENTS_SCAN_SCHEMA,
)
async def _documents_scan(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from core.knowledge_vfs_config import knowledge_vfs_enabled
    if not knowledge_vfs_enabled():
        return _vfs_disabled()
    _ensure_vfs_registered()
    from core.vfs_registry import resolve_provider
    path = (args.get("path") or "").strip()
    max_depth = max(1, min(int(args.get("max_depth", 10)), 20))
    provider = resolve_provider(path)
    if provider is None:
        return {"success": False, "error": "no_provider", "message": f"No VFS provider for path '{path}'"}
    leaves = await provider.scan(path, _vfs_context(context), max_depth=max_depth)
    return {
        "success": True,
        "path": path,
        "files": [{"path": n.path, "size": n.size} for n in leaves],
        "file_count": len(leaves),
    }


@register_action(
    "documents.map",
    description="Bounded fan-out over VFS leaf paths: apply one op (cat/head/grep) per item. Complexity 3 / SUPERVISED-gated at the dispatch layer.",
    parameters_schema=_DOCUMENTS_MAP_SCHEMA,
)
async def _documents_map(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from core.knowledge_vfs_config import knowledge_vfs_enabled
    if not knowledge_vfs_enabled():
        return _vfs_disabled()
    _ensure_vfs_registered()
    from core.vfs_registry import resolve_provider
    paths = list(args.get("paths") or [])
    op = (args.get("op") or "").strip().lower()
    if not paths or op not in ("cat", "head", "grep"):
        return {"success": False, "error": "paths and op (cat|head|grep) are required"}
    max_items = max(1, min(int(args.get("max_items", 10)), 50))
    paths = paths[:max_items]
    ctx = _vfs_context(context)
    results: List[Dict[str, Any]] = []
    for p in paths:
        provider = resolve_provider(p)
        if provider is None:
            results.append({"path": p, "error": "no_provider"})
            continue
        try:
            if op == "grep":
                pattern = (args.get("pattern") or "").strip()
                if not pattern:
                    results.append({"path": p, "error": "pattern required for grep"})
                    continue
                hits = await provider.grep(pattern, p, ctx)
                results.append({"path": p, "matches": [c.to_dict() for c in hits]})
            else:
                res = await provider.cat(p, ctx)
                if op == "head":
                    n = max(1, int(args.get("lines", 20)))
                    results.append({"path": p, "lines": res.lines[:n]})
                else:
                    results.append({"path": p, "line_count": len(res.lines)})
        except Exception as e:
            logger.warning(f"documents.map item {p} failed: {e}")
            results.append({"path": p, "error": "item_failed"})
    return {"success": True, "op": op, "items_processed": len(results), "results": results}


@register_action(
    "documents.reduce",
    description="Aggregate a documents.map result list (count | concat | unique).",
    parameters_schema=_DOCUMENTS_REDUCE_SCHEMA,
)
async def _documents_reduce(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from core.knowledge_vfs_config import knowledge_vfs_enabled
    if not knowledge_vfs_enabled():
        return _vfs_disabled()
    items = list(args.get("items") or [])
    mode = (args.get("mode") or "").strip().lower()
    if not items or mode not in ("count", "concat", "unique"):
        return {"success": False, "error": "items and mode (count|concat|unique) are required"}
    if mode == "count":
        total_lines = 0
        match_count = 0
        for item in items:
            lines = item.get("lines")
            if lines is not None:
                total_lines += len(lines)
            elif item.get("line_count") is not None:
                total_lines += int(item.get("line_count", 0))
            if "matches" in item:
                match_count += len(item.get("matches", []))
        return {"success": True, "mode": "count", "total_lines": total_lines, "match_count": match_count}
    if mode == "concat":
        blobs: List[str] = []
        for item in items:
            blobs.extend(item.get("lines") or [])
        return {"success": True, "mode": "concat", "lines": blobs, "line_count": len(blobs)}
    seen: Dict[str, bool] = {}
    unique: List[str] = []
    for item in items:
        for m in item.get("matches") or []:
            key = m.get("path", "")
            if key and key not in seen:
                seen[key] = True
                unique.append(key)
    return {"success": True, "mode": "unique", "paths": unique, "unique_count": len(unique)}


@register_action(
    "documents.ask_image",
    description="Ask a vision-capable model about an image in the VFS (requires a provider with vision support).",
    parameters_schema=_DOCUMENTS_ASK_IMAGE_SCHEMA,
)
async def _documents_ask_image(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from core.knowledge_vfs_config import knowledge_vfs_enabled
    if not knowledge_vfs_enabled():
        return _vfs_disabled()
    _ensure_vfs_registered()
    from core.vfs_registry import resolve_provider
    path = (args.get("path") or "").strip()
    prompt = (args.get("prompt") or "").strip()
    if not path or not prompt:
        return {"success": False, "error": "path and prompt are required"}
    provider = resolve_provider(path)
    if provider is None:
        return {"success": False, "error": "no_provider", "message": f"No VFS provider for path '{path}'"}
    answer = await provider.ask_image(path, prompt, _vfs_context(context))
    return {"success": answer.get("success", False), "path": path, **answer}


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
    "canvas.list_versions",
    description=(
        "List the version history of a canvas, newest first (the append-only "
        "audit trail). Use this to review earlier drafts and pick the right "
        "version before reverting — the newest entry is flagged is_current."
    ),
    parameters_schema=_CANVAS_LIST_VERSIONS_SCHEMA,
)
async def _canvas_list_versions(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from tools.canvas_crud_tool import list_canvas_versions

    canvas_id = args.get("canvas_id")
    if not canvas_id:
        return {"success": False, "error": "canvas_id is required"}
    user_id = _context_user_id(context)
    if not user_id:
        return {"success": False, "error": "Authenticated user is required to list canvas versions"}
    return await list_canvas_versions(
        user_id,
        str(canvas_id),
        limit=int(args.get("limit") or 20),
        include_content=bool(args.get("include_content") or False),
    )


@register_action(
    "canvas.restore_version",
    description=(
        "Revert a canvas to an earlier version by its audit_id (from "
        "canvas.list_versions). The restore is appended as a new version — "
        "nothing is lost, the pre-restore state stays in history, so a "
        "mistaken revert is itself revertable."
    ),
    parameters_schema=_CANVAS_RESTORE_VERSION_SCHEMA,
)
async def _canvas_restore_version(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from tools.canvas_crud_tool import restore_canvas_version

    canvas_id = args.get("canvas_id")
    audit_id = args.get("audit_id")
    if not canvas_id or not audit_id:
        return {"success": False, "error": "canvas_id and audit_id are required"}
    user_id = _context_user_id(context)
    if not user_id:
        return {"success": False, "error": "Authenticated user is required to restore a canvas version"}
    return await restore_canvas_version(user_id, str(canvas_id), str(audit_id))


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


# ============================================================================
# Mini-app authoring harness (agent-driven coding).
# Agents create, author, test, publish, install, and run stateful mini-apps
# through these actions. Handlers live in tools/mini_app_tool and are imported
# lazily (seed-action pattern) so action_registry stays dependency-light.
# ============================================================================
_MINI_APP_SCAFFOLD_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Mini-app name"},
        "spec": {"type": "object", "description": "Optional spec (description, base_image, ...)"},
        "declared_scopes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Tool scopes the app may use (default canvas_render/canvas_get_state)",
        },
        "dependencies": {
            "type": "array",
            "items": {"type": "string"},
            "description": "PyPI dependencies baked into the per-app rootfs (e.g. ['pandas==2.2'])",
        },
    },
    "required": ["name"],
}

_MINI_APP_WRITE_LOGIC_SCHEMA = {
    "type": "object",
    "properties": {
        "app_id": {"type": "string", "description": "Mini-app id (from mini_app_scaffold)"},
        "source": {"type": "string", "description": "Python logic source (syntax-gated)"},
    },
    "required": ["app_id", "source"],
}

_MINI_APP_APP_ID_SCHEMA = {
    "type": "object",
    "properties": {
        "app_id": {"type": "string", "description": "Mini-app id"},
    },
    "required": ["app_id"],
}

_MINI_APP_DEV_RUN_SCHEMA = {
    "type": "object",
    "properties": {
        "app_id": {"type": "string", "description": "Mini-app id"},
        "inputs": {"type": "object", "description": "User inputs (injected as a global; state is auto-injected)"},
    },
    "required": ["app_id"],
}

_MINI_APP_RUN_SCHEMA = {
    "type": "object",
    "properties": {
        "canvas_id": {"type": "string", "description": "Installed instance canvas id"},
        "inputs": {"type": "object", "description": "User inputs (state is auto-injected)"},
    },
    "required": ["canvas_id"],
}

_MINI_APP_CANVAS_ID_SCHEMA = {
    "type": "object",
    "properties": {
        "canvas_id": {"type": "string", "description": "Mini-app instance canvas id"},
    },
    "required": ["canvas_id"],
}


@register_action(
    "mini_app_scaffold",
    description="Scaffold a stateful mini-app (draft): creates a source canvas + starter logic + manifest. Agent-driven authoring starts here.",
    parameters_schema=_MINI_APP_SCAFFOLD_SCHEMA,
)
async def _mini_app_scaffold(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from tools.mini_app_tool import mini_app_scaffold

    return await mini_app_scaffold(args, context)


@register_action(
    "mini_app_write_logic",
    description="Save the mini-app's Python logic (syntax-gated) to its blueprint canvas. The agent authors code here.",
    parameters_schema=_MINI_APP_WRITE_LOGIC_SCHEMA,
)
async def _mini_app_write_logic(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from tools.mini_app_tool import mini_app_write_logic

    return await mini_app_write_logic(args, context)


@register_action(
    "mini_app_dev_run",
    description="Dry-run the mini-app logic in the Firecracker microVM: returns resulting state + proposed storage ops without committing. Fail-closed when deps are unsafe or the per-app rootfs is not built.",
    parameters_schema=_MINI_APP_DEV_RUN_SCHEMA,
)
async def _mini_app_dev_run(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from tools.mini_app_tool import mini_app_dev_run

    return await mini_app_dev_run(args, context)


@register_action(
    "mini_app_publish",
    description="Publish a mini-app: fail-closed dep scan + rootfs check, snapshots initial_state + blueprint (credentials stripped). Required before install.",
    parameters_schema=_MINI_APP_APP_ID_SCHEMA,
)
async def _mini_app_publish(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from tools.mini_app_tool import mini_app_publish

    return await mini_app_publish(args, context)


@register_action(
    "mini_app_install",
    description="Install a published mini-app: hydrates a fresh, immutable instance canvas (copy-on-install).",
    parameters_schema=_MINI_APP_APP_ID_SCHEMA,
)
async def _mini_app_install(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from tools.mini_app_tool import mini_app_install

    return await mini_app_install(args, context)


@register_action(
    "mini_app_run",
    description="Run an installed mini-app instance statefully: reads CanvasState, executes logic in a Firecracker microVM, persists new state + storage ops, broadcasts a canvas:update.",
    parameters_schema=_MINI_APP_RUN_SCHEMA,
)
async def _mini_app_run(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from tools.mini_app_tool import mini_app_run

    return await mini_app_run(args, context)


@register_action(
    "mini_app_list",
    description="List mini-apps the requesting user owns (or public ones).",
    parameters_schema={"type": "object", "properties": {}, "required": []},
)
async def _mini_app_list(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from tools.mini_app_tool import mini_app_list

    return await mini_app_list(args, context)


@register_action(
    "mini_app_get_state",
    description="Read the current state + version of a mini-app instance canvas.",
    parameters_schema=_MINI_APP_CANVAS_ID_SCHEMA,
)
async def _mini_app_get_state(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from tools.mini_app_tool import mini_app_get_state

    return await mini_app_get_state(args, context)


_MINI_APP_DB_QUERY_SCHEMA = {
    "type": "object",
    "properties": {
        "canvas_id": {"type": "string", "description": "Mini-app instance canvas id"},
        "op": {"type": "string", "enum": ["query", "count", "get", "list_series"],
               "description": "Read operation (default: query)"},
        "series": {"type": "string", "description": "Series name (^[a-z0-9_]{1,64}$); omit for list_series"},
        "record_id": {"type": "string", "description": "Record id (for op=get)"},
        "filter": {"type": "object", "description": "Equality filter on data keys (scalar values)"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 10000, "default": 100},
        "order": {"type": "string", "enum": ["asc", "desc"], "default": "desc"},
    },
    "required": ["canvas_id"],
}


@register_action(
    "mini_app_db_query",
    description="Read structured records of a mini-app instance (query/count/get/list_series). INTERN+ tier. Owner-gated.",
    parameters_schema=_MINI_APP_DB_QUERY_SCHEMA,
)
async def _mini_app_db_query(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from tools.mini_app_tool import mini_app_db_query

    return await mini_app_db_query(args, context)


_MINI_APP_DB_WRITE_SCHEMA = {
    "type": "object",
    "properties": {
        "canvas_id": {"type": "string", "description": "Mini-app instance canvas id"},
        "op": {"type": "string",
               "enum": ["append", "update", "update_many", "delete", "delete_series", "clear"],
               "description": "Write operation"},
        "series": {"type": "string", "description": "Series name (^[a-z0-9_]{1,64}$); omit for clear"},
        "data": {"type": "object", "description": "Row payload (for append/update/update_many)"},
        "record_id": {"type": "string", "description": "Record id (for update/delete)"},
        "filter": {"type": "object", "description": "Equality filter (for update_many)"},
        "id": {"type": "string", "description": "Optional client-supplied record id (for append)"},
    },
    "required": ["canvas_id", "op"],
}


@register_action(
    "mini_app_db_write",
    description="Mutate structured records of a mini-app instance (append/update/update_many/delete/delete_series/clear). SUPERVISED+ tier. Owner-gated.",
    parameters_schema=_MINI_APP_DB_WRITE_SCHEMA,
)
async def _mini_app_db_write(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from tools.mini_app_tool import mini_app_db_write

    return await mini_app_db_write(args, context)


# ============================================================================
# Agent harness — acceptance tests, logic checkpoints, constraint probe.
# Research-backed additions to the authoring loop (generator-evaluator loop,
# clean-state recovery, constraint observability).
# ============================================================================
_MINI_APP_SET_TESTS_SCHEMA = {
    "type": "object",
    "properties": {
        "app_id": {"type": "string", "description": "Mini-app id"},
        "tests": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "initial_state": {"type": "object"},
                    "inputs": {"type": "object"},
                    "expect_state": {"type": "object"},
                    "expect_ops": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                },
            },
            "description": "Acceptance cases: {name?, initial_state?, inputs?, expect_state?, expect_ops?} — each must assert expect_state and/or expect_ops",
        },
    },
    "required": ["app_id", "tests"],
}

_MINI_APP_VERSION_SCHEMA = {
    "type": "object",
    "properties": {
        "app_id": {"type": "string", "description": "Mini-app id"},
        "version": {
            "type": "integer",
            "description": "Logic checkpoint version to revert to",
        },
    },
    "required": ["app_id", "version"],
}


@register_action(
    "mini_app_set_tests",
    description="Declare acceptance-test cases for a mini-app (stored in its manifest). Each case is {name?, initial_state?, inputs?, expect_state?, expect_ops?} — the harness runs every case and grades expected vs actual state so the agent can self-correct.",
    parameters_schema=_MINI_APP_SET_TESTS_SCHEMA,
)
async def _mini_app_set_tests(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from tools.mini_app_tool import mini_app_set_tests

    return await mini_app_set_tests(args, context)


@register_action(
    "mini_app_run_tests",
    description="Run a mini-app's acceptance tests in the Firecracker microVM (dry, no commit). Returns per-case pass/fail with expected-vs-actual state diffs and a pass count — the generator-evaluator feedback loop for agent self-correction.",
    parameters_schema=_MINI_APP_APP_ID_SCHEMA,
)
async def _mini_app_run_tests(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from tools.mini_app_tool import mini_app_run_tests

    return await mini_app_run_tests(args, context)


@register_action(
    "mini_app_logic_history",
    description="List a mini-app's logic checkpoints (oldest → newest). Every write_logic records a versioned snapshot; the agent can revert to a known-good version on failure.",
    parameters_schema=_MINI_APP_APP_ID_SCHEMA,
)
async def _mini_app_logic_history(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from tools.mini_app_tool import mini_app_logic_history

    return await mini_app_logic_history(args, context)


@register_action(
    "mini_app_revert_logic",
    description="Revert a mini-app's logic to a previously checkpointed version (clean-state recovery when a run/test fails).",
    parameters_schema=_MINI_APP_VERSION_SCHEMA,
)
async def _mini_app_revert_logic(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from tools.mini_app_tool import mini_app_revert_logic

    return await mini_app_revert_logic(args, context)


@register_action(
    "mini_app_status",
    description="Probe a mini-app's authoring constraints before iterating: logic syntax validity, effective scopes (viewer tier ∩ declared), dependency-scan state, per-app rootfs presence, and Firecracker runtime availability.",
    parameters_schema=_MINI_APP_APP_ID_SCHEMA,
)
async def _mini_app_status(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from tools.mini_app_tool import mini_app_status

    return await mini_app_status(args, context)


# ============================================================================
# Mini-app DB store — agent access to instance record data (read bridge +
# record CRUD). Read-only INTERN+, mutations SUPERVISED+ (tier floor enforced
# in the handlers). Same op vocabulary as the microVM record_ops envelope.
# ============================================================================
_MINI_APP_DB_QUERY_SCHEMA = {
    "type": "object",
    "properties": {
        "canvas_id": {"type": "string", "description": "Mini-app instance canvas id"},
        "op": {
            "type": "string",
            "enum": ["query", "count", "get", "list_series"],
            "description": "Read op (default query)",
        },
        "series": {"type": "string", "description": "Series name (^[a-z0-9_]{1,64}$)"},
        "filter": {"type": "object", "description": "Equality filter on record data"},
        "limit": {"type": "integer", "description": "Max rows (1..10000, default 100)"},
        "order": {"type": "string", "enum": ["asc", "desc"], "description": "Row order by seq"},
        "record_id": {"type": "string", "description": "Record id (op=get)"},
    },
    "required": ["canvas_id"],
}

_MINI_APP_DB_WRITE_SCHEMA = {
    "type": "object",
    "properties": {
        "canvas_id": {"type": "string", "description": "Mini-app instance canvas id"},
        "op": {
            "type": "string",
            "enum": ["append", "update", "update_many", "delete", "delete_series", "clear"],
            "description": "Mutation op",
        },
        "series": {"type": "string", "description": "Series name (^[a-z0-9_]{1,64}$)"},
        "data": {"type": "object", "description": "Record payload (append/update/update_many)"},
        "record_id": {"type": "string", "description": "Record id (update/delete)"},
        "id": {"type": "string", "description": "Optional client id for append"},
        "filter": {"type": "object", "description": "Equality filter (update_many)"},
    },
    "required": ["canvas_id", "op"],
}


@register_action(
    "mini_app_db_query",
    description="Read structured records of a mini-app instance (query/count/get/list_series). Owner-gated; INTERN+ tier floor. Same op vocabulary as the app's own record_ops.",
    parameters_schema=_MINI_APP_DB_QUERY_SCHEMA,
)
async def _mini_app_db_query(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from tools.mini_app_tool import mini_app_db_query

    return await mini_app_db_query(args, context)


@register_action(
    "mini_app_db_write",
    description="Mutate structured records of a mini-app instance (append/update/update_many/delete/delete_series/clear). Owner-gated; SUPERVISED+ tier floor.",
    parameters_schema=_MINI_APP_DB_WRITE_SCHEMA,
)
async def _mini_app_db_write(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from tools.mini_app_tool import mini_app_db_write

    return await mini_app_db_write(args, context)


# ============================================================================
# Shopify content actions (product listings + blogs/articles).
# Resolve the connected store from the workspace, then call ShopifyService.
# Enforcement (P2 capability scoping, P3 gatekeeper, P9 sandbox) is layered on
# top by the shared dispatch path — these are intentionally thin wrappers.
# ============================================================================

_SHOPIFY_PRODUCT_CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Product title"},
        "body_html": {"type": "string", "description": "Product description (HTML)"},
        "vendor": {"type": "string"},
        "product_type": {"type": "string"},
        "tags": {"type": "string", "description": "Comma-separated tags"},
        "handle": {"type": "string"},
        "status": {"type": "string", "enum": ["active", "draft", "archived"], "default": "active"},
        "variants": {"type": "array", "description": "List of variant objects e.g. [{title, price, sku, inventory_quantity}]"},
        "images": {"type": "array", "description": "List of image URLs or {src: 'https://...'} objects"},
    },
    "required": ["title"],
}

_SHOPIFY_BLOG_CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Blog title"},
        "handle": {"type": "string", "description": "Optional URL handle"},
    },
    "required": ["title"],
}

_SHOPIFY_ARTICLE_CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "blog_id": {"type": "string", "description": "Target blog id"},
        "title": {"type": "string", "description": "Article title"},
        "body_html": {"type": "string", "description": "Article body (HTML)"},
        "author": {"type": "string"},
        "tags": {"type": "string", "description": "Comma-separated tags"},
        "published": {"type": "boolean", "default": True},
    },
    "required": ["blog_id", "title", "body_html"],
}

_SHOPIFY_BLOGS_LIST_SCHEMA = {
    "type": "object",
    "properties": {},
}


def _resolve_shopify_store(context: Dict[str, Any]) -> tuple:
    """Resolve (access_token, shop_domain) for the workspace's connected store.

    Fail-closed: returns (None, None) when the workspace has no store — never
    falls back to another tenant's store, which would let one workspace read or
    mutate another tenant's storefront (P1 cross-tenant exposure).
    """
    try:
        from core.database import SessionLocal
        from core.models import EcommerceStore
        ws_id = (context or {}).get("workspace_id", "default")
        with SessionLocal() as db:
            store = db.query(EcommerceStore).filter(
                EcommerceStore.tenant_id == ws_id
            ).first()
            if not store or not store.access_token:
                return None, None
            return store.access_token, store.shop_domain
    except Exception as e:
        logger.warning(f"Failed to resolve Shopify store: {e}")
        return None, None


@register_action(
    "shopify_create_product",
    description="Create a product listing on the connected Shopify store (title, description, variants, images, tags).",
    parameters_schema=_SHOPIFY_PRODUCT_CREATE_SCHEMA,
)
async def _shopify_create_product(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    token, shop = _resolve_shopify_store(context)
    if not token:
        return {"success": False, "error": "no_shopify_store", "message": "No Shopify store connected to this workspace."}
    from integrations.shopify_service import ShopifyService
    product = await ShopifyService().create_product(token, shop, product=args)
    return {"success": True, "product": product}


@register_action(
    "shopify_list_blogs",
    description="List blogs on the connected Shopify store.",
    parameters_schema=_SHOPIFY_BLOGS_LIST_SCHEMA,
)
async def _shopify_list_blogs(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    token, shop = _resolve_shopify_store(context)
    if not token:
        return {"success": False, "error": "no_shopify_store", "message": "No Shopify store connected to this workspace."}
    from integrations.shopify_service import ShopifyService
    blogs = await ShopifyService().list_blogs(token, shop)
    return {"success": True, "blogs": blogs}


@register_action(
    "shopify_create_blog",
    description="Create a blog on the connected Shopify store to host articles/posts.",
    parameters_schema=_SHOPIFY_BLOG_CREATE_SCHEMA,
)
async def _shopify_create_blog(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    token, shop = _resolve_shopify_store(context)
    if not token:
        return {"success": False, "error": "no_shopify_store", "message": "No Shopify store connected to this workspace."}
    from integrations.shopify_service import ShopifyService
    blog = await ShopifyService().create_blog(token, shop, title=args["title"], handle=args.get("handle"))
    return {"success": True, "blog": blog}


@register_action(
    "shopify_create_article",
    description="Create/publish a blog article (post) on the connected Shopify store.",
    parameters_schema=_SHOPIFY_ARTICLE_CREATE_SCHEMA,
)
async def _shopify_create_article(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    token, shop = _resolve_shopify_store(context)
    if not token:
        return {"success": False, "error": "no_shopify_store", "message": "No Shopify store connected to this workspace."}
    from integrations.shopify_service import ShopifyService
    article = await ShopifyService().create_article(
        token, shop,
        blog_id=args["blog_id"],
        title=args["title"],
        body_html=args.get("body_html", ""),
        author=args.get("author"),
        tags=args.get("tags"),
        published=args.get("published", True),
    )
    return {"success": True, "article": article}



# ============================================================================
# Knowledge/goal/ontology actions — close the GraphRAG↔agent and goal↔agent
# seams (gaps B4/B7, A-agent-surface). Previously there were zero graph,
# knowledge, or goal actions: agents could not query the knowledge graph,
# create or evaluate goals, or inspect the ontology.
# ============================================================================

_GRAPH_QUERY_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Natural-language query over the knowledge graph"},
        "mode": {"type": "string", "enum": ["auto", "local", "global"],
                 "description": "local = entity-anchored traversal, global = community synthesis"},
    },
    "required": ["query"],
}


@register_action(
    "knowledge.query",
    description="Query the workspace knowledge graph (GraphRAG). Local mode returns "
                "entities/relationships around the query anchors; global mode synthesizes "
                "over community summaries.",
    parameters_schema=_GRAPH_QUERY_SCHEMA,
    effects=[{"effect": "read_only"}],
)
async def _knowledge_query(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from core.graphrag_engine import graphrag_engine
    result = await graphrag_engine.query(
        workspace_id=context.get("workspace_id"),
        query=str(args.get("query", "")),
        mode=str(args.get("mode", "auto")),
    )
    return {"success": not result.get("error"), "result": result}


_GOAL_CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "criteria": {
            "type": "array",
            "description": "Machine-checkable success criteria "
                "(graph_edge_exists, entity_exists, board_task_status, state_equals, "
                "numeric_compare, metric_gte, all_of, any_of, manual)",
            "items": {"type": "object"},
        },
        "key_results": {"type": "array", "items": {"type": "object"},
                        "description": "OKR key results [{description, metric, target}]"},
        "target_date": {"type": "string", "description": "ISO date"},
    },
    "required": ["title"],
}


@register_action(
    "goals.create",
    description="Create a persisted goal with machine-checkable success criteria. "
                "Use together with goals.evaluate; the goal_id can be passed as "
                "context.goal_id to make an agent run terminate when the goal is met.",
    parameters_schema=_GOAL_CREATE_SCHEMA,
    effects=[{"effect": "goal_created", "goal_id": "$args.title"}],
)
async def _goals_create(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from core.goals.goal_service import GoalService
    target = args.get("target_date")
    target_dt = None
    if target:
        from datetime import datetime
        target_dt = datetime.fromisoformat(str(target).replace("Z", "+00:00"))
    goal = GoalService(
        workspace_id=context.get("workspace_id", "default"),
        tenant_id=context.get("tenant_id", "default"),
    ).create_goal(
        title=str(args["title"]),
        description=str(args.get("description", "")),
        criteria=args.get("criteria") or [],
        key_results=args.get("key_results") or [],
        owner_id=context.get("user_id"),
        target_date=target_dt,
        source="agent",
    )
    return {"success": True, "goal": goal}


@register_action(
    "goals.evaluate",
    description="Evaluate a persisted goal's success criteria against the current "
                "graph/board/state; updates progress and status (achieved/at_risk).",
    parameters_schema={
        "type": "object",
        "properties": {"goal_id": {"type": "string"}},
        "required": ["goal_id"],
    },
    effects=[{"effect": "goal_evaluated", "goal_id": "$args.goal_id"}],
)
async def _goals_evaluate(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from core.goals.goal_service import GoalService
    result = GoalService(
        workspace_id=context.get("workspace_id", "default"),
        tenant_id=context.get("tenant_id", "default"),
    ).evaluate(str(args["goal_id"]))
    return {"success": "error" not in result, **result}


@register_action(
    "goals.decompose",
    description="HTN-decompose a goal into a dependency-validated subtask plan "
                "(reusable workflow-template methods; parallel execution groups included).",
    parameters_schema={
        "type": "object",
        "properties": {
            "goal": {"type": "string"},
            "template_id": {"type": "string", "description": "Optional specific method"},
        },
        "required": ["goal"],
    },
    effects=[{"effect": "plan_produced"}],
)
async def _goals_decompose(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from core.goals.htn_planner import HTNPlanner
    plan = HTNPlanner().decompose(str(args["goal"]), template_id=args.get("template_id"))
    return {"success": not plan.get("cycles"), "plan": plan}


@register_action(
    "ontology.inspect",
    description="Inspect the workspace ontology: entity types (with hierarchy), "
                "declared relations with domain/range, and undeclared relation types "
                "found in the graph (formalization candidates).",
    parameters_schema={"type": "object", "properties": {}, "required": []},
    effects=[{"effect": "read_only"}],
)
async def _ontology_inspect(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    from core.ontology import get_ontology_service
    onto = get_ontology_service(context.get("tenant_id", "default"))
    schema = onto.get_schema()
    return {
        "success": True,
        "entity_types": [
            {k: t[k] for k in ("slug", "parent_type", "aliases", "abstract", "fields")}
            for t in schema["entity_types"]
        ],
        "relations": [
            {k: r[k] for k in ("name", "domain", "range", "description")}
            for r in schema["relations"]
        ],
        "undeclared_relations_in_use": onto.undeclared_relations_in_use(
            context.get("workspace_id", "default")),
    }
