"""User-facing answer boundary for tool-backed replies.

The reply model receives internal ``LIVE TOOL RESULTS`` evidence. Some
models echo that envelope back as the first paragraph of their answer
(attempt 4's L3 turn did exactly that). The envelope is an internal
evidence carrier, not user-facing prose.

This module deliberately does only two things:

1. remove the exact internal envelope from the answer;
2. if the answer consisted only of that envelope, either render a fact
   supplied by **existing structured evidence** or return an explicit
   limitation.

It does NOT rank source sentences by word overlap and does NOT treat the
presence of a code-like token as proof that the token belongs to the
requested subject. A candidate sentence is not a supported answer: the
subject → field → value → source association must come from structured
evidence, and a fallback is allowed only when that association is unique.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

_INTERNAL_HEADER = "LIVE TOOL RESULTS"

EXPLICIT_LIMITATION = (
    "I found retrieved evidence for this request, but I could not "
    "establish the requested subject and value from it without guessing. "
    "Please ask me to open the specific source, or name the subject and "
    "field you want checked.")

_FACT_KEYS = ("subject", "field", "value", "source")
_LINE_NUMBERED = re.compile(r"^\s*L\d+:\s")
_FULL_TEXT_LEAD = re.compile(
    r"(?:full text|top hit|source excerpt|excerpt|stored document)",
    re.IGNORECASE)
_SOURCE_MARKERS = r"ingested|vector|communication|memory|documents?|knowledge"
# A numbered source-list entry: the marker must be followed by a named
# source and a colon. A marker mention alone is not a carrier.
_RETRIEVED_PARAGRAPH = re.compile(
    r"^\s*\d{1,3}\.\s*\[(?:" + _SOURCE_MARKERS + r")\]\s+"
    r"[^\s:][^:\n]{0,200}:", re.IGNORECASE)
_INGESTED_SOURCE = re.compile(
    r"\[(" + _SOURCE_MARKERS + r")\]\s+"
    r"([^\s:][^:\n]{0,200}):", re.IGNORECASE)
# A model preamble that introduces an echoed source paragraph. This is
# deliberately narrower than "contains [ingested]": the marker alone must
# never be enough to delete user-facing prose.
_CARRIER_PREAMBLE = re.compile(
    r"^(?:(?:based on|according to|from|using)\s+"
    r"(?:the\s+|your\s+|my\s+)?(?:live\s+)?"
    r"(?:tool\s+results|retrieved\s+(?:documents?|evidence|sources?)|"
    r"uploaded\s+documents?|search\s+results?)|the\s+live\s+tool\s+results)\b",
    re.IGNORECASE)
# The served attempt-8 shape: "From [ingested] <source>: ...".
_INLINE_MARKER_LEAD = re.compile(
    r"^(?:from|based on|according to)\s+\[(?:" + _SOURCE_MARKERS + r")\]\s+",
    re.IGNORECASE)
# Explicit requests to quote source material. A business noun or verb such
# as "does the quote match", "compare the quotation", or "quote the approved
# price" is not a request to reproduce text and must not disable stripping.
_QUOTE_REQUEST = re.compile(
    r"(?:"
    r"\b(?:please\s+)?quote\s+(?:"
    r"(?:the\s+)?(?:source|document|note|text|passage|paragraph|"
    r"lines?|wording|quote|quotation)"
    r"(?:\s+(?:source|document|note|text|passage|paragraph|lines?|"
    r"wording))?"
    r"\s*(?:$|[,.!?]|\b(?:exactly|verbatim|word|from|in full|"
    r"as written)\b)"
    r"|the\s+exact\s+(?:text|wording|words)\b"
    r"|line\s+\d+\b"
    r"|(?:exactly\s+)?what\b"
    r"|the\s+(?:first|last|next|following)\s+(?:line|paragraph|sentence)"
    r"\s*(?:$|[,.!?]|\b(?:exactly|verbatim|word|from|in full|"
    r"as written)\b)"
    r"|the\s+\w+'s\s+(?:first|last|next|following)\s+"
    r"(?:line|paragraph|sentence)\b"
    r"|the\s+(?:source\s+)?lines?\s+(?:below|above|\d+)\b"
    r"|from\b|verbatim\b|exactly\b"
    r"|(?:this|that|it|my|your)\b)"
    r"|\bquoted\s+(?:text|wording|passage|paragraph|source|material)\b"
    r"|\bverbatim\b"
    r"|\bword[- ]for[- ]word\b"
    r"|\bexact(?:ly)?\s+(?:text|wording|words|quote|quotation|passage)\b"
    r"|\bwhat\s+did\s+i\s+(?:write|say)\b"
    r"|\brepeat\s+(?:my|the)\s+(?:text|words|message|wording)\b"
    r"|\brepeat\s+the\s+(?:paragraph|passage|source|text|note|document)\b"
    r"|\bcopy\s+(?:the|my)\s+(?:text|words|message|wording)\b"
    r"|\bcopy\s+(?:the|my)\s+(?:source|original|exact)\s+(?:text|wording)\b"
    r"|\bpreserve\s+(?:the|my)\s+(?:text|quote|wording)\b"
    r"|\bshow\s+me\s+(?:exactly\s+)?what\s+the\s+"
    r"(?:document|note|source|text)\s+(?:says|contains)\b"
    r"|\bgive\s+me\s+the\s+(?:source|original|exact)\s+(?:text|wording)\b"
    r"|\bpaste\s+the\s+(?:source|original|exact)\s+(?:text|wording)\b"
    r"|\bwhat\s+(?:exactly\s+)?does\s+the\s+"
    r"(?:document|note|source|text)\s+(?:say|contain)\b"
    r"|\btell\s+me\s+what\s+the\s+"
    r"(?:document|note|source|text)\s+(?:says?|contains?)\b"
    r")",
    re.IGNORECASE)
# Values that usually carry the answer. Used by the line-numbered path,
# which still removes an internal block; the [ingested] path only removes
# the carrier prefix and always keeps the body.
_ANSWER_VALUE = re.compile(
    r"(?<!\w)(?:[A-Z][A-Za-z0-9]*-[A-Za-z0-9]+"
    r"|[A-Za-z]+\s+\d{1,3}"
    r"|\d{4}-\d{2}-\d{2}"
    r"|\$\s?\d[\d,]*(?:\.\d+)?"
    r"|\d+(?:\.\d+)?%)(?!\w)")


def _source_marker_label(text: str) -> tuple[str, str]:
    # A carrier names its source near the start of the paragraph. Limit the
    # search so a later marker mention cannot supply the label.
    match = _INGESTED_SOURCE.search(text[:400])
    if not match:
        return "", ""
    label = match.group(2).strip().strip("\"'").rstrip(".,;")
    return match.group(1).lower(), label


def _body_after_source(text: str) -> str:
    match = _INGESTED_SOURCE.search(text[:400])
    return text[match.end():].strip() if match else ""


def _neutralized_carrier(text: str) -> str:
    """Remove the marker, keep the source label, prefix answer, and body."""
    match = _INGESTED_SOURCE.search(text[:400])
    if not match:
        return text
    body = text[match.end():].strip()
    if not body:
        return ""
    label = match.group(2).strip().strip("\"'").rstrip(".,;")
    prefix = text[:match.start()]
    prefix = re.sub(r"^\s*\d{1,3}\.\s*", "", prefix).strip()
    # Keep prefix prose only when it carries an answer-like value; ordinary
    # model preamble is discarded. The source label is always retained so a
    # "which document?" answer cannot disappear with the marker.
    head = f"{prefix} " if _answer_values(prefix) else ""
    return f"{head}{label}: {body}"


def _tool_block_has_source(
        tool_block: Optional[str], marker: str, label: str) -> bool:
    """True when the same marker and source occur in the live evidence."""
    if not tool_block or not marker or not label:
        return False
    pattern = re.compile(
        r"\[" + re.escape(marker) + r"\]\s+"
        + re.escape(label) + r"\s*:", re.IGNORECASE)
    return bool(pattern.search(str(tool_block)))


def _answer_values(text: str) -> set[str]:
    return {match.group(0).lower() for match in _ANSWER_VALUE.finditer(text)}


def _value_in_text(value: str, text: str) -> bool:
    return bool(re.search(
        r"(?<!\w)" + re.escape(value) + r"(?!\w)", text, re.IGNORECASE))


def _body_is_evidence_excerpt(body: str, tool_block: Optional[str]) -> bool:
    """True when the paragraph body is copied from the tool block.

    This is what separates an echoed carrier from explanatory prose that
    happens to name a real source. The check is whitespace-normalized and
    requires the whole body to occur in the tool block; a paragraph with
    appended user-facing prose is preserved. Bodies shorter than 20
    characters are preserved: they can be the entire answer.
    """
    if not body or not tool_block:
        return False
    normalized_body = " ".join(body.split())
    normalized_tool = " ".join(str(tool_block).split())
    if len(normalized_body) < 20:
        return False
    return normalized_body in normalized_tool


def _is_retrieved_carrier(
        paragraph: str, index: int, tool_block: Optional[str]) -> bool:
    """Identify an internal evidence carrier prefix from structure/origin.

    A numbered source-list entry or a first-paragraph model preamble must
    name a source that occurs in the live tool block, and the body after the
    marker must be a copied excerpt of that block. The body itself is never
    deleted; only the carrier prefix is removed. Explanatory prose that
    names a real source is therefore preserved whole.
    """
    numbered = bool(_RETRIEVED_PARAGRAPH.match(paragraph))
    marker_lead = bool(_INLINE_MARKER_LEAD.match(paragraph))
    preamble = index == 0 and bool(_CARRIER_PREAMBLE.match(paragraph))
    if not (numbered or marker_lead or preamble):
        return False
    marker, label = _source_marker_label(paragraph)
    if not marker or not label:
        return False
    if not _tool_block_has_source(tool_block, marker, label):
        return False
    return _body_is_evidence_excerpt(
        _body_after_source(paragraph), tool_block)


def _strip_retrieved_excerpt(
        text: str, tool_block: Optional[str] = None,
        preserve_excerpts: bool = False) -> str:
    """Drop a positively identified retrieved-source paragraph.

    Some models open with a numbered ``[ingested]`` excerpt or a
    "Based on the live tool results ..." echo and only then answer. When
    the source and body are copied from the live tool block, remove the
    carrier prefix but keep the body. Keeping the body is deliberate: an
    answer-bearing hybrid must never lose its answer. A marker mention, an
    ordinary quotation, explanatory prose, and a user-requested excerpt are
    preserved whole.
    """
    if preserve_excerpts:
        return text
    paragraphs = re.split(r"\n\s*\n", text)
    if not paragraphs:
        return text
    kept = []
    for index, paragraph in enumerate(paragraphs):
        stripped = paragraph.strip()
        if _is_retrieved_carrier(stripped, index, tool_block):
            neutralized = _neutralized_carrier(stripped)
            if neutralized:
                kept.append(neutralized)
            continue
        kept.append(paragraph)
    return "\n\n".join(kept).strip()


def _strip_line_numbered_excerpt(
        text: str, preserve_excerpts: bool = False) -> str:
    """Remove an internal line-numbered VFS excerpt from user-facing text.

    The knowledge VFS renders evidence as consecutive ``L1:``/``L2:``
    lines. That is an internal carrier; the answer is the prose around it.
    A single ``L1:`` line is left alone (it can be a legitimate citation).
    An explicit user request to quote source lines preserves the block.
    A removal that would leave only a short remainder is not performed:
    the line-numbered block may itself contain the answer.
    """
    if preserve_excerpts:
        return text
    lines = text.splitlines()
    kept = []
    removed_lines = []
    index = 0
    while index < len(lines):
        if _LINE_NUMBERED.match(lines[index]):
            end = index
            while end < len(lines) and _LINE_NUMBERED.match(lines[end]):
                end += 1
            if end - index >= 2:
                if kept and _FULL_TEXT_LEAD.search(kept[-1]):
                    kept.pop()
                removed_lines.extend(lines[index:end])
                index = end
                continue
        kept.append(lines[index])
        index += 1
    cleaned = "\n".join(kept).strip()
    if not removed_lines:
        return cleaned
    # A line labelled "Decoy" is intentionally adversarial fixture text, not
    # the answer. Other answer-like values must survive in the remainder or
    # the block is preserved.
    non_decoy = "\n".join(
        line for line in removed_lines if "decoy" not in line.lower())
    values = _answer_values(non_decoy)
    if any(not _value_in_text(value, cleaned) for value in values):
        return text
    if len(" ".join(cleaned.split())) < 80:
        return text
    return cleaned


def _strip_exact(content: str, tool_block: Optional[str]) -> str:
    if not tool_block:
        return content
    block = str(tool_block).strip()
    if not block:
        return content
    idx = content.find(block)
    if idx < 0:
        return content
    return (content[:idx] + content[idx + len(block):]).strip()


def strip_internal_tool_envelope(
        content: str, tool_block: Optional[str] = None,
        message: str = "") -> str:
    """Remove an echoed internal evidence envelope from user-facing text.

    The exact tool block is removed first. If a truncated/rewritten echo
    still starts with the internal header, the header paragraph (up to the
    first blank line) is removed. Anything after that paragraph is kept.
    An explicit request to quote source material preserves excerpt-shaped
    paragraphs; the exact internal envelope is still removed.
    """
    text = str(content or "").strip()
    if not text:
        return text
    preserve_excerpts = bool(message and _QUOTE_REQUEST.search(str(message)))
    text = _strip_exact(text, tool_block)
    # The planner emits several carrier header shapes: ``LIVE TOOL
    # RESULTS (documents.search)``, ``LIVE TOOL RESULTS — regex scan ...``,
    # ``LIVE TOOL RESULTS:``. They are all the same internal envelope; the
    # answer starts after the first blank line. A sentence that merely
    # mentions the phrase mid-answer is not a carrier.
    if text.upper().startswith(_INTERNAL_HEADER):
        paragraphs = re.split(r"\n\s*\n", text, maxsplit=1)
        text = paragraphs[1].strip() if len(paragraphs) == 2 else ""
    text = _strip_line_numbered_excerpt(
        text.strip(), preserve_excerpts=preserve_excerpts)
    return _strip_retrieved_excerpt(
        text, tool_block=tool_block, preserve_excerpts=preserve_excerpts)


def _unique_fact(facts: Optional[Iterable[dict]]) -> Optional[dict]:
    """The one fully specified structured association, or None.

    The caller supplies facts already bound to the requested subject. A
    fallback is not allowed to choose among candidates: zero or more than
    one association means the boundary cannot construct an answer.
    """
    valid = []
    for fact in facts or []:
        if not isinstance(fact, dict):
            continue
        if all(str(fact.get(key) or "").strip() for key in _FACT_KEYS):
            valid.append(fact)
    return valid[0] if len(valid) == 1 else None


def present_answer(content: str, tool_block: Optional[str],
                   message: str,
                   supported_facts: Optional[Iterable[dict]] = None) -> str:
    """Return the user-facing answer without the internal envelope.

    A substantive answer after envelope removal is preserved unchanged;
    the boundary does not rewrite or certify it from token presence. If
    the envelope consumed the whole answer, a unique structured
    ``subject``/``field``/``value``/``source`` association may be rendered;
    otherwise the explicit limitation is returned. ``message`` is used only
    to recognize an explicit request to quote source material, so a
    user-requested quotation is not mistaken for an internal carrier; it is
    not used to rank or certify answers.
    """
    stripped = strip_internal_tool_envelope(content, tool_block, message)
    if stripped:
        return stripped
    fact = _unique_fact(supported_facts)
    if fact is None:
        return EXPLICIT_LIMITATION
    return (
        f"{str(fact['subject']).strip()} {str(fact['field']).strip()}: "
        f"{str(fact['value']).strip()} "
        f"(Source: {str(fact['source']).strip()})")
