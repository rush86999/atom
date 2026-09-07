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
from typing import Any, Awaitable, Callable, List, Optional, Sequence, Tuple

# --- Identifier shapes -------------------------------------------------------

_ALPHA_PREFIX_RE = re.compile(r"^[a-z]+(?=[0-9])", re.IGNORECASE)


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
    the per-token retry order for providers whose search ANDs tokens."""
    terms = [
        t for t in dict.fromkeys(re.findall(r"[A-Za-z0-9]+", query or ""))
        if len(t) >= min_len
    ]
    terms.sort(key=identifier_rank)
    return terms


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


def filter_by_terms(
    records: Sequence[Any],
    query: str,
    text_of: Optional[Callable[[Any], str]] = None,
    limit: int = 8,
) -> List[Any]:
    """Client-side relevance filter for list endpoints that lack a
    server-side search param. ANY query term (>=3 chars; falls back to the
    whole query) matches, and matches are RANKED by the total length of the
    terms they hit — a record containing the model code outranks one that
    merely shares a prose word — with recency (original) order preserved
    for ties. Unranked first-N filtering buried the identifier the question
    was about (live 2026-09-04)."""
    query = (query or "").strip()
    if not query:
        return []
    terms = [t.lower() for t in query.split() if len(t) >= 3] or [query.lower()]
    scored: List[Tuple[int, int, Any]] = []
    for idx, record in enumerate(records):
        hay = _texts_of(record, text_of).lower()
        weight = sum(len(t) for t in terms if t in hay)
        if weight:
            scored.append((-weight, idx, record))
    scored.sort(key=lambda entry: (entry[0], entry[1]))
    return [record for _w, _i, record in scored[:limit]]


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
    ``max_calls``, and FAILS FAST when the first attempt raises (provider
    unreachable — don't hammer the remaining ladder into the same failure);
    later attempt errors are skipped. Ranked by record_score so the exact
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
        except Exception:
            if attempt_no == 0:
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
