# -*- coding: utf-8 -*-
"""Target-set resolution for follow-up asks (2026-09-30).

The architectural defect this module exists for (owner analysis of the
2026-09-30 'check the other machinery' incident): the app mistook
"related to the previous task" for "repeat the previous task."
``_resolve_active_items`` inherits the previous objective's items when
the current message names no explicit codes — correct for "check those
again", wrong for "check the OTHER machinery", which is a CONTRASTIVE
reference: same domain, different target set. The distinction must be
made BEFORE retrieval, and when it cannot be made the turn must ASK,
not silently inherit.

Design (per the owner's directive — a general mechanism, not a regex
for one sentence):

1. DETECT the contrastive grammar generically: "the other <NP>",
   "the rest of <NP>", "the remaining <NP>", "everything/all <NP>
   except|besides|other than <NP>", "not <NP>". The category noun is
   never matched against a fixed list — any noun phrase qualifies.
2. RESOLVE the base set against TYPED candidates, in authority order:
   the conversation's canvas/draft item list (the quote the user is
   looking at), then the stored objective's items. Resolution must be
   unambiguous: when the candidates disagree and neither contains the
   other, the turn clarifies instead of guessing.
3. APPLY the contrast semantics: the base set minus what the
   conversation already served and minus anything the message itself
   excludes. An empty result clarifies (a one-item set has no
   "others").
4. FAIL CLOSED: every unresolved shape returns ``{"kind": "clarify"}``
   with the question to ask — the caller must NOT run a read on
   inherited items.

Pure functions only: no retrieval, no DB, no LLM. The orchestrator
supplies candidate sets extracted from ITS state (canvas body, stored
task, last delivered result); this module decides.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

__all__ = [
    "detect_contrastive_reference",
    "extract_items_from_text",
    "resolve_target_set",
]

# CONTRASTIVE GRAMMAR (generic across category nouns and domains).
# Group names: cat = the category noun phrase; excl = explicitly
# excluded items ("except the 381"). The markers are the closed set;
# the noun phrase is open.
_CONTRASTIVE_RE = re.compile(
    r"\b(?:the\s+)?(?:other|remaining|rest\s+of\s+the|remaining)\s+"
    r"(?P<cat>[a-z][a-z0-9 &/'-]{2,40})"
    r"|\b(?:all|everything|the\s+rest)(?:\s+[a-z][a-z0-9 &/'-]{2,40})?"
    r"\s+(?:except|besides|but|other\s+than|apart\s+from)\s+(?P<excl1>.{2,60})"
    r"|\b(?:not|excluding|without)\s+(?P<excl2>the\s+.{2,60})",
    re.IGNORECASE,
)

# Words that end the category noun phrase.
_CAT_STOP = re.compile(
    r"\s+(?:in|on|from|of|for|with|against|to|and\s+verify|and\s+check|"
    r"and\s+see|then|please|now)\b", re.IGNORECASE)


def detect_contrastive_reference(text: str) -> Optional[Dict[str, str]]:
    """The contrastive marker and category in `text`, or None.

    Returns ``{"marker": ..., "category": ..., "excluded_text": ...}``.
    Purely grammatical — resolution against candidate sets happens in
    :func:`resolve_target_set`.
    """
    t = " ".join(str(text or "").split())
    if not t:
        return None
    m = _CONTRASTIVE_RE.search(t)
    if m is None:
        return None
    cat = (m.group("cat") or "").strip()
    excluded_text = (m.group("excl1") or m.group("excl2") or "").strip()
    if not cat and not excluded_text:
        return None
    if cat:
        stop = _CAT_STOP.search(cat)
        if stop:
            cat = cat[:stop.start()].strip()
    marker = (
        "except" if (m.group("excl1") or m.group("excl2")) else "other")
    return {
        "marker": marker,
        "category": cat,
        "excluded_text": excluded_text,
    }


def extract_items_from_text(text: str) -> List[str]:
    """Model/item codes in a text, via the workbook extractor.

    Used on canvas/draft bodies (typed candidate base sets) and on the
    user's message (items the message itself names, e.g. after
    'except'). Canvas markup is cleaned first: HTML tags stripped,
    common entities decoded, and the backslash-uXXXX escapes JSON embedding
    leaves in stored bodies normalized (live 2026-10-01: a real quote
    canvas yielded 'u20135'/'u20138' junk items from encoded en-dashes).
    Multi-word PROSE fragments (product descriptions, company names,
    header text) are not item codes — only single tokens and short
    alphanumeric codes survive; the tokens that matter ('No. 381',
    'U-22', 'GSL48-16') all do. Deduplicates case-insensitively,
    preserves order.
    """
    from core.workbook_read_artifact import extract_targets

    cleaned = re.sub(r"<[^>]+>", " ", str(text or ""))
    cleaned = (cleaned.replace("&nbsp;", " ").replace("&amp;", "&")
               .replace("&#8211;", "-").replace("&ndash;", "-")
               .replace("&mdash;", "-").replace("&rsquo;", "'"))
    cleaned = re.sub(r"u20[0-9a-fA-F]{2}", "-", cleaned)
    raw_items = extract_targets(cleaned, [], [])

    # IDENTITY-SHAPE RULES (2026-10-01 live finding on the quote
    # canvas): '36' in 'Roper Whitney 36" No. 381' is a SPECIFICATION,
    # not an item — the read then probed a bare '36' and matched every
    # sheet containing 36 anywhere. Domain-neutral signals:
    #   1. IDENTIFIER-PREFIXED tokens are items regardless of shape
    #      (No. 381, SKU 12, Model 7 — cross-domain conventions).
    #   2. ALPHANUMERIC-MIXED tokens are items (U-22, SLE24-16, R-102).
    #   3. Bare numerics are items only when >= 4 digits (real numeric
    #      SKUs) — short bare numbers are dimensions/quantities/row
    #      indices unless rule 1 claimed them.
    # (Unit-marked specs are already gone: '36"' style tokens do not
    # survive markup cleanup as bare item candidates.)
    identifier_prefix = re.compile(
        r"(?:\bno\.?|\bmodel\b|\bsku\b|\bpart(?:\s+no)?|"
        r"\bitem\b|\bcode\b|\bm/n\b|\bp/n\b|\bref\.?)\s*$",
        re.IGNORECASE)
    out: List[str] = []
    seen = set()
    for item in raw_items:
        token = str(item).strip()
        if len(token) > 18 or (
                " " in token and not re.search(r"\d", token)):
            continue
        m = re.search(r"\d+", token)
        if not m:
            continue  # item codes carry a digit
        core = m.group(0)
        pos = cleaned.find(token)
        window = cleaned[max(0, pos - 12):pos] if pos >= 0 else ""
        prefixed = bool(identifier_prefix.search(window))
        mixed_alnum = bool(re.search(r"[A-Za-z]", token))
        if (not mixed_alnum and len(core) < 4 and not prefixed):
            continue
        key = token.lower()
        if key and key not in seen:
            seen.add(key)
            out.append(token)
    return out


#: Outcome-referenced subsets: 'the ones not found', 'the missing
#: machinery', 'the incomplete ones', 'the ones without prices' — the
#: user points at a RESULT STATE of the conversation's own reads instead
#: of naming items. Deterministic floor; the statuses map to the read's
#: identity statuses ('none' = absent in the artifact's vocabulary).
_OUTCOME_SUBSET_RE = re.compile(
    r"\b(?:ones?|items?|machinery|machines?|models?|parts?|prices?|"
    r"pricing)\b"
    r"[^.;!?\n]{0,30}\b(?:not\s+found|missing|absent|incomplete|"
    r"not\s+complete|without\s+prices?|unpriced|still\s+open|"
    r"unresolved|outstanding|nothing\s+(?:was\s+|were\s+|is\s+|are\s+)?"
    r"found|not\s+resolved|no\s+result)\b"
    r"|\b(?:not\s+found|missing|absent|incomplete|not\s+complete|"
    r"unpriced|still\s+open|unresolved|outstanding|"
    r"nothing\s+(?:was\s+|were\s+|is\s+|are\s+)?found|not\s+resolved|"
    r"no\s+result)\b"
    r"[^.;!?\n]{0,20}\b(?:ones?|items?|machinery|machines?|models?|"
    r"parts?|prices?|pricing)\b"
    r"|\bwhat\s+machinery\s+was\s+not\s+found\b",
    re.IGNORECASE,
)


def outcome_referenced_items(
    message: str,
    conversation_id: Optional[str] = None,
) -> List[str]:
    """The items a result-state reference points at ('the ones not
    found') — resolved from the conversation's durable read outcomes,
    never from the user re-typing codes. Absent items first (that is
    what 'not found' means), then ambiguous (unconfirmed — 'incomplete'
    covers them); found-only items never ride. [] when the message
    carries no outcome reference or the ledger holds no outcomes
    (fail-closed: the normal lanes own the turn)."""
    if not _OUTCOME_SUBSET_RE.search(message or ""):
        return []
    if not conversation_id:
        return []
    try:
        from core import dialogue_state as _ds

        outcomes = _ds.active_item_outcomes(conversation_id)
    except Exception:  # noqa: BLE001 — ledger optional
        return []
    absent = [i for i, s in outcomes.items() if s == "none"]
    ambiguous = [i for i, s in outcomes.items() if s == "multiple"]
    # preserve the objective's order when available
    try:
        order = [
            i for i in _ds.active_objective_items(conversation_id)]
    except Exception:  # noqa: BLE001
        order = []
    rank = {i: n for n, i in enumerate(order)}
    absent.sort(key=lambda i: rank.get(i, 10_000))
    ambiguous.sort(key=lambda i: rank.get(i, 10_000))
    return absent + ambiguous


def resolve_target_set(
    message: str,
    *,
    canvas_items: Optional[Sequence[str]] = None,
    prior_items: Optional[Sequence[str]] = None,
    last_served_items: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Resolve a contrastive follow-up to the concrete set it refers to.

    Returns one of:

    - ``{"kind": "none"}`` — the message is not contrastive; the caller
      keeps its normal item resolution.
    - ``{"kind": "resolved", "items": [...], "origin": "canvas" |
      "prior_objective", "base_size": n, "excluded": [...]}`` — the set
      to investigate, replacing any inherited items.
    - ``{"kind": "clarify", "question": str, "candidate_sets": {...}}``
      — the target set could not be resolved unambiguously; the caller
      must ask, NOT read.

    "Other/remaining/rest" semantics: base minus the items the
    conversation already served (``last_served_items``) minus items the
    message itself names or excludes.
    """
    contrast = detect_contrastive_reference(message)
    if contrast is None:
        return {"kind": "none"}

    canvas = [str(i).strip() for i in (canvas_items or []) if str(i).strip()]
    prior = [str(i).strip() for i in (prior_items or []) if str(i).strip()]
    served = [str(i).strip() for i in (last_served_items or [])
              if str(i).strip()]

    def _norm(items: Sequence[str]) -> List[str]:
        seen: set = set()
        out: List[str] = []
        for i in items:
            key = re.sub(r"[\s._-]+", "", i.lower())
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(i)
        return out

    def _matches_any(norm: str, excluded: set) -> bool:
        # Subsumption both ways with a length floor: the served item may
        # be spelled shorter ("381") than the base item ("No. 381") or
        # longer; a 2-char floor keeps "38" from excluding "381".
        for ex in excluded:
            if norm == ex or (len(ex) >= 2 and ex in norm) or (
                    len(norm) >= 2 and norm in ex):
                return True
        return False

    canvas_n, prior_n = _norm(canvas), _norm(prior)

    # BASE PRECEDENCE (2026-10-01 live finding): the CANVAS — the live
    # document the user is looking at — is the authoritative base when
    # it carries a real item list; the prior objective is HISTORY (and
    # can be stale: a superseded extraction-era set once outranked the
    # fresh draft purely by being larger, re-importing its junk). The
    # objective is the fallback when no canvas list exists. Disjoint
    # sets do not clarify here: with the draft open, 'the other
    # machinery' means the draft's.
    if len(canvas_n) >= 2:
        base, origin = canvas, "canvas"
    elif len(prior_n) >= 2:
        base, origin = prior, "prior_objective"
    else:
        # No candidate base can give an "other" — asking beats reading
        # the one item the user explicitly moved past.
        return {
            "kind": "clarify",
            "question": (
                "Which items should I check? I don't have a list of "
                "other items to work from in this conversation yet."),
            "candidate_sets": {},
        }

    base_norms = _norm(base)

    def _message_exclusions() -> set:
        """Items of THIS base the message itself names or excludes.

        Two lanes, unioned: the item extractor (identifier-prefixed,
        alnum-mixed, bare >=4 digits) and BASE-AWARE LITERAL MATCHING
        (2026-10-01 flagged gap): 'except 622' names a bare 3-digit code
        the extractor deliberately drops — but we are not mining new
        items here, we are recognizing which KNOWN base items the user
        moved past, so a word-boundary literal hit on a base item counts.
        This cannot reopen the '36' junk class: only tokens that ARE
        base items match.
        """
        out: set = set()
        for item in extract_items_from_text(message):
            out |= set(_norm([item]))
        for item in extract_items_from_text(
                contrast.get("excluded_text") or ""):
            out |= set(_norm([item]))
        span = f"{message} {contrast.get('excluded_text') or ''}"
        for i, n in zip(base, base_norms):
            if not i or not n or n in out:
                continue
            if re.search(
                    rf"(?<![\w-]){re.escape(str(i))}(?![\w-])",
                    span, re.IGNORECASE):
                out.add(n)
        return out

    excluded_norm = set(_norm(served)) | _message_exclusions()

    resolved = [
        i for i, n in zip(base, base_norms)
        if not _matches_any(n, excluded_norm)]

    if not resolved:
        # REFRESH-OPERATIVE RE-CHECK (2026-10-01 live, e2e replay): an
        # EXPLICIT re-retrieval / source-freshness request over a set we
        # just served is a RE-CHECK of that set against the latest
        # source — not a request for new items. Live: 'check the other
        # machinery from price list and verify if any pricing needs to
        # be updated from latest pricing data' arrived right after the
        # full 8-item set was served; 'other' made it contrastive, the
        # whole base was already served, and the clarify branch answered
        # 'which other items should I check?' — a question the user did
        # not ask, while their re-verification never ran. When the
        # message itself asks for the re-check, resolve to the base
        # minus only the items the MESSAGE names/excludes.
        try:
            from core.pending_file_task import (
                is_retrieval_refresh_request,
            )

            if is_retrieval_refresh_request(message):
                _msg_excluded = _message_exclusions()
                recheck = [
                    i for i, n in zip(base, base_norms)
                    if not _matches_any(n, _msg_excluded)]
                if recheck:
                    return {
                        "kind": "resolved",
                        "items": recheck,
                        "origin": f"{origin}_recheck",
                        "base_size": len(base),
                        "excluded": [i for i, n in zip(base, base_norms)
                                     if _matches_any(n, _msg_excluded)],
                    }
        except Exception:  # noqa: BLE001 — clarify remains the floor
            pass
        return {
            "kind": "clarify",
            "question": (
                "That set only contained the item(s) we just covered — "
                "which other items should I check?"),
            "candidate_sets": {origin: list(base)},
        }
    return {
        "kind": "resolved",
        "items": resolved,
        "origin": origin,
        "base_size": len(base),
        "excluded": [i for i, n in zip(base, base_norms)
                     if _matches_any(n, excluded_norm)],
    }
