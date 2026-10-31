"""Durable, typed context clarification for conversation-derived teaching.

The resolver in ``student_learning_service.resolve_teaching_contract`` is the
authority for what context a lesson needs. This module turns its typed
blockers into a pending obligation, interprets the user's bounded answer, and
merges only confirmed fields back into the task context.

It deliberately does not infer authority or qualification from prose. A
self-reported value is recorded as ``user_confirmation`` — never as an
independently verified certification.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SCHEMA = "teaching-clarification-1"

_UNCERTAIN_RE = re.compile(
    r"\b(?:probably|maybe|perhaps|possibly|might\s+be|may\s+be|"
    r"i\s+think|i\s+believe|not\s+sure|unsure|likely|roughly|"
    r"around|approximately|guess(?:ing)?)\b",
    re.IGNORECASE,
)
_CANCEL_RE = re.compile(
    r"^\s*(?:cancel|never\s*mind|nevermind|stop|forget\s+it|"
    r"don'?t\s+bother|no\s+thanks?)\s*[.!]?\s*$",
    re.IGNORECASE,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_pending(
    *,
    session_id: str,
    user_id: str,
    agent_id: str,
    workspace_id: str,
    tenant_id: str,
    objective: str,
    required_context: List[Dict[str, Any]],
    established_context: Optional[Dict[str, Any]] = None,
    lesson_refs: Optional[List[Dict[str, Any]]] = None,
    source_bindings: Optional[List[Dict[str, Any]]] = None,
    request_id: Optional[str] = None,
    all_context_values: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    return {
        "schema": SCHEMA,
        "clarification_id": uuid.uuid4().hex,
        "state": "pending",
        "session_id": str(session_id or ""),
        "user_id": str(user_id or ""),
        "agent_id": str(agent_id or ""),
        "workspace_id": str(workspace_id or ""),
        "tenant_id": str(tenant_id or ""),
        "objective": str(objective or "")[:4000],
        "request_id": str(request_id or "") or None,
        "lesson_refs": [
            {"id": str(item.get("id") or ""),
             "revision": int(item.get("revision") or 1)}
            for item in (lesson_refs or []) if item.get("id")
        ][:40],
        "required_context": [
            {
                "key": str(row.get("key") or ""),
                "allowed_values": [
                    str(value) for value in (row.get("allowed_values") or [])
                    if str(value).strip()
                ][:20],
                "lesson_ids": [
                    str(value) for value in (row.get("lesson_ids") or [])
                    if str(value).strip()
                ][:20],
                "authority": "user_confirmation",
            }
            for row in (required_context or []) if row.get("key")
        ][:24],
        "established_context": dict(established_context or {}),
        "all_context_values": {
            str(key): [str(value) for value in (values or []) if str(value).strip()]
            for key, values in (all_context_values or {}).items()
        },
        "source_bindings": list(source_bindings or [])[:40],
        "created_at": _now(),
        "updated_at": _now(),
        "last_answer": None,
        "last_status": "pending",
        "confirmed_context": {},
        "confirmation_source": None,
        "confirmed_at": None,
    }


def is_cancel(message: str) -> bool:
    return bool(_CANCEL_RE.match(str(message or "")))


def _match_allowed(text: str, allowed: List[str]) -> List[str]:
    low = str(text or "").casefold()
    matched: List[str] = []
    for value in allowed:
        probe = str(value or "").strip().casefold()
        if not probe:
            continue
        if re.search(r"(?<![a-z0-9])" + re.escape(probe) + r"(?![a-z0-9])",
                     low):
            if value not in matched:
                matched.append(value)
    return matched


def _explicit_value(text: str, key: str) -> Optional[str]:
    pattern = re.compile(
        r"(?<![a-z0-9_])" + re.escape(str(key or "")) +
        r"\s*(?:=|:|\bis\b|\bof\b)\s*([^\n,;]+)",
        re.IGNORECASE,
    )
    match = pattern.search(str(text or ""))
    if not match:
        return None
    value = " ".join(match.group(1).split()).strip(" .")
    return value[:200] or None


def infer_context_from_message(
    message: str,
    all_context_values: Dict[str, List[str]],
) -> Dict[str, str]:
    """Conservative context inference from the ORIGINAL request.

    Only a single unambiguous allowed value per key is accepted. This is
    what lets "the Customer-A order" establish ``customer`` without the
    client handcrafting request JSON, while "Customer-A or Customer-B"
    stays unresolved.
    """
    inferred: Dict[str, str] = {}
    if _UNCERTAIN_RE.search(str(message or "")):
        # "probably Customer-A" is not established context.
        return inferred
    for key, values in (all_context_values or {}).items():
        matched = _match_allowed(message, [str(v) for v in (values or [])])
        if len(matched) == 1:
            inferred[str(key)] = matched[0]
    return inferred


def extract_confirmation(message: str, pending: Dict[str, Any]) -> Dict[str, Any]:
    """Bounded interpretation of the user's answer to a pending clarification.

    - an explicit value for a required key resolves that key;
    - a known allowed value resolves it only when exactly one value matches;
    - multiple values for one key are ambiguous and never silently chosen;
    - uncertainty markers preserve uncertainty instead of confirming;
    - an explicit value for an already-established key is a scope update.
    """
    text = str(message or "")
    if is_cancel(text):
        return {"status": "cancelled", "answers": {}, "scope_updates": {},
                "ambiguous": [], "uncertain": [], "unmatched": []}
    uncertain = bool(_UNCERTAIN_RE.search(text))
    required = list((pending or {}).get("required_context") or [])
    established = dict((pending or {}).get("established_context") or {})
    all_values = dict((pending or {}).get("all_context_values") or {})
    answers: Dict[str, str] = {}
    scope_updates: Dict[str, str] = {}
    ambiguous: List[str] = []
    uncertain_keys: List[str] = []
    unmatched: List[str] = []

    required_keys = {str(row.get("key") or "") for row in required}
    for row in required:
        key = str(row.get("key") or "").strip()
        if not key:
            continue
        allowed = [str(value) for value in (row.get("allowed_values") or [])]
        explicit = _explicit_value(text, key)
        if explicit:
            if allowed:
                matched = _match_allowed(explicit, allowed)
                if len(matched) == 1:
                    answers[key] = matched[0]
                elif len(matched) > 1:
                    ambiguous.append(key)
                else:
                    unmatched.append(key)
            else:
                answers[key] = explicit
            continue
        matched = _match_allowed(text, allowed)
        if len(matched) > 1:
            ambiguous.append(key)
        elif len(matched) == 1:
            if uncertain:
                uncertain_keys.append(key)
            else:
                answers[key] = matched[0]
        else:
            unmatched.append(key)

    # A value for a non-missing established key is a scope change. Only an
    # explicit key=value form is accepted; bare names are too ambiguous to
    # silently rewrite an already-established task dimension.
    for key, values in all_values.items():
        if key in required_keys:
            continue
        explicit = _explicit_value(text, key)
        if not explicit:
            continue
        matched = _match_allowed(explicit, values) if values else [explicit]
        if len(matched) == 1:
            current = established.get(key)
            if str(current or "").casefold() != matched[0].casefold():
                scope_updates[key] = matched[0]
        elif len(matched) > 1:
            ambiguous.append(key)

    if ambiguous:
        status = "ambiguous"
    elif uncertain_keys:
        status = "uncertain"
    elif required and len(answers) >= len([
            row for row in required if row.get("key")]):
        status = "confirmed"
    elif answers or scope_updates:
        status = "partial"
    else:
        status = "unresolved"
    return {
        "status": status,
        "answers": answers,
        "scope_updates": scope_updates,
        "ambiguous": sorted(set(ambiguous)),
        "uncertain": sorted(set(uncertain_keys)),
        "unmatched": sorted(set(unmatched)),
    }


def merge_confirmed_context(
    pending: Dict[str, Any],
    confirmation: Dict[str, Any],
) -> Dict[str, Any]:
    merged = dict((pending or {}).get("established_context") or {})
    merged.update(dict((confirmation or {}).get("answers") or {}))
    merged.update(dict((confirmation or {}).get("scope_updates") or {}))
    return merged


def render_user_question(pending: Dict[str, Any]) -> str:
    required = list((pending or {}).get("required_context") or [])
    parts: List[str] = []
    for row in required:
        key = str(row.get("key") or "").strip()
        if not key:
            continue
        allowed = [str(value) for value in (row.get("allowed_values") or [])
                   if str(value).strip()]
        parts.append(key + (f" (one of: {', '.join(allowed)})" if allowed else ""))
    if not parts:
        return "I need one more detail before I can apply the taught method."
    question = (
        "Before I can apply the taught method, I need to confirm: "
        + "; ".join(parts) + "."
    )
    status = str((pending or {}).get("last_status") or "")
    if status == "ambiguous":
        question += (
            " I couldn't safely choose between the values you mentioned; "
            "please name the one that applies."
        )
    elif status == "uncertain":
        question += (
            " I don't want to treat an uncertain answer as confirmed; "
            "please state the value plainly."
        )
    return question


def mark_confirmed(
    pending: Dict[str, Any],
    confirmation: Dict[str, Any],
) -> Dict[str, Any]:
    updated = dict(pending or {})
    updated["state"] = "confirmed"
    updated["confirmed_context"] = dict(
        (confirmation or {}).get("answers") or {})
    updated["scope_updates"] = dict(
        (confirmation or {}).get("scope_updates") or {})
    updated["confirmation_source"] = "user"
    updated["confirmed_at"] = _now()
    updated["updated_at"] = _now()
    updated["last_status"] = "confirmed"
    return updated


def mark_pending(
    pending: Dict[str, Any],
    confirmation: Dict[str, Any],
    message: str,
) -> Dict[str, Any]:
    updated = dict(pending or {})
    updated["state"] = "pending"
    updated["last_answer"] = str(message or "")[:1000]
    updated["last_status"] = str(
        (confirmation or {}).get("status") or "unresolved")
    updated["updated_at"] = _now()
    return updated
