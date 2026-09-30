"""Answer presentation — slice 1 (review rounds 27-28 work order).

PURPOSE. The workbook answer collapsed three concerns into one text blob:
what the evidence establishes, how it is presented, and what a follow-up
asks for. This module separates presentation from evidence: a PURE
renderer consumes a structured presentation contract plus presentation
preferences and returns a readable answer. No retrieval, no database
writes, no evidence mutation. Detailed evidence stays out of the main
answer (the evidence block / evidence UI remains its home).

CONTRACT (pres-v2). Input is the scan layer's per-target outcome -
identity status, field-selection status, typed values with their original
column labels and bases, source references - plus the ordered requested
items and a source block (workbook identity, saved-copy date, live-vs-
saved, coverage). Evidence revision and presentation version are stamped
on the result so stored answers are traceable to both.

MEANING RULES (work order section 4): aliases aid matching without
becoming extra items; multiple cells in one matched row are one
candidate, but genuinely different rows stay distinct candidates; price
bases (PRICE / U.S. LIST / Factory Price / FULL COST CDN) never collapse;
no field is silently chosen - labeled alternatives or one focused
clarification; zero stays zero; blank is stated plainly; non-finite is
unavailable, never nan; uncertainty is stated once; missing items never
imply absence from the live workbook.

RETRIEVAL FAILURE IS NOT ABSENCE (2026-09-26). "No candidate row" and "the
source would not open" are both an empty evidence list, so the target
carries the scan's read verdict (``retrieval``) alongside its identity
verdict. When retrieval failed, the item is reported as a READ FAILURE with
the scan's error CATEGORY and the honest-absence sentence is withheld: a
negative nobody could verify is not a negative. A target that was searched
successfully and genuinely is not there keeps the absence wording.

COMPAT PATH. present_from_rendered_text rebuilds the contract from a
legacy rendered answer (text parsing). It is explicitly COMPATIBILITY
COVERAGE for records that stored only text - it cannot validate the
artifact-native path and is not evidence reconstruction.
"""
from __future__ import annotations

import math
import copy
import re
from typing import Any, Dict, List, Optional, Sequence

PRESENTATION_VERSION = "pres-v2"

# Retrieval verdict carried per target (mirrors the scan's read-leg
# vocabulary). ``searched`` means the source opened and was searched, so an
# empty result is a real negative; ``failed`` means it did not open.
RETRIEVAL_SEARCHED = "searched"
RETRIEVAL_FAILED = "failed"

# Error categories in user-legible words. The category itself (never
# ``str(exception)``) is what reaches the user, and it is rendered here
# rather than in the scan so the wording lives with the presentation.
_READ_FAILURE_REASONS = {
    "source_corrupt": "the stored copy is damaged or not a readable workbook",
    "source_missing": "the stored copy is no longer available",
    "source_unavailable": "the stored copy could not be opened",
    "access_denied": "access to the stored copy was refused",
    "timeout": "reading the stored copy timed out",
    "configuration": "the reader for this copy is not available",
    "unknown": "the reason is unknown",
}
# The scan layer's per-target status for "the source would not open"
# (workbook_read_artifact.TARGET_UNAVAILABLE). Spelled here because the scan
# module is imported lazily by this renderer.
_SCAN_UNAVAILABLE = "unavailable"

_CITE_RE = re.compile(r"([A-Za-z][A-Za-z0-9 .&'-]*?)\s*!\s*([A-Z]{1,3}\d{1,7})")
_PAIR_RE = re.compile(
    r"([A-Z]{1,3}\d{1,7})\s*=\s*(-?\$?[\d,]+(?:\.\d+)?|)\s*\[basis=([^\];]+)")

#: How many candidates an ambiguous item shows before the confirmation ask.
AMBIGUOUS_CANDIDATE_WINDOW = 3

#: A sheet-scope browse lists rows; the record holds at most the browse's
#: per-sheet cap, so the listing renders every stored row up to this cap
#: and states the surplus rather than applying a silent window.
LISTING_ROW_CAP = 12
LISTING_VALUE_CAP = 4

#: Value kinds that let a candidate ANSWER a request. A row whose value cells
#: are blank, zero, or unavailable carries no figure — it cannot resolve the
#: question the reader was asked, however well its identity cell matches.
_ANSWERABLE_VALUE_KINDS = frozenset({"number", "text"})


# ---------------------------------------------------------------------------
# SHEET SCOPE — a sheet the READER named is part of the request.
#
# WHY. The visible candidate window is a fixed prefix of the candidate list,
# and the candidate list arrives in SCAN order, which is alphabetical by sheet
# name (`sheet_dataset_service.entries_for_file_sync` orders by
# `entity_name.asc()`). So for an item whose matches span two sheets, the
# alphabetically-first sheet deterministically consumed every display slot and
# the other sheet's rows were unreachable in the answer — regardless of what
# the reader asked for. Live 2026-09-30: "show me the tennsmith sheet
# searches" for No. 381 returned three RoperWhitney rows plus a
# sheet-UNION tail ("+7 more match(es) on RoperWhitney, Tennsmith"), which
# tells the reader a sheet exists but not that five of the seven are on it,
# so the follow-up had nothing to act on.
#
# The scope is a RANKING input, never a filter. Ranking already exists here
# (`_rank_candidates`) and its established discipline is that precedence
# REORDERS and never eliminates — ambiguity survives, the confirmation ask
# survives, and no candidate is dropped from the record. A sheet the reader
# named cannot prove which row is theirs any more than a brand can, so it
# must not narrow the set.
#
# It is deliberately NOT routed through `_disambiguation_criteria`
# (`core.workbook_read_artifact`): that channel is a hard FILTER, and in this
# same incident chain a mined criterion filtered out every candidate twice
# ("Priya's text message" → organization=Priya; "when does A. Kumar's
# certificate expire" → the interrogative possessor). This is a separate
# ranking seam, not a fourth door into the filter.
# ---------------------------------------------------------------------------

#: A sheet REFERENCE in the request's own words. The captured group is the
#: qualifier, not a noun phrase that is trusted as a sheet name — see
#: `resolve_requested_sheets`, which only ever returns names that are already
#: present in the candidate set.
_SHEET_REFERENCE_RE = re.compile(
    r"\b(?:the|this|that|those|my|our|its|their)\s+"
    r"([A-Za-z0-9][A-Za-z0-9 &'./-]{1,39}?)\s+"
    r"(?:sheets?|tabs?|worksheets?)\b"
    r"|\b(?:on|from|in|under|per|across)\s+"
    r"(?:the\s+)?([A-Za-z0-9][A-Za-z0-9 &'./-]{1,39}?)\s+"
    r"(?:sheets?|tabs?|worksheets?)\b",
    re.IGNORECASE,
)

#: Reference words that name a sheet GENERICALLY ("the sheet", "each sheet").
#: They carry no sheet identity, so they must not resolve to one; a reference
#: with no qualifier is not a scope.
_UNQUALIFIED_SHEET_REFERENCE = frozenset({
    "", "same", "other", "another", "first", "second", "third", "last",
    "next", "previous", "same", "that", "this", "those", "these", "one",
    "top", "bottom", "left", "right", "new", "old", "main", "front",
    "back", "above", "below", "whole", "entire", "single", "every",
    "each", "any", "all", "current", "active", "relevant", "matching",
})

#: Minimum qualifier length on BOTH sides before a reference is allowed to
#: match a sheet name. Below this, containment matching turns ordinary words
#: into sheet scopes ("the a sheet" → every sheet whose name contains "a").
#: Mirrors the floor already used to anchor a query token to a sheet name in
#: `integrations.universal_integration_service._query_anchored_excerpt`.
_SHEET_SCOPE_MIN_CHARS = 5


def mentions_sheet_reference(text: str) -> bool:
    """Does `text` refer to a NAMED sheet (as opposed to a workbook, or to a
    sheet generically)?

    The routing-side half of `resolve_requested_sheets`, sharing its regex and
    its unqualified-reference list so the two halves cannot drift. It answers
    only "is this turn sheet-shaped?", never "which sheet?" — the caller at
    that point has a file identity but no sheet catalog, so naming a sheet
    there could only be a guess. Which real sheet is meant is settled later,
    by `resolve_requested_sheets` against the sheets the file actually
    indexes.
    """
    for match in _SHEET_REFERENCE_RE.finditer(str(text or "")):
        phrase = str(match.group(1) or match.group(2) or "").strip()
        if _norm(phrase) not in _UNQUALIFIED_SHEET_REFERENCE:
            return True
    return False


def _sheet_scope_key(value: Any) -> str:
    """Comparable key for a sheet name: casefolded, punctuation and spacing
    collapsed. A reader who types "tenn smith" and a sheet named
    "TennSmith" are one sheet; nothing else is."""
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def resolve_sheet_phrase(phrase: str,
                         sheet_names: Sequence[str]) -> Optional[str]:
    """Resolve ONE already-extracted reference phrase against real sheets,
    or None. The per-phrase half of `resolve_requested_sheets` (same
    floors, same two-way containment, never fabricates), shared so a
    consumer holding a phrase without the surrounding sentence — the typed
    action program's pending ``SheetRef`` — resolves EXACTLY as the
    resolver would have inside the sentence.
    """
    known: List[tuple] = []
    seen_keys = set()
    for name in sheet_names or []:
        text = str(name or "").strip()
        key = _sheet_scope_key(text)
        if not text or not key or key in seen_keys:
            continue
        seen_keys.add(key)
        known.append((text, key))
    if not known:
        return None
    pkey = _sheet_scope_key(phrase)
    if not pkey:
        return None
    for text, key in known:
        shorter, _longer = sorted((len(pkey), len(key)))
        if shorter < _SHEET_SCOPE_MIN_CHARS:
            continue
        if pkey in key or key in pkey:
            return text
    return None


def resolve_requested_sheets(
    query: str,
    sheet_names: Sequence[str],
) -> List[str]:
    """The sheets in `sheet_names` that `query` refers to, in request order.

    RESOLUTION AGAINST KNOWN SHEETS, NOT EXTRACTION. The request's words are
    never taken as a sheet name. Each reference is matched against the sheet
    names that are actually present, so a phrase that names no real sheet
    ("the Tennessee sheet", "the pricing sheet") resolves to nothing and the
    rendering is exactly what it was before — a wrong scope can narrow a
    user's search, so the burden of proof is on the match, never on the
    request.

    Matching is a two-way containment on the collapsed key, so a reader may
    name a sheet partially ("Roper" for "RoperWhitney") or loosely
    ("Tenn Smith" for "TennSmith"). Both directions are needed: the request
    habitually shortens and the workbook habitually concatenates. The floor
    is applied to the shorter side so a one-word reference cannot sweep in
    every sheet whose name happens to contain that word.
    """
    out: List[str] = []
    matched_keys = set()
    for match in _SHEET_REFERENCE_RE.finditer(str(query or "")):
        phrase = str(match.group(1) or match.group(2) or "").strip()
        if _norm(phrase) in _UNQUALIFIED_SHEET_REFERENCE:
            continue
        text = resolve_sheet_phrase(phrase, sheet_names)
        if text is None:
            continue
        key = _sheet_scope_key(text)
        if key not in matched_keys:
            matched_keys.add(key)
            out.append(text)
    return out


def sheet_reference_phrases(text: str) -> List[str]:
    """The NAMED-sheet reference phrases in `text`, in order — the
    extraction half of `resolve_requested_sheets`.

    Shares the same regex and the same unqualified-reference list as the
    resolver, so what this returns is exactly what COULD resolve later
    against a real catalog; it resolves nothing itself. Consumers that
    need a typed, unresolved reference at decision time (see
    `core.action_program` — the sheet scope enters the turn program here,
    as a pending mention, because no sheet catalog exists at that seam)
    get the user's own words, never a guessed sheet name.
    """
    phrases: List[str] = []
    for match in _SHEET_REFERENCE_RE.finditer(str(text or "")):
        phrase = str(match.group(1) or match.group(2) or "").strip()
        if _norm(phrase) in _UNQUALIFIED_SHEET_REFERENCE:
            continue
        if phrase and phrase not in phrases:
            phrases.append(phrase)
    return phrases


def typed_value(raw: Any) -> Dict[str, Any]:
    """Classify a raw cell value: zero stays zero, blank is blank,
    non-finite/invalid is unavailable (never nan)."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return {"kind": "blank", "display": "blank"}
    if isinstance(raw, str):
        cleaned = raw.replace("$", "").replace(",", "").strip()
        try:
            num = float(cleaned)
        except ValueError:
            return {"kind": "text", "display": raw.strip()}
    else:
        num = float(raw)
    if math.isnan(num) or math.isinf(num):
        return {"kind": "unavailable", "display": "unavailable"}
    if num == 0:
        return {"kind": "zero", "display": "0"}
    display = f"{num:,.2f}".rstrip("0").rstrip(".")
    return {"kind": "number", "value": num, "display": display}


def _value_answers_request(value: Any) -> bool:
    """Whether one value cell can answer the request (a real figure or
    non-empty text — not blank, zero, or unavailable)."""
    if not isinstance(value, dict):
        return False
    kind = str(value.get("kind") or "")
    if kind:
        return kind in _ANSWERABLE_VALUE_KINDS
    # An untyped value (older records) falls back to its display text.
    return str(value.get("display") or "").strip() not in {
        "", "blank", "0", "unavailable", "nan", "None"}


def _candidate_answers_request(
    candidate: Dict[str, Any],
    requested_fields: Optional[Sequence[str]] = None,
) -> bool:
    """Whether this candidate can ANSWER the request as it will be displayed.

    Identity alone is not enough to be a useful candidate. When a target
    matches several rows, only the rows whose PRIMARY value — the one the
    renderer leads with, chosen by the same ``_select_values`` the render
    uses — is a real figure can answer. A row whose leading value is blank
    or zero can only be reported back as "several rows match", which is
    exactly what the user already had and could not use. Incidental figures
    further down the same row (a freight or exchange-rate column) do not
    rescue it, because the renderer would print the blank one first.

    Live 2026-09-29 (session ``replay-retry2-20260923``): a read of the
    same workbook returned a DIFFERENT visible answer minutes apart —
    22:04 led with the priced row, 23:34 led with three rows whose price
    cells were blank/0 and truncated the priced row out of the window
    entirely. The candidate list arrives in scan order and dataset entries
    are ordered by entity name ascending, so the window was decided by
    alphabetical SHEET NAME rather than by which row could answer. This
    predicate restores the data-driven order; it never drops a candidate,
    so ambiguity is still reported and still asks for confirmation.
    """
    values = list(candidate.get("values") or [])
    selected = _select_values(values, list(requested_fields or []), None)
    if selected:
        return _value_answers_request(selected[0])
    # Nothing to select from (no value columns recorded): fall back to any
    # real figure in the row, so the ordering still reflects the data.
    return any(_value_answers_request(value) for value in values)


def _scoped_sheet_note(
    candidates: List[Dict[str, Any]],
    requested_sheets: Optional[Sequence[str]],
) -> str:
    """Name the requested sheets that hold no matching row — or "".

    A sheet scope REORDERS; it never filters (see the SHEET SCOPE note
    above). That is what keeps an "include the Tennsmith sheet" ask from
    silently hiding the RoperWhitney rows the same user also wants. But
    reordering alone is not sufficient, and this clause is why.

    The failure it prevents: the reader asks for one specific sheet, that
    sheet happens to hold nothing for this item, and the answer — being an
    honest report of every candidate — leads with rows from OTHER sheets
    without ever acknowledging the sheet that was asked for. The reader
    cannot tell "here are your rows" from "your sheet had none and I did
    not check". Stating it costs one clause and converts a silent
    substitution into a stated fact.

    Only sheets the request NAMED are eligible, and only sheets that
    resolved against the file's own index reach here (a phrase matching no
    indexed sheet resolves to no scope at all, upstream) — so this can
    never claim a sheet the workbook does not have.
    """
    named = [str(s).strip() for s in (requested_sheets or []) if str(s).strip()]
    if not named:
        return ""
    present = {_sheet_scope_key(_candidate_sheet(c)) for c in candidates}
    missing = [s for s in named if _sheet_scope_key(s) not in present]
    if not missing:
        return ""
    sheets = ", ".join(f"'{s}'" for s in missing)
    one = len(missing) == 1
    elsewhere = (
        "the row shown is on another sheet"
        if len(candidates) == 1 else
        f"the {len(candidates)} rows shown are on other sheets"
    )
    return (f"nothing on the {sheets} {'sheet' if one else 'sheets'} — "
            f"{elsewhere}")


def _candidate_sheet(candidate: Dict[str, Any]) -> str:
    """The sheet a candidate's row sits on, from its row locator
    ("Tennsmith!R338"). A locator without a sheet yields "" rather than
    guessing — a candidate the scan could not place is not attributable to
    any sheet, and must not inherit a scope it was never shown to have."""
    return str(candidate.get("ref") or "").partition("!")[0].strip()


def _rank_candidates(
    candidates: List[Dict[str, Any]],
    requested_fields: Optional[Sequence[str]] = None,
    requested_sheets: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """Stable partition: answerable candidates first, then sheet scope, then
    scan order.

    Two precedence axes, in this order:

    1. ANSWERABILITY. A candidate whose requested value is a real figure
       leads; blank/zero/unavailable cannot answer however well its identity
       matches.
    2. SHEET SCOPE. Within each of those buckets, a candidate on a sheet the
       reader named leads.

    The axis order is deliberate: answerability decides what can REPLY, so it
    outranks a positional preference. Scope then decides what the reader gets
    to SEE among rows that can all reply.

    Stable by construction (one pass per axis, no sort key), so candidates
    that are equally answerable and equally in-scope keep the reader's order
    and no existing rendering changes. Neither axis ELIMINATES: every input
    candidate is still returned, so ambiguity is still reported, the
    confirmation ask still stands, and the structured artifact still retains
    the full set.
    """
    scoped_keys = {_sheet_scope_key(s) for s in (requested_sheets or [])}
    scoped_keys.discard("")

    def _scope_first(bucket: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not scoped_keys:
            return bucket
        named = [c for c in bucket
                 if _sheet_scope_key(_candidate_sheet(c)) in scoped_keys]
        rest = [c for c in bucket
                if _sheet_scope_key(_candidate_sheet(c)) not in scoped_keys]
        return named + rest

    answering: List[Dict[str, Any]] = []
    silent: List[Dict[str, Any]] = []
    for candidate in candidates:
        (answering if _candidate_answers_request(candidate, requested_fields)
         else silent).append(candidate)
    return _scope_first(answering) + _scope_first(silent)


def _read_failure_clause(t: Dict[str, Any]) -> Optional[str]:
    """The user-legible reason a target has no result because the SOURCE could
    not be read, or None when the source was searched successfully.

    The category is the scan's, not an exception message: it is safe to show a
    user, and it is the same vocabulary every retrieval failure reports.
    """
    retrieval = t.get("retrieval") or {}
    if str(retrieval.get("status") or "") != RETRIEVAL_FAILED:
        return None
    category = str(retrieval.get("error_category") or "unknown")
    return _READ_FAILURE_REASONS.get(category, _READ_FAILURE_REASONS["unknown"])


def _concise_result(t: Dict[str, Any]) -> str:
    """One short result clause for table cells: primary display plus its
    basis and row reference, never silent about what was chosen."""
    failure = _read_failure_clause(t)
    if failure:
        return f"source could not be read ({failure})"
    ident = t.get("identity") or {}
    candidates = ident.get("candidates") or []
    pooled = (t.get("field") or {}).get("values") or []
    if (ident.get("status") == "multiple" or not pooled) and candidates:
        first = candidates[0]
        cvals = first.get("values") or []
        if cvals:
            return (f"several rows match; {first.get('ref', '?')}: "
                    f"{cvals[0].get('basis', '')} "
                    f"{cvals[0].get('display', '')}".strip())
        return "several rows match; confirmation needed"
    if not pooled:
        return "no readable value"
    primary = pooled[0]
    return (f"{primary.get('display', '?')} "
            f"({primary.get('basis', '')})".strip())


def _read_failure_reason(category: Any) -> str:
    key = str(category or "unknown")
    return _READ_FAILURE_REASONS.get(key, _READ_FAILURE_REASONS["unknown"])


def _read_failure_phrase(coverage: Dict[str, Any]) -> str:
    """One clause naming HOW MUCH of the source could not be read, and why.

    Shared by the per-source line and the failed-attempt line so the two never
    describe the same failure differently.
    """
    status = str(coverage.get("read_status") or "")
    unreadable = coverage.get("unreadable_sheet_count")
    if not isinstance(unreadable, int):
        unreadable = 0
    if unreadable <= 0:
        # No per-sheet detail (an unobserved scan). Naming "0 sheets" would be
        # a number nobody can act on; the source is what could not be read.
        return ("the source could not be read "
                f"({_read_failure_reason(coverage.get('error_category'))})")
    if status == "failed":
        scope = (f"all {unreadable} indexed sheet" if unreadable == 1
                 else f"all {unreadable} indexed sheets")
    else:
        scope = f"{unreadable} of the indexed sheets"
    return (f"{scope} could not be read "
            f"({_read_failure_reason(coverage.get('error_category'))})")


def _source_read_failure(source: Dict[str, Any]) -> Optional[str]:
    """The source-level read failure clause, or None when the source was read.

    The coverage block carries the scan's ``read_status`` /
    ``absence_claimable`` verdict. ``failed`` (nothing could be read) and
    ``partial`` (some of it could not be) both withhold the absence claim;
    only a completed read supports it.
    """
    coverage = source.get("coverage")
    if not isinstance(coverage, dict):
        return None
    if str(coverage.get("read_status") or "") not in ("failed", "partial"):
        return None
    if coverage.get("absence_claimable") is True:
        return None
    return _read_failure_phrase(coverage)


def present(*, requested_items: List[str], requested_fields: List[str],
            source: Dict[str, Any], targets: List[Dict[str, Any]],
            evidence_revision: str = "", style: str = "default",
            field: Optional[str] = None,
            requested_sheets: Optional[Sequence[str]] = None,
            requested_sheets_sources: Optional[Dict[str, str]] = None,
            ) -> Dict[str, Any]:
    """The pure renderer: structured contract in, readable answer out.
    No retrieval, no database writes, no evidence mutation. ``style`` is
    one of default (full entries), compact (one line per item), or table
    (one markdown row per item); ``field`` prefers one basis by name.

    ``requested_sheets`` is the sheet scope the reader asserted, carried from
    the record so a re-render (retry, reload, presentation action) reproduces
    the same answer. It only ever ADDS a clause — a named sheet that holds no
    matching row is stated as such — so presenting a record without it
    (older records, the compat path) renders exactly as before.

    CONVERSATIONAL RENDERING (2026-09-30, research-grounded: answer-first
    with layered detail — NN/g chatbot guidance, Botpress 2026 expert
    consensus, the Perplexity answer+citations pattern): the answer a user
    reads leads with the value and its location in their words ("$3,254 —
    Tennsmith sheet, row 338"); cell coordinates and alternate bases stay
    available as trailing detail and in the structured card's evidence
    expander, but the sentence is written for the reader, not the
    verifier. Honesty semantics are unchanged: saved-copy provenance,
    coverage numbers, and the no-absence-claim rule all survive, in
    plain words instead of audit vocabulary.
    """
    lines: List[str] = []
    name = source.get("file_name") or "the workbook"
    saved = _human_date(source.get("saved_copy_date"))
    live_vs_saved = source.get("live_vs_saved") or "saved copy"
    source_failure = _source_read_failure(source)
    if style == "table":
        # The table style is the machine-facing compact form; it keeps the
        # established column contract (parse_item_table reads it).
        opening = f"Results from the {live_vs_saved} of {name}"
        if saved:
            opening += f" (copy saved {saved})"
        lines.append(opening + ":")
        lines.append("")
        lines.append("| item | result |")
        lines.append("|---|---|")
        for item in requested_items:
            t = _find_target(targets, item)
            if t is None:
                lines.append(
                    f"| {item} | {_unresolved_clause(source_failure)} |")
                continue
            lines.append(f"| {item} | {_concise_result(t)} |")
    else:
        # Answer-first opening: what was searched, in one human line.
        opening = f"From the {live_vs_saved} of {name}"
        if saved:
            opening += f" (saved {saved})"
        lines.append(opening + ":")
        # Scope receipt: the search was narrowed, and the user can see why.
        scope_bits = []
        for s in (requested_sheets or []):
            origin = (requested_sheets_sources or {}).get(str(s))
            scope_bits.append(
                f"{s}" + (" — per your standing preference"
                          if origin == "standing" else ""))
        if scope_bits:
            lines.append(f"Looking in: {', '.join(scope_bits)}.")
        lines.append("")
        for item in requested_items:
            t = _find_target(targets, item)
            if t is None:
                lines.append(
                    f"- **{item}** — {_unresolved_clause(source_failure)}")
                continue
            lines.append(_render_target(
                t, item, style=style, field=field,
                requested_fields=requested_fields,
                requested_sheets=requested_sheets))
    coverage_raw = source.get("coverage") or "unknown"
    if isinstance(coverage_raw, dict):
        parts = []
        if coverage_raw.get("indexed_sheets") is not None:
            parts.append(f"indexed sheets={coverage_raw.get('indexed_sheets')}")
        scanned = coverage_raw.get("scanned_entries")
        if scanned is None:
            scanned = coverage_raw.get("scanned_sheets")
        if scanned is not None:
            parts.append(f"scanned entries={scanned}")
        if coverage_raw.get("catalog_truncated"):
            parts.append("catalog truncated")
        coverage = "; ".join(parts) if parts else "partial"
        indexed = coverage_raw.get("indexed_sheets")
    else:
        coverage = str(coverage_raw)
        indexed = None
    lines.append("")
    if source_failure:
        # The retrieval failed. Say so once, in its own line, and retract the
        # absence reading of everything above it.
        lines.append(
            f"I couldn't read the source ({source_failure}), so nothing "
            f"above is a statement that the items are absent from {name} — "
            f"no result is reported for a source that could not be read.")
    if style == "table":
        note = (f"Source: {name} - {live_vs_saved}"
                + (f", copy saved {saved}" if saved else "")
                + f". Coverage: {coverage}. Unlisted sheets or newer versions "
                  f"may contain more; this is not an absence claim about the "
                  f"live workbook.")
    else:
        # Human footer: same three facts (which copy, how much was
        # searched, no claim about the live file) without audit wording.
        where = (f"searched all {indexed} sheets of this copy"
                 if isinstance(indexed, int) and not source_failure
                 else f"coverage: {coverage}")
        note = (f"From the {live_vs_saved} of {name}"
                + (f" (saved {saved})" if saved else "")
                + f" — {where}. A newer version of the file may differ; "
                  f"no-match lines are about this copy, not the live file.")
    lines.append(note)
    return {"answer": "\n".join(lines),
            "presentation_version": PRESENTATION_VERSION,
            "evidence_revision": evidence_revision,
            "requested_fields": list(requested_fields),
            "style": style}


def _unresolved_clause(source_failure: Optional[str]) -> str:
    """Clause for an item with no target at all.

    With a failed read there is nothing to have searched, so the clause reports
    the failure; otherwise it keeps the long-standing honest wording.
    """
    if source_failure:
        return f"I couldn't read the source ({source_failure})"
    return "no result in this copy"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def _human_date(value: Any) -> Optional[str]:
    """`2026-09-07T23:06:19` → `2026-09-07` — a saved-copy date a human
    reads as a date, not a timestamp. Unparseable values pass through."""
    text = str(value or "").strip()
    if not text:
        return None
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", text)
    return match.group(1) if match else text


def _find_target(targets: List[Dict[str, Any]], item: str) -> Optional[Dict[str, Any]]:
    """Exact normalized correspondence only. Unresolved stays unresolved:
    no substring fallback (a bare '381' must never claim a '381mm' row)."""
    key = _norm(item)
    for t in targets:
        labels = [t.get("item", "")] + list(t.get("aliases") or [])
        for lab in labels:
            if _norm(lab) == key:
                return t
    return None


def _field_match_terms(field: Optional[str]) -> List[List[str]]:
    """Alias-expanded match terms for a requested field, reusing the
    scan layer's field vocabulary (generic - no per-product rules).
    Each term is a token list; a basis matches when it contains EVERY
    token ("factory price" selects Factory Price, not every PRICE)."""
    if not field:
        return []
    try:
        from core.workbook_read_artifact import _FIELD_ALIASES
        key = str(field).strip().lower()
        if key in _FIELD_ALIASES:
            return [[t for t in _norm(a).split(" ") if t]
                    for a in _FIELD_ALIASES[key]]
    except Exception:
        pass
    return [[t for t in _norm(field).split(" ") if t]]


def _value_matches(value: Dict[str, Any], terms: List[List[str]]) -> bool:
    if not terms:
        return True
    basis = [t for t in _norm(value.get("basis") or "").split(" ") if t]
    for term in terms:
        if term and all(tok in basis for tok in term):
            return True
    return False


def _select_values(values: List[Dict[str, Any]],
                   requested_fields: List[str],
                   field: Optional[str]) -> List[Dict[str, Any]]:
    """Apply requested fields: an explicit field preference wins; else the
    requested-field families filter. Never silently choose: filtering only
    narrows to what was asked for.

    A PREFERENCE RANKS, IT NEVER ERASES (2026-09-30 generalization): the
    default request vocabulary is pricing-shaped ("price"), so a
    non-pricing domain (hydration %, stock counts, lead times) whose
    columns match none of the requested families filtered to NOTHING —
    a recipes workbook rendered "no price column" for a row that had
    the exact value asked about. When the families match no value but
    answerable values exist, the unfiltered values flow (the scan's own
    ranking already put the most relevant columns first); the preference
    only reorders domains it recognizes.
    """
    terms: List[List[str]] = []
    if field:
        terms = _field_match_terms(field)
    else:
        for req in requested_fields or []:
            terms.extend(_field_match_terms(req))
    if not terms:
        return list(values)
    selected = [v for v in values if _value_matches(v, terms)]
    if selected:
        return selected
    if any(_value_answers_request(v) for v in values):
        return list(values)
    return selected


def _identity_cells(cand: Dict[str, Any]) -> List[str]:
    """The exact identity CELL coordinates bound to one candidate.

    `build_targets_from_scan` records the cells whose text actually matched
    under `candidate.identity.references[].cell` (e.g. "A26"). The compact
    `ref` is a row locator ("LINMAC!R26"), which is a position and NOT proof of
    which cell held the identity. Both are carried, because the contract
    (AGENT_SEARCH_WORK_ORDER_2026_09_26 line 79) allows a row citation to be
    DISPLAYED compactly while requiring the exact identity and value
    references to stay separately exposed. A row locator is never presented
    as if it were a cell.
    """
    ident = cand.get("identity") or {}
    out: List[str] = []
    for ref in ident.get("references") or []:
        cell = str((ref or {}).get("cell") or "").strip().upper()
        if re.match(r"^[A-Z]{1,3}\d{1,7}$", cell) and cell not in out:
            out.append(cell)
    return out


def _value_clause(v: Dict[str, Any]) -> str:
    """One value as `<cell> '<basis>' <display>`.

    Every clause names the CELL it came from and quotes the BASIS, so a reader
    -- and an evidence parser -- can tell which cell is blank and on what
    basis. The ambiguous branch used to render a bare `PRICE blank` with no
    cell at all, which made "this row's price cell is blank"
    indistinguishable from "no price column exists here", and left an
    evaluator nothing to bind a value to.
    """
    cell = str(v.get("col") or "").strip()
    basis = str(v.get("basis") or "").strip()
    display = str(v.get("display") or "").strip()
    if not cell:
        return f"{basis} {display}".strip()
    return f"{cell} '{basis}' {display}".strip()


def _human_ref(ref: Any) -> str:
    """'Tennsmith!R338' -> 'Tennsmith sheet, row 338' — a locator written
    as the reader says it. The raw ref stays in the structured record and
    the card's evidence expander for verification."""
    text = str(ref or "").strip()
    if "!" in text:
        sheet, _, row = text.partition("!")
        row = row.lstrip("Rr")
        if row.isdigit():
            return f"{sheet} sheet, row {row}"
    return text


def _render_target(t: Dict[str, Any], item: str, *,
                   style: str = "default",
                   field: Optional[str] = None,
                   requested_fields: Optional[List[str]] = None,
                   requested_sheets: Optional[Sequence[str]] = None
                   ) -> str:
    ident = t.get("identity") or {}
    status = ident.get("status")
    alias = t.get("aliases") or []
    alias_note = f" (matched via '{alias[0]}')" if alias else ""
    requested_fields = list(requested_fields or [])
    candidates = ident.get("candidates") or []
    # A named sheet that holds nothing for this item is stated wherever the
    # item is reported, not only in the ambiguous branch: a single match on
    # another sheet, or no match at all, is exactly as much a substitution.
    scope_note = _scoped_sheet_note(candidates, requested_sheets)
    scope_suffix = f"; {scope_note}" if scope_note else ""
    failure = _read_failure_clause(t)
    if failure:
        # BEFORE the absence branch, deliberately: `identity.status == "none"`
        # is reached both by "searched, not there" and by "the source would not
        # open", and only the retrieval verdict separates them. The absence
        # sentence is a factual claim about the source's contents; it may not
        # be printed for a source that was never successfully read.
        return (f"- **{item}**{alias_note} — I couldn't read the source "
                f"({failure}), so no result for this one; it may still be "
                f"in the workbook")
    if t.get("presentation") == "listing":
        # SHEET-SCOPE BROWSE (2026-09-30): a read whose "items" are whole
        # sheets lists their rows. The captured cells render verbatim —
        # field preferences do not filter a listing, and the ambiguity
        # language ("which one is yours") does not apply because nothing
        # here is awaiting identification. The cap is stated, never
        # silently applied: the record holds at most the browse's
        # per-sheet cap, and the sheet's real row count (when known)
        # turns a truncated listing into an honest "first N of M".
        if not candidates:
            return (f"- **{item}**{alias_note} - no rows in the indexed "
                    f"content searched")
        parts = []
        for c in candidates[:LISTING_ROW_CAP]:
            shown = "; ".join(
                _value_clause(v)
                for v in (c.get("values") or [])[:LISTING_VALUE_CAP])
            parts.append(
                f"{c.get('ref', '?')} ({shown})" if shown
                else str(c.get("ref", "?")))
        extra = candidates[LISTING_ROW_CAP:]
        tail = (f"; +{len(extra)} more row(s) in the indexed copy"
                if extra else "")
        try:
            total_n = (int(t.get("listing_total_rows"))
                       if t.get("listing_total_rows") is not None else None)
        except (TypeError, ValueError):
            total_n = None
        if total_n and total_n > len(candidates):
            head = f"first {len(candidates)} of {total_n} rows"
        else:
            head = f"{len(candidates)} row(s)"
        return (f"- **{item}**{alias_note} - {head} on this sheet: "
                f"{'; '.join(parts)}{tail}")
    if status == "none":
        # The footer already bounds the claim to this copy ("no-match
        # lines are about this copy, not the live file"), so the item
        # line can say it plainly.
        if scope_note:
            return (f"- **{item}**{alias_note} — no match in this copy; "
                    f"{scope_note}")
        return f"- **{item}**{alias_note} — no match in this copy"
    pooled = (t.get("field") or {}).get("values") or []
    selected = _select_values(pooled, requested_fields, field)
    if status == "multiple":
        parts = []
        for c in candidates[:AMBIGUOUS_CANDIDATE_WINDOW]:
            cvals = _select_values(c.get("values") or [], requested_fields, field)
            shown = "; ".join(_value_clause(v) for v in cvals[:2])
            parts.append(
                f"{_human_ref(c.get('ref', '?'))}"
                + (f" ({shown})" if shown else ""))
        # CANDIDATE-CAP FAIRNESS (2026-09-29): only the first three
        # candidates render; if more rows matched — possibly on OTHER
        # sheets the user explicitly cares about — say so, with the
        # sheets that hold them. Hiding surplus matches made a user who
        # had been promised a Tennsmith-sheet row read a candidate list
        # that looked exhaustive but was not (live: Tennsmith!R338 was in
        # the evidence, behind three alphabetically-earlier RoperWhitney
        # rows and the cap).
        #
        # PER-SHEET COUNTS, NOT A SHEET UNION (2026-09-30). The tail named
        # the sheets holding the surplus ("on RoperWhitney, Tennsmith")
        # but not how many of the hidden rows each one held, so a reader who
        # asked to see one specific sheet could not tell whether it was
        # worth re-asking for: the follow-up "show me the tennsmith sheet
        # searches" was answered by the very same sentence, because the
        # union said Tennsmith existed but not that five of the seven
        # surplus rows were on it. A count per sheet is the difference
        # between "there is something there" and "here is what is there".
        extra = candidates[AMBIGUOUS_CANDIDATE_WINDOW:]
        tail = ""
        if extra:
            per_sheet: Dict[str, int] = {}
            for c in extra:
                sheet = str((c.get("ref") or "").split("!", 1)[0] or "").strip()
                if not sheet:
                    # An unplaceable surplus row must still be counted, or
                    # the total the reader is given would not add up.
                    sheet = "an unnamed sheet"
                per_sheet[sheet] = per_sheet.get(sheet, 0) + 1
            breakdown = ", ".join(
                f"{sheet} {count}" for sheet, count in per_sheet.items())
            tail = f"; +{len(extra)} more match(es) ({breakdown})"
        # CONVERSATIONAL ASK (2026-09-30): the count leads, the candidates
        # read as locations ("Tennsmith sheet, row 338 (…)"), and the
        # confirmation ask is a question a person would ask — not audit
        # boilerplate ("which one is yours needs your confirmation").
        line = (f"- **{item}**{alias_note} — {len(candidates)} possible "
                f"rows: {' or '.join(parts)}{tail}{scope_suffix} — "
                f"which one do you mean?")
        return line
    cand = candidates[0] if candidates else {}
    ref = cand.get("ref", "")
    idcells = _identity_cells(cand)
    # A labelled pair, so the row locator and the identity cell read as two
    # distinct facts. An earlier phrasing appended " matched at A26" after a
    # "matched at <ref>" prefix and produced "matched at LINMAC!R26 matched at
    # A26"; the plan requires identity and row to stay separate, and repeating
    # the label made them look like one mangled locator instead.
    idnote = f", identity {', '.join(idcells)}" if idcells else ""
    fstatus = (t.get("field") or {}).get("status")
    if fstatus == "absent" or not pooled:
        _fields_named = ", ".join(
            f for f in (requested_fields or []) if f) or "the requested field"
        return (f"- **{item}**{alias_note} — found at {_human_ref(ref)}"
                f"{idnote}, but no column matching {_fields_named} on that "
                f"row{scope_suffix}")
    if field and not selected:
        bases = sorted({str(v.get("basis") or "") for v in pooled if v.get("basis")})
        return (f"- **{item}**{alias_note} — found at {_human_ref(ref)}{idnote}, "
                f"but '{field}' is not among this row's columns "
                f"({', '.join(bases)}) — which should I use?")
    if not selected:
        bases = sorted({str(v.get("basis") or "") for v in pooled if v.get("basis")})
        return (f"- **{item}**{alias_note} — found at {_human_ref(ref)}{idnote}, "
                f"but none of the requested fields match this row's columns "
                f"({', '.join(bases)}) — which should I use?")
    primary = selected[0]
    if style == "compact":
        return (f"- **{item}**{alias_note} — {primary.get('display', '?')} "
                f"('{primary.get('basis', '')}', {_human_ref(ref)}){scope_suffix}")
    seg = (f"{primary.get('display', '?')} '{primary.get('basis', '')}' "
           f"({_human_ref(ref)}, cell {primary.get('col', '')}"
           + (f", matched at {', '.join(idcells)}" if idcells else ""))
    # Keep distinct (col, basis) even when displays are equal: same value
    # in two bases (e.g. List Price vs List Price_2, or PRICE blank vs
    # U.S. LIST blank) is still two labeled facts, not one. Dedup only
    # exact (col, basis, display) repeats (the compat path repeats the
    # same pair once per citation).
    seen_pairs, alts = set(), []
    seen_pairs.add((primary.get("col"), primary.get("basis"),
                    primary.get("display")))
    for v in selected[1:]:
        key = (v.get("col"), v.get("basis"), v.get("display"))
        if key not in seen_pairs:
            seen_pairs.add(key)
            alts.append(v)
    if alts:
        seg += "; also " + ", ".join(
            f"{v['display']} '{v['basis']}' ({v['col']})" for v in alts)
    seg += ")"
    bound_note = " — the row you confirmed" if t.get("bound") else ""
    return f"- **{item}**{alias_note} — {seg}{scope_suffix}{bound_note}"


# ---------------------------------------------------------------------------
# Compatibility adapter (labeled): legacy rendered text -> contract.
# Validates presentation behavior over records that stored only text; it
# CANNOT validate the artifact-native path and is not evidence reconstruction.
# LIMITATION: it merges citations by row ref — valid ONLY where the artifact
# establishes one product identity per row; the artifact-native path carries
# distinct variants explicitly and never merges them here.
# ---------------------------------------------------------------------------

def _row_key(sheet: str, cell: str) -> str:
    """Row identity for the compat adapter: same sheet + same row number
    is one candidate. Multiple matching CELLS in one row must not become
    multiple candidates (the 381/622 failure: A88/B88/L88 are one row)."""
    m = re.search(r"(\d+)", cell or "")
    row = m.group(1) if m else (cell or "?")
    return f"{(sheet or '?').strip()}!R{row}"


def present_from_rendered_text(reply: str, *, ask: str, source: Dict[str, Any],
                               requested_items: Optional[List[str]] = None,
                               evidence_revision: str = "legacy-text") -> Dict[str, Any]:
    rows = parse_item_table(reply)
    if not rows:
        raise ValueError("no per-item table found in legacy text")
    items = requested_items or extract_requested_order(ask)
    targets: List[Dict[str, Any]] = []
    for r in rows:
        # Per-segment parsing: each " ; "-separated evidence segment cites
        # one match cell with ITS OWN values, so per-row values stay
        # attributed to their row instead of flattening across candidates.
        row_values: Dict[str, List[Dict[str, Any]]] = {}
        row_seen: Dict[str, set] = {}
        for seg in str(r.get("evidence", "")).split(" ; "):
            cites = [(m.group(1).strip(), m.group(2))
                     for m in _CITE_RE.finditer(seg)]
            if not cites:
                continue
            pairs = [{"col": m.group(1), "raw": m.group(2),
                      "basis": m.group(3).strip()}
                     for m in _PAIR_RE.finditer(seg)]
            seg_values = []
            for p in pairs:
                tv = typed_value(p["raw"])
                seg_values.append(
                    {"col": p["col"], "basis": p["basis"], **tv})
            for sheet, cell in cites:
                rk = _row_key(sheet, cell)
                grp = row_values.setdefault(rk, [])
                seen = row_seen.setdefault(rk, set())
                for v in seg_values:
                    vk = (v.get("col"), v.get("basis"), v.get("display"))
                    if vk not in seen:
                        seen.add(vk)
                        grp.append(v)
        candidates = _rank_candidates(
            [{"ref": rk, "values": vals} for rk, vals in row_values.items()])
        values, seen_vals = [], set()
        for vals in row_values.values():
            for v in vals:
                vk = (v.get("col"), v.get("basis"), v.get("display"))
                if vk not in seen_vals:
                    seen_vals.add(vk)
                    values.append(v)
        status = (r.get("status") or "").upper()
        # Identity from ROWS, not cells: several cells in one row = one
        # candidate. AMBIG status with a single row means the field (not
        # the product) is unresolved — keep single identity so the
        # renderer shows competing bases instead of a false multi-row
        # ambiguity.
        identity_status = (
            "none" if ("NOT FOUND" in status or "ABSENT" in status)
            else "multiple" if len(candidates) > 1
            else "single")
        targets.append({
            "item": r.get("target", ""),
            "aliases": [],
            "identity": {"status": identity_status,
                         "candidates": candidates},
            "field": {"status": ("competing" if len({v.get("basis") for v in values}) > 1
                                 else "single" if values else "absent"),
                      "values": values},
        })
    # One entry per REQUESTED item: merge every legacy row matching the
    # same requested item (alias duplicates like 1624 / TK 1624) into one
    # target with combined row-candidates. Matching is strict subsumption
    # (never substring): unresolved correspondence stays unresolved, and
    # legacy rows matching NO requested item (e.g. contamination from
    # earlier email prices) are excluded — they must not become extra
    # top-level entries.
    matched: List[Dict[str, Any]] = []
    for item in items:
        hits = [t for t in targets
                if _subsumes(item, str(t.get("item") or ""))
                or _norm(t.get("item", "")) == _norm(item)]
        if not hits:
            continue  # present() renders the no-result line from items
        cand_seen, cand_all, v_seen, v_all = set(), [], set(), []
        for h in hits:
            for c in (h.get("identity") or {}).get("candidates") or []:
                if c.get("ref") in cand_seen:
                    continue
                cand_seen.add(c.get("ref"))
                # Carry IDENTITY through the alias merge. This rebuild used
                # to copy only ref+values, which is where the matched cell
                # disappeared: the per-target build bound it correctly, the
                # consolidation step then dropped it on the floor, and every
                # target came back identity-unbound with no error anywhere.
                _merged_identity = copy.deepcopy(
                    c.get("identity") or _identity_block([]))
                # Two alias spellings of one item can each contribute a
                # reference; keep every distinct cell rather than first-wins.
                for _other in (h.get("identity") or {}).get(
                        "candidates") or []:
                    if _other.get("ref") != c.get("ref"):
                        continue
                    for _ref in ((_other.get("identity") or {}).get(
                            "references") or []):
                        _cell = str((_ref or {}).get("cell") or "").upper()
                        if not _cell:
                            continue
                        if _cell not in {r.get("cell") for r in
                                         _merged_identity["references"]}:
                            _merged_identity["references"].append(
                                copy.deepcopy(_ref))
                if _merged_identity["references"]:
                    _merged_identity["status"] = IDENTITY_BOUND
                cand_all.append(
                    {"ref": c.get("ref"),
                     "values": list(c.get("values") or []),
                     "identity": _merged_identity})
            for v in (h.get("field") or {}).get("values") or []:
                vk = (v.get("col"), v.get("basis"), v.get("display"))
                if vk not in v_seen:
                    v_seen.add(vk)
                    v_all.append(v)
        bases = {v.get("basis") for v in v_all}
        exact = next((h for h in hits if _norm(h.get("item", "")) == _norm(item)), None)
        best_label = (exact or hits[0]).get("item", "")
        alias_note = [] if _norm(best_label) == _norm(item) else [best_label]
        # Bound by the user's own earlier assertion? The scan pinned the
        # row (user_assertion binding verified at this revision) — carried
        # so the answer can say "the row you confirmed" instead of
        # re-opening a settled question.
        bound = any(
            str(((artifact_outcomes or {}).get(raw) or {}).get("bound_by")
                or "") == "user_assertion"
            for raw in owned)
        matched.append({
            "item": item,
            "aliases": alias_note,
            "identity": {"status": ("none" if not cand_all
                                    else "multiple" if len(cand_all) > 1
                                    else "single"),
                         "candidates": cand_all},
            "field": {"status": ("competing" if len(bases) > 1
                                 else "single" if v_all else "absent"),
                      "values": v_all},
            **({"bound": True} if bound else {}),
        })
    return present(requested_items=items, requested_fields=["price"],
                   source=source, targets=matched,
                   evidence_revision=evidence_revision)


def parse_item_table(reply: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for line in (reply or "").splitlines():
        line = line.strip()
        if not (line.startswith("|") and line.count("|") >= 3):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3 or not cells[0] or set(cells[0]) <= {"-", ":", " "}:
            continue
        if _norm(cells[0]) in ("item", "machine", "target"):
            continue
        rows.append({"target": cells[0], "status": cells[1],
                     "evidence": "|".join(cells[2:])})
    return rows


def extract_requested_order(ask: str) -> List[str]:
    t = ask or ""
    seg = t.rsplit(":", 1)[-1] if ":" in t else t
    parts = re.split(r",|\band\b", seg)
    items = [p.strip(" .") for p in parts if len(p.strip(" .")) >= 2]
    return items[:12]


# ---------------------------------------------------------------------------
# Requested-item authority: the extractor fans one request out into raw
# tokens (regex numerics like "1624" plus list-phrase items like
# "TK 1624"; right-tail variants like "Manual Flanger" alongside
# "TK Manual Flanger"). The PRESENTED list must be the resolved machines,
# not the raw probe tokens. Consolidation keeps the longer (more specific)
# form and preserves first-appearance order.
# ---------------------------------------------------------------------------

def _item_tokens(text: str) -> List[str]:
    return [t for t in _norm(text).split(" ") if t]


def _subsumes(keeper: str, other: str) -> bool:
    """Does resolved item `keeper` cover raw token `other` (keep keeper)?"""
    kn, on = _norm(keeper), _norm(other)
    if not kn or not on:
        return False
    if kn == on:
        return True
    kt, ot = _item_tokens(keeper), _item_tokens(other)
    if len(ot) < len(kt) and kt[-len(ot):] == ot:
        # Right-tail alias: "Manual Flanger" rides "TK Manual Flanger".
        # Pure-numeric tails never alias on their own ("381" stays exact)
        # unless the keeper carries them as a standalone token.
        if len(ot) >= 2 or not re.fullmatch(r"[0-9]+", ot[0] if ot else ""):
            return True
        return ot[0] in kt
    if re.fullmatch(r"[0-9]+", on.replace(" ", "")) and len(kt) > len(ot):
        # Bare number inside a longer model code: "1624" in "TK 1624".
        # The digits must appear as a standalone token of the keeper so
        # "381" never swallows "381mm".
        compact_other = on.replace(" ", "")
        return compact_other in kt
    return False


def resolve_requested_items(tokens: List[str],
                              order_hint: Optional[str] = None) -> List[str]:
    """Consolidate raw probe tokens into the resolved ordered request list.

    Survivors keep first-appearance order; when ``order_hint`` (the asking
    turn's text) is given, survivors sort by first occurrence there, so
    presentation follows the REQUESTED order rather than lane-assembly
    order (regex hits otherwise precede multi-word names found later).
    Distinct models never merge; replacement keeps the earliest slot.
    """
    resolved: List[str] = []
    for token in tokens or []:
        text = str(token or "").strip()
        if not text:
            continue
        if any(_subsumes(kept, text) for kept in resolved):
            continue
        drop = [kept for kept in resolved if _subsumes(text, kept)]
        if drop:
            idx = resolved.index(drop[0])
            for d in drop:
                resolved.remove(d)
            resolved.insert(idx, text)
        else:
            resolved.append(text)
    if order_hint:
        hay = _norm(order_hint)
        positions = []
        for i, item in enumerate(resolved):
            key = _norm(item)
            at = hay.find(key) if key else -1
            positions.append((at if at >= 0 else 10 ** 9, i, item))
        resolved = [item for _, _, item in sorted(positions)]
    return resolved


def _rank_candidates_with_receipt(
    item: str,
    candidate_list: List[Dict[str, Any]],
    requested_fields: Optional[Sequence[str]],
    requested_sheets: Optional[Sequence[str]],
) -> tuple:
    """Rank one item's candidates through the typed action program.

    WHY A PROGRAM, when the ranking primitive is right here: the order
    ``_rank_candidates`` produces is correct but UNEXPLAINED — a reader of
    the record could not tell a scope-driven order from a scan accident
    (that is the 2026-09-30 open item). Executing a ``filter_previous``
    op over the same candidates yields the IDENTICAL order (the executor
    calls ``_rank_candidates`` with the same arguments) plus an effect
    receipt — resolved scope, in-scope counts, which rows the display
    window will hide on the sheet the reader named — that travels with the
    target into the structured record.

    Fail-open to the direct ranking on any error: identical behavior, no
    receipt. The deferred import is mutual with ``action_program`` (it
    imports this module's primitives at call time only), so neither
    module imports the other at load time.
    """
    try:
        from core import action_program as _ap

        refs = [
            _ap.SheetRef(mention=str(s), resolved_name=str(s),
                         status="resolved")
            for s in (requested_sheets or []) if str(s).strip()]
        program = _ap.ActionProgram(actions=[
            _ap.FilterPreviousOp(action_id="scope", item=str(item or ""),
                                 sheets=refs)])
        record = _ap.execute_program(
            program, sheet_names=[str(s) for s in (requested_sheets or [])],
            candidates={str(item or ""): candidate_list},
            requested_fields=list(requested_fields or []))
        outcome = record.outcome_for("scope")
        ranked = record.ranked_by_action.get("scope")
        if outcome is None or ranked is None:
            raise ValueError("no filter outcome")
        receipt = {k: v for k, v in outcome.items()
                   if k not in ("action_id", "op")}
        return ranked, receipt
    except Exception:  # noqa: BLE001 — fail-open to identical direct ranking
        return _rank_candidates(candidate_list, requested_fields,
                                requested_sheets), None


def build_targets_from_scan(
    resolved_items: List[str],
    artifact_outcomes: Dict[str, Any],
    per_item: Optional[Dict[str, Any]] = None,
    requested_fields: Optional[Sequence[str]] = None,
    requested_sheets: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """Artifact-native targets for the presentation contract.

    Row grouping assumes ONE product identity per (sheet, row): several
    matching cells in the same row are one candidate; distinct rows stay
    distinct candidates and are never merged. That assumption is valid
    for price-list sheets where each row is one model; it is stated here
    (and in the compat adapter) rather than hidden in grouping code.

    ``identity.status == "none"`` alone cannot separate "searched, not there"
    from "the source would not open" — both yield zero candidates — so the
    scan's per-target status is carried through as ``retrieval``. Downstream
    that is the difference between the honest absence sentence and a reported
    read failure.

    ``requested_fields`` scopes which candidates can ANSWER (see
    ``_candidate_answers_request``). It only orders the candidate list; when
    omitted the ranking falls back to the scan's own selected value columns.
    ``requested_sheets`` is the sheet scope the reader asserted (see
    ``resolve_requested_sheets``); it is a SECOND ranking axis of equal
    benign character — it reorders, never filters, so a sheet the reader named
    can bring its rows into view without being able to eliminate any.
    """
    per_item = per_item or {}
    raw_tokens = list((artifact_outcomes or {}).keys()) + [
        k for k in per_item.keys() if k not in (artifact_outcomes or {})]
    targets: List[Dict[str, Any]] = []
    for item in resolved_items or []:
        owned = [t for t in raw_tokens if _subsumes(item, str(t))]
        row_groups: Dict[str, Dict[str, Any]] = {}
        aliases: List[str] = []
        retrieval: Dict[str, Any] = {
            "status": RETRIEVAL_SEARCHED, "error_category": None}
        for raw in owned:
            outcome = (artifact_outcomes or {}).get(raw)
            if isinstance(outcome, dict):
                if str(outcome.get("status") or "") == _SCAN_UNAVAILABLE:
                    retrieval = {
                        "status": RETRIEVAL_FAILED,
                        "error_category": str(
                            outcome.get("error_category") or "unknown"),
                    }
                for ev in outcome.get("evidence") or []:
                    if not isinstance(ev, dict):
                        continue
                    sheet = str(ev.get("sheet") or "?").strip()
                    row = ev.get("row")
                    key = f"{sheet}!R{row}"
                    grp = row_groups.get(key)
                    if grp is None:
                        grp = {"ref": key, "values": [], "seen": set(),
                               "identity": _identity_block([])}
                        row_groups[key] = grp
                    _idref = _identity_reference(ev, sheet, row)
                    if _idref is not None:
                        grp["identity"]["references"].append(_idref)
                        grp["identity"]["status"] = IDENTITY_BOUND
                    for v in ev.get("values") or ev.get("prices") or []:
                        if not isinstance(v, dict):
                            continue
                        basis = str(v.get("price_basis") or v.get("field")
                                    or v.get("column") or "value")
                        col = str(v.get("cell") or "")
                        tv = typed_value(v.get("value"))
                        vk = (col, basis, tv.get("display"))
                        if vk not in grp["seen"]:
                            grp["seen"].add(vk)
                            grp["values"].append(
                                {"col": col, "basis": basis, **tv})
                    alias = ev.get("matched_alias")
                    if alias and str(alias) not in aliases:
                        aliases.append(str(alias))
                continue
            record = per_item.get(raw)
            if isinstance(record, dict):
                columns = list(record.get("columns") or [])
                letters = record.get("column_letters") or {}
                rows = record.get("rows") or []
                if rows:
                    row0 = rows[0]
                    rn = (row0.get("__sheet_row") or row0.get("__row__")
                          or "?")
                    sheet = str(record.get("entity_name") or "?").strip()
                    key = f"{sheet}!R{rn}"
                    grp = row_groups.get(key)
                    if grp is None:
                        grp = {"ref": key, "values": [], "seen": set(),
                               "identity": _identity_block([])}
                        row_groups[key] = grp
                    # The content probe records the exact cells whose text
                    # matched, so identity is bound to a real coordinate
                    # rather than left unverified. A record WITHOUT them
                    # keeps the explicit unverified status.
                    for _m in (record.get("matched_cells") or []):
                        if not isinstance(_m, dict):
                            continue
                        _coord = str(_m.get("cell") or "").strip().upper()
                        if not re.match(r"^[A-Z]{1,3}\d{1,7}$", _coord):
                            continue
                        if _coord not in {r["cell"] for r in
                                          grp["identity"]["references"]}:
                            grp["identity"]["references"].append({
                                "sheet": sheet,
                                "cell": _coord,
                                "row": rn,
                                "value": str(_m.get("value") or "") or None,
                                "role": "matched_target",
                            })
                            grp["identity"]["status"] = IDENTITY_BOUND
                    # DOMAIN-GENERAL VALUE PICK (2026-09-30): the
                    # pricing-family preference orders which columns
                    # surface first, and when NO column matches the
                    # family the row's own leading columns flow instead —
                    # a preference ranks, it never erases (a stock-count
                    # or hydration sheet is not "no value").
                    _family_cols = [
                        column for column in columns
                        if re.search(
                            r"price|cost|amount|rate|value|list|total|dealer",
                            str(column), re.IGNORECASE)]
                    if not _family_cols:
                        _family_cols = [
                            column for column in columns
                            if column not in ("__sheet_row", "__row__")][:4]
                    for column in _family_cols:
                        letter = letters.get(column)
                        if not letter:
                            continue
                        col = f"{letter}{rn}"
                        tv = typed_value(row0.get(column))
                        vk = (col, str(column), tv.get("display"))
                        if vk not in grp["seen"]:
                            grp["seen"].add(vk)
                            grp["values"].append(
                                {"col": col, "basis": str(column), **tv})
        candidates, scope_receipt = _rank_candidates_with_receipt(
            item, [
                {"ref": g["ref"], "values": list(g["values"]),
                 "identity": copy.deepcopy(
                     g.get("identity") or _identity_block([]))}
                for g in row_groups.values()], requested_fields,
            requested_sheets)
        values: List[Dict[str, Any]] = []
        for g in row_groups.values():
            values.extend(g["values"])
        bases = {v.get("basis") for v in values}
        # Normalise identity references after the consolidation: several
        # alias spellings can each contribute the same coordinate, so they
        # are deduplicated by cell at ONE point here rather than at each
        # append — correct regardless of how many spellings merged.
        for _c in candidates:
            _idn = _c.get("identity") or _identity_block([])
            _seen_cells, _uniq = set(), []
            for _r in _idn.get("references") or []:
                _cell = str((_r or {}).get("cell") or "").upper()
                if not _cell or _cell in _seen_cells:
                    continue
                _seen_cells.add(_cell)
                _uniq.append(_r)
            _idn["references"] = _uniq
            _idn["status"] = IDENTITY_BOUND if _uniq else IDENTITY_UNVERIFIED
            _c["identity"] = _idn
        targets.append({
            "item": item,
            "aliases": [a for a in aliases
                        if _norm(a) != _norm(item)][:3],
            # The typed program's effect receipt for the scope: resolved
            # sheets, in-scope counts, window truncation, and the explicit
            # no-binding/no-edit-authorization facts. Additive — older
            # records and scopeless reads simply carry None.
            "scope_receipt": scope_receipt,
            "identity": {"status": ("none" if not candidates
                                    else "multiple" if len(candidates) > 1
                                    else "single"),
                         "candidates": candidates},
            "field": {"status": ("competing" if len(bases) > 1
                                 else "single" if values else "absent"),
                      "values": values},
            "retrieval": retrieval,
            # Bound by the user's own earlier assertion (the scan pinned
            # the row at this revision): the answer says "the row you
            # confirmed" instead of re-opening a settled question.
            **({"bound": True} if any(
                str(((artifact_outcomes or {}).get(raw) or {}).get(
                    "bound_by") or "") == "user_assertion"
                for raw in owned) else {}),
        })
    return targets


# ---------------------------------------------------------------------------
# Slice 2: versioned structured-result persistence + attempt identities +
# explicit presentation intent carried through the existing continuation
# mechanism (pending-task metadata) — consumed by ALL presentation sites,
# never re-inferred independently at each one.
# ---------------------------------------------------------------------------

STRUCTURED_RESULT_SCHEMA = "structured-result-2"
STRUCTURED_RESULT_SCHEMA_PREVIOUS = ("structured-result-1",)


# ---------------------------------------------------------------------------
# IDENTITY EVIDENCE (contract v2)
#
# A candidate's ``ref`` is a ROW LOCATOR ("LINMAC!R26"). That is useful for
# display and completely insufficient for proof: a row can hold several
# prices, and nothing in "R26" says which cell the requested identity was
# matched in, nor what was read there. Equally, the label cell alone does
# not prove a price. Identity and value are SEPARATE bindings and are now
# carried separately.
#
# The scan already knows the exact matched coordinate — it is
# ``evidence[hit]["cell"]`` — and it was being dropped when candidates were
# grouped by row. It is preserved here instead.
#
# Nothing is inferred. Where the source does not establish an identity
# coordinate (the legacy row record, the rendered-text compat adapter),
# the binding is reported UNVERIFIED with no references rather than
# reconstructed from a row number or assumed to be column A: models,
# descriptions, aliases and merged labels all live in different cells.
# ---------------------------------------------------------------------------

IDENTITY_BOUND = "bound"
IDENTITY_UNVERIFIED = "unverified"


def _identity_reference(ev: Dict[str, Any], sheet: str, row: Any,
                        role: str = "matched_target") -> Optional[Dict[str, Any]]:
    """One exact identity reference from a scan evidence record, or None
    when the record carries no matched coordinate."""
    cell = str(ev.get("cell") or "").strip()
    if not cell or not re.match(r"^[A-Z]{1,3}\d{1,7}$", cell.upper()):
        return None
    return {
        "sheet": sheet,
        "cell": cell.upper(),
        "row": row,
        "value": str(ev.get("value") or "").strip() or None,
        "role": role,
    }


def _identity_block(refs: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "status": IDENTITY_BOUND if refs else IDENTITY_UNVERIFIED,
        "references": list(refs),
    }


def new_attempt_id() -> str:
    """A NEW search attempt gets a NEW attempt identity, even when its
    evidence revision is unchanged (same copy re-read)."""
    import uuid
    return f"attempt-{uuid.uuid4()}"


EVIDENCE_ACTIONS = ("new_read", "read_failed", "reused", "unverified")


def workbook_result_card(
    structured_result: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Compact, versioned card payload for chat UI rendering of a
    workbook read (2026-09-30 presentation pass).

    The rendered markdown stays the source of truth for text consumers
    (copy/export/fallback); the card is a CLEAN presentation of the same
    artifact: one row per requested item (value + basis + provenance
    under an expander), ambiguous items carry their candidate count,
    absent items say so without inventing anything, and the footer
    carries the file, evidence kind and coverage. Generic across
    domains: everything here is structural (item/value/basis/ref).
    """
    try:
        sr = structured_result or {}
        source = sr.get("source_identity") or {}
        file_name = str(source.get("file_name") or "").strip()
        if not file_name:
            return None
        kind = str(source.get("live_vs_saved") or "").strip()
        ingested = str(source.get("ingested_at") or "")[:10]
        source_note = " · ".join(x for x in (kind, ingested) if x)
        items: List[Dict[str, Any]] = []
        for t in sr.get("targets") or []:
            item = str((t or {}).get("item") or "").strip()
            if not item:
                continue
            ident = t.get("identity") or {}
            status = str(ident.get("status") or "none")
            entry: Dict[str, Any] = {"item": item}
            cands = ident.get("candidates") or []
            if t.get("presentation") == "listing":
                # A sheet-scope browse: the "item" is a whole sheet and
                # its candidates are listed rows, not competing answers —
                # the ambiguous badge ("needs your pick") would misread a
                # listing as an unresolved question.
                entry["status"] = "found"
                entry["value"] = None
                entry["basis"] = (
                    f"{len(cands)} rows listed"
                    + (f" of {t.get('listing_total_rows')}"
                       if t.get("listing_total_rows") else ""))
                items.append(entry)
                continue
            if status == "multiple" and cands:
                entry["status"] = "ambiguous"
                entry["candidates"] = []
                for c in cands[:5]:
                    vals = c.get("values") or []
                    first = next(
                        (v for v in vals if str(
                            v.get("display") or "").strip().lower()
                        not in ("", "blank", "unavailable")), None)
                    cells = [
                        str(r.get("cell"))
                        for r in ((c.get("identity") or {})
                                  .get("references") or [])[:2]
                        if (r or {}).get("cell")]
                    entry["candidates"].append({
                        "ref": c.get("ref"),
                        "value": (first or {}).get("display"),
                        "basis": (first or {}).get("basis"),
                        "identity_cells": cells,
                    })
                entry["more_candidates"] = max(
                    0, len(cands) - len(entry["candidates"]))
            elif cands:
                c = cands[0]
                vals = c.get("values") or []
                first = next(
                    (v for v in vals if str(
                        v.get("display") or "").strip().lower()
                    not in ("", "blank", "unavailable")), None)
                entry["status"] = "found"
                entry["value"] = (first or {}).get("display")
                entry["basis"] = (first or {}).get("basis")
                entry["ref"] = c.get("ref")
                entry["identity_cells"] = [
                    str(r.get("cell"))
                    for r in ((c.get("identity") or {})
                              .get("references") or [])[:2]
                    if (r or {}).get("cell")]
                entry["other_bases"] = [
                    {"basis": v.get("basis"), "display": v.get("display")}
                    for v in vals[1:5]
                    if str(v.get("display") or "").strip().lower()
                    not in ("", "blank", "unavailable")][:3]
            else:
                entry["status"] = "absent"
            items.append(entry)
        coverage = sr.get("coverage") or {}
        coverage_bits = []
        for key, label in (("indexed_sheets", "sheets indexed"),
                           ("scanned_sheets", "sheets scanned"),
                           ("catalog_rows_seen", "catalog rows")):
            if coverage.get(key) is not None:
                coverage_bits.append(f"{coverage[key]} {label}")
        return {
            "schema": "workbook-result-1",
            "file": file_name,
            "source_note": source_note or None,
            "coverage": " · ".join(coverage_bits) or None,
            "items": items[:24],
        }
    except Exception:  # noqa: BLE001 — the card is presentational only
        return None


def build_structured_record(*, source_identity: Dict[str, Any],
                            evidence_revision: str,
                            attempt_id: str,
                            evidence_action: str,
                            requested_items: List[str],
                            requested_fields: List[str],
                            targets: List[Dict[str, Any]],
                            coverage: Any,
                            requested_sheets: Optional[Sequence[str]] = None,
                            requested_sheets_sources: Optional[Dict[str, str]] = None,
                            retrieved_at: Optional[float] = None) -> Dict[str, Any]:
    """The versioned structured artifact to persist beside (not instead of)
    the rendered text. evidence_action is EVIDENCE-BASED: the caller stamps
    what actually happened (retrieval completed / failed / reused cache) —
    creating a record or minting an attempt id establishes nothing.

    ``requested_sheets`` records the sheet scope this turn asserted. The
    candidate ORDER in ``targets`` is a consequence of it, so it is persisted
    rather than left inferable: a reader of the record can then tell a
    reordering the request asked for from one the scan happened to produce.
    It is provenance, not a filter — the record keeps every candidate.
    """
    import time as _t
    if evidence_action not in EVIDENCE_ACTIONS:
        raise ValueError(f"evidence_action must be one of {EVIDENCE_ACTIONS}")
    return {
        "schema_version": STRUCTURED_RESULT_SCHEMA,
        "source_identity": dict(source_identity or {}),
        "evidence_revision": evidence_revision,
        "attempt_id": attempt_id,
        "evidence_action": evidence_action,
        "retrieved_at": retrieved_at if retrieved_at is not None else _t.time(),
        "requested_items": list(requested_items),
        "requested_fields": list(requested_fields),
        "requested_sheets": [str(s) for s in (requested_sheets or [])],
        "requested_sheets_sources": {
            str(k): str(v) for k, v in (requested_sheets_sources or {}).items()},
        "targets": targets,
        "coverage": coverage,
    }


def set_presentation_intent(record: Dict[str, Any],
                            resolved_intent: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """A SEPARATE presentation-action record referencing the original
    retrieval. The intent comes from the EXISTING request/continuation
    mechanism (resolved upstream) — this function classifies nothing and
    NEVER rewrites the original record's evidence history. The original's
    evidence_action and attempt remain the historical facts."""
    if record is None:
        raise ValueError("presentation action requires the original record")
    import time as _t
    intent = dict(resolved_intent or {})
    return {
        "schema_version": "presentation-action-1",
        "action_type": "presentation",
        "action": intent.get("action", "present"),
        "created_at": _t.time(),
        "references_attempt_id": record.get("attempt_id"),
        "references_evidence_revision": record.get("evidence_revision"),
        "referenced_evidence_action": record.get("evidence_action"),
        "intent": intent,
    }


def mark_delivered(record: Dict[str, Any], delivered_answer: str) -> Dict[str, Any]:
    """Pin the DELIVERED answer to the record. Transport retries serve this
    pinned original verbatim — a renderer upgrade must never alter an
    already-delivered answer.

    PIN-AFTER-FINALIZATION (review round 31): the caller MUST pass the
    message as actually DELIVERED — i.e. AFTER the finalization seam
    (failure correction, claim reconciliation) — never the renderer's
    intermediate output. Pinning an intermediate would make transport
    retries disagree with the response the user originally received."""
    import hashlib as _h
    import time as _t
    out = dict(record)
    out["delivery_pin"] = {
        "delivered_at": _t.time(),
        "delivered_answer_sha256": _h.sha256(delivered_answer.encode()).hexdigest(),
        "delivered_text": delivered_answer,
    }
    return out


def serve_on_transport_retry(record: Dict[str, Any]) -> Optional[str]:
    """Transport retry: return the PINNED delivered answer verbatim, or None
    when nothing was delivered (the caller then follows its normal path)."""
    pin = (record or {}).get("delivery_pin")
    return pin.get("delivered_text") if pin else None


def validate_rendered_against_record(
    answer: str,
    record: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Does this answer's factual content match the evidence it claims?

    WHY THIS EXISTS. Answer text used to be trusted because a deterministic
    renderer produced it -- true for the lookup turn, false for a turn where
    no structured read ran and the model narrated instead. On "Replace U-22
    with U-38" the model returned the previous list AND reworded a citation
    the artifact had exactly right (``Tinknock!R100`` for
    ``Tinknocker!R100``). A user cannot tell a mangled sheet name from a real
    one, and the structured record -- the thing that actually knows the truth
    -- disagreed with the text in front of them.

    This is a SEMANTIC check, not a prose-equality check. It never compares
    wording to an expected string, because the same facts legitimately render
    many ways (compact vs table, one basis vs several). It compares only the
    things that must be true of any correct rendering of this record:

      citations_grounded   every Sheet!Cell / Sheet!R<n> the answer shows
                           exists in this record, spelled exactly. A row
                           locator is accepted as a locator; a cell is accepted
                           only as a cell.
      items_not_stale      the answer does not present an item the record does
                           not have, and does not omit one it does. This is
                           what catches a previous list served as the answer to
                           a changed request.
      values_grounded      every number the answer attaches to an item appears
                           in that item's evidence, so a price cannot be
                           invented or carried over from a different row.
      no_failed_read_as_data
                           a record whose read failed must not be rendered as
                           a list of results.

    Returns {"ok", "checks", "violations"}. A caller that finds ok=False must
    NOT deliver `answer` as a success: re-render from the record, and if that
    also fails, return an explicit incomplete outcome.
    """
    checks = {"citations_grounded": True, "items_not_stale": True,
              "values_grounded": True, "no_failed_read_as_data": True}
    violations: List[Dict[str, Any]] = []
    text = answer or ""
    rec = record if isinstance(record, dict) else {}
    targets = [t for t in (rec.get("targets") or []) if isinstance(t, dict)]

    # -- a failed read must never be presented as results -------------------
    if rec.get("evidence_action") == "read_failed":
        looks_like_results = any(
            re.search(r"^\s*[-*]\s*\S", line, re.MULTILINE) and " - " in line
            for line in text.splitlines())
        if looks_like_results and "did not complete" not in text.lower():
            checks["no_failed_read_as_data"] = False
            violations.append({"check": "no_failed_read_as_data",
                               "detail": "record says the read failed but the "
                                         "answer presents a result list"})

    # -- build the exact set of coordinates this record supports -------------
    supported_sheet_cell: set = set()
    supported_row_locs: set = set()
    for t in targets:
        ident = t.get("identity") or {}
        groups = []
        refs = ident.get("references")
        if isinstance(refs, list):
            groups.append({"references": refs})
        for cand in ident.get("candidates") or []:
            if not isinstance(cand, dict):
                continue
            ref = str(cand.get("ref") or "")
            if "!" in ref:
                sheet, _, loc = ref.partition("!")
                loc = loc.strip()
                m = re.match(r"^R(\d+)$", loc, re.IGNORECASE)
                if m:
                    supported_row_locs.add((sheet.strip().upper(),
                                            f"R{m.group(1)}"))
                elif re.match(r"^[A-Z]{1,3}\d{1,7}$", loc, re.IGNORECASE):
                    supported_sheet_cell.add((sheet.strip().upper(),
                                              loc.upper()))
            sub = cand.get("identity")
            if isinstance(sub, dict) and isinstance(sub.get("references"), list):
                groups.append(sub)
            for v in cand.get("values") or []:
                if not isinstance(v, dict):
                    continue
                cell = str(v.get("col") or "").strip().upper()
                if not re.match(r"^[A-Z]{1,3}\d{1,7}$", cell):
                    continue
                sheet = ref.partition("!")[0].strip().upper() if "!" in ref else ""
                if sheet:
                    supported_sheet_cell.add((sheet, cell))
        for grp in groups:
            for r in grp["references"]:
                cell = str((r or {}).get("cell") or "").strip().upper()
                sheet = str((r or {}).get("sheet") or "").strip().upper()
                if sheet and re.match(r"^[A-Z]{1,3}\d{1,7}$", cell):
                    supported_sheet_cell.add((sheet, cell))

    # -- 1. every citation in the text must be supported --------------------
    # `_CITE_RE`'s sheet group admits spaces, so on a line like
    # "matched at LINMAC!R26" it captures the sheet as "matched at LINMAC".
    # Real sheet names contain spaces too ("US$ SCOTCH PARTS"), so the group
    # cannot simply be narrowed to a single word. Instead each match retries
    # after dropping leading words, longest-suffix first: the true sheet name
    # is found whether or not prose precedes it, and an unsupported citation
    # still fails after every suffix has been tried.
    for sheet, loc in _CITE_RE.findall(text):
        l_key = loc.strip().upper()
        words = [w for w in re.split(r"\s+", sheet.strip()) if w]
        matched = False
        for start in range(len(words)):
            cand_sheet = " ".join(words[start:]).upper()
            if (cand_sheet, l_key) in supported_sheet_cell:
                matched = True
                break
            m = re.match(r"^R(\d+)$", l_key)
            if m and (cand_sheet, f"R{m.group(1)}") in supported_row_locs:
                matched = True
                break
        if matched:
            continue
        checks["citations_grounded"] = False
        violations.append({"check": "citations_grounded",
                           "detail": f"{sheet.strip()}!{loc.strip()}",
                           "supported_sheets": sorted(
                               {s for s, _ in supported_sheet_cell}
                               | {s for s, _ in supported_row_locs})[:8]})

    # -- 2. item coverage: no stale item, no missing item -------------------
    # Only meaningful once the answer's list structure has been parsed. A
    # render style this parser does not understand must not be reported as
    # "stale" -- that would fail a correct table for the crime of being a table.
    parsed_items = _visible_items(text)
    answered = {_norm(str(t.get("item") or "")) for t in targets}
    answered.discard("")
    for t in ([] if not parsed_items else targets):
        item = str(t.get("item") or "").strip()
        if not item:
            continue
        ident = t.get("identity") or {}
        if str(ident.get("status") or "") == "none":
            continue  # an absent item is legitimately named as absent
        # an item the record HAS must be visible in the answer
        if _norm(item) not in {_norm(w) for w in _visible_items(text)}:
            checks["items_not_stale"] = False
            violations.append({"check": "items_not_stale",
                               "detail": f"record has {item!r} but the answer "
                                         f"does not present it"})
    # an item the answer LEADS with must exist in the record
    for item in parsed_items:
        if _norm(item) in answered:
            continue
        if _norm(item) in {_norm(i) for i in
                                 (rec.get("requested_items") or [])}:
            # requested but not in targets: only legitimate if the record
            # reports it absent, which `_visible_items` cannot distinguish.
            # Treat presence in requested_items as acceptable (the renderer
            # states absence explicitly for these).
            continue
        checks["items_not_stale"] = False
        violations.append({"check": "items_not_stale",
                           "detail": f"answer presents {item!r}, which is not "
                                     f"in this record's targets"})

    # -- 3. every number beside an item must be in that item's evidence -----
    for t in targets:
        item = str(t.get("item") or "").strip()
        if not item or not _norm(item) in {
                _norm(w) for w in _visible_items(text)}:
            continue
        allowed: set = set()
        for cand in ((t.get("identity") or {}).get("candidates") or []):
            for v in (cand.get("values") or []):
                if not isinstance(v, dict):
                    continue
                val = v.get("value")
                if isinstance(val, (int, float)):
                    allowed.add(round(float(val), 2))
                dv = _display_number(v.get("display"))
                if dv is not None:
                    allowed.add(dv)
        if not allowed:
            continue
        line = _item_line(text, item)
        if not line:
            continue
        # Numbers that are part of the ITEM NAME are not values. "U-22" and
        # "No. 381" contain digits; scanning the raw line flagged every item
        # label as an unbound value, which would fail every correct rendering
        # and make the check worthless. Strip the label, then strip citation
        # coordinates (R<row> and Sheet!Cell), which citations_grounded owns.
        scan = line
        for label in _visible_items(line) or [item]:
            scan = re.sub(re.escape(label), " ", scan, flags=re.IGNORECASE)
        scan = _CITE_RE.sub(" ", scan)
        scan = re.sub(r"\bR\d{1,7}\b", " ", scan)
        # Bare A1-style coordinates (A26, C26, E88) are CELL REFERENCES, not
        # values, and citations_grounded already owns them. Left in place they
        # made every ambiguous line look like it contained an unbound value
        # (the row number of the cell it cites), which would fail every
        # correct rendering.
        scan = re.sub(r"\b[A-Z]{1,3}\d{1,7}\b", " ", scan)
        for raw in re.findall(r"\d[\d,]*(?:\.\d+)?", scan):
            try:
                got = round(float(raw.replace(",", "")), 2)
            except ValueError:
                continue
            if got in allowed:
                continue
            # Tolerate a number that is part of a citation (row/cell) rather
            # than a value: those are checked by citations_grounded.
            if any(abs(got - a) < 0.005 for a in allowed):
                continue
            checks["values_grounded"] = False
            violations.append({"check": "values_grounded",
                               "detail": f"{item!r} shows {raw} which is not in "
                                         f"its evidence {sorted(allowed)[:6]}"})
            break
    # GATING vs ADVISORY. A validator that rejects a CORRECT rendering is
    # worse than none: it turns a right answer into "incomplete". The two
    # roles are therefore separated deliberately.
    #
    #   citations_grounded     GATING. Set containment against exact
    #                          coordinates the record carries. No false
    #                          positive is possible unless the record itself
    #                          lacks the coordinate, and it is the check that
    #                          catches the real observed defect (a model
    #                          rewording a sheet name).
    #   no_failed_read_as_data GATING. Structural: a failed read is not a list.
    #   items_not_stale        GATING only when the answer's list structure was
    #                          actually PARSED. An unparsed style (a markdown
    #                          table) yields no items, and "no items parsed" is
    #                          not evidence of staleness.
    #   values_grounded        ADVISORY. Deciding which numbers in a sentence
    #                          are values rather than coordinates, part numbers
    #                          or basis names depends on the render style, and
    #                          every strict version tried produced false
    #                          positives on correct output. Reported for
    #                          diagnostics; never blocks delivery.
    gating = {
        "citations_grounded": checks["citations_grounded"],
        "no_failed_read_as_data": checks["no_failed_read_as_data"],
    }
    if _visible_items(text):
        gating["items_not_stale"] = checks["items_not_stale"]
    return {"ok": all(gating.values()), "gating": gating,
            "checks": checks, "advisory": ["values_grounded"],
            "violations": violations,
            "validator": "evidence-bindings-v1"}


def _display_number(display: Any) -> Optional[float]:
    if display is None:
        return None
    m = re.match(r"^\s*-?[\d,]+(?:\.\d+)?\s*$", str(display))
    if not m:
        return None
    try:
        return round(float(str(display).replace(",", "").strip()), 2)
    except ValueError:
        return None


_ITEM_LINE_RE = re.compile(
    r"^\s*[-*]?\s*\**(?P<item>[^*:\n]{1,80}?)\**\s*(?:\([^)]*\))?\s*-\s",
    re.MULTILINE)


def _visible_items(text: str) -> List[str]:
    """Item labels the answer actually presents, from its list lines."""
    out: List[str] = []
    for line in (text or "").splitlines():
        if " - " not in line and " — " not in line:
            continue
        m = _ITEM_LINE_RE.match(line.strip())
        if not m:
            continue
        label = m.group("item").strip().strip("*_ ").strip()
        label = re.sub(r"\s*\((?:matched via|matched|via)\b.*$", "", label,
                       flags=re.IGNORECASE).strip()
        if label and label.lower() not in _ITEM_JUNK_PRESENTATION:
            out.append(label)
    return out


_ITEM_JUNK_PRESENTATION = {
    "source", "coverage", "note", "result", "results", "summary",
}


def _item_line(text: str, item: str) -> str:
    """The answer's line for one item, or '' when absent."""
    for line in (text or "").splitlines():
        if item and _norm(item) in _norm(line) and (
                " - " in line or " — " in line):
            return line
    return ""


def present_from_record(record: Dict[str, Any],
                        presentation_intent: Optional[Dict[str, Any]] = None,
                        presentation_action: Optional[Dict[str, Any]] = None,
                        style: Optional[str] = None,
                        field: Optional[str] = None
                        ) -> Dict[str, Any]:
    """The artifact-native path: render from a PERSISTED structured record.
    Retries and reloads use the SAME renderer via this entry point.
    presentation_action (from set_presentation_intent) supplies the carried
    intent and keeps the ORIGINAL attempt/revision as references. Style and
    field preferences ride the intent (explicit params win, then the
    action's intent, then the bare intent): preferences visibly change the
    rendering — an action record alone never counts as honoring them. A
    read_failed record is delivered as an honest failed-retrieval outcome —
    never rendered as if it were evidence, and never as an absence: the reason
    the read failed is named, in the shared error-category wording."""
    if record.get("evidence_action") == "read_failed":
        coverage = record.get("coverage")
        reason = (" the source could not be read"
                  if not isinstance(coverage, dict)
                  else f" {_read_failure_phrase(coverage)}")
        return {"answer": ("The search attempt did not complete:"
                           + reason
                           + ", so no fresh evidence is available from it and "
                             "no absence is claimed for the items you asked "
                             "about. The earlier saved results remain "
                             "unchanged."),
                "presentation_version": PRESENTATION_VERSION,
                "evidence_revision": record.get("evidence_revision"),
                "attempt_id": record.get("attempt_id"),
                "evidence_action": "read_failed"}
    if record.get("evidence_action") == "unverified":
        return {"answer": ("The search status could not be verified — no "
                           "retrieval was observed for this attempt — so no "
                           "values are reported from it."),
                "presentation_version": PRESENTATION_VERSION,
                "evidence_revision": record.get("evidence_revision"),
                "attempt_id": record.get("attempt_id"),
                "evidence_action": "unverified"}
    if presentation_action is not None:
        presentation_intent = presentation_action.get("intent") or presentation_intent
    intent = presentation_intent or {}
    resolved_style = style or intent.get("style") or "default"
    if resolved_style not in ("default", "compact", "table"):
        resolved_style = "default"
    resolved_field = field or intent.get("field")
    src_id = record.get("source_identity") or {}
    saved = src_id.get("ingested_at") or src_id.get("saved_copy_date")
    result = present(
        requested_items=record.get("requested_items") or [],
        requested_fields=record.get("requested_fields") or ["price"],
        source={"file_name": src_id.get("file_name"),
                "saved_copy_date": saved,
                "live_vs_saved": src_id.get("live_vs_saved") or "saved copy",
                "coverage": record.get("coverage")},
        targets=record.get("targets") or [],
        evidence_revision=str(record.get("evidence_revision") or ""),
        style=resolved_style, field=resolved_field,
        requested_sheets=record.get("requested_sheets") or None,
        requested_sheets_sources=record.get("requested_sheets_sources") or None)
    result["attempt_id"] = record.get("attempt_id")
    result["evidence_action"] = record.get("evidence_action")
    result["presentation_intent"] = presentation_intent or record.get("presentation_intent")
    result["presentation_style"] = resolved_style
    result["presentation_field"] = resolved_field
    if presentation_action is not None:
        result["presentation_action"] = {
            "action_type": "presentation",
            "references_attempt_id": presentation_action.get("references_attempt_id"),
            "references_evidence_revision": presentation_action.get("references_evidence_revision"),
        }
        # the referenced originals are the historical facts
        result["attempt_id"] = presentation_action.get("references_attempt_id")
        result["evidence_revision"] = presentation_action.get("references_evidence_revision")
    return result
