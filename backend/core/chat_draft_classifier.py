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

# Narration-tolerant rescan: how many ---fenced segments to try, and the
# fake separator line used to flush the final segment after the loop (must
# match _SEPARATOR_LINE).
_MAX_SEGMENT_SCAN = 4
_SEPARATOR_SENTINEL = "-" * 80

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


def select_draft_message(candidates: List[Any]) -> Optional[Dict[str, Any]]:
    """Pick the message an "open draft in canvas" click actually means.

    Chat keeps moving after a draft lands ("one more question…"), so the
    LATEST assistant message is often not the draft at all. Given recent
    assistant messages newest-first — each a bare content string, or an
    ``{"id", "content"}`` dict so the chosen message can be identified in
    the UI — return ``{"content", "kind", "message_id"?}`` for the most
    recent DRAFT-SHAPED message; None when no candidate qualifies — callers
    fall back to the latest message.

    Qualifying is stricter than ``detect_draft_kind``: a conversational
    ANSWER routinely *contains* a code snippet or a comparison table, and
    being newer than the real draft it would win the newest-first scan and
    the canvas would open the wrong message (observed live). So code/table
    candidates count only when the artifact DOMINATES the message (drafts
    are mostly artifact, answers are mostly prose); email, slides, and
    leading-heading documents are draft-shaped by construction.
    """
    for candidate in candidates or []:
        message_id: Any = None
        if isinstance(candidate, dict):
            message_id = candidate.get("id")
            content = candidate.get("content")
        else:
            content = candidate
        if not isinstance(content, str):
            continue
        kind = detect_draft_kind(content)
        if not kind:
            continue
        if kind in ("email", "slides", "doc") or _artifact_dominates(content, kind):
            selected: Dict[str, Any] = {"content": content, "kind": kind}
            if message_id is not None:
                selected["message_id"] = message_id
            return selected
    return None


# A draft IS the artifact with a line or two of framing; an answer is prose
# that happens to embed one. 2:1 keeps real drafts ("Here's the script:" +
# 20 code lines) while rejecting snippet-bearing replies.
_DOMINANCE_RATIO = 2


def _nonempty_lines(text: str) -> int:
    return sum(1 for ln in text.splitlines() if ln.strip())


def _artifact_dominates(text: str, kind: str) -> bool:
    """Whether the code/table artifact outweighs the surrounding prose.

    Code: all fenced-block lines vs everything outside the fences. Table:
    the first table block's lines (header + separator + rows) vs the rest
    of the message.
    """
    if kind == "code":
        parts = text.split("```")
        artifact = sum(_nonempty_lines(part) for part in parts[1::2])
        prose = sum(_nonempty_lines(part) for part in parts[0::2])
    elif kind == "table":
        lines = text.splitlines()
        artifact, start = 0, -1
        for i in range(len(lines) - 1):
            if "|" in lines[i] and _TABLE_SEPARATOR.match(lines[i + 1]):
                start = i
                artifact = 2  # header + separator
                for follow in lines[i + 2:]:
                    if "|" not in follow or not follow.strip():
                        break
                    artifact += 1
                break
        if not artifact:
            return False
        prose = sum(
            1 for j, ln in enumerate(lines)
            if ln.strip() and not (start <= j < start + artifact)
        )
    else:
        return False
    return artifact >= max(3, _DOMINANCE_RATIO * prose)


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


_BR_TAG = re.compile(r"<br\s*/?>", re.IGNORECASE)


def _draft_text(content: Any) -> Optional[str]:
    """Accept a markdown string or the ``{"type": "doc", "content": str}``
    shape chat_draft_to_canvas stores; anything else is not classifiable.

    HTML-ish bodies are normalized first: the email composer stores ``<br>``
    line breaks (observed in the live incident's canvas body), and header
    extraction is line-based — without this the entire draft is ONE line and
    the To/Subject headers can never be lifted into the structured fields."""
    if isinstance(content, str):
        text = content
    elif isinstance(content, dict):
        inner = content.get("content")
        if not isinstance(inner, str):
            return None
        text = inner
    else:
        return None
    if "<br" in text.lower():
        text = _BR_TAG.sub("\n", text)
    return text


def _strip_separators(lines: List[str]) -> List[str]:
    start, end = 0, len(lines)
    while start < end and (not lines[start].strip() or _SEPARATOR_LINE.match(lines[start])):
        start += 1
    while end > start and (not lines[end - 1].strip() or _SEPARATOR_LINE.match(lines[end - 1])):
        end -= 1
    return lines[start:end]


def _scan_header_block(lines: List[str]) -> Tuple[Dict[str, str], int]:
    """Scan a line list for a leading RFC 5322-style header block.

    Returns ``(headers, last_header_idx)`` where ``last_header_idx`` is the
    index of the final header line (-1 when no Subject header was found).
    The first non-header non-empty line ends the block: notes/prose before
    any Subject: line means this line list does not open with a draft.
    """
    headers: Dict[str, str] = {}
    last_header_idx = -1
    seen_non_empty = 0
    for i, line in enumerate(lines):
        if not line.strip() or _SEPARATOR_LINE.match(line):
            continue
        seen_non_empty += 1
        if seen_non_empty > _MAX_HEADER_SCAN_LINES:
            break
        m = _HEADER_LINE.match(line)
        if not m:
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
    return headers, last_header_idx


def _extract_from_lines(lines: List[str], start: int, headers: Dict[str, str]) -> Optional[Dict[str, str]]:
    """Build the draft dict from a header block found at ``lines[start:end]``."""
    body = "\n".join(_strip_separators(lines[start + 1:])).strip()
    if len(body) < _MIN_BODY_CHARS:
        return None
    return {
        "to": headers.get("to", ""),
        "cc": headers.get("cc", ""),
        "subject": headers.get("subject", ""),
        "body": body,
    }


def extract_email_draft(content: Any) -> Optional[Dict[str, str]]:
    """Split an email-shaped draft into ``{"to", "cc", "subject", "body"}``.

    Returns None when the content is not an email draft (non-text shapes,
    no header block near the top, or no meaningful body after it).

    Narration-tolerant: chat replies usually wrap the draft in prose
    ("I found the email for X... Here's the draft:") fenced by ``---``
    separators — observed live as a seeded canvas whose Subject field held
    a truncated narration sentence and whose To/Cc stayed empty even though
    the draft carried ``**To:** jschulz@…``. When the top-of-message scan
    finds no header block, each ``---``-separated segment is rescanned (the
    draft lives between the fences), so a header block after narration is
    still lifted into the structured fields and the surrounding commentary
    stays out of the body.
    """
    text = _draft_text(content)
    if not text or not text.strip():
        return None

    lines = text.splitlines()
    headers, last_header_idx = _scan_header_block(lines)
    if headers.get("subject"):
        draft = _extract_from_lines(lines, last_header_idx, headers)
        if draft:
            return draft

    # Narration-tolerant rescan: try each ---fenced segment (the draft is
    # between the fences; prose and approval trailers live outside them).
    segment: List[str] = []
    segments_scanned = 0
    for line in list(lines) + [_SEPARATOR_SENTINEL]:
        if _SEPARATOR_LINE.match(line):
            if segments_scanned >= _MAX_SEGMENT_SCAN:
                break
            segments_scanned += 1
            seg_headers, seg_idx = _scan_header_block(segment)
            if seg_headers.get("subject"):
                draft = _extract_from_lines(segment, seg_idx, seg_headers)
                if draft:
                    return draft
            segment = []
        else:
            segment.append(line)
    return None


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
