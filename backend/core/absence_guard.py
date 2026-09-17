"""Universal absence claims, and whether this turn's lookups cover them.

RCA 2026-09-17 answer-quality defects: a mailbox search for PRICE VIPUL
became "No file with that name exists in the system", and "None that we
sent" silently narrowed the user's scope to external recipients. A reply
may only assert absence about the scope it actually searched — this module
detects the universal phrasing and checks the delivered evidence block for
coverage, so the orchestrator can demand a scoped, honest restatement.

Direction semantics are part of the correction: an internal forward IS
sent by its sender, and one matching hit never proves no other match
exists.
"""

import re
from typing import List

from core.plan_relevance import content_tokens

#: Executed-lookup markers a LIVE evidence block carries. A block without
#: any of these (a failure note, a decline, empty) covers nothing.
_COVERAGE_MARKERS = (
    "LIVE TOOL RESULTS",
    "SEARCH RESULTS",
    "SQL RESULT",
    "FORMULAS FOR THE MATCHED ROW",
    "HISTORICAL CORRESPONDENCE",
    "FRESH DATA",
    "ingested mailbox",
)

#: Universal absence phrasings. Each pattern captures nothing; the
#: SENTENCE carrying the match is the claim (that is what the reply must
#: rescope). Kept to clear universal forms — hedged phrasing ("I could not
#: find", "no results in the CRM search") is honest already and must not
#: trip a regeneration.
_ABSENCE_RES: List[re.Pattern] = [
    # "No file with that name exists in the system", "no matching records"
    re.compile(r"\bno\s+(?:\w+\s+){0,4}?(?:such|matching)\b", re.IGNORECASE),
    # "no emails/documents/files/records ... (exist|found|in the system)"
    re.compile(
        r"\bno\s+(?:\w+\s+){0,3}?"
        r"(?:emails?|e-?mails?|files?|documents?|records?|messages?|"
        r"attachments?|workbooks?|spreadsheets?|scorecards?|quotes?)\b"
        r"[^.!?]{0,60}?\b(?:exists?|exist|found|in the system|available)\b",
        re.IGNORECASE),
    # "None that we sent", "nothing was attached", "neither was received"
    re.compile(
        r"\b(?:none|nothing|neither)\b[^.!?]{0,60}?\b"
        r"(?:was|were|has been|have been)?\s*"
        r"(?:sent|found|received|attached|uploaded|forwarded)\b",
        re.IGNORECASE),
    # "does not exist / doesn't exist"
    re.compile(r"\bdoes\s?not\s+exist\b|\bdoesn'?t\s+exist\b", re.IGNORECASE),
    # "I found no ..." / "no results found"
    re.compile(r"\bfound\s+no\b|\bno\s+results\b", re.IGNORECASE),
]

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_MAX_CLAIMS = 3


def universal_absence_claims(reply: str) -> List[str]:
    """Sentences in ``reply`` that assert absence universally, capped at
    ``_MAX_CLAIMS``. Empty list = nothing to guard."""
    if not reply:
        return []
    out: List[str] = []
    for sentence in _SENTENCE_SPLIT_RE.split(reply):
        if len(out) >= _MAX_CLAIMS:
            break
        if not sentence:
            continue
        for pat in _ABSENCE_RES:
            if pat.search(sentence):
                out.append(sentence.strip()[:200])
                break
    return out


def _claims_covered(claim: str, tool_block: str) -> bool:
    """True when the delivered evidence block represents an executed
    lookup whose text plausibly names the claim's subject."""
    if not tool_block:
        return False
    if not any(m in tool_block for m in _COVERAGE_MARKERS):
        return False
    claim_tokens = content_tokens(claim)
    if not claim_tokens:
        return True  # nothing specific asserted; cannot call it uncovered
    block_tokens = content_tokens(tool_block[:4000])
    return bool(claim_tokens & block_tokens)


def uncovered_absence_claims(reply: str, tool_block: str) -> List[str]:
    """Absence claims this turn's evidence does NOT cover — the ones the
    reply may not ship as written."""
    return [c for c in universal_absence_claims(reply)
            if not _claims_covered(c, tool_block)]


def absence_correction_message(claims: List[str],
                               sources_block: str = "") -> str:
    """The corrective system message for uncovered absence claims."""
    cited = " ".join(claims[:2])
    msg = (
        "ABSENCE CLAIM NOT COVERED BY THIS TURN'S LOOKUPS: your reply stated "
        f"\"{cited}\". The evidence retrieved this turn does not verify that "
        "absence, so regenerate the SAME answer with the claim scoped to what "
        "was actually checked — e.g. \"I did not find one in <what this turn "
        "searched>\" — and never as a universal statement about the system. "
        "Two scope rules: an internal forward is still SENT by its sender, so "
        "do not narrow \"we sent\" to external recipients only; and finding "
        "one match never proves no other match exists. Do not claim a file or "
        "record does not exist."
    )
    if sources_block:
        msg += f" {sources_block}"
    return msg
