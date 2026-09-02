"""LLM-based canvas editor for the chat path (canvas co-editor panel).

The /canvas/{id} side panel ("Agent Co-Editor") sends /api/chat/message with
the open canvas in ``context`` (canvas_id / canvas_type / canvas_content).
Until now nothing on the chat path consumed it: the reply came from a prompt
that had never seen the canvas, the tool planner is read-only integration
search by design, and the intent router misfiled edit requests (a "tighten
the draft" message became TASK_MANAGEMENT and created a junk local task).

This module is the write-side counterpart of ``core.chat_tool_planner``
(which stays read-only): a cheap structured-output LLM call decides whether
the message asks to change THE OPEN CANVAS; if so the edit is PATCH-FIRST —
exact find→replace ops against the current content (anything the ops don't
touch is preserved byte-for-byte, so the user's manual on-canvas edits
survive), with complete-content replacement reserved for explicit rewrites.
``apply_canvas_edit`` persists it through the existing general mechanism —
``tools.canvas_crud_tool.update_canvas_content`` (append-only CanvasAudit +
WS ``canvas:update`` broadcast that the canvas page already renders live).

Every leg is fault-isolated like the planner: any failure returns None and
the turn falls through to the normal conversational path — never raises into
the chat path, never loses the user's message.
"""
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

from core.evidence_grounding import CANVAS_ARTIFACT_GROUNDING_RULE

logger = logging.getLogger(__name__)

# Pin to a known-reachable vetted model — same rationale as the planner's
# PLANNER_MODEL (unpinned "auto" routing prefers the free local Ollama client
# by value, which is frequently unreachable; the connection-error retries eat
# seconds and lose the structured output entirely).
# Flash-class non-reasoning pin: the previous pin (minimax-m3) is a
# reasoning model whose provider ignores the disable flag — every tiny
# planning call burned 1,100-2,000 hidden tokens and 30-75s (measured
# 2026-09-01; the canvas-edit plan alone blew the 30s budget). The editor
# plans ~60-line JSON; a fast non-reasoning flash model is the right shape.
CANVAS_EDITOR_MODEL = os.getenv(
    "ATOM_CANVAS_EDITOR_MODEL", "qwen/qwen3.7-flash")

# The current canvas content rides in the prompt; bound it so a huge sheet
# can't blow the structured-call budget.
_MAX_CONTENT_CHARS = 6000

# Total edit-plan prompt budget (chars ≈ tokens/4). Learning sections make
# the prompt grow; when the budget is exceeded, sections drop by priority:
# current-canvas corrections > versions > taught lessons > cross-canvas
# channels — the closest context always outranks the recalled context.
_MAX_EDIT_PROMPT_CHARS = int(os.getenv("ATOM_CANVAS_EDIT_PROMPT_MAX_CHARS", "48000"))


class CanvasPatchOp(BaseModel):
    """One surgical find→replace against the CURRENT canvas content.

    ``find`` is matched exactly (first occurrence) and must be copied
    verbatim from the content shown to the planner; ``field`` names the key
    to edit inside object-shaped content (e.g. an email's "body") and is
    None for plain string canvases. For grid content (sheets) ``cell`` is
    the A1 reference and ``find`` must equal the cell's current value.
    Everything an op doesn't touch is preserved byte-for-byte — that's the
    guarantee full-content regeneration could never make (real case: a
    narrow "update the email from your findings" request rewrote the whole
    draft and silently dropped the supervisor's manual on-canvas edits)."""
    field: Optional[str] = None
    cell: Optional[str] = None
    find: str = ""
    replace: str = ""


class CanvasEditPlan(BaseModel):
    wants_edit: bool = False
    # "patch" (default): ops carry the surgical find→replace edits.
    # "replace": updated_content_json carries the complete new content —
    # reserved for explicit rewrite requests; then every section unrelated
    # to the request must still be reproduced EXACTLY as the current content
    # has it.
    edit_mode: Optional[str] = None
    ops: List[CanvasPatchOp] = []
    # Complete new canvas content as a JSON-encoded string (replace mode) —
    # strings survive every structured-output provider (weak models mangle
    # free-form object fields far more often than string fields).
    updated_content_json: Optional[str] = None
    title: Optional[str] = None
    reply: str = ""


class CanvasPlanUnavailable(Exception):
    """The planning LLM call failed (provider down / timeout / no JSON).

    Distinct from ``None`` (a legitimate "this turn is not an edit"): callers
    must NOT fall through to generic intent routing on this — an edit-shaped
    request misfiled into TASK_MANAGEMENT produces a chat reply claiming the
    edit succeeded while the canvas never changed (observed live 2026-08-31:
    "Append this exact line … LIVEUPDATEcheck456" answered with a false
    success, no audit row, no broadcast)."""


_EDITOR_SYSTEM = """You are the canvas editor for an AI co-editing panel.
The user is chatting next to an OPEN canvas whose current content is shown
below. Decide whether their latest message asks you to CHANGE that canvas
(edit, revise, shorten, expand, remove, add, reformat, translate, fill in),
and if so produce the edit.

Preservation rules — the canvas may hold MANUAL EDITS by the user that are
newer than anything in the conversation. The current content shown below is
the authority, NOT your memory of earlier drafts:
- Default to edit_mode="patch": return ops, each an exact find→replace.
  Copy "find" VERBATIM from the current content (every character and
  newline); the first match is replaced by "replace". Text the ops don't
  touch is preserved exactly as-is — that is the point of patch mode.
- Touch ONLY the parts the request targets. Never reword, reorder, or drop
  text the request doesn't mention, and never revert the user's own wording
  to an earlier draft.
- The CANVAS APP section below names this app's real input fields (the same
  fields its UI renders). For object content set "field" to one of THOSE
  keys; the op applies inside that field only, and the other keys stay
  untouched.
- SET-FIELD ops: to FILL AN EMPTY field (e.g. an empty To or Cc), return
  {"field": "<name>", "find": "", "replace": "<new value>"}. find="" is
  accepted ONLY when that field is currently empty — it sets the field.
  A field that already holds text must be edited with a normal verbatim
  find→replace inside it.
- For spreadsheet/grid content (rows, or {cells: ...}) set "cell" to the
  A1 reference instead: {"cell": "B2", "find": <the cell's current value>,
  "replace": <new value>}. "find" must equal the cell's current value.
- edit_mode="replace" ONLY when the user explicitly asked for a rewrite /
  fresh draft, or no patch can express the change (e.g. reformat
  everything): then updated_content_json is the new content. For object
  content it may contain ONLY the keys you are changing — they are MERGED
  into the current content and every key you omit is preserved as-is (a
  full set of keys is also fine). Match the current shape (same value
  types); never return a fragment or an explanation.
- RECENT VERSIONS (when present in the prompt) hold earlier drafts of this
  canvas. To go back to one, return edit_mode="replace" copying that
  version's content VERBATIM from the section — then apply any extra change
  the user asked for on top. Never invent text for a version that isn't
  shown; if none matches what the user describes, say so instead of guessing.
- Remove meta-commentary ("Here's your draft...", "Want me to adjust...")
  from the content itself — the canvas holds only the artifact.
- Send/dispatch requests ("send it", "email it to Mark", "try sending
  again") are NOT edits: wants_edit=false — a separate step owns actions.
- Questions, discussion, or requests about other things ("what do you
  think", "search my email") are wants_edit=false too.
- Sender identity is NEVER a guessing problem: the SENDER IDENTITY section
  (when present) names the user the draft is sent by. Never take a sender
  name or signature from the To/Cc fields — those are RECIPIENTS (a Cc'd
  colleague's first name is not the sender's). Never remove or replace an
  existing signature unless the request says to ("i added my signature,
  adjust" means polish AROUND it, not swap it for a guessed name).
- reply is one or two short sentences telling the user what you changed.
  For wants_edit=false, reply is a short conversational answer based on the
  canvas content (or empty if another step will answer).

""" + CANVAS_ARTIFACT_GROUNDING_RULE

# Fallback prompt when patch ops fail to match the current content (the
# model mis-copied "find"): one re-ask for content under the same
# preservation duty. Deterministic safety, not a second chance to patch.
# Field-scoped: the model returns ONLY the keys it is changing (merged on
# apply) — echoing untouched fields verbatim was the burden that made small
# models emit oversized, invalid JSON (observed live 2026-08-31).
_REPLACE_FALLBACK_SUFFIX = (
    "Your ops did not match the current content exactly, so they were "
    "discarded. Try again with edit_mode=\"replace\": return the new content "
    "for ONLY the keys you are changing (they will be merged in; keys you "
    "omit are preserved), applying the user's request. Same shape and value "
    "types as the current content."
)


def _serialize_content(content: Any) -> str:
    """Current canvas content as prompt-safe text, bounded."""
    if isinstance(content, str):
        text = content
    else:
        try:
            text = json.dumps(content, indent=2, default=str)
        except Exception:
            text = str(content)
    if len(text) > _MAX_CONTENT_CHARS:
        text = text[:_MAX_CONTENT_CHARS] + "\n…(truncated)"
    return text


def _history_transcript(history: List[Dict[str, Any]], current: str) -> str:
    """Recent turns, user AND agent lines: follow-ups like "now make it
    shorter", "update the draft based on your findings", and "apply what you
    just showed me" hang off earlier requests AND the agent's own replies —
    the draft the user is referring to often IS the last agent reply (a
    proposal shown in chat, never applied to the canvas). That reply therefore
    gets a generous budget: truncating it to a fragment made "update the
    canvas" unactionable — the model saw "We car…" and refused to apply a
    draft it couldn't read (observed live 2026-08-31). Older replies stay
    brief. Error turns are skipped: flagged failure artifacts must not anchor
    the plan."""
    turns: List[tuple] = []
    for h in (history or [])[-8:]:
        h = h or {}
        u = str(h.get("message") or "").strip()
        if u:
            turns.append(("user", u))
        if h.get("error"):
            continue
        resp = h.get("response")
        a = str((resp or {}).get("message") if isinstance(resp, dict) else (resp or "")).strip()
        if a:
            turns.append(("agent", a))
    turns.append(("user", current))

    # The LAST agent reply in the window carries the proposal the user most
    # likely means ("update the canvas" → apply it); give it room.
    last_agent_idx = max((i for i, (role, _) in enumerate(turns) if role == "agent"), default=None)
    lines: List[str] = []
    for i, (role, text) in enumerate(turns):
        if role == "user":
            budget = 600 if i == len(turns) - 1 else 200
            lines.append(f"User: {text[:budget]}")
        else:
            budget = 2400 if i == last_agent_idx else 300
            trimmed = text[:budget] + ("…(trimmed)" if len(text) > budget else "")
            lines.append(f"Agent: {trimmed}")
    return "\n".join(lines)


_CELL_REF = re.compile(r"^([A-Za-z]{1,3})([0-9]+)$")


def _identity_section(user_identity: Optional[Dict[str, Any]]) -> str:
    """SENDER IDENTITY: who the draft is sent by, resolved server-side from
    the account record and (email canvases) the composer's default-signature
    store. Live incident (2026-09-02, canvas da27bb76…): with no identity in
    the prompt the editor "adjusted" the signature by guessing a name from
    the Cc line — chandrakant@brennan.ca became the signature. Identity is
    data, never a guess. Rendered unconditionally (it is tiny and must
    survive prompt-budget trims that shave the learning sections)."""
    if not user_identity:
        return ""
    name = str(user_identity.get("name") or "").strip()
    email = str(user_identity.get("email") or "").strip()
    signature = str(user_identity.get("signature") or "").strip()
    who = name or email
    if not who and not signature:
        return ""
    lines = ["SENDER IDENTITY — resolved from the account, not a guess:"]
    if who:
        lines.append(
            f"The sender (the user you edit for): {who}. Never invent the "
            "sender's name from the To/Cc fields — those are RECIPIENTS."
        )
    if signature:
        trimmed = signature[:600]
        lines.append(
            "Their default email signature — use this when a signature is "
            "asked for or clearly needed:\n"
            f"{trimmed}{'…(trimmed)' if len(signature) > 600 else ''}"
        )
    lines.append(
        "Never remove or replace an existing signature unless the request "
        "says to."
    )
    return "\n".join(lines) + "\n\n"


def _playbooks_section(playbooks: Optional[List[Dict[str, Any]]]) -> str:
    """Approved company playbooks matching this turn (Installation
    Adaptation Plan Phase 3) — the install's OWN process as procedural
    memory: which steps to follow, which template questions to ask. Advisory
    (prompt leg), bounded, and ranked by the retrieval service; the CURRENT
    content section still outranks everything here."""
    if not playbooks:
        return ""
    blocks: List[str] = []
    for pb in playbooks[:2]:
        lines: List[str] = [f"### {pb.get('name', 'Process')}"]
        if pb.get("description"):
            lines.append(str(pb["description"])[:200])
        for step in (pb.get("steps") or [])[:6]:
            lines.append(f"- {str(step)[:200]}")
        questions = pb.get("template_questions") or []
        if questions:
            lines.append("Ask these template questions (verbatim, with the "
                         "installation's usual examples):")
            for q in questions[:6]:
                lines.append(f"- {str(q)[:200]}")
        blocks.append("\n".join(lines))
    if not blocks:
        return ""
    return (
        "COMPANY PLAYBOOKS — this installation's own process for drafts like "
        "this one. Follow the steps and include the template questions "
        "unless the user explicitly overrides them:\n\n"
        + "\n\n".join(blocks) + "\n\n"
    )


def _provenance_section(provenance: Optional[Dict[str, Any]]) -> str:
    """Origin transcript: the conversation this canvas was CREATED from
    (canvas_audit's create row carries its session_id; chat_routes hydrates
    the messages). Without it the co-editor honestly answers "I don't know
    who wrote this" to "why was the draft written this way" — the panel
    session starts empty and the origin conversation is a different thread.
    Read-only background: the CURRENT content section above always outranks
    it (the user's manual edits are newer than anything in the origin)."""
    messages = (provenance or {}).get("messages") or []
    lines: List[str] = []
    for m in messages[-6:]:
        if not isinstance(m, dict):
            continue
        content = str(m.get("content") or "").strip()
        if not content:
            continue
        role = "User" if m.get("role") == "user" else "Agent"
        lines.append(f"{role}: {content[:600]}{'…(trimmed)' if len(content) > 600 else ''}")
    if not lines:
        return ""
    return (
        "DRAFT ORIGIN — how this canvas came to be (the conversation that "
        "produced it, before this panel existed). Background only: these "
        "statements are NOT evidence — treat nothing here as verified fact. "
        "The CURRENT content section above always outranks the origin:\n"
        + "\n".join(lines) + "\n\n"
    )


def _cell_indices(ref: Optional[str]) -> Optional[Tuple[int, int]]:
    """'B2' → zero-based (row 1, col 1); None when not an A1 reference."""
    m = _CELL_REF.match((ref or "").strip())
    if not m:
        return None
    col = 0
    for ch in m.group(1).upper():
        col = col * 26 + (ord(ch) - ord("A") + 1)
    return int(m.group(2)) - 1, col - 1


def _patch_grid(rows: List[Any], ops: List[CanvasPatchOp]) -> Tuple[List[Any], List[CanvasPatchOp]]:
    """Cell ops over a list-of-rows grid. ``find`` must equal the cell's
    current value; a cell beyond the current width is reachable (padded) —
    grids grow, that's not a mismatch."""
    failed: List[CanvasPatchOp] = []
    grid = [list(r) if isinstance(r, list) else r for r in rows]
    for op in ops:
        idx = _cell_indices(op.cell)
        if not idx or idx[0] >= len(grid) or not isinstance(grid[idx[0]], list):
            failed.append(op)
            continue
        r, c = idx
        row = list(grid[r])
        if c >= len(row):
            row.extend([""] * (c + 1 - len(row)))
        if (op.find or "") and str(row[c]) == op.find:
            row[c] = op.replace
            grid[r] = row
        else:
            failed.append(op)
    return grid, failed


def _replace_in_text(text: str, find: str, replace: str) -> Tuple[str, bool]:
    """One find→replace against a text field, two matching tiers.

    Tier 1 exact (the preservation guarantee: what matches is what the
    planner copied). Tier 2 whitespace-insensitive — Aider's documented
    ladder (exact → whitespace-normalized) for when the model's copy is
    right except for indentation/line-wrap drift. Never fuzzy: a tier-2
    match still anchors on the find text's actual words, only its spacing
    flexes. Returns (new_text, matched)."""
    if find in text:
        return text.replace(find, replace, 1), True

    tokens = find.split()
    if len(tokens) < 2:
        return text, False  # single-token finds have no whitespace to flex
    pattern = re.compile(r"\s+".join(re.escape(t) for t in tokens))
    m = pattern.search(text)
    if not m:
        return text, False
    return text[:m.start()] + replace + text[m.end():], True


def _apply_patch_ops(content: Any, ops: List["CanvasPatchOp"]) -> tuple:
    """Apply surgical find→replace ops against the current content.

    Deterministic and all-or-nothing per op: an op whose ``find`` doesn't
    appear is REPORTED, never guessed at. Returns (new_content, failed_ops)
    — callers decide between committing (no failures) and falling back.
    Object content is edited per-key (op.field), grids per-cell (op.cell);
    every other key/row keeps its identity, so untouched data can't drift.

    Set-field ops (find="") fill an EMPTY field — the "include to and cc
    emails" case that was structurally impossible before (an empty field
    has no text to find, so those ops always failed and forced the fragile
    replace re-ask). A set-field op on a non-empty field is a validation
    failure, never an overwrite."""
    if not ops:
        return content, []
    failed: List[CanvasPatchOp] = []
    if isinstance(content, str):
        text = content
        for op in ops:
            find = op.find or ""
            if not find:
                failed.append(op)  # set-field needs a named field; not a string canvas
                continue
            text, matched = _replace_in_text(text, find, op.replace)
            if not matched:
                failed.append(op)
        return text, failed
    if isinstance(content, list):
        return _patch_grid(content, ops)
    if isinstance(content, dict):
        if isinstance(content.get("rows"), list):
            rows, failed = _patch_grid(content["rows"], ops)
            return {**content, "rows": rows}, failed
        if isinstance(content.get("cells"), dict):
            # SpreadsheetCanvasService shape: cells[ref] = {cell_ref, value, ...}.
            cells = dict(content["cells"])
            for op in ops:
                ref = (op.cell or "").strip().upper()
                entry = cells.get(ref)
                if (
                    _cell_indices(op.cell)
                    and isinstance(entry, dict)
                    and (op.find or "")
                    and str(entry.get("value")) == op.find
                ):
                    cells[ref] = {**entry, "value": op.replace}
                else:
                    failed.append(op)
            return {**content, "cells": cells}, failed
        result = dict(content)
        for op in ops:
            key = op.field
            if not (key and isinstance(result.get(key), str)):
                failed.append(op)
                continue
            find = op.find or ""
            if not find:
                # Set-field: only an empty field may be filled.
                if not result[key].strip():
                    result[key] = op.replace
                else:
                    failed.append(op)
                continue
            result[key], matched = _replace_in_text(result[key], find, op.replace)
            if not matched:
                failed.append(op)
        return result, failed
    return content, list(ops)  # scalars can't patch — force replace fallback


def _brief(value: Any, limit: int = 300) -> str:
    """Any correction payload as bounded single-line text."""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, default=str)
        except Exception:
            text = str(value)
    text = " ".join(text.split())
    return text[:limit] + ("…" if len(text) > limit else "")


def _corrections_section(corrections: Optional[List[Dict[str, Any]]]) -> str:
    """The supervisor's hand-edits of the agent's drafts, as planner-visible
    lessons. Capture alone (AgentFeedback/maturity) changes a score, not the
    next draft — this is the feedback actually reaching the edit decision."""
    if not corrections:
        return ""
    lines: List[str] = []
    for i, c in enumerate(corrections[-3:], 1):
        c = c or {}
        original = c.get("original") if isinstance(c.get("original"), dict) else {}
        corrected = c.get("corrected") if isinstance(c.get("corrected"), dict) else {}
        lines.append(
            f"[{i}] BEFORE: {_brief(original.get('content') or original)}\n"
            f"    AFTER:  {_brief(corrected.get('content') or corrected)}"
        )
    if not lines:
        return ""
    return (
        "Recent supervisor corrections on THIS canvas — the supervisor hand-edited "
        "the agent's draft; AFTER is what they kept. Treat AFTER as the preferred "
        "wording/structure: never revert it, match its style in new edits, and keep "
        "every current-content part the request doesn't touch.\n"
        + "\n".join(lines) + "\n\n"
    )


# Per-version content budget in the planner prompt. Four trimmed versions cost
# ~3k chars on top of the 6k current-content cap — enough to diff against and
# copy verbatim, without crowding out the current content.
_VERSION_CHARS = 800


def _canvas_profile_text(canvas: Dict[str, Any], bound: int = 1500) -> str:
    """Bounded profile of the CURRENT canvas for cross-canvas similarity:
    what this canvas is about (type, title, content head) — the query side
    of the episodic recall."""
    parts = [
        str(canvas.get("canvas_type") or ""),
        str(canvas.get("title") or ""),
        _serialize_content(canvas.get("content"))[:bound],
    ]
    return " ".join(p for p in parts if p)


def _similar_lessons_section(
    similar_corrections: Optional[List[Dict[str, Any]]],
    correction_patterns: Optional[List[Dict[str, Any]]],
) -> str:
    """Cross-canvas learning channels for the edit planner — the parts of a
    human's experience beyond the canvas in front of them:

    - EPISODIC: how the supervisor corrected drafts on OTHER similar
      canvases (relevance × recency ranked by canvas_context_service).
    - DISTILLED: recurring patterns across ALL the supervisor's corrections
      (ExpeL-style insights, e.g. "filled the empty 'to' field in 3 of 4
      corrections").

    Precedence is explicit: these transfer PREFERENCES; the current canvas's
    own content and its own corrections still outrank them."""
    if not similar_corrections and not correction_patterns:
        return ""
    lines: List[str] = []
    if similar_corrections:
        lines.append(
            "LEARNINGS FROM SIMILAR PAST CANVASES — how your supervisor "
            "corrected your drafts on other similar canvases of this kind "
            "(most similar first). Transfer the corrected style, structure, "
            "and field conventions here:"
        )
        for i, entry in enumerate(similar_corrections, 1):
            entry = entry or {}
            lines.append(
                f"[{i}] similar {entry.get('canvas_type') or 'canvas'} canvas "
                f"(relevance {entry.get('relevance', 0):.2f}):"
            )
            for c in (entry.get("corrections") or [])[-2:]:
                c = c if isinstance(c, dict) else {}
                original = c.get("original") if isinstance(c.get("original"), dict) else {}
                corrected = c.get("corrected") if isinstance(c.get("corrected"), dict) else {}
                lines.append(
                    f"    BEFORE: {_brief(original.get('content') or original)}\n"
                    f"      AFTER: {_brief(corrected.get('content') or corrected)}"
                )
    if correction_patterns:
        rendered = "; ".join(
            f"{p.get('pattern')} ({p.get('count')}/{p.get('total')} corrections)"
            for p in correction_patterns if isinstance(p, dict) and p.get("pattern")
        )
        if rendered:
            lines.append(
                "RECURRING SUPERVISOR PREFERENCES across your past canvases "
                "(distilled from every correction you have received): "
                + rendered + "."
            )
    if not lines:
        return ""
    return (
        "\n".join(lines)
        + "\nThese transfer preferences only — the CURRENT canvas content "
        "and the current-canvas corrections above outrank them.\n\n"
    )


def _lessons_section(lessons: Optional[List[Dict[str, Any]]]) -> str:
    """The operating agent's PERMANENT taught lessons (TrainingPanel /teach,
    mentor lessons, observed human corrections), as planner-visible standing
    instructions. Storage alone only moved a confidence score — this section
    is what makes a taught lesson shape the edit it should have been shaping,
    for every agent and every canvas app. Reuses the shared renderer so
    all work-time surfaces carry the same permanence framing."""
    if not lessons:
        return ""
    try:
        from core.student_learning_service import format_lessons_block

        block = format_lessons_block(lessons)
    except Exception as e:  # fault-isolated like every other section
        logger.debug(f"lessons section skipped: {e}")
        return ""
    if not block:
        return ""
    return (
        block + "\nApply these lessons to THIS edit: match the taught "
        "preferences in style, structure, and content — subject to the "
        "preservation rules above (never revert the supervisor's manual "
        "edits or any current-content part the request doesn't touch).\n\n"
    )


def _versions_section(
    versions: Optional[List[Dict[str, Any]]],
    current: Any,
) -> str:
    """Earlier drafts of THIS canvas (newest first, from the append-only audit
    trail), so the planner can diff against what it is about to change and
    RESTORE an earlier version verbatim when asked — the recovery path that
    was impossible before (observed live: an overwrite left the agent unable
    to go back, and it had to tell the user so). Versions identical to the
    current content are dropped; everything is trimmed to _VERSION_CHARS."""
    if not versions:
        return ""
    if isinstance(current, str):
        current_key = current
    else:
        try:
            current_key = json.dumps(current, sort_keys=True, default=str)
        except Exception:
            current_key = str(current)

    lines: List[str] = []
    for v in versions or []:
        if len(lines) >= 4:
            break
        v = v or {}
        content = v.get("content")
        if content is None:
            continue
        if isinstance(content, str):
            text = content
            content_key = content
        else:
            text = json.dumps(content, default=str)
            try:
                content_key = json.dumps(content, sort_keys=True, default=str)
            except Exception:
                content_key = text
        if content_key == current_key:
            continue  # that IS the current content — nothing to restore
        when = (v.get("created_at") or "earlier").replace("T", " ")[:19]
        actor = v.get("actor") or "unknown"
        title = f", title: {v['title']}" if v.get("title") else ""
        trimmed = text[:_VERSION_CHARS] + ("…(trimmed)" if len(text) > _VERSION_CHARS else "")
        lines.append(f"[{when} — {actor}{title}]\n{trimmed}")

    if not lines:
        return ""
    return (
        "RECENT VERSIONS of this canvas (newest first, trimmed). If the user asks to go "
        "back to / restore / revert to an earlier version or their original draft, pick "
        "the version they mean and return edit_mode=\"replace\" with that version's "
        "content VERBATIM — then apply any additional change they asked for on top. "
        "Never invent text for a version that isn't shown here; if none matches, say so.\n"
        + "\n---\n".join(lines) + "\n\n"
    )


async def plan_canvas_edit(
    message: str,
    history: List[Dict[str, Any]],
    canvas: Dict[str, Any],
    llm_service: Any,
    corrections: Optional[List[Dict[str, Any]]] = None,
    versions: Optional[List[Dict[str, Any]]] = None,
    lessons: Optional[List[Dict[str, Any]]] = None,
    similar_corrections: Optional[List[Dict[str, Any]]] = None,
    correction_patterns: Optional[List[Dict[str, Any]]] = None,
    provenance: Optional[Dict[str, Any]] = None,
    user_identity: Optional[Dict[str, Any]] = None,
    playbooks: Optional[List[Dict[str, Any]]] = None,
) -> Optional[CanvasEditPlan]:
    """Decide (via cheap structured LLM output) whether this turn edits the
    open canvas, and produce the edit — patch ops by default, complete
    content for explicit rewrites. ``corrections`` are the supervisor's recent
    on-canvas edits of this canvas (the RLHF signal, returned to the point of
    generation). ``versions`` are earlier drafts from the audit trail (see
    _versions_section) — the go-back/restore path. ``lessons`` are the
    operating agent's permanent taught lessons (see _lessons_section) — the
    work-time application of /teach, general across agents and canvas apps.
    ``similar_corrections``/``correction_patterns`` are the CROSS-CANVAS
    learning channels — episodic (corrections on similar other canvases) and
    distilled (recurring supervisor preference patterns), see
    _similar_lessons_section. ``provenance`` is the ORIGIN conversation the
    canvas was created from (see _provenance_section) — how the draft came
    to be, so grounding questions have real provenance instead of an
    honest "I don't know". ``user_identity`` is the SENDER (account name /
    email / default email signature, see _identity_section) — with it absent
    the editor guessed a signature name from the Cc line. Patch ops are
    validated against the current
    content here: a mis-copied "find" gets ONE re-ask in replace mode (still
    under the preservation duty) rather than a broken write. Returns None on
    any failure — the caller then falls through to the conversational path."""
    if llm_service is None or not canvas.get("canvas_id"):
        return None

    from core.canvas_app_schema import app_prompt_section

    # Prompt budget: the core (system + app + current content + history)
    # always stays; learning sections are included in priority order and
    # the lowest-priority ones trim first when the budget is tight —
    # recalled context must never crowd out the live artifact, and the
    # whole prompt must fit the serving model's context window.
    app_section = app_prompt_section(canvas.get("canvas_type"), canvas.get("content"))
    content_section = (
        f"Current canvas content:\n{_serialize_content(canvas.get('content'))}\n\n"
    )
    history_section = (
        f"Recent conversation:\n{_history_transcript(history, message)}\n\n"
        "Return the edit plan."
    )
    rendered = {  # canonical layout order; priority = same order
        "corrections": _corrections_section(corrections),
        "versions": _versions_section(versions, canvas.get("content")),
        "lessons": _lessons_section(lessons),
        "cross": _similar_lessons_section(similar_corrections, correction_patterns),
        # Origin context ranks LAST — useful for grounding questions, never
        # at the cost of the live artifact or the learning signal.
        "origin": _provenance_section(provenance),
    }
    budget = _MAX_EDIT_PROMPT_CHARS - len(
        _EDITOR_SYSTEM + app_section + content_section + history_section
    )
    included: Dict[str, str] = {}
    trimmed_any = False
    for name, section in rendered.items():
        if not section:
            continue
        if len(section) <= budget:
            included[name] = section
            budget -= len(section)
        elif budget > 800:  # keep only when a usable head fits
            # Reserve the marker's own length so the kept head + marker
            # still land inside the budget.
            head = max(0, budget - 60)
            included[name] = (
                section[:head]
                + "\n…(trimmed to fit the model's context budget)\n\n"
            )
            trimmed_any = True
            budget = 0
        else:
            trimmed_any = True
    if trimmed_any:
        logger.info(
            f"canvas edit prompt trimmed to {_MAX_EDIT_PROMPT_CHARS} chars — "
            f"lowest-priority learning sections reduced first"
        )
    prompt = (
        f"{_EDITOR_SYSTEM}\n\n"
        f"{_identity_section(user_identity)}"
        f"{_playbooks_section(playbooks)}"
        f"{included.get('corrections', '')}"
        f"{included.get('versions', '')}"
        f"{included.get('lessons', '')}"
        f"{included.get('cross', '')}"
        f"{included.get('origin', '')}"
        f"{app_section}\n"
        f"{content_section}"
        f"{history_section}"
    )

    # Pin (provider, model) exactly like the planner: generate_structured_
    # response forwards provider_model into the handler, pinning the option
    # list to one reachable (provider, model).
    kwargs: Dict[str, Any] = {}
    try:
        if "openrouter" in llm_service._get_handler().clients:
            kwargs["provider_model"] = ("openrouter", CANVAS_EDITOR_MODEL)
    except Exception:
        pass

    plan = await llm_service.generate_structured_response(
                disable_reasoning=True,
        prompt=prompt,
        response_model=CanvasEditPlan,
        system_instruction="You return only the requested JSON object.",
        temperature=0.0,
        **kwargs,
    )
    if plan is None:
        # The structured call failed outright (all providers/timeout) — a
        # planning INFRASTRUCTURE failure, not "not an edit". Raise so the
        # caller answers honestly instead of routing an edit request into
        # generic intent handling (false-success claims, junk tasks).
        raise CanvasPlanUnavailable(
            "canvas edit planning LLM returned no plan (provider failure)"
        )
    if not plan.wants_edit:
        return plan

    # Patch validation: ops must match the current content EXACTLY. A
    # failed match discards the ops (never a partial write) and re-asks once
    # for complete content — the user's request still lands, without
    # guess-based fuzzy matching corrupting the artifact. A replace plan with
    # NO ops and NO content is degenerate (the model committed to an edit it
    # couldn't produce — observed live when the draft it needed had been
    # truncated out of its context) and gets the same one re-ask instead of
    # sailing into apply just to be discarded.
    reask_reason = None
    if plan.ops:
        _, failed = _apply_patch_ops(canvas.get("content"), plan.ops)
        if failed:
            reask_reason = f"{len(failed)}/{len(plan.ops)} patch op(s) failed to match"
    elif not (plan.updated_content_json or "").strip():
        reask_reason = "replace plan carried no ops and no content"

    if reask_reason:
        logger.info(
            f"canvas edit: {reask_reason} — falling back to a replace-mode re-ask"
        )
        replan = await llm_service.generate_structured_response(
                disable_reasoning=True,
            prompt=f"{prompt}\n\n{_REPLACE_FALLBACK_SUFFIX}",
            response_model=CanvasEditPlan,
            system_instruction="You return only the requested JSON object.",
            temperature=0.0,
            **kwargs,
        )
        if replan is None:
            # First call proved this IS an edit; the re-ask dying is an
            # infrastructure failure — same honest-failure treatment.
            raise CanvasPlanUnavailable(
                "canvas edit replace re-ask LLM returned no plan (provider failure)"
            )
        if not replan.wants_edit:
            return None
        # Only a usable replace plan rescues the turn; another broken patch
        # set does not — fall through to conversation instead of guessing.
        if replan.updated_content_json and replan.updated_content_json.strip():
            return replan
        if replan.ops:
            _, failed2 = _apply_patch_ops(canvas.get("content"), replan.ops)
            if not failed2:
                return replan
        # Last structured leg failed to produce usable content: one RAW
        # completion retry, parsed locally with the same repair ladder —
        # the action planner's proven fallback (_raw_json_action_plan).
        # Instructor/tool-mode structured calls are exactly where weak
        # models mangle the embedded JSON string; a raw completion often
        # carries the same JSON intact.
        raw_plan = await _raw_json_replace_plan(
            llm_service, f"{prompt}\n\n{_REPLACE_FALLBACK_SUFFIX}", kwargs
        )
        if raw_plan is not None and (raw_plan.updated_content_json or "").strip():
            logger.info("canvas edit replace plan recovered via raw-JSON fallback")
            return raw_plan
        return None
    return plan


def _repair_json(raw: str) -> Optional[Any]:
    """Second-chance JSON decode for LLM payloads.

    Structured-output providers hand back the JSON-encoded string field with
    markdown fences, unescaped newlines/quotes, or truncation (observed live
    as "updated_content_json is not valid JSON — discarding", which threw
    away a real edit). Defense in depth, in order: strict parse →
    fence-strip → outermost {...}/{...} extraction → json_repair (the de
    facto repair library for exactly this failure class). Returns None only
    when nothing parses."""
    raw = (raw or "").strip()
    if not raw:
        return None
    fence = re.match(r"^```[a-zA-Z0-9]*\s*\n(.*?)\n?```\s*$", raw, re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start = raw.find(opener)
        end = raw.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except (json.JSONDecodeError, ValueError):
                continue
    try:
        import json_repair

        repaired = json_repair.loads(raw)
    except Exception:
        return None
    # json_repair "succeeds" on plain prose (returns it as a string) — that
    # is not an edit payload.
    if isinstance(repaired, str):
        return None
    return repaired


def _merge_replace_content(
    parsed: Any,
    current: Any,
    canvas_type: Optional[str],
) -> Tuple[Optional[Any], Optional[str]]:
    """Merge a replace-mode payload onto the current content.

    For dict-shaped apps (email, form — content_kind "fields") the payload
    carries ONLY the keys being changed; omitted keys are preserved. This
    is the contract that removed the echo burden: requiring models to
    reproduce the entire body byte-for-byte produced oversized, invalid
    JSON (observed live 2026-08-31). Keys are validated against the app's
    real UI fields so nothing the canvas can't render is smuggled in.

    Returns (new_content, failure_reason) — failure_reason None on success.
    """
    from core.canvas_app_schema import get_app_spec, known_field_names

    spec = get_app_spec(canvas_type)

    if isinstance(parsed, dict) and isinstance(current, dict):
        if isinstance(current.get("rows"), list) or isinstance(current.get("cells"), dict):
            # Grid content: replace stays whole (e.g. a version restore
            # copies the version's rows verbatim).
            return parsed, None
        known = known_field_names(spec)
        merged = dict(current)
        applied = 0
        dropped: List[str] = []
        for key, value in parsed.items():
            if key in known or key in current:
                merged[key] = value
                applied += 1
            else:
                dropped.append(key)
        if dropped:
            logger.info(
                f"canvas edit: dropped non-field key(s) {dropped} not in the "
                f"{spec.canvas_type} app schema"
            )
        if not applied:
            return None, "replace payload carried none of this app's fields"
        return merged, None

    # Same-type whole replace stays valid for every other shape
    # (string canvas, chart data array, …).
    if type(parsed) is type(current):
        return parsed, None

    if isinstance(parsed, str) and isinstance(current, dict):
        # Text drafts get stored as {"content": <str>} wrappers on some
        # creation paths — accept the unwrapped string back into the wrapper.
        keys = set(current.keys())
        if keys == {"content"} and isinstance(current.get("content"), str):
            return {"content": parsed}, None
        return None, "replace payload was plain text but the canvas content is structured"

    return None, "replace payload shape does not match the current content"


def _decode_replace_content(
    plan: CanvasEditPlan,
    current: Any,
) -> Tuple[Optional[Any], Optional[str]]:
    """Decode replace-mode content. Returns (content, failure_reason)."""
    raw = (plan.updated_content_json or "").strip()
    if not raw:
        # Defensive stop: the planner now re-asks before a content-less
        # replace plan gets here. Quietly unusable — not a "not valid JSON"
        # scenario (that warning sent debugging down the wrong path once).
        logger.debug("canvas edit: replace plan carried no content")
        return None, "no_content"
    parsed = _repair_json(raw)
    if parsed is None:
        # Keep a fragment of what the model actually returned in the log —
        # the 2026-08-31 RCA was blind exactly because the discarded payload
        # was never captured.
        logger.warning(
            "canvas edit: updated_content_json is not valid JSON even after "
            f"repair — discarding. Payload head: {raw[:400]!r}"
        )
        if isinstance(current, str):
            return raw, None  # a plain-string canvas can take the raw text
        return None, "not_valid_json"
    return parsed, None


async def apply_canvas_edit(
    plan: CanvasEditPlan,
    user_id: str,
    canvas: Dict[str, Any],
    return_reason: bool = False,
):
    """Persist the planned edit through the general canvas CRUD layer
    (CanvasAudit append + WS broadcast). Patch ops are re-applied
    deterministically against the canvas content the plan validated against;
    replace plans are decoded, repaired, and — for dict-shaped apps —
    MERGED field-scoped onto the current content (omitted keys preserved).
    Per-app policy: file-backed canvases (real .docx/.xlsx/.pptx) refuse
    content writes — the file is the artifact, a snapshot write would change
    nothing the user can see.

    Returns the update result dict on success, None on any failure. With
    ``return_reason=True`` returns ``(result_or_None, reason_or_None)`` so
    the caller can answer with WHAT failed instead of a generic retry."""
    from core.canvas_app_schema import get_app_spec

    def _out(result, reason):
        return (result, reason) if return_reason else result

    if not plan or not plan.wants_edit:
        return _out(None, "not_an_edit")

    current = canvas.get("content")
    canvas_id = str(canvas.get("canvas_id"))
    canvas_type = str(canvas.get("canvas_type") or "generic")
    spec = get_app_spec(canvas_type)

    if spec.content_kind == "file_backed":
        return _out(None, "file_backed")

    new_content: Any = None
    reason: Optional[str] = None

    if plan.ops:
        new_content, failed = _apply_patch_ops(current, plan.ops)
        if failed:
            # The plan validated in plan_canvas_edit; a mismatch here means
            # the content moved between the two steps — refuse rather than
            # write a partial edit on top of a state nobody saw.
            logger.warning("canvas edit: patch ops no longer match — refusing partial write")
            return _out(None, "ops_no_longer_match")
    else:
        parsed, decode_reason = _decode_replace_content(plan, current)
        if parsed is None:
            return _out(None, decode_reason or "not_valid_json")
        new_content, reason = _merge_replace_content(parsed, current, canvas_type)
        if new_content is None:
            return _out(None, reason or "merge_failed")

    # No-op guard: a plan whose result equals the current content writes
    # nothing and reports honestly. Live incident (2026-09-02, canvas
    # da27bb76…): four identical rewrites in a row — "mark is the dealer and
    # not end user" produced a byte-identical audit row and the reply still
    # claimed "I have updated the email body…", which read to the user as
    # the agent lying ("nothing changed"). Skipping the write also keeps
    # the audit trail free of non-edits.
    if new_content == current:
        return _out(None, "no_change")

    try:
        from tools.canvas_crud_tool import update_canvas_content

        result = await update_canvas_content(
            user_id, canvas_id, new_content, canvas_type, plan.title
        )
    except Exception as e:
        logger.warning(f"canvas edit apply failed for {canvas_id}: {e}")
        return _out(None, f"store_error: {e}")

    if not (result or {}).get("success"):
        logger.info(f"canvas edit rejected for {canvas_id}: {(result or {}).get('error')}")
        return _out(None, f"store_rejected: {(result or {}).get('error')}")
    return _out(result, None)


def normalize_degenerate_content(
    canvas_type: Optional[str],
    content: Any,
) -> Optional[Any]:
    """Deterministic healing for canvases seeded before the narration-
    tolerant extractor existed: fill EMPTY input fields of a dict-shaped
    app from the draft text already inside the content (the live case: an
    email canvas with to="" / cc="" whose body holds "**To:**
    jschulz@blumetric.ca"). Only empty fields are ever filled — with ONE
    narrow exception: a Subject that carries the old seeder's "Draft — "
    narration marker is replaced by the draft's real subject. Manual user
    edits can't be clobbered. Returns the healed content, or None when
    there is nothing to heal (the overwhelmingly common case)."""
    from core.canvas_app_schema import empty_fillable_fields, get_app_spec, normalize_app_type

    spec = get_app_spec(canvas_type)
    if spec.content_kind != "fields" or not isinstance(content, dict):
        return None
    empty = empty_fillable_fields(spec, content)
    if not empty:
        return None
    if normalize_app_type(canvas_type) != "email":
        return None  # email is the app with extractable header-shaped drafts
    body = content.get("body")
    if not isinstance(body, str) or not body.strip():
        return None
    try:
        from core.chat_draft_classifier import extract_email_draft

        extracted = extract_email_draft(body)
    except Exception:
        return None
    if not extracted:
        return None
    merged = dict(content)
    healed = False
    for field_name in ("to", "cc", "subject"):
        if field_name not in empty and field_name == "subject":
            # One narrow, code-generated marker exception: the old seeder
            # filled Subject with "Draft — <first 60 chars of chat
            # narration>" (chat_routes.py's title builder) when extraction
            # failed. That narration is never a real subject — replace it
            # when the draft carries the real one. Any other non-empty
            # subject stays untouched.
            current_subject = (merged.get("subject") or "").strip()
            if not current_subject.startswith("Draft — "):
                continue
        elif field_name not in empty:
            continue
        if extracted.get(field_name):
            merged[field_name] = extracted[field_name]
            healed = True
    return merged if healed else None


async def _raw_json_replace_plan(
    llm_service: Any,
    prompt: str,
    kwargs: Dict[str, Any],
) -> Optional[CanvasEditPlan]:
    """Plain-completion fallback for the replace re-ask: ask for raw JSON
    and parse it locally (repair-tolerant), instead of the Instructor
    structured path that weak models answer with mangled embedded JSON.
    Fault-isolated — None on any failure."""
    try:
        messages = [
            {"role": "system", "content": "You reply with a single raw JSON object only. No markdown fences, no tool calls, no prose."},
            {"role": "user", "content": prompt},
        ]
        completion_kwargs = {}
        pm = (kwargs or {}).get("provider_model")
        if pm:
            completion_kwargs["model"] = pm[1]
        raw = await llm_service.generate_completion(
            messages, temperature=0.0, max_tokens=2000, **completion_kwargs
        )
        if isinstance(raw, dict):
            if not raw.get("success", True):
                return None
            text = raw.get("content") or raw.get("text") or ""
        else:
            text = str(raw or "")
        if not text:
            return None
        match = re.search(r"\{.*\}", str(text), re.DOTALL)
        if not match:
            return None
        data = _repair_json(match.group(0))
        if not isinstance(data, dict):
            return None
        fields = {k: v for k, v in data.items() if k in CanvasEditPlan.model_fields}
        if not fields.get("wants_edit", True):
            return None
        if not (fields.get("updated_content_json") or "").strip():
            return None
        return CanvasEditPlan(**fields)
    except Exception as e:
        logger.debug(f"raw-JSON replace plan fallback failed: {e}")
        return None


def describe_apply_failure(
    reason: Optional[str],
    canvas_type: Optional[str],
    canvas: Optional[Dict[str, Any]] = None,
) -> str:
    """The user-facing explanation for an apply failure — specific enough to
    act on, instead of the old generic "try rephrasing" dead end."""
    from core.canvas_app_schema import (
        empty_fillable_fields,
        get_app_spec,
    )

    spec = get_app_spec(canvas_type)
    content = (canvas or {}).get("content")
    empty = empty_fillable_fields(spec, content)
    field_hint = ""
    if empty:
        pretty = ", ".join(f.upper() if f in ("to", "cc") else f.capitalize()
                           for f in empty)
        field_hint = (
            f" Right now the {pretty} field(s) are empty — tell me the "
            f'value(s) (e.g. "set {empty[0]}: <value>") and I\'ll fill '
            "them in directly."
        )

    if reason == "no_change":
        return (
            "I read the canvas and it already reflects that — nothing "
            "needed changing. If you expected a difference, point me at "
            "the specific wording to change."
        )
    if reason == "file_backed":
        return (
            f"This is a {spec.label} canvas backed by a real file, so "
            "canvas-text edits can't change the document itself — tell me "
            "what to change and I'll route it through the file engine "
            "instead."
        )
    if reason and reason.startswith("store_rejected"):
        return (
            "The canvas store refused that edit. Nothing was changed — "
            f"the store said: {reason.split(':', 1)[1].strip()}. Try again "
            "in a moment."
        )
    if reason == "not_valid_json" or reason == "no_content":
        return (
            "I drafted the edit but couldn't produce a clean structured "
            "payload for this canvas, so nothing was changed. Try a smaller, "
            "more specific instruction (e.g. one field or one paragraph at "
            "a time)." + field_hint
        )
    if field_hint:
        return (
            f"I couldn't apply that edit to the {spec.label} canvas — "
            f"nothing was changed.{field_hint}"
        )
    return (
        "I tried to make that edit but couldn't apply it cleanly "
        "to the current canvas — nothing was changed. Try rephrasing "
        "or pointing me at the exact text to change."
    )


class CanvasActionPlan(BaseModel):
    """Plan for DOING something with the canvas (vs editing it): sending the
    draft, forwarding it, etc. Executes through the maturity + autonomy-policy
    gates — never directly from the planner."""
    wants_action: bool = False
    action: Optional[str] = None  # "send_email" (extensible)
    to: Optional[str] = None      # recipient(s), comma/semicolon separated
    cc: Optional[str] = None      # cc recipient(s), comma/semicolon separated
    subject: Optional[str] = None
    body: Optional[str] = None    # full email body; defaults to canvas content
    reply: str = ""
    # Threaded reply: when the user says to reply on/in the existing thread,
    # the plan carries the conversationId from the canvas's email context
    # and the send becomes a threaded reply instead of a fresh mail.
    thread_id: Optional[str] = None
    reply_all: bool = False


_ACTION_SYSTEM = """You are the action planner for an AI co-editing panel.
The user is chatting next to an OPEN canvas (its content is shown below).
Decide whether their latest message asks you to PERFORM an external action
with this canvas — currently: SEND the draft as an email — as opposed to
editing it (a different step owns edits).

Rules:
- wants_action=true ONLY for send/dispatch requests ("send this", "email it
  to Mark", "send the draft to a@b.com", "forward this to…"). Editing,
  rewriting, questions, discussion → wants_action=false.
- ``to``: the recipient(s) from the message (emails or names). Empty if the
  message doesn't say — never invent addresses.
- ``cc``: any CC recipients named in the message OR in the canvas content's
  "cc" field (comma-separated string). Empty if none — never invent.
- ``subject``: from the message or the canvas title; empty if unclear.
- ``body``: the canvas draft content VERBATIM — it may hold manual edits by
  the user that outrank anything in the conversation. Do NOT rewrite,
  "improve", or restructure it when the message only says to send; strip
  obvious meta notes that aren't part of the artifact itself. Deviate only
  when the message itself asks for content changes.
- ``action``: exactly "send_email" for any send/dispatch request.
- ``reply``: one short sentence describing what you will do.
- ``thread_id``: when the message asks to reply on/in the thread AND the
  canvas context shows a conversationId for that thread, copy it here so
  the send stays in the original conversation; empty for a fresh send.
  ``reply_all``: true only when the message says reply to everyone."""


async def plan_canvas_action(
    message: str,
    history: List[Dict[str, Any]],
    canvas: Dict[str, Any],
    llm_service: Any,
) -> Optional[CanvasActionPlan]:
    """Decide whether this turn asks to DO something with the canvas (send
    email). Returns None on failure — caller falls through."""
    if llm_service is None or not canvas.get("canvas_id"):
        return None

    prompt = (
        f"{_ACTION_SYSTEM}\n\n"
        f"Canvas title: {canvas.get('title') or '(untitled)'}\n"
        f"Canvas type: {canvas.get('canvas_type') or 'generic'}\n"
        f"Canvas content:\n{_serialize_content(canvas.get('content'))}\n\n"
        f"Recent conversation:\n{_history_transcript(history, message)}\n\n"
        "Return the action plan as RAW JSON — do NOT wrap it in ```json fences."
    )

    kwargs: Dict[str, Any] = {}
    try:
        if "openrouter" in llm_service._get_handler().clients:
            kwargs["provider_model"] = ("openrouter", CANVAS_EDITOR_MODEL)
    except Exception:
        pass

    plan = await llm_service.generate_structured_response(
                disable_reasoning=True,
        prompt=prompt,
        response_model=CanvasActionPlan,
        system_instruction="You return only the requested JSON object — raw JSON, no markdown fences.",
        temperature=0.0,
        **kwargs,
    )
    if plan is None:
        # Deterministic fallback: the structured (Instructor/tool-mode) path
        # is unreliable for action-shaped schemas — the schema class name
        # becomes the tool name the model sees, and it sometimes answers
        # with tool-call syntax, which Instructor rejects ("use List[Model]
        # instead") even though the completion holds perfect JSON (observed
        # live across provider variants). Parse a raw completion ourselves:
        # fence-stripping + pydantic validation.
        plan = await _raw_json_action_plan(llm_service, prompt, kwargs)
        if plan is not None:
            logger.info("canvas action plan recovered via raw-JSON fallback")
    if plan and plan.wants_action:
        # Normalize: models return the plain verb ("send", "email it") as
        # often as the canonical token — map the aliases, drop the rest.
        action = (plan.action or "").strip().lower().replace(" ", "_")
        if not action:
            action = "send_email"
        if action in {"send_email", "send", "email", "email_it", "send_draft",
                      "send_the_draft", "dispatch", "send_now"}:
            plan.action = "send_email"
        else:
            return None  # unknown actions fall through to conversation
    return plan


async def _raw_json_action_plan(llm_service: Any, prompt: str, kwargs: Dict[str, Any]) -> Optional[CanvasActionPlan]:
    """Plain-completion fallback for the action plan: ask for raw JSON and
    parse it locally (fence-tolerant). Fault-isolated — None on any failure."""
    import json as _json
    import re

    try:
        messages = [
            {"role": "system", "content": "You reply with a single raw JSON object only. No markdown fences, no tool calls, no prose."},
            {"role": "user", "content": prompt},
        ]
        completion_kwargs = {}
        pm = (kwargs or {}).get("provider_model")
        if pm:
            completion_kwargs["model"] = pm[1]
        raw = await llm_service.generate_completion(
            messages, temperature=0.0, max_tokens=1200, **completion_kwargs
        )
        # generate_completion returns {"success", "content"/"text", ...}
        if isinstance(raw, dict):
            if not raw.get("success", True):
                return None
            text = raw.get("content") or raw.get("text") or ""
        else:
            text = str(raw or "")
        if not text:
            return None
        logger.info(f"canvas action raw fallback output: {str(text)[:160]}")
        # strip markdown fences and <think> blocks if present
        cleaned = re.sub(r"</?mm:think>|</?think>", "", str(text))
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return None
        data = _json.loads(match.group(0))
        # Lenient coercion: the raw completion has no schema enforcement —
        # observed "to" as a list, booleans as strings. Normalize before
        # pydantic validation instead of losing the plan.
        fields = {k: v for k, v in data.items() if k in CanvasActionPlan.model_fields}
        if isinstance(fields.get("to"), (list, tuple)):
            fields["to"] = ", ".join(str(x) for x in fields["to"] if x)
        if isinstance(fields.get("wants_action"), str):
            fields["wants_action"] = fields["wants_action"].strip().lower() in ("true", "yes", "1")
        for str_field in ("action", "subject", "body", "reply"):
            if fields.get(str_field) is not None and not isinstance(fields[str_field], str):
                fields[str_field] = str(fields[str_field])
        return CanvasActionPlan(**fields)
    except Exception as e:
        logger.debug(f"raw-JSON action plan fallback failed: {e}")
        return None
