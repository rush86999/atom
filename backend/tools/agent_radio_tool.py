"""Thin tool-surface for the Agent Radio layer.

Handler implementations live in ``core/agent_radio/radio_actions.py``
(the Unified Action Registry path — RPC + capability + sandbox gating all
flow through ``integrations/mcp_service.call_tool``). This module exists so
the ReAct loops' ToolRegistry listings carry the governance metadata
(maturity_required) for the four ``radio.*`` tools, and re-exports the
handlers for direct/test use.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from core.agent_radio.radio_actions import (
    radio_create_thread,
    radio_read_inbox,
    radio_send_message,
    radio_wait_for_mention,
)

logger = logging.getLogger(__name__)

RADIO_TOOL_NAMES = [
    "radio.create_thread",
    "radio.send_message",
    "radio.wait_for_mention",
    "radio.read_inbox",
]

Handler = Any  # async (args, context) -> dict, action-registry compatible


def register_agent_radio_tools(tool_registry=None) -> None:
    """Register radio.* tools with the ToolRegistry (ReAct loop listings)."""
    from tools.registry import get_tool_registry

    if tool_registry is None:
        tool_registry = get_tool_registry()

    tool_registry.register(
        name="radio.create_thread",
        function=radio_create_thread,
        version="1.0.0",
        description=(
            "Open a lateral coordination thread shared by a team of agents. "
            "Use when a task has responsibility breakpoints (legacy system, "
            "cross-service incident, migration, security analysis) and the "
            "team needs to share mid-task discoveries in real time. "
            "INTERN+ tier floor."
        ),
        category="coordination",
        complexity=2,
        maturity_required="INTERN",
        parameters={
            "name": "string (optional) — human-readable thread name",
            "member_agent_ids": "list[string] (required) — agents on the thread",
        },
        tags=["radio", "coordination", "thread", "multi-agent"],
    )

    tool_registry.register(
        name="radio.send_message",
        function=radio_send_message,
        version="1.0.0",
        description=(
            "Send a directed @mention message on a radio thread (mention-first; "
            "no broadcast). Recipients absorb it at their next work step "
            "without interruption. INTERN+ tier floor."
        ),
        category="coordination",
        complexity=2,
        maturity_required="INTERN",
        parameters={
            "thread_id": "string (required) — the thread to post on",
            "content": "string (required) — the message body (≤8000 chars)",
            "mention_agent_ids": "list[string] (required) — recipient agent ids",
            "priority": "string (optional) — normal | high | urgent",
        },
        tags=["radio", "coordination", "mention", "message"],
    )

    tool_registry.register(
        name="radio.wait_for_mention",
        function=radio_wait_for_mention,
        version="1.0.0",
        description=(
            "Block (bounded, ≤30s) until a mention for this agent arrives on "
            "the thread, or return a timeout note. Only use when your current "
            "step genuinely depends on a peer's answer; otherwise rely on the "
            "passive inbox drain. STUDENT+ read-only."
        ),
        category="coordination",
        complexity=1,
        maturity_required="STUDENT",
        parameters={
            "thread_id": "string (required) — the thread to listen on",
            "timeout": "integer (optional, ≤30) — seconds to wait",
        },
        tags=["radio", "coordination", "wait", "mention"],
    )

    tool_registry.register(
        name="radio.read_inbox",
        function=radio_read_inbox,
        version="1.0.0",
        description=(
            "Non-blocking read of pending mentions and the thread snapshot "
            "(instant context, like a worklog). STUDENT+ read-only."
        ),
        category="coordination",
        complexity=1,
        maturity_required="STUDENT",
        parameters={
            "thread_id": "string (optional) — target thread; omitting reads "
            "your latest thread's inbox",
        },
        tags=["radio", "coordination", "inbox", "read"],
    )

    logger.info("radio.* tools registered with ToolRegistry")