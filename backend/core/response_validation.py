"""Central malformed-output validation for provider and tool payloads.

Providers occasionally leak INTERMEDIATE PROTOCOL into final text: tool-call
XML from any vendor's function-calling dialect (``<minimax:tool_call>``,
``<invoke>``, ``<parameter>``), reasoning tags (``</mm:think>``, ``<think>``),
and bare tool-name JSON blocks (``search_read: {"file": …}`` — observed live
2026-09-24). None of that is an answer. Shipping it presents protocol
residue as content, and SANITIZING it can hide a failed execution behind
whatever prose survives the strip — so the contract is REJECT, not strip
(2026-09-24 review).

One shape-based detector, used everywhere a payload becomes user-facing or
persisted: reply finalization (narration rejection), error-turn
classification, and anything else that must distinguish an answer from a
protocol fragment. The patterns describe SHAPES (tag-like tool-call syntax,
reasoning wrappers, single-line tool-name JSON), never provider names or
task vocabulary — new providers that leak the same shapes are covered
without code changes.
"""
import re
from typing import List, Optional

# Tag-dialect tool-call syntax: <any-namespace:tool_call>, <invoke>,
# <parameter>, </function_call> … (shape-based; the namespace varies by
# provider).
_TOOL_CALL_TAG_RE = re.compile(
    r"<[a-z0-9_.:-]*:(?:tool_call|function_call)\b|<\?function_call\b|"
    r"<invoke\b|<parameter\b|</(?:[a-z0-9_.:-]*:)?function_call>",
    re.IGNORECASE,
)

# Reasoning/model-internal wrappers.
_REASONING_TAG_RE = re.compile(
    r"<think\b|</(?:mm:)?think>|</?(?:mm:)?thinking>",
    re.IGNORECASE,
)

# A bare tool-name JSON line: `tool_name: {…}` — single line, JSON object
# tail. Tool names are snake/keel identifiers; the object must open and
# the line must END in } or ) (a prose line with a colon rarely does).
_TOOL_NAME_JSON_LINE_RE = re.compile(
    r"^\s*[a-z][a-z0-9_-]{2,40}\s*:\s*\{.*\}[,;]?\s*$",
    re.MULTILINE,
)

_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")

_MALFORMED_MARKERS = (
    _TOOL_CALL_TAG_RE,
    _REASONING_TAG_RE,
    _TOOL_NAME_JSON_LINE_RE,
)


def malformed_output_reason(text: str) -> Optional[str]:
    """Why this payload is protocol residue rather than an answer, or
    ``None`` when it looks like ordinary content."""
    t = str(text or "")
    if not t.strip():
        return None
    normalized = _ZERO_WIDTH_RE.sub("", t)
    if _TOOL_CALL_TAG_RE.search(normalized):
        return "tool-call tag syntax"
    if _REASONING_TAG_RE.search(normalized):
        return "reasoning tag residue"
    for line in normalized.splitlines():
        if _TOOL_NAME_JSON_LINE_RE.match(line):
            return f"bare tool-name JSON line ({line.strip()[:60]!r})"
    return None


def is_malformed_output(text: str) -> bool:
    """True when the payload is protocol residue and must be REJECTED (not
    sanitized) wherever it would become an answer."""
    return malformed_output_reason(text) is not None


def strip_protocol_fragments(
    text: str, captured: Optional[List[str]] = None,
) -> str:
    """Remove paired protocol fragments from STREAMED content while
    capturing ``<think>`` inner text for audit.

    This is for stream assembly, where partial cleanup is legitimate; final
    answers use :func:`is_malformed_output` and reject instead."""
    t = _ZERO_WIDTH_RE.sub("", str(text or "")).strip()
    if captured is not None:
        for _m in re.finditer(r"<think>(.*?)</think>", t, flags=re.DOTALL):
            _block = (_m.group(1) or "").strip()
            if _block:
                captured.append(_block)
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.DOTALL)
    t = re.sub(r"<tool_call>.*?</tool_call>", "", t, flags=re.DOTALL)
    t = re.sub(r"</?(?:mm:)?think>", "", t)
    t = re.sub(r"\]?<\]?minimax\[>?", "", t)
    return t.strip()
