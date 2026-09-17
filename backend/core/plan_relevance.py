"""Does a planned lookup actually address the user's CURRENT request?

RCA 2026-09-17 finding 2 (canvas a1a13834): the planner answered an OLD
request — the final scorecard turn executed ``outlook.search "PRICE VIPUL
price list attachment"`` and its result was accepted as this turn's
evidence. Prevention upstream (transcript labels) lives in the planner;
this module is the acceptance gate: whatever a leg PLANS to execute (or
reuses) must name something the current message names.

Deliberately conservative — a false "irrelevant" declines good evidence,
so the verdict is IRRELEVANT only when the overlap is ZERO-shaped: no
strong identifier of the message (numbers, codes, quoted phrases) appears
in the query AND fewer than two ordinary content words are shared. A query
that is absent or token-free is "unknown" (fail-open): intents like
documents.read can carry their target in kwargs rather than the query.
"""

import re
from typing import List, Set

#: Pure function words only — content words (price, scorecard, vendor) must
#: survive or the overlap test has nothing to overlap.
_STOPWORDS = frozenset({
    "the", "a", "an", "of", "in", "on", "for", "to", "and", "or", "is",
    "are", "was", "were", "be", "been", "being", "with", "about", "as",
    "at", "by", "from", "that", "this", "these", "those", "it", "its",
    "me", "my", "we", "our", "you", "your", "i", "do", "does", "did",
    "can", "could", "would", "should", "will", "shall", "may", "might",
    "up", "out", "into", "over", "under", "again", "then", "than", "so",
    "too", "very", "just", "now", "also", "please", "find", "search",
    "look", "show", "tell", "give", "get", "need", "want", "check",
    "see", "us", "via", "per", "if", "when", "where", "how", "what",
    "which", "who", "there", "here",
})

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9._+\-]*")
_QUOTED_RE = re.compile(r"[\"'“”‘’]([^\"'“”‘’]{3,80})[\"'“”‘’]")
_ALLCAPS_RE = re.compile(r"\b[A-Z]{2,}\d*\b")


def content_tokens(text: str) -> Set[str]:
    """Lowercase content words of ``text`` — minus stopwords, single
    characters, and bare 1-digit numbers."""
    out: Set[str] = set()
    for tok in _TOKEN_RE.findall((text or "").lower()):
        if tok in _STOPWORDS or len(tok) < 2:
            continue
        if tok.isdigit() and len(tok) < 2:
            continue
        out.add(tok)
    return out


def strong_tokens(text: str) -> Set[str]:
    """Identifiers a query must honor to claim it addresses the ask:
    numbers with a decimal or 3+ digits (0.87, 7519), codes with digits
    or hyphens (wg-350dsav, r235), and ALL-CAPS words (RFQ, VIPUL)."""
    out: Set[str] = set()
    lowered = (text or "").lower()
    for tok in _TOKEN_RE.findall(lowered):
        if any(ch.isdigit() for ch in tok) and (
                "." in tok or "-" in tok or len(tok) >= 3):
            out.add(tok)
    for m in _ALLCAPS_RE.findall(text or ""):
        out.add(m.lower())
    return out


def quoted_phrases(text: str) -> List[str]:
    """Quoted spans, normalized for substring matching."""
    return [" ".join(m.group(1).split()).lower()
            for m in _QUOTED_RE.finditer(text or "")]


def relevance_verdict(query: str, message: str) -> str:
    """``relevant`` | ``irrelevant`` | ``unknown`` (fail-open) for a
    planned lookup query against the current user message.

    Review R4 (2026-09-17) fixed three defects here. The verdict is consulted by
    the planner AND re-run by the editor/chat gates, so a wrong ``irrelevant``
    BLOCKS valid work — the more damaging direction, and the one the rules below
    are shaped around.

    1. REFERENTIAL REQUESTS. "Open the attachment from that email you just found"
       names its target by anaphora; the referent is in the conversation, not the
       sentence, so lexical matching cannot see it and returned ``irrelevant`` —
       blocking a lookup the planner had already validated by provenance. Such a
       message is ``unknown`` (inspect/replan), never ``irrelevant``.
    2. A SHARED NUMBER IS NOT A SHARED SUBJECT. ``strong_tokens`` alone accepted
       "PRICE VIPUL 0.87" for "what is the vendor scorecard reliability 0.87"
       purely because both contain 0.87. A strong token now needs corroboration
       from a content word — unless the message is nothing BUT the identifier
       ("show me row 235"), where the identifier is the subject.
    3. Ambiguous lexical signal (some overlap, not enough) is ``unknown`` rather
       than ``irrelevant``: insufficient evidence to accept is not proof of
       mismatch.
    """
    if not query or not str(query).strip():
        return "unknown"
    q_norm = " ".join(str(query).lower().split())
    msg_tokens = content_tokens(message)
    if not msg_tokens:
        return "unknown"
    query_tokens = content_tokens(q_norm)

    for phrase in quoted_phrases(message):
        if phrase in q_norm:
            return "relevant"

    strong_hits = strong_tokens(message) & query_tokens
    overlap = msg_tokens & query_tokens

    # (1) A referential message cannot be judged lexically. Checked BEFORE the
    # identifier shortcut so an anaphoric ask is never declined for lacking
    # terms it resolves elsewhere.
    if _REFERENTIAL_RE.search(str(message or "")):
        return "unknown"

    # (2) An identifier must be corroborated by a content word.
    if strong_hits and (overlap - strong_hits):
        return "relevant"
    if strong_hits and len(msg_tokens) <= 2:
        return "relevant"

    if len(overlap) >= 2:
        return "relevant"
    # Short asks ("price of WG-350?") share one word legitimately — the
    # hyphenated code may be re-tokenized in the query ("wg 350 price").
    if len(overlap) >= 1 and len(msg_tokens) <= 4 and not strong_hits:
        return "relevant"
    # A message this short with zero overlap carries too little signal to
    # judge ("hi", "ok thanks") — fail open rather than decline.
    if not overlap and len(msg_tokens) <= 2:
        return "unknown"
    # (3) Some signal but not enough to accept: hand it back to the caller.
    if overlap:
        return "unknown"
    if strong_hits:
        # An identifier with no `msg_tokens` branch above means the message had
        # nothing else to corroborate it with — still inspect rather than decline.
        return "unknown"
    # A SHARED FIGURE IS A SHARED TARGET. "FW: RFQ - Foot shear" and "search for
    # this one: $ 5,350.00 - 10 % in stock" share no WORD, but 5,350 is exactly
    # what identifies the message — the quoted-body-to-subject mapping the planner
    # already exempts from its own lexical check. Digit runs are compared, not the
    # whole decorated token, so "5,350.00" and "5350" agree.
    if _digit_runs(message) & _digit_runs(query):
        return "unknown"
    # NO shared signal at all: the query and the request are about different
    # subjects, which is the one case lexical evidence can settle.
    return "irrelevant"


def _digit_runs(text: str) -> Set[str]:
    """Digit sequences of 3+ characters (figures and codes)."""
    return {
        run for run in re.findall(r"\d{3,}", str(text or "").replace(",", ""))
    }


#: Language that points at something ALREADY IN THE CONVERSATION. Must not match
#: an ordinary definite article — "what is the weather in Paris" contains a
#: "the"-noun pair and is not referential (that over-broad first version made
#: every such message `unknown` and broke nine of the module's own tests).
_REFERENTIAL_RE = re.compile(
    # a deictic determiner with a document noun: "that email", "those files"
    r"\b(?:that|those|these|same|previous|earlier|above|last)\s+"
    r"(?:email|e-mail|message|thread|attachment|file|document|workbook|sheet|"
    r"spreadsheet|invoice|quote|record|result|one)s?\b"
    # "the one/ones" is referential; "the email you just found" too
    r"|\bthe\s+ones?\b"
    r"|\b(?:the|that|this)\s+(?:email|e-mail|message|thread|attachment|file|"
    r"document|workbook|invoice|quote|record|result)s?\s+"
    r"(?:you|we|i|he|she|they)\b"
    r"|\b(?:you|we)\s+(?:just\s+)?(?:found|opened|mentioned|sent)\b"
    r"|\bas\s+(?:above|before|mentioned)\b",
    re.IGNORECASE,
)
