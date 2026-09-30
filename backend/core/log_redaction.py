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
import os
import threading
from typing import Any, Dict, List, Optional

__all__ = ["shape", "fingerprint", "describe", "capture", "capture_enabled"]

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
