#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Incident-closure acceptance replay against the backend the UI actually uses.

Runs the three original asks plus two controls through the REAL chat endpoint,
through the canvas the incident happened on, and scores each case with explicit
acceptance criteria instead of keyword presence.

Why this was rewritten
----------------------
The previous revision decided PASS/FAIL by keyword presence: a case passed when
the reply contained ANY token from an ``any_of`` list (later extended with an
``any_regex`` list — the same technique), and the "unrelated source" control
passed when the reply merely repeated the requested source name ("workbook",
"formula", "attachment"). Repeating a word from the question cannot establish
that an answer is right — on 2026-09-16 the directional case was scored PASS on
a reply that said "I can't confirm that from the data available to me". A
keyword harness certifies wording, not correctness.

The three evidence kinds used here, in order of preference
----------------------------------------------------------
1. STRUCTURED EVIDENCE FROM THE RESPONSE. ``POST /api/chat/message`` returns
   ``message``/``model``/``provider``/``metadata``/``session_id``/
   ``execution_id``/``success``/``error_code``; the serving process is stamped
   as ``X-Atom-Serving-Instance`` and ``metadata.serving_instance`` (with a
   pre-run ``GET /api/health`` identity only as fallback). The persisted turn
   trace (``GET /api/chat/trace/{session_id}``) carries the planner / tool /
   final-answer steps — including which service was consulted and per-step
   ``duration_ms`` — which is what distinguishes "the harness looked" from "the
   model said something plausible".
2. INDEPENDENT VERIFICATION OF THE ANSWER'S CLAIMS AGAINST THE REAL STORES.
   Strictly read-only, in-process: the ingested-mailbox store (LanceDB
   ``atom_communications``), the ingested-attachment ledger
   (``ingested_documents``, ``<message_id>:<attachment_id>``), the sheet/dataset
   catalog and the Parquet + formula sidecar behind a workbook row. If the
   reply says row 235 of a workbook holds a formula, this reads that workbook
   and checks the sheet, the row, the formula and its dependencies. No LLM.
3. DIRECT REVIEW OF THE COMPLETE ANSWER when 1 and 2 cannot decide — and then
   only for a specific fact, an attribution, a dependency, or an explicit
   "unresolved" statement, never "contains one of these words".

Delivery and quality are scored SEPARATELY. A provider failure (or a dead
socket) is a FAILED DELIVERY with quality NOT EVALUATED: never a quality
failure, never a pass. The failing stage (transport / planning / retrieval /
derivation / final generation) is recorded together with the stage evidence
that exists, because a final-generation failure does not prove that retrieval
or formula extraction never happened.

The case set and messages are UNCHANGED from the previous revision so results
stay comparable. ``--json`` carries, per case: delivery outcome, quality
outcome, failing stage, the criteria checked with their evidence, the route
(provider/model), per-stage timings, latency, the serving instance that
answered, and the attempt sequence.

Usage::

    ./venv/bin/python scripts/acceptance_replay_canvas.py --port 8001
    ./venv/bin/python scripts/acceptance_replay_canvas.py --port 8001 --only quote
    ./venv/bin/python scripts/acceptance_replay_canvas.py --port 8001 \
        --json /tmp/acceptance_criteria.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CANVAS_ID = "a1a13834-7bb3-4b3b-91cf-e83a2287daf0"

# ---------------------------------------------------------------------------
# Case set — messages UNCHANGED from the previous revision. What changed is
# ``criteria``: each case names the acceptance checks that must hold, and those
# checks resolve to the per-case code further down.
# ---------------------------------------------------------------------------

CASES: List[Dict[str, Any]] = [
    {
        "key": "quote",
        "label": "original quotation lookup (pasted vendor line)",
        "message": "search for this one: $ 5,350.00 - 10 % in stock",
        "quote": {"figure": "5350", "phrases": ["in stock", "10"]},
        "criteria": [
            "quote.identifies_stored_message",
            "quote.attribution_verified",
            "quote.quoted_from_source",
            "quote.not_reversed",
        ],
    },
    {
        "key": "directional",
        "label": "directional mail lookup (what did we send out)",
        "message": ("which emails did we send that carried the PRICE VIPUL "
                    "price list as an attachment?"),
        "attachment": {"name": "PRICE VIPUL", "tokens": ["price", "vipul"]},
        "criteria": [
            "directional.attachment_linked",
            "directional.direction_verified",
            "directional.no_phantom_outbound",
        ],
    },
    {
        "key": "derivation",
        "label": "workbook derivation (formula chain)",
        "message": ("open PRICE VIPUL and show how the 7519 listed price "
                    "was derived"),
        "workbook": {"name": "PRICE VIPUL", "target_value": 7519.0,
                     "row_number": 235},
        "criteria": [
            "derivation.correct_workbook",
            "derivation.correct_row",
            "derivation.formula_chain",
            "derivation.no_fabricated_chain",
            "derivation.unresolved_reported",
        ],
    },
    {
        "key": "control_unrelated_source",
        "label": "CONTROL: quoted line that is not mail",
        "message": ("search for this one: reliability score 0.87 from the "
                    "vendor scorecard workbook"),
        "source": {"name": "vendor scorecard", "value": "0.87"},
        "criteria": [
            "control_unrelated_source.lookup_evidence",
            "control_unrelated_source.source_verified_or_disclaimed",
            "control_unrelated_source.no_false_source",
        ],
    },
    {
        "key": "control_missing_evidence",
        "label": "CONTROL: answer not in any store (must not be invented)",
        "message": ("what is the list price of the F-9999 hydraulic press "
                    "in our records?"),
        "target": {"code": "F-9999", "kind": "hydraulic press"},
        "criteria": [
            "control_missing_evidence.target_addressed",
            "control_missing_evidence.no_price_attributed_to_target",
        ],
    },
]

PROVIDER_FAILURE_MARKERS = (
    "all llm providers failed",
    "no api keys configured",
    "no eligible llm providers",
    "llm client not initialized",
)

# ---------------------------------------------------------------------------
# Evidence containers. Pure data: the criteria functions take these plus the
# reply text, so every criterion is unit-testable with synthetic evidence.
# ---------------------------------------------------------------------------


@dataclass
class StoredMessage:
    """One ingested-mailbox record (read-only projection of a store row)."""

    message_id: str
    sender: str
    recipients: List[str]
    subject: str
    timestamp: str
    text: str
    sender_name: str = ""
    attachments: List[str] = field(default_factory=list)
    doc_ids: List[str] = field(default_factory=list)
    store_direction: str = ""

    @property
    def sender_address(self) -> str:
        return _first_address(self.sender) or ""

    @property
    def recipient_addresses(self) -> List[str]:
        out: List[str] = []
        for raw in self.recipients:
            out.extend(_addresses_in(raw))
        return out


@dataclass
class WorkbookStep:
    """One verified link of a workbook formula chain."""

    cell: str
    label: str
    expression: str
    value: Optional[float] = None
    kind: str = "other"  # input | identity | factor | offset | round | other
    constant: Optional[float] = None


@dataclass
class WorkbookFacts:
    """Ground truth read out of the stored workbook (Parquet + formula sidecar)."""

    file_name: str
    dataset_name: str
    sheet_name: str
    row_number: int
    product: str
    target_value: float
    sheet_count: int = 1
    values: Dict[str, Any] = field(default_factory=dict)
    formulas: Dict[str, str] = field(default_factory=dict)
    steps: List[WorkbookStep] = field(default_factory=list)
    allowed_numbers: List[float] = field(default_factory=list)
    unresolved_cells: List[str] = field(default_factory=list)


@dataclass
class EvidenceBundle:
    """Everything a criterion may assert against. All of it is read-only."""

    our_domains: List[str] = field(default_factory=list)
    messages: Dict[str, StoredMessage] = field(default_factory=dict)
    carriers: Dict[str, List[str]] = field(default_factory=dict)
    datasets: List[Dict[str, Any]] = field(default_factory=list)
    workbook: Optional[WorkbookFacts] = None
    trace_steps: List[Dict[str, Any]] = field(default_factory=list)
    trace_error: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    #: Name/domain tokens the store knows as EXTERNAL correspondents (used to
    #: recognise a counterparty named in prose, without any hardcoded list).
    counterparty_tokens: List[str] = field(default_factory=list)

    def is_ours(self, address: str) -> bool:
        dom = _domain_of(address)
        return bool(dom) and dom in {d.lower() for d in self.our_domains}

    def classify_direction(self, msg: StoredMessage) -> str:
        """outbound | inbound | internal — derived from addresses, never from
        the store's own ``direction`` column (measured live 2026-09-16: 7329 of
        7339 rows say "inbound", including messages this mailbox sent)."""
        sender = msg.sender_address
        if not sender:
            return "unknown"
        recips = msg.recipient_addresses
        if self.is_ours(sender):
            if recips and all(self.is_ours(r) for r in recips):
                return "internal"
            return "outbound"
        return "inbound"


@dataclass
class CriterionResult:
    criterion: str
    requirement: str
    passed: bool
    detail: str
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "criterion": self.criterion,
            "requirement": self.requirement,
            "passed": self.passed,
            "detail": self.detail,
            "evidence": self.evidence,
        }


# ---------------------------------------------------------------------------
# Pure text helpers (unit-tested in backend/tests/test_acceptance_criteria.py)
# ---------------------------------------------------------------------------

_PREFIX_RE = re.compile(r"^\s*(?:re|fw|fwd|aw|sv)\s*:\s*", re.IGNORECASE)
_CLAUSE_SPLIT_RE = re.compile(
    r"(?<=[.;!?])\s+|\n+|\s+(?:but|however|whereas|while|although|though)\s+"
    r"|;\s*|\s+—\s+|\s+–\s+",
    re.IGNORECASE,
)
_ADDRESS_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
#: A number, with a comma treated as a thousands separator only when it is
#: followed by exactly three digits ("235,0" is two numbers, not 2350).
_NUM_PAT = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_MONEY_RE = re.compile(
    r"(?P<cur>[$€£])\s?(?P<num>" + _NUM_PAT + r")"
    r"|(?P<num2>" + _NUM_PAT + r")\s?(?P<cur2>USD|CAD|EUR|GBP)\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(_NUM_PAT)
_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_MONTH_DAY_RE = re.compile(
    r"\b(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\.?\s+"
    r"(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(\d{4}))?",
    re.IGNORECASE,
)

UNRESOLVED_CUES = (
    "unresolved", "not resolvable", "cannot be resolved", "can't be resolved",
    "could not be resolved", "couldn't be resolved", "not in the workbook",
    "isn't in the workbook", "is not in the workbook", "no formula",
    "not available", "not present", "isn't present", "is not present",
    "does not appear", "doesn't appear", "not shown", "isn't shown",
    "is not shown", "not recorded", "no value", "cannot be verified",
    "can't verify", "could not verify", "unverified", "not retrievable",
    "cannot determine", "can't determine", "no evidence", "no record",
    "not documented", "does not resolve", "doesn't resolve", "not derivable",
    "no match", "not found", "couldn't find", "could not find", "no such",
    "don't have", "do not have", "isn't in", "is not in", "not in our records",
    "cannot confirm", "can't confirm", "could not confirm", "couldn't confirm",
    "unable to confirm", "there is no", "there's no", "other than",
    "does not exist", "doesn't exist", "not in the catalog", "no dataset",
    "no workbook",
)

#: Cues that a clause is actually MAKING a derivation statement (an operator, a
#: multiplication/division/addition word). Column NAMES ("Factory Discount",
#: "Exchange rate") are not derivation statements: treating them as such
#: flagged a true statement about the sheet's 240 rows as a fabricated figure
#: in the 2026-09-16 live run.
DERIVATION_CUES = (
    "*", "×", "/", "÷", "+", "=", "multipl", "times", "divide", "divided",
    " plus ", "adds ", "markup", "round up", "roundup", "rounded",
)

NEGATION_CUES = (
    "no ", "not ", "n't", "never", "none", "nothing", "without", "absent",
    "unavailable", "missing", "outside",
)

SENT_CUES = (
    "we sent", "you sent", "i sent", "we emailed", "you emailed",
    "sent to", "sent out", "was sent", "were sent", "we forwarded",
    "forwarded to", "went out", "delivered to", "we shared", "shared with",
    "we issued", "issued to", "outbound", "on our side", "our sent",
    "we replied", "we mailed",
)

RECEIVED_CUES = (
    "we received", "you received", "received from", "sent us", "sent you",
    "came from", "arrived from", "was sent to us", "were sent to us",
    "inbound", "we got", "you got", "from the vendor", "the vendor sent",
    "they sent", "he sent", "she sent",
)


#: Typographic punctuation models emit constantly. Folded to ASCII in ``canon``
#: so cue matching cannot be defeated by typography (see ``canon`` docstring).
_PUNCT_FOLD = str.maketrans({
    "\u2019": "'", "\u2018": "'", "\u02bc": "'", "\u2032": "'",
    "\u201c": '"', "\u201d": '"', "\u2033": '"',
    "\u2013": "-", "\u2014": "-", "\u2212": "-",
    "\u00a0": " ", "\u202f": " ", "\u2009": " ",
    "\u2026": "...",
})


def canon(text: Any) -> str:
    """Casefolded, whitespace-collapsed, punctuation-folded text.

    The Unicode fold is LOAD-BEARING, not cosmetic. Every cue in
    UNRESOLVED_CUES is written with an ASCII apostrophe, so a reply saying
    "I can’t confirm …" (U+2019) matched NOTHING and a correct disclaimer was
    scored as a fabricated claim. That produced false FAILs on
    `control_unrelated_source` — "claimed a value from a source no store
    contains" — for a reply whose entire content was "I can’t confirm a
    reliability score of 0.87 from the documents currently available to me".
    Verified 2026-09-16: the same sentence matches with an ASCII apostrophe and
    does not without.
    """
    folded = str(text or "").translate(_PUNCT_FOLD)
    return re.sub(r"\s+", " ", folded).strip().lower()


def canon_alnum(text: Any) -> str:
    """Alphanumeric-only, casefolded — for subject/phrase matching."""
    return re.sub(r"[^a-z0-9]+", " ", canon(text)).strip()


def digits_only(text: Any) -> str:
    return re.sub(r"\D+", "", str(text or ""))


def figure_in(figure: Any, text: Any) -> bool:
    """Is a figure (e.g. '5,350.00') present in text, ignoring punctuation?"""
    fig = digits_only(figure)
    return bool(fig) and fig in digits_only(text)


def money_mentions(text: str) -> List[Tuple[str, float]]:
    """(raw, value) for every currency-shaped number in text."""
    out: List[Tuple[str, float]] = []
    for m in _MONEY_RE.finditer(text or ""):
        raw = m.group("num") or m.group("num2") or ""
        try:
            out.append((m.group(0), float(raw.replace(",", ""))))
        except (TypeError, ValueError):
            continue
    return out


def number_values(text: str) -> List[float]:
    out: List[float] = []
    for m in _NUMBER_RE.finditer(text or ""):
        try:
            out.append(float(m.group(0).replace(",", "")))
        except ValueError:
            continue
    return out


def split_clauses(text: str) -> List[str]:
    """Sentence/clause split used by the attribution + direction parsers."""
    return [p.strip() for p in _CLAUSE_SPLIT_RE.split(text or "") if p and p.strip()]


def addresses_in(text: str) -> List[str]:
    return [a.lower() for a in _ADDRESS_RE.findall(text or "")]


def _addresses_in(text: str) -> List[str]:
    return addresses_in(text)


def _first_address(text: str) -> Optional[str]:
    found = addresses_in(text)
    return found[0] if found else None


def _domain_of(address: str) -> str:
    m = _ADDRESS_RE.search(str(address or ""))
    if not m:
        return ""
    return m.group(0).split("@", 1)[-1].lower()


def date_matches(text: str, timestamp: str) -> bool:
    """Does ``text`` name the calendar day of ``timestamp``?

    Accepts an ISO date, a month-name/day pair, or a ``M/D`` pair when it is
    unambiguous against the stored timestamp.
    """
    ts = str(timestamp or "")
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", ts)
    if not m:
        return False
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    body = text or ""
    if f"{year:04d}-{month:02d}-{day:02d}" in body:
        return True
    for mm in _MONTH_DAY_RE.finditer(body):
        if _MONTHS.get(mm.group(1).lower()) != month:
            continue
        if int(mm.group(2)) != day:
            continue
        if mm.group(3) and int(mm.group(3)) != year:
            continue
        return True
    for slash in re.finditer(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", body):
        a, b = int(slash.group(1)), int(slash.group(2))
        yr = slash.group(3)
        if yr and len(yr) == 4 and int(yr) != year:
            continue
        if (a == month and b == day) or (b == month and a == day):
            return True
    return False


def subject_in(text: str, subject: str) -> bool:
    """Is the (prefix-stripped) subject present in text?"""
    want = canon_alnum(_PREFIX_RE.sub("", str(subject or "")))
    if not want or len(want) < 4:
        return False
    return want in canon_alnum(text)


def sender_display_name(metadata: Any) -> str:
    """The sender's display name out of the ingested row's own metadata.

    The store records it (``metadata.email_metadata.outlook_metadata.from``);
    reading it here is what lets an answer identify a message by the name a
    human actually writes ("Joel Seguin, Aug 26 2026") instead of demanding a
    raw address. Read-only, tolerant of every shape the column takes.
    """
    meta = metadata
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:  # noqa: BLE001
            return ""
    if not isinstance(meta, dict):
        return ""
    node: Any = meta.get("email_metadata") or {}
    if isinstance(node, dict):
        node = node.get("outlook_metadata") or {}
    if isinstance(node, dict):
        node = node.get("from") or {}
    if isinstance(node, dict):
        addr = node.get("emailAddress") or {}
        if isinstance(addr, dict):
            return str(addr.get("name") or "").strip()
        return ""
    if isinstance(node, str):
        m = re.match(r"\s*([^<]+?)\s*<", node)
        return (m.group(1).strip() if m else "")
    return ""


def name_tokens(name: str) -> List[str]:
    """Distinctive tokens of a display name ('Joel Seguin' -> [joel, seguin])."""
    return [t for t in re.split(r"[^A-Za-z0-9]+", canon(name)) if len(t) >= 3]


def message_match_reasons(reply: str, msg: StoredMessage) -> List[str]:
    """How the reply refers to one stored message — ids, citations, sender/date.

    "Names a vendor somewhere" produces no reasons: an identity has to resolve
    to this message's id/citation, or to its sender (address or the display name
    the store holds for it) AND its date/subject.
    """
    reasons: List[str] = []
    body = reply or ""
    mid = str(msg.message_id or "")
    if mid and len(mid) >= 20:
        if mid in body or mid[:60] in body:
            reasons.append("message_id")
        if f"knowledge/conversations/{mid}" in body:
            reasons.append("citation")
    sender = msg.sender_address
    if sender and sender in canon(body):
        reasons.append("sender_address")
        if date_matches(body, msg.timestamp):
            reasons.append("sender+date")
        elif subject_in(body, msg.subject):
            reasons.append("sender+subject")
    else:
        toks = name_tokens(msg.sender_name)
        if toks and all(t in canon(body) for t in toks):
            reasons.append("sender_name")
            if date_matches(body, msg.timestamp):
                reasons.append("sender_name+date")
            elif subject_in(body, msg.subject):
                reasons.append("sender_name+subject")
        elif date_matches(body, msg.timestamp) and subject_in(body, msg.subject):
            reasons.append("date+subject")
    return reasons


#: Reasons strong enough to count as a corroborated message attribution.
STRONG_MATCH_REASONS = {
    "message_id", "citation", "sender+date", "sender+subject",
    "sender_name+date", "sender_name+subject", "date+subject",
}


def direction_claims(reply: str) -> List[Dict[str, Any]]:
    """Classify each clause as a SENT or RECEIVED claim (or neither).

    ``sent`` cues describe mail leaving this mailbox; ``received`` cues describe
    mail arriving. A clause carrying both is reported with both, because that
    contradiction is itself evidence the direction is confused.
    """
    out: List[Dict[str, Any]] = []
    for clause in split_clauses(reply):
        low = canon(clause)
        sent = [c for c in SENT_CUES if c in low]
        recv = [c for c in RECEIVED_CUES if c in low]
        if not sent and not recv:
            continue
        out.append({
            "clause": clause.strip()[:400],
            "sent_cues": sent,
            "received_cues": recv,
            # A negated claim ("it was NOT sent to a counterparty") is not an
            # assertion about direction and must not be read as one.
            "sent_negated": any(
                _has_negation_before(low, low.index(cue) + len(cue) - 1, 30)
                for cue in sent
            ),
            "received_negated": any(
                _has_negation_before(low, low.index(cue) + len(cue) - 1, 30)
                for cue in recv
            ),
            "addresses": addresses_in(clause),
            "figures": [raw for raw, _ in money_mentions(clause)],
        })
    return out


def _has_negation_before(text: str, index: int, window: int = 40) -> bool:
    head = canon(text[max(0, index - window):index])
    return any(cue in head for cue in NEGATION_CUES)


@dataclass
class PriceAudit:
    attributed: List[Dict[str, Any]] = field(default_factory=list)
    disclaimed: List[str] = field(default_factory=list)
    other_subject: List[Dict[str, Any]] = field(default_factory=list)


def audit_price_attribution(reply: str, target_patterns: Sequence[str],
                            price_words: Sequence[str] = ("price", "cost", "listed", "list")) -> PriceAudit:
    """Is a price ATTRIBUTED to the target — judged per clause, in context?

    A clause counts as an attribution when it mentions the target and carries a
    price whose nearest preceding subject mention is the target, with no
    negation governing the target. Prices in clauses about a DIFFERENT product
    land in ``other_subject``: mentioning another product's real price is
    correct behaviour, and the previous revision's proximity regex failed
    exactly that answer.
    """
    tpat = re.compile("|".join(target_patterns), re.IGNORECASE)
    word_pat = re.compile(
        r"\b(?:%s)\b[^.\n]{0,20}?(%s)" % (
            "|".join(re.escape(w) for w in price_words), _NUM_PAT),
        re.IGNORECASE,
    )
    audit = PriceAudit()
    for clause in split_clauses(reply):
        target_hits = list(tpat.finditer(clause))
        if not target_hits:
            continue
        money = money_mentions(clause)
        bare = [(m.group(0), float(m.group(1).replace(",", "")))
                for m in word_pat.finditer(clause)]
        findings = money or bare
        if not findings:
            low = canon(clause)
            if any(cue in low for cue in UNRESOLVED_CUES) or \
                    _has_negation_before(clause, target_hits[0].start()):
                audit.disclaimed.append(clause.strip()[:300])
            continue
        for raw, value in findings:
            idx = clause.find(raw)
            prior = [(m.start(), m.group(0)) for m in tpat.finditer(clause[:max(idx, 0)])]
            negated = _has_negation_before(clause, target_hits[0].start()) or any(
                _has_negation_before(clause, start) for start, _ in prior)
            if prior:
                if negated:
                    audit.disclaimed.append(clause.strip()[:300])
                else:
                    audit.attributed.append({
                        "clause": clause.strip()[:300],
                        "price": raw, "value": value, "subject": prior[-1][1],
                    })
            else:
                audit.other_subject.append({
                    "clause": clause.strip()[:300],
                    "price": raw, "value": value, "subject": None,
                })
    return audit


def has_unresolved_statement(text: str) -> bool:
    low = canon(text)
    return any(cue in low for cue in UNRESOLVED_CUES)


def unsupported_figures(reply: str, allowed: Iterable[float],
                        tolerance: float = 0.005,
                        cues: Sequence[str] = DERIVATION_CUES) -> List[str]:
    """Numbers the reply presents as part of a derivation that the store cannot
    account for.

    Two shapes are checked, both inside clauses that actually make a derivation
    statement (a multiplier, divisor, offset, cell reference or rounding cue):
    currency-shaped figures, and any other number that is not a percentage and
    not a year. Numbers inside an explicit "unresolved" statement are excused —
    naming a missing input is honest; asserting a fabricated chain is what
    fails. Incidental numbers elsewhere in the answer are not derivation
    claims and are not flagged.
    """
    allowed_vals = [float(a) for a in allowed]
    out: List[str] = []
    for clause in split_clauses(reply):
        if has_unresolved_statement(clause):
            continue
        low = canon(clause)
        if not any(cue in low for cue in cues):
            continue
        seen = {raw for raw, _ in money_mentions(clause)}
        for match in _NUMBER_RE.finditer(clause):
            raw = match.group(0)
            tail = clause[match.end():match.end() + 2]
            if tail.strip().startswith("%"):
                continue
            value = float(raw.replace(",", ""))
            if 1900 <= value <= 2100 and "." not in raw:
                continue  # a year, not a chain figure
            if "." not in raw and value < 100:
                continue  # row/cell numbers, quantities
            if any(abs(value - a) <= max(abs(a) * tolerance, 0.011)
                   for a in allowed_vals):
                continue
            out.append(raw if raw not in seen else f"${raw}")
    return out


# ---------------------------------------------------------------------------
# Delivery / stage classification
# ---------------------------------------------------------------------------


def classify_delivery(http_status: Optional[int], body: Optional[Dict[str, Any]],
                      transport_error: Optional[str],
                      trace_steps: Sequence[Dict[str, Any]],
                      case_key: str) -> Dict[str, Any]:
    """Delivery outcome + the stage the failure is attributed to.

    Delivery is "did a real answer come back": a provider failure, a dead
    socket, a non-200, an empty reply, or a ``template`` route (a canned string
    instead of a model answer) all fail delivery, and quality is then NOT
    EVALUATED. ``stage_evidence`` records what the turn demonstrably did before
    it failed; a final-generation failure must not be reported as "retrieval
    never ran".
    """
    stages: Dict[str, List[str]] = {
        "planning": [], "retrieval": [], "derivation": [], "final_generation": [],
    }
    for step in trace_steps:
        action = str(step.get("action") or "")
        step_type = str(step.get("step_type") or "")
        observation = str(step.get("observation") or "")
        low = f"{action} {observation}".lower()
        where = f"{step_type or '?'}:{action or '?'}"
        if action == "tool_planner" or (step_type == "thought" and "plan" in low):
            stages["planning"].append(where)
        if action and action not in ("tool_planner", "llm"):
            stages["retrieval"].append(where)
        if re.search(r"dataset|workbook|formula|price vipul|sheet|row \d+", low) or \
                re.search(r"=[A-Z]{1,3}\d+", observation):
            stages["derivation"].append(where)
        if step_type == "final_answer" or action == "llm":
            stages["final_generation"].append(where)
    for key, value in list(stages.items()):
        stages[key] = value[:4]

    reply = str((body or {}).get("message") or "")
    error_code = (body or {}).get("error_code")
    provider_failure = any(m in reply.lower() for m in PROVIDER_FAILURE_MARKERS) or \
        error_code in ("no_llm_provider",)
    unevidenced = [s for s in ("planning", "retrieval", "derivation")
                   if not stages[s]]

    if transport_error:
        return {
            "outcome": "transport_error", "stage_failed": "transport",
            "reason": transport_error[:400], "stage_evidence": stages,
            "stages_unevidenced": unevidenced, "provider_failure": False,
        }
    if http_status != 200:
        return {
            "outcome": "http_error", "stage_failed": "transport",
            "reason": f"HTTP {http_status}", "stage_evidence": stages,
            "stages_unevidenced": unevidenced, "provider_failure": False,
        }
    if provider_failure:
        return {
            "outcome": "provider_failure", "stage_failed": "final_generation",
            "reason": reply[:300] or str(error_code), "stage_evidence": stages,
            "stages_unevidenced": unevidenced, "provider_failure": True,
        }
    # A template answer is NOT a model answer: the turn was answered by a
    # canned string, so no generation happened and the reply cannot be scored
    # as a product answer (or as a quality pass).
    route_provider = str((body or {}).get("provider") or "").lower()
    route_model = str((body or {}).get("model") or "").lower()
    if route_provider == "template" or route_model == "template":
        return {
            "outcome": "template_fallback", "stage_failed": "final_generation",
            "reason": f"no model answer — route {route_provider}/{route_model}",
            "stage_evidence": stages, "stages_unevidenced": unevidenced,
            "provider_failure": False,
        }
    if error_code:
        return {
            "outcome": "structured_error", "stage_failed": "final_generation",
            "reason": str(error_code), "stage_evidence": stages,
            "stages_unevidenced": unevidenced, "provider_failure": False,
        }
    if not reply.strip():
        return {
            "outcome": "empty_reply", "stage_failed": "final_generation",
            "reason": "200 with empty message", "stage_evidence": stages,
            "stages_unevidenced": unevidenced, "provider_failure": False,
        }
    # TEMPLATE FALLBACK IS NOT A MODEL ANSWER. When the orchestrator's LLM call
    # returns nothing it labels the turn `provider="template"`,
    # `model="template"` and serves `_generate_main_message(...)` — a canned
    # string. That reply is non-empty and carries no provider-failure marker,
    # so it was classified `answered` and its QUALITY was scored, conflating
    # "no model answered" with "the model answered badly". Reported separately
    # so the case is NOT_EVALUATED (and the run INVALID) instead of FAIL.
    _route_provider = str((body or {}).get("provider") or "").lower()
    _route_model = str((body or {}).get("model") or "").lower()
    if _route_provider == "template" or _route_model == "template":
        return {
            "outcome": "template_fallback", "stage_failed": "final_generation",
            "reason": "no model answered; the orchestrator served a canned "
                      "template response",
            "stage_evidence": stages, "stages_unevidenced": unevidenced,
            "provider_failure": False,
        }
    return {
        "outcome": "answered", "stage_failed": None, "reason": "",
        "stage_evidence": stages, "stages_unevidenced": [],
        "provider_failure": False,
    }


def aggregate_quality(delivery: Dict[str, Any],
                      criteria: Sequence[CriterionResult]) -> Dict[str, Any]:
    """Quality is NOT EVALUATED when a real answer never came back."""
    if delivery.get("outcome") != "answered":
        return {
            "outcome": "not_evaluated",
            "reason": f"delivery failed ({delivery.get('outcome')}) — "
                      f"answer quality not evaluated",
            "failed_criteria": [],
            "failing_stage": [],
        }
    failed = [c.criterion for c in criteria if not c.passed]
    return {
        "outcome": "fail" if failed else "pass",
        "reason": "" if not failed else f"{len(failed)} criterion(s) failed",
        "failed_criteria": failed,
        "failing_stage": [FAILING_STAGE_BY_CRITERION.get(c, "unknown")
                          for c in failed],
    }


# ---------------------------------------------------------------------------
# Per-case acceptance criteria
# ---------------------------------------------------------------------------


def _quote_candidates(ev: EvidenceBundle, spec: Dict[str, Any]) -> List[StoredMessage]:
    out: List[StoredMessage] = []
    for msg in ev.messages.values():
        if not figure_in(spec["figure"], msg.text):
            continue
        low = canon(msg.text)
        if not any(p in low for p in spec.get("phrases", [])):
            continue
        out.append(msg)
    return out


def criteria_quote(reply: str, ev: EvidenceBundle,
                   spec: Dict[str, Any]) -> List[CriterionResult]:
    """The reply must identify the CORRECT stored message and quote FROM it."""
    results: List[CriterionResult] = []
    candidates = _quote_candidates(ev, spec)
    matched = [(m, message_match_reasons(reply, m)) for m in candidates]
    matched = [(m, r) for m, r in matched if r]

    results.append(CriterionResult(
        criterion="quote.identifies_stored_message",
        requirement=("the reply identifies the stored message that carries the "
                     "quoted line (message id, citation, or sender+date/subject)"),
        passed=bool(matched),
        detail=("no message-level identity resolved — naming a vendor, a price "
                "or the word 'quote' is not an identification" if not matched
                else f"{len(matched)} stored message(s) identified"),
        evidence=[f"{m.timestamp} | {m.sender_address} | {m.subject[:60]} | via {r}"
                  for m, r in matched[:3]],
    ))

    strong = [(m, r) for m, r in matched
              if STRONG_MATCH_REASONS & set(r)]
    results.append(CriterionResult(
        criterion="quote.attribution_verified",
        requirement=("the attribution (sender — address or the store's display "
                     "name — plus date/subject) agrees with the stored message; "
                     "naming a vendor is not enough"),
        passed=bool(strong),
        detail=("no corroborated sender+date/subject attribution" if not strong
                else "attribution corroborated against the store"),
        evidence=[f"{m.sender_address} ({m.sender_name or 'no display name'}) @ "
                  f"{m.timestamp} ({m.subject[:50]}) via {r}"
                  for m, r in strong[:3]] or
                 [f"matched without a corroborating date/subject: {r}"
                  for _, r in matched[:2]],
    ))

    quoted_ok = [
        f"{m.message_id[:40]}… contains {spec['figure']} + {spec.get('phrases')}"
        for m, _ in matched[:3]
        if figure_in(spec["figure"], m.text) and figure_in(spec["figure"], reply)
    ]
    results.append(CriterionResult(
        criterion="quote.quoted_from_source",
        requirement=("the quoted terms are verifiably present in the identified "
                     "stored message (the quote is quoted FROM the source)"),
        passed=bool(quoted_ok),
        detail=("quoted terms not verifiable in any identified stored message"
                if not quoted_ok else "quoted terms verified in the stored source"),
        evidence=quoted_ok[:2] or
                 [f"store candidates containing {spec['figure']}: {len(candidates)}"],
    ))

    reversed_claims = [
        c for c in direction_claims(reply)
        if c["sent_cues"] and any(figure_in(spec["figure"], f) for f in c["figures"])
    ]
    results.append(CriterionResult(
        criterion="quote.not_reversed",
        requirement=("the quote is a RECEIVED vendor line, not something this "
                     "mailbox sent"),
        passed=not reversed_claims,
        detail=("reply frames the quoted price as outbound" if reversed_claims
                else "no outbound framing of the vendor quote"),
        evidence=[c["clause"] for c in reversed_claims[:2]],
    ))
    return results


def criteria_directional(reply: str, ev: EvidenceBundle,
                         spec: Dict[str, Any]) -> List[CriterionResult]:
    """Right messages AND the right direction, with the attachment linked."""
    results: List[CriterionResult] = []
    key = " ".join(sorted(spec.get("tokens") or [spec.get("name", "")])).lower()
    carrier_ids = list(ev.carriers.get(key) or [])
    carriers = [ev.messages[i] for i in carrier_ids if i in ev.messages]

    matched = [(m, message_match_reasons(reply, m)) for m in carriers]
    matched = [(m, r) for m, r in matched if r]
    store_view = [
        f"{m.timestamp} | {m.sender_address} -> {', '.join(m.recipient_addresses)} "
        f"| {m.subject[:50]} | {ev.classify_direction(m)}"
        for m in carriers[:3]
    ]
    results.append(CriterionResult(
        criterion="directional.attachment_linked",
        requirement=("the attachment is linked to a NAMED stored message that "
                     "really carried it (verified in the attachment ledger)"),
        passed=bool(matched),
        detail=(f"{len(carriers)} store message(s) carry {spec.get('name')}; "
                f"{len(matched)} referenced by the reply"),
        evidence=([f"{m.timestamp} | {m.sender_address} -> "
                   f"{', '.join(m.recipient_addresses)} | {m.subject[:50]} | "
                   f"attachments={m.attachments} | via {r}" for m, r in matched[:3]]
                  or [f"store carrier(s): {store_view}"]),
    ))

    problems: List[str] = []
    confirmations: List[str] = []
    claim_sentences = direction_claims(reply)
    live_claims = [c for c in claim_sentences
                   if not (c["sent_negated"] and c["received_negated"])]
    for msg, _ in matched:
        truth = ev.classify_direction(msg)
        for claim in live_claims:
            low = canon(claim["clause"])
            mentions_msg = (
                bool(msg.sender_address and msg.sender_address in low)
                or date_matches(claim["clause"], msg.timestamp)
                or subject_in(claim["clause"], msg.subject)
                or any(addr in low for addr in msg.recipient_addresses)
            )
            if not mentions_msg:
                continue
            if claim["sent_cues"] and not claim["sent_negated"] and truth == "inbound":
                problems.append(
                    "claims SENT but the store's sender is the counterparty: "
                    f"'{claim['clause'][:160]}'")
            elif claim["received_cues"] and not claim["received_negated"] and \
                    truth in ("outbound", "internal"):
                problems.append(
                    "claims RECEIVED but the store says this mailbox sent it: "
                    f"'{claim['clause'][:160]}'")
            elif claim["sent_cues"] and not claim["sent_negated"]:
                confirmations.append(
                    f"sent-direction claim matches store ({truth}): "
                    f"'{claim['clause'][:120]}'")
            elif claim["received_cues"] and not claim["received_negated"]:
                confirmations.append(
                    f"received-direction claim matches store (inbound): "
                    f"'{claim['clause'][:120]}'")

    results.append(CriterionResult(
        criterion="directional.direction_verified",
        requirement=("every direction the reply asserts for the carrying "
                     "message(s) matches the store (sent BY us vs received)"),
        passed=bool(matched) and not problems,
        detail=("direction contradicted by the store" if problems else
                "direction claims consistent with the store") if matched
        else "no carrying message was referenced, so direction cannot be verified",
        evidence=(problems + confirmations)[:4] or store_view,
    ))

    # Phantom outbound: "we sent the price list to <counterparty>" with no such
    # carrier in the store. The live store exposes exactly this failure mode —
    # its only PRICE VIPUL carrier is an internal forward — so a claim of an
    # outbound-to-counterparty delivery has to be corroborated, or explicitly
    # qualified as internal, or it is unsupported.
    #
    # What makes a claim an OUTBOUND-TO-COUNTERPARTY claim is that it says so:
    # an address outside this install, counterparty framing ("the customer"),
    # or a name/domain the store knows as an external correspondent. "We sent
    # one email carrying the price list", followed by the recipient lines, is a
    # description of the send, not a claim about where it went — flagging it
    # would fail a correct answer.
    outbound_claims: List[str] = []
    qualified: List[str] = []
    counterparty_framing = re.compile(
        r"customer|client|counterpart|externally|external (?:party|recipient)|"
        r"vendor|supplier|dealer|to them\b|out to\b")
    for claim in live_claims:
        low = canon(claim["clause"])
        if not claim["sent_cues"] or claim["sent_negated"]:
            continue
        if not any(tok in low for tok in (spec.get("tokens") or [])):
            continue
        external_address = any(
            not ev.is_ours(a) and a not in {r for m in carriers
                                            for r in m.recipient_addresses}
            for a in claim["addresses"])
        counterparty_named = any(t in low for t in ev.counterparty_tokens)
        internal_qualified = (
            any(ev.is_ours(a) for a in claim["addresses"])
            or any(addr in low for m in carriers for addr in m.recipient_addresses)
            or bool(re.search(r"internal|internally|in-house|colleague|"
                              r"to a colleague|forwarded to", low))
        )
        is_external_claim = (
            external_address
            or bool(counterparty_framing.search(low))
            or counterparty_named
        ) and not internal_qualified
        (outbound_claims if is_external_claim else qualified).append(
            claim["clause"][:200])
    verified_outbound = [m for m in carriers
                         if ev.classify_direction(m) == "outbound"]
    phantom = bool(outbound_claims) and not verified_outbound
    results.append(CriterionResult(
        criterion="directional.no_phantom_outbound",
        requirement=("a claim that the price list went OUT to a counterparty "
                     "must have a matching carrier in the store (a genuinely "
                     "internal send must be described as internal)"),
        passed=not phantom,
        detail=("reply asserts an outbound-to-counterparty delivery but the "
                "store has no such carrier" if phantom else
                "no unsupported outbound-to-counterparty claim"),
        evidence=(outbound_claims[:2] + [
            "sent claims without counterparty framing (allowed): "
            f"{[q[:120] for q in qualified[:2]]}",
            "store carrier directions: "
            f"{[(m.timestamp, ev.classify_direction(m)) for m in carriers][:3]}",
            f"store outbound carriers: "
            f"{[m.timestamp for m in verified_outbound] or 'none'}",
        ])[:4],
    ))
    return results


DERIVATION_STEP_SPECS: List[Dict[str, Any]] = [
    {
        "key": "factory_discount",
        "requirement": "the 10% factory-discount step (x0.9 / -10%)",
        "patterns": [r"\b0\.9\b", r"\b90\s?%", r"10\s?%"],
    },
    {
        "key": "freight_offset",
        "requirement": "the +700 freight step",
        "patterns": [r"\b700\b", r"\+\s?700"],
    },
    {
        "key": "warehouse_factor",
        "requirement": "the x1.02 warehouse step",
        "patterns": [r"\b1\.02\b", r"\b2\s?%"],
    },
    {
        "key": "brennan_margin",
        "requirement": "the /0.87 Brennan-margin step",
        "patterns": [r"\b0\.87\b"],
    },
    {
        "key": "dealer_margin",
        "requirement": "the /0.86 dealer-margin step",
        "patterns": [r"\b0\.86\b"],
    },
    {
        "key": "rounding",
        "requirement": "the ROUNDUP rounding to the listed price",
        "patterns": [r"round\s?up", r"rounded\s+up", r"rounding"],
    },
]


def criteria_derivation(reply: str, ev: EvidenceBundle) -> List[CriterionResult]:
    """The strictest case: workbook, sheet, row, formulas, dependencies, rounding.

    Every intermediate must be verified against the stored workbook; an
    intermediate the workbook does not resolve must be reported by the answer as
    EXPLICITLY UNRESOLVED. Asserting a fabricated chain fails.
    """
    results: List[CriterionResult] = []
    wb = ev.workbook
    if wb is None:
        return [CriterionResult(
            criterion="derivation.workbook_available",
            requirement="the stored workbook must be readable to verify the chain",
            passed=False,
            detail="workbook evidence unavailable (store read failed)",
            evidence=ev.errors[:3],
        )]

    stem = canon_alnum(re.sub(r"\.(xlsx|xlsm|xls|csv)$", "", wb.file_name))
    tokens = [t for t in stem.split() if len(t) >= 4]
    name_present = bool(tokens) and all(t in canon_alnum(reply) for t in tokens)
    results.append(CriterionResult(
        criterion="derivation.correct_workbook",
        requirement=f"the reply works in the correct workbook ({wb.file_name})",
        passed=name_present,
        detail="workbook named in the reply" if name_present
        else f"workbook {wb.file_name!r} never named",
        evidence=[f"{wb.file_name} | dataset={wb.dataset_name} | sheet={wb.sheet_name}"],
    ))

    row_present = bool(re.search(rf"(?:row|r)\s*#?\s*{wb.row_number}\b", canon(reply))) \
        or bool(re.search(rf"\b{wb.row_number}\b", reply))
    product_present = bool(wb.product) and (
        canon_alnum(wb.product)[:8] in canon_alnum(reply)
        or digits_only(wb.product)[:4] in digits_only(reply)
    )
    value_present = bool(re.search(
        rf"\b{re.escape(f'{wb.target_value:,.0f}')}\b", reply)) or \
        bool(re.search(rf"\b{re.escape(f'{wb.target_value:.0f}')}\b", reply))
    sheet_named = canon_alnum(wb.sheet_name) in canon_alnum(reply) if wb.sheet_name else False
    # With a single sheet there is nothing to disambiguate; with several, the
    # reply has to name the right one.
    sheet_ok = wb.sheet_count <= 1 or sheet_named
    results.append(CriterionResult(
        criterion="derivation.correct_row",
        requirement=(f"the reply identifies row {wb.row_number} — the row whose "
                     f"listed price is {wb.target_value:g}"
                     + (f" — on sheet {wb.sheet_name!r}" if wb.sheet_count > 1
                        else " (the workbook's only sheet)")),
        passed=row_present and (product_present or value_present) and sheet_ok,
        detail=("row identified" if row_present else "row number missing") +
               ("; product named" if product_present else
                ("; listed value stated" if value_present else "; row not identified by product or value")) +
               (f"; sheet {wb.sheet_name!r} named" if sheet_named else
                ("" if sheet_ok else f"; sheet {wb.sheet_name!r} NOT named")),
        evidence=[f"store row {wb.row_number}: product={wb.product!r} "
                  f"listed={wb.target_value:g} sheet={wb.sheet_name!r} "
                  f"(sheets in file: {wb.sheet_count})",
                  f"row formulas: {wb.formulas}"],
    ))

    step_hits: List[str] = []
    step_misses: List[str] = []
    for spec in DERIVATION_STEP_SPECS:
        hit = any(re.search(p, reply, re.IGNORECASE) for p in spec["patterns"])
        (step_hits if hit else step_misses).append(spec["requirement"])
    results.append(CriterionResult(
        criterion="derivation.formula_chain",
        requirement=("the reply states the source formulas, their dependencies "
                     "and the rounding (every chain step verified)"),
        passed=not step_misses,
        detail=(f"{len(step_hits)}/{len(DERIVATION_STEP_SPECS)} chain steps stated"
                + (f"; missing: {step_misses}" if step_misses else "")),
        evidence=[f"{s.cell} {s.expression} -> {s.value} ({s.label})"
                  for s in wb.steps],
    ))

    allowed = list(wb.allowed_numbers) + [wb.target_value]
    fabricated = unsupported_figures(reply, allowed)
    results.append(CriterionResult(
        criterion="derivation.no_fabricated_chain",
        requirement=("every figure the reply presents as part of the chain must "
                     "exist in the stored workbook (or be flagged unresolved)"),
        passed=not fabricated,
        detail=("fabricated intermediate(s) asserted" if fabricated
                else "all asserted figures trace to stored values"),
        evidence=([f"unsupported: {fabricated}"] if fabricated else
                  [f"allowed values: {sorted(set(allowed))[:14]}"]) +
                 [f"store row values: {wb.values}"],
    ))

    needed_unflagged = bool(fabricated) and not has_unresolved_statement(reply)
    results.append(CriterionResult(
        criterion="derivation.unresolved_reported",
        requirement=("any intermediate the workbook does not resolve must be "
                     "reported as EXPLICITLY UNRESOLVED"),
        passed=not needed_unflagged,
        detail=("asserted values with no explicit unresolved statement"
                if needed_unflagged else
                ("explicit unresolved statement present"
                 if has_unresolved_statement(reply) else
                 "every chain input resolves in the workbook")),
        evidence=[f"workbook unresolved cells: {wb.unresolved_cells or 'none'}",
                  "reply contains an unresolved marker: "
                  f"{has_unresolved_statement(reply)}"],
    ))
    return results


def criteria_control_unrelated_source(reply: str, ev: EvidenceBundle,
                                      spec: Dict[str, Any]) -> List[CriterionResult]:
    """The harness must show evidence of the SELECTED source.

    Repeating "workbook"/"formula" from the question cannot pass: either the
    named source verifies in a real store, or the reply explicitly states the
    source was not found — and a lookup must be visible in the turn trace.
    """
    results: List[CriterionResult] = []
    lookup_steps = [s for s in ev.trace_steps
                    if str(s.get("action") or "") not in ("", "llm")]
    results.append(CriterionResult(
        criterion="control_unrelated_source.lookup_evidence",
        requirement=("the turn shows structured evidence that a lookup ran "
                     "against a concrete store/service"),
        passed=bool(lookup_steps),
        detail=(f"{len(lookup_steps)} planner/tool step(s) recorded"
                if lookup_steps else
                "no lookup step in the persisted turn trace"),
        evidence=[f"{s.get('step_type')}:{s.get('action')} "
                  f"({str(s.get('observation') or '')[:90]})"
                  for s in lookup_steps[:3]] or
                 ([f"trace error: {ev.trace_error}"] if ev.trace_error else []),
    ))

    src_tokens = [t for t in canon(spec.get("name", "")).split() if len(t) >= 4]
    named_source = bool(src_tokens) and all(t in canon(reply) for t in src_tokens)
    matching_datasets = [
        d for d in ev.datasets
        if src_tokens and all(t in canon(d.get("file_name") or "") for t in src_tokens)
    ]
    disclaimed = named_source and has_unresolved_statement(reply)
    results.append(CriterionResult(
        criterion="control_unrelated_source.source_verified_or_disclaimed",
        requirement=("either the named source exists in a store and is verified, "
                     "or the reply explicitly states it was not found"),
        passed=bool(matching_datasets) or disclaimed,
        detail=(f"{len(matching_datasets)} catalog dataset(s) match the named source"
                if matching_datasets else
                ("explicit not-found statement about the named source"
                 if disclaimed else
                 "named source neither verified in a store nor disclaimed — "
                 "repeating the source name from the question proves nothing")),
        evidence=[f"catalog matches: "
                  f"{[d.get('file_name') for d in matching_datasets][:3]}",
                  f"explicit not-found statement: {disclaimed}",
                  f"datasets scanned: {len(ev.datasets)}"],
    ))

    value = str(spec.get("value") or "")
    false_claim = False
    evidence: List[str] = []
    if named_source and not matching_datasets and not disclaimed and value:
        for clause in split_clauses(reply):
            if value in clause and not has_unresolved_statement(clause):
                false_claim = True
                evidence.append(clause.strip()[:200])
    results.append(CriterionResult(
        criterion="control_unrelated_source.no_false_source",
        requirement=("the reply must not assert the quoted value came from a "
                     "source that no store contains"),
        passed=not false_claim,
        detail=("claimed a value from a source no store contains" if false_claim
                else "no unsupported source claim"),
        evidence=evidence[:2] or
                 [f"value={value!r} → sources containing it: none in the catalog"],
    ))
    return results


def criteria_control_missing_evidence(reply: str, ev: EvidenceBundle,
                                      spec: Dict[str, Any]) -> List[CriterionResult]:
    """No unsupported price ATTRIBUTED to the missing target, judged in context."""
    results: List[CriterionResult] = []
    code = str(spec["code"])
    patterns = [re.escape(code), re.escape(code.replace("-", " ")),
                re.escape(code.replace("-", ""))]
    audit = audit_price_attribution(reply, patterns)
    results.append(CriterionResult(
        criterion="control_missing_evidence.no_price_attributed_to_target",
        requirement=(f"no price may be attributed to {code} (prices of OTHER "
                     f"products are legitimate)"),
        passed=not audit.attributed,
        detail=(f"{len(audit.attributed)} price(s) attributed to {code}"
                if audit.attributed else f"no price attributed to {code}"),
        evidence=[f"attributed: {a}" for a in audit.attributed[:3]] +
                 [f"other-product prices (allowed): "
                  f"{[o['price'] for o in audit.other_subject][:4]}",
                  f"in-context disclaimers seen: {audit.disclaimed[:2]}"],
    ))

    addressed = code.lower() in canon(reply) and (
        bool(audit.disclaimed)
        or any(cue in canon(reply) for cue in UNRESOLVED_CUES)
    )
    results.append(CriterionResult(
        criterion="control_missing_evidence.target_addressed",
        requirement=(f"the reply explicitly states {code} is not in the records "
                     f"(or has no price there)"),
        passed=addressed,
        detail=("explicit unresolved statement about the target" if addressed
                else "target not addressed with an explicit not-found statement"),
        evidence=[f"disclaimers: {audit.disclaimed[:2]}",
                  f"target mentioned: {code.lower() in canon(reply)}"],
    ))
    return results


CRITERIA_DISPATCH = {
    "quote": criteria_quote,
    "directional": criteria_directional,
    "derivation": criteria_derivation,
    "control_unrelated_source": criteria_control_unrelated_source,
    "control_missing_evidence": criteria_control_missing_evidence,
}

#: Which stage a failed criterion indicts (used for the quality-side stage).
FAILING_STAGE_BY_CRITERION = {
    "quote.identifies_stored_message": "retrieval",
    "quote.attribution_verified": "retrieval",
    "quote.quoted_from_source": "retrieval",
    "quote.not_reversed": "retrieval",
    "directional.attachment_linked": "retrieval",
    "directional.direction_verified": "retrieval",
    "directional.no_phantom_outbound": "retrieval",
    "derivation.correct_workbook": "retrieval",
    "derivation.correct_row": "retrieval",
    "derivation.formula_chain": "derivation",
    "derivation.no_fabricated_chain": "derivation",
    "derivation.unresolved_reported": "derivation",
    "control_unrelated_source.lookup_evidence": "planning",
    "control_unrelated_source.source_verified_or_disclaimed": "retrieval",
    "control_unrelated_source.no_false_source": "final_generation",
    "control_missing_evidence.target_addressed": "final_generation",
    "control_missing_evidence.no_price_attributed_to_target": "final_generation",
}


def evaluate_case(case: Dict[str, Any], reply: str,
                  ev: EvidenceBundle) -> List[CriterionResult]:
    """Run the case's own criteria — no shared keyword list, no fallback."""
    fn = CRITERIA_DISPATCH[case["key"]]
    spec: Dict[str, Any] = {}
    for key in ("quote", "attachment", "workbook", "source", "target"):
        if key in case:
            spec = case[key]
    try:
        if case["key"] == "derivation":
            return fn(reply, ev)
        return fn(reply, ev, spec)
    except Exception as exc:  # noqa: BLE001 — a criterion bug is a FAIL, not a crash
        return [CriterionResult(
            criterion=f"{case['key']}.criteria_execution",
            requirement="the case criteria must execute",
            passed=False,
            detail=f"{type(exc).__name__}: {exc}",
            evidence=[],
        )]


# ---------------------------------------------------------------------------
# Evidence collection — strictly READ-ONLY
# ---------------------------------------------------------------------------


def _resolve_our_domains(records: Sequence[Dict[str, Any]]) -> List[str]:
    """The operator's own mail domain(s), derived from per-install data.

    Never hardcoded: each domain is scored by its two-way traffic with other
    domains plus the number of distinct addresses it contributes. The mailbox
    owner's domain wins by a wide margin on a real install; the top two scoring
    domains are returned so an install with two company domains still works.
    """
    senders: Dict[str, set] = {}
    outbound: Dict[str, int] = {}
    inbound: Dict[str, int] = {}
    for row in records:
        sd = _domain_of(str(row.get("sender") or ""))
        rd = {_domain_of(a) for a in _addresses_in(str(row.get("recipient") or ""))}
        rd.discard("")
        if sd:
            senders.setdefault(sd, set()).add(str(row.get("sender") or "").lower())
        if sd and rd and any(d != sd for d in rd):
            outbound[sd] = outbound.get(sd, 0) + 1
        for d in rd:
            if sd and d != sd:
                inbound[d] = inbound.get(d, 0) + 1
    scores = {
        d: outbound.get(d, 0) + inbound.get(d, 0) + 5 * len(senders.get(d, ()))
        for d in set(outbound) | set(inbound)
    }
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [d for d, score in ranked[:2] if score >= 20]


def collect_mail_evidence(bundle: EvidenceBundle) -> None:
    """Read the ingested mailbox + attachment ledger (read-only)."""
    try:
        from core.chat_tool_planner import _comms_store_records

        records = _comms_store_records()
    except Exception as exc:  # noqa: BLE001
        bundle.errors.append(f"mail store unavailable: {type(exc).__name__}: {exc}")
        return
    bundle.our_domains = _resolve_our_domains(records)

    attachments: Dict[str, List[tuple]] = {}
    try:
        from core.database import get_db_session
        from core.models import IngestedDocument

        with get_db_session() as db:
            rows = (
                db.query(
                    IngestedDocument.external_id,
                    IngestedDocument.file_name,
                    IngestedDocument.id,
                )
                .filter(IngestedDocument.integration_id == "outlook")
                .all()
            )
        for ext, name, doc_id in rows:
            parent = str(ext or "").split(":", 1)[0]
            if not parent or not name:
                continue
            attachments.setdefault(parent, []).append((str(name), str(doc_id or "")))
    except Exception as exc:  # noqa: BLE001
        bundle.errors.append(
            f"attachment ledger unavailable: {type(exc).__name__}: {exc}")

    for row in records:
        mid = str(row.get("id") or "")
        if not mid:
            continue
        meta = row.get("metadata")
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:  # noqa: BLE001
                meta = None
        text_parts = [str(row.get("subject") or ""), str(row.get("content") or "")]
        if isinstance(meta, dict):
            text_parts.append(str(meta.get("html_body") or ""))
        pairs = attachments.get(mid, [])
        bundle.messages[mid] = StoredMessage(
            message_id=mid,
            sender=str(row.get("sender") or ""),
            recipients=[str(row.get("recipient") or "")],
            subject=str(row.get("subject") or ""),
            timestamp=str(row.get("timestamp") or ""),
            text="\n".join(text_parts),
            sender_name=sender_display_name(meta),
            attachments=[name for name, _ in pairs],
            doc_ids=[doc for _, doc in pairs],
            store_direction=str(row.get("direction") or ""),
        )
        for name, _doc in pairs:
            key = carrier_key(name)
            bundle.carriers.setdefault(key, []).append(mid)

    # Counterparty vocabulary, straight out of the store: tokens of the sender
    # addresses (and domains) that are NOT ours. Used to recognise "…to Seguin"
    # as a claim about an external recipient without hardcoding any name.
    tokens: set = set()
    for msg in bundle.messages.values():
        addr = msg.sender_address
        if not addr or bundle.is_ours(addr):
            continue
        local, _, dom = addr.partition("@")
        for tok in re.split(r"[^a-z0-9]+", local.lower()):
            if len(tok) >= 4 and tok not in ("info", "sales", "admin", "noreply",
                                             "no-reply", "support", "service",
                                             "accounts", "billing", "mail"):
                tokens.add(tok)
        for tok in re.split(r"[^a-z0-9]+", dom.split(".")[0].lower()):
            if len(tok) >= 4:
                tokens.add(tok)
    bundle.counterparty_tokens = sorted(tokens)


_FILE_STOPWORDS = {
    "xlsx", "xls", "xlsm", "pdf", "docx", "doc", "csv", "file", "copy",
    "final", "version", "rev", "attachment",
}


def _file_tokens(name: str) -> List[str]:
    return [
        t.lower() for t in re.split(r"[^0-9A-Za-z]+", str(name or ""))
        if len(t) >= 3 and t.lower() not in _FILE_STOPWORDS
    ]


def carrier_key(name: str) -> str:
    """Canonical key for the attachment→messages index (tokens, sorted)."""
    return " ".join(sorted(_file_tokens(name)))


def collect_dataset_evidence(bundle: EvidenceBundle, query: str) -> None:
    """Read the sheet/dataset catalog (read-only)."""
    try:
        from core.sheet_dataset_service import find_entries_sync

        bundle.datasets = list(find_entries_sync(query) or [])
    except Exception as exc:  # noqa: BLE001
        bundle.errors.append(f"dataset catalog unavailable: {type(exc).__name__}: {exc}")


def collect_workbook_facts(bundle: EvidenceBundle, name: str, target: float,
                           row_number: int = 235) -> None:
    """Read one workbook row + its formula chain out of the store (read-only).

    Nothing is assumed: the row is located in the Parquet by ``__sheet_row``,
    the sheet name comes from the catalog entry, and the chain comes from the
    formula sidecar (an unresolvable cell is reported, never guessed).
    """
    try:
        import pandas as pd

        from core.sheet_dataset_service import (
            find_entries_sync,
            load_formulas_for_parquet,
        )
    except Exception as exc:  # noqa: BLE001
        bundle.errors.append(
            f"workbook readers unavailable: {type(exc).__name__}: {exc}")
        return
    try:
        entries = [
            e for e in (find_entries_sync(name) or [])
            if str(e.get("file_name") or "").lower().startswith(name.lower())
            and str(e.get("parquet_path") or "")
        ]
        if not entries:
            bundle.errors.append(f"no dataset entry for workbook {name!r}")
            return
        entry = entries[0]
        df = pd.read_parquet(entry["parquet_path"])
        formulas = load_formulas_for_parquet(entry["parquet_path"])
        target_row = None
        if "__sheet_row" in df.columns:
            hits = df[df["__sheet_row"].astype(float) == float(row_number)]
            if not len(hits):
                bundle.errors.append(
                    f"row {row_number} not present in {entry.get('file_name')}")
                return
            target_row = hits.iloc[0]
        else:
            for _, candidate in df.iterrows():
                if any(isinstance(v, (int, float)) and abs(float(v) - float(target)) < 0.5
                       for v in candidate.values):
                    target_row = candidate
                    break
        if target_row is None:
            bundle.errors.append("target row not found in workbook")
            return

        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        columns = list(df.columns)
        values: Dict[str, Any] = {}
        cell_values: Dict[str, float] = {}
        for i, col in enumerate(columns):
            letter = letters[i] if i < len(letters) else f"c{i}"
            val = target_row[col]
            values[f"{letter} ({col})"] = None if pd.isna(val) else val
            try:
                if not pd.isna(val):
                    cell_values[f"{letter}{row_number}"] = float(val)
            except (TypeError, ValueError):
                continue

        row_formulas = {
            str(cell): str(expr) for cell, expr in formulas.items()
            if re.match(rf"^[A-Z]{{1,3}}{row_number}$", str(cell))
        }

        def _label(cell: str) -> str:
            m = re.match(r"^([A-Z]{1,3})", cell)
            if not m:
                return cell
            idx = 0
            for ch in m.group(1):
                idx = idx * 26 + (ord(ch) - ord("A") + 1)
            idx -= 1
            return str(columns[idx]) if 0 <= idx < len(columns) else m.group(1)

        steps: List[WorkbookStep] = []
        allowed: List[float] = [float(row_number)]
        for cell in sorted(row_formulas):
            expr = row_formulas[cell]
            body = expr.lstrip("=").strip()
            value = cell_values.get(cell)
            # Strip cell references before reading constants, or "=N235*O235"
            # would contribute 235 as if it were a factor.
            constants = [
                float(n) for n in re.findall(r"\d+(?:\.\d+)?",
                                             re.sub(r"[A-Z]{1,3}\d+", " ", body))
            ]
            upper = body.upper()
            if upper.startswith("ROUNDUP") or upper.startswith("ROUND"):
                kind, const = "round", None
            elif re.fullmatch(r"[A-Z]{1,3}\d+", body):
                kind, const = "identity", None
            elif "*" in body:
                kind, const = "factor", (constants[-1] if constants else None)
            elif "/" in body:
                kind, const = "factor", (constants[-1] if constants else None)
            elif "+" in body:
                kind, const = "offset", (constants[-1] if constants else None)
            else:
                kind, const = "other", None
            allowed.extend(constants)
            if value is not None:
                allowed.append(value)
            steps.append(WorkbookStep(
                cell=cell, label=_label(cell), expression=expr, value=value,
                kind=kind, constant=const,
            ))

        product = ""
        for key in ("Product Name", "Product", "Description"):
            if key in df.columns and not pd.isna(target_row[key]):
                product = str(target_row[key])
                break
        list_value = None
        for key in ("LIST Price", "List Price", "Price"):
            if key in df.columns:
                try:
                    list_value = float(target_row[key])
                    break
                except (TypeError, ValueError):
                    continue

        unresolved = [
            f"{s.cell} ({s.label})" for s in steps
            if s.value is None and s.kind in ("other", "identity")
        ]
        sheets_in_file = [
            e for e in (find_entries_sync(name) or [])
            if str(e.get("file_name") or "") == str(entry.get("file_name") or "")
        ]
        sheet_count = len(sheets_in_file) or 1
        bundle.workbook = WorkbookFacts(
            file_name=str(entry.get("file_name") or ""),
            dataset_name=str(entry.get("dataset_name") or ""),
            sheet_name=str(entry.get("entity_name") or entry.get("sheet_name") or ""),
            row_number=row_number,
            product=product,
            target_value=float(list_value if list_value is not None else target),
            sheet_count=sheet_count,
            values=values,
            formulas=row_formulas,
            steps=steps,
            allowed_numbers=sorted(set(allowed)),
            unresolved_cells=unresolved,
        )
    except Exception as exc:  # noqa: BLE001 — evidence failure is reported, not raised
        bundle.errors.append(f"workbook read failed: {type(exc).__name__}: {exc}")


def _fetch_trace(base: str, token: str, session_id: Optional[str],
                 since_iso: Optional[str]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Read the persisted turn trace (GET, read-only)."""
    if not session_id:
        return [], "no session id"
    try:
        r = httpx.get(f"{base}/api/chat/trace/{session_id}",
                      headers={"Authorization": f"Bearer {token}"},
                      params={"limit": 10}, timeout=20)
        if r.status_code != 200:
            return [], f"trace HTTP {r.status_code}"
        payload = r.json()
    except Exception as exc:  # noqa: BLE001
        return [], f"{type(exc).__name__}: {exc}"
    steps: List[Dict[str, Any]] = []
    for run in payload.get("runs") or []:
        started = str(run.get("started_at") or "")
        if since_iso and started and started < since_iso:
            continue
        for step in run.get("steps") or []:
            steps.append({**step, "run_id": run.get("execution_id"),
                          "run_started_at": started})
    return steps, None


def _canvas_fingerprint() -> Dict[str, Any]:
    """Read-only fingerprint of the incident canvas, so the report can show
    whether the replay touched the artifact under investigation."""
    try:
        import hashlib

        from core.database import get_db_session
        from core.models import Canvas, CanvasAudit

        with get_db_session() as db:
            canvas = db.query(Canvas).filter(Canvas.id == CANVAS_ID).first()
            audits = db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == CANVAS_ID).count()
        if canvas is None:
            return {"found": False}
        blob = json.dumps(canvas.content, sort_keys=True, default=str)
        return {
            "found": True,
            "content_sha256": hashlib.sha256(blob.encode()).hexdigest()[:16],
            "updated_at": str(getattr(canvas, "updated_at", "")),
            "audit_rows": audits,
        }
    except Exception as exc:  # noqa: BLE001
        return {"found": None, "error": f"{type(exc).__name__}: {exc}"}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _mint_token() -> Optional[str]:
    """An operator token for the local install (the operator's own machine).

    The repo env files MUST be loaded in the SERVER's own order, or the token is
    signed with the wrong key and every request 401s. ``main_api_app`` does:

        load_dotenv(backend/.env)
        load_dotenv(project_root/.env)             # no override
        load_dotenv(project_root/.env.local, override=True)

    So ``backend/.env``'s SECRET_KEY wins over the root one. Reading only the
    root `.env` (and, failing that, ``data/.dev_secret_key``) produced
    well-formed tokens the server rejected — the first two runs of this script
    failed exactly that way, on every case.
    """
    try:
        try:
            from dotenv import load_dotenv

            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            project_root = os.path.dirname(backend_dir)
            load_dotenv(os.path.join(backend_dir, ".env"))
            load_dotenv(os.path.join(project_root, ".env"))
            load_dotenv(os.path.join(project_root, ".env.local"), override=True)
        except Exception:  # noqa: BLE001 — env may already be correct
            pass

        from core.auth import create_access_token
        from core.database import get_db_session
        from core.models import User

        with get_db_session() as db:
            user = (db.query(User)
                    .filter(User.email == "admin@example.com").first())
            if user is None:
                return None
            uid, email = str(user.id), user.email
            role = getattr(user, "role", None)
            role = getattr(role, "value", role)
        return create_access_token({
            "sub": uid, "user_id": uid, "email": email,
            "role": str(role or "workspace_admin"),
        })
    except Exception as exc:  # noqa: BLE001
        print(f"token mint failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None


def _identity(base: str) -> Dict[str, Any]:
    try:
        r = httpx.get(f"{base}/api/health", timeout=10)
        data = r.json()
        return data.get("identity", data)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


def _serving_instance(headers: Any, metadata: Any,
                      fallback: Dict[str, Any]) -> Dict[str, Any]:
    """Per-request attribution: header → metadata → pre-run health identity."""
    header_val = None
    try:
        header_val = headers.get("X-Atom-Serving-Instance") if headers else None
    except Exception:  # noqa: BLE001
        header_val = None
    meta_val = metadata.get("serving_instance") if isinstance(metadata, dict) else None
    if header_val:
        return {"value": header_val, "source": "header:X-Atom-Serving-Instance"}
    if meta_val:
        return {"value": meta_val, "source": "metadata.serving_instance"}
    return {"value": fallback, "source": "pre_run_health_fallback"}


async def _run_case(client: httpx.AsyncClient, base: str, token: str,
                    case: Dict[str, Any], session_id: Optional[str],
                    timeout: float, attempts_max: int,
                    pre_run_identity: Dict[str, Any]) -> Dict[str, Any]:
    context = {
        "canvas": {
            "id": CANVAS_ID,
            "canvas_type": "email",
            "name": "Quote for 52 Inch 16 Gauge Foot Shear",
        },
    }
    payload = {
        "message": case["message"],
        "user_id": "acceptance",
        "session_id": session_id,
        "context": context,
    }
    out: Dict[str, Any] = {
        "key": case["key"],
        "label": case["label"],
        "message": case["message"],
    }
    case_t0 = time.monotonic()
    out["canvas_before"] = _canvas_fingerprint()

    attempt_records: List[Dict[str, Any]] = []
    body: Optional[Dict[str, Any]] = None
    http_status: Optional[int] = None
    transport_error: Optional[str] = None
    headers: Any = None
    for attempt in range(1, attempts_max + 1):
        started = time.monotonic()
        try:
            r = await client.post(f"{base}/api/chat/message", json=payload,
                                  headers={"Authorization": f"Bearer {token}"},
                                  timeout=timeout)
            http_status = r.status_code
            headers = r.headers
            if r.headers.get("content-type", "").startswith("application/json"):
                body = r.json()
            else:
                body = {"message": r.text[:4000]}
            attempt_records.append({
                "attempt": attempt,
                "outcome": f"http_{r.status_code}",
                "latency_s": round(time.monotonic() - started, 1),
            })
            transport_error = None
            break
        except Exception as exc:  # noqa: BLE001
            transport_error = f"{type(exc).__name__}: {exc}"
            attempt_records.append({
                "attempt": attempt,
                "outcome": "transport_error",
                "latency_s": round(time.monotonic() - started, 1),
                "error": transport_error[:300],
            })
            # Another agent may restart the backend mid-run; a dead socket is
            # retried and EVERY attempt is preserved separately in the report.
            await asyncio.sleep(3)
    request_s = round(time.monotonic() - case_t0, 1)

    body = body or {}
    reply = str(body.get("message") or body.get("response") or "")
    metadata = body.get("metadata")
    trace_t0 = time.monotonic()
    steps, trace_error = _fetch_trace(base, token, body.get("session_id"),
                                      out["canvas_before"].get("updated_at"))
    trace_s = round(time.monotonic() - trace_t0, 1)

    out.update({
        "http": http_status,
        "reply": reply[:6000],
        "session_id": body.get("session_id") or session_id,
        "execution_id": body.get("execution_id"),
        "intent": body.get("intent"),
        "success": body.get("success"),
        "error_code": body.get("error_code"),
        "route": {
            # The route that ACTUALLY answered, plus what was requested when
            # the response carries it (streaming legs report both).
            "provider": body.get("provider"),
            "model": body.get("model"),
            "requested_provider": body.get("requested_provider"),
            "requested_model": body.get("requested_model"),
        },
        "serving_source": headers.get("X-Atom-Source") if headers else None,
        "serving_instance": _serving_instance(headers, metadata, pre_run_identity),
        "metadata_keys": sorted(metadata.keys()) if isinstance(metadata, dict) else None,
        "metadata": json.loads(json.dumps(metadata, default=str)[:4000])
        if metadata is not None else None,
        "attempts": attempt_records,
        "retry_note": (
            "the chat API does not expose a provider-retry count in the response; "
            f"the attempts listed are the {len(attempt_records)} HTTP attempt(s) "
            "this harness made for the case"
        ),
        "transport_error": transport_error,
        "trace_error": trace_error,
    })

    ev = EvidenceBundle(trace_steps=steps, trace_error=trace_error)
    evidence_t0 = time.monotonic()
    collect_mail_evidence(ev)
    if case["key"] == "control_unrelated_source":
        collect_dataset_evidence(ev, case["source"]["name"])
    if case["key"] == "derivation":
        collect_dataset_evidence(ev, case["workbook"]["name"])
        collect_workbook_facts(ev, case["workbook"]["name"],
                               case["workbook"]["target_value"],
                               case["workbook"].get("row_number", 235))
    evidence_s = round(time.monotonic() - evidence_t0, 1)

    delivery = classify_delivery(http_status, body, transport_error, steps,
                                 case["key"])
    # Quality is only assessed when a real answer came back: scoring criteria
    # against a provider-failure sentinel would dress an availability failure up
    # as a bad answer, which is exactly what this revision must not do.
    criteria = evaluate_case(case, reply, ev) \
        if delivery["outcome"] == "answered" else []
    quality = aggregate_quality(delivery, criteria)
    # A fresh identity read AFTER the turn: a restart between cases must be
    # visible in the report instead of averaged away.
    out["per_case_health_identity"] = _identity(base)

    out["canvas_after"] = _canvas_fingerprint()
    out["canvas_mutated"] = out["canvas_before"] != out["canvas_after"]
    out["delivery"] = delivery
    out["quality"] = quality
    out["criteria"] = [c.to_dict() for c in criteria]
    out["timings"] = {
        "request_s": request_s,
        "trace_s": trace_s,
        "evidence_s": evidence_s,
        "total_s": round(time.monotonic() - case_t0, 1),
        "first_attempt_s": attempt_records[0]["latency_s"] if attempt_records else None,
        "backend_steps": [
            {
                "step_type": s.get("step_type"),
                "action": s.get("action"),
                "duration_ms": s.get("duration_ms"),
                "observation": str(s.get("observation") or "")[:200],
            }
            for s in steps
        ],
    }
    out["latency_s"] = request_s
    out["evidence_checked"] = {
        "store_messages": len(ev.messages),
        "our_domains": ev.our_domains,
        "attachment_carriers": {k: len(v) for k, v in ev.carriers.items()},
        "datasets": [d.get("file_name") for d in ev.datasets][:8],
        "workbook": (f"{ev.workbook.file_name} row {ev.workbook.row_number} "
                     f"({ev.workbook.sheet_name}) formulas="
                     f"{len(ev.workbook.formulas)}" if ev.workbook else None),
        "trace_steps": len(steps),
        "errors": ev.errors,
    }
    out["verdict"] = (
        "PASS" if delivery["outcome"] == "answered" and quality["outcome"] == "pass"
        else ("NOT_EVALUATED" if quality["outcome"] == "not_evaluated" else "FAIL")
    )
    return out


async def main_async(args) -> int:
    base = f"http://127.0.0.1:{args.port}"
    token = _mint_token()
    if not token:
        print("could not mint an operator token; aborting", file=sys.stderr)
        return 2
    pre_run_identity = _identity(base)
    print(f"pre-run serving process: {json.dumps(pre_run_identity)}")

    cases = [c for c in CASES if not args.only or c["key"] in args.only]
    results: List[Dict[str, Any]] = []
    session_id: Optional[str] = None
    async with httpx.AsyncClient() as client:
        for case in cases:
            res = await _run_case(client, base, token, case, session_id,
                                  args.timeout, args.attempts, pre_run_identity)
            if res.get("session_id"):
                session_id = res["session_id"]
            results.append(res)
            print(f"[{res['verdict']:>13}] {res['key']:26} "
                  f"http={res.get('http')} {res['latency_s']}s "
                  f"delivery={res['delivery']['outcome']} "
                  f"quality={res['quality']['outcome']} "
                  f"route={res['route']['provider']}/{res['route']['model']} "
                  f"instance={str(res['serving_instance']['value'])[:60]} "
                  f"({res['serving_instance']['source']})")
            for crit in res["criteria"]:
                mark = "ok  " if crit["passed"] else "FAIL"
                print(f"      {mark} {crit['criterion']}: {crit['detail']}")
    report = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "port": args.port,
        "base": base,
        "pre_run_serving_process": pre_run_identity,
        "canvas_id": CANVAS_ID,
        "scoring": "explicit per-case acceptance criteria; delivery scored "
                   "separately from quality",
        "results": results,
        "passed": sum(1 for r in results if r["verdict"] == "PASS"),
        "failed": sum(1 for r in results if r["verdict"] == "FAIL"),
        "not_evaluated": sum(1 for r in results if r["verdict"] == "NOT_EVALUATED"),
        "total": len(results),
        "canvas_mutated": any(r.get("canvas_mutated") for r in results),
    }

    # RUN-LEVEL VALIDITY. Per-case identity is recorded, but a run split across
    # processes still printed a pass COUNT, and a count reads as a result. Two
    # runs of this suite were split exactly that way (a backend died mid-run and
    # its successor answered the remaining cases); the counts (3/5, then 0
    # deliverable) were noise, not verdicts. A run is only a verdict when every
    # case was ANSWERED and every answer came from ONE serving instance.
    _instances = []
    for _r in results:
        _si = _r.get("serving_instance")
        _val = _si.get("value") if isinstance(_si, dict) else _si
        if _val:
            _instances.append(str(_val))
    report["distinct_serving_instances"] = sorted(set(_instances))
    _reasons = []
    if len(set(_instances)) > 1:
        _reasons.append(
            f"the run was served by {len(set(_instances))} different backend "
            "instances (a restart happened mid-run)")
    if report["not_evaluated"]:
        _reasons.append(
            f"{report['not_evaluated']} case(s) were never evaluated "
            "(transport error / no delivery)")
    if not _instances:
        _reasons.append("no serving instance could be identified")
    report["run_invalid_reasons"] = _reasons
    report["run_valid"] = not _reasons

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
    print(f"\n{report['passed']}/{report['total']} acceptance cases passed "
          f"({report['failed']} failed, {report['not_evaluated']} not evaluated)")
    if report["canvas_mutated"]:
        print("WARNING: the incident canvas changed during this run — inspect "
              "canvas_before/canvas_after in the JSON report")
    if not report["run_valid"]:
        print("RUN INVALID — do not read the count above as a verdict:")
        for _reason in _reasons:
            print(f"  - {_reason}")
        return 2
    return 0 if report["passed"] == report["total"] else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8001,
                    help="backend port the UI uses (default 8001)")
    ap.add_argument("--only", action="append", default=None,
                    help="run only these case keys (repeatable)")
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--attempts", type=int, default=2,
                    help="HTTP attempts per case (a dead socket is retried; "
                         "every attempt is reported separately)")
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
