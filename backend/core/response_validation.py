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
_TOOL_NAME_JSON_PREFIX_RE = re.compile(
    r"^\s*[a-z][a-z0-9_-]{2,40}\s*:\s*\{"
)
_TOOL_NAME_JSON_CANDIDATE_RE = re.compile(
    r"^\s*[a-z][a-z0-9_-]{0,40}(?::|_)"
)
_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
_PARTIAL_MARKER_RE = re.compile(r"<\/?[A-Za-z0-9_.:-]*\s*$")
_QUOTED_LINE_RE = re.compile(r"^\s*[\"'].*[\"']\s*$")
_DOUBLE_QUOTED_RE = re.compile(r"\"(?:\\.|[^\"\\])*\"")
_SINGLE_QUOTED_RE = re.compile(r"'(?:\\.|[^'\\])*'")
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


# A short QUOTED SPAN: 'Use "<minimax:tool_call>" carefully.' — the marker
# inside quotes is an EXAMPLE being shown, not protocol being executed
# (2026-09-24 review: quoted examples must survive validation).
_QUOTED_SPAN_RE = re.compile(
    '"[^"]{0,200}"' 
    "|'[^']{0,200}'"
)



def _looks_like_quoted_protocol(value: str) -> bool:
    return bool(
        _TOOL_CALL_TAG_RE.search(value)
        or _REASONING_TAG_RE.search(value)
        or _PARTIAL_MARKER_RE.search(value)
        or re.search(
            r"[a-z][a-z0-9_-]{2,40}\s*:\s*\{",
            value,
            re.IGNORECASE,
        )
    )


def _add_quoted_protocol_spans(
    text: str, spans: List[tuple[int, int]],
) -> None:
    raw = str(text or "")
    complete_quotes = [
        * _DOUBLE_QUOTED_RE.finditer(raw),
        * _SINGLE_QUOTED_RE.finditer(raw),
    ]
    for match in complete_quotes:
        if _looks_like_quoted_protocol(match.group(0)):
            spans.append((match.start(), match.end()))
    for match in re.finditer(r"(?<!\\)([\"'])", raw):
        start = match.start()
        if any(begin <= start < end for begin, end in spans):
            continue
        quote = match.group(1)
        closing = re.search(
            rf"(?<!\\){re.escape(quote)}", raw[start + 1:]
        )
        end = start + 1 + closing.start() if closing else len(raw)
        if _looks_like_quoted_protocol(raw[start:end]):
            spans.append((start, end))


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
            or _PARTIAL_MARKER_RE.search(line)
        ):
            spans.append((start, end))
    if fence_start is not None:
        spans.append((fence_start, len(str(text or ""))))
    raw = str(text or "")
    _add_quoted_protocol_spans(raw, spans)
    for match in _INLINE_CODE_RE.finditer(raw):
        spans.append((match.start(), match.end()))
    for line_match in re.finditer(r"(?m)^.*$", raw):
        line_start = line_match.start()
        if any(start <= line_start < end for start, end in spans):
            continue
        ticks = [
            line_start + match.start()
            for match in re.finditer(r"(?<!`)`(?!`)", line_match.group(0))
        ]
        if len(ticks) % 2:
            spans.append((ticks[-1], len(raw)))
    for _q in _QUOTED_SPAN_RE.finditer(text):
        spans.append((_q.start(), _q.end()))
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
    for line in visible.splitlines():
        if _TOOL_NAME_JSON_PREFIX_RE.match(line):
            return f"incomplete bare tool-name JSON line ({line.strip()[:60]!r})"
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
    if (
        normalized_channel in {"final_text", "persisted_text"}
        and not normalized_type.startswith("text/")
    ):
        return ResponseValidation(
            False,
            "final text response must use a text content type",
            normalized_channel,
            normalized_type,
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
                # PENDING QUOTE (2026-09-24 review: identical content must
                # yield identical outcomes under any chunk boundary): a
                # marker preceded on its line by an ODD number of quotes
                # sits inside a span whose closing quote has not arrived
                # — hold from the opening quote, do not declare residue.
                line_start = t.rfind("\n", 0, match.start()) + 1
                prefix = t[line_start:match.start()]
                if prefix.count('"') % 2 or prefix.count("'") % 2:
                    quote_pos = max(
                        prefix.rfind('"'), prefix.rfind("'"))
                    hold_from = line_start + quote_pos
                    return t[:hold_from], t[hold_from:], False
                return t[: match.start()], "", True
    for match in re.finditer(r"(?m)^.*$", t):
        line = match.group(0)
        if _inside_spans(match.start(), spans):
            continue
        if _TOOL_NAME_JSON_LINE_RE.match(line):
            return t[: match.start()], "", True
        if _TOOL_NAME_JSON_PREFIX_RE.match(line):
            if match.end() >= len(t):
                return t[: match.start()], t[match.start() :], False
            return t[: match.start()], "", True
        if (
            _TOOL_NAME_JSON_CANDIDATE_RE.match(line)
            and match.end() >= len(t)
        ):
            return t[: match.start()], t[match.start() :], False
    for match in _PARTIAL_MARKER_RE.finditer(t):
        if (
            match.end() == len(t)
            and not _inside_spans(match.start(), spans)
        ):
            return t[: match.start()], t[match.start() :], False
    # PARTIAL bare tool-name JSON line: 'search_read: {"fi…' split across
    # chunks — the prefix would display before the line completes and the
    # full-line rule can reject it (2026-09-24 review: test bare JSON
    # lines in streaming, not just XML-style markers). Hold the tail.
    for match in re.finditer(
        r"(?m)^[ \t]*[a-z][a-z0-9_-]{2,40}[ \t]*:[ \t]*\{[^{}\n]*$",
        t,
    ):
        if not _inside_spans(match.start(), spans):
            return t[: match.start()], t[match.start() :], False
    return t, "", False
