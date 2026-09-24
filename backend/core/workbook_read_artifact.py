"""Structured workbook read artifacts and target coverage."""
from __future__ import annotations

import hashlib
import io
import json
import re
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
    r"price|cost|amount|rate|value|msrp|list|wholesale|dealer|currency",
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
        "dealer", "retail", "unit cost", "selling price", "quote",
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
    "month", "months", "year", "years", "percent", "pct", "usd", "cad",
    "eur", "gbp", "aud", "nzd", "jpy", "inr", "mxn", "brl", "zar",
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
    if not selected and requested:
        generic = [
            item for item in descriptors
            if _VALUE_HEADER_RE.search(str(item.get("label") or ""))
        ]
        selected = generic
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
        if field in {"price", "quantity", "date", "version"}:
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
_CURRENCY_RE = re.compile(
    r"\b(?:CAD|USD|EUR|GBP|AUD|NZD|JPY|CHF|INR|MXN|BRL|ZAR)\b|"
    r"\[[$€£¥₹₩₽₺-][^\]]*\]",
    re.IGNORECASE,
)


def _canonical(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def _is_year(value: str) -> bool:
    return bool(_YEAR_RE.fullmatch(str(value or "").strip()))


def extract_targets(
    query: str = "", context_texts: Optional[Sequence[str]] = None,
    explicit: Optional[Sequence[str]] = None,
) -> List[str]:
    """Extract likely item/model identifiers without treating years as targets."""
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
        for match in _TARGET_RE.finditer(str(text or "")):
            add(match.group(0))
    if not values:
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
        for text in [query or "", *(context_texts or [])]:
            value_text = str(text or "")
            for match in quoted_target.finditer(value_text):
                add(match.group(1))
            for match in named_target.finditer(value_text):
                words = match.group(1).split()
                while words and words[0].lower() in ignored_words:
                    words.pop(0)
                kept = []
                for word in words:
                    if word.lower() in ignored_words:
                        break
                    if kept and not (word[:1].isupper() or "-" in word):
                        break
                    kept.append(word)
                if kept:
                    add(" ".join(kept))
    return values[:64]


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _matches_target(target: str, value: Any) -> bool:
    text = _cell_text(value)
    if not text:
        return False
    canonical = _canonical(target)
    if not canonical:
        return False
    value_canonical = _canonical(text)
    if canonical in value_canonical:
        if canonical.isdigit():
            return re.search(
                rf"(?<!\d){re.escape(canonical)}(?!\d)", str(text)
            ) is not None
        return True
    return False



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
    if any(ch.isalpha() for ch in text):
        return True
    if re.fullmatch(r"(?:c\d+|#ref!|\d+)", header, re.IGNORECASE):
        return False
    if re.search(
        r"model|part|item|sku|product|description|name|catalog|cat\.?\s*no|code",
        header,
        re.IGNORECASE,
    ):
        return True
    return not _PRICE_HEADER_RE.search(header)

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
            while parts and parts[0].lower() in _ATTRIBUTE_STOPWORDS:
                parts.pop(0)
            if parts:
                _add_criteria_value(criteria, "organization", " ".join(parts))
        for match in labelled.finditer(value_text):
            _add_criteria_value(criteria, match.group(1), match.group(2).strip())
    return criteria


_INTERROGATIVE_GUARD = {
    "what", "which", "who", "whom", "whose", "when", "where", "why",
    "how", "the", "this", "that", "these", "those", "it", "there",
    "here", "name", "please", "kind", "sort", "type", "one", "find",
    "search", "check", "tell", "show", "give",
}


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
    if attr in str(evidence.get("sheet") or "").lower():
        return True
    headers = evidence.get("headers") or {}
    for item in evidence.get("row_context") or []:
        if not isinstance(item, dict):
            continue
        cell_ref = str(item.get("cell") or "")
        column_letter = re.match(r"([A-Z]+)", cell_ref)
        header = (
            headers.get(column_letter.group(1))
            if column_letter else None
        ) or str(evidence.get("column") or "")
        if header and _IDENTITY_HEADER_RE.search(str(header)):
            if attr in str(item.get("value") or "").lower():
                return True
    return False


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
                        evidence[target].append({
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
        if len(designations) > 1:
            exact = [
                item for item in designations
                if _canonical(item.get("value")) == _canonical(target)
            ]
            if len(exact) == 1:
                designations = exact
        selection = next(
            (item.get("field_selection") for item in designations
             if item.get("field_selection")),
            next(
                (item.get("field_selection") for item in found
                 if item.get("field_selection")),
                {},
            ),
        )
        if not designations:
            note = (
                f"{len(coincidences)} numeric coincidence(s) in "
                "price/rate columns; no model-designation cell matched "
                "— not treated as product rows"
            )
            if any(criteria.values()):
                note = "no candidate matched the supplied attribute constraints"
            if selection.get("ambiguous"):
                note += "; requested fields are ambiguous"
            outcomes.append({
                "target": target,
                "status": "absent",
                "evidence": [],
                "note": note,
                "disambiguation": criteria,
                "field_selection": selection,
            })
            continue
        status = "found" if len(designations) == 1 else "ambiguous"
        note = None
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
                    evidence[target].append({
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
        selection = next(
            (item.get("field_selection") for item in designations
             if item.get("field_selection")),
            next(
                (item.get("field_selection") for item in found
                 if item.get("field_selection")),
                {},
            ),
        )
        outcome = {
            "target": target,
            "status": status,
            "evidence": (
                designations
                if status in ("ambiguous", "incomplete")
                else designations[:1]),
            "disambiguation": criteria,
            "field_selection": selection,
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
