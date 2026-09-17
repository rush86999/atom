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
    planned lookup query against the current user message."""
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
    if strong_hits:
        return "relevant"

    overlap = msg_tokens & query_tokens
    if len(overlap) >= 2:
        return "relevant"
    # Short asks ("price of WG-350?") share one word legitimately — the
    # hyphenated code may be re-tokenized in the query ("wg 350 price").
    if len(overlap) >= 1 and len(msg_tokens) <= 4:
        return "relevant"
    # A message this short with zero overlap carries too little signal to
    # judge ("hi", "ok thanks") — fail open rather than decline.
    if not overlap and len(msg_tokens) <= 2:
        return "unknown"
    return "irrelevant"
