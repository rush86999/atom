# -*- coding: utf-8 -*-
"""Event-sourced dialogue state (2026-10-01, migration step 2).

The architecture the step-back research pointed at: the conversation's
durable decisions — objectives, standing preferences, row bindings,
turn programs — live in ONE append-only ledger (models.ConversationEvent)
and everything the lanes consume becomes a PROJECTION of it. Nothing is
popped: superseding an objective appends an event that references the
old one, so the supersession stash and the _stored_requested_items
precedence chain (task → stash → result row, ordered because the
carriers were written at different moments) stop being load-bearing —
they remain as fallbacks while the ledger fills.

Durable facts are never compacted away (the Letta/Mem0-tier rule): a
preference taught on turn 3 applies on turn 300 with its receipt — the
ask lane merges the projection's standing phrases into every program's
constraints, which is the fix for the 2026-09-30 'always include the
Tennsmith sheet' lesson that existed in storage but was invisible at
decision time because resolvers see a 6-turn window.

Store contract (hard):
- APPEND and FETCH only. There is no update and no delete — not "we
  don't call them", they do not exist. Supersede/retire = a new event
  referencing ``supersedes_event_id``.
- FAULT-ISOLATED: every store failure is logged and swallowed — the
  ledger must never break a turn; callers fall back to the carriers.
- PURE PROJECTIONS: ``project_events`` is a pure function over rows, so
  replay correctness is unit-testable without a database.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

__all__ = [
    "append_event",
    "fetch_events",
    "project_events",
    "active_objective_items",
    "active_preference_phrases",
    "active_bindings",
    "record_program",
    "OBJECTIVE_SET",
]

OBJECTIVE_SET = "objective_set"
OBJECTIVE_SUPERSEDED = "objective_superseded"
PREFERENCE_SET = "preference_set"
PREFERENCE_RETIRED = "preference_retired"
BINDING_CAPTURED = "binding_captured"
PROGRAM_RECORDED = "program_recorded"
FILE_RESOLVED = "file_resolved"

_TABLE_READY = False


def _session():
    global _TABLE_READY
    from core.database import SessionLocal

    if not _TABLE_READY:
        # Lazy, idempotent, checkfirst: production-ready regardless of
        # startup create_all ordering; creates the scratch table under
        # TESTING=1 the same way.
        from core.models import Base

        engine = SessionLocal().get_bind()
        Base.metadata.create_all(bind=engine, tables=[
            Base.metadata.tables["conversation_events"]])
        _TABLE_READY = True
    return SessionLocal()


def append_event(
    kind: str,
    conversation_id: str,
    payload: Optional[Dict[str, Any]] = None,
    *,
    supersedes_event_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> Optional[str]:
    """Append one decided fact. Returns the event id, or None on any
    failure (logged; the turn proceeds on carriers)."""
    try:
        from core.models import ConversationEvent

        db = _session()
        try:
            row = ConversationEvent(
                conversation_id=str(conversation_id or ""),
                kind=str(kind or ""),
                payload_json=json.dumps(payload or {}, default=str),
                supersedes_event_id=supersedes_event_id,
                workspace_id=workspace_id,
                tenant_id=tenant_id,
            )
            db.add(row)
            db.commit()
            return row.id
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 — ledger never breaks a turn
        logger.debug("dialogue-state append failed (%s): %r", kind, exc)
        return None


def fetch_events(
    conversation_id: str,
    *,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """The conversation's events, oldest first (bounded: projections
    need recent state; the audit tail stays queryable in the DB)."""
    try:
        from core.models import ConversationEvent

        db = _session()
        try:
            rows = (
                db.query(ConversationEvent)
                .filter(ConversationEvent.conversation_id
                        == str(conversation_id or ""))
                .order_by(ConversationEvent.created_at.desc(),
                          ConversationEvent.id.desc())
                .limit(int(limit))
                .all()
            )
            out = []
            for row in reversed(rows):
                try:
                    payload = json.loads(row.payload_json or "{}")
                except (TypeError, ValueError):
                    payload = {}
                out.append({
                    "id": row.id,
                    "kind": row.kind,
                    "payload": payload,
                    "supersedes_event_id": row.supersedes_event_id,
                    "created_at": (
                        row.created_at.isoformat()
                        if row.created_at else None),
                })
            return out
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 — read failure = no state
        logger.debug("dialogue-state fetch failed: %r", exc)
        return []


# ---------------------------------------------------------------------------
# PURE projections — no DB, unit-testable by replay
# ---------------------------------------------------------------------------

def project_events(events: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Replay events → the conversation's current durable state.

    Returns {objective, preferences, bindings, last_program, file}. A
    superseded/retired event id removes that fact; a binding is active
    only at its captured ``content_hash`` (a changed workbook revision
    expires it by projection, matching the task-carrier semantics).
    """
    objective: Optional[Dict[str, Any]] = None
    objective_event_id: Optional[str] = None
    preferences: List[Dict[str, Any]] = []
    pref_event_ids: set = set()
    bindings: List[Dict[str, Any]] = []
    binding_event_ids: set = set()
    last_program: Optional[Dict[str, Any]] = None
    file: Optional[Dict[str, Any]] = None

    for ev in events or []:
        kind = str((ev or {}).get("kind") or "")
        payload = (ev or {}).get("payload") or {}
        eid = str((ev or {}).get("id") or "")
        sup = (ev or {}).get("supersedes_event_id")
        if sup:
            if sup == objective_event_id:
                objective, objective_event_id = None, None
            pref_event_ids.discard(str(sup))
            preferences = [p for p in preferences
                           if p.get("_event_id") != str(sup)]
            binding_event_ids.discard(str(sup))
            bindings = [b for b in bindings
                        if b.get("_event_id") != str(sup)]
        if kind == OBJECTIVE_SET:
            objective = dict(payload)
            objective_event_id = eid
        elif kind == OBJECTIVE_SUPERSEDED:
            objective, objective_event_id = None, None
        elif kind == PREFERENCE_SET:
            if eid not in pref_event_ids:
                pref_event_ids.add(eid)
                preferences.append({**payload, "_event_id": eid})
        elif kind == PREFERENCE_RETIRED:
            target = payload.get("event_id")
            pref_event_ids.discard(str(target))
            preferences = [p for p in preferences
                           if p.get("_event_id") != str(target)]
        elif kind == BINDING_CAPTURED:
            if eid not in binding_event_ids:
                binding_event_ids.add(eid)
                bindings.append({**payload, "_event_id": eid})
        elif kind == PROGRAM_RECORDED:
            last_program = dict(payload)
        elif kind == FILE_RESOLVED:
            file = dict(payload)
    return {
        "objective": objective,
        "preferences": preferences,
        "bindings": bindings,
        "last_program": last_program,
        "file": file,
    }


# ---------------------------------------------------------------------------
# Projection reads (DB-backed, fault-isolated)
# ---------------------------------------------------------------------------

def _projection(conversation_id: str) -> Dict[str, Any]:
    return project_events(fetch_events(conversation_id))


def active_objective_items(conversation_id: str) -> List[str]:
    """The active objective's ordered items, or [] (caller falls back to
    the carriers — the ledger fills turn by turn)."""
    obj = _projection(conversation_id).get("objective") or {}
    return [str(i).strip() for i in (obj.get("items") or [])
            if str(i).strip()]


def active_preference_phrases(conversation_id: str) -> List[str]:
    """Active standing preference phrases (the user's own words — the
    READ resolves them against the file's real sheet catalog)."""
    out: List[str] = []
    seen: set = set()
    for pref in _projection(conversation_id).get("preferences") or []:
        phrase = str((pref or {}).get("phrase") or "").strip()
        if phrase and phrase.lower() not in seen:
            seen.add(phrase.lower())
            out.append(phrase)
    return out


def active_bindings(
    conversation_id: str, content_hash: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Bindings active at ``content_hash`` (revision expiry by
    projection)."""
    out = []
    for b in _projection(conversation_id).get("bindings") or []:
        if content_hash and b.get("content_hash") != content_hash:
            continue
        out.append({k: v for k, v in b.items() if k != "_event_id"})
    return out


def record_program(
    conversation_id: str, program: Optional[Dict[str, Any]],
    *, workspace_id: Optional[str] = None,
) -> None:
    """Audit the decided program (bounded payload — the full program
    already rides the task and response metadata)."""
    if not isinstance(program, dict):
        return
    slim = {
        "schema": program.get("schema"),
        "operation": program.get("operation"),
        "target_set": {
            "kind": (program.get("target_set") or {}).get("kind"),
            "size": len((program.get("target_set") or {}).get("items")
                        or []),
            "origin": (program.get("target_set") or {}).get("origin"),
        },
        "reference": program.get("reference"),
        "clarify": bool((program.get("clarify") or {}).get("needed")),
        "recorded_at": time.time(),
    }
    append_event(PROGRAM_RECORDED, conversation_id, slim,
                 workspace_id=workspace_id)
