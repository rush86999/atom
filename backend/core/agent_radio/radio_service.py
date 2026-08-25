"""DB source of truth for the Agent Radio lateral messaging layer.

Operates on the dedicated ``agent_threads`` / ``lateral_messages`` tables
(models.py:1856/:1905). These are intentionally separate from
``agent_messages`` (live board-comment storage — never reuse it).

Delivery model is mention-first and per-recipient: a message lists the agents
it @mentions (``mentions`` JSON); each recipient's read state is tracked in
``metadata_json["read_by"]``. A message is ``delivered`` once every mentioned
recipient has read it.
"""

from __future__ import annotations

import logging
import math
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.agent_radio import radio_config
from core.models import AgentThread, LateralMessage

logger = logging.getLogger(__name__)


class RadioError(Exception):
    """Base error for the radio layer (generic, non-identifying message)."""


class RadioAccessError(RadioError):
    """Caller is not a member of the thread (or thread missing/closed)."""


class RadioPolicyError(RadioError):
    """Message violates attention governance (mention-first policy)."""


class RadioBudgetExceeded(RadioError):
    """Thread's cumulative message budget is exhausted (or unreadable)."""


class RadioBudgetCorrupted(RadioError):
    """Thread budget metadata is unreadable — enforcement fails CLOSED."""


# In-process serialization of the budget check->update critical section. The
# DB-level ``with_for_update`` row lock closes the race on PostgreSQL; SQLite
# ignores it, so this lock guarantees atomic accounting on the embedded store.
_RADIO_BUDGET_LOCK = threading.Lock()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_thread(
    db: Session,
    name: str,
    created_by_agent_id: str,
    member_agent_ids: List[str],
    *,
    chain_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> AgentThread:
    """Create a lateral coordination thread (one per recruited team)."""
    roster = list(dict.fromkeys(member_agent_ids))
    if created_by_agent_id not in roster:
        roster.insert(0, created_by_agent_id)
    meta = dict(metadata_json or {})
    meta.setdefault("used_budget_usd", 0.0)
    thread = AgentThread(
        name=name,
        created_by_agent_id=created_by_agent_id,
        member_agent_ids=roster,
        chain_id=chain_id,
        tenant_id=tenant_id,
        status="open",
        metadata_json=meta,
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    logger.info(f"radio: thread {thread.id} created by {created_by_agent_id}")
    return thread


def is_member(thread: AgentThread, agent_id: str) -> bool:
    if not agent_id:
        return False
    roster = thread.member_agent_ids or []
    return agent_id in roster or thread.created_by_agent_id == agent_id


def thread_budget_used_usd(thread: AgentThread) -> float:
    """Read the thread's used budget.

    Fail-CLOSED: corrupted/unreadable ``used_budget_usd`` metadata raises
    ``RadioBudgetCorrupted`` instead of silently returning 0.0 — returning
    0.0 would let an agent mint unlimited budget by corrupting its own
    thread metadata.
    """
    meta = thread.metadata_json or {}
    raw = meta.get("used_budget_usd", 0.0)
    try:
        used = float(raw)
    except (TypeError, ValueError):
        raise RadioBudgetCorrupted(
            "Radio thread budget metadata is corrupted; refusing to send."
        )
    if not math.isfinite(used) or used < 0.0:
        raise RadioBudgetCorrupted(
            "Radio thread budget metadata is corrupted; refusing to send."
        )
    return used


def send_message(
    db: Session,
    *,
    thread_id: str,
    from_agent_id: str,
    content: str,
    mention_agent_ids: Optional[List[str]] = None,
    to_agent_id: Optional[str] = None,
    cost_usd: float = 0.0,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> LateralMessage:
    """Persist a directed message on a thread.

    Mention-first: at least one explicit mention is required unless a single
    ``to_agent_id`` recipient is given. The sender must be a thread member and
    the thread must be open. Enforcement of the per-thread budget lives here
    so every dispatch path (registry action, fleet, tests) is governed.
    """
    mentions = [m for m in (mention_agent_ids or []) if m and m != from_agent_id]
    if to_agent_id and to_agent_id != from_agent_id:
        mentions = list(dict.fromkeys([to_agent_id] + mentions))
    if not mentions:
        raise RadioPolicyError(
            "radio.send_message requires at least one @mention recipient "
            "(mention-first; no broadcast)."
        )

    # Fast-fail outside the lock: thread existence/open/membership. The
    # authoritative check happens again under the budget lock so a concurrent
    # close cannot race past it.
    thread = db.query(AgentThread).filter(AgentThread.id == thread_id).first()
    if thread is None or thread.status != "open":
        raise RadioAccessError("Radio thread not found or closed.")
    if not is_member(thread, from_agent_id):
        raise RadioAccessError("Sender is not a member of this radio thread.")

    cost = cost_usd if isinstance(cost_usd, (int, float)) and math.isfinite(cost_usd) else 0.0
    cost = max(0.0, cost)

    # Atomic budget accounting: check + increment under the in-process lock,
    # re-reading the thread with FOR UPDATE so PostgreSQL serializes
    # concurrent sends on the same thread (SQLite: lock covers it).
    # populate_existing() is required — the fast-fail read above may already
    # have loaded this thread into the session identity map with a stale
    # budget; without a forced re-select the race would not actually close.
    with _RADIO_BUDGET_LOCK:
        thread = (
            db.query(AgentThread)
            .filter(AgentThread.id == thread_id)
            .with_for_update()
            .populate_existing()
            .first()
        )
        if thread is None or thread.status != "open":
            raise RadioAccessError("Radio thread not found or closed.")
        if not is_member(thread, from_agent_id):
            raise RadioAccessError("Sender is not a member of this radio thread.")

        try:
            used = thread_budget_used_usd(thread)
        except RadioBudgetCorrupted:
            # Fail closed: an unreadable budget must reject, never spend.
            raise RadioBudgetExceeded(
                "Radio thread budget metadata is corrupted; refusing to send."
            )
        if used + cost > radio_config.team_budget_usd():
            raise RadioBudgetExceeded("Radio thread message budget exhausted.")

        meta = dict(metadata_json or {})
        meta["read_by"] = []
        message = LateralMessage(
            thread_id=thread.id,
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            content=content,
            mentions=mentions,
            delivered=False,
            metadata_json=meta,
        )
        db.add(message)

        if cost > 0.0:
            thread_meta = dict(thread.metadata_json or {})
            thread_meta["used_budget_usd"] = round(used + cost, 6)
            thread.metadata_json = thread_meta

        db.commit()
    db.refresh(message)
    logger.info(f"radio: {from_agent_id} -> {mentions} on {thread_id}")

    # P0 org telemetry (write-only; never raises) — social-contact edges for
    # the radio→recruitment conflict-of-interest report.
    try:
        from core.org_telemetry_service import emit_org_event

        for recipient in mentions or ([to_agent_id] if to_agent_id else []):
            emit_org_event(
                db,
                "radio_message",
                actor_agent_id=from_agent_id,
                target_agent_id=recipient,
                chain_id=thread_id,
                payload={"message_id": message.id},
            )
    except Exception as e:  # noqa: BLE001 — telemetry must never raise
        logger.debug(f"org telemetry message emit skipped: {e}")
    return message


def get_thread(db: Session, thread_id: str) -> Optional[AgentThread]:
    return db.query(AgentThread).filter(AgentThread.id == thread_id).first()


def _read_by(message: LateralMessage) -> List[str]:
    meta = message.metadata_json or {}
    return list(meta.get("read_by", []) or [])


def mark_read(db: Session, message: LateralMessage, agent_id: str) -> None:
    """Record that ``agent_id`` consumed the message (per-recipient delivery)."""
    if agent_id in _read_by(message):
        return
    meta = dict(message.metadata_json or {})
    meta["read_by"] = _read_by(message) + [agent_id]
    message.metadata_json = meta
    mentions = message.mentions or []
    if mentions and set(_read_by(message)) >= set(mentions):
        message.delivered = True
    db.commit()


def get_pending_mentions(
    db: Session,
    thread_id: str,
    agent_id: str,
    *,
    limit: Optional[int] = None,
) -> List[LateralMessage]:
    """Non-blocking inbox: undelivered messages mentioning ``agent_id``.

    Filters out self-messages and stale backlog (per ``radio_config``). The
    result is ordered oldest-first. Callers must ``mark_read`` each message
    once surfaced.
    """
    if not agent_id:
        return []
    cutoff = _utcnow() - timedelta(minutes=radio_config.backlog_ttl_minutes())
    messages = (
        db.query(LateralMessage)
        .filter(
            LateralMessage.thread_id == thread_id,
            LateralMessage.from_agent_id != agent_id,
            LateralMessage.created_at >= cutoff,
        )
        .order_by(LateralMessage.created_at.asc())
        .all()
    )
    pending = [
        m
        for m in messages
        if agent_id in (m.mentions or []) and agent_id not in _read_by(m)
    ]
    if limit is not None and len(pending) > limit:
        pending = pending[:limit]
    return pending


def get_thread_snapshot(
    db: Session,
    thread_id: str,
    agent_id: str,
    *,
    limit: int = 20,
) -> Dict[str, Any]:
    """Full thread snapshot for instant context (AgentRadio contract).

    Includes thread metadata, the most recent ``limit`` messages, and the
    caller's unread mention count.
    """
    thread = get_thread(db, thread_id)
    if thread is None:
        return {"thread_id": thread_id, "found": False, "messages": []}
    messages = (
        db.query(LateralMessage)
        .filter(LateralMessage.thread_id == thread_id)
        .order_by(LateralMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    messages = list(reversed(messages))
    unread = len(
        [
            m
            for m in messages
            if agent_id in (m.mentions or []) and agent_id not in _read_by(m)
        ]
    )
    try:
        budget_used = thread_budget_used_usd(thread)
    except RadioBudgetCorrupted:
        budget_used = None  # display-only: never substitutes for enforcement
    return {
        "thread_id": thread.id,
        "name": thread.name,
        "status": thread.status,
        "member_agent_ids": thread.member_agent_ids or [],
        "messages": [
            {
                "id": m.id,
                "from_agent_id": m.from_agent_id,
                "to_agent_id": m.to_agent_id,
                "content": m.content,
                "mentions": m.mentions or [],
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
        "unread_mentions": unread,
        "budget_used_usd": budget_used,
        "found": True,
    }


def close_thread(db: Session, thread_id: str) -> Optional[AgentThread]:
    thread = get_thread(db, thread_id)
    if thread is None:
        return None
    thread.status = "closed"
    db.commit()
    db.refresh(thread)
    return thread


def inbox_drain_text(
    agent_id: str,
    thread_id: Optional[str] = None,
    *,
    max_items: Optional[int] = None,
) -> str:
    """Passive-awareness hook body: returns `[RADIO INBOX]` context lines.

    Opens a short-lived session (never raises). If ``thread_id`` is omitted,
    the most recent open thread the agent belongs to is used. Messages are
    marked read once surfaced so each mention reaches the agent once.
    """
    if not radio_config.radio_enabled() or not agent_id:
        return ""
    try:
        from core.database import get_db_session

        with get_db_session() as db:
            if thread_id is None:
                threads = (
                    db.query(AgentThread)
                    .filter(
                        AgentThread.status == "open",
                        AgentThread.created_at
                        >= _utcnow()
                        - timedelta(minutes=radio_config.backlog_ttl_minutes()),
                    )
                    .order_by(AgentThread.created_at.desc())
                    .limit(10)
                    .all()
                )
                thread_id = next(
                    (
                        t.id
                        for t in threads
                        if agent_id in (t.member_agent_ids or [])
                    ),
                    None,
                )
            if thread_id is None:
                return ""
            pending = get_pending_mentions(
                db,
                thread_id,
                agent_id,
                limit=max_items or radio_config.inbox_cap(),
            )
            if not pending:
                return ""
            lines = [f"[RADIO INBOX] {len(pending)} new mention(s) on thread {thread_id}:"]
            for m in pending:
                lines.append(
                    f"- @{m.from_agent_id}: {m.content[:400]}"
                )
                mark_read(db, m, agent_id)
            lines.append("Respond via radio.send_message if the team expects an answer.")
            return "\n".join(lines) + "\n"
    except Exception as e:  # pragma: no cover - defensive; drain must never break the loop
        logger.debug(f"radio inbox drain failed: {e}")
        return ""
