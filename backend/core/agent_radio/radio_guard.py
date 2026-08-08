"""Attention + cost governance for the Agent Radio layer.

Implements the paper's bottleneck #1 — "attention governance and verification":
passive awareness makes communication *available*; it does not decide which
discovery deserves an interruption, who should receive it, or whether the
evidence is strong enough to revise a plan. All policies here are
deterministic and fail-safe.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.agent_radio import radio_config
from core.models import AgentThread, LateralMessage

# A mention is only ever surfaced to the explicitly listed recipient(s).
# Broadcast (`mentions=[]` with no recipient) is rejected at the service layer.


def check_send_policy(
    thread: AgentThread,
    from_agent_id: str,
    mention_agent_ids: Optional[List[str]],
    to_agent_id: Optional[str],
    content: str,
) -> Optional[str]:
    """Return a policy violation message, or None if the send is allowed.

    Policies (deterministic):
    - mention-first: at least one recipient (mention or ``to_agent_id``).
    - no self-mention-only sends.
    - content non-empty and size-bounded.
    - sender is a member (service-level check duplicated here for guard tests).
    """
    mentions = [m for m in (mention_agent_ids or []) if m and m != from_agent_id]
    if to_agent_id and to_agent_id != from_agent_id:
        mentions = list(dict.fromkeys([to_agent_id] + mentions))
    if not mentions:
        return "radio.send_message requires at least one @mention recipient (mention-first; no broadcast)."
    if not content or not content.strip():
        return "radio.send_message requires non-empty content."
    if len(content) > 8000:
        return "radio.send_message content exceeds the 8000-char limit."
    if thread is None or thread.status != "open":
        return "Radio thread not found or closed."
    roster = thread.member_agent_ids or []
    if from_agent_id not in roster and thread.created_by_agent_id != from_agent_id:
        return "Sender is not a member of this radio thread."
    return None


def budget_allows_send(thread: AgentThread, cost_usd: float = 0.0) -> bool:
    """Per-thread cumulative message budget (cost governance)."""
    if not thread:
        return False
    used = 0.0
    meta: Dict[str, Any] = thread.metadata_json or {}
    try:
        used = float(meta.get("used_budget_usd", 0.0))
    except (TypeError, ValueError):
        used = 0.0
    return bool(used + max(0.0, cost_usd) <= radio_config.team_budget_usd())


def inbox_pending_messages(
    messages: List[LateralMessage],
    agent_id: str,
    *,
    now_iso: Optional[str] = None,
) -> List[LateralMessage]:
    """Filter a message list down to unread mentions for ``agent_id``.

    Pure-function form of the service query (used by tests and by the loop
    hook's cap logic).
    """
    del now_iso
    cap = radio_config.inbox_cap()
    pending = [
        m
        for m in messages
        if agent_id in (m.mentions or [])
        and agent_id not in ((m.metadata_json or {}).get("read_by", []) or [])
    ]
    return pending[:cap] if len(pending) > cap else pending


def interrupt_worth_it(message: LateralMessage, agent_id: str) -> bool:
    """Should this message interrupt the receiving agent's current plan?

    Deterministic heuristics: the message must mention the agent and carry
    actionable evidence (non-empty content). High-priority metadata and a
    prior mention-response pair (`correlation_id`-style metadata) raise
    interrupt worthiness. Kept conservative: noise must not derail a valid
    path (paper: communication can distract).
    """
    if agent_id not in (message.mentions or []):
        return False
    if not (message.content or "").strip():
        return False
    meta = message.metadata_json or {}
    if meta.get("priority") in ("high", "urgent"):
        return True
    # A message that answers an outstanding question (response marker) is
    # worth interrupting for; anything else surfaces in the next drain.
    return bool(meta.get("is_response"))
