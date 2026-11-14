"""Deterministic discount terms read from authorized text evidence.

A governed agreement may state a simple line discount in prose ("category B
lines carry a 5% contract discount").  This module turns only that narrow,
explicit shape into the calculator's ``discount_rules`` contract.  It never
invents a rate or scope: the numeric value comes from the accepted document
text, and a clause whose scope cannot be represented (an exclusion or a
denial) carries only a provisional zero while the scope question is open,
while the document's resource identity, revision/hash and paragraph are
carried onto every rule.

The parser is intentionally conservative:

* only percentage/percent statements near a discount/rebate word are read;
* a recognised category qualifier becomes a ``category`` condition;
* explicit "all lines"/"entire order" language bounds a general rule;
* an exclusion ("all lines except category B") or a denial ("category B
  receives no 5% discount") is the complement of a scope, not a scope value;
  it stays a live ``discount_scope`` condition and carries no provisional
  rate, so the existing ``quote.calculate`` resolver asks a durable
  clarification instead of reading the excluded side as the scope and
  applying the discount to it;
* an unrecognised qualifier becomes a ``discount_scope`` condition, so the
  existing ``quote.calculate`` resolver asks a durable clarification instead of
  silently applying the rate to every line; and
* every distinct affirmative percentage becomes its own rule, so two
  disagreeing statements surface as the existing discount-conflict
  clarification.

No customer, SKU, category, rate or agreement identifier is hardcoded.
"""
from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

_DISCOUNT_KEYWORDS = ("discount", "rebate")
_PERCENT_RE = re.compile(
    r"(?<![\w.])(\d{1,3}(?:\.\d+)?)\s*(?:%|percent\b|per\s+cent\b)",
    re.IGNORECASE,
)
_CATEGORY_RE = re.compile(
    r"\bcategor(?:y|ies)\s+([A-Za-z0-9][A-Za-z0-9&._/-]{0,40}?)"
    r"(?=\s+(?:lines?|items?|products?|skus?|orders?|purchases?)\b"
    r"|[\s,.;:)])",
    re.IGNORECASE,
)
_CATEGORY_IN_RE = re.compile(
    r"\b(?:lines?|items?|products?|skus?)\s+(?:in|from|of)\s+"
    r"categor(?:y|ies)\s+([A-Za-z0-9][A-Za-z0-9&._/-]{0,40})",
    re.IGNORECASE,
)
_UNIVERSAL_RE = re.compile(
    r"\b(?:all|any|every)\s+(?:lines?|items?|products?|orders?|purchases?)\b"
    r"|\bentire\s+(?:order|quote|invoice|purchase)\b",
    re.IGNORECASE,
)
#: Qualifiers this parser cannot evaluate against accepted row columns. They
#: remain explicit conditions, so the calculator asks which scope applies.
_UNSUPPORTED_SCOPE_RE = re.compile(
    r"\b(preferred|tier|segment|region|volume|bulk|minimum|"
    r"over\s+\$?\d|first\s+order|new\s+customer|loyalty|member|"
    r"clearance|promo(?:tion)?)\b",
    re.IGNORECASE,
)
#: Language that excludes lines from a rate or denies the rate outright.
#: The calculator's ``when`` is a conjunction of equality tests, so the
#: complement of a scope ("except category B") cannot be represented there.
#: Such a clause stays a live scope question and must never be read as the
#: positive scope it excludes.
_EXCLUSION_RE = re.compile(
    r"\b(?:except(?:\s+for)?|excluding|exclusive\s+of|other\s+than|"
    r"but\s+not|with\s+the\s+exception\s+of|apart\s+from|save\s+for|"
    r"excluded|exempt\s+from)\b",
    re.IGNORECASE,
)
_NEGATED_DISCOUNT_RE = re.compile(
    r"\b(?:no|not|never|without|zero|ineligible)\b[^.;]{0,40}?"
    r"\b(?:discount|rebate)\b"
    r"|\b(?:discount|rebate)\b[^.;]{0,40}?\b(?:does\s+not|do\s+not|"
    r"is\s+not|are\s+not|will\s+not|shall\s+not)\b",
    re.IGNORECASE,
)
_CLAUSE_SPLIT_RE = re.compile(r"\s*(?:;|\band\b)\s*", re.IGNORECASE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_SPACE_RE = re.compile(r"\s+")

#: The same embedded-instruction markers the quote-evidence oracle treats as
#: evidence text rather than authority. A discount sentence that carries one
#: is not a commercial term.
_UNTRUSTED_MARKERS = (
    "ignore previous", "ignore all", "system prompt",
    "send without approval", "grant permission",
)

#: Bound the number of rules one document may contribute.
MAX_DISCOUNT_RULES = 20

#: Bound the amount of prose a single rule may cite back to the request.
EXCERPT_LIMIT = 500


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _bounded(value: Any, limit: int = EXCERPT_LIMIT) -> str:
    return _SPACE_RE.sub(" ", _text(value))[:limit]


def _rate_text(percent: Decimal) -> str:
    rate = percent / Decimal("100")
    return format(rate.normalize(), "f")


def _rule_id(
    rate: str, when: Mapping[str, Any], source_ref: Mapping[str, Any],
    excerpt: str,
) -> str:
    payload = {
        "rate": rate,
        "when": dict(when),
        "source_ref": dict(source_ref),
        "excerpt": excerpt,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return f"evidence-discount-{digest[:16]}"


def _category_scope(clause: str) -> Optional[str]:
    for pattern in (_CATEGORY_RE, _CATEGORY_IN_RE):
        match = pattern.search(clause)
        if match:
            value = _text(match.group(1)).strip(" .,;:()[]")
            if value:
                return value
    return None


def _excludes_discount(clause: str) -> bool:
    return bool(
        _EXCLUSION_RE.search(clause)
        or _NEGATED_DISCOUNT_RE.search(clause))


def _scope(clause: str) -> Dict[str, Any]:
    # An exclusion or denial describes where the rate does *not* apply. It is
    # not an equality condition, so it remains a live scope question rather
    # than being read as the positive category it excludes.
    if _excludes_discount(clause):
        return {"discount_scope": _bounded(clause, 200)}
    # A qualifier we cannot evaluate must remain a live condition. The
    # existing resolver treats a missing line field as unknown and asks a
    # durable question rather than guessing.
    if _UNSUPPORTED_SCOPE_RE.search(clause):
        return {"discount_scope": _bounded(clause, 200)}
    category = _category_scope(clause)
    if category:
        return {"category": category}
    if _UNIVERSAL_RE.search(clause):
        return {}
    return {}


def _scope_label(when: Mapping[str, Any]) -> str:
    if when.get("category"):
        return f"category {when['category']}"
    if when.get("discount_scope"):
        return "conditional"
    return "all lines"


def _clauses(text: str) -> Iterable[str]:
    """Bounded sentences and conjunctive clauses, preserving order."""
    for line in _text(text).splitlines():
        line = line.strip()
        if not line:
            continue
        for sentence in _SENTENCE_SPLIT_RE.split(line):
            sentence = sentence.strip()
            if not sentence:
                continue
            if any(
                    marker in sentence.casefold()
                    for marker in _UNTRUSTED_MARKERS):
                # Embedded instructions stay evidence text; they never become
                # a commercial term.
                continue
            for clause in _CLAUSE_SPLIT_RE.split(sentence):
                clause = _bounded(clause)
                if clause:
                    yield clause


def discount_rules_from_text(
    text: str,
    *,
    source: Optional[Mapping[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Extract simple rate discounts stated by one authorized text source.

    ``source`` carries the accepted read receipt identity: ``resource_id``,
    ``version``/``source_version``, ``sha256``, ``step_id`` and ``path``.  The
    returned rules are calculator-ready (fractional ``rate``) and bound to
    that exact identity.  A source with no explicit rate yields no rules.
    """
    source = dict(source or {})
    resource_id = _text(source.get("resource_id"))
    version = _text(
        source.get("version") or source.get("source_version"))
    sha256 = _text(source.get("sha256") or source.get("content_hash"))
    source_ref = {
        "resource_id": resource_id,
        "version": version,
        "source_version": version,
        "sha256": sha256,
        "step_id": _text(source.get("step_id")),
        "path": _text(source.get("path")),
    }
    source_ref = {key: value for key, value in source_ref.items() if value}
    authority = (
        f"{resource_id}@{version}" if resource_id and version
        else resource_id or version or "document-evidence"
    )

    rules: List[Dict[str, Any]] = []
    seen = set()
    paragraph = 0
    for raw_line in _text(text).splitlines():
        if raw_line.strip():
            paragraph += 1
        for clause in _clauses(raw_line):
            lowered = clause.casefold()
            if not any(keyword in lowered for keyword in _DISCOUNT_KEYWORDS):
                continue
            if any(marker in lowered for marker in _UNTRUSTED_MARKERS):
                # Embedded instructions stay evidence text; they never become
                # a commercial term.
                continue
            if len(rules) >= MAX_DISCOUNT_RULES:
                return rules
            percentages = list(_PERCENT_RE.finditer(clause))
            if not percentages:
                continue
            when = _scope(clause)
            excluded = _excludes_discount(clause)
            distinct: List[Decimal] = []
            for match in percentages:
                try:
                    value = Decimal(match.group(1))
                except (InvalidOperation, ValueError):
                    continue
                if not value.is_finite() or value <= 0 or value > 100:
                    continue
                if value not in distinct:
                    distinct.append(value)
            for value in distinct:
                # Exclusion/denial clauses keep a provisional 0 rather than
                # the stated rate. The scope is unresolved, and a
                # same-rate affirmative rule elsewhere must not make the
                # exclusion look price-equivalent and silently win.
                provisional = Decimal("0") if excluded else value
                rate = _rate_text(provisional)
                excerpt = _bounded(clause)
                rule_id = _rule_id(rate, when, source_ref, excerpt)
                rule = {
                    "rule_id": rule_id,
                    "lesson_id": rule_id,
                    "revision": version or sha256 or "unversioned",
                    "name": (
                        "discount scope unresolved" if excluded else (
                            f"{format(provisional.normalize(), 'f')}% "
                            f"{_scope_label(when)} discount")),
                    "when": dict(when),
                    "rate": rate,
                    "type": "rate",
                    "source": "authorized_document_evidence",
                    "source_version": version,
                    "source_ref": dict(source_ref),
                    "authority": authority,
                    "description": excerpt,
                    "notes": f"paragraph {paragraph}",
                }
                key = (
                    resource_id, version, rate,
                    json.dumps(when, sort_keys=True, default=str),
                )
                if key in seen:
                    continue
                seen.add(key)
                rules.append(rule)
    return rules


def discount_source_ref(
    result: Mapping[str, Any], *, step_id: str = "",
) -> Dict[str, Any]:
    """Accepted document read identity used by :func:`discount_rules_from_text`."""
    result = dict(result or {})
    verification = (
        result.get("verification")
        if isinstance(result.get("verification"), Mapping) else {})
    evidence = result.get("evidence")
    entries: List[Mapping[str, Any]] = []
    if isinstance(evidence, Sequence) and not isinstance(evidence, (str, bytes)):
        entries = [item for item in evidence if isinstance(item, Mapping)]
    # A durable document read records its content digest on the evidence
    # entry. The top-level source_version may be an opaque provider revision,
    # so it is never treated as a SHA-256 fallback.
    document_entries = [
        item for item in entries
        if str(item.get("kind") or "").lower() in (
            "document", "document_extraction")
    ]
    evidence_entry = next(iter(document_entries or entries), None)
    path = _text(evidence_entry.get("path")) if evidence_entry else ""
    evidence_sha256 = _text(
        evidence_entry.get("content_hash")
        or evidence_entry.get("content_sha256")
        or evidence_entry.get("sha256")) if evidence_entry else ""
    source = result.get("source") if isinstance(
        result.get("source"), Mapping) else {}
    version = _text(
        result.get("source_version") or result.get("version")
        or verification.get("version"))
    sha256 = _text(
        result.get("sha256") or result.get("content_sha256")
        or source.get("sha256") or source.get("content_sha256")
        or result.get("content_hash") or evidence_sha256)
    return {
        "resource_id": _text(result.get("resource_id")),
        "version": version,
        "source_version": version,
        "sha256": sha256,
        "step_id": _text(step_id),
        "path": path,
    }
