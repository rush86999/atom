"""BPE meta-actions registered in the shared action registry.

Exposes the four harness meta-actions — ``workspace.track``,
``workspace.commit``, ``workspace.recall``, ``workspace.note`` — through
``core.action_registry`` so both the agent MCP dispatch and the frontend RPC
route them like any other tool (plan Phase 1). Handlers are thin: state
lives in the per-scope :class:`~core.bpe.workspace.BPEWorkspace`.

Scope resolution: ``context['workspace_id']`` + ``context['agent_id']`` +
``context['session_id'] or context['execution_id']`` (execution scope when
no session is bound). Maturity-gated visibility is enforced upstream by
``GenericAgent._custom_action_visible`` — these actions ship enabled for
INTERN+ agents and behind ``ATOM_BPE_WORKSPACE_ENABLED`` (default off) for
shadow logging.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

from core.action_registry import register_action
from core.bpe.workspace import get_workspace

logger = logging.getLogger(__name__)


def bpe_enabled() -> bool:
    """Flag gate (Switchyard convention: off → shadow-log only, prompt unchanged)."""
    return os.getenv("ATOM_BPE_WORKSPACE_ENABLED", "false").strip().lower() in (
        "1", "true", "yes",
    )


def _scope_from_context(context: Dict[str, Any]) -> Dict[str, str]:
    workspace_id = str(context.get("workspace_id") or "default")
    agent_id = str(context.get("agent_id") or "atom_main")
    scope_key = str(
        context.get("session_id") or context.get("execution_id") or ""
    )
    return {"workspace_id": workspace_id, "agent_id": agent_id, "scope_key": scope_key}


def _resolve_workspace(context: Dict[str, Any]):
    scope = _scope_from_context(context)
    ws = get_workspace(scope["workspace_id"], scope["agent_id"], scope["scope_key"])
    # Late-bind the belief adapter (avoid import cycles at module load).
    if ws.adapter is None:
        try:
            from core.bpe.chat_adapter import ChatBeliefAdapter

            ws.adapter = ChatBeliefAdapter()
        except Exception:
            from core.bpe.adapter import NullAdapter

            ws.adapter = NullAdapter()
    return ws, scope


_COMMON_SCHEMA = {
    "type": "object",
    "properties": {},
    "required": [],
}


@register_action(
    "workspace.track",
    description="Read the workspace Belief state — task-relevant facts about "
                "entities, their states and relations. Pass a topic (entity "
                "name) or 'world' for a compact global summary. Cheap to "
                "consult; still consumes a step.",
    parameters_schema={
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "Entity/topic to inspect, or 'world'"},
        },
        "required": [],
    },
)
async def _bpe_track(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    ws, _scope = _resolve_workspace(context)
    return await ws.apply("track", args.get("topic") or "world", context)


@register_action(
    "workspace.commit",
    description="Commit execution state to workspace Progress: add a subgoal "
                "(no status) or update an existing subgoal's status "
                "(pending|in_progress|done|blocked). Keeps the plan external "
                "and bounded (max 8 subgoals).",
    parameters_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Subgoal title (or prefix to match)"},
            "status": {"type": "string", "description": "pending|in_progress|done|blocked (omit to add new)"},
        },
        "required": ["title"],
    },
)
async def _bpe_commit(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    ws, _scope = _resolve_workspace(context)
    payload = {"title": args.get("title") or "", "status": args.get("status")}
    return await ws.apply("commit", payload)


@register_action(
    "workspace.recall",
    description="Recall reusable Experience — past skills, procedures, common "
                "mistakes, and search priors matching a query. Query modes: "
                "how-to procedures, mistakes to avoid, entity facts.",
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to recall (procedures / mistakes / facts)"},
        },
        "required": ["query"],
    },
)
async def _bpe_recall(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    ws, _scope = _resolve_workspace(context)
    return await ws.apply("recall", args.get("query") or "")


@register_action(
    "workspace.note",
    description="Buffer an insight for later consolidation into long-term "
                "Experience (does NOT answer anything now). Use to record a "
                "lesson, failure mode, or discovered fact worth remembering.",
    parameters_schema={
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "The insight to note"},
        },
        "required": ["content"],
    },
)
async def _bpe_note(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    ws, _scope = _resolve_workspace(context)
    return await ws.apply("note", args.get("content") or "")
