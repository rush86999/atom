"""
Agent-callable memory tools — let the agent explicitly remember or forget a
durable fact mid-turn.

These are the agent-facing counterparts to the passive per-turn extraction
layer (turn_fact_extractor.py). Where extraction is fire-and-forget and
automatic, these tools let the agent honor direct user requests like
"remember that we use Stripe" or "forget the old launch date".

Governance:
  - memory_remember: complexity 2 (INTERN+) — storing knowledge is moderate risk
  - memory_forget:   complexity 3 (SUPERVISED+) — destroying knowledge is high risk

Both delegate to core.turn_fact_extractor helpers and never raise.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.turn_fact_categories import ALL_FACT_CATEGORIES
from core.turn_fact_extractor import (
    forget_fact_explicit,
    remember_fact_explicit,
)

logger = logging.getLogger(__name__)


async def memory_remember(
    fact_text: str,
    category: str,
    domain: str = "general",
    confidence: float = 0.95,
    workspace_id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    tenant_id: str = "default",
    **kwargs,
) -> Dict[str, Any]:
    """
    Explicitly store a durable fact that should survive across sessions.

    Use when the user says "remember this", "note this down", "don't forget",
    or when you observe a durable constraint/value/preference you'll need later.

    Args:
        fact_text: The fact as a self-contained sentence (no pronouns).
        category: One of: exact_value, hard_constraint, decision_reason,
                  cross_task_dep, implicit_pref.
        domain: Knowledge domain (finance, hr, operations, general, ...).
        confidence: 0.0–1.0 (default 0.95 — explicit remembers are high-trust).
        workspace_id: Workspace scope (resolved from agent context if omitted).
        user_id, session_id, execution_id: Provenance for audit.

    Returns:
        {"success": bool, "fact_id": str | None, "message": str}
    """
    ws = workspace_id or kwargs.get("agent_workspace") or "default"

    if category not in ALL_FACT_CATEGORIES:
        return {
            "success": False,
            "fact_id": None,
            "message": (
                f"Invalid category '{category}'. Must be one of: "
                f"{', '.join(ALL_FACT_CATEGORIES)}"
            ),
        }
    if not fact_text or not fact_text.strip():
        return {"success": False, "fact_id": None, "message": "fact_text is required"}

    row = remember_fact_explicit(
        workspace_id=ws,
        fact_text=fact_text,
        category=category,
        domain=domain,
        confidence=confidence,
        user_id=user_id,
        session_id=session_id,
        execution_id=execution_id,
        tenant_id=tenant_id,
    )
    if row is None:
        return {
            "success": False,
            "fact_id": None,
            "message": "Could not persist fact (dedup collision or store error).",
        }
    return {
        "success": True,
        "fact_id": row.id,
        "message": f"Remembered [{category}]: {row.fact_text}",
        "category": row.category,
        "confidence": row.confidence,
    }


async def memory_forget(
    fact_id: Optional[str] = None,
    fact_text_contains: Optional[str] = None,
    workspace_id: Optional[str] = None,
    tenant_id: str = "default",
    **kwargs,
) -> Dict[str, Any]:
    """
    Remove (invalidate) a durable fact. Soft-delete — audit history preserved.

    Provide EITHER fact_id (exact, preferred) OR fact_text_contains (substring
    match scoped to the workspace). If neither is given, returns success=false —
    the agent cannot wipe the whole workspace on a vague request (deletion safety).

    Args:
        fact_id: Exact ID of the fact to forget (preferred — precise).
        fact_text_contains: Substring to match; all active facts in the workspace
                            containing this text are invalidated.

    Returns:
        {"success": bool, "invalidated_count": int, "message": str}
    """
    ws = workspace_id or kwargs.get("agent_workspace") or "default"

    if not fact_id and not fact_text_contains:
        return {
            "success": False,
            "invalidated_count": 0,
            "message": (
                "Provide fact_id (preferred) or fact_text_contains. "
                "Refusing to forget without a specific target."
            ),
        }

    count = forget_fact_explicit(
        workspace_id=ws,
        fact_id=fact_id,
        fact_text_contains=fact_text_contains,
        tenant_id=tenant_id,
    )
    if count == 0:
        return {
            "success": False,
            "invalidated_count": 0,
            "message": "No matching active facts found.",
        }
    return {
        "success": True,
        "invalidated_count": count,
        "message": f"Forgot {count} fact(s).",
    }


def register_memory_tool(tool_registry=None):
    """Register memory_remember + memory_forget with the tool registry."""
    from tools.registry import get_tool_registry

    if tool_registry is None:
        tool_registry = get_tool_registry()

    tool_registry.register(
        name="memory_remember",
        function=memory_remember,
        version="1.0.0",
        description=(
            "Explicitly store a durable fact that should survive across sessions. "
            "Use when the user says 'remember this' or you observe a durable "
            "constraint/value/preference. Categories: "
            + ", ".join(ALL_FACT_CATEGORIES) + "."
        ),
        category="memory",
        complexity=2,
        maturity_required="INTERN",
        parameters={
            "fact_text": "string (required) — the fact as a self-contained sentence",
            "category": f"string (required) — one of: {', '.join(ALL_FACT_CATEGORIES)}",
            "domain": "string (optional) — finance, hr, operations, general, ...",
            "confidence": "float (optional, default 0.95)",
        },
        tags=["memory", "knowledge", "remember", "persist", "durable"],
    )

    tool_registry.register(
        name="memory_forget",
        function=memory_forget,
        version="1.0.0",
        description=(
            "Remove (invalidate) a durable fact. Provide fact_id (preferred) or "
            "fact_text_contains (substring). Refuses to forget without a specific "
            "target — deletion safety."
        ),
        category="memory",
        complexity=3,
        maturity_required="SUPERVISED",
        parameters={
            "fact_id": "string (optional, preferred) — exact fact ID to forget",
            "fact_text_contains": "string (optional) — substring match within workspace",
        },
        tags=["memory", "knowledge", "forget", "delete", "invalidate"],
    )

    logger.info("memory_remember + memory_forget registered with ToolRegistry")
