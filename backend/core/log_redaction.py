"""Log redaction: describe payloads structurally instead of reproducing them.

WHY THIS EXISTS
Routine INFO logging in the chat path wrote the request itself:

    chat_routes: ``Processing chat message from user {id}: {request.message}``
    chat_routes: ``[CHATCTX] ... context={request.context!r}``
    websockets:  ``Broadcasting to '{channel}' ({n} clients): {str(message)[:200]}``

The second one alone dumps ``context['canvas_content']`` -- the entire canvas
body -- and the third truncates a payload rather than describing it, which
reproduces the first 200 characters of whatever the frame happened to carry.
The candidate_fix1 ``preview_backend.log`` (2.7 MB) contains a user's message
text and a canvas body verbatim. Diagnostics need the SHAPE of a payload to
debug a routing or parsing problem; they never need the payload itself.

What is kept, per the standing rule for this work:
  * schema shape -- types, dict keys, list lengths, nesting
  * identities   -- ids that already appear in the surrounding record
  * violations   -- the concrete conflicting fields a check rejected
  * redacted diagnostics -- lengths and content fingerprints, which are enough
    to answer "did this turn carry a canvas?", "was it the same body twice?",
    and "did the body change after the edit?" without storing the body.

Full payloads are still available, but only as an explicit, separate artifact:
set ``ATOM_ACCEPTANCE_CAPTURE_PAYLOAD=<path>`` and the values are appended to
that file, which is acceptance evidence under a controlled world, not the
routine log. Unset -- the default everywhere, including production -- nothing
is written.

``fingerprint`` is a truncated sha256 of the value, not of its repr, so it
compares equal for equal content across processes and log lines.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

__all__ = [
    "shape", "fingerprint", "describe", "capture", "capture_enabled",
    "redact_log_text", "LogRedactionFilter",
]

_MAX_DEPTH = 4
_MAX_KEYS = 24
_MAX_SEQ = 3
_capture_lock = threading.Lock()


def fingerprint(value: Any) -> str:
    """Short, stable content fingerprint. Equal content -> equal string."""
    if value is None:
        return "none"
    if isinstance(value, str):
        raw = value
    else:
        try:
            raw = json.dumps(value, sort_keys=True, default=str)
        except (TypeError, ValueError):
            raw = str(value)
    return hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:12]


def shape(value: Any, _depth: int = 0) -> Any:
    """Structural description of a value. Never returns a scalar's content.

    Types and key names are preserved because they are the diagnostic signal;
    string values are reduced to a length, so a leaked body cannot ride along
    inside a "shape".
    """
    if _depth >= _MAX_DEPTH:
        return "..."
    if value is None or isinstance(value, (bool, int, float)):
        return type(value).__name__
    if isinstance(value, str):
        return f"str(len={len(value)})"
    if isinstance(value, bytes):
        return f"bytes(len={len(value)})"
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for i, (k, v) in enumerate(value.items()):
            if i >= _MAX_KEYS:
                out["..."] = f"+{len(value) - _MAX_KEYS} more keys"
                break
            out[str(k)] = shape(v, _depth + 1)
        return out
    if isinstance(value, (list, tuple, set)):
        seq = list(value)
        return {
            "__seq__": type(value).__name__,
            "len": len(seq),
            "sample": [shape(v, _depth + 1) for v in seq[:_MAX_SEQ]],
        }
    return f"{type(value).__name__}()"


def describe(value: Any, label: str = "") -> str:
    """One-line, value-free description suitable for a routine log line."""
    prefix = f"{label} " if label else ""
    if isinstance(value, str):
        return f"{prefix}len={len(value)} fp={fingerprint(value)}"
    return f"{prefix}shape={json.dumps(shape(value), sort_keys=True, default=str)}"


def capture_enabled() -> bool:
    return bool(os.environ.get("ATOM_ACCEPTANCE_CAPTURE_PAYLOAD"))


def capture(value: Any, label: str) -> Optional[str]:
    """Append a full payload to the acceptance-evidence file, if enabled.

    Returns the path written, or None when capture is off (the default). This
    is the ONLY sanctioned place a full request or frame body is written, and
    it is a separate file from the routine log so that turning capture on
    cannot widen what the routine log contains.
    """
    path = os.environ.get("ATOM_ACCEPTANCE_CAPTURE_PAYLOAD")
    if not path:
        return None
    record = {
        "label": label,
        "pid": os.getpid(),
        "shape": shape(value),
        "fingerprint": fingerprint(value),
        "payload": value,
    }
    line = json.dumps(record, default=str)
    with _capture_lock:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    return path


# ---------------------------------------------------------------------------
# Credential-safe log text
# ---------------------------------------------------------------------------
# Uvicorn logs the WebSocket request target at INFO on its own logger
# (``uvicorn.error``), including the ``?token=<jwt>`` query string.  The
# generic payload helpers above intentionally describe application payloads;
# this filter is the narrower boundary for request/status log lines.
_SENSITIVE_KEYS = {
    "access_token", "refresh_token", "id_token", "session_token",
    "device_token", "token", "jwt", "api_key", "apikey", "secret",
    "password", "passwd", "authorization", "auth", "signature", "sig",
}
_QUERY_RE = re.compile(r"([?&;])([^=&#\s]+)=([^&#\s]*)")
_ASSIGN_RE = re.compile(
    r"(?i)(\b(?:access[_-]?token|refresh[_-]?token|id[_-]?token|"
    r"session[_-]?token|device[_-]?token|token|jwt|api[_-]?key|apikey|"
    r"secret|password|passwd|auth|signature|sig)\b"
    r"[\"']?\s*[:=]\s*[\"']?)([^\"'\s,;&}]+)")
_AUTH_HEADER_RE = re.compile(
    r"(?i)\b(Authorization\s*:\s*)(Bearer\s+)?"
    r"[A-Za-z0-9._~+/=\-]{8,}")
_BEARER_RE = re.compile(
    r"(?i)\b(Bearer)\s+[A-Za-z0-9._~+/=\-]{8,}")


def _normalized_key(key: str) -> str:
    try:
        key = unquote(key)
    except Exception:  # noqa: BLE001 — malformed escape is still a key
        pass
    return key.strip().lower().replace("-", "_")


def _redact_query(match: "re.Match[str]") -> str:
    separator, key, _value = match.groups()
    if _normalized_key(key) in _SENSITIVE_KEYS:
        return f"{separator}{key}=<redacted>"
    return match.group(0)


def redact_log_text(text: str) -> str:
    """Redact credential-bearing query/assignment material from log text.

    Preserves the path, status, operation and non-sensitive parameters. Handles
    repeated and percent-encoded query keys/values, URL query strings, ordinary
    key/value text and ``Bearer`` headers. Never raises.
    """
    if not text:
        return text
    try:
        value = str(text)
        value = _QUERY_RE.sub(_redact_query, value)
        value = _AUTH_HEADER_RE.sub(r"\1\2<redacted>", value)
        value = _BEARER_RE.sub(r"\1 <redacted>", value)
        value = _ASSIGN_RE.sub(r"\1<redacted>", value)
        return value
    except Exception:  # noqa: BLE001 — logging must never break
        return text


class LogRedactionFilter(logging.Filter):
    """Apply :func:`redact_log_text` before handlers format a record."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
            redacted = redact_log_text(message)
            if redacted != message:
                record.msg = redacted
                record.args = ()
        except Exception:  # noqa: BLE001 — never drop a log record
            pass
        return True
