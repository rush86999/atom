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
    # datasets.find_all: an EXACT-COUNT scan over every cell — the strongest
    # scoped-absence evidence the catalog can produce (0 matches over a
    # complete scan proves the value is in no cell of what was scanned).
    "FIND ALL RESULTS",
)

#: Data/document verbs through which absence is asserted (2026-09-21 review
#: follow-up): "the workbook CONTAINS no sheet", "no email MENTIONS it",
#: "the attachment DOES NOT CONTAIN any clause". FIND and MATCH are
#: deliberately absent from the do-support form — "I did not find one" and
#: "the search did not match any rows" report the SEARCH's own behaviour,
#: which is the honest, already-scoped form.
_DATA_VERBS = (
    r"(?:contain(?:s|ed)?|includ(?:e|es|ed)|mention(?:s|ed)?|"
    r"holds?|held|shows?|showed|shown|lists?|listed)"
)

#: Universal absence phrasings. Each pattern captures nothing; the
#: SENTENCE carrying the match is the claim (that is what the reply must
#: rescope). Kept to clear universal forms — hedged phrasing ("I could not
#: find", "no results in the CRM search") is honest already and must not
#: trip a regeneration.
_ABSENCE_RES: List[re.Pattern] = [
    # "No file with that name exists in the system", "no matching records"
    re.compile(r"\bno\s+(?:\w+\s+){0,4}?(?:such|matching)\b", re.IGNORECASE),
    # "no spreadsheet cell contains X" / "no cells hold that value" — the
    # find_all phrasing (2026-09-20): absence asserted through a verb, which
    # none of the exist/found forms catch.
    re.compile(
        r"\bno\s+(?:\w+\s+){0,3}?cells?\b[^.!?]{0,60}?"
        r"\b(?:contain|contains|held|hold|holds|has|have|mention|mentions|"
        r"include|includes)\b",
        re.IGNORECASE),
    # "no emails/documents/files/records ... (exist|found|matched|mention...)"
    re.compile(
        r"\bno\s+(?:\w+\s+){0,3}?"
        r"(?:emails?|e-?mails?|files?|documents?|records?|messages?|"
        r"attachments?|workbooks?|spreadsheets?|scorecards?|quotes?)\b"
        r"[^.!?]{0,60}?\b(?:exists?|exist|found|in the system|available|"
        r"match(?:es|ed)?|" + _DATA_VERBS + r")\b",
        re.IGNORECASE),
    # "the workbook contains/holds/shows no X", "holds none of ..." —
    # absence through a data verb BEFORE the 'no' (2026-09-21): "PRICE VIPUL
    # contains no scorecard sheet" matched none of the no-noun forms above,
    # so that exact RCA over-claim shape shipped unguarded.
    re.compile(r"\b" + _DATA_VERBS + r"\s+(?:no|none)\b", re.IGNORECASE),
    # "the attachment does not contain/mention any X" — the do-support shape
    # of the same verb-mediated absence (find/match excluded on purpose).
    re.compile(
        r"\b(?:does|do|did|has|have|had)\s?(?:not|n'?t)\s+"
        + _DATA_VERBS + r"\b",
        re.IGNORECASE),
    # "no OTHER …", "no further …" — an explicit completeness claim about a set.
    # Review R2 (2026-09-17): "No other email carried it." was not recognised at
    # all, so the guard never examined it — an absence claim reaching no detector
    # is indistinguishable from a covered one.
    re.compile(
        r"\bno\s+(?:other|further|additional|more)\b",
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


#: The lookup did NOT complete, so it cannot support an absence claim at all.
#: Covering a universal negative requires a search that FINISHED over the whole
#: scope; these say it did not.
_INCOMPLETE_COVERAGE_RE = re.compile(
    r"\b(failed|failure|error|denied|permission|unauthori[sz]ed|forbidden|"
    r"timed? ?out|timeout|aborted|could not (?:complete|run|search|reach)|"
    r"unavailable|not attempted|no lookup was attempted)\b",
    re.IGNORECASE,
)

#: Evidence says the search was PARTIAL or there is more to read — a page
#: boundary, truncation, or a next-page cursor. A first page cannot establish
#: that something exists nowhere.
_PARTIAL_COVERAGE_RE = re.compile(
    r"(next_page_token|next page|has_more|more rows matched|first page only|"
    r"truncated|\.\.\.\s*\d+ more|page \d+ of \d+|partial|incomplete)",
    re.IGNORECASE,
)

#: Evidence contains at least one actual RESULT — a positive hit contradicts an
#: absence claim about the same subject outright.
_POSITIVE_HIT_RE = re.compile(
    r"\b(\d+)\s+(?:result|match|hit|row|message)s?\b", re.IGNORECASE
)


def _claims_covered(claim: str, tool_block: str) -> bool:
    """True only when the evidence SUPPORTS an absence claim over its scope.

    R2 (review 2026-09-17). The previous version accepted any block carrying a
    coverage marker plus ONE shared content token, so:

      * "The vendor scorecard workbook does not exist" passed against evidence
        reading "first page only; 1 result; next_page_token=abc" — a POSITIVE hit
        and an explicitly partial search;
      * "No file with that name exists in the system." passed against "file search
        failed with permission denied".

    Sharing a word proves neither absence nor exhaustiveness. Coverage is now
    derived from what the evidence says about the LOOKUP: it must have produced
    results without reporting a failure, and must not report itself as partial.
    Anything else — failed, denied, timed out, truncated, more pages, or nothing
    that positively establishes completion — is INCONCLUSIVE, which is the safe
    direction: an inconclusive lookup cannot license a universal negative.
    """
    if not tool_block:
        return False
    if not any(m in tool_block for m in _COVERAGE_MARKERS):
        return False
    block = tool_block[:4000]
    # A failed/denied/timed-out lookup cannot support absence.
    if _INCOMPLETE_COVERAGE_RE.search(block):
        return False
    # A partial page or a continuation cursor cannot support absence.
    if _PARTIAL_COVERAGE_RE.search(block):
        return False
    claim_tokens = content_tokens(claim)
    if not claim_tokens:
        return True  # nothing specific asserted; cannot call it uncovered
    # content_tokens keeps _TOKEN_RE's edge characters, so a sentence-final
    # subject arrives as "rfq." while the evidence names "rfq" — an honest,
    # covered answer would be flagged purely on punctuation. Strip token-EDGE
    # punctuation on both sides (internal dots/dashes — "0.87", "wg-350" —
    # are untouched).
    claim_tokens = {t.strip("._+-") for t in claim_tokens}
    claim_tokens.discard("")
    block_tokens = {t.strip("._+-")
                    for t in content_tokens(block)}
    block_tokens.discard("")
    if not (claim_tokens & block_tokens):
        return False  # the evidence never speaks to this subject
    # A positive hit ABOUT THE CLAIM'S SUBJECT contradicts absence. "No other X"
    # against evidence that found exactly one X is not an over-scope negative —
    # it is contradicted by the result, so the guard must catch it (review R2).
    if re.search(r"\bno\s+(?:other|further|additional|more)\b", claim, re.IGNORECASE):
        return False
    hit = _POSITIVE_HIT_RE.search(block)
    if hit and int(hit.group(1)) > 0:
        # A hit is only exculpatory if the evidence does not speak to this claim's
        # subject; when the subject matches, a positive result refutes absence.
        return False
    return True


def uncovered_absence_claims(reply: str, tool_block: str) -> List[str]:
    """Absence claims this turn's evidence does NOT cover — the ones the
    reply may not ship as written."""
    return [c for c in universal_absence_claims(reply)
            if not _claims_covered(c, tool_block)]


#: The deterministic last resort. It must itself be honest AND must not trip
#: the absence detectors (checked against every _ABSENCE_RES pattern), or the
#: guard would re-flag its own fallback and loop.
_SCOPED_LIMITATION = (
    "I did not find one in what this turn actually searched, and I can't "
    "rule out places that were not searched.")


def strip_uncovered_absence_claims(reply: str, tool_block: str) -> str:
    """Deterministic last resort: replace each uncovered universal absence
    sentence with a scoped limitation.

    The corrective regeneration is best-effort — the provider can 401,
    time out, or RETURN ANOTHER over-claim. The invariant (no unsupported
    universal absence ships) must not depend on the model cooperating, so
    when the regenerated text still carries uncovered claims (or there was
    no regeneration), this rewrites the offending sentences in place and
    leaves everything else untouched. Each sentence is tested individually,
    so the _MAX_CLAIMS cap of :func:`universal_absence_claims` does not
    leak into here.
    """
    if not reply:
        return reply
    out: List[str] = []
    changed = False
    for sentence in _SENTENCE_SPLIT_RE.split(reply):
        if sentence.strip() and uncovered_absence_claims(sentence, tool_block):
            out.append(_SCOPED_LIMITATION)
            changed = True
        else:
            out.append(sentence)
    if not changed:
        return reply
    return " ".join(part.strip() for part in out if part.strip())


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
