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

import asyncio
import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Literal, Optional, Tuple

# Reference detector: ONE shared constant with the validator — the
# round-2 independent review (2026-10-15) found the two hand-mirrored
# phrase sets had drifted and certified reference text as supplied.
from core.factual_change_validation import (
    REFERENCE_PHRASE as _SOURCE_REF_PHRASE,
)

logger = logging.getLogger(__name__)

SCHEMA = "turn-decision-1"

# Requested information SOURCES, represented explicitly (directive
# boundary change #2): a communication-source word is a source the user
# wants consulted, never a reason to refuse resolving the workbook.
_SOURCE_NOUN_RE = re.compile(
    r"\b(e-?mails?|mails?|inbox|threads?|dms?|chats?|messages?|texts?|"
    r"calendar|tickets?|notes?|memos?|letters?|comments?|posts?|"
    # DOCUMENT-STORE VOCABULARY (pristine-J2 false-search finding,
    # 2026-10-12): "Search my documents ..." is a source ask — the
    # documents/files the product ingests and serves are a consultable
    # source the same as mail. Without these nouns the seek-shaped
    # imperative compiled to a bare `converse` op, zero searches ran,
    # and the reply narrated searches that never happened.
    r"documents?|docs?|files?|folders?|drives?|workbooks?|"
    r"spreadsheets?|sheets|pdfs?|knowledge\s?base)\b",
    re.IGNORECASE,
)

#: Authorization verdicts, mirroring the maturity/policy vocabulary.
AUTH_GRANTED = "granted"
AUTH_NEEDS_CONFIRMATION = "needs_confirmation"
AUTH_NEEDS_GRANT = "needs_grant"

_KIND_RESEARCH = "research"
_KIND_LEARNING = "learning"
_KIND_CANVAS_EDIT = "canvas_edit"

# 2026-10-08 Phase-2 interpretation slice: the async entry point proposes
# semantics; this schema version identifies its records beside the
# deterministic turn-decision-1.
INTERPRETATION_SCHEMA = "turn-interpretation-1"

#: Scope-change modes an interpretation may propose. "replace" — a new
#: explicit subject supersedes prior scope; "extend" — an addition
#: ("also check the Flanger"); "subset" — a narrowing ("only check
#: U-22"); "continue" — select the persisted unfinished action;
#: "unresolved" — the interpreter could not establish the request (also
#: the explicit outcome of every degraded path: timeout, malformed
#: output, no available model). An unresolved interpretation NEVER
#: authorizes guessed work — callers keep the deterministic floor.
SCOPE_CHANGES = ("replace", "extend", "subset", "continue", "unresolved")
#: The authoritative interpretation action vocabulary (same kinds the
#: authorization policy and prompt already use).
INTERPRETATION_ACTION_KINDS = (
    "research", "learning", "canvas_edit", "calculation",
    "presentation", "conversation",
)

# A negated edit command. "Research this; don't change the draft" carries
# an edit verb + artifact and would ground an instruction by the verb
# rule alone — the negation governs it and the edit is NOT authorized.
# Shared by BOTH decision paths (sync + interpretation): one policy, not
# two. Live defect class: case-1 T1 explicitly says "Don't change the
# draft yet" and the edit lane must not treat that as a grant.
# NOTE: 'send' is deliberately NOT a negated-EDIT verb: "do not send"
# withholds SHIPPING, not editing — "prepare the draft and do not send"
# still authorizes the edit (2026-10-08 case-1 T_AUTH).
_NEGATED_EDIT_RE = re.compile(
    r"\b(?:don'?t|do\s+not|never|please\s+not)\s+(?:change|edit|update|"
    r"modify|touch|alter|rebuild|rewrite|revise|apply)\b"
    r"|\b(?:don'?t|do\s+not|never)\s+(?:make\s+any|apply\s+any)\s+"
    r"(?:changes?|edits?|updates?|modifications?)\b"
    r"|\bwithout\s+(?:changing|editing|updating|modifying|touching)\b"
    r"|\bleave\s+(?:the\s+|my\s+|this\s+)?[\w\s]{0,30}?"
    r"(?:draft|quote|canvas|it)\s+(?:alone|unchanged|as\s+is|"
    r"untouched|out\s+of\s+it)\b"
    r"|\b(?:draft|quote|canvas)\s+(?:stays|remains)\s+"
    r"(?:as\s+is|unchanged|untouched)\b",
    re.IGNORECASE,
)


def edit_authorization(
    message: str,
    edit_retry_instruction: str = "",
    canvas_id: Optional[str] = None,
) -> tuple:
    """Deterministic edit authorization shared by BOTH decision paths.

    Returns ``(authorization, instruction)``. A canvas edit is GRANTED
    only by the user's own command in this turn (or a retry of a
    previously authorized edit) — and a NEGATED command ("don't change
    the draft") is not a command. Model-proposed edits from the async
    interpreter are overwritten by this evaluation; the model never
    authorizes anything.
    """
    if not canvas_id:
        return (AUTH_NEEDS_GRANT, "")
    instruction = edit_retry_instruction or _user_grounded_edit_instruction(
        message)
    if not instruction:
        return (AUTH_NEEDS_GRANT, "")
    if _NEGATED_EDIT_RE.search(instruction):
        return (AUTH_NEEDS_GRANT, "")
    return (AUTH_GRANTED, instruction)


def _authorization_for_proposed_action(
    action: Dict[str, Any],
    message: str,
    canvas_id: Optional[str],
) -> str:
    """Deterministic authorization for ONE model-proposed action.

    The async interpreter proposes kinds; this function overwrites any
    model-supplied authorization with the same policy the synchronous
    decision applies. Reads/analysis are granted (they mutate nothing);
    learning needs confirmation; a canvas edit needs the same
    user-grounded, non-negated command the sync path requires.
    """
    kind = str((action or {}).get("kind") or "").strip().lower()
    if kind in (_KIND_RESEARCH, "presentation", "conversation",
                "calculation"):
        return AUTH_GRANTED
    if kind == _KIND_LEARNING:
        return AUTH_NEEDS_CONFIRMATION
    if kind == _KIND_CANVAS_EDIT:
        verdict, _ = edit_authorization(
            message, "", canvas_id=canvas_id)
        return verdict
    return AUTH_NEEDS_GRANT


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
    r"insert|append|sort|rename|paste|prepare|finalize|compose)\b",
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
    r"prices|value|row|rows|entry|field|figure|footer|list|quote|"
    r"quotation)\b",
    re.IGNORECASE,
)

# HEADER-FIELD TARGETS (owner correction 2026-10-10): "fill in To and
# CC" is a legitimate instruction to edit an open email canvas's header
# fields — missing recipient EVIDENCE may need clarification, but the
# instruction is not inherently unauthorized. Deliberately TIGHT
# phrases only: a bare "to" would match "rows 1 to 5".
_HEADER_FIELD_TARGET_RE = re.compile(
    r"\b(?:cc|bcc)\b|"
    r"\bto\s+(?:and\s+)?(?:cc|bcc)\b|"
    r"\b(?:to|cc|bcc)\s+(?:fields?|lines?|recipients?|address(?:es)?)\b",
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
    if not t or not (_ARTIFACT_TARGET_RE.search(t)
                     or _HEADER_FIELD_TARGET_RE.search(t)):
        return ""
    # FILENAMES ARE NOT COMMANDS (2026-09-30 scenario eval): "Copy of
    # Consolidated Price List 2019 - Linmac Update.xlsx" carries
    # 'Update' as part of the NAME — an edit verb inside a filename
    # span never grounds an instruction.
    scrubbed = _FILENAME_SPAN_RE.sub(" ", t)
    if not (_ARTIFACT_TARGET_RE.search(scrubbed)
            or _HEADER_FIELD_TARGET_RE.search(scrubbed)):
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


#: L2 (2026-10-18; corrected 2026-10-18 after owner review) — continuation
#: evidence references. REQUESTED sources (the F-C2 requirement carriers)
#: only NOMINATE candidates; OBSERVED sources (the supplied retrieval
#: observations) are the only prior evidence. The composer resolves the
#: async interpretation's proposed reference against the observed pool —
#: all eligible matches collected first — and preserves resolved /
#: ambiguous / unresolved states explicitly. Never substring donation,
#: never insertion-order selection.
_EVIDENCE_REQ_PREFIX = "_evidence_requirement_"
_EVIDENCE_OBS_PREFIX = "_retrieval_source_observations_"

#: Observation source families -> the program kind vocabulary.
_OBSERVED_FAMILY_KINDS = {
    "ingested": "document",
    "vector": "document",
    "communication": "email",
    "communications": "email",
    "comms": "email",
}


def _source_identity_key(kind: Any, file_name: Any) -> tuple:
    """Dedupe key by STABLE source identity: the kind plus the complete
    filename (case-folded, whitespace-trimmed, separators preserved).

    The previous alphanumeric-only key concatenated away separators, so
    `approved_records_AB-12.txt` and `approved_records_AB12.txt` merged
    before ambiguity detection and one was silently chosen (owner review
    2026-10-18). Without a stable source ID, the full filename IS the
    identity."""
    return (str(kind or "").strip().lower(),
            str(file_name or "").strip().casefold())


#: Descriptive glue words that carry no identity constraint (articles,
#: prepositions, possessives). Dropped from references; a source NAME is
#: matched on its remaining tokens.
_REFERENCE_STOPWORDS = frozenset({
    "the", "a", "an", "of", "and", "or", "for", "with", "in", "on", "at",
    "to", "from", "by", "my", "our", "your", "their", "its", "this",
    "that", "these", "those",
})

#: EXPLICITLY SUPPORTED descriptive equivalents (owner review 2026-10-18:
#: "restrict any descriptive-word normalization to explicitly supported
#: equivalents, such as record/records"). Nothing else is normalized —
#: identifiers are compared exactly, never stemmed.
_DESCRIPTIVE_EQUIVALENTS = {
    "record": "record", "records": "record",
    "document": "document", "documents": "document",
    "file": "file", "files": "file",
    "report": "report", "reports": "report",
    "sheet": "sheet", "sheets": "sheet",
    "note": "note", "notes": "note",
}


def _is_identifier_token(token: str) -> bool:
    """A token acting as an IDENTIFIER: it carries digits (order number,
    code, version) or is a single character ("A", "7") — its characters
    are part of the identity. Identifier-shaped tokens are never dropped
    as stopwords and always compare exactly (owner review 2026-10-18:
    "A" was deleted by the stopword list and "approved record A" resolved
    to a different file)."""
    return len(token) == 1 or any(ch.isdigit() for ch in token)


def _descriptive_canon(token: str) -> str:
    return _DESCRIPTIVE_EQUIVALENTS.get(token, token)


def _reference_tokens(text: Any) -> List[str]:
    """Token-boundary tokens of a reference.

    Every token is preserved except pure glue words — and a word that
    could act as a source identifier is NEVER dropped merely because it
    also appears in the stopword list ("A"). When the grammatical role is
    uncertain the token stays as a constraint (owner review 2026-10-18)."""
    return [t for t in re.findall(r"[a-z0-9]+", str(text or "").lower())
            if _is_identifier_token(t) or t not in _REFERENCE_STOPWORDS]


def _token_matches(proposed: str, name_token: str) -> bool:
    """Boundary-preserving token comparison.

    Identifiers (tokens carrying digits) compare EXACTLY — "ab12" never
    matches "ab12s"; "381" never matches "6603". Descriptive words
    compare through the explicit equivalence table only ("record" matches
    "records"); no stemming, no plural stripping of arbitrary tokens."""
    if _is_identifier_token(proposed) or _is_identifier_token(name_token):
        return proposed == name_token
    return _descriptive_canon(proposed) == _descriptive_canon(name_token)


def session_observed_sources(
    session: Optional[Dict[str, Any]], limit: int = 8,
) -> List[Dict[str, Any]]:
    """The conversation's OBSERVED evidence sources — supplied retrieval
    observations only (never requirement carriers; a request nominates,
    it does not establish evidence). Bounded and deduped."""
    if not isinstance(session, dict):
        return []
    entries: List[Dict[str, Any]] = []
    for key in [k for k in session
                if str(k).startswith(_EVIDENCE_OBS_PREFIX)][-8:]:
        try:
            value = session.get(key)
        except Exception:  # noqa: BLE001 — carriers are best-effort
            continue
        if not isinstance(value, list):
            continue
        execution_id = str(key)[len(_EVIDENCE_OBS_PREFIX):]
        for obs in value:
            if not isinstance(obs, dict):
                continue
            kind = _OBSERVED_FAMILY_KINDS.get(
                str(obs.get("source") or "").strip().lower(), "")
            name = str(obs.get("file_name")
                       or obs.get("title") or "").strip()
            if kind and name:
                entries.append({"kind": kind, "file_name": name,
                                "execution_id": execution_id})
    out: List[Dict[str, Any]] = []
    seen = set()
    for entry in reversed(entries):
        dedupe_key = _source_identity_key(entry["kind"],
                                          entry["file_name"])
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        out.append(entry)
        if len(out) >= limit:
            break
    return out


def session_requested_sources(
    session: Optional[Dict[str, Any]], limit: int = 8,
) -> List[Dict[str, Any]]:
    """The conversation's REQUESTED sources (requirement carriers) —
    nominations for the interpreter, never prior evidence."""
    if not isinstance(session, dict):
        return []
    out: List[Dict[str, Any]] = []
    seen = set()
    for key in [k for k in session
                if str(k).startswith(_EVIDENCE_REQ_PREFIX)][-8:]:
        try:
            value = session.get(key)
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(value, dict):
            continue
        execution_id = str(key)[len(_EVIDENCE_REQ_PREFIX):]
        identity = value.get("identity") if isinstance(
            value.get("identity"), dict) else {}
        name = str(identity.get("file_name") or "").strip()
        kinds = [str(k or "").strip().lower()
                 for k in (value.get("sources") or [])
                 if str(k or "").strip()]
        for kind in (kinds or [""]):
            dedupe_key = _source_identity_key(kind, name)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            out.append({"kind": kind, "file_name": name,
                        "execution_id": execution_id})
            if len(out) >= limit:
                return out
    return out


def session_evidence_sources(
    session: Optional[Dict[str, Any]], limit: int = 8,
) -> List[Dict[str, Any]]:
    """Combined view for the INTERPRETATION PROMPT only: observed sources
    first (``observed: True``), then requested nominations
    (``observed: False``). Never used for resolution."""
    observed = [dict(e, observed=True)
                for e in session_observed_sources(session, limit)]
    requested = [dict(e, observed=False)
                 for e in session_requested_sources(session, limit)]
    seen = {_source_identity_key(e["kind"], e["file_name"])
            for e in observed}
    combined = list(observed)
    for entry in requested:
        key = _source_identity_key(entry["kind"], entry["file_name"])
        if key in seen:
            continue
        seen.add(key)
        combined.append(entry)
        if len(combined) >= limit:
            break
    return combined


def _reference_candidates(
    proposed: str, observed: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """ALL observed sources a reference could mean — collected before any
    decision (zero / one / many). A canonical kind resolves to the
    observed sources of that family; a name resolves by boundary-
    preserving token containment: EVERY reference token (short names and
    identifiers included) must match a distinct name token."""
    from core.action_program import normalize_source_kind

    text = str(proposed or "").strip()
    if not text:
        return []
    # EXACT FULL IDENTITY first (owner review 2026-10-18): a proposal that
    # IS a source's complete filename resolves to it directly — no token
    # games, separators and identifiers preserved.
    exact = [e for e in observed or []
             if str(e.get("file_name") or "").strip().casefold()
             == text.casefold()]
    if exact:
        return exact
    kind = normalize_source_kind(text)
    if kind:
        return [e for e in observed or []
                if str(e.get("kind") or "") == kind]
    tokens = _reference_tokens(text)
    if not tokens:
        return []
    matches: List[Dict[str, Any]] = []
    for entry in observed or []:
        name_tokens = _reference_tokens(entry.get("file_name"))
        if len(name_tokens) < len(tokens):
            continue
        available = list(name_tokens)
        ok = True
        for token in tokens:
            hit = next((nt for nt in available
                        if _token_matches(token, nt)), None)
            if hit is None:
                ok = False
                break
            available.remove(hit)
        if ok:
            matches.append(entry)
    return matches


#: A request can NAME a source by description instead of by filename
#: ("the approved record", "the same document"). This is not a source
#: KIND; it is a reference to an antecedent the conversation has already
#: observed. The deterministic floor resolves it against the observed
#: pool with the SAME collector used for interpretation proposals, so a
#: degraded interpretation cannot erase an explicitly named, unambiguous
#: continuation.
_SOURCE_REFERENCE_RE = re.compile(
    r"\b(?:the|that|this|same|my|our|your|their|its)\s+"
    r"((?:[A-Za-z0-9][A-Za-z0-9&'’._-]*\s+){0,3}?)"
    r"(records?|documents?|files?|reports?)\b",
    re.IGNORECASE,
)
#: Descriptors that carry no identity constraint in a source reference.
#: These are participation/attachment modifiers, not names — the same
#: distinction `_REFERENCE_STOPWORDS` draws for glue words.
_SOURCE_REFERENCE_MODIFIERS = frozenset({
    # Attachment/participation verbs do not identify a document; temporal
    # or versioning adjectives ("original", "latest", "current") DO and
    # must stay in the identity phrase.
    "uploaded", "attached", "enclosed", "provided", "supplied", "shared",
    # A back-reference marker, not an identity token: "the same document"
    # must resolve like "the document".
    "same",
})
_SOURCE_REFERENCE_KIND_TOKENS = frozenset({
    "record", "records", "document", "documents", "file", "files",
    "report", "reports",
})
#: Request nouns that name the same evidence family but are not all in the
#: program's canonical kind vocabulary. Used ONLY to compare a floor
#: capture with a resolved reference; it never selects a source.
_SOURCE_FAMILY_ALIASES = {
    "file": "document", "files": "document", "doc": "document",
    "docs": "document", "pdf": "document", "pdfs": "document",
    "document": "document", "documents": "document",
    "record": "record", "records": "record",
    "email": "email", "emails": "email", "mail": "email",
    "mails": "email", "inbox": "email",
    "thread": "thread", "threads": "thread",
    "spreadsheet": "spreadsheet", "spreadsheets": "spreadsheet",
    "workbook": "spreadsheet", "workbooks": "spreadsheet",
    "sheet": "spreadsheet",
}
#: Families a BARE back-reference ("the record", "the file") may bind.
#: A user's "record" commonly means an ingested document, never an email;
#: "file"/"document"/"report" stay in the document family. A family noun
#: is a constraint, not a wildcard over every observed source.
_BACKREF_FAMILIES = {
    "record": frozenset({"record", "document"}),
    "records": frozenset({"record", "document"}),
    "file": frozenset({"document"}),
    "files": frozenset({"document"}),
    "document": frozenset({"document"}),
    "documents": frozenset({"document"}),
    "report": frozenset({"document"}),
    "reports": frozenset({"document"}),
}


def _source_family_key(source: Any) -> str:
    key = str(source or "").strip().casefold()
    try:
        from core.action_program import normalize_source_kind

        kind = normalize_source_kind(key)
    except Exception:  # noqa: BLE001 — comparison helper only
        kind = ""
    return kind or _SOURCE_FAMILY_ALIASES.get(key, key)


def _request_source_reference_phrases(message: str) -> List[str]:
    """Named source references in the request, as identity phrases.

    Only the nearest determiner-led phrase ending in a source noun is
    kept ("the approved record"), with attachment/participation modifiers
    removed. Conjunctions and punctuation break the phrase, so
    "the draft, and ... the approved record" yields the latter, not a
    merged descriptor."""
    phrases: List[str] = []
    seen = set()
    text = str(message or "")
    for match in _SOURCE_REFERENCE_RE.finditer(text):
        descriptor_tokens = [
            token for token in re.findall(
                r"[A-Za-z0-9][A-Za-z0-9&'’._-]*", match.group(1))
            if token.casefold() not in _SOURCE_REFERENCE_MODIFIERS
            and token.casefold() not in _REFERENCE_STOPWORDS]
        phrase_tokens = [*descriptor_tokens, match.group(2).casefold()]
        # Preserve a trailing identifier constraint ("approved record A",
        # "approved records AB-12", "approved record 381"). Only a
        # digit-bearing token or a single capital letter qualifies; an
        # ordinary following word is not part of the name.
        tail = re.match(
            r"\s*(?:[\(\[]\s*['\"]?|#\s*)?"
            r"([A-Za-z0-9][A-Za-z0-9._-]{0,15})\b",
            text[match.end():])
        if tail:
            token = tail.group(1)
            if (any(ch.isdigit() for ch in token)
                    or (len(token) == 1 and token.isalpha()
                        and token.isupper())):
                phrase_tokens.append(token)
        phrase = " ".join(phrase_tokens).strip()
        key = phrase.casefold()
        if phrase and key not in seen:
            seen.add(key)
            phrases.append(phrase)
    return phrases


def _reference_phrase_variants(phrase: str) -> List[str]:
    """Identity-match variants for one named reference.

    The strongest form is tried first. A trailing CONTAINER noun is
    removed only when ANOTHER source noun remains in the phrase
    ("approved records document" -> "approved records"). The sole
    identity noun is never stripped: "approved record" must not fall
    through to the bare adjective "approved", which would bind an
    unrelated file such as approved_quotation.pdf."""
    tokens = _reference_tokens(phrase)
    variants: List[str] = []
    if tokens:
        variants.append(" ".join(tokens))
    while (len(tokens) >= 2
           and tokens[-1] in _SOURCE_REFERENCE_KIND_TOKENS
           and any(token in _SOURCE_REFERENCE_KIND_TOKENS
                   for token in tokens[:-1])):
        tokens = tokens[:-1]
        candidate = " ".join(tokens)
        if candidate not in variants:
            variants.append(candidate)
    return variants


def resolve_request_source_reference(
    message: str, session: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Resolve a request's NAMED source against observed evidence.

    Fail-closed by construction:

    * no named reference -> None (the request does not ask for a source);
    * no observed evidence -> None (a request nominates, it does not
      establish evidence);
    * one observed candidate -> resolved;
    * several candidates -> ambiguous, ALL candidates preserved;
    * a named reference with no candidate -> unresolved, the name kept.

    No prior requirement carrier is an antecedent, and no candidate is
    selected by insertion order. This is the deterministic-floor
    counterpart of ``apply_interpretation_references``; it never consumes
    a model proposal, so a degraded interpretation cannot invent a source.
    """
    phrases = _request_source_reference_phrases(message)
    if not phrases:
        return None
    observed = session_observed_sources(session)
    if not observed:
        return None
    from core.action_program import normalize_source_kind

    resolutions: List[Dict[str, Any]] = []
    for phrase in phrases:
        candidates: List[Dict[str, Any]] = []
        for variant in _reference_phrase_variants(phrase):
            candidates = _reference_candidates(variant, observed)
            if candidates:
                break
        bare_kind = (
            len(_reference_tokens(phrase)) == 1
            and phrase.casefold() in _SOURCE_REFERENCE_KIND_TOKENS)
        if not candidates and bare_kind:
            # "the record" / "the same document" / "the file" with no
            # same-family observed source is a BACK-REFERENCE to the
            # conversation's observed evidence — WITHIN the named family.
            # One candidate resolves; several stay ambiguous; a different
            # family (an email for "the record") is never adopted.
            allowed_families = _BACKREF_FAMILIES.get(
                phrase.casefold()) or frozenset({
                    _source_family_key(phrase)})
            candidates = [
                entry for entry in observed
                if _source_family_key(entry.get("kind"))
                in allowed_families]
        resolutions.append({
            "phrase": phrase,
            "kind": normalize_source_kind(phrase),
            "candidates": candidates,
        })
    missing = [r for r in resolutions if not r["candidates"]]
    observed_kinds = sorted({
        str(entry.get("kind") or "") for entry in observed
        if str(entry.get("kind") or "")}) or ["document"]
    if missing:
        return {
            "origin": "deterministic_floor",
            "state": "unresolved",
            "resolved_file": "",
            "resolved_kinds": observed_kinds,
            "phrases": phrases,
            "names": [r["phrase"] for r in missing][:4],
        }
    # Union every candidate before deciding; several distinct files are
    # ambiguity, never a first-match choice.
    distinct: List[Dict[str, Any]] = []
    seen = set()
    for resolution in resolutions:
        for candidate in resolution["candidates"]:
            key = _source_identity_key(
                candidate.get("kind"), candidate.get("file_name"))
            if key in seen:
                continue
            seen.add(key)
            distinct.append(candidate)
    kinds = sorted({
        str(candidate.get("kind") or "") for candidate in distinct
        if str(candidate.get("kind") or "")}) or observed_kinds
    if len(distinct) == 1:
        candidate = distinct[0]
        return {
            "origin": "deterministic_floor",
            "state": "resolved",
            "resolved_file": str(candidate.get("file_name") or ""),
            "resolved_kinds": kinds,
            "phrases": phrases,
            "antecedents": [{
                "kind": candidate.get("kind"),
                "file_name": candidate.get("file_name"),
                "execution_id": candidate.get("execution_id"),
            }],
        }
    return {
        "origin": "deterministic_floor",
        "state": "ambiguous",
        "resolved_file": "",
        "resolved_kinds": kinds,
        "phrases": phrases,
        "candidates": [{
            "kind": candidate.get("kind"),
            "file_name": candidate.get("file_name"),
        } for candidate in distinct][:4],
    }


def apply_interpretation_references(
    decision: Optional[Dict[str, Any]],
    interpretation: Optional[Dict[str, Any]],
    session: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Compose the resolved interpretation's source reference into the
    accepted decision (L2 repair; corrected after owner review).

    The reference is resolved against the conversation's OBSERVED sources
    (supplied retrieval observations). Requirements nominate candidates;
    they are never prior evidence. Decision pattern:

    * one candidate -> adopt its identity (the stash re-resolves it
      against the catalog for the exact identity);
    * several candidates -> preserve the AMBIGUITY (candidates recorded;
      never insertion-order selection);
    * no candidate, name proposal, observed evidence context present ->
      preserve the UNRESOLVED reference (kinds grounded in the observed
      families; the settlement reports the honest non-match);
    * no candidate otherwise (no observed context, or generic-kind-only
      proposals) -> the decision is UNCHANGED: a generic kind describes a
      proposed lookup and cannot prove which record the reference means.

    Guards unchanged: only a RESOLVED interpretation composes; the
    deterministic floor's own references always win; degraded
    interpretations and unresolvable references never invent anything.
    """
    if not isinstance(decision, dict) or not isinstance(
            interpretation, dict):
        return decision
    origin = str(interpretation.get("origin") or "")
    scope_change = str(interpretation.get("scope_change") or "")
    if origin == "unresolved" or scope_change == "unresolved":
        return decision  # degraded: the deterministic floor stays in charge
    refs = decision.get("references")
    if not isinstance(refs, dict):
        refs = {}
    if refs.get("sources") or refs.get("file"):
        return decision  # the floor already carries references
    proposed = [str(s).strip()
                for s in (interpretation.get("sources") or [])
                if str(s or "").strip()][:4]
    if not proposed:
        return decision
    observed = session_observed_sources(session)
    if not observed:
        return decision  # no observed evidence context: nothing to resolve
    from core.action_program import normalize_source_kind

    # RESOLVE EACH PROPOSAL BEFORE AGGREGATING (owner review 2026-10-18):
    # a union that drops an unmatched proposal whenever another proposal
    # resolves silently discards a requested source. Per-proposal states:
    #   resolved      — exactly one observed candidate
    #   ambiguous     — several observed candidates
    #   unresolved    — a NAME proposal with no candidate
    #   no_antecedent — a generic-kind proposal with no candidate
    resolutions: List[Dict[str, Any]] = []
    for proposal in proposed:
        kind = normalize_source_kind(proposal)
        candidates_for = _reference_candidates(proposal, observed)
        if kind:
            state = ("resolved" if len(candidates_for) == 1
                     else "ambiguous" if len(candidates_for) > 1
                     else "no_antecedent")
        else:
            state = ("resolved" if len(candidates_for) == 1
                     else "ambiguous" if len(candidates_for) > 1
                     else "unresolved")
        resolutions.append({"proposal": proposal, "kind": kind,
                            "state": state,
                            "candidates": candidates_for})
    marker: Dict[str, Any] = {
        "origin": "interpretation",
        "proposed": proposed,
    }
    missing_proposals = [r["proposal"] for r in resolutions
                         if r["state"] in ("unresolved", "no_antecedent")]
    unresolved_proposals = [r["proposal"] for r in resolutions
                            if r["state"] == "unresolved"]
    no_antecedent_proposals = [r["proposal"] for r in resolutions
                               if r["state"] == "no_antecedent"]
    # Kinds: proposal kinds + the observed families (grounding for the
    # unresolved obligation's identity).
    kinds: List[str] = []
    for r in resolutions:
        kind = str(r.get("kind") or "")
        if kind and kind not in kinds:
            kinds.append(kind)
    for entry in observed:
        kind = str(entry.get("kind") or "")
        if kind and kind not in kinds:
            kinds.append(kind)

    def _candidate_records(cands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        seen = set()
        for entry in cands:
            key = _source_identity_key(entry.get("kind"),
                                       entry.get("file_name"))
            if key in seen:
                continue
            seen.add(key)
            out.append({"kind": entry.get("kind"),
                        "file_name": entry.get("file_name"),
                        "execution_id": entry.get("execution_id")})
        return out

    if missing_proposals:
        # A MISSING PROPOSAL NEVER DISAPPEARS (owner review 2026-10-18): an
        # unmatched named source (`unresolved`) AND a requested kind with
        # no observed antecedent (`no_antecedent`, e.g. `email` when only
        # documents were observed) both block adoption — the composition
        # preserves the missing obligation instead of silently resolving
        # to whatever another proposal matched.
        if not kinds:
            return decision
        marker.update({
            "state": "unresolved",
            "resolved_kinds": kinds,
            "resolved_file": "",
            "names": missing_proposals,
            "no_antecedent": no_antecedent_proposals,
        })
        new_refs = dict(refs)
        new_refs["sources"] = kinds
        new_refs["continuation_evidence"] = marker
        composed = dict(decision)
        composed["references"] = new_refs
        return composed
    # No unresolved proposal: the distinct candidate files decide.
    # Several distinct files (from ambiguous proposals or from several
    # resolved proposals) must CLARIFY — the downstream contract carries
    # one file, so nothing is collapsed to a first filename.
    candidate_files = _candidate_records(
        [c for r in resolutions for c in r["candidates"]])
    if len(candidate_files) == 1:
        candidate = candidate_files[0]
        kinds_resolved = [str(candidate.get("kind") or "document")]
        file_name = str(candidate.get("file_name") or "")
        marker.update({
            "state": "resolved",
            "resolved_kinds": kinds_resolved,
            "resolved_file": file_name,
            "antecedents": [candidate],
        })
        new_refs = dict(refs)
        new_refs["sources"] = kinds_resolved
        new_refs["file"] = {"file_name": file_name}
        new_refs["continuation_evidence"] = marker
        composed = dict(decision)
        composed["references"] = new_refs
        return composed
    if len(candidate_files) > 1:
        marker.update({
            "state": "ambiguous",
            "resolved_kinds": kinds,
            "resolved_file": "",
            "candidates": candidate_files[:4],
        })
        new_refs = dict(refs)
        new_refs["sources"] = kinds or ["document"]
        new_refs["continuation_evidence"] = marker
        composed = dict(decision)
        composed["references"] = new_refs
        return composed
    # No candidates anywhere: generic-kind-only proposals never nominate
    # an antecedent; the decision is unchanged.
    return decision


#: Imperative work that makes a turn MORE than a bounded read-only
#: continuation. A deterministic fast path must never skip planning for a
#: request that also mutates, sends, schedules, or submits. "draft" is
#: deliberately absent: it is the ARTIFACT the S7 ask compares, not a verb.
_COMPOUND_ACTION_VETO_RE = re.compile(
    # A transitive action verb followed by a determiner/pronoun object
    # ("send it", "updated the draft", "sending it"). An inflected form
    # used as an ADJECTIVE ("the updated draft") does not match because
    # no object follows.
    r"\b(?:updat(?:e|es|ed|ing)|edit(?:s|ed|ing)?|"
    r"chang(?:e|es|ed|ing)|set|sets|setting|apply|applies|applied|"
    r"applying|send|sends|sent|sending|creat(?:e|es|ed|ing)|"
    r"add|adds|added|adding|remov(?:e|es|ed|ing)|"
    r"delet(?:e|es|ed|ing)|writ(?:e|es|ten|ing)|"
    r"schedul(?:e|es|ed|ing)|book|books|booked|booking|"
    r"pay|pays|paid|paying|submit|submits|submitted|submitting|"
    r"upload|uploads|uploaded|uploading|remember|remembers|remembered|"
    r"remembering|learn|learns|learned|learning|"
    r"replac(?:e|es|ed|ing)|correct(?:s|ed|ing)?|fix(?:es|ed|ing)?)\b"
    r"\s+(?:the|a|an|this|that|my|our|your|their|its|it|them|him|her|"
    r"me|us)\b"
    # A determinerless imperative still names an artifact object: "update
    # draft", "send draft", "add terms". An inflected ADJECTIVE
    # ("updated draft") is not in this verb list.
    r"|\b(?:update|edit|change|set|apply|send|create|add|remove|delete|"
    r"write|schedule|book|pay|submit|upload|replace|correct|fix)\b\s+"
    r"(?:draft|document|email|message|summary|terms?|price|prices|row|"
    r"rows|field|fields|footer|list|quote|quotation|canvas|sheet|slide|"
    r"text|copy|content|subject|body|table)\b"
    # A creative/build verb can take a bare or lightly qualified object
    # ("prepare summary", "prepare short summary"). "on the draft" is not
    # a verb use.
    r"|\b(?:draft|prepare|compose|write|rewrite|revise|adjust|insert|"
    r"replace|correct|fix)\b\s+"
    r"(?:a|an|the|my|our|your|it|this|that|summary|reply|email|"
    r"message|paragraph|section|terms?|name|short|new|brief|final|"
    r"clean)\b"
    # A mutation/send verb with ANY object is still an additional
    # obligation. This is the general action clause the obligation
    # extractor records; it is not a phrase-specific blacklist.
    r"|\b(?:insert|append|prepend|send|submit|upload|schedule|book|"
    r"pay|create|write|remove|delete|add)\b\s+\w+",
    re.IGNORECASE,
)


def deterministic_continuation_ready(
    message: str,
    session: Optional[Dict[str, Any]],
    decision: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """The bounded shape whose facts do not need a model interpretation.

    Ready only when ALL of the following hold:

    * the request is comparison-shaped, seek-shaped, and carries exactly
      one canonical typed field;
    * it names a source by description and that source resolves to
      exactly ONE observed antecedent;
    * it contains no mutation/send/schedule obligation;
    * the deterministic decision proposed no action beyond conversation
      or research.

    The caller may use these facts immediately, with at most a bounded
    optional model refinement: the named reference and the typed field
    are the request contract, and the existing comparison renderer
    consumes them. Anything broader, ambiguous, unresolved, or mixed
    stays on the normal interpretation path.
    """
    text = str(message or "")
    if not text.strip() or _COMPOUND_ACTION_VETO_RE.search(text):
        return None
    if not _looks_seek_shaped(text):
        return None
    try:
        # The accepted assignment/obligation table is the authority: any
        # additional mutation/send/insertion clause means the request is
        # more than the bounded read-only continuation.
        _obligations = extract_request_assignments(text)
        if (_obligations.get("unresolved_additions")
                or _obligations.get("additional_actions")):
            return None
    except Exception:  # noqa: BLE001 — fail closed on the fast path
        return None
    try:
        from core.workbook_read_artifact import (
            accepted_comparison_scope, comparison_request_shaped,
            extract_field_requests,
        )

        if not comparison_request_shaped(text):
            return None
        fields = extract_field_requests([text])
        # Only a NARROW request may skip the model. A genuinely broad
        # follow-up keeps its whole-document obligation on the normal
        # interpretation path (and the degraded fallback if that model is
        # unavailable).
        if accepted_comparison_scope(
                {"requested_fields": fields, "constraints": []}, text):
            return None
    except Exception:  # noqa: BLE001 — the fast path is optional
        return None
    if len(fields) != 1:
        return None
    resolved = resolve_request_source_reference(text, session)
    if not resolved or str(resolved.get("state") or "") != "resolved":
        return None
    if isinstance(decision, dict):
        refs = decision.get("references")
        refs = refs if isinstance(refs, dict) else {}
        if refs.get("file"):
            # A specific floor file owns the source identity; the named
            # reference must not silently replace it.
            return None
        floor_families = {
            _source_family_key(source)
            for source in (refs.get("sources") or []) if str(source)}
        resolved_families = {
            _source_family_key(kind)
            for kind in (resolved.get("resolved_kinds") or []) if str(kind)}
        phrase_families = {
            _source_family_key(token)
            for phrase in (resolved.get("phrases") or [])
            for token in _reference_tokens(phrase)}
        if floor_families - resolved_families - phrase_families:
            # Another source family is part of the request ("also check
            # my email"); the named-record fast path cannot account for it.
            return None
        kinds = {
            str(action.get("kind") or "")
            for action in (decision.get("requested_actions") or [])
            if isinstance(action, dict) and action.get("kind")
        }
        if kinds - {_KIND_RESEARCH, "conversation"}:
            return None
    return {"reference": resolved, "fields": fields}


def apply_degraded_continuation_references(
    decision: Optional[Dict[str, Any]],
    interpretation: Optional[Dict[str, Any]],
    session: Optional[Dict[str, Any]],
    message: str = "",
    *,
    fill_missing_source: bool = False,
) -> Optional[Dict[str, Any]]:
    """Compose the request's named source when the model did not.

    Two entry conditions:

    * the semantic interpretation is unresolved/absent (the degraded
      path); or
    * ``fill_missing_source`` is set and the resolved record left NO
      reference marker. A schema-valid record with ``sources=[]`` made no
      source decision; a generic floor capture ("document") is a
      nomination, not a model decision. The request's own named reference
      is still the contract.

    A model that supplied a resolved/ambiguous/unresolved marker is
    respected. A specific floor file is preserved; a named reference to a
    different file becomes an unresolved mixed marker so the receipt
    cannot certify the whole request from the floor file alone.

    Fail-closed: no named reference, no observed evidence, or several
    candidates composes nothing (or preserves ambiguity); no prior
    requirement carrier is evidence, and no candidate is selected by
    insertion order.
    """
    if not isinstance(decision, dict):
        return decision
    resolved_interpretation = False
    if isinstance(interpretation, dict):
        origin = str(interpretation.get("origin") or "")
        scope_change = str(interpretation.get("scope_change") or "")
        resolved_interpretation = (
            origin != "unresolved" and scope_change != "unresolved")
        if resolved_interpretation and not fill_missing_source:
            return decision
    text = message or str(decision.get("message") or "")
    if not _looks_seek_shaped(text):
        # A conversational mention ("the approved record was helpful") is
        # not an evidence request; do not manufacture an obligation.
        return decision
    refs = decision.get("references")
    refs = refs if isinstance(refs, dict) else {}

    def _compose(marker: Dict[str, Any]) -> Dict[str, Any]:
        composed = dict(decision)
        new_refs = dict(refs)
        new_refs["continuation_evidence"] = marker
        composed["references"] = new_refs
        provenance = dict(composed.get("provenance") or {})
        signals = list(provenance.get("signals") or [])
        signals.append(
            "degraded_source_reference_%s"
            % str(marker.get("state") or "unresolved"))
        provenance["signals"] = signals
        composed["provenance"] = provenance
        return composed

    # AN ADDITIONAL ACTION OBLIGATION BLOCKS READ-ONLY COMPLETION even
    # when the model resolved a source or the source itself resolves.
    # The existing assignment/obligation table is the authority; this is
    # not a phrase list. The marker reuses the request-bound unresolved
    # identity, so every settlement path sees unfinished work.
    try:
        _actions = extract_request_assignments(text).get(
            "additional_actions") or []
    except Exception:  # noqa: BLE001 — the obligation extractor is total
        _actions = []
    if _actions:
        return _compose({
            "origin": "deterministic_floor",
            "state": "unresolved",
            "resolved_file": "",
            "resolved_kinds": [],
            "phrases": [str(a.get("text") or "")[:120]
                        for a in _actions][:4],
            "names": [str(a.get("text") or "")[:120]
                      for a in _actions][:4],
            "unresolved_reason": "additional_action",
        })
    if resolved_interpretation and refs.get("continuation_evidence"):
        # The model made a source decision (including an honest
        # unresolved/ambiguous one); do not overwrite it. A generic floor
        # capture without a marker is only a nomination and may be
        # refined below; a specific floor file is preserved by the
        # mixed-marker branch.
        return decision
    resolved = resolve_request_source_reference(text, session)
    if not resolved:
        return decision

    def _mixed_marker(reason: str) -> Dict[str, Any]:
        marker = dict(resolved)
        marker.update({
            "state": "unresolved",
            "resolved_file": "",
            "mixed_source_families": reason,
            "names": list(
                resolved.get("names")
                or resolved.get("phrases")
                or ["the named source"])[:4],
        })
        return marker

    kinds = [
        str(kind) for kind in (resolved.get("resolved_kinds") or [])
        if str(kind)] or ["document"]
    resolved_families = {
        _source_family_key(kind) for kind in kinds}
    floor_sources = {
        str(source) for source in (refs.get("sources") or []) if str(source)}
    floor_families = {
        _source_family_key(source) for source in floor_sources}
    phrase_families = {
        _source_family_key(token)
        for phrase in (resolved.get("phrases") or [])
        for token in _reference_tokens(phrase)}

    if refs.get("file"):
        floor_file = refs.get("file") if isinstance(
            refs.get("file"), dict) else {}
        floor_name = str(
            floor_file.get("file_name") or floor_file.get("name") or "")
        if (str(resolved.get("state") or "") == "resolved"
                and floor_name
                and str(resolved.get("resolved_file") or "").casefold()
                == floor_name.casefold()):
            return decision
        # Preserve the floor file but record the named reference as an
        # unresolved mixed obligation. The requirement identity prefers
        # this marker over the file, so the turn cannot complete from the
        # floor file alone.
        return _compose(_mixed_marker("floor_file_and_named_reference"))

    if floor_families - resolved_families - phrase_families:
        # The turn names ANOTHER source family ("also check my email").
        # Preserve that obligation but mark the named reference unresolved:
        # the receipt must not certify the whole request from one family.
        return _compose(_mixed_marker("additional_source_family"))

    composed = dict(decision)
    new_refs = dict(refs)
    # Preserve the floor's own source vocabulary ("documents") while the
    # named reference supplies the file identity. Only a completely empty
    # floor capture needs the resolved kind.
    new_refs["sources"] = sorted(floor_sources) if floor_sources else sorted(
        resolved_families)
    if str(resolved.get("state") or "") == "resolved":
        file_name = str(resolved.get("resolved_file") or "")
        if file_name:
            new_refs["file"] = {"file_name": file_name}
    new_refs["continuation_evidence"] = resolved
    composed["references"] = new_refs
    provenance = dict(composed.get("provenance") or {})
    signals = list(provenance.get("signals") or [])
    signals.append(
        "degraded_source_reference_%s"
        % str(resolved.get("state") or "unresolved"))
    provenance["signals"] = signals
    composed["provenance"] = provenance
    return composed


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
        # Authorization via the SHARED deterministic evaluation (the same
        # rule the async interpreter's proposals are overwritten by):
        # a user-grounded command grants, a NEGATED command ("don't
        # change the draft") does not, everything else needs a grant.
        _auth, _instruction = edit_authorization(
            t, edit_retry_instruction, canvas_id=canvas_id)
        actions.append({
            "kind": _KIND_CANVAS_EDIT,
            "target_canvas": str(canvas_id),
            "nomination": edit_nomination,
            "user_grounded_instruction": _instruction or None,
            "authorization": _auth,
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


def extract_request_assignments(
    message: str,
) -> Dict[str, Any]:
    """The request's OWN assignments, deterministically extracted.

    "update/set/change <target> to <value>" → an accepted assignment
    (the user authored the new value in the instruction). "add <label>"
    and "use the ... from <somewhere>" phrases → unresolved obligations:
    the value must come from records, systems, or the user — the request
    does not supply it. This is the ACCEPTED ASSIGNMENT table the
    factual-change validator checks proposed edits against (an LLM's
    assertion that a change is grounded is not its evidence; the
    instruction's own assignment is)."""
    import re as _re

    text = str(message or "")
    assignments: List[Dict[str, Any]] = []
    unresolved: List[Dict[str, Any]] = []
    source_refs: List[str] = []

    def _is_source_reference(value: str) -> bool:
        """The value span POINTS at where a fact lives instead of stating
        the fact ("the exact number from our records", "see the attached
        schedule", "the supplier's quoted date"). Such a span is an
        unresolved source reference — recording it as an explicit
        assignment would let the plan certify its own echo as a supplied
        value. Detection uses the SHARED REFERENCE_PHRASE constant
        (factual_change_validation, imported at module level), so the
        extractor and the validator can never drift apart on what counts
        as a reference."""
        return bool(_SOURCE_REF_PHRASE.search(value))

    for m in _re.finditer(
            r"(?:update|set|change)\s+(?:the\s+)?"
            r"(?P<target>[a-z0-9][a-z0-9 /'-]{1,60}?)\s+to\s+"
            r"(?P<value>[^;\n]+?)(?=[.;](?:\s|$)|$)",
            text, _re.IGNORECASE):
        value = m.group("value").strip().rstrip(".")
        if not value:
            continue
        if _is_source_reference(value):
            # A source reference in the VALUE position: the target is
            # real, the value is an obligation to resolve — recorded as
            # unresolved, never as an explicit assignment.
            unresolved.append({
                "target": _norm_target(m.group("target")),
                "reference": value,
            })
            continue
        assignments.append({
            "target": _norm_target(m.group("target")),
            "value": value,
            "span": list(m.span()),
        })
    for m in _re.finditer(
            r"\badd\s+(?:the\s+)?(?P<label>[a-z0-9][a-z0-9 /'-]{2,60})",
            text, _re.IGNORECASE):
        label = m.group("label").strip()
        # "add X to THIS/the quotation/the canvas" — a LOCATION, not a
        # value: the value is an unresolved obligation (fetch or ask).
        window = text[m.start():m.end() + 60]
        if _re.search(r"\bto\s+(?:this|the\s+quotation|the\s+canvas)\b",
                      window, _re.IGNORECASE):
            label = _re.split(
                r"\s+to\s+(?:this|the\s+quotation|the\s+canvas)\b",
                label, maxsplit=1, flags=_re.IGNORECASE)[0].strip()
            unresolved.append({"label": label})
    for m in _re.finditer(
            r"\bfrom\s+(our\s+)?(records|systems?|files?|crm|workbook|"
            r"database|hr\s+system|personnel\s+record)\b", text, _re.IGNORECASE):
        source_refs.append(m.group(0))
    # ADDITIONAL ACTION OBLIGATIONS. The accepted assignment spans are
    # already accounted for above; any OTHER mutation/send/insertion
    # clause is an unresolved obligation. The fast read-only path must
    # refuse the whole request, not just the exact object noun.
    occupied = [
        (int(span[0]), int(span[1]))
        for span in (a.get("span") for a in assignments)
        if isinstance(span, (list, tuple)) and len(span) == 2]
    additional_actions: List[Dict[str, Any]] = []
    for m in _COMPOUND_ACTION_VETO_RE.finditer(text):
        if any(start <= m.start() < end or start < m.end() <= end
               for start, end in occupied):
            continue
        snippet = m.group(0).strip()[:120]
        if snippet:
            additional_actions.append({"text": snippet})
    return {
        "assignments": assignments,
        "unresolved_additions": unresolved,
        "additional_actions": additional_actions,
        "source_references": source_refs,
    }


def _norm_target(target: str) -> str:
    import re as _re
    return _re.sub(r"\s+", " ", str(target or "").strip().lower())


def turn_evidence_required(
    decision: Optional[Dict[str, Any]],
) -> Optional[bool]:
    """Does the ACCEPTED request require live evidence for this turn?

    The decision already records this: a research action (source_ask,
    continuation, direct ask, approval resume, evidence back-reference)
    or named references (``references.sources`` / ``references.file``).
    A SELF-CONTAINED edit — the replacement value is supplied in the
    instruction — carries none of those, and its lane must not pay a
    general lookup's latency before its own plan can run.

    Returns True (required), False (not required), or None when the
    decision is absent/unreadable — callers must treat None as "keep
    the existing behavior", never as "not required".
    """
    if not isinstance(decision, dict):
        return None
    for action in decision.get("requested_actions") or []:
        if isinstance(action, dict) and action.get("kind") == _KIND_RESEARCH:
            return True
    refs = decision.get("references")
    if isinstance(refs, dict):
        if refs.get("sources"):
            return True
        if refs.get("file"):
            return True
    # A SOURCE REFERENCE IN THE REQUEST CREATES THE EVIDENCE OBLIGATION
    # (owner directive): "use the value from our records" names a
    # consultable source the same as "the workbook" does — the absence of
    # a research action must not prove the evidence unnecessary.
    try:
        message = str(decision.get("message") or "")
        _obligations = extract_request_assignments(message)
        if (_obligations.get("source_references")
                or _obligations.get("additional_actions")):
            return True
    except Exception:  # noqa: BLE001 — additive; never blocks the lane
        pass
    return False


def turn_presentation_only(
    decision: Optional[Dict[str, Any]],
) -> bool:
    """Whether the ACCEPTED request is PRESENTATION-ONLY over the
    attached artifact: a presentation action was granted, no edit or
    research action was requested, and the request carries no live-
    evidence requirement (``turn_evidence_required`` is False — no
    sources, no file, no source references in the words).

    The recorded-outcome resolver consumes this to classify a turn that
    presents the artifact it was handed and whose accepted request
    names nothing live to go fetch (owner directive 2026-10-15, the J6
    T2 envelope defect: a correct, delivered canvas comparison resolved
    success=false / outcome_unconfirmed in every recorded run because
    no recorded delivery fact existed for a presentation). The guard
    NEVER blesses an answer's wording — narration agreement stays with
    the fabrication layer. False for absent or unreadable decisions
    (callers treat it as "not presentation-only" — the conservative
    direction)."""
    if not isinstance(decision, dict):
        return False
    actions = [action for action in decision.get("requested_actions") or []
               if isinstance(action, dict)]
    kinds = {str(action.get("kind") or "") for action in actions}
    if _KIND_CANVAS_EDIT in kinds or _KIND_RESEARCH in kinds:
        return False
    if "presentation" not in kinds:
        return False
    return turn_evidence_required(decision) is False


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


# ---------------------------------------------------------------------------
# ASYNC STRUCTURED INTERPRETATION (2026-10-08 Phase-2 slice)
#
# One semantic interpretation per request, through the established
# LLMService structured-generation path (catalog-served model selection,
# cost-priority "planning" task class) with the cheap-NLU operational
# envelope: hard timeout, consecutive-failure breaker, telemetry, and an
# explicit UNRESOLVED outcome for every degraded path — an unavailable
# model never yields guessed work.
#
# Division of labor (unchanged from the module's design rules): the
# interpretation PROPOSES actions/subjects/sources/fields/constraints and
# a scope-change mode; deterministic POLICY overwrites every proposed
# authorization (see _authorization_for_proposed_action); the catalog
# layer (agent_file_context) stays authoritative for file identity; and
# execution proves. The synchronous build_turn_decision interface is
# untouched and remains the floor.
# ---------------------------------------------------------------------------
# 12s (not cheap-nlu's 6): the structured call can pay one 402 round
# trip on a credit-dead ranked route BEFORE the healthy gateway answers
# (live 2026-10-08: interpretation dispatched to opencode-go at ~6s and
# timed out at the wall). Still far under the turn's reply budget.
# 12s was the original bound. The 2026-10-19 diagnostic (scratch replay of
# the actual S3/S7 payloads on the frozen route) measured the first valid
# S7 interpretation record at ~58s on the BPC-selected compatible route
# (qwen3.8-flash; reasoning switch accepted, though the route still
# reported hidden reasoning tokens), while the reasoning-mandatory
# glm-5.3-flash path never validated within a 90s window. This is a
# BOUNDED, EVALUATED increase (65s) that fits the ordinary 95s turn budget
# with ~30s left for the reply leg; the served attempt measures total turn
# latency against the user-usable goal.
_INTERPRET_TIMEOUT_S = float(os.getenv("ATOM_TURN_INTERPRET_TIMEOUT_S", "65"))
_INTERPRET_BREAKER_MAX = int(os.getenv("ATOM_TURN_INTERPRET_BREAKER", "3"))

#: Structured-output budget for the turn interpretation. Derived from
#: REPRESENTATIVE valid records, not a tiny arbitrary cap: the attempt-1
#: S7 record (2 sources, 2 actions, 2 subjects, 1 field) is ~1,163
#: cl100k tokens; a multiple-source/long-filename record (8 sources incl.
#: a 512-char filename, 8 subjects, 3 actions with 4 subjects each,
#: 8 requested fields, 8 constraints) is ~3,385 cl100k tokens. 5,500
#: leaves ~1.6x headroom over the larger representative record. This is
#: a ceiling, not a target; other structured callers keep the handler's
#: 6,000 default. The intended latency lever on reasoning-capable routes
#: is disable_reasoning; providers that mandate reasoning keep the
#: bounded recovery and are measured by the served run.
_INTERPRET_OUTPUT_BUDGET_TOKENS = 5500
_interpret_failures = 0
_interpret_breaker_until = 0.0
_interpret_metrics: Dict[str, Any] = {
    "ok": 0, "unresolved": 0, "timeout": 0, "error": 0, "skipped": 0,
    "stage_budget_exhausted": 0, "max_ms": 0.0, "sum_ms": 0.0}
_interpretation_metrics_lock = threading.Lock()

#: Scratch-only capture of the producer's raw scope/action shape before
#: normalization (enabled by ATOM_TURN_INTERPRET_CAPTURE=1). Records no
#: message/source content and no credentials.
_interpret_capture: List[Dict[str, Any]] = []
_interpret_capture_request_id = ""
_last_interpret_capture: Dict[str, Any] = {}
_interpret_capture_lock = threading.Lock()


def _capture_enabled() -> bool:
    return os.getenv("ATOM_TURN_INTERPRET_CAPTURE", "0").lower() in (
        "1", "on", "true", "yes")


def reset_interpret_capture(request_id: str = "") -> None:
    global _interpret_capture_request_id, _last_interpret_capture
    with _interpret_capture_lock:
        _interpret_capture.clear()
        _interpret_capture_request_id = str(request_id or "")
        _last_interpret_capture = {}


def _record_interpret_capture(
    data: Any, *, phase: str, rejection_reason: str = "",
) -> None:
    """Record a content-free shape sample for the current attempt.

    The last record is always kept in memory so validation failures can
    be classified even when archival capture is disabled. Only recognized
    enum values and placeholders are stored; arbitrary model text never
    enters the record or the log.
    """
    if not isinstance(data, dict):
        return
    scope_present = "scope_change" in data
    raw_scope = data.get("scope_change")
    scope_text = (str(raw_scope).strip().lower()
                  if raw_scope is not None else None)
    if not scope_present:
        scope_value = None
    elif scope_text in SCOPE_CHANGES:
        scope_value = scope_text
    else:
        scope_value = "<invalid>"

    actions = data.get("actions")
    action_list = actions if isinstance(actions, list) else []
    kinds: List[str] = []
    has_missing_kind = False
    has_invalid_kind = False
    for action in action_list[:8]:
        raw_kind = (action.get("kind")
                    if isinstance(action, dict) else None)
        kind = str(raw_kind or "").strip().lower()
        if not kind:
            has_missing_kind = True
            kinds.append("<missing>")
        elif kind in INTERPRETATION_ACTION_KINDS:
            kinds.append(kind)
        else:
            has_invalid_kind = True
            kinds.append("<invalid>")
    record = {
        "request_id": _interpret_capture_request_id,
        "phase": phase,
        "scope_present": scope_present,
        "scope_raw": scope_value,
        "action_count": len(action_list),
        "action_kinds": kinds,
        "has_missing_action_kind": has_missing_kind,
        "has_invalid_action_kind": has_invalid_kind,
        "rejection_reason": rejection_reason,
    }
    global _last_interpret_capture
    with _interpret_capture_lock:
        _last_interpret_capture = dict(record)
        if not _capture_enabled():
            return
        _interpret_capture.append(record)
    try:
        logger.info(
            "[turn-interpretation-capture] %s",
            json.dumps(record, sort_keys=True))
    except Exception:  # noqa: BLE001 — telemetry never raises
        pass


def _last_capture_for(request_id: str) -> Dict[str, Any]:
    with _interpret_capture_lock:
        record = dict(_last_interpret_capture)
    if record and record.get("request_id") == request_id:
        return record
    return {}


def get_interpret_capture() -> List[Dict[str, Any]]:
    with _interpret_capture_lock:
        return [dict(item) for item in _interpret_capture]


def interpretation_enabled() -> bool:
    return os.getenv("ATOM_TURN_INTERPRETATION", "1").lower() not in (
        "0", "off", "false")


def reset_interpretation_for_tests() -> None:
    """Clear breaker + metric state (test-only)."""
    global _interpret_failures, _interpret_breaker_until
    _interpret_failures = 0
    _interpret_breaker_until = 0.0
    for k in ("ok", "unresolved", "timeout", "error", "skipped",
              "stage_budget_exhausted"):
        _interpret_metrics[k] = 0
    _interpret_metrics.update({"max_ms": 0.0, "sum_ms": 0.0})


def _interpretation_unresolved(
    reason: str, message: str, request_id: str,
    deterministic: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "schema": INTERPRETATION_SCHEMA,
        "request_id": request_id,
        "origin": "unresolved",
        "unresolved_reason": reason,
        "message": (message or "")[:500],
        "actions": [],
        "subjects": [],
        "sources": [],
        "requested_fields": [],
        "output_format": "",
        "constraints": [],
        "scope_change": "unresolved",
        "confidence": 0.0,
        # The deterministic decision rides along: an unresolved
        # interpretation leaves the existing floor fully in charge.
        "deterministic_decision": deterministic,
    }


def interpretation_deterministic_continuation(
    message: str,
    request_id: str,
    deterministic: Optional[Dict[str, Any]],
    reference: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """An EXPLICIT non-model interpretation for a bounded continuation.

    This is not a degraded record: the request's own named reference and
    typed field establish the contract, and the deterministic floor has
    already resolved the source against observed evidence. Recording the
    origin honestly (instead of a model attribution) keeps the evidence
    truthful and the turn off the interpretation budget.
    """
    reference = reference if isinstance(reference, dict) else {}
    file_name = str(reference.get("resolved_file") or "")
    kinds = [str(kind) for kind in (reference.get("resolved_kinds") or [])
             if str(kind)] or ["document"]
    return {
        "schema": INTERPRETATION_SCHEMA,
        "request_id": request_id,
        "origin": "deterministic:continuation",
        "unresolved_reason": "",
        "message": (message or "")[:500],
        "actions": [{
            "kind": _KIND_RESEARCH,
            "authorization": AUTH_GRANTED,
            "note": "deterministic read-only continuation",
        }],
        "subjects": [],
        "sources": [file_name] if file_name else kinds,
        "requested_fields": [],
        "output_format": "",
        "constraints": [],
        "scope_change": "continue",
        "confidence": 1.0,
        "deterministic_decision": deterministic,
    }


def interpretation_budget_unresolved(
    message: str,
    request_id: str = "",
    deterministic: Optional[Dict[str, Any]] = None,
    reason: str = "stage_budget_exhausted",
) -> Dict[str, Any]:
    """Request-bound degraded interpretation when the stage has no budget.

    No provider call is made, no action or source is invented, and the
    deterministic decision remains the floor. This is the explicit record
    the outer deadline/caller must preserve instead of ``None``.
    """
    with _interpretation_metrics_lock:
        _interpret_metrics["skipped"] += 1
        _interpret_metrics["stage_budget_exhausted"] += 1
    return _interpretation_unresolved(
        reason, message, request_id, deterministic)


def _interpretation_prompt(
    message: str,
    history: Optional[List[Dict[str, Any]]],
    session: Dict[str, Any],
    context: Dict[str, Any],
) -> str:
    """Compact, structured interpretation context.

    Supplies exactly what the completion guide names: recent
    conversation, persisted unfinished work, applicable teaching
    presence, and catalog summaries (names only — never source bodies,
    never a flattening to the last prompt).
    """
    parts: List[str] = [f"REQUEST: {message or ''}"]
    recent = [
        {"role": str(h.get("role") or "")[:9],
         "text": str(h.get("content") or h.get("message") or "")[:220]}
        for h in (history or [])[-6:]
        if str(h.get("content") or h.get("message") or "").strip()
    ]
    if recent:
        parts.append("RECENT CONVERSATION: " + json.dumps(recent))
    unfinished = _task_objective(session)
    if unfinished:
        parts.append(
            "PERSISTED UNFINISHED WORK: " + json.dumps(unfinished)[:600])
    if context.get("applicable_teaching"):
        parts.append(
            "APPLICABLE TEACHING: "
            + str(context["applicable_teaching"])[:400])
    if context.get("catalog_files"):
        names = [str(n) for n in context["catalog_files"]][:40]
        parts.append("SOURCE CATALOG (names): " + "; ".join(names))
    # L2 (2026-10-18; producer contract corrected 2026-10-19): the
    # conversation's OWN verified evidence sources — the antecedents a
    # continuation ask ("does it still match the approved record?")
    # refers to. Observed evidence, requested nominations and the attached
    # artifact are SEPARATE structured entries: only observed evidence is
    # an antecedent; the attached canvas is the comparison subject/input,
    # never an external lookup.
    attached_artifact: Dict[str, Any] = {}
    _canvas = context.get("canvas") if isinstance(
        context.get("canvas"), dict) else {}
    canvas_id = (context.get("canvas_id") or _canvas.get("canvas_id")
                 or _canvas.get("id"))
    canvas_title = (context.get("canvas_title") or _canvas.get("title")
                    or _canvas.get("name"))
    canvas_summary = context.get("canvas_summary") or _canvas.get("summary")
    if canvas_id:
        attached_artifact["canvas_id"] = str(canvas_id)[:120]
    if canvas_title:
        attached_artifact["title"] = str(canvas_title)[:200]
    if canvas_summary:
        attached_artifact["summary"] = str(canvas_summary)[:600]
    if attached_artifact:
        attached_artifact["role"] = (
            "attached comparison artifact/input; not an external evidence "
            "source")
    prior_sources = session_evidence_sources(session)
    observed_sources = [e for e in prior_sources if e.get("observed")]
    requested_sources = [e for e in prior_sources if not e.get("observed")]

    def _source_entry(entry: Dict[str, Any]) -> Dict[str, str]:
        return {"kind": str(entry.get("kind") or ""),
                "file_name": str(entry.get("file_name") or "")}

    source_references = {
        "observed_evidence": [
            _source_entry(e) for e in observed_sources[:6]],
        "requested_sources": [
            _source_entry(e) for e in requested_sources[:6]],
        "attached_artifact": attached_artifact or None,
    }
    if (source_references["observed_evidence"]
            or source_references["requested_sources"]
            or attached_artifact):
        parts.append(
            "SOURCE REFERENCES (structured JSON): "
            + json.dumps(source_references, ensure_ascii=False))
    try:
        from core.action_program import SOURCE_KINDS

        supported_kinds = ", ".join(SOURCE_KINDS)
    except Exception:  # noqa: BLE001 — vocabulary hint is best-effort
        supported_kinds = (
            "spreadsheet, email, inbox, thread, chat, message, text, "
            "calendar, ticket, note, memo, letter, comment, post, "
            "document, canvas, record, task, web, agent")
    parts.append("SUPPORTED SOURCE KINDS: " + supported_kinds)
    parts.append(
        "Interpret the REQUEST. Propose: actions (research / learning / "
        "canvas_edit / calculation / presentation / conversation — more "
        "than one allowed). Questions and follow-up comparisons are actions "
        "too: propose the applicable read-only action for answering, "
        "presenting, or consulting evidence (research/presentation/"
        "conversation as appropriate). 'continue' describes the relationship "
        "to prior work; it does not replace the action list. If the request "
        "cannot be interpreted, return explicit unresolved scope. A "
        "resolved scope must include at least one action; use an empty "
        "actions list only when scope_change is 'unresolved'. Specify "
        "the FULL subject names exactly as the user "
        "means them, EXTERNAL evidence sources requiring consultation "
        "(if the request names a specific source, copy that source's "
        "complete filename/name exactly; for a prior observed source, copy "
        "the observed filename exactly; only when the request asks for a "
        "source kind without naming a specific source, use one of the "
        "SUPPORTED SOURCE KINDS — prefer the kind shown on the matching "
        "SOURCE REFERENCES observed entry; if several observed sources "
        "could match the request's wording, do not choose one — preserve "
        "the wording; never append explanations, parentheses, or "
        "uncertainty notes; never include the attached draft/canvas as an "
        "external source), the data fields wanted, output format, explicit "
        "constraints (including things the user said NOT to do), and the "
        "requested scope: replace (a new subject supersedes the current "
        "conversation/work), extend (adds items), subset (narrows to some "
        "items), continue (FOLLOW UP on an established conversation "
        "subject — even when the prior turn completed — or resume "
        "persisted unfinished work), or unresolved (the reference is "
        "genuinely ambiguous or cannot be established). A request that "
        "names its own NEW subject unrelated to the established "
        "conversation is 'replace'; a follow-up that refers to the "
        "established subject/antecedent is 'continue' even if no "
        "unfinished work remains. scope_change is REQUIRED and must be "
        "exactly one of those five values; do not map uncertainty to "
        "'continue'. Copy constraint wording from the request; never "
        "invent subjects.")
    return "\n\n".join(parts)


_INTERPRET_SYSTEM = (
    "You interpret one user request for a work system. You propose; "
    "policy decides authorization; you never invent subjects or sources "
    "the user did not name or clearly mean.")


async def interpret_turn_request(
    message: str,
    session: Optional[Dict[str, Any]] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    context: Optional[Dict[str, Any]] = None,
    session_id: str = "",
    request_id: str = "",
    llm_service: Any = None,
) -> Dict[str, Any]:
    """ONE structured semantic interpretation of this request.

    Returns a turn-interpretation-1 record. Every degraded path (feature
    off, breaker open, no model, timeout, malformed output) returns an
    EXPLICIT ``scope_change="unresolved"`` record carrying the
    deterministic decision — callers keep the floor and never execute
    guessed work. Authorization on every proposed action is overwritten
    by the deterministic policy.
    """
    global _interpret_failures, _interpret_breaker_until
    deterministic: Optional[Dict[str, Any]] = None
    try:
        deterministic = build_turn_decision(
            message, session, history, context, session_id=session_id)
    except Exception:  # noqa: BLE001 — the floor is best-effort here
        deterministic = None

    def _unresolved(reason: str) -> Dict[str, Any]:
        return _interpretation_unresolved(
            reason, message, request_id, deterministic)

    if not interpretation_enabled():
        _interpret_metrics["skipped"] += 1
        return _unresolved("feature_disabled")
    if time.time() < _interpret_breaker_until:
        _interpret_metrics["skipped"] += 1
        return _unresolved("breaker_open")

    try:
        from pydantic import BaseModel, ConfigDict, Field, model_validator
    except ImportError:  # pragma: no cover — pydantic always present
        return _unresolved("pydantic_unavailable")

    class _ProposedAction(BaseModel):
        model_config = ConfigDict(hide_input_in_errors=True)
        kind: Literal[
            "research", "learning", "canvas_edit", "calculation",
            "presentation", "conversation",
        ]
        subjects: List[str] = Field(default_factory=list)
        note: str = ""

    class _Interpretation(BaseModel):
        model_config = ConfigDict(hide_input_in_errors=True)
        actions: List[_ProposedAction]
        subjects: List[str] = Field(default_factory=list)
        sources: List[str] = Field(
            default_factory=list,
            description=(
                "External evidence sources requiring consultation. If the "
                "request names a specific source, copy that source's "
                "complete filename/name exactly; for a prior observed "
                "source, copy the observed filename exactly. Only when the "
                "request asks for a source kind without naming a specific "
                "source, use a supported canonical source kind — prefer "
                "the kind shown on the matching observed entry. If several "
                "observed sources could match the request's wording, do "
                "not choose one — preserve the wording. Do not append "
                "explanations, parentheses, or uncertainty notes. Do not "
                "include the attached draft/canvas as an external source."),
        )
        requested_fields: List[str] = Field(default_factory=list)
        output_format: str = ""
        constraints: List[str] = Field(default_factory=list)
        scope_change: Literal[
            "replace", "extend", "subset", "continue", "unresolved"
        ]
        confidence: float = 0.0

        @model_validator(mode="before")
        @classmethod
        def _capture_before_validation(cls, data):
            try:
                _record_interpret_capture(
                    data, phase="pre_validation")
            except Exception:  # noqa: BLE001 — capture is additive
                pass
            return data

        @model_validator(mode="after")
        def _require_action_for_resolved_scope(self):
            if self.scope_change != "unresolved" and not self.actions:
                raise ValueError(
                    "Resolved interpretation requires an explicit action.")
            return self

    if llm_service is None:
        try:
            from core.llm_service import get_llm_service

            llm_service = get_llm_service()
        except Exception as exc:  # noqa: BLE001 — unresolved, not a crash
            logger.debug("interpretation llm service unavailable: %r", exc)
            _interpret_metrics["unresolved"] += 1
            return _unresolved("llm_service_unavailable")

    started = time.perf_counter()
    try:
        from core.llm.pinned_planning import (
            LAST_FAILURE,
            pinned_structured_call,
            resolve_pinned_provider_model,
        )

        # The wrapper converts provider errors to None by contract; keep
        # the interpretation's explicit reason by reading ITS OWN call's
        # published failure (a unique label avoids the shared-dict race
        # with the canvas editor).
        _interpret_label = (
            f"turn interpretation:{request_id or session_id or '-'}")
        LAST_FAILURE.update(kind=None, detail="", label="")
        try:
            reset_interpret_capture(_interpret_label)
        except Exception:  # noqa: BLE001 — capture is additive
            pass

        def _schema_rejection(reason: str) -> Dict[str, Any]:
            _interpret_metrics["unresolved"] += 1
            _emit_interpret(
                "empty" if reason == "no_actions_proposed"
                else "unparseable", reason=reason)
            return _unresolved(reason)

        # ROUTE SELECTION FROM THE 2026-10-19 DIAGNOSTIC: the measured
        # compatible interpretation route accepts the reasoning-disable
        # switch and produced a schema-valid record (the cheap
        # reasoning-mandatory candidate rejected the switch and never
        # validated within 90s). The pin is a preference only — the
        # existing wrapper retries unpinned (excluding the failed pin)
        # when this route yields nothing. Operators can override the
        # measured default through ATOM_TURN_INTERPRET_PIN.
        _interpret_pin = resolve_pinned_provider_model(
            llm_service, "ATOM_TURN_INTERPRET_PIN", "qwen3.8-flash",
            provider="opencode-go")
        result = await asyncio.wait_for(
            pinned_structured_call(
                llm_service,
                prompt=_interpretation_prompt(
                    message, history,
                    session if isinstance(session, dict) else {},
                    context if isinstance(context, dict) else {}),
                response_model=_Interpretation,
                system_instruction=_INTERPRET_SYSTEM,
                task_type="planning",
                temperature=0.0,
                disable_reasoning=True,
                call_kwargs=_interpret_pin or None,
                extra_kwargs={
                    "max_tokens": _INTERPRET_OUTPUT_BUDGET_TOKENS,
                    # MoA would multiply one small interpretation into N
                    # samples + an aggregator when a long prompt is
                    # classified COMPLEX/ADVANCED and ATOM_MOA_ENABLED is
                    # on. This call opts out explicitly; the shared
                    # handler default is unchanged.
                    "allow_moa": False,
                },
                log_label=_interpret_label,
                stage="turn_interpretation",
                execution_id=request_id or session_id or "-",
            ),
            timeout=_INTERPRET_TIMEOUT_S,
        )
        if result is None:
            try:
                _last = _last_capture_for(_interpret_label)
            except Exception:  # noqa: BLE001
                _last = {}
            if _last:
                if not _last.get("scope_present"):
                    return _schema_rejection("missing_scope")
                _captured_scope = str(
                    _last.get("scope_raw") or "").strip().lower()
                if _captured_scope == "unresolved":
                    return _schema_rejection("scope_unresolved")
                if _captured_scope not in SCOPE_CHANGES:
                    return _schema_rejection("invalid_scope")
                if _last.get("has_missing_action_kind"):
                    return _schema_rejection("missing_action_kind")
                if _last.get("has_invalid_action_kind"):
                    return _schema_rejection("invalid_action_kind")
                if not _last.get("action_count"):
                    return _schema_rejection("no_actions_proposed")
        if (result is None
                and LAST_FAILURE.get("label") == _interpret_label
                and LAST_FAILURE.get("kind")):
            if LAST_FAILURE.get("kind") == "deadline_cancelled":
                raise asyncio.TimeoutError()
            raise RuntimeError(
                "structured interpretation failed: "
                f"{LAST_FAILURE.get('kind')}")
    except asyncio.TimeoutError:
        _interpret_failures += 1
        _interpret_metrics["timeout"] += 1
        _note_breaker()
        _emit_interpret("timeout")
        return _unresolved("timeout")
    except Exception as exc:  # noqa: BLE001 — unresolved, not a crash
        _interpret_failures += 1
        _interpret_metrics["error"] += 1
        _note_breaker()
        _emit_interpret("error", error=type(exc).__name__)
        logger.debug("turn interpretation failed: %r", exc)
        return _unresolved("error")

    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    _interpret_metrics["max_ms"] = max(
        _interpret_metrics["max_ms"], latency_ms)
    _interpret_metrics["sum_ms"] += latency_ms

    data = result if isinstance(result, dict) else (
        getattr(result, "model_dump", lambda: {})())
    try:
        _record_interpret_capture(data, phase="post_validation")
    except Exception:  # noqa: BLE001 — capture is additive
        pass
    _scope_present = "scope_change" in data
    _scope_raw_text = str(data.get("scope_change") or "").strip().lower()
    scope_change = _scope_raw_text
    # Near-miss normalization (live 2026-10-08: v4-flash served
    # "replacement"/"narrow" against the enumerated enum): map the
    # obvious variants, everything else stays unresolved — never a
    # guess about the request's semantics.
    _SCOPE_NEAR_MISSES = {
        "replaces": "replace", "replacement": "replace", "new": "replace",
        "narrow": "subset", "narrowing": "subset", "filter": "subset",
        "add": "extend", "adds": "extend", "extension": "extend",
        "additional": "extend", "resume": "continue",
        "continuation": "continue", "same": "continue",
    }
    if scope_change not in SCOPE_CHANGES:
        scope_change = _SCOPE_NEAR_MISSES.get(scope_change, "unresolved")
    _raw_action_value = data.get("actions")
    _all_raw_actions = [
        a if isinstance(a, dict)
        else getattr(a, "model_dump", lambda: {})()
        for a in (_raw_action_value
                  if isinstance(_raw_action_value, list) else [])
    ]
    _action_kinds = [
        str(a.get("kind") or "").strip().lower()
        for a in _all_raw_actions]
    _bad_action_reason = ""
    if any(not kind for kind in _action_kinds):
        _bad_action_reason = "missing_action_kind"
    elif any(kind not in INTERPRETATION_ACTION_KINDS
             for kind in _action_kinds):
        _bad_action_reason = "invalid_action_kind"
    raw_actions = _all_raw_actions[:8]
    if _bad_action_reason or not raw_actions or scope_change == "unresolved":
        if not _scope_present:
            reason = "missing_scope"
        elif _scope_raw_text == "unresolved":
            reason = "scope_unresolved"
        elif (_scope_raw_text not in SCOPE_CHANGES
              and scope_change == "unresolved"):
            reason = "invalid_scope"
        elif _bad_action_reason:
            reason = _bad_action_reason
        elif not raw_actions:
            reason = "no_actions_proposed"
        else:
            reason = "scope_unresolved"
        try:
            _record_interpret_capture(
                data, phase="normalized", rejection_reason=reason)
        except Exception:  # noqa: BLE001
            pass
        _interpret_metrics["unresolved"] += 1
        _emit_interpret(
            "unparseable" if raw_actions else "empty", reason=reason)
        return _unresolved(reason)

    canvas_id = (context or {}).get("canvas_id") or (
        (context or {}).get("canvas") or {}).get("canvas_id")
    actions_out: List[Dict[str, Any]] = []
    for a in raw_actions:
        kind = str(a.get("kind") or "").strip().lower()
        actions_out.append({
            "kind": kind,
            "subjects": [
                str(s)[:200] for s in (a.get("subjects") or [])[:12]
                if str(s).strip()],
            "note": str(a.get("note") or "")[:200],
            # POLICY OVERWRITES THE MODEL: deterministic authorization
            # only — a proposed edit never carries model-granted rights.
            "authorization": _authorization_for_proposed_action(
                {"kind": kind}, message, canvas_id),
        })
    _interpret_failures = 0
    _interpret_metrics["ok"] += 1
    _emit_interpret("ok", latency_ms=latency_ms)
    origin = "llm"
    try:
        served = getattr(result, "_raw_response", None)
        model = getattr(served, "model", None)
        if model:
            origin = f"llm:{str(model)[:80]}"
    except Exception:  # noqa: BLE001 — origin is best-effort
        pass
    return {
        "schema": INTERPRETATION_SCHEMA,
        "request_id": request_id,
        "origin": origin,
        "unresolved_reason": "",
        "message": (message or "")[:500],
        "actions": actions_out,
        "subjects": [
            str(s)[:200] for s in (data.get("subjects") or [])[:16]
            if str(s).strip()],
        "sources": [
            str(s)[:512] for s in (data.get("sources") or [])[:8]
            if str(s).strip()],
        "requested_fields": [
            str(f)[:80] for f in (data.get("requested_fields") or [])[:8]
            if str(f).strip()],
        "output_format": str(data.get("output_format") or "")[:40],
        "constraints": [
            str(c)[:200] for c in (data.get("constraints") or [])[:8]
            if str(c).strip()],
        "scope_change": scope_change,
        "confidence": max(0.0, min(1.0, float(
            data.get("confidence") or 0.0))),
        "deterministic_decision": deterministic,
    }


def _note_breaker() -> None:
    global _interpret_breaker_until
    if _interpret_failures >= _INTERPRET_BREAKER_MAX:
        _interpret_breaker_until = time.time() + 60.0


def _emit_interpret(outcome: str, **extra: Any) -> None:
    try:
        logger.info("[turn-interpretation] %s %s", outcome,
                    " ".join(f"{k}={v}" for k, v in extra.items()))
    except Exception:  # noqa: BLE001 — telemetry must never raise
        pass
