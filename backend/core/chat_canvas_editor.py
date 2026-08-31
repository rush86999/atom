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

logger = logging.getLogger(__name__)

# Pin to a known-reachable vetted model — same rationale as the planner's
# PLANNER_MODEL (unpinned "auto" routing prefers the free local Ollama client
# by value, which is frequently unreachable; the connection-error retries eat
# seconds and lose the structured output entirely).
CANVAS_EDITOR_MODEL = os.getenv("ATOM_CANVAS_EDITOR_MODEL", "minimax/minimax-m3")

# The current canvas content rides in the prompt; bound it so a huge sheet
# can't blow the structured-call budget.
_MAX_CONTENT_CHARS = 6000


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
- For object content (e.g. an email {to, cc, subject, body}) set "field" to
  the key you are editing (usually "body"); the op applies inside that field
  only, and the other keys stay untouched.
- For spreadsheet/grid content (rows, or {cells: ...}) set "cell" to the
  A1 reference instead: {"cell": "B2", "find": <the cell's current value>,
  "replace": <new value>}. "find" must equal the cell's current value.
- edit_mode="replace" ONLY when the user explicitly asked for a rewrite /
  fresh draft, or no patch can express the change (e.g. reformat
  everything): then updated_content_json is the COMPLETE new content, in
  EXACTLY the same shape as the current content (same keys, same types),
  and every part unrelated to the request must stay IDENTICAL to the
  current content. Never return a fragment or an explanation.
- Remove meta-commentary ("Here's your draft...", "Want me to adjust...")
  from the content itself — the canvas holds only the artifact.
- Send/dispatch requests ("send it", "email it to Mark", "try sending
  again") are NOT edits: wants_edit=false — a separate step owns actions.
- Questions, discussion, or requests about other things ("what do you
  think", "search my email") are wants_edit=false too.
- reply is one or two short sentences telling the user what you changed.
  For wants_edit=false, reply is a short conversational answer based on the
  canvas content (or empty if another step will answer)."""

# Fallback prompt when patch ops fail to match the current content (the
# model mis-copied "find"): one re-ask for complete content under the same
# preservation duty. Deterministic safety, not a second chance to patch.
_REPLACE_FALLBACK_SUFFIX = (
    "Your ops did not match the current content exactly, so they were "
    "discarded. Try again with edit_mode=\"replace\": return the COMPLETE "
    "new content in EXACTLY the current shape, applying the user's request "
    "and keeping every part the request doesn't touch IDENTICAL to the "
    "current content shown below."
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
    shorter" and "update the draft based on your findings" hang off earlier
    requests AND the agent's own replies — the findings ("WFS is a dealer")
    live in the agent's message, not the user's. Error turns are skipped:
    flagged failure artifacts must not anchor the plan."""
    lines: List[str] = []
    for h in (history or [])[-8:]:
        h = h or {}
        u = str(h.get("message") or "").strip()
        if u:
            lines.append(f"User: {u[:200]}")
        if h.get("error"):
            continue
        resp = h.get("response")
        a = str((resp or {}).get("message") if isinstance(resp, dict) else (resp or "")).strip()
        if a:
            lines.append(f"Agent: {a[:300]}")
    lines.append(f"User: {current[:600]}")
    return "\n".join(lines)


_CELL_REF = re.compile(r"^([A-Za-z]{1,3})([0-9]+)$")


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


def _apply_patch_ops(content: Any, ops: List["CanvasPatchOp"]) -> tuple:
    """Apply surgical find→replace ops against the current content.

    Deterministic and all-or-nothing per op: an op whose ``find`` doesn't
    appear is REPORTED, never guessed at. Returns (new_content, failed_ops)
    — callers decide between committing (no failures) and falling back.
    Object content is edited per-key (op.field), grids per-cell (op.cell);
    every other key/row keeps its identity, so untouched data can't drift."""
    if not ops:
        return content, []
    failed: List[CanvasPatchOp] = []
    if isinstance(content, str):
        text = content
        for op in ops:
            find = op.find or ""
            if find and find in text:
                text = text.replace(find, op.replace, 1)
            else:
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
            if key and isinstance(result.get(key), str):
                find = op.find or ""
                if find and find in result[key]:
                    result[key] = result[key].replace(find, op.replace, 1)
                else:
                    failed.append(op)
            else:
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


async def plan_canvas_edit(
    message: str,
    history: List[Dict[str, Any]],
    canvas: Dict[str, Any],
    llm_service: Any,
    corrections: Optional[List[Dict[str, Any]]] = None,
) -> Optional[CanvasEditPlan]:
    """Decide (via cheap structured LLM output) whether this turn edits the
    open canvas, and produce the edit — patch ops by default, complete
    content for explicit rewrites. ``corrections`` are the supervisor's
    recent on-canvas edits of this canvas (the RLHF signal, returned to the
    point of generation). Patch ops are validated against the current
    content here: a mis-copied "find" gets ONE re-ask in replace mode
    (still under the preservation duty) rather than a broken write.
    Returns None on any failure — the caller then falls through to the
    conversational path."""
    if llm_service is None or not canvas.get("canvas_id"):
        return None

    prompt = (
        f"{_EDITOR_SYSTEM}\n\n"
        f"{_corrections_section(corrections)}"
        f"Canvas type: {canvas.get('canvas_type') or 'generic'}\n"
        f"Current canvas content:\n{_serialize_content(canvas.get('content'))}\n\n"
        f"Recent conversation:\n{_history_transcript(history, message)}\n\n"
        "Return the edit plan."
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
        prompt=prompt,
        response_model=CanvasEditPlan,
        system_instruction="You return only the requested JSON object.",
        temperature=0.0,
        **kwargs,
    )
    if plan is None or not plan.wants_edit:
        return plan

    # Patch validation: ops must match the current content EXACTLY. A
    # failed match discards the ops (never a partial write) and re-asks once
    # for complete content — the user's request still lands, without
    # guess-based fuzzy matching corrupting the artifact.
    if plan.ops:
        _, failed = _apply_patch_ops(canvas.get("content"), plan.ops)
        if not failed:
            return plan
        logger.info(
            f"canvas edit: {len(failed)}/{len(plan.ops)} patch op(s) failed to "
            f"match — falling back to a replace-mode re-ask"
        )
        replan = await llm_service.generate_structured_response(
            prompt=f"{prompt}\n\n{_REPLACE_FALLBACK_SUFFIX}",
            response_model=CanvasEditPlan,
            system_instruction="You return only the requested JSON object.",
            temperature=0.0,
            **kwargs,
        )
        if replan is None or not replan.wants_edit:
            return None
        # Only a usable replace plan rescues the turn; another broken patch
        # set does not — fall through to conversation instead of guessing.
        if replan.updated_content_json and replan.updated_content_json.strip():
            return replan
        if replan.ops:
            _, failed2 = _apply_patch_ops(canvas.get("content"), replan.ops)
            if not failed2:
                return replan
        return None
    return plan


def _decode_replace_content(plan: CanvasEditPlan, current: Any) -> Optional[Any]:
    """Decode replace-mode content. If the model returned a bare string for
    a canvas whose content IS a plain string (markdown/doc bodies), a failed
    JSON parse still yields a usable value — accept it only for that shape."""
    raw = (plan.updated_content_json or "").strip()
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        if isinstance(current, str):
            return raw
        logger.warning("canvas edit: updated_content_json is not valid JSON — discarding")
        return None


async def apply_canvas_edit(
    plan: CanvasEditPlan,
    user_id: str,
    canvas: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Persist the planned edit through the general canvas CRUD layer
    (CanvasAudit append + WS broadcast). Patch ops are re-applied
    deterministically against the canvas content the plan validated against;
    replace plans store their complete content verbatim. Returns the update
    result dict on success, None on any failure (caller falls through to
    the conversational path instead of storing garbage)."""
    if not plan or not plan.wants_edit:
        return None

    current = canvas.get("content")
    new_content: Any = None

    if plan.ops:
        new_content, failed = _apply_patch_ops(current, plan.ops)
        if failed:
            # The plan validated in plan_canvas_edit; a mismatch here means
            # the content moved between the two steps — refuse rather than
            # write a partial edit on top of a state nobody saw.
            logger.warning("canvas edit: patch ops no longer match — refusing partial write")
            return None
    else:
        new_content = _decode_replace_content(plan, current)

    if new_content is None:
        return None

    canvas_id = str(canvas.get("canvas_id"))
    canvas_type = str(canvas.get("canvas_type") or "generic")
    try:
        from tools.canvas_crud_tool import update_canvas_content

        result = await update_canvas_content(
            user_id, canvas_id, new_content, canvas_type, plan.title
        )
    except Exception as e:
        logger.warning(f"canvas edit apply failed for {canvas_id}: {e}")
        return None

    if not (result or {}).get("success"):
        logger.info(f"canvas edit rejected for {canvas_id}: {(result or {}).get('error')}")
        return None
    return result


class CanvasActionPlan(BaseModel):
    """Plan for DOING something with the canvas (vs editing it): sending the
    draft, forwarding it, etc. Executes through the maturity + autonomy-policy
    gates — never directly from the planner."""
    wants_action: bool = False
    action: Optional[str] = None  # "send_email" (extensible)
    to: Optional[str] = None      # recipient(s), comma/semicolon separated
    subject: Optional[str] = None
    body: Optional[str] = None    # full email body; defaults to canvas content
    reply: str = ""


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
- ``subject``: from the message or the canvas title; empty if unclear.
- ``body``: the canvas draft content VERBATIM — it may hold manual edits by
  the user that outrank anything in the conversation. Do NOT rewrite,
  "improve", or restructure it when the message only says to send; strip
  obvious meta notes that aren't part of the artifact itself. Deviate only
  when the message itself asks for content changes.
- ``action``: exactly "send_email" for any send/dispatch request.
- ``reply``: one short sentence describing what you will do."""


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
