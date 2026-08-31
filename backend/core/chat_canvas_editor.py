"""LLM-based canvas editor for the chat path (canvas co-editor panel).

The /canvas/{id} side panel ("Agent Co-Editor") sends /api/chat/message with
the open canvas in ``context`` (canvas_id / canvas_type / canvas_content).
Until now nothing on the chat path consumed it: the reply came from a prompt
that had never seen the canvas, the tool planner is read-only integration
search by design, and the intent router misfiled edit requests (a "tighten
the draft" message became TASK_MANAGEMENT and created a junk local task).

This module is the write-side counterpart of ``core.chat_tool_planner``
(which stays read-only): a cheap structured-output LLM call decides whether
the message asks to change THE OPEN CANVAS; if so it produces the complete
new content, and ``apply_canvas_edit`` persists it through the existing
general mechanism — ``tools.canvas_crud_tool.update_canvas_content``
(append-only CanvasAudit + WS ``canvas:update`` broadcast that the canvas
page already renders live).

Every leg is fault-isolated like the planner: any failure returns None and
the turn falls through to the normal conversational path — never raises into
the chat path, never loses the user's message.
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional

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


class CanvasEditPlan(BaseModel):
    wants_edit: bool = False
    # Complete new canvas content as a JSON-encoded string — strings survive
    # every structured-output provider (weak models mangle free-form object
    # fields far more often than string fields).
    updated_content_json: Optional[str] = None
    title: Optional[str] = None
    reply: str = ""


_EDITOR_SYSTEM = """You are the canvas editor for an AI co-editing panel.
The user is chatting next to an OPEN canvas whose current content is shown
below. Decide whether their latest message asks you to CHANGE that canvas
(edit, revise, rewrite, shorten, expand, remove, add, reformat, translate,
fill in, or produce the final version of it), and if so produce the new
content.

Rules:
- wants_edit=true ONLY for requests that change this canvas's content.
  Questions, discussion, or requests about other things (e.g. "send it",
  "what do you think", "search my email") are wants_edit=false.
- updated_content_json must be the COMPLETE new canvas content, JSON-encoded,
  in EXACTLY the same shape as the current content shown below (same keys,
  same types). Never return a fragment, a diff, or an explanation — the
  harness stores it verbatim as the new canvas content.
- Apply the user's instruction faithfully to the whole content. Remove any
  meta-commentary ("Here's your draft...", "Want me to adjust...") from the
  content itself — the canvas holds only the artifact.
- reply is one or two short sentences telling the user what you changed.
  For wants_edit=false, reply is a short conversational answer based on the
  canvas content (or empty if another step will answer)."""


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
    """User turns only, mirroring the planner: follow-ups like "now make it
    shorter" are only interpretable against the earlier request."""
    lines: List[str] = []
    for h in (history or [])[-6:]:
        u = str((h or {}).get("message") or "").strip()
        if u:
            lines.append(f"User: {u[:200]}")
    lines.append(f"User: {current[:600]}")
    return "\n".join(lines)


async def plan_canvas_edit(
    message: str,
    history: List[Dict[str, Any]],
    canvas: Dict[str, Any],
    llm_service: Any,
) -> Optional[CanvasEditPlan]:
    """Decide (via cheap structured LLM output) whether this turn edits the
    open canvas, and produce the full new content. Returns None on any
    failure — the caller then falls through to the conversational path."""
    if llm_service is None or not canvas.get("canvas_id"):
        return None

    prompt = (
        f"{_EDITOR_SYSTEM}\n\n"
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
    return plan


async def apply_canvas_edit(
    plan: CanvasEditPlan,
    user_id: str,
    canvas: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Persist the planned content through the general canvas CRUD layer
    (CanvasAudit append + WS broadcast). Returns the update result dict on
    success, None on any failure or malformed plan (caller falls through to
    the conversational path instead of storing garbage)."""
    if not plan or not plan.wants_edit or not (plan.updated_content_json or "").strip():
        return None

    raw = plan.updated_content_json.strip()
    current = canvas.get("content")
    # Decode the JSON string. If the model returned a bare string for a
    # canvas whose content IS a plain string (markdown/doc bodies), a failed
    # JSON parse still yields a usable value — accept it only for that shape.
    try:
        new_content = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        if isinstance(current, str):
            new_content = raw
        else:
            logger.warning("canvas edit: updated_content_json is not valid JSON — discarding")
            return None

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
- ``body``: the FULL email body to send. Default to the canvas draft content
  (cleaned of any meta notes) unless the message specifies changes.
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
