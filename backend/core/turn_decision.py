# -*- coding: utf-8 -*-
"""One structured decision per turn (2026-09-30 consolidation directive).

WHY THIS MODULE EXISTS. The turn pipeline accumulated several gates that
each partially interpret the same message (teaching detection,
supersession, retry resolution, edit nomination, read resolution). An
early gate can decide before a later one sees the full request — the
pattern behind both live defects ("research became an edit"; "new
research became the old workbook search"). The directive: consolidate
INTERPRETATION into one structured decision per turn while keeping the
existing execution, validation and recovery machinery.

DESIGN RULES (from the directive):

- This module COMPOSES the existing, tested gates — it must not add a
  second, competing interpreter. Each signal is credited by name in
  ``provenance.signals`` so a decision is auditable back to the gates
  that produced it.
- ONE DECISION, MANY ACTIONS: "repeat the search and learn to include
  Tennsmith…" proposes research + learning and NO edit, without forcing
  the turn into an exclusive lane.
- REASONING PROPOSES; POLICY AUTHORIZES; EXECUTION PROVES. Every
  action carries an ``authorization`` verdict from deterministic
  policy; nothing here executes anything.
- Sources are represented EXPLICITLY (a message naming an email is a
  request for that source, not a special exclusion): the workbook
  reference resolves even when the request also needs email.
- The proposed TASK REVISION retains the previous objective until the
  revision commits — supersession becomes a proposal here, not a pop.
- Learning carries an explicit DESTINATION (agent / task / workspace /
  user preference); unresolved destinations are surfaced, not dropped.

SHADOW MODE (directive step 2): the orchestrator records this decision
beside the reply without routing by it. Migration of compound turns
onto the contract and removal of duplicated gates follow only after the
evaluation (step 3) passes on the incident transitions.
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

SCHEMA = "turn-decision-1"

# Requested information SOURCES, represented explicitly (directive
# boundary change #2): a communication-source word is a source the user
# wants consulted, never a reason to refuse resolving the workbook.
_SOURCE_NOUN_RE = re.compile(
    r"\b(e-?mails?|mails?|inbox|threads?|dms?|chats?|messages?|texts?|"
    r"calendar|tickets?|notes?|memos?|letters?|comments?|posts?)\b",
    re.IGNORECASE,
)

#: Authorization verdicts, mirroring the maturity/policy vocabulary.
AUTH_GRANTED = "granted"
AUTH_NEEDS_CONFIRMATION = "needs_confirmation"
AUTH_NEEDS_GRANT = "needs_grant"

_KIND_RESEARCH = "research"
_KIND_LEARNING = "learning"
_KIND_CANVAS_EDIT = "canvas_edit"


def _requested_sources(message: str) -> List[str]:
    """Source kinds the message explicitly asks to consult."""
    return sorted({m.lower() for m in _SOURCE_NOUN_RE.findall(
        message or "")})


def _task_objective(session: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The active/stashed file objective as evidence (never mutated)."""
    for carrier in ((session or {}).get("_pending_file_task"),
                    (session or {}).get("_superseded_file_task_context")):
        if isinstance(carrier, dict) and carrier.get("original_message"):
            out = {
                "original_message": str(
                    carrier.get("original_message"))[:300],
                "mention": carrier.get("mention")
                or carrier.get("confirmed_mention"),
                "status": carrier.get("status"),
            }
            ident = carrier.get("resolved_file")
            if isinstance(ident, dict):
                out["resolved_file"] = {
                    k: ident.get(k) for k in
                    ("file_name", "file_id", "content_hash")
                    if ident.get(k) is not None}
            bindings = ((carrier.get("disambiguation") or {})
                        .get("resolved_bindings"))
            if bindings:
                out["row_bindings"] = len(bindings)
            return out
    return {}


def build_turn_decision(
    message: str,
    session: Optional[Dict[str, Any]] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    context: Optional[Dict[str, Any]] = None,
    session_id: str = "",
    reasoning_available: Optional[bool] = None,
    routed_lane: Optional[str] = None,
) -> Dict[str, Any]:
    """Compose ONE structured decision for a turn.

    Calls the existing gates (teaching cues, extends-objective, the
    failed-edit retry detector, edit-shape, the read resolver) and
    represents their consensus as proposed actions with authorization
    verdicts. Pure: no session mutation, no execution, no LLM calls —
    ``reasoning_available`` is supplied by the caller when known.
    """
    t = (message or "").strip()
    session = session if isinstance(session, dict) else {}
    context = context if isinstance(context, dict) else {}
    signals: List[str] = []
    actions: List[Dict[str, Any]] = []

    # ---- references: sources named + workbook resolution ---------------
    sources = _requested_sources(t)
    if sources:
        signals.append("requested_sources")
    file_reference: Dict[str, Any] = {}
    mention = ""
    try:
        from core.agent_file_context import spreadsheet_mentions

        sm = spreadsheet_mentions(t)
        if sm:
            mention = sm[0]
            signals.append("spreadsheet_mention")
    except Exception:  # noqa: BLE001 — belt-only
        mention = ""
    if not mention:
        # compose the resolver's identity carriers directly (its async
        # entry is orchestrator-owned; the carriers are the same)
        for carrier in (session.get("_pending_file_task"),
                        session.get("_superseded_file_task_context")):
            ident = (carrier or {}).get("resolved_file") if isinstance(
                carrier, dict) else None
            nm = str((ident or {}).get("file_name") or "").strip()
            if nm and nm.rsplit(".", 1)[-1].lower() in (
                    "xlsx", "xls", "xlsm", "csv", "tsv"):
                mention = nm.lower()
                signals.append("inherited_file_identity")
                break
    if mention:
        file_reference = {"kind": "spreadsheet", "name": mention}

    # ---- action: research -----------------------------------------------
    research = None
    extends = False
    task_obj = _task_objective(session)
    if file_reference or task_obj:
        try:
            from core.pending_file_task import (
                is_retrieval_refresh_request,
                request_extends_objective,
                build_pending_task,
            )

            base = build_pending_task(
                task_obj.get("original_message") or "",
                task_obj.get("mention") or mention or "")
            if task_obj:
                base["status"] = task_obj.get("status") or "pending"
            extends = bool(request_extends_objective(t, base))
            rerun = bool(is_retrieval_refresh_request(t))
        except Exception:  # noqa: BLE001 — compose-only
            extends, rerun = False, False
        if extends:
            signals.append("extends_objective")
        if rerun:
            signals.append("rerun_request")
        needs = bool(file_reference or task_obj)
        seek = _looks_seek_shaped(t)
        if needs and (rerun or extends) and not seek:
            # new work on the file that is NOT seek-shaped is a
            # PRESENTATION action over existing evidence ("make it
            # cleaner") — its own action, never research.
            actions.append({
                "kind": "presentation",
                "target": file_reference or {
                    "kind": "task_objective",
                    "mention": task_obj.get("mention")},
                "authorization": AUTH_GRANTED,
            })
        if needs and (rerun or (extends and seek)):
            research = {
                "kind": _KIND_RESEARCH,
                "target": file_reference or {
                    "kind": "task_objective",
                    "mention": task_obj.get("mention")},
                "additional_sources": sources,
                "constraints": _scope_constraints(t),
                "authorization": AUTH_GRANTED,  # reads are authorized
                "proposed_revision": {
                    # directive boundary #1: RETAIN the previous
                    # objective until this revision commits — the
                    # decision never pops anything.
                    "retains_previous_objective": True,
                    "adds_constraints": _scope_constraints(t),
                    "adds_sources": sources,
                },
            }
            actions.append(research)

    # ---- action: learning -------------------------------------------------
    lesson = ""
    destination = None
    destination_candidates: List[str] = []
    try:
        from core.chat_teaching import (
            detect_mid_message_cue,
            detect_teaching_cue,
        )

        lesson = detect_teaching_cue(t) or detect_mid_message_cue(t) or ""
    except Exception:  # noqa: BLE001 — compose-only
        lesson = ""
    if lesson:
        signals.append("teaching_cue")
        agent_id = (context.get("agent_id")
                    or session.get("_task_agent_id"))
        if agent_id:
            destination = f"agent:{agent_id}"
        else:
            # directive boundary #6: surface the missing destination,
            # never silently drop the learning request.
            destination_candidates = ["agent", "workspace", "user"]
        actions.append({
            "kind": _KIND_LEARNING,
            "lesson": lesson[:400],
            "destination": destination,
            "destination_candidates": destination_candidates,
            "authorization": AUTH_NEEDS_CONFIRMATION,
        })

    # ---- action: canvas edit (nomination → grant requirement) ------------
    canvas_id = (context.get("canvas_id")
                 or (context.get("canvas") or {}).get("canvas_id"))
    edit_nomination = False
    user_grounded_instruction = ""
    if canvas_id:
        try:
            from integrations.chat_orchestrator import _canvas_edit_shaped

            edit_nomination = bool(_canvas_edit_shaped(
                t, {"canvas": {"canvas_id": canvas_id}}))
            if edit_nomination:
                signals.append("edit_shape_nomination")
        except Exception:  # noqa: BLE001 — compose-only
            edit_nomination = False
        try:
            from integrations.chat_orchestrator import (
                _failed_edit_retry_target,
            )

            retry = _failed_edit_retry_target(
                session_id or str(session.get("id") or ""), t,
                history or [])
            if retry:
                user_grounded_instruction = retry.get("instruction") or ""
                signals.append("user_grounded_edit_retry")
        except Exception:  # noqa: BLE001 — compose-only
            user_grounded_instruction = ""
    if canvas_id and (edit_nomination or user_grounded_instruction):
        actions.append({
            "kind": _KIND_CANVAS_EDIT,
            "target_canvas": str(canvas_id),
            "nomination": edit_nomination,
            "user_grounded_instruction": user_grounded_instruction or None,
            # directive: an edit-shape hint NOMINATES; authorization
            # requires a user-grounded instruction (this turn's explicit
            # edit request, or the retry of a previously authorized one).
            "authorization": (
                AUTH_GRANTED if user_grounded_instruction
                else AUTH_NEEDS_GRANT),
        })

    if not actions:
        actions.append({
            "kind": "conversation",
            "authorization": AUTH_GRANTED,
        })

    return {
        "schema": SCHEMA,
        "session_id": session_id or str(session.get("id") or ""),
        "created_at": time.time(),
        "message": t[:500],
        "requested_actions": actions,
        "references": {
            "sources": sources,
            "file": file_reference or None,
        },
        "task_state_view": {
            "active_objective": task_obj or None,
            "revision_proposed": bool(
                research and research.get("proposed_revision",
                                          {}).get("adds_constraints")),
        },
        "policy": {
            # reasoning proposes; policy authorizes; execution proves.
            "reasoning_available": reasoning_available,
        },
        "provenance": {"signals": signals},
        # shadow-mode observability: which lane ACTUALLY served (the
        # contract does not route yet — directive step 2).
        "routed_lane": routed_lane,
    }


def _looks_seek_shaped(text: str) -> bool:
    return bool(re.search(
        r"\b(?:find|search|look\s?up|check|get|show|list|pull|read|"
        r"fetch|locate|repeat)\b", text or "", re.IGNORECASE))


def _scope_constraints(message: str) -> List[str]:
    """Explicit scope guidance the user added to a repeat request —
    the 'include tennsmith sheet for roper whitney searches' clause.
    Kept as the user's own words (scoped search guidance, never a
    binding)."""
    t = message or ""
    out: List[str] = []
    m = re.search(
        r"\b(?:include|also\s+search|add)\b\s+(.{4,90}?)(?:\s+for\s+|"
        r"\s+when\s+|\.|,|$)", t, re.IGNORECASE)
    if m:
        out.append(m.group(1).strip())
    return out[:3]
