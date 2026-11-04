"""One attempt ID across dispatch, parse, validation and cancellation.

The employee adaptation path needs a preserved trail for the exact request
that reached the model transport, the raw completion that came back, the
validation errors, and the stage that failed. Provider errors otherwise
collapse to ``None`` in ``pinned_structured_call`` and the only surviving
diagnosis is "no proposal" — which cannot distinguish a deadline from
malformed output.

This module is deliberately transport-agnostic. It is a recorder, not a
router: callers create one journal per user-visible attempt (initial + one
bounded repair) and events are appended in order under that attempt ID.
Secrets are redacted by key name; prompt/completion bodies are bounded.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

_SECRET_HINTS = (
    "api_key", "apikey", "api-key", "authorization", "bearer", "token",
    "secret", "password", "credential", "private_key",
)
_MAX_BODY = 24000


_TOKEN_COUNT_KEYS = {
    "tokens", "prompt_tokens", "completion_tokens", "total_tokens",
    "input_tokens", "output_tokens", "reasoning_tokens",
}


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        cleaned = {}
        for key, item in value.items():
            name = str(key).lower()
            is_count = name in _TOKEN_COUNT_KEYS and isinstance(
                item, (int, float)) and not isinstance(item, bool)
            if any(hint in name for hint in _SECRET_HINTS) and not is_count:
                cleaned[str(key)] = "[redacted]"
            else:
                cleaned[str(key)] = _redact(item)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    if isinstance(value, str) and len(value) > _MAX_BODY:
        return value[:_MAX_BODY] + "...[truncated]"
    return value


def _content_of(completion: Any) -> Optional[str]:
    """Best-effort raw text from an OpenAI-shaped completion object."""
    if completion is None:
        return None
    if isinstance(completion, str):
        return completion
    if isinstance(completion, Mapping):
        choices = completion.get("choices") or []
        if choices:
            first = choices[0]
            message = (first.get("message") if isinstance(first, Mapping)
                       else getattr(first, "message", None))
            if message is not None:
                content = (message.get("content")
                           if isinstance(message, Mapping)
                           else getattr(message, "content", None))
                if content is not None:
                    return str(content)
            text = (first.get("text") if isinstance(first, Mapping)
                    else getattr(first, "text", None))
            if text is not None:
                return str(text)
        return json.dumps(completion, default=str)[:12000]
    choices = getattr(completion, "choices", None) or []
    if choices:
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if content is not None:
            return str(content)
        text = getattr(choices[0], "text", None)
        if text is not None:
            return str(text)
    raw = getattr(completion, "content", None)
    if raw is not None:
        return str(raw)
    try:
        return json.dumps(completion, default=str)[:12000]
    except Exception:  # noqa: BLE001 — diagnostic only
        return str(completion)[:12000]


def failure_kind(exc: BaseException) -> str:
    name = type(exc).__name__.lower()
    text = f"{name} {exc}".lower()
    if "timeout" in name or "timeout" in text or "cancel" in name:
        return "deadline_cancelled"
    if any(token in text for token in (
            "validation", "json", "parse", "schema", "malformed",
            "truncat", "instructorretry")):
        return "malformed_structured_output"
    return "provider_failure"


def _exception_detail(exc: BaseException) -> Dict[str, Any]:
    detail: Dict[str, Any] = {
        "error_type": type(exc).__name__,
        "error": str(exc)[:12000],
    }
    errors = getattr(exc, "errors", None)
    if callable(errors):
        try:
            serialized = []
            for item in errors():
                serialized.append({
                    "type": str(item.get("type") or ""),
                    "loc": [str(part) for part in item.get("loc") or ()],
                    "msg": str(item.get("msg") or ""),
                    "input": _redact(item.get("input")),
                })
            detail["validation_errors"] = serialized
        except Exception:  # noqa: BLE001 — diagnostics only
            pass
    raw: List[str] = []
    for failed in getattr(exc, "failed_attempts", None) or []:
        completion = getattr(failed, "completion", None)
        content = _content_of(completion)
        failed_exc = getattr(failed, "exception", None)
        if content is None and failed_exc is not None:
            content = str(failed_exc)[:12000]
        if content:
            raw.append(content)
        if failed_exc is not None and "validation_errors" not in detail:
            nested = getattr(failed_exc, "errors", None)
            if callable(nested):
                try:
                    detail["validation_errors"] = [
                        {"type": str(i.get("type") or ""),
                         "loc": [str(p) for p in i.get("loc") or ()],
                         "msg": str(i.get("msg") or "")}
                        for i in nested()
                    ]
                except Exception:  # noqa: BLE001
                    pass
    last = getattr(exc, "last_completion", None)
    if last is not None:
        content = _content_of(last)
        if content:
            raw.append(content)
    if raw:
        detail["raw_completions"] = [_redact(item) for item in raw]
    return detail


class AttemptJournal:
    """Append-only record under one attempt ID; optional JSONL persistence."""

    def __init__(
        self,
        path: Optional[Any] = None,
        attempt_id: Optional[str] = None,
        stage: str = "employee-adaptation",
    ) -> None:
        self.attempt_id = attempt_id or uuid.uuid4().hex
        env_path = os.getenv("ATOM_EMPLOYEE_ATTEMPT_LOG")
        self.path = Path(path or env_path) if (path or env_path) else None
        self.stage = stage
        self.events: List[Dict[str, Any]] = []

    def record(self, event: str, **fields: Any) -> Dict[str, Any]:
        item = _redact({
            "attempt_id": self.attempt_id,
            "stage": self.stage,
            "event": event,
            "at": time.time(),
            **fields,
        })
        self.events.append(item)
        if self.path is not None:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(item, default=str, sort_keys=True))
                    handle.write("\n")
            except OSError:
                # Diagnostics must never break the employee call.
                pass
        return item

    def dispatch(self, **fields: Any) -> None:
        self.record("dispatch", **fields)

    def parsed(self, **fields: Any) -> None:
        self.record("parsed", **fields)

    def failure(self, exc: BaseException, **fields: Any) -> None:
        self.record(
            "failure", kind=failure_kind(exc), **_exception_detail(exc),
            **fields)

    def event(self, name: str, **fields: Any) -> None:
        self.record(name, **fields)
