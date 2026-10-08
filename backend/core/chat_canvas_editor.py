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
import asyncio
import json
import logging
import os
import re
from decimal import Decimal, InvalidOperation
from enum import Enum
from html import unescape
from typing import Any, Awaitable, Callable, Dict, List, NamedTuple, Optional, Tuple

from pydantic import BaseModel

from core import log_redaction
from core.evidence_grounding import CANVAS_ARTIFACT_GROUNDING_RULE

logger = logging.getLogger(__name__)

# The editor plans ~60-line JSON, so the call is SHAPED as a cheap,
# non-reasoning one (``disable_reasoning=True``, temperature 0). WHICH model
# serves it is BPC's decision — see ``_plan_structured`` below.
#
# Do not reintroduce a model constant/pin here. ``provider_model`` collapses
# the candidate list to a single tuple (byok_handler: ``options =
# [provider_model]``), which removes every provider fallback; a brief upstream
# 429 then becomes fatal to the whole edit leg (OpenRouter, 2026-09-10). The
# earlier pin existed ONLY as a shape fix — the previous model (minimax-m3)
# ignored the disable flag and burned 1,100–2,000 hidden tokens / 30–75s on a
# tiny planning answer (measured 2026-09-01), blowing the 30s stage budget.
# Shape is now enforced by ``disable_reasoning`` + the handler's
# reasoning-mandatory exclusion, so routing can stay dynamic.

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
    # "restore": revert the canvas to an earlier version by id —
    # restore_audit_id names the version (from the RECENT VERSIONS section).
    # Applied deterministically through the audit-trail restore, so the
    # restored content is EXACT no matter how long it is (the old path made
    # the model copy the version's text out of a trimmed excerpt, which
    # garbled or truncated anything over a few hundred chars).
    edit_mode: Optional[str] = None
    ops: List[CanvasPatchOp] = []
    # Version to restore (edit_mode="restore"): the audit_id of one of the
    # RECENT VERSIONS entries, copied verbatim — never invented.
    restore_audit_id: Optional[str] = None
    # Complete new canvas content as a JSON-encoded string (replace mode) —
    # strings survive every structured-output provider (weak models mangle
    # free-form object fields far more often than string fields).
    updated_content_json: Optional[str] = None
    title: Optional[str] = None
    reply: str = ""


def _plan_shape(plan: "CanvasEditPlan") -> str:
    """One-line description of a plan, for the repair-exchange log."""
    if plan is None:
        return "None"
    ops = list(plan.ops or [])
    return (
        f"wants_edit={bool(plan.wants_edit)} edit_mode={plan.edit_mode!r} "
        f"ops={len(ops)}[{_ops_preview(ops)}] "
        f"replacement={'set' if (plan.updated_content_json or '').strip() else 'empty'} "
        f"restore={'set' if (plan.restore_audit_id or '').strip() else 'empty'} "
        f"violation={plan_contract_violation(plan)}")


def plan_contract_violation(plan: "CanvasEditPlan") -> Optional[str]:
    """The SCHEMA-BOUNDARY contract check (2026-09-28).

    A plan must be exactly one of three forms:

      (1) DECLINE          wants_edit=false AND no ops AND no replacement
                           content AND no restore id
      (2) OPERATION EDIT   wants_edit=true  AND ops present
      (3) FULL REPLACEMENT wants_edit=true  AND updated_content_json present

    Returns None when the plan is one of those, else a description naming the
    CONCRETE conflicting fields, which is what the bounded repair is told.

    This runs where the plan is parsed, so a contradictory answer is caught
    before it can be mistaken for an accepted plan downstream. It deliberately
    does NOT normalise the plan: silently flipping wants_edit to True would
    manufacture an edit the planner did not authorise, and the lifecycle gate
    upstream must keep being the thing that decides whether a canvas may change.
    """
    if plan is None:
        return "no plan"
    ops = list(plan.ops or [])
    replacement = (plan.updated_content_json or "").strip()
    restore = (plan.restore_audit_id or "").strip()
    wants = bool(plan.wants_edit)
    if not wants:
        conflicting = []
        if ops:
            conflicting.append(f"ops[{len(ops)}]={_ops_preview(ops)}")
        if replacement:
            conflicting.append("updated_content_json=<set>")
        if restore:
            conflicting.append("restore_audit_id=<set>")
        if conflicting:
            return ("wants_edit=false but " + " AND ".join(conflicting)
                    + " (legal forms: decline with all three empty, or "
                      "wants_edit=true with the work)")
        return None
    # wants_edit=true must actually carry the work it claims.
    if not (ops or replacement or restore):
        return ("wants_edit=true but ops=[] AND updated_content_json=<empty> "
                "AND restore_audit_id=<empty> (an edit claim with no work)")
    return None


def _ops_preview(ops: List[Any], limit: int = 2) -> str:
    out = []
    for op in list(ops)[:limit]:
        field = getattr(op, "field", None) or "?"
        find = str(getattr(op, "find", "") or "")[:24]
        out.append(f"{{field={field},find={find!r}}}")
    return "; ".join(out)


class CanvasPlanUnavailable(Exception):
    """The planning LLM call failed (provider down / timeout / no JSON).
    Distinct from ``None`` (a legitimate "this turn is not an edit"): callers
    must NOT fall through to generic intent routing on this — an edit-shaped
    request misfiled into TASK_MANAGEMENT produces a chat reply claiming the
    edit succeeded while the canvas never changed (observed live 2026-08-31:
    "Append this exact line … LIVEUPDATEcheck456" answered with a false
    success, no audit row, no broadcast)."""


def _small_edit_shape(message: str, prompt_len: int) -> bool:
    """A HEADER/SMALL edit: short instruction, no fresh-data section, no
    multi-row vocabulary. Its plan is a couple of find→replace ops — a
    14k-token output reservation buys nothing and costs deadline (owner
    systemic item 4, 2026-10-08: a small header change entered the
    heavyweight path and lost its budget before producing a patch)."""
    msg = str(message or "")
    if prompt_len > 24000:
        return False
    probe = msg.lower().replace("everything else", "")
    if any(w in probe for w in (
            "row", "table", "all ", "every", "rebuild", "regenerate",
            "rewrite the", "entire", "whole")):
        return False
    return len(msg) <= 220


async def _plan_structured(
    llm_service: Any,
    *,
    prompt: str,
    response_model: Any,
    system_instruction: str,
    message: str = "",
) -> Any:
    """Structured canvas-planning call routed by BPC (no model pin).

    Routing is deliberately left to BPC so model choice stays dynamic —
    cost/quality/health aware, and free to move off a model that is briefly
    rate-limited. The call is still SHAPED as a small non-reasoning plan
    (``disable_reasoning=True``, temperature 0), which is what the old
    hardcoded pin was really buying: reasoning models ignore the disable flag
    and burn 1,100–2,000 hidden tokens / 30–75s on a 60-line planning answer,
    which blew this stage's 30s budget.

    Fault-isolated: a provider error returns ``None`` so the caller keeps its
    own failure contract (``CanvasPlanUnavailable`` for an infrastructure
    failure vs ``None`` for a genuine "not an edit").
    """
    from core.llm.pinned_planning import (
        build_provider_model_pin,
        pinned_structured_call,
    )

    # ASYNC-TIER EDIT-PLAN RUNG (2026-09-22): operator knob pointing the
    # edit-plan structured call at a schema-capable model for BACKGROUND
    # retries (ATOM_ASYNC_EDIT_PLAN_MODEL="provider/model"). Rationale: the
    # interactive cost ladder can land on flash rungs whose outputs fail
    # CanvasEditPlan schema validation (live: HTTP 200s, "providers failed,
    # last error: None"), and the async tier — with its relaxed timeout and
    # backoff — is exactly where a slower, schema-capable rung fits. Empty
    # or unset = no pin (BPC ranks), byte-identical to before.
    import os as _os

    _pin = {}
    _edit_plan_max_tokens = int(
        _os.getenv("ATOM_ASYNC_EDIT_PLAN_MAX_TOKENS", "14000") or 14000)
    # WORKLOAD-AWARE ALLOWANCE (owner systemic item 4): a small/header
    # edit plans in a 2,000-token envelope — the multi-row 14k
    # reservation exists for whole-table patch payloads, and asking a
    # small edit to carry it spends the interactive deadline on output
    # space the plan will never use.
    if _small_edit_shape(message, len(prompt or "")):
        _edit_plan_max_tokens = min(
            _edit_plan_max_tokens,
            int(_os.getenv("ATOM_SMALL_EDIT_MAX_TOKENS", "2000") or 2000))
    _pin_spec = (_os.getenv("ATOM_ASYNC_EDIT_PLAN_MODEL") or "").strip()
    if _pin_spec and "/" in _pin_spec:
        _prov, _mod = _pin_spec.split("/", 1)
        _pin = build_provider_model_pin(llm_service, _prov.strip(),
                                        _mod.strip())

    return await pinned_structured_call(
        llm_service,
        prompt=prompt,
        response_model=response_model,
        system_instruction=system_instruction,
        call_kwargs=_pin or None,
        log_label="canvas edit planning",
        task_type="planning",
        # A multi-row table rebuild via patch ops carries LARGE replace
        # payloads (full HTML blocks) — the 6000-token default truncated
        # the plan mid-JSON (live 2026-09-23). The cap rides extra_kwargs
        # so it ALSO applies to the unpinned fallback (the pin-only
        # call_kwargs were dropped on the retry — review finding 3).
        extra_kwargs={"max_tokens": _edit_plan_max_tokens},
    )


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
- REFERENTIAL VALUES (2026-10-02 live, the 'update the prices that were
  found in the email' turn): when the request references values by their
  SOURCE instead of naming them ('the prices found in the email', 'the
  numbers from the quote', 'your latest findings', 'the confirmed
  values'), RESOLVE them from the Recent conversation section — it
  carries the agent's own replies with the exact figures. Emit ops whose
  "replace" holds the CONCRETE value quoted there (e.g. "$2,902.00") and
  whose "find" is the canvas's current text for that same row, copied
  verbatim. NEVER emit an op whose replace is a description ("the email
  price") or leave a value unresolved because the user didn't type it —
  the conversation is the authority the request points at. If a
  referenced value genuinely appears nowhere in the prompt, do not guess
  and do not emit a vague op: wants_edit=false with a reply naming
  exactly which values are missing.
- REFERENTIAL EDITS REPORT THE FULL SET (2026-10-02 live, the 'updated
  only 1 price' misread): a plural referential instruction ("update the
  prices that were found in the email") resolved to ONE changed row is
  usually CORRECT — the other rows already match — but a reply that
  names only the change reads as if the work stopped short. The reply
  must account for EVERY referenced item: how many were checked, which
  changed (old → new), and how many already matched. Same for
  fill-in-the-blank sets: report filled vs already-correct vs missing.
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
  canvas, each stamped with its version_id. To go back to one, PREFER
  edit_mode="restore" with restore_audit_id set to that version's
  version_id (copied VERBATIM — never invented): the restore is exact and
  lossless even for content longer than the excerpt shown. Fall back to
  edit_mode="replace" copying that version's content only when no
  version_id is shown for it. Never invent text for a version that isn't
  shown; if none matches what the user describes, say so instead of
  guessing. Restoring when the user asks to go back also beats "patching"
  toward an earlier draft from memory.
- Remove meta-commentary ("Here's your draft...", "Want me to adjust...")
  from the content itself — the canvas holds only the artifact.
- Send/dispatch requests ("send it", "email it to Mark", "try sending
  again") are NOT edits: wants_edit=false — a separate step owns actions.
- TEACHING POINTS and standing guidance are NOT edits either: a message
  that states a norm, preference, or instruction for how you should work
  GOING FORWARD ("this will be the norm", "always cc the same people",
  "use different keywords when you search zoho",
  "do not change my writing unless I say so") teaches future behavior —
  it does not ask you to change THIS canvas now, so wants_edit=false and
  the canvas stays untouched. Edit only what the message explicitly asks
  to change NOW: "update cc to vipul and chandrakant. this will be the
  norm" applies the explicit cc edit; the trailing norm is guidance,
  never a license to restyle the draft to match it.
- Lookup/research requests ("web search X", "check zoho inventory",
  "what row holds the price?") are answered in chat: do NOT fold the
  findings into the canvas unless the message asks for that ("add it to
  the draft", "include that info").
- Questions, discussion, or requests about other things ("what do you
  think", "search my email") are wants_edit=false too.
- EMAIL canvases support real HTML tables (Outlook-style): when the user
  asks for tabular content (quotes, specs, comparisons, lists of options),
  insert a <table> with inline cell borders
  (style="border-collapse: collapse;" + border: 1pt solid on each cell) —
  tables render in the outgoing email, they are not stripped. Inline cell
  styles are supported the same way (background-color shading, font
  color/size, padding, width): a request to "color/shade/highlight the
  headings" means restyling the header row's <td> styles in place — keep
  their text unchanged.
- Sender identity is NEVER a guessing problem: the SENDER IDENTITY section
  (when present) names the user the draft is sent by. Never take a sender
  name or signature from the To/Cc fields — those are RECIPIENTS (a Cc'd
  colleague's first name is not the sender's). Never remove or replace an
  existing signature unless the request says to ("i added my signature,
  adjust" means polish AROUND it, not swap it for a guessed name).
- EXTERNAL FACTS are never a guessing problem either: names, figures,
  prices, dates, and specs must come from the user's message, the canvas
  content, or the FRESH DATA section (when present) — never from memory or
  plausibility. Live 2026-09-03: when no evidence is in the prompt, a price
  from the consolidated price list was typed into a draft as $14,500.00
  (the workbook said $14,145.00). If a value the request needs is in none
  of those sources, do not invent it. If the user permits an explicit
  placeholder, use one and name the missing source in `reply`; if the user
  forbids placeholders, stop and report that the edit was not applied.
- A structured SOURCE COMPARISON separates verified values, incomparable
  values, gaps, and proposed actions. Numeric equality alone does not make
  currency, unit, price basis, or effective date equivalent. A historical or
  older list is not automatically authoritative, and a newer source is not
  automatically correct. Never use an incomparable or historical-only value
  to replace the artifact. Apply only a READY CHANGE explicitly supported by
  the comparison and the user's edit request; otherwise explain the gap and
  leave the artifact unchanged.
- When the request supplies a count or a requested/alternative split, reconcile
  the complete source-backed product set before writing. Do not fill a named
  row with a generic "alternative" label, and do not invent an unnamed row to
  make the count match.
- When the request says to preserve the footer, preserve its text, signature,
  validity language, and URLs exactly; only change the product scope and values.
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
#: Appended when a plan contradicts itself. Names the CONCRETE conflicting
#: fields, restates the three legal forms, and requires exactly one of them. It
#: does not instruct the model to produce an edit -- the repair resolves an
#: inconsistency, it does not authorise anything, and the flag is never flipped
#: on the model's behalf.
_INCONSISTENT_PLAN_SUFFIX = """

IMPORTANT -- your previous answer was self-contradictory. It declared
wants_edit=false while also carrying the edit work below. Both cannot be true,
and a plan must be exactly one of these three forms:

  (1) DECLINE           wants_edit=false, ops=[], updated_content_json=null,
                        restore_audit_id=null. Use this when the user did not
                        ask you to change THIS canvas.
  (2) OPERATION EDIT    wants_edit=true, with ops=[] carrying find/replace
                        pairs against the CURRENT canvas content you were
                        shown, edit_mode="patch".
  (3) FULL REPLACEMENT  wants_edit=true, edit_mode="replace", with
                        updated_content_json holding the complete new content
                        and ops=[].

Re-answer as ONE of those three forms, choosing from the user's request and the
canvas content above. Keep the user's request and the canvas content in view.
Do not declare wants_edit=false and then carry operations. Do not invent an
edit the user did not ask for in order to fill a field.
"""


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


_SCOPE_GENERIC_TOKENS = frozenset({
    "row", "rows", "table", "machine", "machines", "item", "items", "price",
    "prices", "actual", "delivery", "lead", "time", "terms", "payment",
    "cad", "fob", "tbd", "in", "stock", "weeks", "week", "months", "month",
    "requested", "alternative", "alternatives", "option", "options", "from",
    "email", "quote", "apply", "update", "keep", "preserve", "footer",
})


def _scope_number(value: str) -> Optional[int]:
    value = str(value or "").strip().lower()
    if value.isdigit():
        return int(value)
    return {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    }.get(value)


def _scope_user_messages(history: Optional[List[Dict[str, Any]]]) -> List[str]:
    result: List[str] = []
    for entry in (history or [])[-12:]:
        if not isinstance(entry, dict):
            continue
        role = str(entry.get("role") or "").lower()
        text = str(entry.get("message") or "").strip()
        if text and role in ("", "user"):
            result.append(text)
    return result


def _requested_product_count(messages: List[str]) -> Optional[int]:
    number = r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
    for text in messages:
        lower = str(text or "").lower()
        total = re.search(
            rf"\b(?:all\s+)?{number}\s+(?:machines?|items?|rows?)\b", lower,
        )
        if total:
            value = _scope_number(total.group(1))
            if value:
                return value
        base = re.search(
            rf"\b{number}\s+(?:[a-z-]+\s+){{0,3}}"
            r"(?:machines?|items?)\b", lower,
        )
        alternatives = re.search(
            rf"\b{number}\s+(?:alternatives?|slitters?|options?)\b",
            lower,
        )
        if base and alternatives:
            left = _scope_number(base.group(1))
            right = _scope_number(alternatives.group(1))
            if left and right:
                between = lower[base.end():alternatives.start()]
                return left + right + (1 if re.search(
                    r"\b(?:sle|tgk|gsl|tk)\w*\d|\b\d{3,}\b", between) else 0)
        row_range = re.search(r"\brows?\s*(\d+)\s*(?:-|to|through)\s*(\d+)\b", lower)
        if row_range:
            return int(row_range.group(2))
    return None


def _scope_codes(messages: List[str]) -> set:
    codes = set()
    for text in messages:
        source = str(text or "").lower()
        money_numbers = set()
        for match in re.finditer(r"[$€£]\s*(\d[\d,]*(?:\.\d+)?)", source):
            money_numbers.add(match.group(1).replace(",", ""))
        for token in re.findall(
            r"\b[a-z]{1,8}[a-z0-9-]*\d[a-z0-9-]*\b|\b\d{3,}\b",
            source,
        ):
            if re.fullmatch(r"(?:19|20)\d{2}", token):
                continue
            if token.isdigit() and any(
                    token in number for number in money_numbers):
                continue
            if token not in _SCOPE_GENERIC_TOKENS:
                codes.add(token)
    return codes


def _scope_tokens(text: str) -> set:
    return {
        token.strip(".,:;()[]{}")
        for token in re.findall(r"[a-z0-9][a-z0-9._+\-]*", str(text or "").lower())
        if token.strip(".,:;()[]{}") not in _SCOPE_GENERIC_TOKENS
        and len(token.strip(".,:;()[]{}")) >= 2
    }


def _money_key(value: str) -> str:
    raw = re.sub(r"[^0-9.]", "", str(value or ""))
    try:
        return format(Decimal(raw), "f").rstrip("0").rstrip(".")
    except (InvalidOperation, ValueError):
        return raw


def _scope_requirements(messages: List[str]) -> List[Tuple[set, set, int]]:
    requirements: List[Tuple[set, set, int]] = []
    for text in messages:
        for clause in re.split(r"[;\n]+", str(text or "")):
            amounts = {
                _money_key(match)
                for match in re.findall(
                    r"[$€£]\s*\d[\d,]*(?:\.\d+)?", clause)
            }
            if not amounts:
                continue
            tokens = _scope_tokens(clause)
            strong = {
                token for token in tokens
                if any(ch.isdigit() for ch in token) or "-" in token
            }
            if strong:
                requirements.append((amounts, strong, 1))
            elif len(tokens) >= 2:
                requirements.append((amounts, tokens, 2))
    return requirements


def _body_from_content(content: Any) -> str:
    if isinstance(content, dict):
        return str(content.get("body") or content.get("content") or "")
    return str(content or "")


def _html_text(value: str) -> str:
    return re.sub(
        r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    ).strip()


def _table_rows(body: str) -> List[List[str]]:
    text = str(body or "")
    rows: List[List[str]] = []
    if "<table" in text.lower():
        for row_html in re.findall(
            r"<tr\b[^>]*>(.*?)</tr>", text, re.IGNORECASE | re.DOTALL
        ):
            cells = [
                _html_text(cell)
                for cell in re.findall(
                    r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row_html,
                    re.IGNORECASE | re.DOTALL,
                )
            ]
            if cells:
                rows.append(cells)
    else:
        for line in text.splitlines():
            if "|" not in line:
                continue
            cells = [_html_text(cell) for cell in line.strip().strip("|").split("|")]
            if cells:
                rows.append(cells)
    if rows and (
        rows[0][0].strip().lower() in {"#", "no", "number"}
        or any(cell.strip().lower() in {"description", "unit price", "delivery"}
               for cell in rows[0])
    ):
        rows = rows[1:]
    return rows


def artifact_observations(
    canvas: Dict[str, Any],
    *,
    requested_entities: List[str],
    requested_fields: List[str],
    source: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    from core.workbook_read_artifact import (
        _canonical_field_name,
        _text_organization,
        observations_from_text,
    )

    content = (canvas or {}).get("content")
    body = _body_from_content(content)
    source_data = dict(source or {})
    source_data.setdefault(
        "source_id",
        str((canvas or {}).get("canvas_id") or "canvas-artifact"),
    )
    source_data.setdefault("source_type", "artifact")
    source_data.setdefault("version", source_data.get("source_id"))
    rows: List[Any] = []
    if isinstance(content, dict) and isinstance(content.get("rows"), list):
        rows = content["rows"]
    elif isinstance(content, list):
        rows = content
    if not rows:
        matrix: List[List[str]] = []
        if "<table" in body.lower():
            for row_html in re.findall(
                r"<tr\b[^>]*>(.*?)</tr>", body, re.IGNORECASE | re.DOTALL
            ):
                cells = [
                    _html_text(cell)
                    for cell in re.findall(
                        r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row_html,
                        re.IGNORECASE | re.DOTALL,
                    )
                ]
                if cells:
                    matrix.append(cells)
        else:
            for line in body.splitlines():
                if "|" not in line:
                    continue
                cells = [
                    _html_text(cell)
                    for cell in line.strip().strip("|").split("|")
                ]
                if cells and not all(
                    re.fullmatch(r"\s*:?-{3,}:?\s*", cell) for cell in cells
                ):
                    matrix.append(cells)
        rows = matrix
    if not rows:
        return observations_from_text(
            body,
            requested_entities=requested_entities,
            requested_fields=requested_fields,
            source=source_data,
            verification="verified",
        )
    if isinstance(rows[0], dict):
        field_rows = [
            {
                str(key): str(value if value is not None else "")
                for key, value in row.items()
            }
            for row in rows
            if isinstance(row, dict)
        ]
        headers = list(field_rows[0].keys()) if field_rows else []
        first_data_row = 1
    else:
        normalized_rows = [
            [
                str(cell if cell is not None else "")
                for cell in row
            ]
            if isinstance(row, (list, tuple))
            else [str(row if row is not None else "")]
            for row in rows
        ]
        if (
            len(normalized_rows) == 1
            and len(requested_fields or []) == 1
            and len(normalized_rows[0]) >= 2
        ):
            headers = ["entity", str(requested_fields[0])]
            field_rows = [dict(zip(headers, normalized_rows[0]))]
            first_data_row = 1
        else:
            headers = normalized_rows[0] if normalized_rows else []
            field_rows = [
                dict(zip(headers, row + [""] * max(0, len(headers) - len(row))))
                for row in normalized_rows[1:]
            ]
            first_data_row = 2
    identity_fields = {
        "model", "model_number", "machine", "item", "product", "part",
        "sku", "code", "id", "name", "description",
    }
    value_fields = {
        "price", "cost", "amount", "rate", "value", "currency", "basis",
        "quantity", "weight", "lead_time", "delivery",
    }
    identity_headers = [
        header for header in headers
        if _canonical_field_name(header) in identity_fields
    ]
    search_headers = identity_headers or [
        header for header in headers
        if _canonical_field_name(header) not in value_fields
    ]
    observations: List[Dict[str, Any]] = []
    for entity in requested_entities or []:
        entity_text = str(entity or "").strip()
        if not entity_text:
            continue
        matching_rows: List[Tuple[int, Dict[str, Any], str, int]] = []
        for row_number, row in enumerate(field_rows, start=first_data_row):
            for header in search_headers:
                text = str(row.get(header) or "").strip()
                match = re.search(
                    rf"(?<![A-Za-z0-9_-]){re.escape(entity_text)}"
                    rf"(?![A-Za-z0-9_-])",
                    text,
                    re.IGNORECASE,
                )
                if match:
                    matching_rows.append((row_number, row, str(header), match.start()))
                    break
        for row_number, row, identity_header, match_start in matching_rows:
            entity_attributes: Dict[str, str] = {}
            for header in headers:
                canonical_header = _canonical_field_name(header)
                if canonical_header not in {
                    "organization", "manufacturer", "vendor", "supplier",
                }:
                    continue
                value = str(row.get(header) or "").strip()
                if value:
                    entity_attributes["organization"] = value
            if not entity_attributes:
                organization = _text_organization(
                    str(row.get(identity_header) or "")[:match_start]
                )
                if organization:
                    entity_attributes["organization"] = organization
            for requested_field in requested_fields or []:
                field = _canonical_field_name(requested_field)
                matching_headers = [
                    header
                    for header in headers
                    if _canonical_field_name(header) == field
                    or field in re.sub(
                        r"[^a-z0-9]+", " ", str(header).casefold()
                    )
                ]
                for header in matching_headers:
                    raw_value = str(
                        row.get(header)
                        if row.get(header) is not None
                        else ""
                    ).strip()
                    synthetic = f"{entity_text}: {raw_value}\n{body}"
                    verification = (
                        "ambiguous"
                        if len(matching_headers) > 1
                        else "field_missing"
                        if not raw_value or raw_value.casefold() in {"tbd", "n/a"}
                        else "verified"
                    )
                    extracted = observations_from_text(
                        synthetic,
                        requested_entities=[entity_text],
                        requested_fields=[requested_field],
                        source=source_data,
                        verification=verification,
                    )
                    for observation in extracted[:1]:
                        observation["field_meaning"] = str(header)
                        observation["entity_attributes"] = dict(
                            entity_attributes
                        )
                        observation["observation_id"] = (
                            f"{source_data['source_id']}:"
                            f"{source_data.get('version') or 'current'}:"
                            f"{row_number}:{entity_text}:{field}:{header}"
                        )
                        observation["locator"] = {
                            "row": row_number,
                            "column": str(header),
                            "source_id": source_data["source_id"],
                        }
                        observations.append(observation)
    return observations


def _contract_entities(
        evidence_contract: Optional[Dict[str, Any]]) -> List[str]:
    """Entity identities the evidence contract tracks — the field
    contract's own subjects, not a product-specific vocabulary."""
    out: List[str] = []
    seen = set()
    for outcome in ((evidence_contract or {}).get("outcomes") or []):
        if isinstance(outcome, dict):
            eid = str(outcome.get("entity_id") or "").strip()
            if eid and eid.lower() not in seen:
                seen.add(eid.lower())
                out.append(eid)
    for action in ((evidence_contract or {}).get("actions") or []):
        if isinstance(action, dict):
            eid = str(action.get("entity_id") or "").strip()
            if eid and eid.lower() not in seen:
                seen.add(eid.lower())
                out.append(eid)
    return out[:24]


def build_canvas_evidence_comparison(
    canvas: Dict[str, Any],
    workbook_read: Dict[str, Any],
    *,
    source_observations: Optional[List[Dict[str, Any]]] = None,
    decision_source_ids: Optional[List[str]] = None,
    authorized_actions: Optional[List[str]] = None,
    objective_text: str = "",
) -> Dict[str, Any]:
    from core.workbook_read_artifact import (
        build_source_comparison,
        designated_source_ids,
        workbook_artifact_observations,
    )

    coverage = (workbook_read or {}).get("coverage") or {}
    requested_entities = [
        str(outcome.get("target") or "")
        for outcome in coverage.get("outcomes") or []
        if isinstance(outcome, dict) and outcome.get("target")
    ]
    if not requested_entities:
        requested_entities = list(dict.fromkeys(
            str(observation.get("entity_id") or "")
            for observation in source_observations or []
            if isinstance(observation, dict)
            and str(observation.get("entity_id") or "").strip()
        ))
    requested_fields: List[str] = []
    for outcome in coverage.get("outcomes") or []:
        if not isinstance(outcome, dict):
            continue
        selections = [outcome.get("field_selection")]
        selections.extend(
            evidence.get("field_selection")
            for evidence in outcome.get("evidence") or []
            if isinstance(evidence, dict)
        )
        for selection in selections:
            if not isinstance(selection, dict):
                continue
            for field in selection.get("requested_fields") or []:
                if field not in requested_fields:
                    requested_fields.append(str(field))
    for observation in source_observations or []:
        field = str((observation or {}).get("field") or "")
        if field and field not in requested_fields:
            requested_fields.append(field)
    if not requested_fields:
        requested_fields = ["price"]
    canvas_source_id = str((canvas or {}).get("canvas_id") or "canvas-artifact")
    draft_observations = artifact_observations(
        canvas,
        requested_entities=requested_entities,
        requested_fields=requested_fields,
        source={
            "source_id": canvas_source_id,
            "source_type": "artifact",
            "version": canvas_source_id,
        },
    )
    observations = workbook_artifact_observations(workbook_read)
    observations.extend(draft_observations)
    observations.extend(
        observation
        for observation in source_observations or []
        if isinstance(observation, dict)
    )
    decision_ids = list(
        decision_source_ids
        if decision_source_ids is not None
        else designated_source_ids(objective_text, source_observations or [])
    )
    return build_source_comparison(
        observations,
        requested_entities=requested_entities,
        requested_fields=requested_fields,
        artifact_source_ids=[canvas_source_id],
        decision_source_ids=decision_ids,
        authorized_actions=authorized_actions or [],
    )


def _footer_start(body: str, after: int = 0) -> Optional[int]:
    lower = str(body or "").lower()
    positions = [
        lower.find(marker, after)
        for marker in (
            "unit price:", "unit price", "fob:", "payment terms:",
            "regards", "visit our web site", "all quotes are valid",
        )
    ]
    positions = [position for position in positions if position >= 0]
    return min(positions) if positions else None


def _bounded_email_content(
    current: Any, proposed: Any,
) -> Optional[Dict[str, Any]]:
    if not isinstance(current, dict) or not isinstance(proposed, dict):
        return None
    old_body = str(current.get("body") or "")
    new_body = str(proposed.get("body") or "")
    old_table = re.search(
        r"<table\b[^>]*>.*?</table>", old_body, re.IGNORECASE | re.DOTALL)
    new_table = re.search(
        r"<table\b[^>]*>.*?</table>", new_body, re.IGNORECASE | re.DOTALL)
    if not old_table or not new_table:
        return None
    old_footer = _footer_start(old_body, old_table.end())
    new_footer = _footer_start(new_body, new_table.end())
    if old_footer is None or new_footer is None:
        return None
    bounded_body = (
        old_body[:old_table.start()]
        + new_table.group(0)
        + new_body[new_table.end():new_footer]
        + old_body[old_footer:]
    )
    merged = dict(current)
    merged["body"] = bounded_body
    return merged


# A reply CLAIMING a canvas change was made ("updated the email",
# "applied the change", "updated quote below"). Deliberately generic
# across artifacts and businesses; denials ("didn't apply", "still
# running") and questions never match. Consumed by the chat reply gate
# that replaces an unbacked success claim with the honest outcome.
_CANVAS_SUCCESS_CLAIM_RE = re.compile(
    r"\b(?:updated|revised|applied|swapped|replaced)\b[^.\n]{0,60}?"
    r"\b(?:email|draft|canvas|quote|table|document)\b"
    r"|\bupdated quote below\b"
    r"|\bquote below\b",
    re.IGNORECASE,
)
_CANVAS_CLAIM_NEGATION_RE = re.compile(
    r"\b(?:didn'?t|did not|could not|couldn'?t|cannot|can't|not)\b"
    r"[^.]{0,60}\b(?:updated|applied|changed|applied the change)\b"
    r"|\bstill running in the background\b",
    re.IGNORECASE,
)


def reply_claims_canvas_change(text: str) -> bool:
    """Whether a reply claims a canvas change was made (success wording).

    Negations and pending/background wording are not claims. Generic
    across artifacts; no business vocabulary.
    """
    t = str(text or "")
    if not t:
        return False
    if _CANVAS_CLAIM_NEGATION_RE.search(t):
        return False
    return bool(_CANVAS_SUCCESS_CLAIM_RE.search(t))


def canvas_operation_has_receipt(
    user_id: Any, canvas_id: Any, execution_id: Any,
) -> bool:
    """Whether a canvas_audit row carries THIS operation's id — the
    receipt that a claimed change actually landed. Fault-isolated: any
    failure returns False (no receipt), never raises."""
    try:
        from core.database import get_db_session
        from core.models import CanvasAudit

        with get_db_session() as db:
            row = (
                db.query(CanvasAudit)
                .filter(
                    CanvasAudit.canvas_id == str(canvas_id),
                    CanvasAudit.details_json.like(
                        f'%{{"operation_id": "{str(execution_id)}"%'),
                )
                .first()
            )
            return row is not None
    except Exception:  # noqa: BLE001 — no receipt on any failure
        return False


def _scope_placeholder_violations(body: str, rows: List[List[str]]) -> List[str]:
    violations: List[str] = []
    if re.search(r"\[[^\]]+\]", body):
        violations.append("bracketed_label")
    for row in rows:
        for cell in row[1:]:
            if re.search(r"\bTBD\b|to be determined|description needed|price needed", cell, re.I):
                violations.append("unresolved_product_cell")
                break
    if re.search(
        r"(?:pricing|price|lead time|delivery).{0,50}(?:follow|shortly|needed)",
        body, re.IGNORECASE | re.DOTALL,
    ):
        violations.append("unresolved_followup")
    return sorted(set(violations))


def _validate_scoped_edit(
    current: Any,
    new_content: Any,
    request_messages: List[str],
    preserve_footer: bool = False,
) -> Optional[str]:
    if not request_messages:
        return None
    request_text = " ".join(request_messages)
    lower_request = request_text.lower()
    if not re.search(
        r"price|lead time|delivery|actual|quote|table|row|apply|update|fill",
        lower_request,
    ):
        return None
    old_body = _body_from_content(current)
    new_body = _body_from_content(new_content)
    rows = _table_rows(new_body)
    expected = _requested_product_count(request_messages)
    if expected is not None and len(rows) != expected:
        return f"scope_row_count:{len(rows)}!={expected}"
    new_tokens = _scope_tokens(new_body)
    missing_codes = _scope_codes(request_messages) - new_tokens
    if missing_codes:
        return "scope_missing_product"
    # PRESERVATION (the invariant the old wide history window groped at):
    # a regeneration may not silently DROP a product identity the canvas
    # already had. Values may change -- that is what edits do; identities
    # may only leave when the instruction itself names them ("remove
    # U-22"). Sourced from the artifact's previous state, so no pasted
    # conversation data can poison it.
    dropped_identities = (
        _scope_codes([old_body])
        - _scope_codes(request_messages)
        - _scope_codes([new_body])
    )
    if dropped_identities:
        head = ",".join(sorted(dropped_identities)[:4])
        return f"scope_dropped_product:{head}"
    new_money = {
        _money_key(match)
        for match in re.findall(
            r"[$€£]\s*\d[\d,]*(?:\.\d+)?", new_body)
    }
    for amounts, identifiers, minimum in _scope_requirements(request_messages):
        if not amounts.intersection(new_money):
            return "scope_missing_price"
        if len(identifiers.intersection(new_tokens)) < minimum:
            return "scope_missing_product"
    if "alternative" in lower_request:
        if not re.search(r"alternatives?|options?", new_body, re.IGNORECASE):
            return "scope_missing_alternatives"
        if "requested" in lower_request and not re.search(
            r"requested", new_body, re.IGNORECASE
        ):
            return "scope_missing_requested_framing"
        if re.search(r"slitter\s+alternatives?", new_body, re.IGNORECASE):
            if any("rotary" in " ".join(row[1:]).lower() for row in rows):
                return "scope_wrong_alternative_category"
    if re.search(
        r"no\s+(?:square\s+brackets?|brackets?|unresolved\s+placeholders?)|"
        r"square\s+brackets?.{0,30}(?:not|never|no)",
        lower_request,
    ):
        violations = _scope_placeholder_violations(new_body, rows)
        if violations:
            return "scope_placeholder:" + ",".join(violations)
    if preserve_footer:
        old_urls = set(_extract_http_urls(old_body))
        new_urls = set(_extract_http_urls(new_body))
        if not old_urls.issubset(new_urls):
            return "footer_missing_link"
        for marker in (
            "unit price", "fob", "payment terms", "all quotes are valid",
        ):
            if marker in old_body.lower() and marker not in new_body.lower():
                return "footer_missing:" + marker.replace(" ", "_")
    return None


def _request_scope_section(
    message: str,
    history: List[Dict[str, Any]],
    fresh_data: Optional[str],
) -> str:
    messages = [message] + _scope_user_messages(history)
    count = _requested_product_count(messages)
    requirements = _scope_requirements(messages)
    if not count and not requirements and not fresh_data:
        return ""
    lines = [
        "SCOPE AND ACCEPTANCE CONTRACT — reconcile the current request with "
        "the current canvas and the retrieved source evidence before editing.",
        "The current request and source-backed evidence outrank earlier drafts; "
        "do not preserve a missing or unnamed row from an earlier attempt.",
    ]
    if count:
        lines.append(
            f"The finished product table must contain exactly {count} data "
            "rows, counting only product rows and excluding the header."
        )
    if requirements:
        lines.append(
            "Every source-backed amount and product identifier explicitly "
            "named by the request must be present in the finished table."
        )
        for text in messages:
            for clause in re.split(r"[;\n]+", text):
                if re.search(r"[$€£]\s*\d", clause):
                    lines.append("Required source item: " + clause.strip()[:240])
    if re.search(r"alternative", message, re.IGNORECASE):
        lines.append(
            "Label requested machines separately from alternatives; do not "
            "call an unnamed item or a product whose own description says "
            "rotary a slitter alternative."
        )
    if re.search(
        r"no\s+(?:square\s+brackets?|brackets?|unresolved\s+placeholders?)|"
        r"square\s+brackets?.{0,30}(?:not|never|no)",
        message, re.IGNORECASE,
    ):
        lines.append(
            "Do not put bracketed reference labels, TBD product cells, or "
            "follow-up placeholders in the customer email. Payment Terms: TBD "
            "is allowed when the source says so."
        )
    if re.search(r"footer|keep the footer|preserve", message, re.IGNORECASE):
        lines.append(
            "Preserve the existing footer, signature, validity text, and URLs "
            "byte-for-byte; change only the product scope and its values."
        )
    if fresh_data:
        lines.append(
            "Use the retrieved source figures and delivery terms; keep source "
            "references in internal evidence metadata, never as customer-facing labels."
        )
    return "\n".join(lines) + "\n\n"


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


def _job_findings_section(
        findings: Optional[Dict[str, Any]]) -> str:
    """The JOB'S DURABLE RESEARCH STATE as planner-visible ground truth
    (round 62, authorized drafting): verified findings (with sources and
    freshness limits), the owner's approved/manual values, and the OPEN
    business decisions with their candidates. The edit this section
    shapes must: APPLY verified findings, PRESERVE approved/manual
    prices exactly, KEEP unresolved choices visible as notes (never
    silently resolve them), and NEVER expose internal sourcing detail in
    customer-facing text (the taught rule)."""
    if not isinstance(findings, dict) or not findings:
        return ""
    lines: List[str] = []
    for f in findings.get("verified") or []:
        item = str(f.get("item") or "").strip()
        note = str(f.get("note") or "").strip()
        source = str(f.get("source") or "").strip()
        if item:
            lines.append(
                f"- {item}: {note}"
                + (f" (source: {source})" if source else ""))
    decisions = findings.get("open_decisions") or []
    for d in decisions:
        item = str(d.get("item") or "").strip()
        question = str(d.get("question") or "").strip()
        if item or question:
            lines.append(
                f"- UNRESOLVED {item or '(job)'}: {question} — keep "
                "visible in the draft as a note naming the choice; do "
                "NOT silently pick")
    manual = findings.get("manual_preserved") or []
    if manual:
        lines.append(
            "- APPROVED MANUAL VALUES (owner-set; preserve exactly, "
            "never overwrite with workbook values): "
            + "; ".join(str(m) for m in manual))
    freshness = findings.get("freshness_limits") or []
    if freshness:
        lines.append(
            "- FRESHNESS LIMITS (do not present these as current "
            "verification in customer-facing text): "
            + "; ".join(str(fl) for fl in freshness))
    for rule in findings.get("taught_rules") or []:
        if str(rule).strip():
            lines.append(f"- {rule} (APPLY unless the user's current "
                         "instruction contradicts it)")
    for hc in findings.get("header_candidates") or []:
        if str(hc).strip():
            lines.append(f"- HEADER (provenance-established): {hc}")
    for rc in findings.get("resolved_cc") or []:
        if str(rc).strip():
            lines.append(f"- {rc} — PRE-RESOLVED: set the cc field to "
                         "exactly these contacts")
    if not lines:
        return ""
    return (
        "JOB FINDINGS — verified research results for THIS canvas's "
        "job (durable record; source-annotated):\n"
        + "\n".join(lines)
        + "\nDrafting rules: apply verified findings AND the taught "
        "formatting/cc rules; populate header fields ONLY from the "
        "provenance-established HEADER lines above — otherwise leave "
        "them and name the specific ambiguity; preserve approved "
        "manual values byte-for-byte; annotate unresolved choices "
        "without choosing, and keep such internal decision notes "
        "VISIBLY SEPARATE from customer-facing content (e.g. a clearly "
        "marked 'Still yours to decide' block, never woven into the "
        "customer text); internal sourcing detail stays OUT of "
        "customer-facing text, BUT freshness limits on customer-"
        "relevant claims (availability, delivery estimates, quote "
        "validity) must NOT become unconditional commitments — where "
        "evidence is insufficient, OMIT the commitment or qualify it "
        "to what the evidence supports.\n\n"
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
        version_id = str(v.get("audit_id") or "").strip()
        trimmed = text[:_VERSION_CHARS] + ("…(trimmed)" if len(text) > _VERSION_CHARS else "")
        stamp = f"[{when} — {actor}{title}]"
        if version_id:
            stamp += f" version_id: {version_id}"
        lines.append(f"{stamp}\n{trimmed}")

    if not lines:
        return ""
    return (
        "RECENT VERSIONS of this canvas (newest first, trimmed; each carries "
        "its version_id). If the user asks to go back to / restore / revert "
        "to an earlier version or their original draft, pick the version they "
        "mean and return edit_mode=\"restore\" with restore_audit_id set to "
        "that version's version_id — exact, lossless, and preferred over "
        "copying the excerpt. Only when no version_id is shown fall back to "
        "edit_mode=\"replace\" with that version's content VERBATIM. Never "
        "invent a version_id or text for a version that isn't shown here; if "
        "none matches, say so.\n"
        + "\n---\n".join(lines) + "\n\n"
    )


# Evidence gathering must never cost the edit its own turn: the planner call
# and the tool execution it triggers live inside this bound. On timeout the
# edit is DECLINED (see FreshDataResult) — proceeding without evidence made
# the editor fabricate values on the user's real draft (live 2026-09-04:
# 'In Stock' delivery + placeholder price invented when the lookup timed
# out). 20s: the lookup now includes the planner's repair pass and the
# storage query rewrite, so 12s false-timed-out constantly. 25s (the top of
# the orchestrator-compatible band, 2026-09-06): the lookup also covers a
# storage READ — query rewrite + download + parse. The live case was
# Consolidated Price List 2019.xlsx (13MB, ~10s parse alone), and the read
# timed out twice, so the data-dependent edit declined and the price the
# user asked to fill in was never filled. Repeat reads of the same bytes
# now hit the parse-result cache (DocumentParser.parse_document_cached),
# so only the first cold read needs the extra seconds; a lookup that still
# overruns declines the edit unchanged — never fabricates.
_FRESH_DATA_TIMEOUT_SECONDS = 25

# The PLANNER is the shared chat-leg call (_tool_plan_task): the turn pays its
# latency either way, so it must not be charged against the evidence budget
# above. A planner overrun also says NOTHING about whether the edit needs live
# data — treating it as "needs data" declined data-INDEPENDENT edits (live
# 2026-09-11: a header-style edit was declined because the shared planner took
# ~62s, and the fallback reply then claimed the edit had landed). Bounded
# separately and generously; if even this is exceeded the edit declines with
# the honest no-edit flag.
_FRESH_DATA_PLAN_TIMEOUT_SECONDS = 75


class FreshDataResult(NamedTuple):
    """Outcome of the edit's live-evidence lookup.

    needed=False            — the planner saw no live-data need; the edit
                              may proceed without evidence.
    needed=True, ok=True    — ``section`` carries real tool evidence.
    needed=True, ok=False   — a live-data need EXISTED but the lookup
                              failed/timed out. Callers must decline the
                              edit: applying guessed values is fabrication.

    ``block`` carries the raw LIVE TOOL RESULTS block for reuse by the
    chat leg when the turn turns out NOT to be an edit — without it the
    chat leg re-planned AND re-executed the identical lookup, doubling
    latency and provider calls on every canvas research turn.
    """

    section: str
    needed: bool
    ok: bool
    block: str = ""
    # 2026-09-22: distinguishes a planner-level OFF-REQUEST decline (the
    # planned lookup did not address the current request, so nothing ran)
    # from a genuine lookup failure. Both decline the edit, but the reply
    # must not tell the user a lookup "failed" when none executed — that
    # false report is the live incident's second defect.
    declined_irrelevant: bool = False
    evidence_contract: Optional[Dict[str, Any]] = None


def _contract_from_receipt(reused: Dict[str, Any]) -> Dict[str, Any]:
    """Derive the readiness gate's evidence contract from a structured
    read receipt — recording only what the read OBSERVED.

    A chained datasets read returns a structured result (subject, field,
    parsed value with its basis/unit/currency, source identity and
    revision, freshness qualification). The readiness gate reads a
    different shape (`evidence_contract`). Rather than invent values or
    an authorized change to satisfy that shape, this maps the receipt's
    own fields across and states plainly that the read authorized NO
    value-changing edit.

    Required by the research-to-draft guide: preserve subject, field,
    value, source/version and freshness TOGETHER.
    """
    sr = reused.get("structured_result") if isinstance(reused, dict) else None
    sr = sr if isinstance(sr, dict) else {}
    src = sr.get("source_identity") if isinstance(
        sr.get("source_identity"), dict) else {}
    targets = sr.get("targets") if isinstance(sr.get("targets"), list) else []

    evidence: List[Dict[str, Any]] = []
    for t in targets:
        if not isinstance(t, dict):
            continue
        subject = str(t.get("item") or "")
        fld = t.get("field") if isinstance(t.get("field"), dict) else {}
        vals = fld.get("values") if isinstance(fld.get("values"), list) else []
        ident = t.get("identity") if isinstance(t.get("identity"), dict) else {}
        refs = []
        for c in (ident.get("candidates") or []):
            if isinstance(c, dict) and c.get("ref"):
                refs.append(str(c.get("ref")))
        for v in vals:
            if not isinstance(v, dict):
                continue
            evidence.append({
                "kind": "workbook_cell",
                "entity_id": subject,
                "field": str(v.get("col") or v.get("basis") or ""),
                "current_value": v.get("value"),
                "raw_value": v.get("display"),
                "basis": v.get("basis"),
                "unit": v.get("unit"),
                "currency": v.get("currency"),
                "source": (refs[0] if refs else ""),
                "source_id": src.get("resource_id"),
                "source_version": sr.get("evidence_revision"),
                "content_hash": src.get("content_hash"),
                "evidence_kind": src.get("evidence_kind"),
                "live_vs_saved": src.get("live_vs_saved"),
                "freshness": (
                    "unknown live freshness"
                    if not src.get("source_modified_at")
                    else f"source_modified={src.get('source_modified_at')}"),
                "addresses_requested": True,
            })

    return {
        "contract_version": 2,
        "source": {
            "file_name": src.get("file_name"),
            "service": src.get("service"),
            "source": src.get("source"),
            "resource_id": src.get("resource_id"),
            "content_hash": src.get("content_hash"),
            "evidence_revision": sr.get("evidence_revision"),
            "evidence_kind": src.get("evidence_kind"),
            "live_vs_saved": src.get("live_vs_saved"),
            "ingested_at": src.get("ingested_at"),
            "source_modified_at": src.get("source_modified_at"),
        },
        "coverage": {
            "requested_entities": sorted({
                str(t.get("item") or "") for t in targets
                if isinstance(t, dict) and t.get("item")}),
            "requested_fields": list(
                (sr.get("requested_fields") or [])[:8]),
            "outcome_count": len(evidence),
            "complete": bool(sr.get("coverage", {}).get("read_status")
                             == "success"),
        },
        # The read authorized NO value-changing edit. Anything that would
        # change a currency/number still needs its own ready, authorized
        # evidence action — this contract never supplies one.
        "actions": [],
        "evidence": evidence,
        "evidence_refs": [e["source"] for e in evidence if e.get("source")],
    }


async def fetch_fresh_data_section(
    message: str,
    history: List[Dict[str, Any]],
    llm_service: Any,
    user_id: Optional[str],
    canvas_id: Optional[str] = None,
    step_recorder: Optional[Callable[[str, Dict[str, Any], str], Awaitable[None]]] = None,
    canvas: Optional[Dict[str, Any]] = None,
    plan_task: Optional[Any] = None,
    existing_block: Optional[str] = None,
    allow_canvas_target: bool = True,
    existing_evidence_contract: Optional[Dict[str, Any]] = None,
    authorized_actions: Optional[List[str]] = None,
    request_scope: Optional[Dict[str, Any]] = None,
    reused_findings: Optional[Dict[str, Any]] = None,
) -> FreshDataResult:
    """LIVE evidence for edit requests that hinge on data the editor cannot
    see — a price "from the consolidated price list", specs from a drive
    file, a status only the CRM knows. Runs the SAME read-only tool planner
    the chat path uses (core.chat_tool_planner) and returns the shaped
    section for plan_canvas_edit's prompt. Called by the CONTEXT ASSEMBLER
    (the chat orchestrator, alongside corrections/versions/lessons) — NOT
    inside plan_canvas_edit, which owns a single structured LLM call and
    must not fire extra ones (its callers' replan ladders and tests count
    those calls).

    ``step_recorder`` (async (step_type, action, observation)) records the
    live lookup into the same reasoning-step trail the chat lane writes —
    the co-editor lane previously ran real provider calls with NO recorded
    evidence, making the audit trail unverifiable (live 2026-09-04: an
    applied "In Stock" edit whose search existed only in gatekeeper logs).

    Live 2026-09-03: with no evidence in the prompt, the editor typed
    $14,500.00 into an email draft as "the price from the consolidated
    price list" (the workbook said $14,145.00) and then "confirmed" the
    user's corrected value just as baselessly. Live 2026-09-04: when the
    lookup timed out, it invented 'In Stock' delivery on the real draft.
    Hence the three-state result: a data-dependent edit whose lookup failed
    must be DECLINED by the caller, never applied on guesses."""
    async def _record(step_type: str, action: Dict[str, Any],
                      observation: str) -> None:
        if step_recorder is None:
            return
        try:
            await step_recorder(step_type, action, observation)
        except Exception as rec_err:  # noqa: BLE001 — recording never blocks
            logger.debug(f"fresh-data step recording skipped: {rec_err}")

    # RECEIPT-BASED REUSE (research-to-draft guide Repair 2, 2026-10-08):
    # durable structured findings from a prior read (same conversation
    # carrier) satisfy the edit's evidence need WITHOUT a new provider
    # call — and are labeled REUSED with their original source identity,
    # never "fetched just now". Validity is the STRUCTURED RECEIPT
    # (observations present), not text non-emptiness.
    #
    # This runs BEFORE the provider guard below on purpose: it needs no
    # model at all. Required pin (Repair 2): "readable durable finding plus
    # unavailable LLM narration still reaches drafting". Gating it on
    # ``llm_service`` made a readable, already-paid-for finding unreachable
    # whenever the model was unavailable — the exact shape of the captured
    # case-1 transition (evidence_contract=False with the workbook already
    # read earlier in the conversation).
    if isinstance(reused_findings, dict):
        _rf_obs = (
            reused_findings.get("source_observations")
            or ((reused_findings.get("structured_result") or {})
                .get("targets"))
            or [])
        _rf_render = str(reused_findings.get("rendered") or "")
        if _rf_obs and _rf_render:
            _rf_ident = reused_findings.get("identity") or {}
            _rf_name = str(
                _rf_ident.get("file_name") or "the resolved file")
            # CONTRACT FROM THE RECEIPT (research-to-draft guide Repair 2):
            # the readiness gate reads `evidence_contract`, while a chained
            # datasets read produces a STRUCTURED RESULT (subject, field,
            # parsed value with basis/unit/currency, source identity and
            # revision, freshness). When no explicit contract was carried,
            # derive one from the receipt's OWN fields — recording what the
            # read observed, never inventing a value or an authorized
            # change. `actions: []` is the truthful statement that this
            # read authorized no value-changing edit.
            _rf_contract = (
                dict(existing_evidence_contract)
                if isinstance(existing_evidence_contract, dict)
                else reused_findings.get("objective_evidence"))
            if not isinstance(_rf_contract, dict):
                _rf_contract = _contract_from_receipt(reused_findings)
            return FreshDataResult(
                section=(
                    "REUSED FINDINGS (durable structured evidence "
                    "from this conversation's earlier read of "
                    f"'{_rf_name}', source identity and revision as "
                    "recorded — not re-fetched this turn):\n"
                    f"{_rf_render[:12000]}\n\n"
                ),
                needed=False,
                ok=True,
                block=_rf_render[:16000],
                evidence_contract=_rf_contract,
            )

    if not message or llm_service is None:
        return FreshDataResult("", False, True)

    try:
        from core.chat_tool_planner import execute_tool_plan, plan_tool_use

        # REUSE: an earlier leg on this turn already planned AND executed
        # — reformat its block instead of hitting providers a second
        # (or third) time with the identical query.
        if existing_block:
            return FreshDataResult(
                section=(
                    "FRESH DATA for this edit (live tool results, fetched just "
                    f"now):\n{existing_block}\n\n"
                ),
                needed=True,
                ok=True,
                block=existing_block,
                evidence_contract=(
                    dict(existing_evidence_contract)
                    if isinstance(existing_evidence_contract, dict)
                    else None
                ),
            )

        async def _resolve_plan() -> Any:
            """The SINGLEFLIGHT planner call: plan_tool_use is one structured
            LLM call per turn, and the chat leg pre-starts it
            (_tool_plan_task). Join the in-flight call instead of paying for a
            second one; a second planner pass re-decided the same need from
            the same words and doubled planning latency on every canvas turn.
            The chat leg awaits this same task, so waiting here adds no work
            the turn wasn't already doing."""
            if plan_task is not None:
                # SHIELD: this leg's timeout must NOT cancel the shared task
                # — cancellation propagates through a plain `await task` and
                # would poison it for the chat leg (live 2026-09-08: a
                # fresh-data timeout killed the plan task → whole turn
                # failed). The shield keeps it running for the chat leg.
                try:
                    return await asyncio.shield(plan_task)
                except asyncio.CancelledError:
                    raise
                except Exception as plan_err:  # noqa: BLE001
                    # A failed SHARED plan is a provider hiccup, not a
                    # live-data need: the chat leg owns the retry, so proceed
                    # without evidence (pre-existing contract).
                    logger.debug(f"shared tool plan failed: {plan_err}")
                    return None
            # Fallback (no shared task from the chat leg): the same
            # context the orchestrator's pre-started plan gets — the open
            # canvas and the provenance menu. Without these the editor's
            # own plan routed blind (the planner-blindness family, live
            # 2026-09-14 canvas a1a13834: a pasted vendor line planned into
            # zoho_inventory). Bounded + fault-isolated: menu failure
            # degrades to the pre-existing bare call.
            try:
                from core.chat_tool_planner import _provenance_menu

                prov = await asyncio.wait_for(
                    _provenance_menu(message, {"history": history}), timeout=6)
            except Exception:  # noqa: BLE001 — menu is best-effort
                prov = ""
            # SOURCE HANDLES (RCA 2026-09-17 finding 3): files the
            # conversation already located, re-extracted from the transcript.
            # Same append the chat path makes to its planner provenance.
            try:
                from core.session_sources import conversation_sources_block

                _src = conversation_sources_block(history)
                if _src:
                    prov = f"{prov}\n\n{_src}" if prov else _src
            except Exception:  # noqa: BLE001 — best-effort
                pass
            return await plan_tool_use(
                message, history, user_id, llm_service,
                canvas=canvas, provenance=prov,
                allow_canvas_target=allow_canvas_target)

        def _resolved_plan_if_done() -> Any:
            """The shared plan's verdict when it landed just after our cap.

            A planner TIMEOUT says nothing about whether the edit needs live
            data; treating it as "needs data" declined data-INDEPENDENT edits
            (live 2026-09-11: the header-style edit declined because the
            shared planner overran, and the reply then claimed it had landed).
            When the task has since resolved, honor its verdict."""
            if plan_task is None or not plan_task.done() or plan_task.cancelled():
                return None
            try:
                return plan_task.result()
            except Exception:  # noqa: BLE001
                return None

        plan = None
        try:
            # This cap bounds the PLANNER wait only — never the evidence
            # lookup below. Charging planner latency to the evidence budget
            # is what declined edits whose plan resolved to "no live data
            # needed" seconds later.
            plan = await asyncio.wait_for(
                _resolve_plan(), timeout=_FRESH_DATA_PLAN_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            plan = _resolved_plan_if_done()
            if plan is None:
                logger.info(
                    "canvas edit evidence planner timed out — declining "
                    "before any lookup")
                await _record(
                    "observation",
                    {"tool": "fresh_data",
                     "params": {"source": "canvas_edit_fresh_data"}},
                    "evidence planner timed out — data-dependent edit must decline")
                return FreshDataResult("", True, False)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 — fault-isolated by contract
            # Reachable only when plan_tool_use itself raised (no shared
            # task): a failed planner cannot be trusted to say "no live data
            # needed", so decline rather than edit ungrounded.
            logger.warning(
                f"canvas edit evidence planner failed — declining "
                f"evidence-dependent edit: {e}")
            await _record(
                "observation",
                {"tool": "fresh_data",
                 "params": {"source": "canvas_edit_fresh_data"}},
                f"live evidence lookup failed: {str(e)[:500]}")
            return FreshDataResult("", True, False)

        if not plan or not plan.use_tool:
            return FreshDataResult("", False, True)

        # OFF-REQUEST GATE (RCA 2026-09-17 finding 2): this is the exact
        # leg that executed the stale query — the final scorecard turn's
        # canvas-edit evidence ran the PREVIOUS turn's "PRICE VIPUL price
        # list attachment" mailbox search (source canvas_edit_fresh_data)
        # and its result was handed to the reply as this turn's evidence.
        # A plan whose query names nothing the current message names is
        # declined as an explicit retrieval failure: the edit leg declines
        # (no data-dependent edit without its evidence) and the block is
        # never written to the blackboard for the reply leg to reuse.
        try:
            from core.plan_relevance import (
                canvas_topic_text,
                resolved_plan_relevance,
            )

            # R4 (2026-09-17): the planner STAMPS the verdict of record on
            # the plan at acceptance — including its provenance-quote
            # exemption, which this raw recompute cannot see and would
            # wrongly decline (query = thread SUBJECT, message = pasted
            # BODY, zero lexical overlap by construction). Plans without a
            # stamp (SimpleNamespace fixtures, legacy callers) fall back to
            # the raw verdict, which still governs.
            #
            # AUDIT (2026-09-23, canvas 0e4defa5): an "irrelevant" verdict —
            # stamped OR raw — no longer declines on its own. It is
            # re-judged against the SAME resolved inputs this leg already
            # holds: the conversation history (request-reference
            # resolution) and the open canvas's subject (the canvas-target
            # rule). Live shape: "update with actual prices in the email"
            # shares zero words with the CORRECT mailbox query (the
            # products being priced live in the canvas, not the message),
            # the stamped decline killed the lookup the request depended
            # on, and the edit never ran. A query that names neither the
            # resolved request nor the canvas target — the genuinely stale
            # plan this gate exists for — still declines, and the decline
            # stays a RELEVANCE rejection (declined_irrelevant), distinct
            # from a retrieval failure.
            _relevance, _relevance_basis = resolved_plan_relevance(
                plan, message, history=history,
                extra_topic=canvas_topic_text(canvas),
                allow_canvas_target=allow_canvas_target,
            )
        except Exception:  # noqa: BLE001 — a failed gate must not gate
            _relevance = "unknown"
        if _relevance == "irrelevant":
            logger.warning(
                "canvas edit evidence declined: planned %s.%s query %r does "
                "not address the current request",
                plan.service, plan.intent, (plan.query or "")[:80])
            await _record(
                "observation",
                {"tool": "fresh_data",
                 "params": {"source": "canvas_edit_fresh_data",
                            "query": plan.query}},
                f"planned lookup {plan.service}.{plan.intent} "
                f"{plan.query!r} does not address the current request — "
                "not executed; data-dependent edit declines")
            return FreshDataResult(
                "", True, False, declined_irrelevant=True)

        await _record(
            "tool_planner",
            {"tool": plan.service,
             "params": {"intent": plan.intent, "query": plan.query,
                        "source": "canvas_edit_fresh_data"}},
            f"canvas edit needs live data; planning "
            f"{plan.service}.{plan.intent} query={plan.query!r}")

        async def _lookup() -> Tuple[bool, str, str]:
            # Canvas context feeds the intelligent query rewrite (subject
            # resolution from the open draft). Live 2026-09-08: this leg
            # executed an explicit web-research search with NO canvas — the
            # query stayed generic ("lead's bandsaw…") and Tavily returned
            # buying guides instead of the DM10/WG-350DSAV pages the open
            # draft names. Same dict shape the chat path sends.
            block = await execute_tool_plan(
                plan,
                user_id,
                context={
                    # Current ask ahead of history (same shape as the chat
                    # path): the stated-date window reads it from here.
                    "message": message,
                    "history": history,
                    # REQUEST-BOUND SUBJECTS (2026-10-08 owner final
                    # repair 2): when the caller resolved this request's
                    # subjects (interactive turn or the reloaded
                    # background contract), they lead the probe — canvas/
                    # history supplies context but never replaces them
                    # (the fresh-data leg planned a memory search while
                    # the job required the workbook).
                    **({"request_scope": request_scope}
                       if isinstance(request_scope, dict) else {}),
                    **({"canvas": {
                        "title": canvas.get("title"),
                        **((canvas.get("content") or {})
                           if isinstance(canvas.get("content"), dict) else {}),
                    }} if canvas else {}),
                },
            )
            result_meta = getattr(plan, "_result_meta", None) or {}
            workbook_read = (
                (result_meta.get("storage_read") or {}).get("workbook_read")
                or {}
            )
            source_observations = list(
                result_meta.get("source_observations") or []
            )
            if (workbook_read or source_observations) and canvas:
                from core.workbook_read_artifact import render_source_comparison

                comparison = build_canvas_evidence_comparison(
                    canvas,
                    workbook_read,
                    source_observations=source_observations,
                    authorized_actions=list(authorized_actions or []),
                    objective_text=message,
                )
                result_meta["objective_evidence"] = comparison
                comparison_text = render_source_comparison(comparison)
                if comparison_text:
                    block = (
                        f"{block}\n\n{comparison_text}"
                        if block else comparison_text
                    )
            observation = (block or "lookup returned nothing usable")[:4000]
            if block and len(block) > 4000:
                # Trace display only — the model-facing section below gets
                # the FULL block. Without the marker a clipped observation
                # reads like a coherent ending and misleads trace-based
                # debugging ("the model never saw the price" when it did).
                observation += (
                    f"…[display truncated — model received the full "
                    f"{len(block)}-char block]"
                )
            await _record(
                "observation",
                {"tool": plan.service,
                 "params": {"intent": plan.intent, "query": plan.query,
                            "source": "canvas_edit_fresh_data"}},
                observation)
            if not block:
                return True, "", ""
            # Arm fact watches: when the evidence carries watchable facts
            # (zoho_inventory items, ...), a background poller re-checks
            # them and alerts if the grounded fact changes.
            try:
                from core.fact_watch import get_fact_watch_service
                await get_fact_watch_service().register_from_trace(
                    {"service": plan.service, "block": block},
                    canvas_id=canvas_id, user_id=user_id)
            except Exception as watch_err:  # noqa: BLE001
                logger.debug(f"fact watch registration skipped: {watch_err}")
            return True, (
                "FRESH DATA for this edit (live tool results, fetched just "
                f"now):\n{block}\n\n"
            ), block

        needed, section, raw_block = await asyncio.wait_for(
            _lookup(), timeout=_FRESH_DATA_TIMEOUT_SECONDS
        )
        return FreshDataResult(
            section=section,
            needed=needed,
            ok=bool(section) or not needed,
            block=raw_block,
            evidence_contract=(
                (getattr(plan, "_result_meta", None) or {}).get(
                    "objective_evidence"
                )
            ),
        )
    except asyncio.TimeoutError:
        logger.info(
            "canvas edit fresh-data lookup timed out — reporting failed "
            "lookup so the edit declines instead of fabricating")
        await _record(
            "observation",
            {"tool": "fresh_data", "params": {"source": "canvas_edit_fresh_data"}},
            "live evidence lookup timed out — data-dependent edit must decline")
        return FreshDataResult("", True, False)
    except Exception as e:  # noqa: BLE001 — fault-isolated by contract
        logger.warning(
            f"canvas edit fresh-data lookup failed — declining "
            f"evidence-dependent edit: {e}")
        await _record(
            "observation",
            {"tool": "fresh_data", "params": {"source": "canvas_edit_fresh_data"}},
            f"live evidence lookup failed: {str(e)[:500]}")
        return FreshDataResult("", True, False)


def canvas_no_edit_note(evidence_unavailable: bool) -> str:
    """System directive for the reply path after a DECLINED canvas edit.

    When the co-editor declines an edit because its required live lookup
    failed, the orchestrator falls through to the conversational leg (so a
    plain data QUESTION still gets answered). That leg has no idea an edit was
    attempted: observed live 2026-09-11 (canvas a1a13834, "fix the table
    header background color with text and also properly update the
    alternatives price") — the reply shipped "Done — here's what I changed"
    for an edit that was never applied, which reads as the agent lying and
    hides the failure. This directive tells the fallback model the canvas is
    unchanged and forbids the claim. Returns "" when no edit was declined."""
    if not evidence_unavailable:
        return ""
    return (
        "NO CANVAS EDIT WAS APPLIED THIS TURN — a required live-data lookup "
        "failed, so the open canvas is unchanged. Do NOT claim or imply that "
        "you changed, fixed, updated or reformatted the canvas; state plainly "
        "that nothing was changed and invite the user to retry."
    )


class CanvasEvidenceStatus(str, Enum):
    """The ONE typed outcome channel for a turn's canvas-edit evidence leg.

    Replaces the former independent booleans (``canvas_evidence_unavailable``
    and the OR-ed gate rejection): separate bools allowed contradictory states
    and conflated "evidence was judged unrelated" with "the lookup failed" —
    which is how the live 2026-09-22 incident shipped a false "a required
    live-data lookup failed" reply after a SUCCESSFUL mailbox search.

    OK                  — evidence stands; nothing to disclaim.
    PLANNER_UNAVAILABLE — edit planning failed/timeout; no lookup conclusion.
    LOOKUP_FAILED       — a live-data need existed and the lookup failed.
    FETCH_DECLINED      — the planned lookup did not address the request, so
                          NO lookup ran (never report one as failed).
    RELEVANCE_UNPROVEN  — evidence was retrieved but could not be confirmed to
                          address the request; withheld, retrieval outcome
                          NOT characterized.
    MISMATCH            — evidence provenance traces OUTSIDE the resolved
                          lineage (a different request); withheld, retrieval
                          outcome NOT characterized.
    """

    OK = "ok"
    PLANNER_UNAVAILABLE = "planner_unavailable"
    LOOKUP_FAILED = "lookup_failed"
    FETCH_DECLINED = "fetch_declined"
    RELEVANCE_UNPROVEN = "relevance_unproven"
    MISMATCH = "mismatch"


def canvas_evidence_status(
    shared_tool: Optional[Dict[str, Any]], gate_relevance: str = "addresses"
) -> CanvasEvidenceStatus:
    """The ONLY place turn flags become a CanvasEvidenceStatus.

    Explicit precedence, so conflicting blackboard flags resolve by rule
    instead of by whichever boolean the caller OR-ed in:

    1. PLANNER_UNAVAILABLE (planning down — its note also forbids claiming a
       search failed merely because edit planning failed, so it outranks the
       failure flag that is set alongside it);
    2. LOOKUP_FAILED;
    3. FETCH_DECLINED;
    4. gate verdict: MISMATCH, then RELEVANCE_UNPROVEN (a non-``addresses``
       gate verdict cannot outrank a genuine retrieval failure — an unrelated
       block does not make a failed lookup a success);
    5. OK.
    """
    shared = shared_tool or {}
    if shared.get("canvas_planning_unavailable"):
        return CanvasEvidenceStatus.PLANNER_UNAVAILABLE
    if shared.get("canvas_evidence_unavailable"):
        return CanvasEvidenceStatus.LOOKUP_FAILED
    if shared.get("canvas_evidence_declined"):
        return CanvasEvidenceStatus.FETCH_DECLINED
    if gate_relevance == "mismatch":
        return CanvasEvidenceStatus.MISMATCH
    if gate_relevance == "unproven":
        return CanvasEvidenceStatus.RELEVANCE_UNPROVEN
    return CanvasEvidenceStatus.OK


def canvas_evidence_note(status: CanvasEvidenceStatus) -> str:
    """The system directive for each non-OK status, in one vocabulary.

    Withheld statuses (RELEVANCE_UNPROVEN / MISMATCH) deliberately make NO
    retrieval-outcome claim: a nonempty rejected block may be partial, stale,
    or an error payload — uncertainty stays uncertainty. Accepts the enum or
    its string value."""
    if not isinstance(status, CanvasEvidenceStatus):
        status = CanvasEvidenceStatus(str(status))
    if status is CanvasEvidenceStatus.OK:
        return ""
    if status is CanvasEvidenceStatus.PLANNER_UNAVAILABLE:
        return (
            "The canvas edit planner was unavailable. NO CANVAS EDIT OR "
            "ACTION WAS APPLIED. Answer the user's information request "
            "from the retrieved evidence normally. If they requested a "
            "change, explain that it was not applied. Do not claim a "
            "search failed merely because edit planning failed."
        )
    if status is CanvasEvidenceStatus.LOOKUP_FAILED:
        return canvas_no_edit_note(True)
    if status is CanvasEvidenceStatus.FETCH_DECLINED:
        return (
            "NO CANVAS EDIT WAS APPLIED THIS TURN — no live-data lookup ran "
            "for this request (the planned lookup did not address it), so "
            "the open canvas is unchanged. Do NOT claim or imply that you "
            "changed the canvas, and do NOT report a lookup failure — none "
            "ran. If the user asked for a change, say plainly that it was "
            "not applied."
        )
    if status is CanvasEvidenceStatus.RELEVANCE_UNPROVEN:
        return (
            "The evidence retrieved this turn could not be confirmed to "
            "address the current request and was WITHHELD from this reply. "
            "It is NOT established whether the lookup succeeded or failed — "
            "do NOT characterize it either way, and do NOT answer from the "
            "withheld content. Say the retrieved results could not be "
            "matched to this request and offer to refine the search."
        )
    if status is CanvasEvidenceStatus.MISMATCH:
        return (
            "The evidence retrieved this turn traces to a DIFFERENT request "
            "than the current one and was WITHHELD. Do NOT answer from it, "
            "and do not characterize the lookup as failed or succeeded; say "
            "the retrieved material belonged to another request and offer "
            "to run the current one."
        )
    return ""


def _count_occurrences(haystack: str, needle: str) -> int:
    if not needle:
        return 0
    return haystack.count(needle)


def _quoted_value(message: str) -> str:
    """The value the user quoted, if any ("from X to Y" / "change X to Y").

    Used only to COUNT occurrences in the canvas body the planner received, so a
    decision can be attributed. The value itself is never logged.
    """
    m = re.search(r"\bfrom\s+([^\s]+)\s+to\s+([^\s.]+)", message or "",
                  re.IGNORECASE)
    if m:
        return m.group(1).strip().strip("'\"")
    m = re.search(r"\bchange\s+(?:the\s+)?[^\s]+\s+from\s+([^\s]+)\s+to\s+([^\s.]+)",
                  message or "", re.IGNORECASE)
    return m.group(1).strip().strip("'\"") if m else ""

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
    fresh_data: Optional[str] = None,
    job_findings: Optional[Dict[str, Any]] = None,
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
    the editor guessed a signature name from the Cc line. ``fresh_data`` is
    the live evidence section the caller gathered via
    fetch_fresh_data_section (scoped to the acting user) for edit requests
    that hinge on external facts — a price from a workbook, specs from a
    drive file.
    Patch ops are
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
    # Live evidence when the edit hinges on data the editor cannot see —
    # fetched by the caller (orchestrator context assembly) via
    # fetch_fresh_data_section and handed in; never gathered here, so this
    # function stays a single structured LLM call.
    rendered = {  # canonical layout order; priority = same order
        "scope": _request_scope_section(message, history, fresh_data),
        "corrections": _corrections_section(corrections),
        "versions": _versions_section(versions, canvas.get("content")),
        # Evidence outranks the learning channels: it is the data THIS edit
        # is about; lessons/corrections are advisory style guidance.
        "fresh": fresh_data or "",
        # Job findings outrank lessons (they are the verified record of
        # THIS canvas's investigation) but sit beside evidence: applied
        # findings must respect fresh_data when both speak.
        "findings": _job_findings_section(job_findings),
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
        # TASK SIGNAL FIRST (live 2026-09-23): the 7k-char instruction set
        # + optional context sections diluted the edit signal enough that
        # flash-tier models returned wants_edit=False for clear rebuild
        # requests — the canvas and request sat at the BOTTOM after all
        # the instructions. Front-load the user's message so the model
        # reads "this is an edit for X" before the editing rules.
        f"USER REQUEST (analyze this against the current canvas below and "
        f"produce a CanvasEditPlan):\n{message}\n\n"
        f"{_EDITOR_SYSTEM}\n\n"
        f"{_identity_section(user_identity)}"
        f"{_playbooks_section(playbooks)}"
        f"{included.get('scope', '')}"
        f"{included.get('fresh', '')}"
        f"{included.get('corrections', '')}"
        f"{included.get('versions', '')}"
        f"{included.get('lessons', '')}"
        f"{included.get('cross', '')}"
        f"{included.get('origin', '')}"
        f"{app_section}\n"
        f"{content_section}"
        f"{history_section}"
    )

    plan = await _plan_structured(
        llm_service,
        prompt=prompt,
        response_model=CanvasEditPlan,
        system_instruction="You return only the requested JSON object.",
        message=message,
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
        # D4: a plan that says "not an edit" while carrying operations is
        # SELF-INCONSISTENT, and it is not a decline -- it is a malformed answer.
        #
        # OBSERVABILITY (2026-09-28). The decision this branch makes is the
        # single boundary that decides whether a canvas changes at all
        # (chat_orchestrator.py gates on `plan.wants_edit` before apply), and it
        # was the only branch with NO log line. A clean decline -- wants_edit
        # false, no ops, no replacement, no restore -- returned here in
        # silence, so the recorded symptom was "the planner ran, then nothing
        # happened": on a browser edit of an unambiguous field the world saw
        # `canvas-edit plan: 8.2s` and no explanation whatsoever, and the reason
        # existed only in in-memory `shared_tool_state`. The bounded repair
        # below was logged; the ordinary decline, which is the common case, was
        # not.
        #
        # Shapes only: counts, flags and the contract verdict. No canvas text, no
        # user text -- same rule as core.log_redaction.
        # Identity evidence, not just sizes. A character count proves the input
        # was NON-EMPTY; it cannot prove the RIGHT body and the RIGHT request
        # reached the model, which is the question that decides whether a
        # decline is the model's judgement or an empty-context artefact. So log
        # truncated hashes of the canvas body and of the user's request, plus
        # how many times the request's quoted value occurs in the body the
        # planner was actually given. All are shapes/identities: no canvas or
        # user text, per the routine-log rule.
        _body_for_id = _body_from_content((canvas or {}).get("content")) or ""
        logger.info(
            "canvas edit: plan DECLINED | wants_edit=%s ops=%d "
            "replacement=%s restore=%s contract_violation=%s",
            bool(plan.wants_edit), len(list(plan.ops or [])),
            bool((plan.updated_content_json or "").strip()),
            bool((plan.restore_audit_id or "").strip()),
            plan_contract_violation(plan))
        # THE MODEL'S OWN DECLINE WORDS (2026-10-08 owner assignment 4):
        # a served planner declining an authorized task must be
        # diagnosed from its stated reason — not attributed to
        # contention. Bounded + redacted (routine-log rule).
        if str(plan.reply or "").strip():
            try:
                from core import log_redaction
                _captured = log_redaction.capture(
                    str(plan.reply)[:400], "canvas_edit_decline_reply")
                logger.info(
                    "canvas edit: decline reply | %s",
                    _captured
                    or log_redaction.describe(plan.reply))
            except Exception:  # noqa: BLE001 — telemetry only
                logger.info(
                    "canvas edit: decline reply | <%d chars, "
                    "unredactable>", len(str(plan.reply)))
        logger.info(
            "canvas edit: planner input identity | prompt_chars=%d "
            "canvas_type=%r history_msgs=%d "
            "canvas_body_sha256_12=%s request_sha256_12=%s "
            "request_value_occurrences_in_body=%d",
            len(prompt or ""), (canvas or {}).get("canvas_type"),
            len(history or []),
            log_redaction.fingerprint(_body_for_id),
            log_redaction.fingerprint(message or ""),
            _count_occurrences(_body_for_id, _quoted_value(message or "")))
        # Measured on candidate_fix1 (2026-09-27): the unpinned route resolves to
        # opencode-go/gemini-3-flash, and on a valid canvas it returned
        # wants_edit=False WITH ops=1 -- the correct edit operation, discarded
        # because of one flag. The code's own comment blamed "flash-tier models"
        # generally, which is contradicted by deepseek-flash handling the same
        # prompt correctly.
        #
        # So it gets ONE bounded repair through the SAME structured-planning
        # mechanism, mirroring the existing patch-failure re-ask. Two things this
        # deliberately does NOT do:
        #   * it does NOT execute the operations because they exist. Operations
        #     present in a plan that disclaims the edit is a contradiction to be
        #     resolved, not an authorization to proceed.
        #   * it does NOT treat which model answered as meaningful. Model
        #     selection is a routing decision and carries no authority over
        #     whether this canvas may be changed; authorization is the
        #     lifecycle gate's job, upstream, and is unaffected either way.
        #
        # If the repair also disagrees, the turn is a decline -- unchanged
        # behaviour, and honest.
        violation = plan_contract_violation(plan)
        if violation is None:
            return plan
        logger.info(
            "canvas edit: SCHEMA-BOUNDARY contract violation: %s", violation)
        replan = await _plan_structured(
            llm_service,
            prompt=f"{prompt}\n\n{_INCONSISTENT_PLAN_SUFFIX}",
            response_model=CanvasEditPlan,
            system_instruction="You return only the requested JSON object.",
        )
        # CAPTURE (2026-09-28): both answers, so a failure is attributable
        # without re-running. A model answering correctly is a routing fact and
        # carries no authority over whether the canvas may change.
        logger.info(
            "canvas edit: repair exchange | original=%s | repair=%s",
            _plan_shape(plan), _plan_shape(replan))
        if replan is None:
            # The repair is infrastructure, not a decision. Fall back to the
            # original decline rather than guessing an edit.
            logger.info(
                "canvas edit: consistency repair returned no plan -- keeping "
                "the decline")
            return plan
        if plan_contract_violation(replan) is not None:
            logger.info(
                "canvas edit: consistency repair ALSO violated the contract "
                "(%s) -- treating the turn as not-an-edit",
                plan_contract_violation(replan))
            return replan
        if not replan.wants_edit:
            logger.info(
                "canvas edit: consistency repair returned a consistent "
                "decline -- treating the turn as not-an-edit")
            return replan
        if not (replan.ops or (replan.updated_content_json or "").strip()):
            logger.info(
                "canvas edit: consistency repair claimed an edit but produced "
                "nothing to apply -- treating the turn as not-an-edit")
            return replan
        # FENCE (2026-09-28, F02): the repair may resolve the contradiction, not
        # widen the edit. Reproduced here: a body-scoped request, a
        # self-contradictory plan naming `body`, and a repair that changed
        # `subject` — written, verified true, reported as a completed edit.
        _widened = repair_out_of_scope(replan, plan, canvas.get("content"))
        if _widened:
            logger.warning(
                "canvas edit: consistency repair REJECTED — %s. The turn stays "
                "a decline; the user is asked to name the exact text instead.",
                _widened)
            # `None`, not `replan`: the plan is applicable-looking but out of
            # scope, and returning it would hand the orchestrator an edit the
            # user never asked for. `None` is the module's existing "no usable
            # plan for this turn", which the caller renders as an honest
            # no-apply.
            return None
        return replan

    logger.info(
        "canvas edit: plan AUTHORIZED by the planner | wants_edit=True "
        "ops=%d replacement=%s restore=%s contract_violation=%s "
        "(this is a planning fact, not an authorization to change the canvas)",
        len(list(plan.ops or [])), bool((plan.updated_content_json or "").strip()),
        bool((plan.restore_audit_id or "").strip()),
        plan_contract_violation(plan))

    # Patch validation: ops must match the current content EXACTLY. A
    # failed match discards the ops (never a partial write) and re-asks once
    # for complete content — the user's request still lands, without
    # guess-based fuzzy matching corrupting the artifact. A replace plan with
    # NO ops and NO content is degenerate (the model committed to an edit it
    # couldn't produce — observed live when the draft it needed had been
    # truncated out of its context) and gets the same one re-ask instead of
    # sailing into apply just to be discarded.
    reask_reason = None
    # Restore plans (edit_mode="restore" / restore_audit_id) carry no ops
    # and no content — they name a version id and the apply step restores
    # from the audit trail deterministically. A restore plan without an id
    # is as degenerate as a replace plan without content: same one re-ask.
    is_restore = (
        (plan.edit_mode or "").strip().lower() == "restore"
        or bool((plan.restore_audit_id or "").strip())
    )
    if is_restore:
        if not (plan.restore_audit_id or "").strip():
            reask_reason = "restore plan carried no version id"
    elif plan.ops:
        _, failed = _apply_patch_ops(canvas.get("content"), plan.ops)
        if failed:
            reask_reason = f"{len(failed)}/{len(plan.ops)} patch op(s) failed to match"
    elif not (plan.updated_content_json or "").strip():
        reask_reason = "replace plan carried no ops and no content"

    if reask_reason:
        logger.info(
            f"canvas edit: {reask_reason} — falling back to a replace-mode re-ask"
        )
        replan = await _plan_structured(
            llm_service,
            prompt=f"{prompt}\n\n{_REPLACE_FALLBACK_SUFFIX}",
            response_model=CanvasEditPlan,
            system_instruction="You return only the requested JSON object.",
        )
        if replan is None:
            # First call proved this IS an edit; the re-ask dying is an
            # infrastructure failure — same honest-failure treatment.
            raise CanvasPlanUnavailable(
                "canvas edit replace re-ask LLM returned no plan (provider failure)"
            )
        if not replan.wants_edit:
            return None
        # FENCE (2026-09-28, F02) — same rule as the consistency repair. This is
        # the leg the reported subject-line change actually came through: the
        # discarded ops named `body`, the re-ask returned a payload that changed
        # `subject`, and it was written and reported as a completed edit.
        _widened = repair_out_of_scope(replan, plan, canvas.get("content"))
        if _widened:
            logger.warning(
                "canvas edit: replace-mode re-ask REJECTED — %s. Nothing is "
                "written; the turn answers honestly and asks for the exact "
                "text.", _widened)
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
        #
        # No pin is passed: with routing left to BPC the raw completion is
        # ranked like any other call. The empty dict keeps the helper's
        # optional ``provider_model`` contract intact.
        raw_plan = await _raw_json_replace_plan(
            llm_service, f"{prompt}\n\n{_REPLACE_FALLBACK_SUFFIX}", {}
        )
        # The raw leg is the SAME bounded repair, so the same fence applies to
        # it: being reached through a different parser changes nothing about
        # what the answer is allowed to say.
        _raw_widened = repair_out_of_scope(raw_plan, plan, canvas.get("content"))
        if _raw_widened:
            logger.warning(
                "canvas edit: raw-JSON replace fallback REJECTED — %s. Nothing "
                "is written.", _raw_widened)
            return None
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
            candidate = raw[start:end + 1]
            try:
                return json.loads(candidate)
            except (json.JSONDecodeError, ValueError):
                relaxed = re.sub(r",\s*([}\]])", r"\1", candidate)
                output: List[str] = []
                in_string = False
                escaped = False
                for index, char in enumerate(relaxed):
                    if not in_string:
                        output.append(char)
                        if char == '"':
                            in_string = True
                        continue
                    if escaped:
                        output.append(char)
                        escaped = False
                        continue
                    if char == "\\":
                        output.append(char)
                        escaped = True
                        continue
                    if char == '"':
                        next_index = index + 1
                        while next_index < len(relaxed) and relaxed[next_index].isspace():
                            next_index += 1
                        if next_index >= len(relaxed) or relaxed[next_index] in ":,}]":
                            in_string = False
                            output.append(char)
                        else:
                            output.append('\\"')
                        continue
                    if char in "}]":
                        output.append('"')
                        in_string = False
                    output.append(char)
                try:
                    return json.loads("".join(output))
                except (json.JSONDecodeError, ValueError):
                    pass
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
    from core.canvas_app_schema import known_field_names, resolve_app_spec

    spec = resolve_app_spec(canvas_type, current)

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


# ---------------------------------------------------------------------------
# BOUNDED-REPAIR SCOPE (2026-09-28, F02).
#
# REPRODUCED on this source: with a patch plan whose `find` text was absent
# from the canvas, the product discarded the ops and re-asked in replace mode.
# The re-ask was answered with a full content payload that changed `subject`
# and left the body alone. That payload was merged field-scoped, written,
# reported `postcondition_verified: true`, and the user was told "Updated the
# canvas and refreshed the subject line" — for a request that concerned quote
# validity in the body. One mutation audit row, on the subject. The same thing
# is reachable through the self-contradictory-plan consistency repair.
#
# The bounded repairs are the only place in this module where a model is handed
# authorship of fields the user's request never named: the discarded patch set
# already said WHICH fields the edit was about, and a recovery answer is allowed
# to fix HOW they are written, not to choose a different edit. So the fence is
# expressed in the plan's own terms — no vocabulary, no phrase list, no
# per-integration branch:
#
#   a bounded repair may not change a content key the discarded plan did not
#   name.
#
# It is deliberately silent where the scope is not knowable (a whole-document
# op, a grid, a reference plan with no ops, a payload that is not key-scoped):
# an unauditable scope is not a scope violation, and refusing there would
# suppress supported edits rather than protect them.
# ---------------------------------------------------------------------------


def _plan_field_scope(plan: Any) -> Optional[set]:
    """The content keys a plan's ops name.

    ``None`` means "not key-scoped, nothing to fence against": no ops at all,
    an op with no ``field`` (a whole-document or per-cell op), or a field-less
    op on a string canvas. Callers must treat ``None`` as 'cannot judge', never
    as 'in scope'.
    """
    ops = list(getattr(plan, "ops", None) or [])
    if not ops:
        return None
    scope: set = set()
    for op in ops:
        field = (op.get("field") if isinstance(op, dict)
                 else getattr(op, "field", None))
        if not field:
            return None
        scope.add(str(field))
    return scope or None


def _changed_content_keys(parsed: Any, current: Any) -> Optional[set]:
    """Keys a decoded replace payload would actually CHANGE.

    Keys whose value equals the current content's are not changes — the
    echo burden of "return only the keys you are changing" is exactly why a
    model may legitimately hand back a whole object. ``None`` when the payload
    is not key-scoped against key-scoped current content (arrays, grids,
    scalars, a shape mismatch that ``_merge_replace_content`` will reject
    anyway), so the caller can tell "nothing out of scope" from "cannot judge".
    """
    if not (isinstance(parsed, dict) and isinstance(current, dict)):
        return None
    if isinstance(current.get("rows"), list) or isinstance(current.get("cells"), dict):
        return None
    return {key for key, value in parsed.items() if current.get(key) != value}


def repair_out_of_scope(
    replan: "CanvasEditPlan",
    reference: "CanvasEditPlan",
    current: Any,
) -> Optional[str]:
    """Does this BOUNDED REPAIR widen the edit beyond the plan it replaces?

    Returns a human-readable reason when it does, ``None`` when it does not.
    Only meaningful for the two repair legs; the first-plan replace mode is
    untouched, because there the model authored the whole edit from the
    request rather than recovering a plan the product had already scoped.
    """
    if replan is None or reference is None:
        return None
    raw = (getattr(replan, "updated_content_json", "") or "").strip()
    if not raw:
        return None  # a patch answer is field-scoped by construction
    parsed = _repair_json(raw)
    if not isinstance(parsed, dict):
        return None
    scope = _plan_field_scope(reference)
    if not scope:
        return None
    changed = _changed_content_keys(parsed, current)
    if not changed:
        return None
    widened = sorted(changed - scope)
    if not widened:
        return None
    return (
        f"bounded repair would change content key(s) {widened} that the "
        f"discarded plan did not name (it named {sorted(scope)})"
    )


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


_HTTP_URL_RE = re.compile(r"https?://[^\s\"'<>\)\]]+", re.IGNORECASE)
_LINK_CHECK_MAX_URLS = 8
_LINK_CHECK_TIMEOUT_SECONDS = 8.0


def _extract_http_urls(value: Any, _seen: Optional[set] = None) -> List[str]:
    """Every absolute http(s) URL appearing anywhere in canvas content —
    dict fields, list items, HTML attribute values, markdown, plain text.
    Order-stable, de-duplicated."""
    found: List[str] = []
    seen_ids = _seen if _seen is not None else set()

    def _walk(node: Any) -> None:
        if isinstance(node, str):
            for match in _HTTP_URL_RE.findall(node):
                url = match.rstrip(".,;:")
                if url not in found:
                    found.append(url)
        elif isinstance(node, dict):
            for k in node:
                if id(node[k]) in seen_ids:
                    continue
                seen_ids.add(id(node[k]))
                _walk(node[k])
        elif isinstance(node, (list, tuple)):
            for item in node:
                if id(item) in seen_ids:
                    continue
                seen_ids.add(id(item))
                _walk(item)

    _walk(value)
    return found


async def _new_dead_links(current: Any, new_content: Any) -> List[str]:
    """URLs the edit INTRODUCES that confirmably do not resolve (HTTP 404 /
    410). The live incident (2026-09-08, canvas c3617a7f…): asked to find a
    product page on brennan.ca, the editor composed a plausible-looking
    `/products/<model-number>` URL that 404'd straight into a
    customer-facing quote email — nothing verified it before the write, and
    the user caught it by clicking.

    Only links NEW relative to the current content are checked (links the
    user already published stay untouched), and the check fails OPEN:
    network errors, timeouts, bot walls (403/401) and unknown statuses all
    count as alive — only a confirmed 404/410 blocks, because a dead link
    in an outgoing draft is worse than no link."""
    try:
        old_urls = set(_extract_http_urls(current))
        new_urls = [
            u for u in _extract_http_urls(new_content) if u not in old_urls
        ][:_LINK_CHECK_MAX_URLS]
        if not new_urls:
            return []

        import httpx

        async def _is_dead(client: "httpx.AsyncClient", url: str) -> bool:
            try:
                head = await client.head(url)
                if head.status_code not in (404, 410):
                    return False
                # HEAD may be unsupported/bot-filtered — confirm with GET
                # before declaring a link dead.
                get = await client.get(url)
                return get.status_code in (404, 410)
            except Exception:  # noqa: BLE001 — unreachable ≠ dead
                return False

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=_LINK_CHECK_TIMEOUT_SECONDS,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AtomAgent/1.0)"},
        ) as client:
            results = await asyncio.wait_for(
                asyncio.gather(*(_is_dead(client, url) for url in new_urls)),
                timeout=_LINK_CHECK_TIMEOUT_SECONDS + 4,
            )
        return [url for url, dead in zip(new_urls, results) if dead]
    except asyncio.TimeoutError:
        # Verification budget exhausted — proceed rather than stall the edit.
        logger.debug("canvas edit link check timed out — proceeding")
        return []
    except Exception as check_err:  # noqa: BLE001 — verification never blocks
        logger.debug(f"canvas edit link check skipped: {check_err}")
        return []


def _evidence_action_applied(
    content: Any,
    action: Dict[str, Any],
) -> bool:
    from core.workbook_read_artifact import (
        _comparison_number,
        _comparison_verified,
        _price_field_meaning,
    )

    entity = str(action.get("entity_id") or "")
    field = str(action.get("field") or "")
    expected_data = action.get("expected")
    if not isinstance(expected_data, dict):
        return False
    expected = str(expected_data.get("raw_value") or "")
    if not entity or not field or not expected:
        return False
    observations = artifact_observations(
        {"canvas_id": "postcondition", "content": content},
        requested_entities=[entity],
        requested_fields=[field],
        source={"source_id": "postcondition", "source_type": "artifact"},
    )
    if len(observations) != 1:
        return False
    matches = []
    for observation in observations:
        if not _comparison_verified(observation):
            continue
        actual = str(observation.get("raw_value") or "")
        if not actual:
            continue
        if any(
            expected_data.get(key) is not None
            and observation.get(key) != expected_data.get(key)
            for key in ("currency", "unit", "basis")
        ):
            continue
        expected_meaning = str(
            expected_data.get("destination_field_meaning")
            or expected_data.get("field_meaning")
            or "unspecified"
        )
        actual_meaning = _price_field_meaning(observation)
        if actual_meaning != expected_meaning:
            continue
        expected_attributes = expected_data.get("entity_attributes") or {}
        if expected_attributes and (
            observation.get("entity_attributes") or {}
        ) != expected_attributes:
            continue
        actual_number = _comparison_number(actual)
        expected_number = _comparison_number(expected)
        if actual_number is not None and expected_number is not None:
            if actual_number == expected_number:
                matches.append(observation)
        elif actual.casefold() == expected.casefold():
            matches.append(observation)
    return len(matches) == 1


def _op_text(op: Any, attr: str) -> str:
    """The find/replace text of a patch op, whatever shape the model returned."""
    if isinstance(op, dict):
        return str(op.get(attr) or "")
    return str(getattr(op, attr, "") or "")


def _intended_change_marks(plan: Any, new_content: Any) -> List[Dict[str, Any]]:
    """What the plan INTENDED to change, derived from its own ops.

    Recorded so the verification can be audited against the request rather than
    against itself. Each mark is the text that must now be present, and the text
    that must now be gone.
    """
    marks: List[Dict[str, Any]] = []
    for op in (getattr(plan, "ops", None) or []):
        find = _op_text(op, "find")
        replace = _op_text(op, "replace")
        field = (op.get("field") if isinstance(op, dict)
                 else getattr(op, "field", None))
        if not find and not replace:
            continue
        marks.append({"field": field, "find": find, "replace": replace})
    return marks


def _verify_intended_change(plan: Any, readback_content: Any,
                            content_persisted: bool = False) -> Dict[str, Any]:
    """Did the durable canvas contain the INTENDED change?

    Content equality proves the right bytes are stored. It does not prove they
    are the change that was asked for: a plan that changed nothing would also
    satisfy equality, and a canvas that already mentioned the target text
    elsewhere would satisfy it while the intended field never moved.

    So each op is checked as a pair -- the replacement must be present AND the
    text it replaced must be gone -- scoped to the field the op named when the
    content is an object. Scoping matters: for an email canvas, "30 days" must
    appear in `body`, not merely somewhere in the document.

    REPLACE-MODE plans carry no ops: they declare the entire new content, so the
    intended change IS that content and content equality is the complete proof.
    Failing them for having no ops would reject the one mode where the request is
    fully specified -- so they are verified by equality, and reported as such
    rather than being passed silently.
    """
    marks = _intended_change_marks(plan, readback_content)
    if not marks:
        replace_mode = bool(getattr(plan, "updated_content_json", None))
        if replace_mode:
            return {"all_intended_applied": bool(content_persisted),
                    "unapplied_ops": ([] if content_persisted else
                                      ["replace-mode plan: the durable content "
                                       "is not the content the plan declared"]),
                    "checked": 1,
                    "scope": "declared full content (replace-mode plan)"}
        # A plan with neither ops nor declared content asked for nothing. There
        # is no intended change, so a success claim would be unfounded.
        return {"all_intended_applied": False,
                "unapplied_ops": ["the plan carried no operations and no "
                                  "declared content, so there is no intended "
                                  "change to verify"],
                "checked": 0, "scope": "none"}

    def _field_text(mark: Dict[str, Any]) -> str:
        field = mark.get("field")
        if field and isinstance(readback_content, dict):
            return str(readback_content.get(field) or "")
        return str(readback_content or "")

    unapplied: List[str] = []
    for mark in marks:
        hay = _field_text(mark)
        replace, find = mark["replace"], mark["find"]
        if replace and replace not in hay:
            unapplied.append(
                f"field {mark.get('field')!r}: the replacement text is absent")
            continue
        # A non-empty `find` that survives means the edit did not replace what
        # it claimed to. Ignored when find == replace, where nothing could
        # change — and for the same reason when `replace` CONTAINS `find`
        # (observed 2026-09-28, F02 control n3: replacing the subject
        # "Quote … WG-350DSAV" with "Quote … WG-350DSAV (updated)"). Applying
        # the op leaves the original text present BY CONSTRUCTION, so the
        # substring test cannot discriminate and reports a landed, verified
        # edit as unapplied — a false failure claim on a durable write. The
        # replacement-present check above still discriminates in that case.
        if (find and replace and find != replace
                and find not in replace and find in hay):
            unapplied.append(
                f"field {mark.get('field')!r}: the text it should have replaced "
                f"is still present")
    return {"all_intended_applied": not unapplied,
            "unapplied_ops": unapplied[:6],
            "checked": len(marks),
            "scope": "field" if isinstance(readback_content, dict) else "document"}


async def apply_canvas_edit(
    plan: CanvasEditPlan,
    user_id: str,
    canvas: Dict[str, Any],
    return_reason: bool = False,
    operation_id: Optional[str] = None,
    expected_prior_audit_id: Optional[str] = None,
    request_message: Optional[str] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    preserve_footer: bool = False,
    pending_review: bool = False,
    evidence_contract: Optional[Dict[str, Any]] = None,
    require_evidence_postconditions: bool = False,
):
    """Persist the planned edit through the general canvas CRUD layer
    (CanvasAudit append + WS broadcast). Patch ops are re-applied
    deterministically against the canvas content the plan validated against;
    replace plans are decoded, repaired, and — for dict-shaped apps —
    MERGED field-scoped onto the current content (omitted keys preserved);
    restore plans revert to an earlier version by audit_id through the
    audit-trail restore. Per-app policy: file-backed canvases (real
    .docx/.xlsx/.pptx) refuse content writes — the file is the artifact, a
    snapshot write would change nothing the user can see.

    Returns the update result dict on success, None on any failure. With
    ``return_reason=True`` returns ``(result_or_None, reason_or_None)`` so
    the caller can answer with WHAT failed instead of a generic retry."""
    from core.canvas_app_schema import resolve_app_spec

    def _out(result, reason):
        return (result, reason) if return_reason else result

    if not plan or not plan.wants_edit:
        return _out(None, "not_an_edit")

    ready_actions = [
        action
        for action in (evidence_contract or {}).get("actions") or []
        if isinstance(action, dict)
        and str(action.get("action_type") or "") in {
            "edit_artifact", "update_artifact",
        }
        and action.get("status") == "ready"
        and action.get("authorized") is True
    ]
    # FACT-CHANGE READINESS vs PRESENTATION READINESS (2026-10-08
    # owner correction 1, replacing the monetary-token heuristic):
    # no_ready_evidence_change protects APPLYING EVIDENCE-DEPENDENT
    # FACTS — money, integers, dates, booleans, and contract-tracked
    # text facts — so readiness turns on whether the op's BEFORE/AFTER
    # value tokens actually DIFFER (the old heuristic matched '$'
    # anywhere and never compared sides: a formatting rewrite that
    # carried an UNCHANGED price was blocked, while changed integers,
    # dates and booleans slipped through). Presentation changes — same
    # canonical value tokens, differently arranged — and pure prose
    # additions proceed under the turn's authorization; authorization
    # and preservation checks are untouched and stay separate.
    def _canonical_fact_tokens(text: str) -> Any:
        from collections import Counter
        tokens = Counter()
        for m in re.finditer(
                r"\$\s?([\d,]+(?:\.\d+)?)|(?<![\w.])"
                r"([\d,]+(?:\.\d+)?)(?![\w%])", text or ""):
            raw = m.group(1) or m.group(2)
            try:
                from decimal import InvalidOperation
                value = Decimal(raw.replace(",", ""))
                key = f"num:{value.normalize()}"
            except (InvalidOperation, ValueError):
                key = f"raw:{raw}"
            tokens[key] += 1
        for m in re.finditer(
                r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})\b",
                text or ""):
            tokens[f"date:{m.group(1)}"] += 1
        low = re.sub(r"\s+", " ", (text or "").lower())
        for phrase in (
                "in stock", "out of stock", "available",
                "unavailable", "yes", "no", "true", "false"):
            tokens[f"bool:{phrase}"] += low.count(phrase)
        # contract-tracked TEXT facts: entity identities the evidence
        # contract named (the field contract supplies the domain — no
        # product-specific vocabulary here).
        for entity in _contract_entities(evidence_contract):
            if entity and entity.lower() in low:
                tokens[f"entity:{entity.lower()}"] += 1
        return tokens

    def _contract_value_index() -> List[str]:
        """Canonical VALUES the field contract binds to (entity, field)
        pairs — numeric values canonicalized, text values verbatim when
        long enough to be an identity-bearing fact. THE ASSOCIATION
        AUTHORITY: touching one of these is touching a tracked fact."""
        values: List[str] = []
        seen = set()

        def _add(raw: Any) -> None:
            text = str(raw or "").strip()
            if not text:
                return
            try:
                key = f"num:{Decimal(text.replace(',', '')).normalize()}"
            except Exception:  # noqa: BLE001 — not numeric
                if len(text) < 3 or len(text) > 80:
                    return
                key = f"txt:{text.lower()}"
            if key not in seen:
                seen.add(key)
                values.append(key)

        for outcome in ((evidence_contract or {}).get("outcomes")
                        or []):
            if not isinstance(outcome, dict):
                continue
            _add(outcome.get("current_value"))
            for ev in outcome.get("evidence") or []:
                if isinstance(ev, dict):
                    _add(ev.get("raw_value"))
                    _add(ev.get("value"))
        for action in ((evidence_contract or {}).get("actions")
                       or []):
            if isinstance(action, dict):
                _add(action.get("current_value"))
                _add(action.get("proposed_value"))
        return values

    _tracked_values = _contract_value_index()

    def _tracked_order(text: str) -> List[str]:
        """Contract-tracked values in first-occurrence order — the
        ASSOCIATION fingerprint. DEMONSTRATED SCOPE (owner
        qualification 2026-10-08): a regression safeguard that catches
        value swaps WITHIN one op's find/replace (equal bag, different
        order = both facts changed). It is NOT a complete subject-field
        binding mechanism: cross-op reassociation that preserves each
        op's internal order is not caught here — the artifact-level
        scope guard (scope_missing/dropped_product) owns that layer."""
        # separator-insensitive scan: canonical "2902" must find the
        # formatted "$2,902.00" — strip non-alphanumerics from both
        # sides; index order in stripped space preserves occurrence
        # order, which is all the association fingerprint needs.
        flat = re.sub(r"[^0-9a-z]", "", str(text or "").lower())
        hits: List[str] = []
        for key in _tracked_values:
            needle = re.sub(r"[^0-9a-z]", "", key.split(":", 1)[1])
            if not needle:
                continue
            idx = flat.find(needle)
            if idx >= 0:
                hits.append((idx, key))
        hits.sort()
        return [k for _, k in hits]

    def _op_changes_fact(op: Any) -> bool:
        find = str(getattr(op, "find", "") or "")
        replace = str(getattr(op, "replace", "") or "")
        if find == replace:
            return False
        # ASSOCIATION RULE FIRST (the field contract is the authority):
        # when the contract binds values, an op that changes WHICH
        # tracked value appears — set difference OR ORDER difference —
        # changes a subject-field-value association and is a fact
        # change. The token heuristic below is SUPPORTING evidence and
        # may only mark MORE ops fact-changing, never certify a
        # presentation-only edit over the contract.
        if _tracked_values:
            before = _tracked_order(find)
            after = _tracked_order(replace)
            if before != after:
                return True
            if before:
                # same tracked values, same order: the tracked
                # associations are preserved. Only the fallback token
                # rule can still flag an UNTRACKED value change.
                pass
        # SUPPORTING token heuristic (numeric/date/bool/entity) —
        # ASSERTION-scoped (2026-10-08 owner step 5, gate telemetry:
        # fact_changing=1 for a 32-char find -> EMPTY replace): the
        # evidence requirement protects ASSERTING evidence-dependent
        # values. A REMOVAL asserts nothing — "leave anything
        # unresolved unasserted" authorizes exactly that — so only
        # tokens INTRODUCED on the after-side (new assertions) or
        # contract-association changes require ready evidence. Deletion
        # of identities stays guarded by the artifact-level scope rules
        # (scope_dropped_product / scope_missing_product), not here.
        tok_before = _canonical_fact_tokens(find)
        tok_after = _canonical_fact_tokens(replace)
        if tok_before == tok_after:
            return False
        introduced = tok_after - tok_before
        return any(
            k.startswith(("num:", "date:", "bool:", "entity:"))
            for k in introduced.elements())

    _fact_changing_ops = [
        op for op in (getattr(plan, "ops", None) or [])
        if _op_changes_fact(op)
    ]
    if (_fact_changing_ops
            and (evidence_contract or require_evidence_postconditions)
            and not ready_actions):
        # GATE TELEMETRY (2026-10-08 owner assignment 4): the refusal is
        # diagnosable — which ops are fact-changing (shape only) and
        # what statuses the contract's outcomes carry.
        try:
            from core import log_redaction
            logger.info(
                "canvas edit: no_ready_evidence_change | fact_changing=%d "
                "ops_total=%d op_shapes=%s contract_outcomes=%s "
                "tracked_values=%d",
                len(_fact_changing_ops), len(plan.ops or []),
                [log_redaction.shape(
                    {"f": str(getattr(op, "find", ""))[:60],
                     "r": str(getattr(op, "replace", ""))[:60]})
                 for op in _fact_changing_ops[:4]],
                [(str(o.get("entity_id"))[:24], str(o.get("field"))[:16],
                  str(o.get("status")))
                 for o in ((evidence_contract or {}).get("outcomes")
                           or [])[:8]],
                len(_tracked_values))
        except Exception:  # noqa: BLE001 — telemetry only
            pass
        return _out(None, "no_ready_evidence_change")
    if (evidence_contract or require_evidence_postconditions) \
            and not ready_actions and not _fact_changing_ops and (
                getattr(plan, "ops", None) or []):
        logger.info(
            "canvas edit: drafting readiness satisfied without fact-"
            "change actions (%d op(s), presentation-only) — proceeding "
            "under the turn's authorization", len(plan.ops or []))

    current = canvas.get("content")
    canvas_id = str(canvas.get("canvas_id"))
    canvas_type = str(canvas.get("canvas_type") or "generic")
    # File binding wins over the legacy canvas_type: office canvases are
    # persisted with generic registry types ("sheets"/"docs"/"presentation")
    # that would otherwise resolve to the plain grid/text apps.
    spec = resolve_app_spec(canvas_type, current)

    if spec.content_kind == "file_backed":
        return _out(None, "file_backed")

    # Restore mode: revert to an earlier version by audit_id through the
    # audit-trail restore (append-only — the pre-restore state stays in
    # history). Deterministic: the restored content is EXACT regardless of
    # length, which copying a trimmed prompt excerpt could never be.
    if (
        (plan.edit_mode or "").strip().lower() == "restore"
        or (plan.restore_audit_id or "").strip()
    ):
        if evidence_contract:
            return _out(None, "evidence_contract_forbids_restore")
        audit_id = (plan.restore_audit_id or "").strip()
        if not audit_id:
            return _out(None, "restore_missing_version")
        try:
            from tools.canvas_crud_tool import restore_canvas_version

            result = await restore_canvas_version(user_id, canvas_id, audit_id)
        except Exception as e:
            # An exception that ESCAPES the store call says nothing about
            # whether its append landed — the store swallows its own, but a
            # cancellation or a fault outside its try block reaches here. It is
            # therefore never a verified zero effect.
            logger.warning(f"canvas restore apply failed for {canvas_id}: {e}")
            return _out(None, f"write_uncertain: {e}")
        if not (result or {}).get("success"):
            err = str((result or {}).get("error") or "")
            if err.strip().lower() == "version not found":
                # Refused while LOOKING for the version: nothing was appended.
                return _out(None, "version_not_found")
            _write_outcome = str((result or {}).get("write_outcome") or "").strip()
            if _write_outcome != "not_attempted":
                logger.warning(
                    "canvas restore store reported failure for %s with "
                    "write_outcome=%r — the append may already be durable: %s",
                    canvas_id, _write_outcome or "(not reported)", err)
                return _out(None, f"write_uncertain: {err}")
            logger.info(f"canvas restore rejected for {canvas_id}: {err}")
            return _out(None, f"store_rejected: {err}")
        if (result or {}).get("no_change"):
            return _out(None, "no_change")
        return _out(result, None)

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
        new_content = None
        if preserve_footer:
            new_content = _bounded_email_content(current, parsed)
        if new_content is None:
            new_content, reason = _merge_replace_content(
                parsed, current, canvas_type)
            if new_content is None:
                return _out(None, reason or "merge_failed")

    request_messages = []
    if request_message:
        request_messages.append(str(request_message))
    # HISTORY IS NOT A SCOPE SOURCE (2026-09-29 live incident): requiring
    # the artifact to contain every code mentioned anywhere in the
    # conversation let a pasted data row (381<TAB>167072381...) demand a
    # raw 9-digit catalog number inside the email, so every edit plan
    # was refused scope_missing_product and the user's explicit price
    # update dead-ended after 3 honest retries. Established practice for
    # artifact edits is to validate the DIFF against the artifact's own
    # previous state: the instruction constrains the delta, the old body
    # constrains preservation. (The edit-plan PROMPT may still see
    # history for context -- _request_scope_section keeps it.)
    scope_reason = _validate_scoped_edit(
        current, new_content, request_messages, preserve_footer=preserve_footer)
    if scope_reason:
        return _out(None, scope_reason)

    missing_ready_actions = [
        action
        for action in ready_actions
        if not _evidence_action_applied(new_content, action)
    ]
    if missing_ready_actions:
        return _out(
            None,
            "postcondition_missing:"
            + ",".join(
                str(action.get("entity_id") or "unknown")
                for action in missing_ready_actions[:4]
            ),
        )

    # No-op guard: a plan whose result equals the current content writes
    # nothing and reports honestly. Live incident (2026-09-02, canvas
    # da27bb76…): four identical rewrites in a row — "mark is the dealer and
    # not end user" produced a byte-identical audit row and the reply still
    # claimed "I have updated the email body…", which read to the user as
    # the agent lying ("nothing changed"). Skipping the write also keeps
    # the audit trail free of non-edits.
    if new_content == current:
        return _out(None, "no_change")

    # Dead-link gate: a URL the edit introduces that confirmably 404s never
    # reaches the canvas (and from there, a customer's inbox). Fail-open —
    # only a confirmed 404/410 blocks; see _new_dead_links.
    dead_links = await _new_dead_links(current, new_content)
    if dead_links:
        logger.info(
            f"canvas edit blocked for {canvas_id}: introduced link(s) "
            f"return 404: {dead_links[:3]}"
        )
        return _out(None, f"dead_link: {dead_links[0]}")

    evidence_refs = list(dict.fromkeys(
        evidence_id
        for action in ready_actions
        for evidence_id in action.get("evidence_ids") or []
        if evidence_id
    ))
    postconditions = [
        {
            "entity_id": action.get("entity_id"),
            "field": action.get("field"),
            "expected_value": action.get("proposed_value"),
            "expected": action.get("expected") or {},
            "evidence_ids": action.get("evidence_ids") or [],
        }
        for action in ready_actions
    ]
    try:
        from tools.canvas_crud_tool import update_canvas_content

        result = await update_canvas_content(
            user_id, canvas_id, new_content, canvas_type, plan.title,
            operation_id=operation_id,
            expected_prior_audit_id=expected_prior_audit_id,
            pending_review=pending_review,
            evidence_refs=evidence_refs,
            postconditions=postconditions,
        )
    except Exception as e:
        # Same rule as the restore path: an exception escaping the store call
        # cannot establish that nothing was written.
        logger.warning(f"canvas edit apply failed for {canvas_id}: {e}")
        return _out(None, f"write_uncertain: {e}")

    if not (result or {}).get("success"):
        if (result or {}).get("conflict"):
            logger.info(
                f"canvas edit CONFLICT for {canvas_id}: "
                f"{(result or {}).get('error')}")
            return _out(None, "conflict: canvas changed during the edit")
        # A refusal is NOT a zero effect until the store says the append was
        # never attempted. It reports the same `success: False` for a failure
        # that happened AFTER its commit, and "the store refused, so nothing
        # changed" is exactly the false zero-effect claim D0 is about. Only the
        # store knows which of the two happened, so it is asked, and an
        # unrecognised answer is treated as unknown rather than as no.
        _write_outcome = str((result or {}).get("write_outcome") or "").strip()
        if _write_outcome != "not_attempted":
            logger.warning(
                "canvas edit store reported failure for %s with "
                "write_outcome=%r — the write may already be durable: %s",
                canvas_id, _write_outcome or "(not reported)", (result or {}).get("error"))
            return _out(None, f"write_uncertain: {(result or {}).get('error')}")
        logger.info(f"canvas edit rejected for {canvas_id}: {(result or {}).get('error')}")
        return _out(None, f"store_rejected: {(result or {}).get('error')}")
    # INDEPENDENT READ-BACK, ALWAYS. Not only for evidence-contract canvases.
    #
    # The store reporting success is the tool's own claim about its own write.
    # Until now the read-back ran only `if isinstance(evidence_contract, dict)`,
    # so an ordinary canvas got NO verification at all -- and the orchestrator
    # then set `updated: True` and rendered the planner's own success text over
    # it. Measured consequence (2026-09-27, candidate_fix1): the reply rendered
    # "**Canvas Updated:** ... Quote validity: **30 days**" while
    # `canvas_audit` held no row for any canvas in 30 minutes and no canvas in
    # the world contained the new text. A success claim with no verified write.
    #
    # So verification is now unconditional, and it is deliberately NOT the
    # evidence-action check alone: a canvas with no contract has no actions, and
    # "every action applied" would then be vacuously true -- a check that always
    # passes is exactly the defect being fixed. The load-bearing assertion is
    # CONTENT: the durable canvas must actually contain what we wrote.
    #
    # Exact equality is the conservative direction. If the store normalises
    # content, this reports UNVERIFIED rather than falsely reporting success,
    # and an unverified-but-applied edit is a much smaller problem than an
    # unverified edit reported as done.
    intended = _intended_change_marks(plan, new_content)
    try:
        from tools.canvas_crud_tool import read_canvas

        readback = await read_canvas(user_id, canvas_id)
        readback_content = (readback or {}).get("content")
        readback_ok = bool((readback or {}).get("success"))
        readback_id = (readback or {}).get("canvas_id")

        right_canvas = readback_id in (None, canvas_id)
        content_persisted = readback_ok and readback_content == new_content
        field_result = _verify_intended_change(plan, readback_content, content_persisted)
        operation_bound = bool(result.get("audit_id"))
        revision_ok = not (result or {}).get("conflict")

        missing_after_write = [
            action
            for action in ready_actions
            if not _evidence_action_applied(readback_content, action)
        ] if not content_persisted else []

        result["postcondition_verified"] = bool(
            readback_ok and right_canvas and content_persisted
            and field_result["all_intended_applied"] and operation_bound
            and revision_ok and not missing_after_write)
        if isinstance(evidence_contract, dict):
            result["postcondition_evidence_refs"] = evidence_refs
        result["postcondition_binding"] = {
            "canvas_id_expected": canvas_id,
            "canvas_id_read_back": readback_id,
            "right_canvas": right_canvas,
            "operation_audit_id": result.get("audit_id"),
            "operation_bound": operation_bound,
            "expected_prior_audit_id": expected_prior_audit_id,
            "revision_unchanged": revision_ok,
            "content_matches_write": content_persisted,
            "intended_marks": intended,
            "fields": field_result,
        }
        if not result["postcondition_verified"]:
            failed = []
            if not right_canvas:
                failed.append(f"read-back was canvas {readback_id!r}, not {canvas_id!r}")
            if not content_persisted:
                failed.append("read-back did not return the content that was written")
            if not field_result["all_intended_applied"]:
                failed.append(
                    "the intended change is not present: "
                    f"{field_result['unapplied_ops']}")
            if not operation_bound:
                failed.append("the store recorded no audit id for this operation")
            if not revision_ok:
                failed.append("the canvas changed concurrently during the edit")
            if missing_after_write:
                failed.append("written content did not satisfy every ready evidence action")
            result["postcondition_error"] = "; ".join(failed)[:400]
            result["postcondition_readback"] = {
                "readback_ok": readback_ok,
                "written_chars": len(new_content or ""),
                "readback_chars": len(readback_content or ""),
            }
            logger.warning(
                "canvas edit read-back did NOT verify for %s: %s",
                canvas_id, result["postcondition_error"])
    except Exception as verify_error:
        result["postcondition_verified"] = False
        result["postcondition_error"] = (
            f"postcondition readback unavailable: {str(verify_error)[:160]}"
        )
    if result.get("postcondition_verified") is False:
        # The write may or may not have landed. Either way the turn must not
        # report it as done: `updated` is the orchestrator's success signal, and
        # success is now defined as verified persistence, not as a tool saying
        # OK. `write_recorded` preserves the distinction for reconciliation.
        result["success"] = False
        result["write_recorded"] = True
        return _out(result, "postcondition_readback_failed")
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
    from core.canvas_app_schema import (
        empty_fillable_fields,
        normalize_app_type,
        resolve_app_spec,
    )

    spec = resolve_app_spec(canvas_type, content)
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


#: Refusals that were decided BEFORE the store was asked to write anything, so
#: "nothing was changed" is a VERIFIED statement about the canvas rather than a
#: guess. Everything that reaches the store is absent from this list on purpose:
#: a store refusal is only a zero effect when the store itself reported that the
#: append was never attempted (it reports the opposite for a failure that
#: happened after its own commit), and `apply_canvas_edit` encodes that as
#: ``write_uncertain``. Prefixes are matched, so a family of reasons
#: (``scope_*``, ``footer_*``, ``dead_link:…``) is listed once.
#:
#: The default direction is therefore UNCERTAIN: a reason nobody has audited
#: gets wording that preserves the doubt, instead of a new confident claim
#: appearing the next time a refusal path is added.
VERIFIED_PRE_WRITE_REFUSALS = (
    "not_an_edit",
    "no_ready_evidence_change",
    "evidence_contract_forbids_restore",
    "file_backed",
    "not_valid_json",
    "no_content",
    "ops_no_longer_match",
    "merge_failed",
    "no_change",
    "restore_missing_version",
    "version_not_found",
    "store_rejected",
    "dead_link",
    "postcondition_missing",
    "scope_",
    "footer_",
)


def _verified_zero_effect_refusal(reason: Optional[str]) -> bool:
    """Is this refusal a VERIFIED no-write for the current canvas?"""
    text = str(reason or "").strip()
    if not text:
        return False
    head = text.split(":", 1)[0].strip()
    return head in VERIFIED_PRE_WRITE_REFUSALS or any(
        head.startswith(prefix) for prefix in VERIFIED_PRE_WRITE_REFUSALS
    )


def describe_apply_failure(
    reason: Optional[str],
    canvas_type: Optional[str],
    canvas: Optional[Dict[str, Any]] = None,
) -> str:
    """The user-facing explanation for an apply failure — specific enough to
    act on, instead of the old generic "try rephrasing" dead end."""
    from core.canvas_app_schema import (
        empty_fillable_fields,
        resolve_app_spec,
    )

    content = (canvas or {}).get("content")
    spec = resolve_app_spec(canvas_type, content)
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
    if reason == "version_not_found":
        return (
            "I couldn't find that earlier version in this canvas's history "
            "— the version may predate the audit trail or wasn't one I "
            "could see. Nothing was changed. Ask me to go back again and "
            "I'll pick from the versions I can actually see."
        )
    if reason == "restore_missing_version":
        return (
            "I meant to revert to an earlier version but couldn't tell "
            "which one — nothing was changed. Tell me which draft to go "
            "back to (e.g. \"the version from this morning\") and I'll "
            "restore it."
        )
    if reason == "file_backed":
        return (
            f"This is a {spec.label} canvas backed by a real file, so "
            "canvas-text edits can't change the document itself — tell me "
            "what to change and I'll route it through the file engine "
            "instead."
        )
    if reason and reason.startswith("dead_link"):
        dead_url = reason.split(":", 1)[1].strip() if ":" in reason else ""
        where = f" ({dead_url})" if dead_url else ""
        return (
            f"I checked the link this edit would have added{where} and it "
            "returns 404 — the page doesn't exist. I left your draft "
            "unchanged rather than put a broken link in it. If you know the "
            "correct address, paste it and I'll add it; otherwise I can "
            "search the site again."
        )
    if reason and reason.startswith("store_rejected"):
        # Only reachable when the store reported the append was never attempted
        # (see `apply_canvas_edit`), which is what makes this a verified
        # zero-effect claim rather than a hopeful one.
        return (
            "The canvas store refused that edit. Nothing was changed — "
            f"the store said: {reason.split(':', 1)[1].strip()}. Try again "
            "in a moment."
        )
    if reason and reason.startswith("write_uncertain"):
        detail = reason.split(":", 1)[1].strip() if ":" in reason else ""
        return (
            "The canvas store reported a failure at the same moment as the "
            "write, so I can't tell you whether your change landed. Open the "
            "canvas and check before relying on it — and don't repeat the "
            "request until you have, because it may already be applied."
            + (f" (the store said: {detail})" if detail else "")
        )
    if reason and reason.startswith("conflict"):
        # Not a zero effect: the canvas DID move, by someone else. Saying
        # "nothing was changed" here would be false about the artifact the
        # user is about to look at.
        return (
            "The canvas changed while I was working on it, so I held my "
            "edit back rather than overwrite a change I hadn't seen. Nothing "
            "of mine was written. Ask me again and I'll apply it to the "
            "current canvas."
        )
    if reason and reason.startswith("store_error"):
        return (
            "The canvas store failed in a way that doesn't tell me whether "
            "the change landed. Please check the canvas before relying on "
            "it, and ask me again if it's unchanged."
        )
    if reason == "not_valid_json" or reason == "no_content":
        return (
            "I drafted the edit but couldn't produce a clean structured "
            "payload for this canvas, so nothing was changed. Try a smaller, "
            "more specific instruction (e.g. one field or one paragraph at "
            "a time)." + field_hint
        )
    if reason and reason.startswith("scope_row_count"):
        return (
            "The source-backed product list does not match the requested "
            "scope yet, so nothing was written. I need the complete named "
            "set before changing the customer's quote."
        )
    if reason and (
        reason.startswith("scope_missing_price")
        or reason.startswith("scope_missing_product")
        or reason.startswith("scope_missing_alternatives")
        or reason.startswith("scope_missing_requested")
        or reason.startswith("scope_wrong_alternative_category")
    ):
        return (
            "The proposed table does not yet contain every source-backed "
            "product and value in the requested scope, so nothing was "
            "written. I left the current draft unchanged rather than send a "
            "partial quote."
        )
    if reason and reason.startswith("scope_placeholder"):
        return (
            "The proposed customer email still contains unresolved product "
            "placeholders, so nothing was written. Source references stay "
            "internal; the email needs the actual values or an explicit "
            "decision to stop."
        )
    if reason and reason.startswith("footer_"):
        return (
            "The proposed edit would remove part of the existing footer or "
            "its links, so nothing was written. I kept the customer footer "
            "unchanged."
        )
    if reason and reason.startswith("scope_dropped_product"):
        # PRESERVATION VIOLATION, NAMED (2026-10-03, reliability run A):
        # the planned patch would have dropped a product identity the
        # canvas already carries (e.g. the PE-16 line under a
        # fill-the-TBC instruction). The guard is the product working as
        # designed — the reply must say WHICH identity and WHY nothing
        # was written, not a generic field hint.
        _dropped = reason.split(":", 1)[1] if ":" in reason else "a product"
        return (
            f"I didn't write the change: the proposed edit would have "
            f"dropped {_dropped} from the quote, and product identities "
            "only leave when you ask for it. The draft is unchanged. If "
            "the line should be reworded, name the new wording with the "
            "item still in it; if it should be removed outright, say "
            f"'remove {_dropped}'."
        )
    if not _verified_zero_effect_refusal(reason):
        # DEFAULT DIRECTION IS UNCERTAIN. Every branch above either decided
        # before the store was called, or is one of the store-facing cases whose
        # effect is unknown. Whatever lands here is a reason nobody has audited
        # for a verified zero effect, so the sentence keeps the doubt instead of
        # denying something we cannot see.
        logger.warning(
            "canvas apply failure with NO verified zero-effect evidence "
            "(reason=%r) — answering with uncertain wording", reason)
        return (
            "I tried to make that edit but couldn't confirm whether the "
            "canvas changed. Please check the canvas before relying on it. "
            "Try rephrasing or pointing me at the exact text to change."
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


# A send-imperative in PRESENT/IMPERATIVE voice aimed at the assistant.
# Past-tense narration about OTHERS ("the thread chandrakant forwarded to
# me"), and the noun "email" inside information asks ("check the email
# thread … show it to me"), must not reach the action LLM: live 2026-09-15
# (canvas a1a13834) the action planner filed a send_email proposal for that
# exact question — three times — because "email"/"forwarded" matched its
# verb list. Detector-gate only: it can suppress the (expensive, wrong)
# action call; it never CREATES an action. Borderline phrasings simply fall
# through to the LLM planner as before.
_ACTION_IMPERATIVE_RE = re.compile(
    r"(?:^|[.!?:;\n]\s*|,\s*(?:and|then)\s+|\bthen\s+|please\s+|"
    r"(?:can|could|will|would)\s+you\s+(?:please\s+)?|"
    r"(?:want|wanted|would\s+like)\s+to\s+)"
    r"(?:send|email|forward|dispatch|fire\s+off|shoot\s+over|shoot\s+them)\b",
    re.IGNORECASE,
)


def _message_asks_canvas_send(message: str) -> bool:
    """True only when the message carries a send verb in imperative/
    present-voice position. 'forwarded/sent' (past tense, third-party
    narration) never counts."""
    return bool(_ACTION_IMPERATIVE_RE.search(message or ""))


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
  ``reply_all``: true only when the message says reply to everyone.
- EXTERNAL FACTS travel with the draft: when composing or amending body
  text, names, figures, prices, dates, and specs must come from the canvas
  content, the user's message, or the FRESH DATA section (when present) —
  never from memory or plausibility. A needed value from none of those
  stays an explicit placeholder (e.g. "[price — from Consolidated Price
  List]") and `reply` names it; sending happens with the placeholder
  visible, never with an invented number."""


async def plan_canvas_action(
    message: str,
    history: List[Dict[str, Any]],
    canvas: Dict[str, Any],
    llm_service: Any,
    fresh_data: Optional[str] = None,
) -> Optional[CanvasActionPlan]:
    """Decide whether this turn asks to DO something with the canvas (send
    email). ``fresh_data`` is the caller-gathered live evidence section
    (fetch_fresh_data_section) — a send that amends the draft with external
    facts ("send it with the current price") gets the same grounding the
    edit path has. Returns None on failure — caller falls through."""
    if llm_service is None or not canvas.get("canvas_id"):
        return None
    # DETERMINISTIC GATE (before any LLM spend): no send-imperative in the
    # message, no action plan — questions about data ("check the email
    # thread … show it to me") can never become send proposals. See
    # _message_asks_canvas_send.
    if not _message_asks_canvas_send(message):
        return None

    fresh_section = (fresh_data or "").strip()
    prompt = (
        f"{_ACTION_SYSTEM}\n\n"
        + (f"{fresh_section}\n" if fresh_section else "")
        + f"Canvas title: {canvas.get('title') or '(untitled)'}\n"
        f"Canvas type: {canvas.get('canvas_type') or 'generic'}\n"
        f"Canvas content:\n{_serialize_content(canvas.get('content'))}\n\n"
        f"Recent conversation:\n{_history_transcript(history, message)}\n\n"
        "Return the action plan as RAW JSON — do NOT wrap it in ```json fences."
    )

    plan = await _plan_structured(
        llm_service,
        prompt=prompt,
        response_model=CanvasActionPlan,
        system_instruction="You return only the requested JSON object — raw JSON, no markdown fences.",
    )
    if plan is None:
        # Deterministic fallback: the structured (Instructor/tool-mode) path
        # is unreliable for action-shaped schemas — the schema class name
        # becomes the tool name the model sees, and it sometimes answers
        # with tool-call syntax, which Instructor rejects ("use List[Model]
        # instead") even though the completion holds perfect JSON (observed
        # live across provider variants). Parse a raw completion ourselves:
        # fence-stripping + pydantic validation.
        plan = await _raw_json_action_plan(llm_service, prompt, {})
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
