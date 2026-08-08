"""The three AgentRadio primitives as Unified-Action-Registry actions.

Registered via ``@register_action`` so the RPC surface
(``POST /api/rpc/radio.*``), the P2 capability gate, and the P9 sandbox gate
all apply automatically through ``integrations/mcp_service.call_tool`` — the
radio layer never runs on a parallel, ungoverned dispatch path.

Primitives (spec: docs/architecture/AGENT_RADIO.md §Protocol):

- ``radio.create_thread`` — INTERN+ (additive, reversible: a thread costs no
  external effect until someone sends on it).
- ``radio.send_message``  — INTERN+ (memory-adjacent: persists a fact-like row
  with full provenance; mention-first, no broadcast).
- ``radio.wait_for_mention`` — STUDENT+ (read-only; the only blocking radio
  op, agent-initiated and hard-capped at ``ATOM_RADIO_WAIT_TIMEOUT_SECONDS``).

Maturity floors are enforced in-handler (``_require_tier``) mirroring
``tools/mini_app_tool.py:623`` — the ActionDefinition itself carries no tier
metadata, so the floor is checked at the top of each handler.

Identity: the calling agent is read from the dispatch ``context["agent_id"]``
(see ``integrations/mcp_service.py:1036``). If absent (e.g. a raw RPC call with
no agent), the action returns ``success: False`` with a clear reason rather
than impersonating a sender.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.action_registry import register_action
from core.agent_radio import radio_config, radio_service, radio_server
from core.agent_radio.radio_service import (
    RadioAccessError,
    RadioBudgetExceeded,
    RadioError,
    RadioPolicyError,
)

logger = logging.getLogger(__name__)

# Mirrors tools/mini_app_tool.py:_TIER_RANK (kept local so this module has no
# dependency on a tool module for a 4-entry map).
_TIER_RANK = {"student": 0, "intern": 1, "supervised": 2, "autonomous": 3}


def _context_tier(context: Dict[str, Any]) -> str:
    """Operating agent's maturity tier (fail-closed → 'student')."""
    tier = (context or {}).get("tier")
    return str(tier or "student").lower()


def _require_tier(context: Dict[str, Any], minimum: str) -> Optional[str]:
    """Return an error string when the agent's tier is below ``minimum``."""
    if _TIER_RANK.get(_context_tier(context), 0) < _TIER_RANK.get(minimum, 0):
        return f"Requires {minimum.upper()}+ maturity tier"
    return None


def _context_agent_id(context: Dict[str, Any]) -> Optional[str]:
    """The calling agent's id (context['agent_id']; see mcp_service.call_tool)."""
    return (context or {}).get("agent_id")


def _disabled_note() -> Dict[str, Any]:
    """Kill-switch response: graceful, never an exception."""
    return {
        "success": False,
        "error": "radio_disabled",
        "message": (
            "AgentRadio is disabled (ATOM_RADIO_ENABLED=false). "
            "Set the flag to true to enable lateral coordination."
        ),
    }


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #

_CREATE_THREAD_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Human-readable thread name."},
        "member_agent_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Agent ids on the team (the creator is added automatically).",
        },
        "scope_hint": {
            "type": "string",
            "description": "fleet | task | manual (metadata only; default manual).",
        },
    },
    "required": ["name", "member_agent_ids"],
}

_SEND_MESSAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "thread_id": {"type": "string"},
        "content": {"type": "string", "description": "Message body."},
        "mention_agent_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Agents to @mention. At least one is REQUIRED (mention-first).",
        },
        "to_agent_id": {
            "type": "string",
            "description": "Optional single direct recipient (counts as a mention).",
        },
        "requires_response": {
            "type": "boolean",
            "description": "Mark this message as needing a reply (interrupt-worthy).",
        },
    },
    "required": ["thread_id", "content"],
}

_WAIT_FOR_MENTION_SCHEMA = {
    "type": "object",
    "properties": {
        "thread_id": {"type": "string"},
        "timeout": {
            "type": "integer",
            "description": "Max seconds to block (hard-capped by config; default 30).",
        },
    },
    "required": ["thread_id"],
}

_READ_INBOX_SCHEMA = {
    "type": "object",
    "properties": {
        "thread_id": {
            "type": "string",
            "description": "Optional — omitting reads your latest thread's inbox.",
        },
    },
}


# --------------------------------------------------------------------------- #
# Actions
# --------------------------------------------------------------------------- #

@register_action(
    "radio.create_thread",
    description=(
        "Create a lateral (peer-to-peer) coordination thread for a team of "
        "agents. Members exchange directed @mentions to self-organize. "
        "Additive + reversible: a thread has no effect until someone sends on it."
    ),
    parameters_schema=_CREATE_THREAD_SCHEMA,
)
async def radio_create_thread(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    if not radio_config.radio_enabled():
        return _disabled_note()
    tier_err = _require_tier(context, "intern")
    if tier_err:
        return {"success": False, "error": tier_err}
    agent_id = _context_agent_id(context)
    if not agent_id:
        return {"success": False, "error": "Context agent_id is required to create a thread."}

    name = (args.get("name") or "").strip()
    members: List[str] = [m for m in (args.get("member_agent_ids") or []) if m]
    if not name:
        return {"success": False, "error": "name is required"}
    if not members:
        return {"success": False, "error": "member_agent_ids must list at least one other agent"}

    scope_hint = (args.get("scope_hint") or "manual").strip()
    tenant_id = (context or {}).get("tenant_id")
    try:
        from core.database import get_db_session

        with get_db_session() as db:
            thread = radio_service.create_thread(
                db,
                name=name,
                created_by_agent_id=agent_id,
                member_agent_ids=members,
                tenant_id=tenant_id,
                metadata_json={"scope": scope_hint},
            )
            return {
                "success": True,
                "thread_id": thread.id,
                "name": thread.name,
                "member_agent_ids": thread.member_agent_ids or [],
                "message": f"Thread '{thread.name}' created with {len(thread.member_agent_ids or [])} member(s).",
            }
    except RadioError as e:
        return {"success": False, "error": "radio_error", "message": str(e)}
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"radio.create_thread failed: {e}")
        return {"success": False, "error": "internal_error", "message": "Could not create thread."}


@register_action(
    "radio.send_message",
    description=(
        "Send a directed @mention message on a radio thread. Mention-first: "
        "at least one recipient (mention_agent_ids or to_agent_id) is REQUIRED. "
        "There is no broadcast — the legacy global feed is a separate channel."
    ),
    parameters_schema=_SEND_MESSAGE_SCHEMA,
)
async def radio_send_message(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    if not radio_config.radio_enabled():
        return _disabled_note()
    tier_err = _require_tier(context, "intern")
    if tier_err:
        return {"success": False, "error": tier_err}
    agent_id = _context_agent_id(context)
    if not agent_id:
        return {"success": False, "error": "Context agent_id is required to send a message."}

    thread_id = (args.get("thread_id") or "").strip()
    content = args.get("content")
    mentions = [m for m in (args.get("mention_agent_ids") or []) if m]
    to_agent_id = args.get("to_agent_id")
    requires_response = bool(args.get("requires_response"))
    if not thread_id:
        return {"success": False, "error": "thread_id is required"}

    meta: Dict[str, Any] = {}
    if requires_response:
        meta["is_response"] = False  # this msg *requests* a response → interrupt-worthy
        meta["priority"] = "high"

    try:
        from core.database import get_db_session

        with get_db_session() as db:
            message = radio_service.send_message(
                db,
                thread_id=thread_id,
                from_agent_id=agent_id,
                content=content,
                mention_agent_ids=mentions,
                to_agent_id=to_agent_id,
                metadata_json=meta or None,
            )
        # Fire-and-forget wakeup for any mentioned agent currently blocking.
        await radio_server.get_radio_server().publish(message)
        return {
            "success": True,
            "message_id": message.id,
            "thread_id": message.thread_id,
            "mentions": message.mentions or [],
            "message": "Message sent.",
        }
    except RadioPolicyError as e:
        return {"success": False, "error": "policy_error", "message": str(e)}
    except RadioAccessError as e:
        return {"success": False, "error": "access_error", "message": str(e)}
    except RadioBudgetExceeded as e:
        return {"success": False, "error": "budget_exceeded", "message": str(e)}
    except RadioError as e:
        return {"success": False, "error": "radio_error", "message": str(e)}
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"radio.send_message failed: {e}")
        return {"success": False, "error": "internal_error", "message": "Could not send message."}


@register_action(
    "radio.wait_for_mention",
    description=(
        "Block the calling agent until a teammate @mentions it on the thread, "
        "or timeout. Agent-initiated and hard-capped (default 30s). NOTE: the "
        "default listener is a non-blocking inbox drain at the top of each step "
        "— agents keep working and absorb mentions passively. Use this only "
        "when the agent deliberately must have an answer before proceeding."
    ),
    parameters_schema=_WAIT_FOR_MENTION_SCHEMA,
)
async def radio_wait_for_mention(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    if not radio_config.radio_enabled():
        return _disabled_note()
    # Read-only block; STUDENT+ floor.
    tier_err = _require_tier(context, "student")
    if tier_err:
        return {"success": False, "error": tier_err}
    agent_id = _context_agent_id(context)
    if not agent_id:
        return {"success": False, "error": "Context agent_id is required to wait."}

    thread_id = (args.get("thread_id") or "").strip()
    if not thread_id:
        return {"success": False, "error": "thread_id is required"}
    timeout = args.get("timeout")
    try:
        timeout_int = int(timeout) if timeout is not None else None
    except (TypeError, ValueError):
        timeout_int = None

    try:
        from core.database import get_db_session

        with get_db_session() as db:
            message = await radio_server.get_radio_server().wait_for_mention(
                thread_id=thread_id,
                agent_id=agent_id,
                timeout=timeout_int,
                db=db,
            )
        if message is None:
            return {
                "success": True,
                "timed_out": True,
                "message": "No mention arrived within the timeout; resume your work.",
            }
        return {
            "success": True,
            "timed_out": False,
            "message_id": message.id,
            "from_agent_id": message.from_agent_id,
            "content": message.content,
            "mentions": message.mentions or [],
            "created_at": message.created_at.isoformat() if message.created_at else None,
        }
    except Exception as e:  # pragma: no cover - defensive; a wait must never raise
        logger.warning(f"radio.wait_for_mention failed: {e}")
        return {"success": False, "error": "internal_error", "message": "Wait failed; resume your work."}


@register_action(
    "radio.read_inbox",
    description=(
        "Non-blocking read of pending mentions + full thread snapshot (instant "
        "context, like a worklog). STUDENT+ read-only."
    ),
    parameters_schema=_READ_INBOX_SCHEMA,
)
async def radio_read_inbox(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    if not radio_config.radio_enabled():
        return _disabled_note()
    tier_err = _require_tier(context, "student")
    if tier_err:
        return {"success": False, "error": tier_err}
    agent_id = _context_agent_id(context)
    if not agent_id:
        return {"success": False, "error": "Context agent_id is required to read the inbox."}

    thread_id = (args.get("thread_id") or "").strip()
    try:
        from core.database import get_db_session

        with get_db_session() as db:
            if thread_id:
                snapshot = radio_service.get_thread_snapshot(db, thread_id, agent_id)
                return {"success": True, **snapshot}
            inbox = radio_service.inbox_drain_text(agent_id, max_items=5)
            return {"success": True, "found": bool(inbox), "inbox": inbox.strip()}
    except Exception as e:  # pragma: no cover - defensive; reads never raise
        logger.warning(f"radio.read_inbox failed: {e}")
        return {"success": False, "error": "internal_error", "message": "Could not read inbox."}


def register_all() -> None:
    """Ensure all four radio actions are registered (startup/test hook).

    The ``@register_action`` decorators run at import time; this exists as an
    explicit wiring point and sanity check.
    """
    from core.action_registry import action_registry

    for name in (
        "radio.create_thread",
        "radio.send_message",
        "radio.wait_for_mention",
        "radio.read_inbox",
    ):
        if action_registry.get_action(name) is None:  # pragma: no cover - defensive
            logger.error(f"radio action {name} did not register")
    logger.debug("radio actions registered: create_thread, send_message, wait_for_mention, read_inbox")
