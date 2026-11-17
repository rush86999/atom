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

Admission snapshot (2026-11-17 follow-up)
-----------------------------------------

A write-time fresh read alone is not enough: it proves the actor is active
NOW, not that the principal admitted at the start of the turn is still the
same scope. A real counter demonstrated a turn admitted as UserA in
tenant/workspace A that waited on the model while the SAME user row moved to
legitimate tenant/workspace B; the write-time read saw B, the fence agreed
with B, and the transcript was silently re-scoped to B while the keyed
transport record still said A (so the durable rows and the transport
disagreed).

``pin_chat_write_actor`` therefore captures the admitted actor + scope in the
turn's context BEFORE any awaited work (the LLM/dispatch scope contextvar is
left untouched: its dict is splatted into provider call signatures). The
write-time resolver compares the fresh actor with THAT admission snapshot and
refuses the append when the tenant, workspace, role or status changed during
the turn. A snapshot that could not be read at admission (authority outage,
inactive account) fails closed at write time rather than being invented or
silently downgraded to the construction scope.

Scope rules (fail closed):

* session owner + durable owner must agree, unless the durable owner is the
  legacy placeholder class that the existing read path may reclaim — and a
  reclaim is only appended to after the durable row is fenced/re-owned in
  the write transaction itself (an in-memory label alone is never authority);
* an owner-named session whose user cannot be resolved/activated is refused —
  never silently re-scoped to ``default`` or another user;
* an admitted local actor whose current tenant/workspace/role/status differs
  from the admission snapshot is refused, even though the fresh row is
  itself self-consistent;
* an identity that was never a local user at admission (the external
  platform bridge's ``external_agent_user`` / ``ext_<sender>`` senders) stays
  a declared external writer with the writer's construction scope. It can
  never be used by a local caller to adopt an external conversation, and an
  external identity that became a local user during the turn is refused;
* only identities that are explicitly declared legacy/global (the placeholder
  class, an external system identity, or a direct caller that supplies no
  actor at all) keep the existing declared construction scope.
"""
from __future__ import annotations

import contextvars
import logging
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import update

logger = logging.getLogger(__name__)

#: The admitted actor + scope snapshot for the CURRENT turn. Kept separate
#: from ``core.request_scope`` because that dict is splatted into LLM dispatch
#: calls (``**_llm_scope``) whose signatures own their own keyword contract;
#: the durable-write identity has no business travelling there. A contextvar
#: (not an orchestrator attribute) is what keeps two concurrent users served
#: by the shared singleton from bleeding.
_ADMISSION: contextvars.ContextVar = contextvars.ContextVar(
    "atom_chat_write_admission", default=None)

#: Admission record states.
_ADMISSION_ACTOR = "actor"          # resolved local User snapshot
_ADMISSION_DECLARED = "declared"    # non-local (external bridge) identity
_ADMISSION_UNAVAILABLE = "unavailable"  # authority read failed: fail closed
_ADMISSION_NONE = "none"            # no actor supplied

#: Fields that constitute the admitted authority. A change to any of them
#: between admission and the durable append refuses the append. Resolved
#: tenant/workspace are compared canonically so the documented Personal
#: NULL -> "default" equivalence is not a false scope change.
_AUTHORITY_FIELDS = ("status", "role", "tenant_id", "workspace_id")

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


def _actor_snapshot(actor: Dict[str, Any]) -> Dict[str, str]:
    """The comparable authority snapshot of a resolved actor."""
    from core.goal_run_decision_service import canonical_scope_id

    return {
        "id": str(actor.get("id") or ""),
        "status": str(actor.get("status") or ""),
        "role": str(actor.get("role") or ""),
        "tenant_id": canonical_scope_id(actor.get("tenant_id")),
        "workspace_id": canonical_scope_id(actor.get("workspace_id")),
    }


def pin_chat_write_actor(user_id: Any):
    """Capture the admitted actor + scope for this turn's durable writes.

    Called at turn entry, BEFORE session load or any awaited model work. The
    resolved snapshot is what the write transaction compares against; a pin
    that could not be read is recorded as unavailable so the write refuses
    instead of inventing a scope.

    Returns the ContextVar token; the caller MUST reset it when the turn
    ends. Fire-and-forget work spawned during the turn copies the context
    and keeps the pin for its own lifetime (it serves the same turn).
    """
    raw_user_id = str(user_id).strip() if user_id else ""
    if not raw_user_id:
        return _ADMISSION.set({
            "state": _ADMISSION_NONE,
            "user_id": None,
        })

    record: Dict[str, Any]
    try:
        from core.database import get_db_session
        from core.goal_run_decision_service import _resolve_actor

        with get_db_session() as db:
            actor = _resolve_actor(db, raw_user_id)
    except Exception as exc:  # noqa: BLE001 — admission authority is required
        logger.warning(
            "chat message authority: admission snapshot unavailable for %s "
            "(%s)", raw_user_id, type(exc).__name__)
        record = {
            "state": _ADMISSION_UNAVAILABLE,
            "user_id": raw_user_id,
            "error_code": "AUTHORITY_UNAVAILABLE",
        }
    else:
        if actor.get("ok"):
            record = {
                "state": _ADMISSION_ACTOR,
                "user_id": str(actor.get("id") or raw_user_id),
                "snapshot": _actor_snapshot(actor),
            }
        elif str(actor.get("error_code") or "") == "UNAUTHENTICATED":
            # No local User row: this is the external-platform bridge identity
            # contract (external_agent_user / ext_<sender>). Keep its declared
            # construction scope; it was never a local principal.
            record = {
                "state": _ADMISSION_DECLARED,
                "user_id": raw_user_id,
            }
        else:
            logger.warning(
                "chat message authority: admission for %s refused (%s)",
                raw_user_id,
                actor.get("error_code") or actor.get("http_status"))
            record = {
                "state": _ADMISSION_UNAVAILABLE,
                "user_id": raw_user_id,
                "error_code": str(
                    actor.get("error_code") or "AUTHORITY_UNAVAILABLE"),
            }
    return _ADMISSION.set(record)


def reset_chat_write_actor(token) -> None:
    """Restore the previous pin (turn exit). Safe on a stale token."""
    if token is not None:
        _ADMISSION.reset(token)


def _pinned_admission() -> Optional[Dict[str, Any]]:
    """The admission record pinned on this turn, if any."""
    try:
        value = _ADMISSION.get()
        return dict(value) if isinstance(value, dict) else None
    except Exception:  # noqa: BLE001 — absent pin is not an authority read
        return None


def _normalized_owner(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _durable_session(db: Any, session_id: str) -> Tuple[bool, Any]:
    """(row_exists, raw_owner) for the durable ChatSession row.

    Only a real ORM row is authoritative. ``row_exists`` distinguishes "no
    durable session row" from "a row whose owner is the empty/placeholder
    class" — the write path must not mistake an unverifiable claim for a
    verified one. An unreadable row is handled by the caller's fail-closed
    wrapper.
    """
    from core.models import ChatSession

    row = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id)
        .first()
    )
    if not isinstance(row, ChatSession):
        return False, None
    return True, row.user_id


def _owner_fence(column, owner: Any):
    if owner is None:
        return column.is_(None)
    return column == str(owner)


def _refusal(http_status: int, code: str, message: str) -> Dict[str, Any]:
    return {
        "ok": False,
        "http_status": int(http_status),
        "error_code": str(code),
        "message": str(message),
    }


def _rows_or_empty(result: Any) -> list:
    """Iterate an ORM result, tolerating a non-iterable test double.

    Production queries always return an iterable (a list, ``Row`` result or
    ``None``). Unit suites that replace the whole ``Session`` with a
    ``MagicMock`` return a mock from the terminal call; it is not a real ORM
    result and must not be mistaken for a durable row. Real query failures
    still raise and are handled as unavailable by the caller.
    """
    if result is None:
        return []
    try:
        return list(result)
    except TypeError:
        return []


def _durable_read_row(db: Any, session_id: str) -> Any:
    """The real durable ``ChatSession`` row (never an in-memory label)."""
    from core.models import ChatSession

    rows = _rows_or_empty(
        db.query(ChatSession)
        .filter(ChatSession.id == session_id)
        .limit(1)
        .all()
    )
    return next((row for row in rows if isinstance(row, ChatSession)), None)


def _durable_message_scopes(db: Any, session_id: str) -> Tuple[bool, set]:
    """(has_rows, tenant ids) for the conversation's durable message rows.

    Empty/NULL tenant ids are reported as the Personal-Edition ``default``
    alias; callers canonicalise before comparing.
    """
    from core.models import ChatMessage

    rows = _rows_or_empty(
        db.query(ChatMessage.tenant_id)
        .filter(ChatMessage.conversation_id == session_id)
        .distinct()
        .all()
    )
    tenants = set()
    for row in rows:
        if isinstance(row, (tuple, list)):
            value = row[0]
        else:
            value = getattr(row, "tenant_id", None)
            if value is None:
                try:
                    value = row[0]
                except Exception:  # noqa: BLE001 — shape is not a scope fact
                    value = None
        if value is None or not str(value).strip():
            tenants.add("default")
        else:
            tenants.add(str(value).strip())
    return bool(rows), tenants


def resolve_chat_read_scope(
    db: Any, session_id: Any, actor: Any,
) -> Dict[str, Any]:
    """Resolve whether ``actor`` may read a session's public envelope.

    This is the read-side twin of :func:`resolve_chat_message_scope`. It uses
    the SAME shared mechanisms (the durable ``ChatSession`` owner, the fresh
    ``_resolve_actor`` snapshot and ``canonical_scope_id``) and adds no second
    policy registry:

    * the durable ``ChatSession`` owner is authority; an in-memory or JSON-file
      label can neither grant a foreign session nor take one away from its
      durable owner;
    * the caller must be a real, currently-active local principal (fresh
      read), so a stale token cannot preserve a moved/revoked scope;
    * a named local owner is served only to that same durable owner. There is
      no chat-session share/grant table in this codebase, so no per-session
      grant is invented and no administrator-wide all-tenant bypass is added;
    * a legacy placeholder owner is reclaimable only for a verified local
      caller whose CURRENT canonical scope matches the conversation's durable
      rows. A NULL/default actor keeps the documented Personal-Edition
      compatibility; a non-default caller cannot adopt a default-scope or
      otherwise foreign-scope conversation;
    * an external/system identity (``external_agent_user`` or the older
      bridge's ``ext_<sender>``) resolves to no local User row, so it is not a
      grant for any local caller. Its own bridge writer is unaffected.
    * durable rows with no verifiable owner (messages without a session row)
      are refused rather than guessed.

    Returns ``ok`` plus the chosen ``source`` on success, or a refusal dict
    with ``http_status``/``error_code``/``message``.
    """
    from core.goal_run_decision_service import (
        _resolve_actor,
        canonical_scope_id,
    )

    actor_id = (
        actor.strip() if isinstance(actor, str)
        else str(getattr(actor, "id", "") or "")
    )
    if not actor_id:
        return _refusal(401, "UNAUTHENTICATED", "Authentication required")

    sid = str(session_id or "").strip()
    if not sid:
        return _refusal(404, "CHAT_SESSION_UNVERIFIED", "Session not found")

    try:
        row = _durable_read_row(db, sid)
        has_messages, message_scopes = _durable_message_scopes(db, sid)
    except Exception as exc:  # noqa: BLE001 — unreadable authority fails closed
        logger.warning(
            "chat read authority: session %s unreadable (%s)",
            sid, type(exc).__name__)
        return _refusal(
            503, "CHAT_READ_AUTHORITY_UNAVAILABLE",
            "The conversation's owner could not be verified")

    if row is None and not has_messages:
        # Nothing durable exists: the pre-existing in-memory/lazy-init contract
        # is allowed to create or serve a caller-owned empty session.
        return {
            "ok": True,
            "source": "no_durable_session",
            "session_id": sid,
            "durable_session": False,
            "durable_owner": None,
            "durable_raw_owner": None,
            "has_messages": False,
            "session_scope": None,
            "needs_reclaim": False,
            "actor": None,
        }

    if row is None:
        # Message rows with no session row: no verifiable owner. Serving them
        # (or reclaiming them) would be a guess.
        logger.warning(
            "chat read authority: session %s has durable messages but no "
            "session owner row; read refused", sid)
        return _refusal(
            404, "CHAT_SESSION_UNVERIFIED",
            "This conversation's owner could not be verified")

    durable_raw_owner = row.user_id
    durable_owner = _normalized_owner(durable_raw_owner)
    session_scope = (
        next(iter(message_scopes)) if len(message_scopes) == 1 else None)

    resolved = _resolve_actor(db, actor_id)
    if not resolved.get("ok"):
        return _refusal(
            int(resolved.get("http_status") or 401),
            str(resolved.get("error_code") or "UNAUTHENTICATED"),
            str(resolved.get("message") or "Authentication required"),
        )

    _created = getattr(row, "created_at", None)
    base = {
        "ok": True,
        "source": "owner",
        "session_id": sid,
        "durable_session": True,
        "durable_owner": durable_owner,
        "durable_raw_owner": durable_raw_owner,
        "durable_title": getattr(row, "title", None),
        "durable_created_at": (
            _created.isoformat() if hasattr(_created, "isoformat")
            else (str(_created) if _created else None)),
        "has_messages": has_messages,
        "session_scope": session_scope,
        "needs_reclaim": False,
        "actor": {
            "id": resolved["id"],
            "tenant_id": resolved["tenant_id"],
            "workspace_id": resolved["workspace_id"],
            "raw_tenant_id": resolved.get("raw_tenant_id"),
            "raw_workspace_id": resolved.get("raw_workspace_id"),
        },
    }

    if durable_owner == actor_id:
        # Verified ownership. The owner is the strongest authority; legacy
        # pre-fix rows may carry the old construction tenant, so ownership is
        # not re-litigated against a historical row scope here.
        return base

    if is_legacy_placeholder_owner(durable_owner):
        # No real owner is recorded. Reclaim only inside the caller's CURRENT
        # canonical scope: the durable rows are the conversation's scope
        # evidence, and a non-default caller must never adopt default/foreign
        # rows merely because the owner label was a placeholder.
        if has_messages:
            if len(message_scopes) != 1:
                logger.warning(
                    "chat read authority: session %s has ambiguous durable "
                    "scopes (%s); read refused", sid, sorted(message_scopes))
                return _refusal(
                    409, "CHAT_SESSION_SCOPE_AMBIGUOUS",
                    "The conversation's scope is inconsistent")
            canonical_row_scope = canonical_scope_id(session_scope)
            if canonical_row_scope != canonical_scope_id(
                    resolved["tenant_id"]):
                logger.warning(
                    "chat read authority: session %s legacy scope %s does "
                    "not match caller %s scope %s; read refused",
                    sid, canonical_row_scope, actor_id,
                    canonical_scope_id(resolved["tenant_id"]))
                return _refusal(
                    403, "CHAT_SESSION_SCOPE_DENIED",
                    "This conversation is outside your workspace or tenant")
        else:
            # An empty placeholder session carries no row-scope evidence but
            # may still have foreign trace/task/request records keyed by its
            # id. There is no durable scope to authorize, so it is not
            # reclaimable on the read path; the write path's first-caller
            # reclaim remains unchanged.
            logger.warning(
                "chat read authority: empty legacy session %s has no durable "
                "scope evidence; read refused", sid)
            return _refusal(
                404, "CHAT_SESSION_UNVERIFIED",
                "This conversation's owner could not be verified")
        base["source"] = "legacy_reclaim"
        base["needs_reclaim"] = True
        return base

    # A non-placeholder owner that is not the caller. Ask the shared actor
    # resolver whether it is a real local principal (foreign user) or an
    # external/system identity (no local User row).
    owner_probe = _resolve_actor(db, durable_owner)
    if owner_probe.get("ok"):
        logger.warning(
            "chat read authority: session %s is durably owned by another "
            "local user; read refused", sid)
        return _refusal(
            403, "CHAT_SESSION_FOREIGN",
            "This conversation belongs to another user")
    if str(owner_probe.get("error_code") or "") == "UNAUTHENTICATED":
        logger.warning(
            "chat read authority: session %s is owned by a non-local "
            "identity (%s); local read refused", sid, durable_owner)
        return _refusal(
            403, "CHAT_SESSION_EXTERNAL_OWNED",
            "This conversation is not available to this account")
    # The owner row exists but could not be read/verified (outage). Fail
    # closed rather than assume it is external, foreign or free.
    return _refusal(
        int(owner_probe.get("http_status") or 503),
        str(owner_probe.get("error_code") or "AUTHORITY_UNAVAILABLE"),
        "The conversation's owner could not be verified",
    )


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

    admission = _pinned_admission() or {}
    admission_state = str(admission.get("state") or _ADMISSION_NONE)
    if admission_state == _ADMISSION_UNAVAILABLE:
        logger.warning(
            "chat message authority: admission authority was unavailable "
            "(%s); append refused",
            admission.get("error_code") or "AUTHORITY_UNAVAILABLE")
        return _refusal(
            503, "CHAT_ADMISSION_AUTHORITY_UNAVAILABLE",
            "The acting user's authority could not be verified for this turn")

    pinned = (
        str(admission.get("user_id"))
        if admission.get("user_id") else None
    )
    if admission_state not in (_ADMISSION_ACTOR, _ADMISSION_DECLARED):
        pinned = None

    session = session if isinstance(session, dict) else {}
    session_id = str(session.get("id") or "").strip()
    session_owner = _normalized_owner(session.get("user_id"))

    try:
        durable_found, durable_raw_owner = (
            _durable_session(db, session_id) if session_id else (False, None))
    except Exception as exc:  # noqa: BLE001 — unreadable is not permission
        logger.warning(
            "chat message authority: session %s owner unreadable (%s)",
            session_id, type(exc).__name__)
        return _refusal(
            503, "CHAT_SESSION_AUTHORITY_UNAVAILABLE",
            "The conversation's owner could not be verified")
    durable_owner = _normalized_owner(durable_raw_owner)

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

    # ---- classify the selected identity ----------------------------------
    legacy_global = False
    rebound_owner: Optional[str] = None
    actor: Dict[str, Any] = {}
    if (
        is_legacy_placeholder_owner(actor_id)
        and not is_system_scope_identity(actor_id)
    ):
        # No actor (or a legacy placeholder). Keep the existing declared
        # construction-scope contract.
        legacy_global = True
    elif is_system_scope_identity(actor_id) and not (
            admission_state == _ADMISSION_ACTOR and pinned == actor_id):
        # External-platform system identity: a declared writer, never a local
        # user. (A real local User whose id literally equals the system id is
        # governed by its admitted actor snapshot instead.)
        legacy_global = True
    elif admission_state == _ADMISSION_DECLARED and actor_id == pinned:
        # A non-local external identity admitted by an external bridge. It
        # must still be non-local at write time: an identity that became a
        # local user during the turn is never adopted implicitly.
        probe = _resolve_actor(db, actor_id)
        if probe.get("ok"):
            logger.warning(
                "chat message authority: external identity %s became a local "
                "user during the turn; append refused", actor_id)
            return _refusal(
                409, "CHAT_ACTOR_IDENTITY_CHANGED",
                "The acting identity changed during this turn")
        if str(probe.get("error_code") or "") != "UNAUTHENTICATED":
            # The identity read itself failed (outage/inactive). Fail closed.
            logger.warning(
                "chat message authority: external identity %s could not be "
                "verified (%s); append refused", actor_id,
                probe.get("error_code") or probe.get("http_status"))
            return {
                **probe,
                "error_code": str(
                    probe.get("error_code") or "AUTHORITY_UNAVAILABLE"),
                "message": str(
                    probe.get("message")
                    or "The acting identity could not be verified"),
            }
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
        if admission_state == _ADMISSION_ACTOR and pinned == actor_id:
            # The admitted snapshot is the authority. A peer tenant/workspace
            # move, role change or deactivation between admission and this
            # write refuses — the turn's content must never be re-scoped.
            admitted = admission.get("snapshot") or {}
            fresh = _actor_snapshot(actor)
            changed = [
                field for field in _AUTHORITY_FIELDS
                if str(admitted.get(field)) != str(fresh.get(field))
            ]
            if changed:
                logger.warning(
                    "chat message authority: actor %s scope changed during "
                    "the turn (%s) for session %s; append refused",
                    actor_id, ",".join(changed), session_id)
                return _refusal(
                    409, "CHAT_ACTOR_SCOPE_CHANGED",
                    "The acting user's authority changed during this turn")
        # Fence the exact actor snapshot in THIS transaction. A peer
        # deactivation, tenant/workspace move or role change between the
        # admission comparison and this append misses and refuses.
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
    # A pinned append (and any existing row) must be verified inside THIS
    # transaction. A placeholder reclaim is therefore never accepted from an
    # in-memory label alone: the durable row must either already carry that
    # placeholder owner or be re-owned here, and only then may the append
    # proceed.
    verify_durable_session = bool(
        session_id and (durable_found or (pinned and actor_id == pinned)))
    if verify_durable_session and not durable_found:
        logger.warning(
            "chat message authority: session %s has no durable owner row; "
            "append refused", session_id)
        return _refusal(
            409, "CHAT_SESSION_UNVERIFIED",
            "The conversation's durable owner could not be verified")

    if verify_durable_session:
        from core.models import ChatSession

        values: Dict[str, Any] = {"updated_at": ChatSession.updated_at}
        if pinned and actor_id == pinned and is_legacy_placeholder_owner(
                durable_owner):
            # Reclaim the legacy placeholder durably, in the same transaction
            # that fences it. The next turn (and any other caller) then sees a
            # real owner instead of a claimable label.
            values["user_id"] = pinned
            rebound_owner = pinned
        try:
            frozen = db.execute(
                update(ChatSession)
                .where(
                    ChatSession.id == session_id,
                    _owner_fence(ChatSession.user_id, durable_raw_owner),
                )
                .values(**values)
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
            "session_rebound_to": rebound_owner,
        }
    return {
        "ok": True,
        "user_id": actor["id"],
        "tenant_id": actor["tenant_id"],
        "workspace_id": actor["workspace_id"],
        "scope_source": "actor",
        "durable_session_owner": durable_owner,
        "session_rebound_to": rebound_owner,
    }
