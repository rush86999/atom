"""Validation and stream cleanup for response-channel payloads."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence


@dataclass(frozen=True)
class ResponseValidation:
    valid: bool
    reason: Optional[str]
    channel: str
    content_type: str


_TOOL_CALL_TAG_RE = re.compile(
    r"<[a-z0-9_.:-]*:(?:tool_call|function_call)\b|<\?function_call\b|"
    r"<invoke\b|<parameter\b|</(?:[a-z0-9_.:-]*:)?function_call>",
    re.IGNORECASE,
)
_REASONING_TAG_RE = re.compile(
    r"<think\b|</(?:mm:)?think>|</?(?:mm:)?thinking>",
    re.IGNORECASE,
)
_TOOL_NAME_JSON_LINE_RE = re.compile(
    r"^\s*[a-z][a-z0-9_-]{2,40}\s*:\s*\{.*\}[,;]?\s*$",
    re.MULTILINE,
)
_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
_PARTIAL_MARKER_RE = re.compile(r"<\/?[A-Za-z0-9_.:-]*\s*$")
_QUOTED_LINE_RE = re.compile(r"^\s*[\"'].*[\"']\s*$")
_EXAMPLE_LINE_RE = re.compile(
    r"^\s*(?:example|e\.g\.|for example|sample|quoted)\b",
    re.IGNORECASE,
)
_ALLOWED_CHANNELS = {
    "final_text",
    "persisted_text",
    "stream",
    "tool",
    "structured",
    "internal",
}


def _normalized_content_type(content_type: str) -> str:
    return str(content_type or "text/plain").split(";", 1)[0].strip().lower()


def _exempt_spans(text: str) -> List[tuple[int, int]]:
    spans: List[tuple[int, int]] = []
    offset = 0
    fence_start: Optional[int] = None
    fence_marker = ""
    for line in str(text or "").splitlines(keepends=True):
        start = offset
        end = start + len(line)
        offset = end
        stripped = line.lstrip()
        fence_match = _FENCE_RE.match(line)
        if fence_start is not None:
            if fence_match and stripped.startswith(fence_marker):
                spans.append((fence_start, end))
                fence_start = None
                fence_marker = ""
            continue
        if fence_match:
            marker = stripped[:3]
            fence_start = start
            fence_marker = marker
            spans.append((start, end))
            continue
        if stripped.startswith(">") or _QUOTED_LINE_RE.match(line):
            spans.append((start, end))
        elif _EXAMPLE_LINE_RE.match(line) and (
            _TOOL_CALL_TAG_RE.search(line)
            or _REASONING_TAG_RE.search(line)
            or _TOOL_NAME_JSON_LINE_RE.match(line)
        ):
            spans.append((start, end))
    if fence_start is not None:
        spans.append((fence_start, len(str(text or ""))))
    for match in _INLINE_CODE_RE.finditer(str(text or "")):
        spans.append((match.start(), match.end()))
    return spans


def _inside_spans(position: int, spans: Sequence[tuple[int, int]]) -> bool:
    return any(start <= position < end for start, end in spans)


def _visible_text(text: str) -> str:
    raw = str(text or "")
    spans = _exempt_spans(raw)
    if not spans:
        return raw
    pieces: List[str] = []
    cursor = 0
    for start, end in sorted(spans):
        if start > cursor:
            pieces.append(raw[cursor:start])
        cursor = max(cursor, end)
    if cursor < len(raw):
        pieces.append(raw[cursor:])
    return "".join(pieces)


def _scan_visible_text(text: str) -> Optional[str]:
    visible = _visible_text(text)
    if _TOOL_CALL_TAG_RE.search(visible):
        return "tool-call tag syntax"
    if _REASONING_TAG_RE.search(visible):
        return "reasoning tag residue"
    if _PARTIAL_MARKER_RE.search(visible):
        return "incomplete protocol marker"
    for line in visible.splitlines():
        if _TOOL_NAME_JSON_LINE_RE.match(line):
            return f"bare tool-name JSON line ({line.strip()[:60]!r})"
    return None


def validate_response_payload(
    payload: Any,
    *,
    channel: str = "final_text",
    content_type: str = "text/plain",
) -> ResponseValidation:
    normalized_channel = str(channel or "final_text").strip().lower()
    normalized_type = _normalized_content_type(content_type)
    if normalized_channel not in _ALLOWED_CHANNELS:
        return ResponseValidation(
            False, "unknown response channel", normalized_channel, normalized_type
        )
    if normalized_type == "application/json" or normalized_type.endswith("+json"):
        if isinstance(payload, (dict, list)):
            return ResponseValidation(
                True, None, normalized_channel, normalized_type
            )
        if isinstance(payload, str):
            try:
                json.loads(payload)
            except (TypeError, ValueError):
                return ResponseValidation(
                    False,
                    "invalid JSON response payload",
                    normalized_channel,
                    normalized_type,
                )
            return ResponseValidation(
                True, None, normalized_channel, normalized_type
            )
        return ResponseValidation(
            False, "JSON response is not an object or string", normalized_channel, normalized_type
        )
    if not isinstance(payload, str):
        return ResponseValidation(
            False, "text response payload is not a string", normalized_channel, normalized_type
        )
    if not payload.strip():
        return ResponseValidation(True, None, normalized_channel, normalized_type)
    if normalized_channel in {"stream", "tool", "structured", "internal"}:
        return ResponseValidation(True, None, normalized_channel, normalized_type)
    if not normalized_type.startswith("text/"):
        return ResponseValidation(
            False, "unsupported final response content type", normalized_channel, normalized_type
        )
    reason = _scan_visible_text(payload)
    return ResponseValidation(
        reason is None,
        reason,
        normalized_channel,
        normalized_type,
    )


def malformed_output_reason(
    text: Any,
    *,
    channel: str = "final_text",
    content_type: str = "text/plain",
) -> Optional[str]:
    return validate_response_payload(
        text, channel=channel, content_type=content_type
    ).reason


def is_malformed_output(
    text: Any,
    *,
    channel: str = "final_text",
    content_type: str = "text/plain",
) -> bool:
    return not validate_response_payload(
        text, channel=channel, content_type=content_type
    ).valid


def strip_protocol_fragments(
    text: str, captured: Optional[List[str]] = None
) -> str:
    normalized = _ZERO_WIDTH_RE.sub("", str(text or "")).strip()
    if captured is not None:
        for match in re.finditer(r"<think>(.*?)</think>", normalized, flags=re.DOTALL):
            block = (match.group(1) or "").strip()
            if block:
                captured.append(block)
    normalized = re.sub(r"<think>.*?</think>", "", normalized, flags=re.DOTALL)
    normalized = re.sub(
        r"<(?:[a-z0-9_.:-]+:)?(?:tool_call|function_call)>.*?"
        r"</(?:[a-z0-9_.:-]+:)?(?:tool_call|function_call)>",
        "",
        normalized,
        flags=re.DOTALL | re.IGNORECASE,
    )
    normalized = re.sub(r"</?(?:mm:)?think>", "", normalized, flags=re.IGNORECASE)
    normalized = _PARTIAL_MARKER_RE.sub("", normalized)
    return normalized.strip()


def split_safe_prefix(text: str) -> "tuple[str, str, bool]":
    t = _ZERO_WIDTH_RE.sub("", str(text or ""))
    spans = _exempt_spans(t)
    for pattern in (_TOOL_CALL_TAG_RE, _REASONING_TAG_RE):
        for match in pattern.finditer(t):
            if not _inside_spans(match.start(), spans):
                return t[: match.start()], "", True
    for match in re.finditer(r"(?m)^.*$", t):
        line = match.group(0)
        if (
            _TOOL_NAME_JSON_LINE_RE.match(line)
            and not _inside_spans(match.start(), spans)
        ):
            return t[: match.start()], "", True
    for match in _PARTIAL_MARKER_RE.finditer(t):
        if (
            match.end() == len(t)
            and not _inside_spans(match.start(), spans)
        ):
            return t[: match.start()], t[match.start() :], False
    return t, "", False
