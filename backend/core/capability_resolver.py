"""
Agent Capability Resolver — P2 (Cloudflare OS G2, tool-level).

Resolves an agent's allowed tool set as the intersection of its declared
``AgentRegistry.capabilities`` with its tier floor
(``TIER_FLOOR_TOOL_WHITELISTS``). Enforced at the dispatch layer
(``integrations/mcp_service.call_tool``) so ALL callers — agent loop, workflow
engine, meta-agent, fleet — are gated identically. This closes the gap that
``generic_agent.py:249`` is an agent-loop-only check, bypassed by the other
dispatch paths.

Backward-compatible: ``capabilities = []``, ``["*"]``, or ``None`` (the column
default) resolves to ``("*",)`` — no restriction, preserving current behavior
for every existing agent.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Optional, Tuple

from core.sandbox_policy import TIER_FLOOR_TOOL_WHITELISTS

logger = logging.getLogger(__name__)

# Sentinel for "no restriction" — matches the AUTONOMOUS tier floor convention.
UNRESTRICTED: Tuple[str, ...] = ("*",)


def _normalize_capabilities(caps: Any) -> Tuple[str, ...]:
    """Coerce the capabilities column value into a tuple of tool names.

    Empty / None / ['*'] -> UNRESTRICTED. Otherwise a deduped tuple of names.
    """
    if not caps:
        return UNRESTRICTED
    if isinstance(caps, str):
        caps = [caps]
    try:
        caps_list = [str(c).strip() for c in caps if str(c).strip()]
    except TypeError:
        return UNRESTRICTED
    if not caps_list or "*" in caps_list:
        return UNRESTRICTED
    # Dedupe, preserve order.
    seen = set()
    out = []
    for c in caps_list:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return tuple(out)


def _tier_floor(tier: Optional[str]) -> Tuple[str, ...]:
    """Return the tier floor, falling back to 'student' for unknown tiers.

    A tier floor is the MAXIMUM tool surface a tier may ever access; an agent's
    declared capabilities can only narrow this, never widen it.
    """
    t = (tier or "student").strip().lower()
    return TIER_FLOOR_TOOL_WHITELISTS.get(t, TIER_FLOOR_TOOL_WHITELISTS["student"])


def resolve_allowed_tools(agent: Any, tier: Optional[str] = None) -> Tuple[str, ...]:
    """Resolve the allowed tool set for an agent at a given tier.

    Args:
        agent: an AgentRegistry row (or any object with a ``capabilities``
            attribute). ``capabilities`` is a JSON list of tool names, or
            empty/``['*']`` for unrestricted.
        tier: the agent's maturity tier (student/intern/supervised/autonomous).
            Case-insensitive. Defaults to the agent's ``status`` if omitted,
            else 'student'.

    Returns:
        A tuple of allowed tool names. ``("*",)`` means unrestricted (bounded
        only by the sandbox layer in P9). Otherwise the agent's declared
        capabilities intersected with its tier floor.
    """
    caps = _normalize_capabilities(getattr(agent, "capabilities", None))

    # Resolve tier: explicit arg > agent.status > student.
    if tier is None:
        status = getattr(agent, "status", None)
        tier = status or "student"
    floor = _tier_floor(tier)

    # AUTONOMOUS floor is ('*',) — accept the agent's declared set verbatim
    # (still narrowed to what they declared, if they declared anything).
    if floor == UNRESTRICTED:
        return caps if caps != UNRESTRICTED else UNRESTRICTED

    # Unrestricted capabilities -> bounded by the tier floor.
    if caps == UNRESTRICTED:
        return floor

    # Otherwise intersect: an agent may never exceed its tier floor.
    floor_set = set(floor)
    return tuple(c for c in caps if c in floor_set)


def is_tool_allowed(allowed: Tuple[str, ...], tool_name: str) -> bool:
    """Check whether ``tool_name`` is permitted under a resolved ``allowed`` set.

    ``("*",)`` permits anything. Otherwise membership is checked exactly.
    Dotted names are permitted ONLY when they are actually registered
    action-registry actions (e.g. 'documents.search'): those are application-
    level actions layered ABOVE the tool whitelist and governed by the
    action_registry + gatekeeper (P3), not the tool floor. Unregistered dotted
    names (e.g. tools exposed by a malicious external MCP server) must not slip
    past the whitelist. An empty ``allowed`` set resolves to deny-all: it only
    arises from an empty tier-floor intersection and must never widen to
    unrestricted.
    """
    if not isinstance(tool_name, str):
        return False
    if allowed == UNRESTRICTED:
        return True
    if tool_name in allowed:
        return True
    if "." in tool_name:
        try:
            from core.action_registry import action_registry

            return action_registry.get_action(tool_name) is not None
        except Exception:
            return False
    return False


def get_agent_for_context(context: Optional[Dict[str, Any]]) -> Optional[Any]:
    """Look up the AgentRegistry row referenced by a dispatch context.

    Returns ``None`` when the context carries no ``agent_id`` or the agent
    can't be loaded (e.g. no DB). ``None`` means "unresolved -> unrestricted",
    preserving backward compatibility for callers that don't pass an agent.
    """
    if not context:
        return None
    agent_id = context.get("agent_id")
    if not agent_id:
        return None
    try:
        from core.database import get_db_session
        from core.models import AgentRegistry

        with get_db_session() as db:
            return db.query(AgentRegistry).filter(AgentRegistry.id == str(agent_id)).first()
    except Exception as e:
        logger.debug("capability_resolver could not load agent %s: %s", agent_id, e)
        return None
