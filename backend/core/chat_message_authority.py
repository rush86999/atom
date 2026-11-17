"""Durable chat-message actor/session authority.

The chat orchestrator is a module-level singleton constructed with the
Personal-Edition default scope (``ChatOrchestrator()``). That construction
scope is right for background/direct writers that declare it explicitly, but
it must never be the source of the tenant on a row written for an
authenticated user: two users served by the same singleton previously had
every persisted ``ChatMessage`` stamped ``tenant_id='default'``.

This module is a thin seam over the mechanisms that already exist:

* ``core.goal_run_decision_service._resolve_actor`` — the shared fresh-actor
  resolver. It re-reads the CURRENT active ``User`` row and returns the
  effective Personal-Edition scope (NULL tenant/workspace -> ``default``,
  see ``core.personal_scope``). Missing, inactive, status-changed or
  unreadable users fail closed; there is no context-scope fallback.
* ``core.goal_run_decision_service.claim_fresh_reviewer`` — the shared
  conditional no-op ``UPDATE`` that fences the exact actor snapshot in the
  SAME transaction as the write (the established atomics used by checkpoint
  decisions, canvas authority and goal-run decisions).
* The owned ``ChatSession`` row — a session's durable owner is part of the
  write authority. A message may only be appended when the session still
  belongs to the acting user (or is a legacy placeholder before the shared
  reclaim path has rebound it).

It adds only those chat-session binding checks; there is no second policy
registry, no new table and no per-request mutation of the orchestrator's
construction scope.

Scope rules (fail closed):

* session owner + durable owner must agree, unless the durable owner is the
  legacy placeholder class that the existing read path may reclaim;
* an owner-named session whose user cannot be resolved/activated is refused —
  never silently re-scoped to ``default`` or another user;
* the actor and the session row are re-verified in the caller's write
  transaction, so a deactivation, tenant move or ownership change that lands
  while the turn awaits the model is refused rather than written under stale
  authority;
* only identities that are explicitly declared legacy/global (the placeholder
  class, the external-platform system identity, or a direct caller that
  supplies no actor at all) keep the existing declared construction scope.
"""
from __future__ import annotations

import contextvars
import logging
from typing import Any, Dict, Optional

from sqlalchemy import update

logger = logging.getLogger(__name__)

#: The admitted principal pinned for the CURRENT turn (raw id, never a scope
#: fallback). Kept separate from ``core.request_scope`` because that dict is
#: splatted into LLM dispatch calls (``**_llm_scope``) whose signatures own
#: their own keyword contract; the durable-write identity has no business
#: travelling there. A contextvar (not an orchestrator attribute) is what
#: keeps two concurrent users served by the shared singleton from bleeding.
_WRITE_ACTOR: contextvars.ContextVar = contextvars.ContextVar(
    "atom_chat_write_actor", default=None)


def pin_chat_write_actor(user_id: Any):
    """Publish the admitted principal id for this turn's durable writes.

    Returns the ContextVar token; the caller MUST reset it when the turn
    ends. Fire-and-forget work spawned during the turn copies the context
    and keeps the pin for its own lifetime (it serves the same turn).
    """
    return _WRITE_ACTOR.set(str(user_id) if user_id else None)


def reset_chat_write_actor(token) -> None:
    """Restore the previous pin (turn exit). Safe on a stale token."""
    if token is not None:
        _WRITE_ACTOR.reset(token)


#: Owner ids that no real authenticated principal can be. Kept as the shared
#: chat-session reclamation class: the read paths may durably re-point one of
#: these at the caller (``integrations.chat_routes._ensure_session_access``).
#: Moved here from ``integrations.chat_routes`` so the write path and the read
#: path use the same definition.
LEGACY_PLACEHOLDER_USER_IDS = frozenset({
    "", "default", "default_user", "anonymous", "anonymous_sales_user", "guest",
    "user", "test_user", "test_user_context", "test_user_agent", "test_user_e2e",
    "test_user_001", "test-user", "test-user-id", "unit_test_user",
    # Greptile PR #583 follow-up: sessions persisted with the all-zero (nil)
    # UUID owner are ownerless ghosts — no real user id can ever equal it, so
    # without this entry they load at startup and stay permanently unclaimable.
    "00000000-0000-0000-0000-000000000000",
})

#: Identities that are not local users at all (external platform senders).
#: Their durable session scope is the writer's declared construction scope —
#: the existing contract for the universal webhook bridge. Deliberately NOT
#: part of the reclamation class above: a local authenticated caller must not
#: be able to claim an external-platform conversation through the read paths.
SYSTEM_SCOPE_USER_IDS = frozenset({"external_agent_user"})


def is_legacy_placeholder_owner(owner: Optional[str]) -> bool:
    return (
        owner is None
        or not str(owner).strip()
        or str(owner) in LEGACY_PLACEHOLDER_USER_IDS
    )


def is_system_scope_identity(owner: Optional[str]) -> bool:
    return bool(owner) and str(owner) in SYSTEM_SCOPE_USER_IDS


def _pinned_request_user_id() -> Optional[str]:
    """The authenticated principal pinned on this turn's write context."""
    try:
        value = _WRITE_ACTOR.get()
        return str(value) if value else None
    except Exception:  # noqa: BLE001 — absent pin is not an authority read
        return None


def _durable_owner(db: Any, session_id: str) -> Optional[str]:
    """The owner recorded on the durable ChatSession row, if readable.

    Only a real ORM row with a string owner is authoritative. A missing row
    is not an owner (session-row creation is owned by
    ``_get_or_create_session``/``_ensure_session_row``); an unreadable row is
    handled by the caller's fail-closed wrapper.
    """
    from core.models import ChatSession

    row = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id)
        .first()
    )
    if not isinstance(row, ChatSession):
        return None
    owner = row.user_id
    return str(owner) if isinstance(owner, str) and owner.strip() else None


def _refusal(http_status: int, code: str, message: str) -> Dict[str, Any]:
    return {
        "ok": False,
        "http_status": int(http_status),
        "error_code": str(code),
        "message": str(message),
    }


def resolve_chat_message_scope(db: Any, session: Any) -> Dict[str, Any]:
    """Resolve the exact durable actor + owned session for this chat write.

    Must be called inside the caller's write transaction (the actor and the
    session row are fenced there before any append). Returns a dict with
    ``ok`` plus, on success, ``user_id``/``tenant_id``/``workspace_id`` and
    ``scope_source`` (``actor``, ``legacy_system`` or ``legacy_unscoped``).
    ``tenant_id`` is ``None`` only for the legacy/global sources; the caller
    uses the writer's declared construction scope for those, exactly as the
    background/direct writers already do.
    """
    from core.goal_run_decision_service import (
        _resolve_actor,
        claim_fresh_reviewer,
    )

    session = session if isinstance(session, dict) else {}
    session_id = str(session.get("id") or "").strip()
    raw_session_owner = session.get("user_id")
    session_owner = (
        str(raw_session_owner)
        if isinstance(raw_session_owner, str) and raw_session_owner.strip()
        else None
    )
    pinned = _pinned_request_user_id()

    try:
        durable_owner = _durable_owner(db, session_id) if session_id else None
    except Exception as exc:  # noqa: BLE001 — unreadable is not permission
        logger.warning(
            "chat message authority: session %s owner unreadable (%s)",
            session_id, type(exc).__name__)
        return _refusal(
            503, "CHAT_SESSION_AUTHORITY_UNAVAILABLE",
            "The conversation's owner could not be verified")

    # ---- choose the identity that must own this append -------------------
    actor_id: Optional[str] = None
    if session_owner and not is_legacy_placeholder_owner(session_owner):
        if (
            durable_owner
            and durable_owner != session_owner
            and not is_legacy_placeholder_owner(durable_owner)
        ):
            logger.warning(
                "chat message authority: session %s is durably owned by "
                "another user; append refused", session_id)
            return _refusal(
                403, "CHAT_SESSION_FOREIGN",
                "This conversation belongs to another user")
        actor_id = session_owner
    elif durable_owner and not is_legacy_placeholder_owner(durable_owner):
        # The in-memory projection is a legacy placeholder but the durable
        # row knows the real owner. That owner is authority.
        actor_id = durable_owner
    elif pinned:
        actor_id = pinned
    elif session_owner:
        actor_id = session_owner

    if actor_id and pinned and actor_id != pinned:
        # The request was admitted as one principal but points at a session
        # bound to another. Never merge them.
        if is_legacy_placeholder_owner(actor_id):
            # A legacy-undetermined session being claimed by the admitted
            # caller: the caller's own scope governs the new append (the
            # established reclamation contract). A system-owned session is
            # NOT reclaimable here — a local principal must never take over
            # an external-platform conversation.
            actor_id = pinned
        else:
            logger.warning(
                "chat message authority: admitted principal and session "
                "owner disagree for session %s; append refused", session_id)
            return _refusal(
                403, "CHAT_ACTOR_SESSION_MISMATCH",
                "This conversation is not bound to the acting user")

    legacy_global = False
    actor: Dict[str, Any] = {}
    if is_legacy_placeholder_owner(actor_id) or is_system_scope_identity(
            actor_id):
        legacy_global = True
    elif actor_id:
        actor = _resolve_actor(db, actor_id)
        if not actor.get("ok"):
            logger.warning(
                "chat message authority: actor %s refused (%s) for session "
                "%s; append refused", actor_id,
                actor.get("error_code") or actor.get("http_status"),
                session_id)
            return {
                **actor,
                "error_code": str(
                    actor.get("error_code") or "CHAT_ACTOR_REFUSED"),
                "message": str(
                    actor.get("message")
                    or "The acting user could not be verified"),
            }
        # Fence the exact actor snapshot in THIS transaction. A peer
        # deactivation, tenant/workspace move or role change between the
        # request's admission and this append misses and refuses.
        if not claim_fresh_reviewer(db, actor):
            logger.warning(
                "chat message authority: actor %s changed during the turn "
                "for session %s; append refused", actor_id, session_id)
            return _refusal(
                409, "CHAT_ACTOR_CHANGED",
                "The acting user's authority changed during this turn")
    else:
        # A direct/background caller supplied no actor at all. There is no
        # request scope to honour; the writer's declared construction scope
        # is the existing contract for that class (never an authenticated
        # user's fallback).
        legacy_global = True

    # ---- fence the durable session owner as observed ---------------------
    if session_id and durable_owner is not None:
        from core.models import ChatSession

        try:
            frozen = db.execute(
                update(ChatSession)
                .where(
                    ChatSession.id == session_id,
                    ChatSession.user_id == durable_owner,
                )
                .values(updated_at=ChatSession.updated_at)
            )
        except Exception as exc:  # noqa: BLE001 — unreadable is not permission
            logger.warning(
                "chat message authority: session %s claim failed (%s)",
                session_id, type(exc).__name__)
            return _refusal(
                503, "CHAT_SESSION_AUTHORITY_UNAVAILABLE",
                "The conversation's owner could not be verified")
        if frozen.rowcount != 1:
            logger.warning(
                "chat message authority: session %s owner changed during "
                "the turn; append refused", session_id)
            return _refusal(
                409, "CHAT_SESSION_CHANGED",
                "The conversation's owner changed during this turn")

    if legacy_global:
        return {
            "ok": True,
            "user_id": actor_id,
            "tenant_id": None,
            "workspace_id": None,
            "scope_source": (
                "legacy_system" if actor_id else "legacy_unscoped"),
            "durable_session_owner": durable_owner,
        }
    return {
        "ok": True,
        "user_id": actor["id"],
        "tenant_id": actor["tenant_id"],
        "workspace_id": actor["workspace_id"],
        "scope_source": "actor",
        "durable_session_owner": durable_owner,
    }
