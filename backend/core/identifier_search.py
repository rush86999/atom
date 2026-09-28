"""Identifier-tolerant search primitives shared by every integration family.

Bug class this closes (live 2026-09-04, Linmac WG-350DSAV across Zoho
Inventory/Books/CRM, Linear, Asana, GitHub, Mailchimp, Calendar): real
queries arrive as prose ("is the bandsaw in stock?"), multi-word ("Linmac
WG-350DSAV"), or in another source's spelling ("wg350dsav" from a price
book vs the "WG-350DSAV" item name) — while provider search APIs are
word-exact (Zoho's search_text ANDs its tokens and matches whole name
tokens only) and naive client-side filters either require the WHOLE query
as one substring (zero hits for any enriched query) or keep the first N
recency-ordered matches (identifier matches buried under generic-term
matches — "bandsaw" matched 42 accessory items while the stocked saw sat
past the limit cut).

Three shapes every app family needs, one implementation each:

- normalize_code / identifier_variants / identifier_rank — model-code
  spellings ("WG-350DSAV", "wg350dsav", "350dsav") and their attempt order;
- filter_by_terms / rank_records — client-side filtering ranked by
  matched-term weight (any term matches; longer/identifier-shaped terms
  outrank prose) instead of first-N-in-list-order;
- run_search_ladder — a bounded attempt ladder over provider APIs that
  offer more than one search parameter (full-text + name-substring),
  stopping at the first skeleton-exact hit.

Pure functions, zero I/O, no repo dependencies — importable from any
integration service without cycles.
"""
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple

# --- Identifier shapes -------------------------------------------------------

_ALPHA_PREFIX_RE = re.compile(r"^[a-z]+(?=[0-9])", re.IGNORECASE)
# Multi-part alnum-hyphen runs: catalog codes ('F-5216', 'WG-350DSAV',
# 'INV-2024-118') keep their hyphens — providers index the hyphenated NAME,
# and splitting the code drops the part that carries the letters.
_HYPHEN_COMPOUND_RE = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+")
# A compound with more parts than this is a URL slug ('52-inch-16-gauge-
# foot-shear'), not a catalog code — its plain parts tokenize as usual.
_MAX_CODE_PARTS = 3


def normalize_code(value: Any) -> str:
    """Lowercase alphanumeric skeleton for name comparisons. Model codes
    arrive in whatever spelling the current source uses ('wg-350dsav' from
    a user, 'WG350DSAV' from a price book, 'wg 350 dsav' over the phone)
    but providers index the item NAME's exact tokens, so comparisons run
    on the stripped form."""
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def identifier_variants(token: str) -> List[str]:
    """Relaxed spellings of an identifier-shaped token. A separator-less
    model code from one source ('WG350DSAV' — a price-book row) is not a
    token of the hyphenated provider name ('WG-350DSAV'): whole-token
    search and name-substring filters both miss it. Stripping the leading
    alpha run leaves a suffix ('350DSAV') that IS a substring of the
    hyphenated name, so substring search can still find the record."""
    t = (token or "").strip()
    stripped = _ALPHA_PREFIX_RE.sub("", t)
    if stripped and stripped != t and len(stripped) >= 4:
        return [stripped]
    return []


def identifier_rank(token: str) -> Tuple[int, int]:
    """Attempt order: identifier-shaped tokens (letters mixed with digits —
    the shape every industry's catalog codes share: machinery 'WG350DSAV',
    electronics 'LM358', apparel 'NK-AQ0818') before prose words, longer
    first. 'WG-350DSAV' is tried before 'Linmac'."""
    has_digit = any(c.isdigit() for c in token)
    has_alpha = any(c.isalpha() for c in token)
    return (0 if (has_digit and has_alpha) else 1, -len(token))


def query_terms(query: str, min_len: int = 3) -> List[str]:
    """Alphanumeric tokens of a query, deduped, identifier-shaped first —
    the per-token retry order for providers whose search ANDs tokens.

    Hyphenated catalog codes ('F-5216') are kept WHOLE and rank with the
    identifiers: the plain tokenizer splits them ('F' falls under min_len,
    '5216' ranks as prose), so the code never got its own ladder rung and
    a 'is the F-5216 in stock?' turn searched everything BUT the code
    (live 2026-09-13, canvas a1a13834). Slug-shaped hyphen runs (more than
    3 parts, or all-alpha like 'sheet-metal-equipment') are not codes —
    their plain parts cover them."""
    compounds = [
        c for c in _HYPHEN_COMPOUND_RE.findall(query or "")
        if len(c) >= min_len
        and len(c.split("-")) <= _MAX_CODE_PARTS
        and any(ch.isdigit() for ch in c)
        and any(ch.isalpha() for ch in c)
    ]
    terms = [
        t for t in dict.fromkeys(
            compounds + re.findall(r"[A-Za-z0-9]+", query or ""))
        if len(t) >= min_len
    ]
    terms.sort(key=identifier_rank)
    return terms


# --- Bounded, constraint-preserving query decomposition ----------------------

_YEAR_RE = re.compile(r"^(19|20)\d{2}$")


def exact_identifiers(query: str) -> List[str]:
    """The exact identifiers a query names, in REQUESTED order, original spelling.

    "Requested order" is the order the user wrote them: a search that reorders
    the set changes which of two similar-looking items is reported first.
    Recognised shapes are the ones real turns use — hyphenated catalog codes
    ('U-22', 'SLE24-16', 'GSL48-16'), mixed alphanumeric runs ('TK1624'), and
    bare part numbers ('381', '1624') — plus their word-joined forms ('No. 381',
    'TK 1624'). Prose words are not identifiers, and the sub-tokens of a hyphen
    compound are not separate identifiers: 'SLE24-16' is one identifier, not
    'SLE24' and '16', or a decomposition would search for halves the user never
    asked about.
    """
    text = query or ""
    claimed: List[tuple] = []
    found: List[str] = []

    for match in _HYPHEN_COMPOUND_RE.finditer(text):
        token = match.group(0)
        if (any(ch.isdigit() for ch in token)
                and any(ch.isalpha() for ch in token)
                and len(token.split("-")) <= _MAX_CODE_PARTS):
            found.append(token)
            claimed.append(match.span())

    def _inside_claim(start: int, end: int) -> bool:
        return any(start >= s and end <= e for s, e in claimed)

    for match in re.finditer(r"[A-Za-z0-9]+", text):
        token = match.group(0)
        if _inside_claim(*match.span()):
            continue
        if not any(ch.isdigit() for ch in token):
            continue
        if _YEAR_RE.match(token):
            continue
        if len(token) < 2:
            continue
        # Word-joined form: 'No. 381' / 'TK 1624' — keep the joining word with
        # the part number so a provider matching on the full label still sees it.
        prefix = re.search(r"([A-Za-z]{1,6}\.?)\s+$", text[: match.start()])
        if prefix and not any(ch.isdigit() for ch in prefix.group(1)):
            found.append(f"{prefix.group(1)} {token}")
        found.append(token)

    seen: set = set()
    ordered: List[str] = []
    for token in found:
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(token)
    return ordered


def bounded_query_variants(
    query: str,
    max_chars: int = 500,
    max_variants: int = 8,
    overlap: Optional[int] = None,
) -> List[str]:
    """Split a query into provider-sized pieces that TOGETHER still cover it.

    The failure this replaces was a bare ``query[:N]``: a turn naming twenty
    machines with the last eight past the cut searched only the first twelve
    and then reported a confident total for all twenty. A character limit is a
    transport constraint, not a licence to drop constraints.

    The decomposition is OVERLAPPING WINDOWS over the original text, so the
    union of the variants is the whole query — not a rephrasing, not a summary,
    and never a reordering. Overlap matters: without it an identifier
    straddling a window boundary is lost by both halves, which is the one case
    a naive chunker cannot detect from the pieces alone. Each identifier also
    gets its own variant so a code is never diluted by surrounding prose in a
    provider that scores the whole string.

    When the text is too long for ``max_variants`` windows the head and the tail
    are covered and the MIDDLE is reported as uncovered rather than quietly
    dropped — a bounded search says what it did not reach. Pair the call with
    ``query_coverage`` to assert on it.

    A query that already fits is returned unchanged as one variant, so the
    common case costs nothing.
    """
    text = (query or "").strip()
    if not text:
        return []
    max_chars = max(16, int(max_chars))
    if len(text) <= max_chars:
        return [text]

    step = max(1, max_chars - (overlap if overlap is not None
                               else max(24, max_chars // 5)))
    # Window edges snap to a token boundary. Slicing at an arbitrary offset cut
    # "invoice 4417" into "nvoice 4417", which is still a dropped constraint in
    # substance — a provider asked for the fragment may not match the whole
    # token — while `query_coverage` reported the run complete because the
    # surviving fragment "4417" matched. The coverage check could not see it.
    windows: List[str] = []
    start = 0
    while start < len(text) and len(windows) < max_variants:
        end = min(start + max_chars, len(text))
        if end < len(text):
            boundary = text.find(" ", start + max_chars // 2, end)
            if boundary != -1:
                end = boundary
        piece = text[start:end].strip()
        if piece and piece not in windows:
            windows.append(piece)
        if end >= len(text):
            break
        nxt = text.find(" ", end)
        start = (nxt + 1) if nxt != -1 else end
        if start >= len(text):
            break

    if windows and windows[-1] != text[-max_chars:].strip():
        windows[-1] = text[-max_chars:].strip()

    seen: set = set()
    variants: List[str] = []
    for candidate in windows:
        if candidate and candidate not in seen:
            seen.add(candidate)
            variants.append(candidate)

    # Windows guarantee COVERAGE. A bare identifier variant adds PRECISION for
    # providers that score the whole string against a document, so it is worth
    # the remaining budget — but it is a bonus, never the mechanism that makes
    # the search complete, and it must not push a window out.
    covered = {t.lower() for v in variants for t in exact_identifiers(v)}
    for token in exact_identifiers(text):
        if token.lower() in covered or token in variants:
            continue
        if len(variants) >= max_variants:
            break
        variants.append(token)

    return variants[:max_variants]


def query_coverage(query: str, sent: Any) -> Dict[str, Any]:
    """Which of the query's exact identifiers actually reached a provider.

    ``sent`` is what was really transmitted: a string, or the sequence of
    strings a decomposed search sent. Returns the requested set, the
    transmitted set, and the identifiers that were dropped, so a caller can
    report a bounded search instead of implying it covered everything. This is
    the assertion a truncation regression has to fail — the drop must be
    DETECTABLE, not merely avoided in the common case.
    """
    requested = exact_identifiers(query)
    parts = [sent] if isinstance(sent, str) else list(sent or [])
    transmitted: set = set()
    for part in parts:
        transmitted.update(t.lower() for t in exact_identifiers(part))
    dropped = [t for t in requested if t.lower() not in transmitted]
    return {
        "requested_identifiers": requested,
        "transmitted_identifiers": sorted(transmitted),
        "dropped_identifiers": dropped,
        "complete": not dropped,
    }


def _http_status_of(err: BaseException) -> Optional[int]:
    """HTTP status of an HTTP error, None for non-HTTP failures. Works for
    httpx/requests HTTPStatusError alike via the shared .response shape."""
    response = getattr(err, "response", None)
    status = getattr(response, "status_code", None)
    return status if isinstance(status, int) else None


# Value-specific client rejections: the request itself is invalid for THIS
# search value, so other rungs (different values) can still succeed. Auth,
# rate-limit and server errors recur for every rung — those keep the
# fail-fast behavior.
_PROVIDER_LEVEL_STATUSES = frozenset({401, 403, 429})


def _is_value_level_error(err: BaseException) -> bool:
    """True when the provider rejected THIS attempt's value (4xx validation)
    rather than the provider/credentials being unavailable."""
    status = _http_status_of(err)
    return (
        status is not None
        and 400 <= status < 500
        and status not in _PROVIDER_LEVEL_STATUSES
    )


# --- Client-side ranked filtering -------------------------------------------

def _term_norms_for(query: str) -> Tuple[str, List[str]]:
    query_norm = normalize_code(query)
    term_norms = [normalize_code(t) for t in query_terms(query)]
    if query_norm not in term_norms:
        term_norms.append(query_norm)
    return query_norm, term_norms


def record_score(text: str, query_norm: str, term_norms: Sequence[str]) -> int:
    """Relevance of one record's text against the query: 3 = the text IS
    the query (skeleton-equal — reunites 'wg350dsav' with 'WG-350DSAV'),
    2 = contains an identifier term, 0 = matched only via a prose term or
    the provider's own ranking."""
    text_norm = normalize_code(text)
    if not text_norm:
        return 0
    if query_norm and text_norm == query_norm:
        return 3
    for tn in term_norms:
        if not tn:
            continue
        if text_norm == tn:
            return 2
        if len(tn) >= 4 and tn in text_norm:
            return 2
    return 0


def _texts_of(record: Any, text_of: Optional[Callable[[Any], str]]) -> str:
    if text_of is not None:
        return text_of(record) or ""
    return str(record)


def filter_by_terms_meta(
    records: Sequence[Any],
    query: str,
    text_of: Optional[Callable[[Any], str]] = None,
    limit: int = 8,
) -> Tuple[List[Any], int]:
    """filter_by_terms, but also returns how many records matched in total.

    A capped result set is only honest when the caller can say "showing 8 of
    41 matches" — without the matched count the agent reads a truncated list
    as the complete answer (the 100K-record mail/store class: the first page
    looks exhaustive). Returns (top-``limit`` records, total_matched)."""
    query = (query or "").strip()
    if not query:
        return [], 0
    terms = [t.lower() for t in query.split() if len(t) >= 3] or [query.lower()]
    scored: List[Tuple[int, int, Any]] = []
    for idx, record in enumerate(records):
        hay = _texts_of(record, text_of).lower()
        weight = sum(len(t) for t in terms if t in hay)
        if weight:
            scored.append((-weight, idx, record))
    scored.sort(key=lambda entry: (entry[0], entry[1]))
    return [record for _w, _i, record in scored[:limit]], len(scored)


def filter_by_terms(
    records: Sequence[Any],
    query: str,
    text_of: Optional[Callable[[Any], str]] = None,
    limit: int = 8,
) -> List[Any]:
    """Client-side relevance filter for list endpoints that lack a
    server-side search param. ANY query term (>=3 chars; falls back to
    the whole query) matches, and matches are RANKED by the total length of
    the terms they hit — a record containing the model code outranks one
    that merely shares a prose word — with recency (original) order preserved
    for ties. Unranked first-N filtering buried the identifier the question
    was about (live 2026-09-04)."""
    return filter_by_terms_meta(records, query, text_of=text_of, limit=limit)[0]


def rank_records(
    records: Sequence[Any],
    query: str,
    name_of: Callable[[Any], str],
    limit: Optional[int] = None,
) -> List[Any]:
    """Skeleton-aware ranking for records already fetched by a provider
    search: exact-name matches first, name-contains next, provider order
    last. Complements filter_by_terms, whose term weights ignore
    spelling variants ('wg350dsav' vs 'WG-350DSAV')."""
    query_norm, term_norms = _term_norms_for(query)
    scored: List[Tuple[int, int, Any]] = []
    for idx, record in enumerate(records):
        score = record_score(name_of(record), query_norm, term_norms)
        scored.append((-score, idx, record))
    scored.sort(key=lambda entry: (entry[0], entry[1]))
    out = [record for _s, _i, record in scored]
    return out[:limit] if limit is not None else out


# --- Server-side attempt ladder ---------------------------------------------

async def run_search_ladder(
    fetch: Callable[[str, str], Awaitable[Sequence[Any]]],
    query: str,
    name_of: Callable[[Any], str],
    max_calls: int = 5,
    max_tokens: int = 3,
    limit: Optional[int] = None,
) -> List[Any]:
    """Run a bounded ladder of provider search attempts and return ranked
    candidates.

    ``fetch(kind, value)`` performs ONE provider search call — ``kind`` is
    the caller's search-parameter discriminator (e.g. 'text' for
    Zoho's search_text, 'name' for name_contains) and must return the raw
    record sequence (empty on zero hits; raising is allowed). The ladder:

      1. full query against both parameter kinds (provider full-text
         reaches descriptions; the name-substring kind reaches hyphenated
         names the tokenizer splits);
      2. per token (identifier-shaped first): name kind, then text kind —
         recovers 'Linmac WG-350DSAV', which token-ANDing APIs zero out;
      3. alpha-prefix-stripped variants: recovers 'wg350dsav' against the
         name 'WG-350DSAV'.

    Stops at the first skeleton-exact name hit, caps provider calls at
    ``max_calls``, and FAILS FAST when the first attempt hits a PROVIDER-
    LEVEL error (transport, auth 401/403, rate-limit 429, 5xx — every
    remaining rung would fail the same way; don't hammer them). A 4xx
    VALIDATION error is value-specific and does NOT abort the ladder —
    not even on the first attempt: the full-query rung can be rejected for
    shape reasons the per-token rungs don't share (live 2026-09-13, canvas
    a1a13834: a 126-char enriched query tripped Zoho's 100-char search_text
    cap with HTTP 400 code 15 — validated BEFORE auth — and the abort meant
    the 'F-5216' token rung that answered the question never ran; the turn
    reported a 'timed out' Zoho Inventory lookup that had actually 400'd).
    Later attempt errors are skipped. Ranked by record_score so the exact
    item surfaces even when the winning attempt matched hundreds of rows.
    """
    query = (query or "").strip()
    if not query:
        return []
    attempts: List[Tuple[str, str]] = [("text", query), ("name", query)]
    seen = set(attempts)
    for tok in query_terms(query)[:max_tokens]:
        for kind in ("name", "text"):
            if (kind, tok) not in seen:
                attempts.append((kind, tok))
                seen.add((kind, tok))
        for variant in identifier_variants(tok):
            if ("name", variant) not in seen:
                attempts.append(("name", variant))
                seen.add(("name", variant))

    query_norm, term_norms = _term_norms_for(query)
    candidates: dict = {}
    calls = 0
    exact_found = False
    for attempt_no, (kind, value) in enumerate(attempts):
        if calls >= max_calls:
            break
        try:
            hits = await fetch(kind, value)
        except Exception as err:
            if attempt_no == 0 and not _is_value_level_error(err):
                raise
            continue
        calls += 1
        for record in hits or []:
            key = getattr(record, "get", None) and (
                record.get("item_id") or record.get("id") or id(record)
            ) or id(record)
            score = record_score(name_of(record), query_norm, term_norms)
            current = candidates.get(key)
            if current is None or score > current[0]:
                candidates[key] = (score, record)
            if score >= 3:
                exact_found = True
        if exact_found:
            break
    ranked = sorted(candidates.values(), key=lambda pair: -pair[0])
    out = [record for _score, record in ranked]
    return out[:limit] if limit is not None else out
