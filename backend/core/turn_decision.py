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


# Verbs that command a change to an artifact. A verb in this list is a
# NOUNINATION on its own; it is a user-grounded INSTRUCTION only when it
# is not governed by a learn/remember/hedge construction and the message
# names an artifact to change.
_EDIT_VERB_RE = re.compile(
    r"\b(?:update|edit|replace|change|set|apply|fill|trim|add|remove|"
    r"delete|restore|rebuild|rewrite|revise|reformat|reword|include|"
    r"insert|append|sort|rename|paste)\b",
    re.IGNORECASE,
)
# Constructions that make a following verb an OBJECT OF A LEARNING or a
# hedge rather than a command. This is the general form of the
# single-consumer teaching veto that was hard-coded into
# `_canvas_edit_shaped` on 2026-09-30: "learn to INCLUDE the tennsmith
# sheet" is a request to remember a search rule, not to edit a canvas.
_GOVERNED_VERB_RE = re.compile(
    r"\b(?:learn|remember|note|make\s+sure|be\s+sure|try|want|need|"
    r"should|would|could|let\s+me\s+know\s+if|say\s+if|tell\s+me\s+if|"
    r"if|whether)\s+(?:to\s+|that\s+|it\s+|you\s+)*$",
    re.IGNORECASE,
)
# An artifact the user could be commanding a change to.
_ARTIFACT_TARGET_RE = re.compile(
    r"\b(?:draft|canvas|email|e-mail|document|doc|text|copy|content|"
    r"subject|body|table|sheet|slide|spreadsheet|presentation|price|"
    r"prices|value|row|rows|entry|field|figure|footer|list)\b",
    re.IGNORECASE,
)


def _continuation_decision(
    message: str, session: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """The EXISTING fail-closed continuation resolver, composed rather
    than re-implemented.

    ``ChatOrchestrator._continuation_decision`` resolves exactly one
    retrieval operation (``none``/``read``/``rerun``/``refresh``) plus an
    independent presentation preference, and returns ``None`` for
    anything it does not positively recognize. It never uses ``self``, so
    it is called unbound. Composing it here is what makes research and
    presentation mutually exclusive: the pre-fix pair of ad-hoc
    conditions could — and did — fire both for one turn.
    """
    try:
        from integrations.chat_orchestrator import ChatOrchestrator

        return ChatOrchestrator._continuation_decision(
            None, message, session)
    except Exception:  # noqa: BLE001 — fail closed to "not a continuation"
        return None


def _is_approval(message: str) -> bool:
    """Does this turn approve/resume a previously asked operation?

    Delegates to the existing ``is_filename_confirmation`` gate, which
    already encodes the rule: "yes" / "go ahead" / a bare confirmation /
    a file back-reference resumes, while an approval that carries its own
    instruction is a NEW request.
    """
    try:
        from core.pending_file_task import is_filename_confirmation

        return bool(is_filename_confirmation(message))
    except Exception:  # noqa: BLE001 — fail closed
        return False


# A source attributed to a PERSON beyond the artifact being edited
# ("consider chandrakant's email contents") — research-worthy beside
# an edit; "the email"/"email price" (the artifact itself) is not.
_PERSON_SOURCE_RE = re.compile(
    r"\b[A-Za-z][a-z]+(?:'s|\u2019s)\s+"
    r"(?:e-?mail|mail|message|thread|note|letter|reply|text)\b",
    re.IGNORECASE,
)
# An explicit back-reference to already-obtained evidence ("as you
# found the latest price") — the edit should write VERIFIED evidence.
_EVIDENCE_BACKREF_RE = re.compile(
    r"\b(?:as\s+you\s+(?:found|located|reported)|that\s+you\s+found|"
    r"from\s+your\s+(?:earlier|previous|last)\s+"
    r"(?:reply|search|lookup|answer|message)|you\s+just\s+found)\b",
    re.IGNORECASE,
)


_FILENAME_SPAN_RE = re.compile(
    r"\b[A-Za-z0-9][A-Za-z0-9 ()'&._-]{0,60}?"
    r"\.(?:xlsx|xls|xlsm|csv|tsv|pdf|docx?|pptx?|txt|md|json)\b",
    re.IGNORECASE,
)


def _user_grounded_edit_instruction(message: str) -> str:
    """The user's OWN command to change an artifact, or "".

    This is the grant evidence the contract was missing: pre-fix, the only
    source of a user-grounded instruction was a retry of a *previously
    failed* edit, so a fresh explicit request — "rebuild the draft now
    with all eight machines" — was never authorized. In the recorded
    incident that meant 0 of 11 explicit edit instructions could be
    granted.

    A verb is a command when it is not governed by a learning/hedge
    construction. That single rule is the general form of the hard-coded
    teaching veto: "learn to INCLUDE the tennsmith sheet" yields "",
    "rebuild the draft … -- rebuild the draft" yields the message.
    """
    t = (message or "").strip()
    if not t or not _ARTIFACT_TARGET_RE.search(t):
        return ""
    # FILENAMES ARE NOT COMMANDS (2026-09-30 scenario eval): "Copy of
    # Consolidated Price List 2019 - Linmac Update.xlsx" carries
    # 'Update' as part of the NAME — an edit verb inside a filename
    # span never grounds an instruction.
    scrubbed = _FILENAME_SPAN_RE.sub(" ", t)
    if not _ARTIFACT_TARGET_RE.search(scrubbed):
        return ""
    for m in _EDIT_VERB_RE.finditer(scrubbed):
        if _GOVERNED_VERB_RE.search(scrubbed[:m.start()]):
            continue
        return t
    return ""


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
    if not mention:
        # an unresolved TASK-SHAPED file reference ("price list 2019",
        # "the workbook") still names a file REQUEST — the first ask of
        # a conversation has no stored task to inherit and must still
        # propose research (replay: 'find all these prices from price
        # list 2019' resolved to conversation).
        try:
            from core.agent_file_context import detect_file_task_mentions

            tm = detect_file_task_mentions(t)
            if tm:
                mention = tm[0]
                signals.append("file_task_mention_unresolved")
        except Exception:  # noqa: BLE001 — compose-only
            pass
    if mention:
        file_reference = {"kind": "spreadsheet", "name": mention}

    # ---- pre-pass: does this turn re-dispatch a previously authorized
    # EDIT? Resolved BEFORE retrieval, because a retry of an edit owns its
    # turn: re-dispatching the edit already re-acquires whatever evidence
    # it needs (`fetch_fresh_data_section` in the edit lane), so also
    # proposing a read is a pile-on, not a second action.
    canvas_id = (context.get("canvas_id")
                 or (context.get("canvas") or {}).get("canvas_id"))
    edit_retry_instruction = ""
    # DURABLE-STATE FORM FIRST: callers that hold the failed-edit
    # record (the state machine's task state; replay evaluation)
    # supply it directly — the DB scan is TTL-bound to NOW and cannot
    # answer historical questions.
    supplied_retry = context.get("failed_edit_retry")
    if isinstance(supplied_retry, dict) and canvas_id:
        edit_retry_instruction = (
            supplied_retry.get("instruction") or "")
        if edit_retry_instruction:
            signals.append("user_grounded_edit_retry_supplied")
    if canvas_id and not edit_retry_instruction:
        try:
            from integrations.chat_orchestrator import (
                _failed_edit_retry_target,
            )

            _retry = _failed_edit_retry_target(
                session_id or str(session.get("id") or ""), t,
                history or [])
            if _retry:
                edit_retry_instruction = _retry.get("instruction") or ""
                signals.append("user_grounded_edit_retry")
        except Exception:  # noqa: BLE001 — compose-only
            edit_retry_instruction = ""

    # ---- actions: research and presentation (mutually exclusive) --------
    # COMPOSE the existing continuation resolver instead of deciding
    # retrieval-vs-presentation privately. It resolves exactly ONE
    # operation, which is what makes the pair exclusive by construction.
    continuation = _continuation_decision(t, session)
    retrieval_op = (continuation or {}).get("retrieval")
    if retrieval_op:
        signals.append("continuation_decision")
    presentation_pref = (continuation or {}).get("presentation") or {}

    task_obj = _task_objective(session)
    needs = bool(file_reference or task_obj)
    seek = _looks_seek_shaped(t)
    approval = _is_approval(t)
    # BARE ACTION RETRY resumes a PENDING task ("try it" after an ask
    # whose lookup never ran — replay-surfaced: the live matcher's
    # confirmation gate misses bare retry verbs, so both the contract
    # AND the live lane answer conversation for a turn the user means
    # as 'run it'). Pending-only: a delivered task is the delivery
    # lane's business, not a fresh read.
    try:
        from core.pending_file_task import is_bare_action_retry

        bare_retry = is_bare_action_retry(t)
    except Exception:  # noqa: BLE001 — compose-only
        bare_retry = False
    pending_task_unresolved = bool(
        task_obj and task_obj.get("status") == "pending")
    # A DIRECT, self-contained ask. The pre-fix contract recognized
    # research only as a CONTINUATION of stored state, so a plain "find
    # the prices of these 8 machines in <file>" resolved to
    # `conversation` — no action at all. In the recorded incident that
    # was 10 of 30 user turns, including nine identical explicit asks.
    direct = bool(seek and (needs or sources))
    # Research against a non-file SOURCE (an email thread) is research
    # too; pre-fix the contract could only ever target a workbook.
    source_ask = bool(sources and seek and not needs)

    reason = None
    # RESEARCH ALONGSIDE AN EXPLICIT EDIT — only when the user asks to
    # CONSULT something beyond the artifact, or to USE prior found
    # evidence. Otherwise the edit owns its turn: the edit lane fetches
    # its own fresh data, and a bare direct_ask on inherited state is a
    # pile-on (replay turn 5: 'update with actual prices in the email'
    # — edit-only). Contrast the corpus cases that DO carry research:
    # 'try again this task, consider chandrakant's email contents'
    # (a person's mailbox beyond the artifact) and 'as you found the
    # latest price … update' (an explicit evidence back-reference, and
    # the resolver itself says refresh).
    _edit_grounded = bool(
        edit_retry_instruction or _user_grounded_edit_instruction(t))
    _consults_beyond_artifact = bool(
        _PERSON_SOURCE_RE.search(t) or _EVIDENCE_BACKREF_RE.search(t))
    if _edit_grounded and not _consults_beyond_artifact:
        reason = None
    elif source_ask:
        reason = "source_ask"
    elif needs and retrieval_op in ("rerun", "refresh", "read"):
        reason = "continuation_%s" % retrieval_op
    elif needs and direct:
        reason = "direct_ask"
    elif needs and approval:
        reason = "approval_resumes_pending"
    elif needs and bare_retry and pending_task_unresolved:
        reason = "bare_retry_resumes_pending"

    if reason:
        target = (file_reference or {"kind": "task_objective",
                                    "mention": task_obj.get("mention")}
                  if needs else {"kind": "source", "sources": sources})
        actions.append({
            "kind": _KIND_RESEARCH,
            "reason": reason,
            "target": target,
            "additional_sources": sources,
            "constraints": _scope_constraints(t),
            "authorization": AUTH_GRANTED,  # reads are authorized
            "proposed_revision": {
                # directive boundary #1: RETAIN the previous objective
                # until this revision commits — never pop anything.
                "retains_previous_objective": True,
                "adds_constraints": _scope_constraints(t),
                "adds_sources": sources,
            },
        })
        signals.append("research_%s" % reason)
        if retrieval_op in ("rerun", "refresh") and (
                presentation_pref.get("style") not in (None, "default")
                or presentation_pref.get("field") is not None):
            # COMPOUND retry+presentation ("search again and give me a
            # clean response"): BOTH actions — the continuation layer
            # already resolves the pair; the contract represents them
            # instead of collapsing to research. The guard keys off a
            # PREFERENCE ACTUALLY EXPRESSED ('default' is the
            # resolver's no-preference sentinel and is truthy — plain
            # "try search again" must NOT invent a re-render; measured
            # 8 spurious presentations in 30 turns pre-guard).
            signals.append("presentation_preference")
            actions.append({
                "kind": "presentation",
                "target": target,
                "style": presentation_pref.get("style"),
                "field": presentation_pref.get("field"),
                "authorization": AUTH_GRANTED,
            })
    elif retrieval_op == "none":
        # Presentation ONLY on the resolver's positive "none" verdict
        # ("make it cleaner"). Pre-fix this fired for ANY non-seek-shaped
        # message touching the file — a catch-all that invented a
        # reformat the user never asked for.
        actions.append({
            "kind": "presentation",
            "target": file_reference or {
                "kind": "task_objective",
                "mention": task_obj.get("mention")},
            "style": presentation_pref.get("style"),
            "field": presentation_pref.get("field"),
            "authorization": AUTH_GRANTED,
        })
        signals.append("presentation_only")

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
    edit_nomination = False
    user_grounded_instruction = edit_retry_instruction
    if canvas_id:
        try:
            from integrations.chat_orchestrator import _canvas_edit_shaped

            edit_nomination = bool(_canvas_edit_shaped(
                t, {"canvas": {"canvas_id": canvas_id}}))
            if edit_nomination:
                signals.append("edit_shape_nomination")
        except Exception:  # noqa: BLE001 — compose-only
            edit_nomination = False
        # Grant evidence #2: the user's OWN instruction in THIS turn.
        # Without this the contract could never authorize a fresh edit —
        # 0 of the 11 explicit edit instructions in the recorded incident.
        if not user_grounded_instruction:
            user_grounded_instruction = _user_grounded_edit_instruction(t)
            if user_grounded_instruction:
                signals.append("user_grounded_edit_instruction")
    presentation_only = bool(
        retrieval_op == "none" and (
            presentation_pref.get("style")
            or presentation_pref.get("field")))
    if canvas_id and (edit_nomination or user_grounded_instruction) \
            and not presentation_only:
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

    # ---- typed action program (the decision's executable shadow) --------
    # Closes the 2026-09-30 open item: the sheet scope the user asserted
    # (message phrasing + parsed constraints) now enters the durable
    # decision row as TYPED, inspectable program data — pending mentions
    # that resolve only against the file's real sheet catalog at execution
    # time (core.action_program), never guessed here. Compilation is total
    # and fail-open; the actions above remain authoritative regardless —
    # the program adds executability and receipts, it does not gate.
    action_program_record = None
    try:
        from core.action_program import program_from_decision

        _program = program_from_decision({
            "session_id": session_id or str(session.get("id") or ""),
            "message": t,
            "requested_actions": actions,
        })
        if _program is not None:
            action_program_record = _program.to_record()
    except Exception:  # noqa: BLE001 — a shadow must never fail the turn
        action_program_record = None

    return {
        "schema": SCHEMA,
        "session_id": session_id or str(session.get("id") or ""),
        "created_at": time.time(),
        "message": t[:500],
        "requested_actions": actions,
        "action_program": action_program_record,
        "references": {
            "sources": sources,
            "file": file_reference or None,
        },
        "task_state_view": {
            "active_objective": task_obj or None,
            "revision_proposed": any(
                a.get("proposed_revision", {}).get("adds_constraints")
                for a in actions),
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
    # Mirrors the live _FILE_READ_SHAPE_RE read-shape vocabulary
    # (scenario-eval gaps: 'compare the workbook values', 'what does
    # the supplier thread say' — compare/question stems are reads).
    return bool(re.search(
        r"\b(?:find|search|look\s?up|lookup|check|get|show|list|pull|"
        r"read|fetch|locate|repeat|compare|what|which|how\s+much|"
        r"does|do|did|say)\b", text or "", re.IGNORECASE))


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
