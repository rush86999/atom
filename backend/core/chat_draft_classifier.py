"""Structural draft/artifact detection for chat→canvas content.

Chat drafts that contain an email (the most common artifact users expand
into a canvas) were stored as generic ``document`` canvases with the
``Subject:`` line embedded in the markdown body — so /canvas/{id} rendered
a plain document editor: no To/Subject fields, no Send button. This module
is the single detector used at every boundary where freeform draft text
becomes canvas content:

- ``integrations.chat_routes.chat_draft_to_canvas`` (creation, and the
  "Open latest draft in canvas" message selection)
- ``tools.canvas_crud_tool.read_canvas`` (read-time repair of canvases
  created before the classifier existed — the audit trail is append-only,
  so misclassified history is normalized on read, never rewritten)
- ``tools.canvas_crud_tool.update_canvas_content`` (co-editor chat edits)

Detection is deliberately conservative and structural, not intent guessing:

- email: the shape every mail client uses (RFC 5322-style ``To:``/
  ``Subject:`` header block at the top of the body); a ``Subject:`` line
  must appear within the first few non-empty lines and be followed by real
  body content — documents that merely mention "Subject:" mid-text do not
  match.
- code / table / doc (``detect_draft_kind``): fenced code blocks, markdown
  tables, and titled documents — so draft selection generalizes to every
  canvas type, skipping conversational replies.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# "To:" / "Cc:" / "Subject:" at line start, tolerant of markdown decoration.
# The bold pair in "**Subject:**" wraps the colon, so the closer is accepted
# after the colon (also handles plain "Subject:" and quoted "> Subject:").
_HEADER_LINE = re.compile(
    r"^\s{0,3}(?:[#>]+\s*)?(?:\*\*|__)?\s*(To|Cc|Subject)\s*:\s*(?:\*\*|__)?\s*(.*)$",
    re.IGNORECASE,
)

# How many non-empty lines to scan for the header block before giving up.
_MAX_HEADER_SCAN_LINES = 8

# A subject alone is not an email — require this much body after the headers.
_MIN_BODY_CHARS = 20

# Canvas types whose content is freeform text and may therefore be a
# misclassified email draft.
_DOC_LIKE_TYPES = {"document", "docs", "markdown", "generic", "doc"}

# Separators agents commonly fence a draft with ("---"). Ignored while
# locating the header block and stripped from the extracted body.
_SEPARATOR_LINE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")

# A standalone closing line ("Best regards,", "**Thanks,**") that
# introduces an agent-typed sign-off. Must occupy the whole line — "thanks
# for your patience" is prose, not a closing. Markdown bold may wrap the
# phrase with the comma inside the pair ("**Best regards,**").
_CLOSING_LINE = re.compile(
    r"^\s*\*{0,2}(?:best regards|warm regards|kind regards|regards|sincerely|"
    r"thank you|thanks|cheers|respectfully)\*{0,2}\s*,?\s*\*{0,2}\s*$",
    re.IGNORECASE,
)


def strip_trailing_signoff(text: str) -> str:
    """Drop an agent-typed trailing sign-off block from a draft body.

    The email composer appends the user's REAL default signature (their
    Outlook integration's); an LLM-guessed sign-off ("[Your Name]",
    wrong contact lines) must not shadow it. Only a clear closing-led tail
    block is stripped — everything else is preserved verbatim.
    """
    if not text:
        return text
    lines = text.rstrip().splitlines()
    for i in range(len(lines) - 1, -1, -1):
        if _CLOSING_LINE.match(lines[i]):
            kept = lines[:i]
            while kept and not kept[-1].strip():
                kept.pop()
            return "\n".join(kept)
        # Sign-off blocks are signature-sized; stop scanning past that
        # window so a "Regards," mid-body never truncates the draft.
        if len(lines) - i > 16:
            break
    return text


def strip_agent_signoff(body: str, default_signature: Optional[str]) -> str:
    """Strip an agent-typed sign-off ONLY when the user HAS a default
    signature — the composer then appends the real one. With no default,
    the agent's closing (better than nothing) is kept for the user to
    edit or delete; stripping it would send a bare draft."""
    if isinstance(default_signature, str) and default_signature.strip():
        return strip_trailing_signoff(body or "")
    return body or ""


def select_draft_message(candidates: List[str]) -> Optional[Dict[str, str]]:
    """Pick the message an "open draft in canvas" click actually means.

    Chat keeps moving after a draft lands ("one more question…"), so the
    LATEST assistant message is often not the draft at all. Given recent
    assistant contents newest-first, return ``{"content", "kind"}`` for the
    most recent message carrying a detectable artifact (email draft, code
    block, table, titled document — see ``detect_draft_kind``); None when
    no candidate carries one — callers fall back to the latest message.
    """
    for candidate in candidates or []:
        kind = detect_draft_kind(candidate)
        if kind:
            return {"content": candidate, "kind": kind}
    return None


# Markdown table separator row ("| --- | --- |"), the structural marker of
# a real table (header + separator + rows).
_TABLE_SEPARATOR = re.compile(r"^\s*\|?[\s:-]*-{3,}[\s:|-]*\|[\s:|-]*$")


def _has_code_block(text: str) -> bool:
    """A fenced code block with at least 3 content lines."""
    parts = text.split("```")
    for block in parts[1::2]:  # text between opening/closing fences
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if len(lines) >= 3:
            return True
    return False


def _has_markdown_table(text: str) -> bool:
    lines = text.splitlines()
    for i in range(len(lines) - 1):
        if "|" in lines[i] and _TABLE_SEPARATOR.match(lines[i + 1]):
            return True
    return False


def _looks_like_titled_document(text: str) -> bool:
    """A standalone titled document: opens with a markdown H1/H2 heading
    and has real body. Conversational answers usually open with prose;
    heading-decorated ANSWERS are why the heading must be leading."""
    stripped = text.lstrip()
    if not stripped.startswith(("# ", "## ")):
        return False
    return len(stripped) >= 200


def detect_draft_kind(content: Any) -> Optional[str]:
    """Classify a chat message by the artifact it carries:
    ``email`` | ``slides`` | ``code`` | ``table`` | ``doc`` | None
    (conversational).

    Ordered by structural strength — an email header block is the
    strongest signal, then a slide outline, fenced code, tables, and
    leading-heading documents. Same conservative rule as the email
    classifier: when in doubt, None (the button falls back to the latest
    message).
    """
    if not isinstance(content, str) or not content.strip():
        return None
    if extract_email_draft(content):
        return "email"
    if _has_slide_outline(content):
        return "slides"
    if _has_code_block(content):
        return "code"
    if _has_markdown_table(content):
        return "table"
    if _looks_like_titled_document(content):
        return "doc"
    return None


# "Slide 3:", "**Slide 3**", "## Slide 3 — Roadmap" — the outline marker.
_SLIDE_LINE = re.compile(r"^\s*(?:#{1,3}\s*|\*\*)?Slide\s+\d+\s*[:.—-]?\s*(.*)$", re.IGNORECASE)


def _has_slide_outline(text: str) -> bool:
    return sum(1 for ln in text.splitlines() if _SLIDE_LINE.match(ln)) >= 2


def extract_slide_outline(text: str) -> List[Dict[str, str]]:
    """Parse a slide-outline draft into ``[{"title", "content"}]``.

    Each "Slide N: Title" (plain, bold, or heading form) starts a slide;
    the lines until the next marker are its body (bullets/prose kept as-is).
    """
    slides: List[Dict[str, str]] = []
    body: List[str] = []

    def flush() -> None:
        if slides:
            slides[-1]["content"] = "\n".join(body).strip()
        body.clear()

    for ln in text.splitlines():
        m = _SLIDE_LINE.match(ln)
        if m:
            flush()
            title = m.group(1).strip().rstrip("*").strip()
            slides.append({"title": title or f"Slide {len(slides) + 1}", "content": ""})
        elif slides:
            body.append(ln.rstrip())
    flush()
    return slides


def markdown_table_rows(text: str) -> Optional[List[List[str]]]:
    """Rows of the first markdown table (header row included), or None.

    Powers the excel path of draft expansion: a chat table becomes a real
    .xlsx office canvas rather than markdown in a document.
    """
    lines = text.splitlines()
    for i in range(len(lines) - 1):
        if "|" in lines[i] and _TABLE_SEPARATOR.match(lines[i + 1]):

            def parse_row(line: str) -> List[str]:
                cells = line.strip().strip("|").split("|")
                return [c.strip() for c in cells]

            rows = [parse_row(lines[i])]
            for follow in lines[i + 2:]:
                if "|" not in follow or not follow.strip():
                    break
                rows.append(parse_row(follow))
            return rows if len(rows) >= 2 else None
    return None


def _draft_text(content: Any) -> Optional[str]:
    """Accept a markdown string or the ``{"type": "doc", "content": str}``
    shape chat_draft_to_canvas stores; anything else is not classifiable."""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        inner = content.get("content")
        if isinstance(inner, str):
            return inner
    return None


def _strip_separators(lines: List[str]) -> List[str]:
    start, end = 0, len(lines)
    while start < end and (not lines[start].strip() or _SEPARATOR_LINE.match(lines[start])):
        start += 1
    while end > start and (not lines[end - 1].strip() or _SEPARATOR_LINE.match(lines[end - 1])):
        end -= 1
    return lines[start:end]


def extract_email_draft(content: Any) -> Optional[Dict[str, str]]:
    """Split an email-shaped draft into ``{"to", "subject", "body"}``.

    Returns None when the content is not an email draft (non-text shapes,
    no header block near the top, or no meaningful body after it).
    """
    text = _draft_text(content)
    if not text or not text.strip():
        return None

    headers: Dict[str, str] = {}
    last_header_idx = -1
    seen_non_empty = 0
    for i, line in enumerate(text.splitlines()):
        if not line.strip() or _SEPARATOR_LINE.match(line):
            continue
        seen_non_empty += 1
        if seen_non_empty > _MAX_HEADER_SCAN_LINES:
            break
        m = _HEADER_LINE.match(line)
        if not m:
            # First non-header line ends the header block — notes/prose
            # before any Subject: line means this is not a pure draft.
            break
        key = m.group(1).lower()
        value = (m.group(2) or "").strip()
        if key == "to":
            headers["to"] = value
        elif key == "cc":
            headers["cc"] = value
        else:
            headers.setdefault("subject", value)
        last_header_idx = i

    if not headers.get("subject"):
        return None

    lines = text.splitlines()
    body = "\n".join(_strip_separators(lines[last_header_idx + 1:])).strip()
    if len(body) < _MIN_BODY_CHARS:
        return None

    return {
        "to": headers.get("to", ""),
        "cc": headers.get("cc", ""),
        "subject": headers["subject"],
        "body": body,
    }


def normalize_email_content(content: Any) -> Dict[str, str]:
    """Normalize any stored email-canvas content into ``{to, subject, body}``.

    Handles the shapes that historically land on email canvases:
    ``{to, subject, body}`` (canvas composer / classifier output — returned
    with defaults filled), ``{"draft": {"to_emails": [...], ...}}``
    (EmailCanvasService.create_email_canvas details), a bare body string,
    and ``{"type": "doc", "content": str}`` doc bodies.
    """
    if isinstance(content, str):
        return {"to": "", "cc": "", "subject": "", "body": content}
    if isinstance(content, dict):
        draft = content.get("draft")
        if isinstance(draft, dict):
            to = draft.get("to_emails")
            cc = draft.get("cc_emails")
            return {
                "to": ", ".join(to) if isinstance(to, list) else str(to or ""),
                "cc": ", ".join(cc) if isinstance(cc, list) else str(cc or ""),
                "subject": str(draft.get("subject") or content.get("subject") or ""),
                "body": str(draft.get("body") or ""),
            }
        body = content.get("body")
        if not isinstance(body, str):
            body = content.get("content") if isinstance(content.get("content"), str) else ""
        return {
            "to": str(content.get("to") or ""),
            "cc": str(content.get("cc") or ""),
            "subject": str(content.get("subject") or ""),
            "body": body,
        }
    return {"to": "", "cc": "", "subject": "", "body": ""}


def coerce_email_canvas(canvas_type: Optional[str], content: Any) -> Tuple[str, Any]:
    """Upgrade email-shaped doc content to a typed email canvas.

    Returns ``(canvas_type, content)``: doc-like canvases whose content is
    an email draft become ``("email", {to, subject, body})``; already-typed
    email canvases with structured content are normalized to the same
    shape; everything else passes through untouched.
    """
    ctype = (canvas_type or "generic").lower()
    if ctype == "email":
        if isinstance(content, dict):
            return "email", normalize_email_content(content)
        return ctype, content
    if ctype in _DOC_LIKE_TYPES:
        draft = extract_email_draft(content)
        if draft:
            return "email", draft
    return canvas_type or "generic", content
