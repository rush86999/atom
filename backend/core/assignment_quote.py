"""Deterministic line-item (quote) calculation over evidence-backed inputs.

Business meaning (customer, SKU, price basis, discount policy) stays in the
caller's descriptors and teaching. This module only:

* validates typed money/quantity/unit/currency inputs with Decimal;
* resolves scoped discount rules without guessing applicability;
* computes each line and the document total with an explicit rounding
  authority; and
* returns a replayable receipt naming every input, rule and evidence source.

It is registered as the ``quote.calculate`` assignment adapter. No provider
call happens here, and no missing currency/unit/tax/rounding is defaulted.
"""
from __future__ import annotations

import copy
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.assignment_executor import (
    NeedsContext,
    register_assignment_adapter,
)

#: Currencies are data. They are validated for structural identity, never
#: converted implicitly.
_KNOWN_CURRENCIES = {"CAD", "USD", "EUR", "GBP", "AUD", "INR", "NZD", "JPY"}

_ROUNDING_MODES = {"half_up": ROUND_HALF_UP}


class QuoteInputError(ValueError):
    """A typed input failed validation; arithmetic must not proceed."""


def _decimal(raw: Any, field: str) -> Decimal:
    if raw is None or str(raw).strip() == "":
        raise QuoteInputError(f"{field} is required")
    if isinstance(raw, float) and raw != raw:  # NaN without importing math
        raise QuoteInputError(f"{field} must be a finite decimal")
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError) as exc:
        raise QuoteInputError(f"{field} is not numeric: {raw!r}") from exc
    if not value.is_finite():
        raise QuoteInputError(f"{field} must be a finite decimal")
    return value


def _money_text(value: Decimal, scale: int) -> str:
    quant = Decimal(1).scaleb(-scale)
    return str(value.quantize(quant, rounding=ROUND_HALF_UP))


#: Rule keys that describe identity, provenance or applicability rather than
#: the commercial result. Everything else participates in the material
#: pricing signature, so an unrecognised cap/basis field cannot make two
#: genuinely different rules look equivalent.
_RULE_METADATA_KEYS = frozenset({
    "lesson_id", "revision", "name", "id", "rule_id", "description",
    "when", "effective_from", "effective_to", "source", "source_version",
    "source_ref", "taught_at", "created_at", "updated_at", "authority",
    "label", "notes", "priority",
})

_LINE_CONTEXT_KEYS = (
    "customer", "customer_id", "category", "currency", "price_basis",
    "region", "segment", "tier",
)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _is_missing(value: Any) -> bool:
    return value is None or _text(value) == ""


def _normalize_material(value: Any) -> Any:
    """Canonical, JSON-safe-ish form for comparing pricing behaviour.

    Decimal-equivalent numeric spellings compare equal (``5`` == ``5.00``).
    Unrecognised rule fields are retained: assuming an unknown field has no
    commercial meaning is exactly how a differing cap or basis gets silently
    applied.
    """
    if isinstance(value, dict):
        return tuple(sorted(
            (str(key), _normalize_material(item))
            for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_normalize_material(item) for item in value)
    if isinstance(value, bool):
        return ("bool", "true" if value else "false")
    text = _text(value)
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        return ("text", text.casefold())
    if not number.is_finite():
        return ("text", text.casefold())
    if number == 0:
        number = Decimal("0")
    return ("number", format(number.normalize(), "f"))


_SUPPORTED_RULE_KEYS = frozenset(_RULE_METADATA_KEYS) | frozenset({
    "rate", "type", "basis", "discount_type",
})
_SUPPORTED_RATE_TYPES = frozenset({"rate", "percent", "percentage"})


def validate_discount_rules(rules: Sequence[Dict[str, Any]]) -> None:
    """Reject pricing semantics this calculator does not implement.

    The arithmetic applies a simple fractional rate.  Caps, fixed amounts,
    tiers, formulas and unknown material fields are refused explicitly before
    any selection or calculation; applying only the rate would misprice the
    line.  This is the explicit safe boundary, not a silent fallback.
    """
    for index, raw in enumerate(rules or []):
        if not isinstance(raw, dict):
            raise QuoteInputError(
                f"discount rule {index + 1} must be an object")
        rule_name = str(raw.get("name") or raw.get("lesson_id")
                        or f"rule {index + 1}")
        unknown = sorted(set(raw) - _SUPPORTED_RULE_KEYS)
        if unknown:
            raise QuoteInputError(
                f"discount rule {rule_name!r} uses unsupported material "
                f"field(s): {', '.join(unknown)}. Only a simple rate is "
                "implemented.")
        for field in ("type", "basis", "discount_type"):
            value = _text(raw.get(field)).lower()
            if value and value not in _SUPPORTED_RATE_TYPES:
                raise QuoteInputError(
                    f"discount rule {rule_name!r} uses unsupported {field} "
                    f"{value!r}; only a rate discount is implemented.")
        rate_text = _text(raw.get("rate"))
        if not rate_text:
            raise QuoteInputError(
                f"discount rule {rule_name!r} has no rate")
        try:
            rate = Decimal(rate_text)
        except (InvalidOperation, ValueError) as exc:
            raise QuoteInputError(
                f"discount rule {rule_name!r} rate is not numeric") from exc
        if not rate.is_finite() or rate < 0 or rate > 1:
            raise QuoteInputError(
                f"discount rule {rule_name!r} rate must be a fraction "
                "between 0 and 1")


def _pricing_signature(rule: Dict[str, Any]) -> Tuple[Any, ...]:
    """The material commercial result of one rule.

    Rate is compared numerically; every other non-metadata field is included
    verbatim (normalised), so caps, basis or future pricing fields cannot be
    ignored by the equivalence check.
    """
    payload = rule if isinstance(rule, dict) else {}
    signature: Dict[str, Any] = {}
    for key, value in payload.items():
        key_text = str(key)
        if key_text.startswith("_") or key_text in _RULE_METADATA_KEYS:
            continue
        signature[key_text] = _normalize_material(value)
    rate = payload.get("rate")
    signature["rate"] = _normalize_material(
        "0" if _is_missing(rate) else rate)
    return tuple(sorted(signature.items()))


_NO_RULE_SIGNATURE = _pricing_signature({})


def _rule_specificity(rule: Dict[str, Any]) -> int:
    when = rule.get("when") if isinstance(rule.get("when"), dict) else {}
    return len([key for key, value in when.items()
                if str(key).strip() and not _is_missing(value)])


def _effective_state(rule: Dict[str, Any], as_of: str) -> str:
    """Applicability of a dated rule: true, false or unknown.

    A missing date is unknown when the rule is dated -- it is never treated
    as "not effective" or "effective", because either assumption could pick
    the wrong governing discount.
    """
    effective_from = _text(rule.get("effective_from"))
    effective_to = _text(rule.get("effective_to"))
    if not effective_from and not effective_to:
        return "true"
    as_of_text = _text(as_of)
    if not as_of_text:
        return "unknown"
    if effective_from and as_of_text < effective_from:
        return "false"
    if effective_to and as_of_text > effective_to:
        return "false"
    return "true"


def _rule_state(
    rule: Dict[str, Any], line: Dict[str, Any], as_of: str,
) -> Tuple[str, List[str]]:
    """Classify one rule as true, false or unknown.

    A definitively false condition makes the whole conjunction false even
    when another condition is missing. Missing conditions are retained as
    unknown; they are never collapsed into false.
    """
    when = rule.get("when") if isinstance(rule.get("when"), dict) else {}
    missing: List[str] = []
    for raw_key, expected in when.items():
        key = str(raw_key)
        if not key.strip() or _is_missing(expected):
            continue
        actual = line.get(key)
        if _is_missing(actual):
            if key not in missing:
                missing.append(key)
            continue
        if _text(actual).casefold() != _text(expected).casefold():
            return "false", []
    effective = _effective_state(rule, as_of)
    if effective == "false":
        return "false", []
    if missing:
        return "unknown", missing
    if effective == "unknown":
        return "unknown", ["effective_date"]
    return "true", []


def _line_identity(line: Dict[str, Any]) -> Dict[str, str]:
    return {
        "item_id": _text(line.get("item_id") or line.get("sku")),
        "sku": _text(line.get("sku")),
        "unit": _text(line.get("unit")),
        "pack_size": _text(line.get("pack_size")),
    }


def _line_accepted_context(line: Dict[str, Any]) -> Dict[str, str]:
    return {
        key: _text(line.get(key))
        for key in _LINE_CONTEXT_KEYS
        if not _is_missing(line.get(key))
    }


def _source_version_entry(
    scope: str, raw: Dict[str, Any],
) -> Optional[Dict[str, str]]:
    if not isinstance(raw, dict):
        return None
    resource_id = _text(
        raw.get("resource_id") or raw.get("dataset_name")
        or raw.get("external_id") or raw.get("path"))
    source_version = _text(
        raw.get("source_version") or raw.get("version")
        or raw.get("content_hash") or raw.get("sha256"))
    if not resource_id and not source_version:
        return None
    return {
        "scope": scope,
        "resource_id": resource_id,
        "source_version": source_version,
    }


def _line_source_versions(line: Dict[str, Any]) -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    source_ref = _source_version_entry("line", line.get("source_ref") or {})
    if source_ref:
        entries.append(source_ref)
    for raw in line.get("evidence") or []:
        entry = _source_version_entry("line_evidence", raw)
        if entry:
            entries.append(entry)
    return sorted(entries, key=lambda item: (
        item.get("scope", ""), item.get("resource_id", ""),
        item.get("source_version", "")))


def _candidate_summary(rule: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "lesson_id": rule.get("lesson_id"),
        "revision": rule.get("revision"),
        "name": rule.get("name"),
        "when": dict(rule.get("when") or {}),
        "rate": str(rule.get("rate")),
        "effective_from": rule.get("effective_from"),
        "effective_to": rule.get("effective_to"),
        "specificity": _rule_specificity(rule),
    }


def _collect_missing_fields(
    entries: Sequence[Dict[str, Any]],
) -> List[str]:
    fields: List[str] = []
    for entry in entries:
        for key in entry.get("missing") or []:
            if key not in fields:
                fields.append(key)
    return fields


def _display_field(key: str) -> str:
    return "effective date" if key == "effective_date" else key.replace("_", " ")


def _discount_gap(
    line: Dict[str, Any],
    *,
    concept: str,
    mode: str,
    reason: str,
    question: str,
    missing_fields: Sequence[str],
    candidates: Sequence[Dict[str, Any]],
    kind: str = "business_decision",
) -> Dict[str, Any]:
    identity = _line_identity(line)
    item = identity["item_id"] or "line"
    fields = [str(field) for field in missing_fields if str(field).strip()]
    binding_key = (
        f"discount:{mode}:{item.casefold()}:{','.join(sorted(fields)) or '-'}")
    binding = {
        "binding_key": binding_key,
        "mode": mode,
        "line_item_id": item,
        "line_identity": identity,
        "missing_fields": fields,
        "candidate_rules": [_candidate_summary(rule) for rule in candidates],
        "accepted_context": _line_accepted_context(line),
        "source_versions": _line_source_versions(line),
    }
    gap = {
        "concept": concept,
        "reason": reason,
        "question": question,
        "item": item,
        "affected_subjects": [item],
        "checked_evidence": [
            str(rule.get("lesson_id") or rule.get("name") or "")
            for rule in candidates
        ],
        "missing_fields": fields,
        "candidate_rules": binding["candidate_rules"],
        "binding_key": binding_key,
        "inputs": {
            "binding_key": binding_key,
            "quote_discount": binding,
        },
        "kind": kind,
        "waiting": {
            "state": "waiting_for_person",
            "party": "pricing owner",
            "resume_on": "answer",
            "detail": reason,
        },
    }
    if kind == "missing_evidence":
        gap.update({
            "next_retrieval": (
                "confirm the line qualifier through the authorized source"),
            "next_action": (
                "read the authorized customer/product evidence and retry"),
        })
    return gap


def resolve_discount_rule(
    line: Dict[str, Any],
    rules: Sequence[Dict[str, Any]],
    *,
    as_of: str = "",
) -> Optional[Dict[str, Any]]:
    """Resolve the one governing discount rule for a line.

    Every rule is classified true, false or unknown. More specific
    established rules override broader ones, equal-specificity established
    rules must agree on material pricing, and any unknown rule that could
    supersede or conflict with the winner is retained as a live possibility.
    A decision is returned only when every remaining possibility prices the
    line identically; otherwise the caller receives a durable clarification.
    """
    validate_discount_rules(rules)
    evaluated: List[Dict[str, Any]] = []
    for raw in rules or []:
        if not isinstance(raw, dict):
            continue
        state, missing = _rule_state(raw, line, as_of)
        evaluated.append({
            "rule": raw,
            "specificity": _rule_specificity(raw),
            "state": state,
            "missing": missing,
            "pricing": _pricing_signature(raw),
        })
    established = [
        item for item in evaluated if item["state"] == "true"]
    unknown = [
        item for item in evaluated if item["state"] == "unknown"]

    if established:
        top = max(item["specificity"] for item in established)
        winners = [
            item for item in established if item["specificity"] == top]
        signatures = {item["pricing"] for item in winners}
        if len(signatures) > 1:
            winner_rules = [item["rule"] for item in winners]
            raise NeedsContext(_discount_gap(
                line,
                concept="discount_rule_conflict",
                mode="conflict",
                reason="equally specific discounts conflict",
                question=(
                    "Which discount governs this line? The applicable "
                    "instructions disagree."),
                missing_fields=[],
                candidates=winner_rules,
            ))
        winner = winners[0]
        # A lower-specificity unknown rule can never beat this winner. Only
        # rules at least as specific, with a different commercial result,
        # remain live possibilities.
        relevant = [
            item for item in unknown
            if item["specificity"] >= top
            and item["pricing"] != winner["pricing"]
        ]
        if not relevant:
            return dict(winner["rule"])
        fields = _collect_missing_fields(relevant)
        candidates = [winner["rule"]] + [item["rule"] for item in relevant]
        display = ", ".join(_display_field(field) for field in fields)
        raise NeedsContext(_discount_gap(
            line,
            concept="discount_scope",
            mode="scope",
            reason=(
                "a scoped discount rule could change the governing price "
                "and its qualifier is not established"),
            question=(
                f"Which {display} applies to this line? A taught discount "
                "could change the governing price depending on it."),
            missing_fields=fields,
            candidates=candidates,
            kind="missing_evidence",
        ))

    if unknown:
        signatures = {item["pricing"] for item in unknown}
        if signatures <= {_NO_RULE_SIGNATURE}:
            # Every live rule prices the line at no discount, so no question
            # can change the commercial result.
            return None
        fields = _collect_missing_fields(unknown)
        display = ", ".join(_display_field(field) for field in fields)
        candidates = [item["rule"] for item in unknown]
        raise NeedsContext(_discount_gap(
            line,
            concept="discount_scope",
            mode="scope",
            reason=(
                "no discount rule is established yet; a scoped rule could "
                "change the governing price"),
            question=(
                f"Which {display} applies to this line? A taught discount "
                "could change the governing price depending on it."),
            missing_fields=fields,
            candidates=candidates,
            kind="missing_evidence",
        ))
    return None


def calculate_line_items(
    *,
    line_items: Sequence[Dict[str, Any]],
    currency: str,
    freight: Any,
    tax: Any,
    discount_rules: Optional[Sequence[Dict[str, Any]]] = None,
    as_of: str = "",
    rounding: str = "half_up",
    scale: int = 2,
    rounding_authority: str = "currency_minor_unit",
    source_evidence: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Compute a line-item document total with an exact receipt."""
    if not isinstance(line_items, (list, tuple)) or not line_items:
        raise QuoteInputError("at least one line item is required")
    validate_discount_rules(discount_rules or [])
    currency = str(currency or "").strip().upper()
    if not currency:
        raise QuoteInputError(
            "currency is required; it is never inferred from country or source")
    mode = str(rounding or "").strip().lower()
    if mode not in _ROUNDING_MODES:
        raise QuoteInputError(f"unsupported rounding authority '{rounding}'")
    try:
        scale = int(scale)
    except (TypeError, ValueError) as exc:
        raise QuoteInputError("rounding scale must be an integer") from exc
    if scale < 0 or scale > 6:
        raise QuoteInputError("rounding scale must be between 0 and 6")

    seen_identity: Dict[str, Dict[str, Any]] = {}
    computed: List[Dict[str, Any]] = []
    with localcontext() as ctx:
        ctx.prec = 28
        for index, raw in enumerate(line_items):
            line = dict(raw or {})
            item_id = str(
                line.get("item_id") or line.get("sku") or "").strip()
            if not item_id:
                raise QuoteInputError(
                    f"line {index + 1} requires an item_id/sku")
            identity_key = item_id.lower()
            identity = {
                "unit": str(line.get("unit") or "").strip().lower(),
                "pack_size": str(line.get("pack_size") or "").strip(),
            }
            previous = seen_identity.get(identity_key)
            if previous is not None and previous != identity:
                raise NeedsContext({
                    "concept": "packaging_identity",
                    "reason": (
                        "the same item id appears with different packaging "
                        "or units"),
                    "question": (
                        f"Which packaging/unit applies to {item_id}?"),
                    "affected_subjects": [item_id],
                    "checked_evidence": [
                        f"unit={previous['unit'] or 'unstated'}",
                        f"pack_size={previous['pack_size'] or 'unstated'}",
                        f"unit={identity['unit'] or 'unstated'}",
                        f"pack_size={identity['pack_size'] or 'unstated'}",
                    ],
                    "kind": "business_decision",
                })
            seen_identity[identity_key] = identity

            unit = str(line.get("unit") or "").strip()
            if not unit:
                raise NeedsContext({
                    "concept": "unit_of_measure",
                    "reason": "the line has no selling unit",
                    "question": f"Which unit applies to {item_id}?",
                    "affected_subjects": [item_id],
                    "next_retrieval": "read the authorized product record",
                    "kind": "missing_evidence",
                })
            pack_size = line.get("pack_size")
            if pack_size in (None, ""):
                raise NeedsContext({
                    "concept": "pack_size",
                    "reason": "the line has no pack size",
                    "question": f"Which pack size applies to {item_id}?",
                    "affected_subjects": [item_id],
                    "next_retrieval": "read the authorized product record",
                    "kind": "missing_evidence",
                })
            price_basis = str(line.get("price_basis") or "").strip().lower()
            if price_basis not in (
                    "list", "contract", "selling", "quoted", "rate"):
                raise NeedsContext({
                    "concept": "price_basis",
                    "reason": "the line does not name a selling price basis",
                    "question": (
                        f"Is the price for {item_id} a list, contract or "
                        "selling price?"),
                    "affected_subjects": [item_id],
                    "next_retrieval": "read the authorized price agreement",
                    "kind": "missing_evidence",
                })
            line_currency = str(
                line.get("currency") or currency).strip().upper()
            if line_currency != currency:
                raise QuoteInputError(
                    f"line {item_id} currency {line_currency} does not match "
                    f"document currency {currency}")

            quantity = _decimal(line.get("quantity"), f"{item_id}.quantity")
            unit_price = _decimal(
                line.get("unit_price"), f"{item_id}.unit_price")
            if quantity <= 0:
                raise QuoteInputError(
                    f"{item_id}.quantity must be greater than zero")
            if unit_price < 0:
                raise QuoteInputError(
                    f"{item_id}.unit_price must not be negative")

            explicit_rate: Optional[Decimal] = None
            if line.get("discount_rate") not in (None, ""):
                authority = str(line.get("discount_authority") or "").strip()
                if not authority:
                    raise NeedsContext({
                        "concept": "discount_authority",
                        "reason": (
                            "an explicit discount was supplied without naming "
                            "its authority"),
                        "question": (
                            f"What authorizes the discount on {item_id}?"),
                        "affected_subjects": [item_id],
                        "kind": "business_decision",
                    })
                explicit_rate = _decimal(
                    line.get("discount_rate"), f"{item_id}.discount_rate")

            rule = None
            if explicit_rate is None and discount_rules:
                rule = resolve_discount_rule(
                    line, discount_rules, as_of=as_of)
            if explicit_rate is not None:
                rate = explicit_rate
                rule_ref = {
                    "authority": str(line.get("discount_authority") or ""),
                    "source": "line",
                }
            elif rule is not None:
                rate = _decimal(
                    rule.get("rate"), f"{item_id}.discount_rate")
                rule_ref = {
                    "authority": "taught",
                    "lesson_id": rule.get("lesson_id"),
                    "name": rule.get("name"),
                    "revision": rule.get("revision"),
                    "when": dict(rule.get("when") or {}),
                }
            else:
                rate = Decimal("0")
                rule_ref = {"authority": "none"}

            if rate < 0 or rate > 1:
                raise QuoteInputError(
                    f"{item_id}.discount_rate must be a fraction between 0 and 1")
            gross = quantity * unit_price
            discount = gross * rate
            net = gross - discount
            computed.append({
                "item_id": item_id,
                "description": str(line.get("description") or ""),
                "quantity": str(quantity),
                "unit": unit,
                "pack_size": str(pack_size),
                "unit_price": _money_text(unit_price, scale),
                "price_basis": price_basis,
                "currency": currency,
                "gross": _money_text(gross, scale),
                "discount_rate": str(rate),
                "discount_amount": _money_text(discount, scale),
                "net": _money_text(net, scale),
                "discount_rule": rule_ref,
                "source_ref": dict(line.get("source_ref") or {}),
                "evidence": list(line.get("evidence") or []),
            })
        freight_value = _decimal(freight, "freight")
        if freight_value < 0:
            raise QuoteInputError("freight must not be negative")
        if not isinstance(tax, dict):
            raise QuoteInputError(
                "tax must be an explicit descriptor, e.g. {'basis':'none'}")
        tax_basis = str(tax.get("basis") or "").strip().lower()
        if tax_basis in ("none", "zero", "exempt"):
            tax_amount = Decimal("0")
            tax_ref = {"basis": tax_basis, "amount": "0"}
        elif tax_basis == "amount":
            tax_amount = _decimal(tax.get("amount"), "tax.amount")
            tax_ref = {"basis": "amount", "amount": _money_text(
                tax_amount, scale)}
        elif tax_basis == "rate":
            rate = _decimal(tax.get("rate"), "tax.rate")
            if rate < 0 or rate > 1:
                raise QuoteInputError(
                    "tax.rate must be a fraction between 0 and 1")
            tax_amount = sum(
                (Decimal(row["net"]) for row in computed), Decimal("0")) * rate
            tax_ref = {
                "basis": "rate",
                "rate": str(rate),
                "amount": _money_text(tax_amount, scale),
            }
        else:
            raise QuoteInputError(
                "tax must name its basis: none, amount or rate")
        if tax_amount < 0:
            raise QuoteInputError("tax must not be negative")

        subtotal = sum((Decimal(row["net"]) for row in computed), Decimal("0"))
        total = subtotal + freight_value + tax_amount
        receipt = {
            "currency": currency,
            "rounding": mode,
            "rounding_authority": rounding_authority,
            "scale": scale,
            "subtotal": _money_text(subtotal, scale),
            "freight": _money_text(freight_value, scale),
            "tax": tax_ref,
            "total": _money_text(total, scale),
            "line_evidence": [
                {
                    "item_id": row["item_id"],
                    "source_ref": row["source_ref"],
                    "evidence": row["evidence"],
                }
                for row in computed
            ],
            "source_evidence": list(source_evidence or []),
            "discount_rules": [
                {
                    "lesson_id": rule.get("lesson_id"),
                    "revision": rule.get("revision"),
                    "when": dict(rule.get("when") or {}),
                    "rate": str(rule.get("rate")),
                }
                for rule in (discount_rules or [])
                if isinstance(rule, dict)
            ],
        }
        return {
            "status": "applied",
            "summary": (
                f"quote total {receipt['total']} {currency} "
                f"({len(computed)} lines)"),
            "value": receipt["total"],
            "unit": currency,
            "currency": currency,
            "expression": " + ".join(
                [f"{row['quantity']}*{row['unit_price']}" for row in computed]
                + ["freight"]
            ),
            "rows": computed,
            "subtotals": {currency: {
                "value": receipt["subtotal"], "rows": len(computed)}},
            "values": [{"currency": currency, "value": receipt["total"]}],
            "operation": "line_items",
            "measure": "quote_total",
            "group_by": "currency",
            "selected_count": len(computed),
            "matched_count": len(computed),
            "truncated": False,
            "substantive": True,
            "calculation_receipt": receipt,
            "evidence": [{
                "kind": "calculation_receipt",
                "currency": currency,
                "total": receipt["total"],
                "rounding": mode,
                "rounding_authority": rounding_authority,
            }],
            "evidence_refs": [
                {
                    "kind": "source",
                    "resource_id": (ref or {}).get("resource_id"),
                    "source_version": (ref or {}).get("source_version"),
                }
                for ref in (source_evidence or [])
                if isinstance(ref, dict)
            ],
        }


def _current_source_versions(
    inputs: Dict[str, Any],
    context: Dict[str, Any],
    line: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    if isinstance(line, dict):
        entries.extend(_line_source_versions(line))
    for raw in inputs.get("source_evidence") or []:
        entry = _source_version_entry("source_evidence", raw)
        if entry:
            entries.append(entry)
    for raw in context.get("sources") or []:
        if not isinstance(raw, dict):
            continue
        binding = raw.get("binding") if isinstance(
            raw.get("binding"), dict) else {}
        entry = _source_version_entry("assignment_source", binding or raw)
        if entry:
            entries.append(entry)
    deduped = {
        (item.get("scope", ""), item.get("resource_id", ""),
         item.get("source_version", "")): item
        for item in entries
    }
    return [deduped[key] for key in sorted(deduped)]


def _rule_revisions(rules: Sequence[Dict[str, Any]]) -> List[str]:
    """Stable teaching fingerprint carried by every discount obligation."""
    fingerprints: List[str] = []
    for rule in rules or []:
        if not isinstance(rule, dict):
            continue
        fingerprints.append(json.dumps({
            "lesson_id": rule.get("lesson_id"),
            "revision": rule.get("revision"),
            "name": rule.get("name"),
            "when": dict(rule.get("when") or {}),
            "effective_from": rule.get("effective_from"),
            "effective_to": rule.get("effective_to"),
            "pricing": _pricing_signature(rule),
        }, sort_keys=True, default=str))
    return sorted(fingerprints)


def _find_line(
    inputs: Dict[str, Any], line_item_id: str,
) -> Tuple[Optional[Dict[str, Any]], int]:
    wanted = _text(line_item_id).casefold()
    if not wanted:
        return None, -1
    for index, raw in enumerate(inputs.get("line_items") or []):
        if not isinstance(raw, dict):
            continue
        identity = _line_identity(raw)
        candidates = {identity["item_id"].casefold(),
                      identity["sku"].casefold()}
        if wanted in candidates:
            return raw, index
    return None, -1


def _resolved_discount_bindings(
    context: Dict[str, Any],
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """Latest resolved answer per durable binding key.

    A newer answer supersedes an older one for the same assignment/line/
    missing-field binding. Older answers stay in the audit history but never
    silently reapply after reassessment.
    """
    step_gap_ids = set(
        (context.get("step") or {}).get("gap_ids") or [])
    latest: Dict[str, Tuple[str, int, Dict[str, Any], Dict[str, Any]]] = {}
    for index, item in enumerate(context.get("resolved_gaps") or []):
        if not isinstance(item, dict) or item.get("status") != "resolved":
            continue
        if step_gap_ids and item.get("question_id") not in step_gap_ids:
            continue
        if not _text(
                item.get("resolution_value") or item.get("resolution")):
            continue
        raw_inputs = item.get("inputs")
        binding = (
            raw_inputs.get("quote_discount")
            if isinstance(raw_inputs, dict) else None)
        if not isinstance(binding, dict):
            continue
        binding_key = _text(
            binding.get("binding_key")
            or (raw_inputs or {}).get("binding_key"))
        if not binding_key:
            continue
        resolved_at = _text(item.get("resolved_at"))
        previous = latest.get(binding_key)
        if previous is not None and previous[0] > resolved_at:
            continue
        if previous is not None and previous[0] == resolved_at:
            if previous[1] > index:
                continue
        latest[binding_key] = (resolved_at, index, binding, item)
    return [
        (entry[2], entry[3])
        for entry in sorted(
            latest.values(), key=lambda value: (value[0], value[1]))
    ]


def _binding_stale_reason(
    binding: Dict[str, Any],
    inputs: Dict[str, Any],
    context: Dict[str, Any],
    line: Dict[str, Any],
) -> str:
    bound_teaching = _text(binding.get("teaching_revision"))
    current_teaching = _text(
        (context.get("teaching") or {}).get("revision"))
    if bound_teaching and bound_teaching != current_teaching:
        return "the teaching revision changed after the clarification"
    bound_rules = binding.get("rule_revisions")
    if isinstance(bound_rules, list) and bound_rules:
        current_rules = _rule_revisions(inputs.get("discount_rules") or [])
        if current_rules != bound_rules:
            return "the discount teaching changed after the clarification"
    bound_sources = binding.get("source_versions")
    if isinstance(bound_sources, list):
        current_sources = _current_source_versions(inputs, context, line)
        if current_sources != bound_sources:
            return "the authorized source version changed after the clarification"
    return ""


def _answer_values(
    binding: Dict[str, Any], value: str,
) -> Dict[str, Any]:
    text = _text(value)
    if text.startswith("{"):
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError):
            parsed = None
        if isinstance(parsed, dict):
            return {str(key): item for key, item in parsed.items()}
    values: Dict[str, Any] = {}
    for part in text.replace(";", ",").split(","):
        if "=" not in part:
            continue
        key, item = part.split("=", 1)
        if _text(key) and _text(item):
            values[_text(key)] = _text(item)
    if values:
        return values
    fields = [
        str(field) for field in binding.get("missing_fields") or []
        if str(field).strip()
    ]
    if len(fields) == 1:
        return {fields[0]: text}
    return {field: text for field in fields}


def _conflict_rate(
    binding: Dict[str, Any], value: str,
) -> Optional[str]:
    answer = _text(value)
    if not answer:
        return None
    for rule in binding.get("candidate_rules") or []:
        if not isinstance(rule, dict):
            continue
        names = {
            _text(rule.get("lesson_id")).casefold(),
            _text(rule.get("name")).casefold(),
        }
        if answer.casefold() in names and names:
            rate = _text(rule.get("rate"))
            if rate:
                return rate
    candidate = answer.rstrip("%").strip()
    try:
        number = Decimal(candidate)
    except (InvalidOperation, ValueError):
        return None
    if answer.endswith("%"):
        number = number / Decimal("100")
    if number < 0 or number > 1:
        return None
    return str(number.normalize())


def _reassessment_gap(
    line: Dict[str, Any],
    binding: Dict[str, Any],
    reason: str,
    rules: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    fields = [
        str(field) for field in binding.get("missing_fields") or []
        if str(field).strip()
    ]
    display = ", ".join(_display_field(field) for field in fields)
    if not display:
        display = "discount"
    return _discount_gap(
        line,
        concept="discount_reassessment_required",
        mode=_text(binding.get("mode")) or "scope",
        reason=reason,
        question=(
            f"{reason[0].upper() + reason[1:]}. Which {display} applies to "
            "this line now?"),
        missing_fields=fields,
        candidates=rules,
        kind="business_decision",
    )


def _merge_resolved_discount_inputs(
    inputs: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    """Apply durable answers to the exact line they were raised for.

    A wrong-line answer is ignored. A stale answer (teaching revision, rule
    set or source version changed) becomes a fresh reassessment obligation
    instead of silently transferring the old value.
    """
    merged = copy.deepcopy(inputs)
    bindings = _resolved_discount_bindings(context)
    if not bindings:
        return merged
    rules = list(merged.get("discount_rules") or [])
    for binding, resolved in bindings:
        bound_assignment = _text(binding.get("assignment_id"))
        current_assignment = _text(context.get("assignment_id"))
        if bound_assignment and current_assignment and (
                bound_assignment != current_assignment):
            continue
        bound_run = _text(binding.get("run_id"))
        current_run = _text(context.get("run_id"))
        if bound_run and current_run and bound_run != current_run:
            continue
        line, index = _find_line(merged, _text(binding.get("line_item_id")))
        if line is None:
            # The answer names a line that is not in this calculation: never
            # apply it to a different item.
            continue
        if binding.get("line_identity") != _line_identity(line):
            continue
        accepted = binding.get("accepted_context")
        if isinstance(accepted, dict) and accepted != _line_accepted_context(
                line):
            raise NeedsContext(_reassessment_gap(
                line, binding,
                "the accepted customer or line context changed after the "
                "clarification", rules))
        reason = _binding_stale_reason(binding, merged, context, line)
        if reason:
            raise NeedsContext(_reassessment_gap(
                line, binding, reason, rules))
        value = _text(
            resolved.get("resolution_value") or resolved.get("resolution"))
        mode = _text(binding.get("mode")) or "scope"
        if mode == "conflict":
            rate = _conflict_rate(binding, value)
            if rate is None:
                raise NeedsContext(_discount_gap(
                    line,
                    concept="discount_rule_conflict",
                    mode="conflict",
                    reason=(
                        "the clarification did not select one of the "
                        "candidate discounts"),
                    question=(
                        "Which discount governs this line? Name one of the "
                        "taught rules or give the authorized rate."),
                    missing_fields=[],
                    candidates=rules,
                ))
            line["discount_rate"] = rate
            line["discount_authority"] = (
                f"resolved clarification {resolved.get('question_id') or ''}"
            ).strip()
            continue
        values = _answer_values(binding, value)
        for field in binding.get("missing_fields") or []:
            field = str(field)
            if field == "effective_date":
                merged["as_of"] = _text(values.get(field, value))
                continue
            if field in values:
                line[field] = values[field]
    return merged


def _bind_quote_gap(
    gap: Dict[str, Any],
    inputs: Dict[str, Any],
    context: Dict[str, Any],
) -> None:
    """Attach the assignment/line/teaching/source identity to the question."""
    raw_inputs = gap.get("inputs")
    if not isinstance(raw_inputs, dict):
        raw_inputs = {}
        gap["inputs"] = raw_inputs
    binding = raw_inputs.get("quote_discount")
    if not isinstance(binding, dict):
        return
    binding = dict(binding)
    line, _ = _find_line(inputs, _text(binding.get("line_item_id")))
    binding["assignment_id"] = _text(context.get("assignment_id"))
    binding["run_id"] = _text(context.get("run_id"))
    binding["teaching_revision"] = _text(
        (context.get("teaching") or {}).get("revision"))
    binding["rule_revisions"] = _rule_revisions(
        inputs.get("discount_rules") or [])
    binding["source_versions"] = _current_source_versions(
        inputs, context, line)
    if isinstance(line, dict):
        binding["accepted_context"] = _line_accepted_context(line)
        binding["line_identity"] = _line_identity(line)
    raw_inputs["quote_discount"] = binding
    raw_inputs["binding_key"] = binding.get("binding_key") or ""


@register_assignment_adapter(
    "quote.calculate",
    description="Calculate evidence-backed line items with exact decimals",
    metadata={"effect": "local", "required_actions": ["calculate"],
              "required_inputs": ["line_items", "currency", "freight", "tax"],
              "allow_standing_authorization": False},
)
async def _quote_calculate(
    inputs: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        merged_inputs = _merge_resolved_discount_inputs(inputs, context)
        return calculate_line_items(
            line_items=merged_inputs.get("line_items") or [],
            currency=str(merged_inputs.get("currency") or ""),
            freight=merged_inputs.get("freight"),
            tax=merged_inputs.get("tax"),
            discount_rules=merged_inputs.get("discount_rules") or [],
            as_of=str(merged_inputs.get("as_of") or ""),
            rounding=str(merged_inputs.get("rounding") or "half_up"),
            scale=int(merged_inputs.get("scale") or 2),
            rounding_authority=str(
                merged_inputs.get("rounding_authority")
                or "currency_minor_unit"),
            source_evidence=merged_inputs.get("source_evidence") or [],
        )
    except NeedsContext as exc:
        _bind_quote_gap(exc.gap, inputs, context)
        raise
    except QuoteInputError as exc:
        gap = {
            "concept": "quote_input",
            "reason": str(exc),
            "question": str(exc),
            "kind": "missing_evidence",
            "next_retrieval": (
                "confirm the missing or invalid quote field with the "
                "customer or the governing agreement"),
            "next_action": (
                "read the authorized customer/agreement evidence and retry"),
            "resolver": "quote owner",
        }
        _bind_quote_gap(gap, inputs, context)
        raise NeedsContext(gap) from exc
