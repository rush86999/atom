"""Structured workbook read artifacts and target coverage."""
from __future__ import annotations

import hashlib
import io
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Sequence

_TARGET_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:[A-Za-z]{1,10}-[0-9](?![A-Za-z0-9])|"
    r"[A-Za-z]{1,10}(?:-[A-Za-z0-9]+)*[0-9][A-Za-z0-9-]*|"
    r"[0-9]{2,6})(?![A-Za-z0-9])"
)
_YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")
# Value-column vocabulary — GENERIC across domains: headers that carry a
# measurable figure. Price lookup is one use case; any requested field
# whose word appears in a header is selected too (see
# extract_attributes — the request's own words drive column selection).
_VALUE_HEADER_RE = re.compile(
    r"price|cost|amount|rate|value|msrp|list|wholesale|currency",
    re.IGNORECASE,
)
# Kept as an alias during transition; behavior identical.
_PRICE_HEADER_RE = _VALUE_HEADER_RE

_ATTRIBUTE_STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "these",
    "those", "find", "search", "check", "look", "what", "which", "where",
    "how", "much", "many", "does", "are", "is", "was", "were", "have",
    "has", "please", "file", "files", "sheet", "sheets", "workbook",
    "spreadsheet", "excel", "table", "row", "rows", "column", "columns",
    "prices", "price", "values", "value", "data", "list", "all", "any",
    "each", "per", "into", "about", "give", "show", "tell", "get",
    "xlsx", "xls", "csv", "tsv", "pdf", "docx", "doc",
}

_FIELD_ALIASES: Dict[str, Sequence[str]] = {
    "price": (
        "price", "cost", "amount", "value", "msrp", "list", "wholesale",
        "dealer price", "dealer cost", "factory price", "retail",
        "unit cost", "selling price", "quote",
    ),
    "quantity": (
        "quantity", "qty", "stock", "on hand", "available", "units", "count",
        "quantity on hand", "available quantity",
    ),
    "weight": ("weight", "mass", "gross weight", "net weight"),
    "lead_time": (
        "lead time", "delivery time", "lead-time", "delivery", "duration",
    ),
    "date": ("date", "effective date", "start date", "end date"),
    "certification_date": (
        "certification date", "certification expiry", "certification expiration",
        "certification valid through", "certification valid until",
    ),
    "expiration_date": (
        "expiration date", "expiry date", "expires", "expire", "expiration",
        "valid through", "valid until", "expiry",
    ),
    "required_version": (
        "required version", "minimum version", "min version", "version requirement",
        "version requirements", "software version requirement",
        "software version requirements", "supported version",
        "required software version",
    ),
    "version": (
        "software version", "application version", "version", "release",
        "revision", "build",
    ),
    "organization": (
        "organization", "company", "manufacturer", "supplier", "vendor",
        "owner", "issuer", "brand", "make",
    ),
    "employee": ("employee", "staff", "worker", "person", "team member"),
    "category": ("category", "type", "class", "classification"),
    "location": ("location", "region", "site", "facility", "branch"),
    "status": ("status", "state", "condition"),
}
_UNIT_TOKENS = {
    "kg", "g", "mg", "lb", "lbs", "oz", "cm", "mm", "m", "in", "ft",
    "day", "days", "week", "weeks", "hour", "hours", "minute", "minutes",
    "month", "months", "year", "years", "percent", "pct", "each", "unit",
    "units", "piece", "pieces", "item", "items", "usd", "cad", "eur", "gbp",
    "aud", "nzd", "jpy", "inr", "mxn", "brl", "zar",
}
def _normalize_field_text(value: Any) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(value or ""))
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).lower()
    text = re.sub(r"\b([a-z])\s+(?=[a-z]\b)", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


_FIELD_ALIAS_ORDER = sorted(
    _FIELD_ALIASES,
    key=lambda key: max(
        (len(_normalize_field_text(alias)) for alias in _FIELD_ALIASES[key]),
        default=0,
    ),
    reverse=True,
)
_FIELD_REQUEST_GROUPS = {
    "price", "quantity", "weight", "lead_time", "date",
    "certification_date", "expiration_date", "required_version", "version",
    "category", "location", "status",
}


def _field_base_and_unit(header: Any) -> tuple[str, Optional[str]]:
    text = str(header or "").strip()
    unit_match = re.search(r"\(([^()]*)\)", text)
    unit = None
    if unit_match:
        candidate = _normalize_field_text(unit_match.group(1))
        if candidate in _UNIT_TOKENS or re.fullmatch(
            r"[a-z]{3,5}\s*/\s*[a-z0-9]+", candidate
        ):
            unit = unit_match.group(1).strip()
            text = re.sub(r"\s*\([^()]*\)", "", text)
    normalized = _normalize_field_text(text)
    tokens = normalized.split()
    while tokens and tokens[-1] in _UNIT_TOKENS:
        unit = unit or tokens.pop()
        normalized = " ".join(tokens)
    return normalized, unit


def _field_aliases(field: Any) -> tuple[str, ...]:
    normalized = _normalize_field_text(field)
    for canonical, aliases in _FIELD_ALIASES.items():
        normalized_aliases = tuple(
            _normalize_field_text(alias) for alias in (canonical, *aliases)
        )
        if normalized in normalized_aliases:
            return (canonical, *normalized_aliases)
    return (normalized,) if normalized else ()


def _canonical_field_name(field: Any) -> str:
    aliases = _field_aliases(field)
    for alias in _FIELD_ALIAS_ORDER:
        if alias in aliases:
            return alias
    return aliases[0] if aliases else _normalize_field_text(field)


def _field_phrase_matches(header: Any, field: Any) -> bool:
    base, _unit = _field_base_and_unit(header)
    aliases = _field_aliases(field)
    if not base:
        return False
    for alias in aliases:
        alias = _normalize_field_text(alias)
        if not alias:
            continue
        if base == alias or base.startswith(alias + " "):
            return True
        if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", base):
            return True
    return False


def extract_field_requests(texts: Sequence[str]) -> List[str]:
    values: List[str] = []
    seen = set()
    for text in texts or []:
        normalized = _normalize_field_text(text)
        if not normalized:
            continue
        for canonical in _FIELD_ALIAS_ORDER:
            aliases = _field_aliases(canonical)
            if any(
                re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized)
                for alias in aliases
                if alias
            ):
                if (
                    canonical in _FIELD_REQUEST_GROUPS
                    and canonical not in seen
                ):
                    seen.add(canonical)
                    values.append(canonical)
    return [
        value for value in values
        if not any(
            value != other
            and _field_phrase_matches(other, value)
            for other in values
        )
    ]


def _column_descriptors(
    labels: Sequence[Any], *, positions: Optional[Sequence[int]] = None,
) -> List[Dict[str, Any]]:
    descriptors: List[Dict[str, Any]] = []
    for index, label in enumerate(labels):
        position = int(positions[index]) if positions else index
        base, unit = _field_base_and_unit(label)
        if re.search(r"(?:[_ ])\d+$", base):
            base = re.sub(r"(?:[_ ])\d+$", "", base)
        descriptors.append({
            "position": position,
            "label": str(label or "").strip(),
            "base": base,
            "unit": unit,
        })
    counts: Dict[str, int] = {}
    for item in descriptors:
        counts[item["base"]] = counts.get(item["base"], 0) + 1
    for item in descriptors:
        item["duplicate"] = counts.get(item["base"], 0) > 1
    return descriptors


def _select_value_columns(
    descriptors: Sequence[Dict[str, Any]],
    attributes: Sequence[str] = (),
    requested_fields: Sequence[str] = (),
) -> Dict[str, Any]:
    requested = []
    for field in requested_fields or ():
        canonical = _canonical_field_name(field)
        if canonical and canonical not in requested:
            requested.append(canonical)
    inferred = []
    for field in attributes or ():
        canonical = _canonical_field_name(field)
        if canonical in _FIELD_ALIASES and canonical not in inferred:
            inferred.append(canonical)
    if not requested:
        requested = inferred
    raw_terms = [
        _normalize_field_text(field) for field in (attributes or ())
        if _normalize_field_text(field)
        and _canonical_field_name(field) not in _FIELD_ALIASES
    ]
    matches: Dict[str, List[Dict[str, Any]]] = {}
    selected: List[Dict[str, Any]] = []
    for item in descriptors:
        label = item.get("label") or ""
        if requested:
            for field in requested:
                if _field_phrase_matches(label, field):
                    matches.setdefault(field, []).append(item)
                    if item not in selected:
                        selected.append(item)
        elif any(
            _stem(term) in _stem(_normalize_field_text(label))
            or _stem(_normalize_field_text(label)) in _stem(term)
            for term in raw_terms
        ):
            selected.append(item)
        elif _VALUE_HEADER_RE.search(str(label)):
            selected.append(item)
    if not requested and not raw_terms:
        matches["generic_value"] = [
            item for item in selected
            if _VALUE_HEADER_RE.search(str(item.get("label") or ""))
        ]
    selected_positions = {id(item) for item in selected}
    selected = [item for item in descriptors if id(item) in selected_positions]
    ambiguous_fields: List[str] = []
    for field, candidates in matches.items():
        if len(candidates) < 2:
            continue
        bases = {_normalize_field_text(item.get("base")) for item in candidates}
        units = {item.get("unit") for item in candidates}
        if len(bases) == 1 and len(units) > 1:
            continue
        if field in {"quantity", "date", "version"}:
            continue
        ambiguous_fields.append(field)
    label_groups: Dict[tuple[str, Optional[str]], int] = {}
    for item in selected:
        key = (str(item.get("base") or ""), item.get("unit"))
        label_groups[key] = label_groups.get(key, 0) + 1
    duplicate_labels = [
        base for (base, _unit), count in label_groups.items() if count > 1
    ]
    unmatched = [field for field in requested if not matches.get(field)]
    return {
        "requested_fields": requested,
        "selected": selected,
        "selected_columns": [item.get("label") for item in selected],
        "ambiguous": bool(ambiguous_fields or duplicate_labels),
        "ambiguous_fields": ambiguous_fields,
        "duplicate_labels": duplicate_labels,
        "unmatched_fields": unmatched,
        "matched_fields": {
            field: [item.get("label") for item in candidates]
            for field, candidates in matches.items()
        },
    }


_HEADER_TERM_RE = re.compile(
    r"id|name|code|sku|item|model|part|product|description|date|time|"
    r"status|state|version|revision|release|quantity|qty|stock|weight|"
    r"mass|price|cost|amount|value|rate|lead|delivery|expiry|expiration|"
    r"certification|organization|company|manufacturer|supplier|owner|"
    r"category|region|location|unit|minimum|maximum|required|available",
    re.IGNORECASE,
)


def _header_candidate(
    values: Sequence[Any], *, require_label: bool = False,
) -> bool:
    nonempty = [_cell_text(value) for value in values if _cell_text(value)]
    if len(nonempty) < 2:
        return False
    numeric = sum(
        bool(re.fullmatch(r"[-+]?\d+(?:\.\d+)?", value))
        for value in nonempty
    )
    if numeric > max(1, int(len(nonempty) * 0.4)):
        return False
    if require_label and not any(_HEADER_TERM_RE.search(value) for value in nonempty):
        return False
    return True


def _infer_header_map(rows: Sequence[Sequence[Any]]) -> tuple[Dict[int, str], List[int]]:
    primary = None
    for index, row in enumerate(rows[:12]):
        if _header_candidate([cell.value for cell in row]):
            primary = index
            break
    if primary is None:
        return {}, []
    header_indices = [primary]
    for index in range(primary + 1, min(len(rows), primary + 4)):
        values = [cell.value for cell in rows[index]]
        if not _header_candidate(values, require_label=True):
            break
        header_indices.append(index)
    labels: Dict[int, List[str]] = {}
    for index in header_indices:
        for cell in rows[index]:
            value = _cell_text(cell.value)
            if value and (cell.column not in labels or value not in labels[cell.column]):
                labels.setdefault(cell.column, []).append(value)
    return {
        column: " ".join(values)
        for column, values in labels.items()
    }, [index + 1 for index in header_indices]


def extract_attributes(
    texts: Sequence[str], targets: Sequence[str],
) -> List[str]:
    """Request-supplied attribute words for entity disambiguation and
    field selection: distinctive words from the request, minus the target
    identifiers themselves and minus generic ask vocabulary (2026-09-24
    review: use attributes the request supplies — manufacturer, brand,
    category, version, field names — matched against the source schema;
    never business-specific lists)."""
    target_tokens = set()
    for target in targets or []:
        target_tokens.update(
            re.findall(r"[a-z0-9]+", str(target).lower()))
    out: List[str] = []
    seen = set()
    for text in texts or []:
        for word in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,24}", str(text or "")):
            cleaned = word.strip().lower()
            key = re.sub(r"[^a-z0-9]+", "", cleaned)
            if (
                len(key) >= 4
                and key not in seen
                and cleaned not in _ATTRIBUTE_STOPWORDS
                and not any(t in key.split() or key in t for t in (
                    target_tokens or set()))
            ):
                seen.add(key)
                out.append(cleaned)
    return out[:16]
_TARGET_EVIDENCE_CAP = 128
#: Extraction contract version. Bumped when target-construction rules
#: change semantics (2026-09-24: v2 — monetary amounts, cents tails, and
#: delivery durations excluded positionally; name targets merged
#: identity-like; filename words never entities). Persisted target lists
#: stamped with an older version are RE-DERIVED, not replayed.
TARGET_EXTRACTION_VERSION = 3
_CURRENCY_RE = re.compile(
    r"\b(?:CAD|USD|EUR|GBP|AUD|NZD|JPY|CHF|INR|MXN|BRL|ZAR)\b|"
    r"\[[$€£¥₹₩₽₺-][^\]]*\]",
    re.IGNORECASE,
)


def _canonical(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def _is_year(value: str) -> bool:
    return bool(_YEAR_RE.fullmatch(str(value or "").strip()))


# VALUE CONTEXT: a numeric run that is part of a monetary amount or a
# duration is a VALUE, not an identity. Positional guards — never a
# blanket number filter (numeric identifiers like 381 stay valid).
_MONEY_BEFORE_RE = re.compile(
    r"[$€£¥₹₩₽₺]\s*$|\b(?:USD|CAD|EUR|GBP|INR|AUD)\s*$"
    r"|[$€£¥₹₩₽₺]\s*[\d,]*\s*$")  # symbol + leading digits/commas of the same amount
_DECIMAL_BEFORE_RE = re.compile(r"\d\s*[.,]\s*$")  # "2,902." then "00" = cents
_CENTS_AFTER_RE = re.compile(r"^\s*[.,]\s*\d{2}\b")
_DURATION_AFTER_RE = re.compile(
    r"^\s*(?:[–—-]\s*\d+\s*)?(?:weeks?|days?|months?|hrs?|hours?)\b",
    re.IGNORECASE,
)
# A COMPLETED monetary amount immediately before (whitespace-separated):
# '... $1,777.00 609' — the bare 609 is a value continuation (qty,
# another amount fragment), not an identifier. 'No. 381' differs: an
# IDENTIFIER MARKER precedes it.
_AMOUNT_BEFORE_RE = re.compile(
    r"\d[\d,]*[.,]\d+\s*$|[$€£¥₹₩₽₺]\s*[\d,]+\s*$")
_ID_MARKER_BEFORE_RE = re.compile(
    r"(?:\b(?:no|nr|num|model|item|part|sku|code|id|ref)\.?\s*$)",
    re.IGNORECASE,
)


def _is_value_position(
    text: str, start: int, end: int, match_run: str = "",
) -> bool:
    """Is the numeric run at text[start:end] part of a monetary amount or
    a delivery duration? (2026-09-24 review: 'No. 381 $2,902.00 10-11
    weeks' extracted 902/00/10/11 as identifiers.)"""
    match_run = match_run or text[start:end]
    match_run_is_numeric = match_run.isdigit()
    before = text[max(0, start - 8):start]
    after = text[end:end + 16]
    if _MONEY_BEFORE_RE.search(before):
        return True
    if _CENTS_AFTER_RE.match(after):
        return True
    if (
        _DECIMAL_BEFORE_RE.search(before)
        and match_run_is_numeric
        and len(match_run) <= 2
    ):
        return True  # the cents tail of a decimal amount
    if (
        match_run_is_numeric
        and _AMOUNT_BEFORE_RE.search(before)
        and not _ID_MARKER_BEFORE_RE.search(before)
    ):
        return True  # bare number trailing a completed amount
    if _DURATION_AFTER_RE.match(after):
        return True
    return False


def extract_targets(
    query: str = "", context_texts: Optional[Sequence[str]] = None,
    explicit: Optional[Sequence[str]] = None,
) -> List[str]:
    """Extract likely item/model identifiers without treating years,
    monetary amounts, or delivery durations as targets."""
    values: List[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        text = str(value or "").strip()
        if not text or _is_year(text):
            return
        canonical = _canonical(text)
        if len(canonical) < 2 or canonical in seen:
            return
        seen.add(canonical)
        values.append(text)

    for value in explicit or []:
        add(value)
    if values:
        return values[:64]
    for text in [query or "", *(context_texts or [])]:
        raw = str(text or "")
        for match in _TARGET_RE.finditer(raw):
            if _is_value_position(
                    raw, match.start(), match.end(), match.group(0)):
                continue
            add(match.group(0))
    # ALWAYS run name extraction; merge only IDENTITY-LIKE names when
    # numeric targets already exist (a mixed list keeps its name-only
    # entities without importing prose fragments); with no numeric
    # targets, all extracted names ride (the pre-merge behavior).
    _numeric_count = len(values)
    _named: List[str] = []
    if True:
        named_target = re.compile(
            r"\b(?:for|of|does|do|is|are)\s+"
            r"([A-Za-z][A-Za-z0-9_-]*(?:\s+[A-Za-z][A-Za-z0-9_-]*){0,3})"
        )
        quoted_target = re.compile(r"[\"']([^\"']{2,80})[\"']")
        ignored_words = {
            "the", "require", "required", "in", "from", "of",
            "for", "version", "minimum", "maximum", "when", "does", "is",
            "what", "which", "how", "many", "expire", "expiration", "on",
            "hand", "certification", "date",
        }
        _FILENAME_TOKEN_RE = re.compile(
    r"\b(?:[A-Z0-9][A-Za-z0-9_()'\ -]*"
    r"(?:\s+[A-Z0-9][A-Za-z0-9_()'\ -]*){0,6})"
    r"\.(?:xlsx|xls|xlsm|csv|tsv|pdf|docx?|pptx?|txt|md|json)\b"
)


# Filename tokens: space-joined words each starting uppercase
        # or a digit (real filenames: 'Consolidated Price List
        # 2019.xlsx'); lowercase prose words terminate the token so the
        # blanking cannot swallow the sentence ('ingest-api is
        # supported in Platform Matrix.xlsx' keeps 'ingest-api').
        _FILENAME_RE = re.compile(
            r"\b(?:[A-Z0-9][A-Za-z0-9_()'\-]*"
            r"(?:\s+[A-Z0-9][A-Za-z0-9_()'\-]*){0,6})"
            r"\.(?:xlsx|xls|xlsm|csv|tsv|pdf|docx?|pptx?|txt|md|json)\b"
        )
        for text in [query or "", *(context_texts or [])]:
            # FILENAME WORDS ARE NOT ENTITIES: blank filename tokens
            # before name extraction so 'Stock Status.xlsx' cannot
            # contribute 'Stock'.
            value_text = _FILENAME_RE.sub(" ", str(text or ""))
            for match in quoted_target.finditer(value_text):
                _named.append(match.group(1))
            for match in named_target.finditer(value_text):
                words = match.group(1).split()
                while words and words[0].lower() in ignored_words:
                    words.pop(0)
                kept: List[str] = []
                for word in words:
                    if word.lower() in ignored_words:
                        break
                    if kept and not (word[:1].isupper() or "-" in word):
                        break
                    kept.append(word)
                if kept:
                    _named.append(" ".join(kept))
    # CAPITALIZED-PHRASE LANE (2026-09-24 reconfirmation): 'Manual
    # Flanger' — a 2+ word capitalized phrase not inside a filename and
    # not stopword-led — is an entity even mid-list and even when
    # numeric identifiers already exist.
    _cap_phrase = re.compile(
        r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,4})\b")
    _CAP_STOP = {
        "The", "This", "That", "These", "Those", "Find", "Check",
        "Search", "Please", "When", "Does", "What", "Which", "How",
        "And", "For", "With", "From", "List", "Price", "Prices",
        "Consolidated", "Stock", "Status", "Training", "Records",
        "Platform", "Matrix", "Warehouse", "Snapshot", "Spec",
    }
    _source_for_caps = [query or "", *(context_texts or [])]
    for source_text in _source_for_caps:
        raw_src = _FILENAME_TOKEN_RE.sub(" ", str(source_text or ""))
        for match in _cap_phrase.finditer(raw_src):
            phrase = match.group(1).strip()
            words = phrase.split()
            if words[0] in _CAP_STOP:
                continue
            _named.append(phrase)
    for name in _named:
        text = str(name or "").strip()
        canonical = _canonical(text)
        if not text or len(canonical) < 2 or canonical in seen:
            continue
        if _numeric_count and not (
            any(ch.isdigit() for ch in text)
            or "-" in text
            or any(w[:1].isupper() for w in text.split())
        ):
            continue  # prose fragment, not an identity
        if len(text.split()) == 1 and text.isalpha() and len(text) <= 3:
            continue  # e.g. 'No' from 'No. 381'
        seen.add(canonical)
        values.append(text)
    return values[:64]


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _matches_target(target: str, value: Any) -> bool:
    text = _cell_text(value)
    target_text = str(target or "").strip()
    if not text or not target_text:
        return False
    return re.search(
        rf"(?<![A-Za-z0-9_-]){re.escape(target_text)}(?![A-Za-z0-9_-])",
        text,
        re.IGNORECASE,
    ) is not None



def _is_designation_match(
    text: str, column_header: str
) -> bool:
    """Is this match a plausible PRODUCT-ROW designation rather than a
    numeric coincidence?

    A numeric collision (the cell VALUE happens to be 381.6 in an
    exchange-rate or price column) is a CANDIDATE, not a product row
    (2026-09-24 review: use request/schema attribute corroboration; report
    ambiguity only when multiple plausible product rows remain). A match
    is a designation when the matched text carries letters (model codes
    like 'U-22', 'SLE24-16', '381mm') OR the cell sits outside every
    price-headed column (a model/part column), i.e. something in the ROW
    identifies it as a product row rather than a bare number.
    """
    header = str(column_header or "").strip()
    # ALPHANUMERIC CODES ARE DESIGNATIONS wherever they appear (2026-09-24
    # review: entity search, not just product rows): 'RF-2' in a
    # Certificate column, 'U-22' in any text column — a code with letters
    # is an identifier, never a numeric coincidence. Only PURE-NUMERIC
    # matches need the column-header corroboration below.
    if any(ch.isalpha() for ch in str(text or "")):
        if re.fullmatch(r"(?:c\d+|#ref!|\d+)", header, re.IGNORECASE):
            return False
        return True
    if re.fullmatch(r"(?:c\d+|#ref!|\d+)", header, re.IGNORECASE):
        return False
    if _VALUE_HEADER_RE.search(header) or re.search(
        r"quantity|qty|stock|weight|mass|lead|delivery|date|time|"
        r"expiry|expiration|version|revision|release",
        header,
        re.IGNORECASE,
    ):
        return False
    return bool(re.search(
        r"model|part|item|sku|product|description|name|catalog|cat\.?\s*no|code|"
        r"employee|staff|worker|person|component|software|application|"
        r"certification|requirement",
        header,
        re.IGNORECASE,
    ))

def _criteria_values(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        for key in ("value", "values", "name", "label"):
            if key in value:
                return _criteria_values(value.get(key))
        return []
    if isinstance(value, (list, tuple, set)):
        values: List[str] = []
        for item in value:
            values.extend(_criteria_values(item))
        return values
    text = _cell_text(value)
    return [text] if text else []


def _add_criteria_value(
    criteria: Dict[str, List[str]], attribute: Any, value: Any,
) -> None:
    field = re.sub(r"[^a-z0-9]+", "_", str(attribute or "").strip().lower())
    field = field.strip("_")
    if not field:
        return
    values = criteria.setdefault(field, [])
    for text in _criteria_values(value):
        if text.lower() not in {item.lower() for item in values}:
            values.append(text)


_INTERROGATIVE_GUARD = {
    "what", "which", "who", "whom", "whose", "when", "where", "why",
    "how", "the", "this", "that", "these", "those", "it", "there",
    "here", "name", "please", "kind", "sort", "type", "one", "find",
    "search", "check", "tell", "show", "give",
}


def extract_natural_language_criteria(
    texts: Sequence[str],
) -> Dict[str, List[str]]:
    criteria: Dict[str, List[str]] = {}
    possessive = re.compile(
        r"(?<![\w])([A-Za-z][A-Za-z0-9&.'-]*(?:\s+[A-Za-z][A-Za-z0-9&.'-]*){0,3})'s\b",
        re.IGNORECASE,
    )
    labelled = re.compile(
        r"\b(organization|company|manufacturer|supplier|vendor|owner|brand)"
        r"\s*(?:is|=|:)\s*([A-Za-z0-9][A-Za-z0-9 ._&-]*)",
        re.IGNORECASE,
    )
    for text in texts or []:
        value_text = str(text or "")
        for match in possessive.finditer(value_text):
            parts = match.group(1).strip().split()
            # INTERROGATIVE GUARD (2026-09-24): "when does A. Kumar's
            # certificate expire" is a QUESTION — the possessive phrase
            # 'when does A. Kumar' must never become an organization
            # constraint (it filtered out the only matching row).
            while parts and (
                parts[0].lower() in _ATTRIBUTE_STOPWORDS
                or parts[0].lower() in _INTERROGATIVE_GUARD
                or parts[0].lower() in {"does", "do", "did", "is", "are"}
            ):
                parts.pop(0)
            if parts and not parts[0].lower() in _INTERROGATIVE_GUARD:
                _add_criteria_value(criteria, "organization", " ".join(parts))
        for match in labelled.finditer(value_text):
            _add_criteria_value(criteria, match.group(1), match.group(2).strip())
    return criteria


def _disambiguation_criteria(
    query: str = "",
    context_texts: Optional[Sequence[str]] = None,
    explicit: Optional[Dict[str, Any]] = None,
) -> Dict[str, List[str]]:
    criteria: Dict[str, List[str]] = {}
    explicit = explicit or {}
    for container_key in ("attributes", "selectors", "fields", "filters", "constraints"):
        container = explicit.get(container_key)
        if isinstance(container, dict):
            for attribute, value in container.items():
                _add_criteria_value(criteria, attribute, value)
        elif isinstance(container, list):
            for selector in container:
                if not isinstance(selector, dict):
                    _add_criteria_value(criteria, container_key, selector)
                    continue
                attribute = (
                    selector.get("attribute")
                    or selector.get("field")
                    or selector.get("name")
                )
                value = selector.get("value", selector.get("values"))
                _add_criteria_value(criteria, attribute, value)
    for attribute, value in explicit.items():
        if attribute not in {
            "attributes", "selectors", "fields", "filters", "constraints"
        }:
            _add_criteria_value(criteria, attribute, value)

    pattern = re.compile(
        r"(?<![\w.])([A-Za-z][A-Za-z0-9 _-]{0,40}?)\s*(?:=|:|\bis\b)\s*"
        r"([^,;\n]+)",
        re.IGNORECASE,
    )
    for text in [query or "", *(context_texts or [])]:
        for match in pattern.finditer(str(text or "")):
            field_text = match.group(1).strip()
            if re.search(
                r"\.(?:xlsx|xls|csv|tsv|pdf|docx?)\s*$",
                field_text,
                re.IGNORECASE,
            ):
                continue
            # INTERROGATIVE GUARD (2026-09-24 review: ordinary requests
            # must not misparse as constraints): "what IS the weight" is a
            # question, not "what = the weight".
            if (not field_text
                    or field_text.lower().split()[0] in _INTERROGATIVE_GUARD
                    or len(field_text) < 3):
                continue
            _add_criteria_value(
                criteria, field_text, match.group(2).strip(" \"'")
            )
    for attribute, values in extract_natural_language_criteria(
        [query or "", *(context_texts or [])]
    ).items():
        for value in values:
            _add_criteria_value(criteria, attribute, value)
    return criteria



def _stem(word: str) -> str:
    """Light stem so 'expire' matches 'Expiry' and 'weight' matches
    'Weights': drop common English inflection suffixes from both sides of
    the comparison (field MEANING, not literal substring)."""
    w = re.sub(r"(?:ies|es|s|ion|ions|ing|ed|y)$", "", str(word or "").lower())
    return w if len(w) >= 3 else str(word or "").lower()


def _is_value_column(header: str, attributes: Sequence[str]) -> bool:
    """Does this column carry a requested VALUE? Generic value vocabulary
    (price/cost/rate/…) OR the request's own field words matching the
    header under light stemming (2026-09-24 review: requested fields
    drive selection — price lookup is one use case, not the pipeline)."""
    if _VALUE_HEADER_RE.search(str(header or "")):
        return True
    h = _stem(re.sub(r"[^a-z0-9 ]", " ", str(header or "").lower())).strip()
    for a in (attributes or []):
        sa = _stem(a)
        if sa and len(sa) >= 4 and (sa in h or h in sa):
            return True
    return bool(
        _select_value_columns(
            _column_descriptors([header]), attributes
        )["selected"]
    )


# Identity-headed columns: where an organization/brand/category attribute
# MEANS something (schema-driven; no business vocabulary).
_IDENTITY_HEADER_RE = re.compile(
    r"brand|vendor|manufacturer|supplier|make|company|organi[sz]ation|"
    r"category|type|family|owner|site|facility|name|source|provider",
    re.IGNORECASE,
)


def _row_identity_values(evidence: Dict[str, Any]) -> List[str]:
    headers = evidence.get("headers") or {}
    values: List[str] = []
    for item in evidence.get("row_context") or []:
        if not isinstance(item, dict):
            continue
        cell_ref = str(item.get("cell") or "")
        column_letter = re.match(r"([A-Z]+)", cell_ref)
        header = (
            headers.get(column_letter.group(1))
            if column_letter else None
        ) or item.get("field") or str(evidence.get("column") or "")
        if header and _IDENTITY_HEADER_RE.search(str(header)):
            value = str(item.get("value") or "").strip()
            if value:
                values.append(value)
    return values


def _attribute_corroborates(
    evidence: Dict[str, Any], attribute: str,
) -> bool:
    """Does this request-supplied attribute corroborate THIS hit? Only via
    the sheet name or a same-row cell in an identity-headed column —
    occurrence anywhere in the sheet is not corroboration (2026-09-24
    review: match attributes to their relevant fields)."""
    attr = str(attribute or "").strip().lower()
    if not attr:
        return False
    identity_values = _row_identity_values(evidence)
    if identity_values:
        return any(attr in value.lower() for value in identity_values)
    return attr in str(evidence.get("sheet") or "").lower()


def _matches_disambiguation(
    evidence: Dict[str, Any], criteria: Dict[str, List[str]],
) -> bool:
    row_context = [
        item for item in (evidence.get("row_context") or [])
        if isinstance(item, dict)
    ]
    all_values = _canonical(
        " ".join([
            str(evidence.get("sheet") or ""),
            *[
                str(item.get("value") or "")
                for item in row_context
            ],
        ])
    )

    def term_matches(term: str, haystack: str) -> bool:
        canonical = _canonical(term)
        if not canonical:
            return False
        if canonical in haystack:
            return True
        tokens = [
            token for token in re.findall(r"[a-z0-9]+", term.lower())
            if len(token) >= 3
        ]
        if not tokens:
            return False
        hits = sum(token in haystack.lower() for token in tokens)
        return hits >= max(1, (len(tokens) + 1) // 2)

    for attribute, terms in criteria.items():
        if not terms:
            continue
        field_values = [
            str(item.get("value") or "")
            for item in row_context
            if any(
                _field_phrase_matches(item.get("field"), alias)
                for alias in _field_aliases(attribute)
            )
        ]
        haystack = _canonical(" ".join(field_values)) if field_values else all_values
        if not any(term_matches(term, haystack) for term in terms):
            return False
    return True


def _currency_for(
    value: Any, number_format: str, header: str
) -> Dict[str, str]:
    header_text = str(header or "")
    format_text = str(number_format or "")
    explicit = _CURRENCY_RE.search(f"{header_text} {format_text}")
    if explicit:
        token = explicit.group(0).upper()
        for code in ("CAD", "USD", "EUR", "GBP", "AUD", "NZD", "JPY", "CHF", "INR", "MXN", "BRL", "ZAR"):
            if code in token:
                return {"currency": code, "currency_hint": token}
    if "$" in format_text or "$" in header_text:
        return {"currency": "unspecified", "currency_hint": "$"}
    if "€" in format_text or "€" in header_text:
        return {"currency": "unspecified", "currency_hint": "€"}
    if "£" in format_text or "£" in header_text:
        return {"currency": "unspecified", "currency_hint": "£"}
    return {"currency": "unspecified", "currency_hint": ""}


def _fallback_artifact(
    content: bytes,
    file_name: str,
    targets: Sequence[str],
    provider: Optional[str],
    resource_id: Optional[str],
    source_metadata: Optional[Dict[str, Any]],
    error: str,
    *,
    content_hash: Optional[str] = None,
    content_hash_algorithm: str = "sha256",
    ingested_at: Optional[str] = None,
    coverage_limits: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    digest = content_hash or (hashlib.sha256(content).hexdigest() if content else None)
    return {
        "provider": provider,
        "resource_id": resource_id,
        "file_name": file_name,
        "content_hash": digest,
        "content_hash_algorithm": content_hash_algorithm if digest else None,
        "ingested_at": ingested_at,
        "sha256": hashlib.sha256(content).hexdigest() if content else None,
        "byte_length": len(content) if content else None,
        "sheets": [],
        "sheet_count": 0,
        "all_sheets_searched": False,
        "truncated": True,
        "formula_status": "unavailable",
        "coverage": {
            "requested": list(targets),
            "outcomes": [
                {
                    "target": target,
                    "status": "incomplete",
                    "reason": error,
                    "evidence": [],
                }
                for target in targets
            ],
            "complete": False,
        },
        "source_metadata": dict(source_metadata or {}),
        "coverage_limits": dict(coverage_limits or {"error": error}),
    }


def inspect_workbook_bytes(
    content: bytes,
    file_name: str,
    *,
    query: str = "",
    context_texts: Optional[Sequence[str]] = None,
    targets: Optional[Sequence[str]] = None,
    attributes: Optional[Sequence[str]] = None,
    requested_fields: Optional[Sequence[str]] = None,
    provider: Optional[str] = None,
    resource_id: Optional[str] = None,
    source_metadata: Optional[Dict[str, Any]] = None,
    ingested_at: Optional[str] = None,
    disambiguation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Read every worksheet once and return one outcome per requested target."""
    requested = extract_targets(query, context_texts, targets)
    criteria = _disambiguation_criteria(query, context_texts, disambiguation)
    try:
        import openpyxl
    except Exception as exc:
        return _fallback_artifact(
            content, file_name, requested, provider, resource_id,
            source_metadata, f"openpyxl unavailable: {exc}",
            ingested_at=ingested_at,
        )

    try:
        workbook = openpyxl.load_workbook(
            io.BytesIO(content), data_only=False, read_only=False,
            keep_links=False,
        )
        values_workbook = openpyxl.load_workbook(
            io.BytesIO(content), data_only=True, read_only=False,
            keep_links=False,
        )
    except Exception as exc:
        return _fallback_artifact(
            content, file_name, requested, provider, resource_id,
            source_metadata, f"workbook parse failed: {exc}",
            ingested_at=ingested_at,
        )

    evidence: Dict[str, List[Dict[str, Any]]] = {
        target: [] for target in requested
    }
    sheets: List[Dict[str, Any]] = []
    formula_states: List[str] = []

    for worksheet in workbook.worksheets:
        value_sheet = values_workbook[worksheet.title]
        rows = list(worksheet.iter_rows())
        header_map, header_rows = _infer_header_map(rows)
        header_columns = sorted(header_map)
        header_descriptors = _column_descriptors(
            [header_map[column] for column in header_columns],
            positions=[column - 1 for column in header_columns],
        )
        field_selection = _select_value_columns(
            header_descriptors,
            attributes or (),
            requested_fields or (),
        )
        selected_columns = field_selection["selected"]
        # STRUCTURED field ambiguity (2026-09-24 review): the gross/net
        # distinction lives in the outcome DATA, not only the render.
        field_ambiguity_map: Dict[str, List[str]] = {}
        for _amb in field_selection.get("ambiguous_fields") or []:
            _cols = [
                str(d.get("label") or "")
                for d in selected_columns
                if _stem(str(_amb)) in _stem(str(d.get("label") or ""))
                or _stem(str(d.get("label") or "")) in _stem(str(_amb))
            ]
            if len(_cols) >= 2:
                field_ambiguity_map[str(_amb)] = _cols
        _ambiguous_labels = {
            label
            for _cols in field_ambiguity_map.values()
            for label in _cols
        }
        for row in rows:
            row_number = row[0].row if row else 0
            row_values = [
                {
                    "cell": cell.coordinate,
                    "value": _cell_text(cell.value),
                    "field": header_map.get(cell.column, ""),
                }
                for cell in row if _cell_text(cell.value)
            ]
            for cell in row:
                value = cell.value
                text = _cell_text(value)
                if not text:
                    continue
                is_formula = isinstance(value, str) and value.startswith("=")
                if is_formula:
                    cached = value_sheet[cell.coordinate].value
                    formula_state = "cached" if cached is not None else "unavailable"
                    formula_states.append(formula_state)
                else:
                    formula_state = "literal"
                for target in requested:
                    if not _matches_target(target, text):
                        continue
                    values: List[Dict[str, Any]] = []
                    for descriptor in selected_columns:
                        column = int(descriptor["position"]) + 1
                        label = str(descriptor.get("label") or "")
                        source_cell = worksheet.cell(row=row_number, column=column)
                        source_value = source_cell.value
                        cached_value = value_sheet.cell(
                            row=row_number, column=column
                        ).value
                        display_value = (
                            cached_value if isinstance(source_value, str)
                            and source_value.startswith("=") else source_value
                        )
                        values.append({
                            "cell": source_cell.coordinate,
                            "value": _cell_text(display_value),
                            "column": label,
                            "field": label,
                            "unit": descriptor.get("unit"),
                            "price_basis": _cell_text(label),
                            **_currency_for(
                                display_value, source_cell.number_format, label
                            ),
                            "formula_state": (
                                "cached" if isinstance(source_value, str)
                                and source_value.startswith("=")
                                and cached_value is not None else "literal"
                            ),
                        })
                    if len(evidence[target]) < _TARGET_EVIDENCE_CAP:
                        for _v in values:
                            _v["field_ambiguous"] = (
                                str(_v.get("column") or "") in _ambiguous_labels
                            )
                        evidence[target].append({
                            "field_ambiguities": dict(field_ambiguity_map),
                            "sheet": worksheet.title,
                            "row": row_number,
                            "cell": cell.coordinate,
                            "value": text,
                            "column": header_map.get(cell.column, ""),
                            "designation": _is_designation_match(
                                text, header_map.get(cell.column, "")),
                            "formula": value if is_formula else None,
                            "formula_state": formula_state,
                            "row_context": row_values[:40],
                            "field_selection": field_selection,
                            "values": values,
                            "prices": values,
                        })
        sheets.append({
            "name": worksheet.title,
            "max_row": int(worksheet.max_row or 0),
            "max_column": int(worksheet.max_column or 0),
            "header_rows": header_rows,
            "headers": {str(column): name for column, name in header_map.items()},
            "field_selection": field_selection,
            "merged_ranges": [str(item) for item in list(worksheet.merged_cells.ranges)[:200]],
            "searched": True,
        })

    outcomes: List[Dict[str, Any]] = []
    for target in requested:
        found = evidence[target]
        designations = [e for e in found if e.get("designation")]
        coincidences = [e for e in found if not e.get("designation")]
        if designations and any(criteria.values()):
            constrained = [
                item for item in designations
                if _matches_disambiguation(item, criteria)
            ]
            if constrained:
                designations = constrained
            else:
                designations = []
        elif designations and attributes:
            # Natural-language attributes ("find Acme's model 381"): the
            # request's distinctive words corroborate via identity-headed
            # fields or sheet names — no special syntax required.
            def _corroboration_count(item: Dict[str, Any]) -> int:
                return sum(
                    1 for a in attributes
                    if _attribute_corroborates(item, a)
                )

            scored = [(_corroboration_count(i), i) for i in designations]
            top = max(score for score, _ in scored)
            if top > 0:
                best = [i for score, i in scored if score == top]
                runner = max(
                    (score for score, _ in scored if score < top),
                    default=0,
                )
                if len(best) == 1 and top > runner:
                    designations = best
            elif any(
                _row_identity_values(item)
                and any(
                    str(attribute or "").strip().lower()
                    in str(item.get("sheet") or "").lower()
                    for attribute in attributes
                    if str(attribute or "").strip()
                )
                for item in designations
            ):
                designations = []
        if len(designations) > 1:
            exact = [
                item for item in designations
                if _canonical(item.get("value")) == _canonical(target)
            ]
            if len(exact) == 1:
                designations = exact
        selection: Dict[str, Any] = {}
        field_ambiguities: Dict[str, Any] = {}
        for candidate in [*designations, *found]:
            candidate_selection = candidate.get("field_selection")
            if isinstance(candidate_selection, dict):
                selection = candidate_selection
            candidate_ambiguities = candidate.get("field_ambiguities")
            if isinstance(candidate_ambiguities, dict):
                field_ambiguities = candidate_ambiguities
            if selection and field_ambiguities:
                break
        if not designations:
            absent_note = (
                f"{len(coincidences)} numeric coincidence(s) in "
                "price/rate columns; no model-designation cell matched "
                "— not treated as product rows"
            )
            if any(criteria.values()):
                absent_note = "no candidate matched the supplied attribute constraints"
            if selection.get("ambiguous"):
                absent_note += "; requested fields are ambiguous"
            outcomes.append({
                "target": target,
                "status": "absent",
                "evidence": [],
                "note": absent_note,
                "disambiguation": criteria,
                "field_selection": selection,
                "field_ambiguities": field_ambiguities,
            })
            continue
        status = "found" if len(designations) == 1 else "ambiguous"
        note: Optional[str] = None
        if selection.get("ambiguous"):
            note = "requested fields map to multiple columns"
        outcomes.append({
            "target": target,
            "status": status,
            "evidence": (
                designations if status == "ambiguous"
                else designations[:1]),
            "disambiguation": criteria,
            "field_selection": selection,
            "field_ambiguities": field_ambiguities,
            **({"note": note} if note else {}),
        })

    return {
        "provider": provider,
        "resource_id": resource_id,
        "file_name": file_name,
        "content_hash": hashlib.sha256(content).hexdigest(),
        "content_hash_algorithm": "sha256",
        "ingested_at": ingested_at,
        "sha256": hashlib.sha256(content).hexdigest(),
        "byte_length": len(content),
        "sheets": sheets,
        "sheet_count": len(sheets),
        "all_sheets_searched": True,
        "truncated": False,
        "formula_status": (
            "cached" if formula_states and all(s == "cached" for s in formula_states)
            else "mixed" if formula_states else "not_present"
        ),
        "coverage": {
            "requested": requested,
            "outcomes": outcomes,
            "complete": all(
                outcome["status"] in ("found", "ambiguous", "absent")
                for outcome in outcomes
            ),
        },
        "source_metadata": dict(source_metadata or {}),
        "coverage_limits": {
            "sheets_expected": len(sheets),
            "sheets_scanned": len(sheets),
            "target_evidence_cap": _TARGET_EVIDENCE_CAP,
        },
    }


def _column_letter(index: int) -> str:
    result = ""
    value = int(index)
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result or "A"


def inspect_dataset_entries(
    entries: Sequence[Dict[str, Any]],
    file_name: str,
    *,
    query: str = "",
    context_texts: Optional[Sequence[str]] = None,
    targets: Optional[Sequence[str]] = None,
    attributes: Optional[Sequence[str]] = None,
    requested_fields: Optional[Sequence[str]] = None,
    provider: Optional[str] = None,
    resource_id: Optional[str] = None,
    source_metadata: Optional[Dict[str, Any]] = None,
    sha256: Optional[str] = None,
    content_hash: Optional[str] = None,
    content_hash_algorithm: str = "sha1",
    ingested_at: Optional[str] = None,
    disambiguation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the same artifact from materialized sheet Parquet entries."""
    requested = extract_targets(query, context_texts, targets)
    criteria = _disambiguation_criteria(query, context_texts, disambiguation)
    evidence: Dict[str, List[Dict[str, Any]]] = {target: [] for target in requested}
    sheets: List[Dict[str, Any]] = []
    complete = bool(entries)
    formula_states: List[str] = []
    sheets_scanned = 0
    unreadable_sheets: List[str] = []
    truncated_sheets: List[str] = []
    coverage_unknown_sheets: List[str] = []
    target_evidence_capped = False
    try:
        import pandas as pd
    except Exception as exc:
        return _fallback_artifact(
            b"", file_name, requested, provider, resource_id,
            source_metadata, f"pandas unavailable: {exc}",
            content_hash=content_hash,
            content_hash_algorithm=content_hash_algorithm,
            ingested_at=ingested_at,
        )

    for entry in entries:
        path = str(entry.get("parquet_path") or "")
        sheet_name = str(entry.get("entity_name") or entry.get("sheet_name") or "")
        if not path or not sheet_name:
            complete = False
            unreadable_sheets.append(sheet_name or path or "<unnamed sheet>")
            continue
        try:
            frame = pd.read_parquet(path)
        except Exception:
            complete = False
            unreadable_sheets.append(sheet_name)
            continue
        sheets_scanned += 1
        expected_rows = entry.get("row_count")
        if expected_rows is not None:
            try:
                if int(expected_rows) > len(frame.index):
                    complete = False
                    truncated_sheets.append(sheet_name)
            except (TypeError, ValueError):
                pass
        entry_coverage = entry.get("coverage") or {}
        if not isinstance(entry_coverage, dict) or not entry_coverage.get("known"):
            complete = False
            coverage_unknown_sheets.append(sheet_name)
        if isinstance(entry_coverage, dict) and entry_coverage.get("truncated"):
            complete = False
            truncated_sheets.append(sheet_name)
        all_columns = [str(column) for column in frame.columns]
        row_column = "__sheet_row" if "__sheet_row" in all_columns else None
        value_positions = [
            index for index, column in enumerate(all_columns)
            if column != row_column
        ]
        value_columns = [all_columns[index] for index in value_positions]
        header_descriptors = _column_descriptors(value_columns)
        field_selection = _select_value_columns(
            header_descriptors,
            attributes or (),
            requested_fields or (),
        )
        selected_columns = field_selection["selected"]
        # STRUCTURED field ambiguity (2026-09-24 review): the gross/net
        # distinction lives in the outcome DATA, not only the render.
        field_ambiguity_map: Dict[str, List[str]] = {}
        for _amb in field_selection.get("ambiguous_fields") or []:
            _cols = [
                str(d.get("label") or "")
                for d in selected_columns
                if _stem(str(_amb)) in _stem(str(d.get("label") or ""))
                or _stem(str(d.get("label") or "")) in _stem(str(_amb))
            ]
            if len(_cols) >= 2:
                field_ambiguity_map[str(_amb)] = _cols
        _ambiguous_labels = {
            label
            for _cols in field_ambiguity_map.values()
            for label in _cols
        }
        formula_map: Dict[str, Any] = {}
        try:
            from core.sheet_dataset_service import load_formulas_for_parquet

            formula_map = load_formulas_for_parquet(path) or {}
        except Exception:
            formula_map = {}

        for row_index, row in frame.iterrows():
            row_number = row.get(row_column) if row_column else row_index + 1
            row_values = row.tolist()
            value_values = [row_values[index] for index in value_positions]
            row_context = [
                {
                    "cell": f"{_column_letter(index + 1)}{row_number}",
                    "value": _cell_text(value),
                    "field": value_columns[index],
                }
                for index, value in enumerate(value_values)
                if _cell_text(value)
            ][:40]
            for column_index, (column, value) in enumerate(
                zip(value_columns, value_values), start=1
            ):
                text = _cell_text(value)
                if not text:
                    continue
                cell_ref = f"{_column_letter(column_index)}{row_number}"
                formula_states.append("cached" if cell_ref in formula_map else "literal")
                for target in requested:
                    if not _matches_target(target, text):
                        continue
                    values: List[Dict[str, Any]] = []
                    for descriptor in selected_columns:
                        value_index = int(descriptor["position"])
                        source_value = value_values[value_index]
                        source_cell = f"{_column_letter(value_index + 1)}{row_number}"
                        label = str(descriptor.get("label") or "")
                        values.append({
                            "cell": source_cell,
                            "value": _cell_text(source_value),
                            "column": label,
                            "field": label,
                            "unit": descriptor.get("unit"),
                            "price_basis": label,
                            **_currency_for(source_value, "", label),
                            "formula_state": (
                                "cached" if source_cell in formula_map else "literal"
                            ),
                        })
                    if len(evidence[target]) >= _TARGET_EVIDENCE_CAP:
                        target_evidence_capped = True
                        continue
                    for _v in values:
                        _v["field_ambiguous"] = (
                            str(_v.get("column") or "") in _ambiguous_labels
                        )
                    evidence[target].append({
                        "field_ambiguities": dict(field_ambiguity_map),
                        "sheet": sheet_name,
                        "row": int(row_number) if str(row_number).isdigit() else row_number,
                        "cell": cell_ref,
                        "value": text,
                        "column": column,
                        "headers": {
                            _column_letter(index + 1): label
                            for index, label in enumerate(value_columns)
                        },
                        "designation": _is_designation_match(text, column),
                        "formula": formula_map.get(cell_ref),
                        "formula_state": (
                            "cached" if cell_ref in formula_map else "literal"
                        ),
                        "row_context": row_context,
                        "field_selection": field_selection,
                        "values": values,
                        "prices": values,
                    })
        sheets.append({
            "name": sheet_name,
            "max_row": int(frame.shape[0]),
            "max_column": int(frame.shape[1]),
            "headers": {
                str(index + 1): label for index, label in enumerate(value_columns)
            },
            "header_rows": [],
            "field_selection": field_selection,
            "merged_ranges": [],
            "searched": True,
        })

    outcomes = []
    for target in requested:
        found = evidence[target]
        designations = [e for e in found if e.get("designation")]
        coincidences = [e for e in found if not e.get("designation")]
        if designations and any(criteria.values()):
            constrained = [
                item for item in designations
                if _matches_disambiguation(item, criteria)
            ]
            if constrained:
                designations = constrained
            else:
                designations = []
        elif designations and attributes:
            def _corroboration_count(item: Dict[str, Any]) -> int:
                return sum(
                    1 for attribute in attributes
                    if _attribute_corroborates(item, attribute)
                )

            scored = [(_corroboration_count(item), item) for item in designations]
            top = max(score for score, _item in scored)
            if top > 0:
                best = [
                    item for score, item in scored if score == top
                ]
                runner = max(
                    (score for score, _item in scored if score < top),
                    default=0,
                )
                if len(best) == 1 and top > runner:
                    designations = best
            elif any(
                _row_identity_values(item)
                and any(
                    str(attribute or "").strip().lower()
                    in str(item.get("sheet") or "").lower()
                    for attribute in attributes
                    if str(attribute or "").strip()
                )
                for item in designations
            ):
                designations = []
        if len(designations) > 1:
            exact = [
                item for item in designations
                if _canonical(item.get("value")) == _canonical(target)
            ]
            if len(exact) == 1:
                designations = exact
        if not complete:
            status = "incomplete"
        elif not designations:
            status = "absent"
        else:
            status = "found" if len(designations) == 1 else "ambiguous"
        selection: Dict[str, Any] = {}
        field_ambiguities: Dict[str, Any] = {}
        for candidate in [*designations, *found]:
            candidate_selection = candidate.get("field_selection")
            if isinstance(candidate_selection, dict):
                selection = candidate_selection
            candidate_ambiguities = candidate.get("field_ambiguities")
            if isinstance(candidate_ambiguities, dict):
                field_ambiguities = candidate_ambiguities
            if selection and field_ambiguities:
                break
        outcome = {
            "target": target,
            "status": status,
            "evidence": (
                designations
                if status in ("ambiguous", "incomplete")
                else designations[:1]),
            "disambiguation": criteria,
            "field_selection": selection,
            "field_ambiguities": field_ambiguities,
        }
        if status == "ambiguous" and len(designations) >= _TARGET_EVIDENCE_CAP:
            outcome["note"] = (
                "multiple plausible product rows remain; candidate evidence "
                "is capped at the scan limit"
            )
        elif status == "absent" and any(criteria.values()):
            outcome["note"] = (
                "no candidate matched the supplied attribute constraints"
            )
        elif status == "absent" and coincidences:
            outcome["note"] = (
                f"{len(coincidences)} numeric coincidence(s) in price/rate "
                "columns; no model-designation cell matched — not treated "
                "as product rows")
        if selection.get("ambiguous"):
            outcome["note"] = "requested fields map to multiple columns"
        outcomes.append(outcome)
    digest = content_hash or sha256
    algorithm = content_hash_algorithm if content_hash else (
        "sha256" if sha256 else None
    )
    return {
        "target_extraction_version": TARGET_EXTRACTION_VERSION,
        "provider": provider,
        "resource_id": resource_id,
        "file_name": file_name,
        "content_hash": digest,
        "content_hash_algorithm": algorithm,
        "ingested_at": ingested_at,
        "sha256": sha256,
        "byte_length": None,
        "sheets": sheets,
        "sheet_count": len(sheets),
        "all_sheets_searched": complete,
        "truncated": not complete or bool(truncated_sheets),
        "formula_status": (
            "cached" if formula_states and all(s == "cached" for s in formula_states)
            else "mixed" if formula_states else "not_present"
        ),
        "coverage": {
            "requested": requested,
            "outcomes": outcomes,
            "complete": (
                complete
                and all(
                    outcome["status"] in ("found", "ambiguous", "absent")
                    for outcome in outcomes
                )
            ),
        },
        "source_metadata": dict(source_metadata or {}),
        "coverage_limits": {
            "sheets_expected": len(entries),
            "sheets_scanned": sheets_scanned,
            "unreadable_sheets": unreadable_sheets,
            "coverage_unknown_sheets": coverage_unknown_sheets,
            "truncated_sheets": truncated_sheets,
            "target_evidence_cap": _TARGET_EVIDENCE_CAP,
            "target_evidence_capped": target_evidence_capped,
        },
    }


_SOURCE_COMPARISON_VERSION = 1
_PRICE_FIELDS = {"price", "cost", "amount", "rate", "value"}
_UNIT_FIELDS = {"quantity", "weight", "lead_time"}


def _comparison_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _explicit_unit(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text or _comparison_text(text) in {"unspecified", "unknown", "n/a", "none"}:
        return None
    return text


def _explicit_currency(value: Any) -> Optional[str]:
    text = str(value or "").strip().upper()
    if not text or text in {"UNSPECIFIED", "UNKNOWN", "N/A", "NONE"}:
        return None
    return text


def _comparison_number(value: Any) -> Optional[Decimal]:
    if isinstance(value, Decimal):
        if not value.is_finite():
            return None
        decimal_tuple = value.as_tuple()
        if (
            len(decimal_tuple.digits) > 256
            or abs(int(decimal_tuple.exponent)) > 1000
        ):
            return None
        number = value
    else:
        text = str(value if value is not None else "").strip()
        if not text or len(text) > 256:
            return None
        negative = text.startswith("(") and text.endswith(")")
        if negative:
            text = text[1:-1].strip()
        leading_minus = bool(
            text.startswith("-")
            or re.match(r"^-\s*[$€£¥₹₩₽₺]", text)
            or re.match(r"^[$€£¥₹₩₽₺]\s*-", text)
        )
        matches = re.findall(
            r"(?<![\w.])[-+]?(?:\d{1,3}(?:[ ,]\d{3})+|\d+)"
            r"(?:\.\d+)?(?:[eE][-+]?\d{1,3})?(?![\w])",
            text,
        )
        normalized = {
            match.replace(" ", "").replace(",", "")
            for match in matches
        }
        if len(normalized) != 1:
            return None
        token = next(iter(normalized))
        try:
            number = Decimal(token)
        except InvalidOperation:
            return None
        if negative or leading_minus:
            number = -abs(number)
    if not number.is_finite():
        return None
    return number


def _comparison_source(observation: Dict[str, Any]) -> Dict[str, Any]:
    source = observation.get("source")
    return dict(source) if isinstance(source, dict) else {}


def _comparison_source_id(observation: Dict[str, Any]) -> str:
    source = _comparison_source(observation)
    return str(
        source.get("source_id")
        or source.get("id")
        or source.get("resource_id")
        or observation.get("source_id")
        or observation.get("resource_id")
        or "unknown"
    )


def _comparison_verified(observation: Dict[str, Any]) -> bool:
    return str(observation.get("verification") or "").lower() in {
        "verified",
        "stored",
        "calculated",
    }


def _text_target_match(text: str, target: str) -> Optional[re.Match[str]]:
    value = str(target or "").strip()
    if not value:
        return None
    return re.search(
        rf"(?<![A-Za-z0-9_-]){re.escape(value)}(?![A-Za-z0-9_-])",
        text,
        re.IGNORECASE,
    )


def _text_source_currency(text: str) -> Optional[str]:
    codes = {
        match.upper()
        for match in re.findall(
            r"\b(?:CAD|USD|EUR|GBP|AUD|NZD|JPY|CHF|INR|MXN|BRL|ZAR)\b",
            text or "",
            re.IGNORECASE,
        )
    }
    return next(iter(codes)) if len(codes) == 1 else None


def _text_source_basis(text: str) -> Optional[str]:
    parts: List[str] = []
    fob = re.search(
        r"\bFOB\s+([^.;\n]+)", text or "", re.IGNORECASE
    )
    if fob:
        parts.append("FOB " + fob.group(1).strip())
    if re.search(r"\b(?:excluding|ex\.?)\s+tax(?:es)?\b", text or "", re.IGNORECASE):
        parts.append("excluding taxes")
    return "; ".join(parts) or None


def _text_field_value(
    text: str, field: str, source_currency: Optional[str]
) -> Optional[str]:
    if field in {"date", "certification_date", "expiration_date"}:
        match = re.search(
            r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
            text,
        )
        return match.group(0) if match else None
    if field in {"version", "required_version"}:
        match = re.search(r"\b\d+(?:\.\d+){1,3}\b", text)
        return match.group(0) if match else None
    if field in _PRICE_FIELDS:
        patterns = (
            r"[$€£¥₹₩₽₺-]\s*-?\d[\d,]*(?:\.\d+)?",
            r"\b(?:CAD|USD|EUR|GBP|AUD|NZD|JPY|CHF|INR|MXN|BRL|ZAR)\s*"
            r"-?\d[\d,]*(?:\.\d+)?",
            r"-?\d[\d,]*\.\d{2}\b",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        if source_currency:
            match = re.search(r"-?\d[\d,]*(?:\.\d+)?", text)
            if match:
                return f"{source_currency} {match.group(0)}"
        return None
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", text)
    return match.group(0).strip() if match else None


def _text_unit(text: str, field: str) -> Optional[str]:
    if field not in _UNIT_FIELDS and field not in _PRICE_FIELDS:
        return None
    source = str(text or "")
    per_unit = re.search(r"\bper\s+([A-Za-z%]+)\b", source, re.IGNORECASE)
    if per_unit:
        return per_unit.group(1)
    number = re.search(r"-?\d[\d,]*(?:\.\d+)?", source)
    if number is None:
        return None
    suffix = re.match(
        r"\s*([A-Za-z%]+)\b", source[number.end():]
    )
    if suffix and suffix.group(1).casefold() in _UNIT_TOKENS:
        return suffix.group(1)
    return None


def _text_organization(prefix: str) -> Optional[str]:
    text = re.sub(r"\b(?:no\.?|model|item|product|part)\b", " ", prefix or "")
    text = re.sub(r"[^A-Za-z0-9& -]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -:")
    if not text or len(text.split()) > 6:
        return None
    if _comparison_text(text) in {
        "requested",
        "requested machines",
        "requested items",
        "quote",
        "machine",
        "item",
        "product",
    }:
        return None
    return text


def observations_from_text(
    text: str,
    *,
    requested_entities: Sequence[str],
    requested_fields: Sequence[str],
    source: Dict[str, Any],
    verification: str = "verified",
) -> List[Dict[str, Any]]:
    source_data = dict(source or {})
    source_id = str(
        source_data.get("source_id")
        or source_data.get("id")
        or source_data.get("resource_id")
        or "text-source"
    )
    source_currency = _explicit_currency(
        source_data.get("currency") or _text_source_currency(text)
    )
    source_basis = str(
        source_data.get("basis") or _text_source_basis(text) or ""
    ).strip() or None
    received = str(
        source_data.get("effective_date")
        or source_data.get("received_date_time")
        or source_data.get("sent_date_time")
        or ""
    )
    effective_date = received[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", received) else None
    lines = str(text or "").splitlines()
    observations: List[Dict[str, Any]] = []
    for entity in requested_entities or []:
        entity_text = str(entity or "").strip()
        if not entity_text:
            continue
        for requested_field in requested_fields or []:
            field = _canonical_field_name(requested_field)
            for line_number, line in enumerate(lines, start=1):
                match = _text_target_match(line, entity_text)
                if match is None:
                    continue
                value_text = line[match.end():]
                raw_value = _text_field_value(
                    value_text, field, source_currency
                )
                if not raw_value:
                    continue
                organization = _text_organization(line[:match.start()])
                currency_match = re.search(
                    r"\b(CAD|USD|EUR|GBP|AUD|NZD|JPY|CHF|INR|MXN|BRL|ZAR)\b",
                    raw_value,
                    re.IGNORECASE,
                )
                line_currency = _text_source_currency(line)
                currency_symbols = set(
                    re.findall(r"[$€£¥₹₩₽₺]", raw_value)
                )
                if currency_match:
                    value_currency = currency_match.group(1).upper()
                elif line_currency:
                    value_currency = line_currency
                elif currency_symbols and currency_symbols != {"$"}:
                    value_currency = None
                else:
                    value_currency = source_currency
                line_basis = _text_source_basis(line) or source_basis
                observations.append(_normalise_comparison_observation({
                    "observation_id": f"{source_id}:{line_number}:{entity_text}:{field}",
                    "entity_id": entity_text,
                    "entity_attributes": (
                        {"organization": organization} if organization else {}
                    ),
                    "field": field,
                    "raw_value": raw_value,
                    "currency": value_currency,
                    "unit": _text_unit(value_text, field),
                    "basis": line_basis,
                    "field_meaning": field,
                    "effective_date": effective_date,
                    "observed_at": received or None,
                    "source": {
                        **source_data,
                        "source_id": source_id,
                        "source_type": source_data.get("source_type") or "text_source",
                        "version": source_data.get("version") or source_id,
                    },
                    "locator": {
                        "line": line_number,
                        "source_id": source_id,
                    },
                    "verification": verification,
                }))
    return observations


def _normalise_comparison_observation(observation: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(observation or {})
    source = _comparison_source(item)
    field = _canonical_field_name(
        item.get("field") or item.get("column") or "value"
    )
    currency = _explicit_currency(item.get("currency"))
    unit = _explicit_unit(item.get("unit"))
    basis = str(
        item.get("basis")
        or item.get("price_basis")
        or ""
    ).strip() or None
    raw_value = str(
        item.get("raw_value")
        if item.get("raw_value") is not None
        else item.get("value") or ""
    )
    numeric = None if field in {
        "date", "certification_date", "expiration_date", "version",
        "required_version",
    } else _comparison_number(
        item.get("numeric_value")
        if item.get("numeric_value") is not None
        else raw_value
    )
    verification = str(item.get("verification") or "").strip().lower()
    if not verification:
        verification = "unverified" if raw_value else "field_missing"
    return {
        "observation_id": str(
            item.get("observation_id")
            or f"{_comparison_source_id(item)}:{item.get('entity_id')}:{field}"
        ),
        "entity_id": str(item.get("entity_id") or item.get("target") or ""),
        "entity_attributes": {
            str(key): str(value)
            for key, value in (item.get("entity_attributes") or {}).items()
            if value not in (None, "")
        },
        "field": field,
        "raw_value": raw_value,
        "numeric_value": str(numeric) if numeric is not None else None,
        "currency": currency,
        "unit": unit,
        "basis": basis,
        "effective_date": str(item.get("effective_date") or "").strip() or None,
        "observed_at": str(item.get("observed_at") or "").strip() or None,
        "field_meaning": str(
            item.get("field_meaning") or item.get("column") or ""
        ).strip() or None,
        "derivation": dict(item.get("derivation") or {}),
        "source": {
            **source,
            "source_id": _comparison_source_id(item),
            "source_type": source.get("source_type") or item.get("source_type"),
            "version": source.get("version") or item.get("version"),
            "temporal_role": source.get("temporal_role")
            or item.get("temporal_role"),
        },
        "locator": dict(item.get("locator") or {}),
        "verification": verification,
    }


def _entity_key(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _entity_identity_reasons(
    left: Dict[str, Any], right: Dict[str, Any]
) -> List[str]:
    left_values = {
        _comparison_text(key): _comparison_text(value)
        for key, value in (left.get("entity_attributes") or {}).items()
    }
    right_values = {
        _comparison_text(key): _comparison_text(value)
        for key, value in (right.get("entity_attributes") or {}).items()
    }
    if not left_values and not right_values:
        return []
    if not left_values or not right_values:
        return ["identity_unresolved"]
    shared = set(left_values).intersection(right_values)
    if not shared:
        return ["identity_unresolved"]
    if any(left_values[key] != right_values[key] for key in shared):
        return ["identity_conflict"]
    return []


def _price_field_meaning(observation: Dict[str, Any]) -> str:
    text = _comparison_text(
        observation.get("field_meaning")
        or observation.get("column")
        or observation.get("field")
    ).replace("_", " ")
    if "wholesale" in text:
        return "wholesale"
    if "retail" in text:
        return "retail"
    if "msrp" in text or "list price" in text:
        return "list"
    if any(term in text for term in ("quote", "quoted", "supplier")):
        return "quoted"
    if text not in {"", "price", "cost", "amount", "value", "rate"}:
        return text
    source = observation.get("source") or {}
    if (
        str(source.get("source_type") or "") == "supplier_quote"
        or "quote" in _comparison_text(source.get("subject"))
    ):
        return "quoted"
    return "unspecified"


def _semantic_comparison_reasons(
    left: Dict[str, Any], right: Dict[str, Any]
) -> List[str]:
    reasons = list(_entity_identity_reasons(left, right))
    field = left.get("field")
    if field in _PRICE_FIELDS:
        left_meaning = _price_field_meaning(left)
        right_meaning = _price_field_meaning(right)
        if (
            left_meaning != right_meaning
            and "unspecified" not in {left_meaning, right_meaning}
        ):
            reasons.append("field_meaning_mismatch")
        left_currency = left.get("currency")
        right_currency = right.get("currency")
        if not left_currency or not right_currency:
            reasons.append("currency_unresolved")
        elif left_currency != right_currency:
            reasons.append("currency_mismatch")
        left_basis = _comparison_text(left.get("basis"))
        right_basis = _comparison_text(right.get("basis"))
        if not left_basis or not right_basis:
            reasons.append("basis_unresolved")
        elif left_basis != right_basis:
            reasons.append("basis_mismatch")
        left_unit = _comparison_text(left.get("unit"))
        right_unit = _comparison_text(right.get("unit"))
        if left_unit or right_unit:
            if not left_unit or not right_unit:
                reasons.append("unit_unresolved")
            elif left_unit != right_unit:
                reasons.append("unit_mismatch")
        source_types = {
            str(left.get("source", {}).get("source_type") or ""),
            str(right.get("source", {}).get("source_type") or ""),
        }
        if "artifact" not in source_types:
            if not left.get("effective_date") or not right.get("effective_date"):
                reasons.append("effective_date_unresolved")
            elif left.get("effective_date") != right.get("effective_date"):
                reasons.append("effective_date_differs")
    else:
        left_unit = _comparison_text(left.get("unit"))
        right_unit = _comparison_text(right.get("unit"))
        if left_unit or right_unit:
            if not left_unit or not right_unit:
                reasons.append("unit_unresolved")
            elif left_unit != right_unit:
                reasons.append("unit_mismatch")
    return list(dict.fromkeys(reasons))


def _numeric_relation(left: Dict[str, Any], right: Dict[str, Any]) -> str:
    left_number = left.get("numeric_value")
    right_number = right.get("numeric_value")
    if left_number is not None and right_number is not None:
        try:
            return "equal" if Decimal(str(left_number)) == Decimal(str(right_number)) else "different"
        except InvalidOperation:
            pass
    left_value = _comparison_text(left.get("raw_value"))
    right_value = _comparison_text(right.get("raw_value"))
    if not left_value or not right_value:
        return "unknown"
    return "equal" if left_value == right_value else "different"


def _compare_observation_pair(
    left: Dict[str, Any], right: Dict[str, Any]
) -> Dict[str, Any]:
    if (
        left.get("verification") == "field_missing"
        or right.get("verification") == "field_missing"
        or not left.get("raw_value")
        or not right.get("raw_value")
    ):
        status = "field_missing"
        reasons = ["field_missing"]
        comparable = False
        relation = "unknown"
    elif not _comparison_verified(left) or not _comparison_verified(right):
        status = "unverified"
        reasons = ["evidence_unverified"]
        comparable = False
        relation = _numeric_relation(left, right)
    else:
        reasons = _semantic_comparison_reasons(left, right)
        comparable = not reasons
        relation = _numeric_relation(left, right)
        if comparable and relation == "equal":
            status = "comparable_match"
        elif comparable and relation == "different":
            status = "comparable_changed"
        elif relation == "equal":
            status = "numeric_match_incomparable"
        elif relation == "different":
            status = "numeric_changed_incomparable"
        else:
            status = "unresolved"
            reasons.append("value_unresolved")
    return {
        "status": status,
        "comparable": comparable,
        "numeric_relation": relation,
        "reasons": list(dict.fromkeys(reasons)),
        "left_observation_id": left.get("observation_id"),
        "right_observation_id": right.get("observation_id"),
        "left_source_id": left.get("source", {}).get("source_id"),
        "right_source_id": right.get("source", {}).get("source_id"),
    }


def workbook_artifact_observations(
    artifact: Dict[str, Any]
) -> List[Dict[str, Any]]:
    source_metadata = dict((artifact or {}).get("source_metadata") or {})
    source = {
        "source_id": str(
            (artifact or {}).get("resource_id")
            or (artifact or {}).get("file_name")
            or "workbook"
        ),
        "source_type": "workbook",
        "version": (artifact or {}).get("content_hash"),
        "file_name": (artifact or {}).get("file_name"),
        "resource_id": (artifact or {}).get("resource_id"),
        "content_hash": (artifact or {}).get("content_hash"),
        "temporal_role": source_metadata.get("temporal_role"),
    }
    effective_date = (
        source_metadata.get("effective_date")
        or source_metadata.get("source_modified_at")
        or (artifact or {}).get("source_modified_at")
    )
    observations: List[Dict[str, Any]] = []
    coverage = (artifact or {}).get("coverage") or {}
    for outcome in coverage.get("outcomes") or []:
        if not isinstance(outcome, dict):
            continue
        target = str(outcome.get("target") or "")
        evidence_items = [
            item for item in outcome.get("evidence") or [] if isinstance(item, dict)
        ]
        selection = outcome.get("field_selection")
        if not isinstance(selection, dict):
            selection = (
                evidence_items[0].get("field_selection")
                if evidence_items else {}
            ) or {}
        requested_fields = [
            _canonical_field_name(field)
            for field in selection.get("requested_fields") or []
        ]
        value_records: List[Dict[str, Any]] = []
        for evidence in evidence_items:
            attributes: Dict[str, str] = {}
            for context in evidence.get("row_context") or []:
                if not isinstance(context, dict):
                    continue
                field_name = _canonical_field_name(context.get("field") or "")
                if field_name in {"organization", "category", "location"}:
                    attributes[field_name] = str(context.get("value") or "")
            for value in evidence.get("values") or evidence.get("prices") or []:
                if isinstance(value, dict):
                    value_records.append({
                        "value": value,
                        "evidence": evidence,
                        "attributes": attributes,
                    })
        if not value_records and requested_fields:
            for field in requested_fields:
                value_records.append({
                    "value": {"field": field, "value": ""},
                    "evidence": evidence_items[0] if evidence_items else {},
                    "attributes": {},
                })
        if not value_records:
            value_records.append({
                "value": {"field": "value", "value": ""},
                "evidence": evidence_items[0] if evidence_items else {},
                "attributes": {},
            })
        for record in value_records:
            value = record["value"]
            raw_value = str(
                value.get("value")
                if value.get("value") is not None
                else ""
            ).strip()
            field = _canonical_field_name(
                value.get("field") or value.get("column") or "value"
            )
            verification = "verified"
            if not raw_value or outcome.get("status") == "absent":
                verification = "field_missing"
            elif outcome.get("status") in {"ambiguous", "incomplete"}:
                verification = str(outcome.get("status"))
            evidence = record["evidence"]
            cell = str(value.get("cell") or evidence.get("cell") or "")
            sheet = str(evidence.get("sheet") or "")
            locator = {
                key: item
                for key, item in {
                    "sheet": sheet,
                    "cell": cell,
                    "row": evidence.get("row"),
                }.items()
                if item not in (None, "")
            }
            observations.append(_normalise_comparison_observation({
                "observation_id": (
                    f"workbook:{source['source_id']}:{target}:{field}:{cell or 'missing'}"
                ),
                "entity_id": target,
                "entity_attributes": record["attributes"],
                "field": field,
                "raw_value": raw_value,
                "currency": value.get("currency"),
                "unit": value.get("unit"),
                "basis": value.get("price_basis") or value.get("column"),
                "field_meaning": value.get("column"),
                "effective_date": effective_date,
                "observed_at": (artifact or {}).get("ingested_at"),
                "derivation": {
                    "formula": evidence.get("formula"),
                    "formula_state": value.get("formula_state")
                    or evidence.get("formula_state"),
                },
                "source": source,
                "locator": locator,
                "verification": verification,
            }))
    return observations


def designated_source_ids(
    text: str,
    observations: Sequence[Dict[str, Any]],
) -> List[str]:
    objective = _comparison_text(text)
    if not objective or re.search(
        r"\b(?:historical|archive|archived|old|prior|previous)\b|"
        r"\b(?:not|rather than|instead of|ignore|exclude|excluding|skip|"
        r"do not use|don't use|never use)\b",
        objective,
    ):
        return []
    designated: List[str] = []
    for observation in observations or []:
        if not isinstance(observation, dict):
            continue
        source = observation.get("source") or {}
        if (
            str(source.get("source_type") or "")
            not in {"message", "supplier_quote"}
            or not _comparison_verified(observation)
            or _comparison_text(source.get("temporal_role")) == "historical"
            or not source.get("source_id")
        ):
            continue
        descriptors = [
            source.get("source_id"),
            source.get("subject"),
            source.get("sender"),
            source.get("sender_name"),
            source.get("display_name"),
            *(
                (observation.get("entity_attributes") or {}).values()
                if isinstance(observation.get("entity_attributes"), dict)
                else ()
            ),
        ]
        normalized_descriptors = {
            _comparison_text(item)
            for item in descriptors
            if len(_comparison_text(item)) >= 3
        }
        if any(item in objective for item in normalized_descriptors):
            source_id = str(source.get("source_id"))
            if source_id not in designated:
                designated.append(source_id)
    return designated if len(designated) == 1 else []


def build_source_comparison(
    observations: Sequence[Dict[str, Any]],
    *,
    requested_entities: Sequence[str],
    requested_fields: Sequence[str],
    artifact_source_ids: Optional[Sequence[str]] = None,
    decision_source_ids: Optional[Sequence[str]] = None,
    authorized_actions: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    normalized = [
        _normalise_comparison_observation(item)
        for item in observations or []
        if isinstance(item, dict)
    ]
    artifact_ids = {str(item) for item in artifact_source_ids or [] if item}
    decision_ids = {str(item) for item in decision_source_ids or [] if item}
    actions_authorized = {
        str(item).strip().lower()
        for item in authorized_actions or []
        if str(item).strip()
    }
    edit_authorized = bool(
        actions_authorized.intersection({"edit_artifact", "update_artifact"})
    )
    outcomes: List[Dict[str, Any]] = []
    gaps: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    blocked_actions: List[Dict[str, Any]] = []
    for entity in requested_entities or []:
        entity_key = _entity_key(entity)
        for requested_field in requested_fields or []:
            field = _canonical_field_name(requested_field)
            matching = [
                item
                for item in normalized
                if _entity_key(item.get("entity_id")) == entity_key
                and item.get("field") == field
            ]
            outcome: Dict[str, Any]
            if not matching:
                outcome = {
                    "entity_id": str(entity),
                    "field": field,
                    "status": "evidence_missing",
                    "comparisons": [],
                    "evidence": [],
                    "reasons": ["evidence_missing"],
                }
                outcomes.append(outcome)
                gaps.append({
                    "entity_id": str(entity),
                    "field": field,
                    "status": "evidence_missing",
                    "next_evidence_needed": f"verified {field} evidence for {entity}",
                })
                continue
            pairs: List[Dict[str, Any]] = []
            for index, left in enumerate(matching):
                for right in matching[index + 1:]:
                    pairs.append(_compare_observation_pair(left, right))
            statuses = [pair["status"] for pair in pairs]
            if not statuses and matching and all(
                item.get("verification") == "field_missing"
                for item in matching
            ):
                statuses = ["field_missing"]
            elif not statuses:
                statuses = ["evidence_missing"]
            has_comparable = any(
                status.startswith("comparable_") for status in statuses
            )
            has_incomparable = any(
                "incomparable" in status for status in statuses
            )
            if any(
                status in {"field_missing", "evidence_missing"}
                for status in statuses
            ):
                status = "partially_comparable" if has_comparable else (
                    "field_missing"
                    if "field_missing" in statuses
                    else "evidence_missing"
                )
            elif has_comparable and has_incomparable:
                status = "partially_comparable"
            elif any(status == "unverified" for status in statuses):
                status = (
                    "partially_comparable"
                    if has_comparable or has_incomparable
                    else "unverified"
                )
            elif "comparable_changed" in statuses:
                status = "comparable_changed"
            elif "comparable_match" in statuses:
                status = "comparable_match"
            elif "numeric_match_incomparable" in statuses:
                status = "numeric_match_incomparable"
            elif "numeric_changed_incomparable" in statuses:
                status = "numeric_changed_incomparable"
            elif any(status == "unverified" for status in statuses):
                status = "unverified"
            else:
                status = "unresolved"
            reasons = list(dict.fromkeys(
                reason for pair in pairs for reason in pair.get("reasons") or []
            ))
            if not reasons:
                reasons = (
                    ["field_missing"]
                    if status == "field_missing"
                    else ["evidence_missing"]
                    if status == "evidence_missing"
                    else ["value_unresolved"]
                    if status == "unresolved"
                    else []
                )
            outcome = {
                "entity_id": str(entity),
                "field": field,
                "status": status,
                "comparisons": pairs,
                "evidence": matching,
                "reasons": reasons,
            }
            outcomes.append(outcome)
            if status not in {"comparable_match", "comparable_changed"}:
                gaps.append({
                    "entity_id": str(entity),
                    "field": field,
                    "status": status,
                    "reasons": reasons,
                    "next_evidence_needed": (
                        f"matching currency, unit, basis, and effective date for {entity} {field}"
                    ),
                })
            artifact_obs = [
                item for item in matching
                if item.get("source", {}).get("source_id") in artifact_ids
            ]
            decision_obs = [
                item for item in matching
                if item.get("source", {}).get("source_id") in decision_ids
            ]
            if len(artifact_obs) == 1 and len(decision_obs) == 1:
                artifact_item = artifact_obs[0]
                decision_item = decision_obs[0]
                pair = _compare_observation_pair(artifact_item, decision_item)
                historical_pair = any(
                    _comparison_text(
                        item.get("source", {}).get("temporal_role")
                    ) == "historical"
                    for item in (artifact_item, decision_item)
                )
                if (
                    pair["status"] == "comparable_changed"
                    and not historical_pair
                    and _comparison_verified(artifact_item)
                    and _comparison_verified(decision_item)
                ):
                    action = {
                        "action_type": "edit_artifact",
                        "entity_id": str(entity),
                        "field": field,
                        "current_value": artifact_item.get("raw_value"),
                        "proposed_value": decision_item.get("raw_value"),
                        "expected": {
                            "raw_value": decision_item.get("raw_value"),
                            "currency": decision_item.get("currency"),
                            "unit": decision_item.get("unit"),
                            "basis": decision_item.get("basis"),
                            "field_meaning": _price_field_meaning(
                                decision_item
                            ),
                            "destination_field_meaning": (
                                _price_field_meaning(artifact_item)
                            ),
                            "entity_attributes": dict(
                                decision_item.get("entity_attributes") or {}
                            ),
                        },
                        "status": "ready" if edit_authorized else "not_authorized",
                        "authorized": edit_authorized,
                        "applied": False,
                        "evidence_ids": [
                            artifact_item.get("observation_id"),
                            decision_item.get("observation_id"),
                        ],
                    }
                    if edit_authorized:
                        actions.append(action)
                    else:
                        blocked_actions.append(action)
    historical = any(
        _comparison_text(item.get("source", {}).get("temporal_role")) == "historical"
        for item in normalized
    )
    implications: List[Dict[str, Any]] = []
    if not actions and not blocked_actions:
        historical_ids = [
            item.get("observation_id")
            for item in normalized
            if _comparison_text(
                item.get("source", {}).get("temporal_role")
            ) == "historical"
        ]
        implications.append({
            "statement": (
                "No draft value should change from the workbook evidence "
                "alone; the workbook is historical."
                if historical else (
                    "No draft value should change because the designated "
                    "source does not support a comparable change."
                    if decision_ids else
                    "No draft value should change because no source was "
                    "explicitly designated for the decision."
                )
            ),
            "verification": "derived",
            "evidence_ids": (
                historical_ids
                or [
                    item.get("observation_id")
                    for item in normalized
                ]
            )[:8],
        })
    if actions:
        implications.append({
            "statement": (
                f"{len(actions)} source-backed artifact change(s) are ready; "
                "none has been applied."
            ),
            "verification": "derived",
            "evidence_ids": list(dict.fromkeys(
                evidence_id
                for action in actions
                for evidence_id in action.get("evidence_ids") or []
            ))[:8],
        })
    if blocked_actions:
        implications.append({
            "statement": (
                f"{len(blocked_actions)} evidence-supported difference(s) were "
                "not converted into changes because no edit was authorized."
            ),
            "verification": "derived",
            "evidence_ids": list(dict.fromkeys(
                evidence_id
                for action in blocked_actions
                for evidence_id in action.get("evidence_ids") or []
            ))[:8],
        })
    outcome_count = len(outcomes)
    verified_numeric_matches = sum(
        outcome.get("status") == "numeric_match_incomparable"
        for outcome in outcomes
    )
    field_missing = sum(
        outcome.get("status") == "field_missing" for outcome in outcomes
    )
    return {
        "contract_version": _SOURCE_COMPARISON_VERSION,
        "coverage": {
            "requested_entities": [str(item) for item in requested_entities or []],
            "requested_fields": [
                _canonical_field_name(item) for item in requested_fields or []
            ],
            "outcome_count": outcome_count,
            "complete": bool(
                outcome_count
                and all(
                    outcome.get("status") in {"comparable_match", "comparable_changed"}
                    for outcome in outcomes
                )
            ),
            "verified_numeric_matches": verified_numeric_matches,
            "field_missing": field_missing,
            "outcomes": outcomes,
        },
        "evidence": normalized,
        "gaps": gaps,
        "implications": implications,
        "actions": actions,
        "blocked_actions": blocked_actions,
    }


def render_source_comparison(comparison: Dict[str, Any]) -> str:
    if not comparison:
        return ""
    coverage = comparison.get("coverage") or {}
    lines = [
        "SOURCE COMPARISON (structured evidence; no source is preferred "
        "unless the user explicitly designated it):",
        (
            f"coverage={coverage.get('outcome_count', 0)} requested outcome(s); "
            f"numeric matches with unresolved semantics="
            f"{coverage.get('verified_numeric_matches', 0)}; "
            f"field missing={coverage.get('field_missing', 0)}"
        ),
    ]
    for outcome in coverage.get("outcomes") or []:
        reasons = ", ".join(outcome.get("reasons") or []) or "none"
        lines.append(
            f"TARGET {outcome.get('entity_id')} / {outcome.get('field')}: "
            f"{str(outcome.get('status') or 'unresolved').upper()} "
            f"(reasons: {reasons})"
        )
        for pair in outcome.get("comparisons") or []:
            lines.append(
                "  "
                f"{pair.get('left_source_id')} vs {pair.get('right_source_id')}: "
                f"numeric={pair.get('numeric_relation')}; "
                f"comparable={pair.get('comparable')}"
            )
    for implication in comparison.get("implications") or []:
        lines.append(f"IMPLICATION: {implication.get('statement')}")
    for action in comparison.get("actions") or []:
        lines.append(
            "READY CHANGE (not applied): "
            f"{action.get('entity_id')} {action.get('field')} "
            f"{action.get('current_value')} -> {action.get('proposed_value')}"
        )
    for action in comparison.get("blocked_actions") or []:
        lines.append(
            "BLOCKED CHANGE (not authorized): "
            f"{action.get('entity_id')} {action.get('field')} "
            f"{action.get('current_value')} -> {action.get('proposed_value')}"
        )
    lines.append(
        "Use these comparisons to explain the decision. Do not silently convert "
        "currency or units, select a preferred source, treat recency as "
        "authority, or mutate an artifact without authorization."
    )
    return "\n".join(lines)


def render_workbook_artifact(artifact: Dict[str, Any]) -> str:
    """Render compact, citable coverage for the model evidence block."""
    if not artifact:
        return ""
    digest = artifact.get("content_hash") or artifact.get("sha256")
    algorithm = artifact.get("content_hash_algorithm")
    lines = [
        "WORKBOOK READ ARTIFACT: "
        f"{artifact.get('file_name') or 'unnamed file'} "
        f"(resource_id={artifact.get('resource_id')}, "
        f"content_hash={digest or 'unavailable'}"
        + (f" ({algorithm})" if algorithm else "")
        + f", ingested_at={artifact.get('ingested_at') or 'unavailable'}, "
        f"sheets={artifact.get('sheet_count')}, "
        f"all_sheets_searched={artifact.get('all_sheets_searched')}, "
        f"truncated={artifact.get('truncated')}, "
        f"formula_status={artifact.get('formula_status')})"
    ]
    coverage = artifact.get("coverage") or {}
    for outcome in coverage.get("outcomes") or []:
        target = outcome.get("target")
        status = outcome.get("status")
        refs = []
        for item in outcome.get("evidence") or []:
            ref = f"{item.get('sheet')}!{item.get('cell')}"
            value = item.get("value")
            if value:
                ref += f"={value}"
            refs.append(ref)
        lines.append(
            f"TARGET {target}: {status.upper()}"
            + (f" | {'; '.join(refs[:8])}" if refs else "")
        )
        for item in (outcome.get("evidence") or [])[:2]:
            selection = item.get("field_selection") or {}
            values = item.get("values") or item.get("prices") or []
            if selection.get("ambiguous"):
                _selection_labels = (
                    selection.get("duplicate_labels")
                    or selection.get("ambiguous_fields")
                    or []
                )
                lines.append(
                    "  FIELD SELECTION: AMBIGUOUS; requested fields map to "
                    f"multiple columns ({', '.join(_selection_labels)})"
                )
            for value in values:
                field = value.get("field") or value.get("column") or "value"
                unit = value.get("unit")
                unit_label = f" | unit={unit}" if unit else ""
                currency = value.get("currency")
                if currency and currency != "unspecified":
                    currency_label = f"currency={currency}"
                elif _VALUE_HEADER_RE.search(str(field)):
                    currency_label = (
                        "currency=UNLABELED (no ISO code or symbol in the "
                        "header/format; basis is the column header VERBATIM "
                        "— no conversion applied, do not infer one)"
                    )
                else:
                    currency_label = "currency=n/a"
                lines.append(
                    f"  VALUE {target} | {value.get('cell')} | "
                    f"{value.get('value')} | field={field} | "
                    f"basis={value.get('price_basis') or field}{unit_label} | "
                    f"{currency_label} | "
                    f"formula_state={value.get('formula_state')}"
                )
    if artifact.get("coverage_limits"):
        lines.append(
            "WORKBOOK COVERAGE LIMITS: "
            + json.dumps(artifact["coverage_limits"], sort_keys=True, default=str)
        )
    if not coverage.get("complete", False):
        lines.append("WORKBOOK COVERAGE: INCOMPLETE")
    return "\n".join(lines)
