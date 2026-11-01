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


def _rule_specificity(rule: Dict[str, Any]) -> int:
    when = rule.get("when") if isinstance(rule.get("when"), dict) else {}
    return len([key for key in when if str(when.get(key) or "") != ""])


def _rule_matches(rule: Dict[str, Any], line: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Return (matches, missing qualifiers).

    A scoped rule whose qualifier is absent from the line cannot be silently
    ignored: that would either skip an applicable exception or apply one
    outside its scope. The caller turns the missing list into a typed
    clarification.
    """
    when = rule.get("when") if isinstance(rule.get("when"), dict) else {}
    missing: List[str] = []
    for key, expected in when.items():
        actual = line.get(str(key))
        if actual in (None, ""):
            missing.append(str(key))
            continue
        if str(actual).strip().lower() != str(expected).strip().lower():
            return False, []
    return True, missing


def _active_rule(rule: Dict[str, Any], as_of: str) -> bool:
    effective_from = str(rule.get("effective_from") or "").strip()
    effective_to = str(rule.get("effective_to") or "").strip()
    if effective_from and as_of and as_of < effective_from:
        return False
    if effective_to and as_of and as_of > effective_to:
        return False
    return True


def resolve_discount_rule(
    line: Dict[str, Any],
    rules: Sequence[Dict[str, Any]],
    *,
    as_of: str = "",
) -> Optional[Dict[str, Any]]:
    """Resolve the one governing discount rule for a line.

    More specific rules (more matched ``when`` keys) override broader ones.
    Equal-specificity rules with different rates are a conflict; missing
    qualifiers are a clarification. A line may carry an explicit discount
    that bypasses policy only when the caller marks it ``discount_authority``.
    """
    applicable: List[Tuple[int, Dict[str, Any]]] = []
    missing: List[Dict[str, Any]] = []
    for raw in rules or []:
        if not isinstance(raw, dict):
            continue
        if not _active_rule(raw, as_of):
            continue
        matches, absent = _rule_matches(raw, line)
        if absent:
            missing.append({"rule": raw, "missing": absent})
            continue
        if matches:
            applicable.append((_rule_specificity(raw), raw))
    if applicable:
        top = max(specificity for specificity, _ in applicable)
        winners = [rule for specificity, rule in applicable
                   if specificity == top]
        rates = {str(rule.get("rate")) for rule in winners}
        if len(rates) > 1:
            raise NeedsContext({
                "concept": "discount_rule_conflict",
                "reason": "equally specific discounts conflict",
                "question": (
                    "Which discount governs this line? The applicable "
                    "instructions disagree."),
                "affected_subjects": [line.get("item_id") or line.get("sku")],
                "checked_evidence": [
                    str(rule.get("lesson_id") or rule.get("name") or "")
                    for rule in winners
                ],
                "kind": "business_decision",
                "waiting": {
                    "state": "waiting_for_person",
                    "party": "pricing owner",
                    "resume_on": "answer",
                    "detail": "conflicting discount rules",
                },
            })
        return dict(winners[0])
    if missing:
        keys: List[str] = []
        for item in missing:
            for key in item["missing"]:
                if key not in keys:
                    keys.append(key)
        raise NeedsContext({
            "concept": "discount_scope",
            "reason": "a scoped discount rule cannot be applied without its qualifiers",
            "question": (
                "Which " + ", ".join(keys) + " applies to this line? A taught "
                "exception depends on it."),
            "affected_subjects": [line.get("item_id") or line.get("sku")],
            "checked_evidence": [
                str(rule.get("lesson_id") or rule.get("name") or "")
                for item in missing for rule in [item["rule"]]
            ],
            "next_retrieval": "confirm the line qualifier through the authorized source",
            "next_action": "read the authorized customer/product evidence and retry",
            "kind": "missing_evidence",
        })
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


@register_assignment_adapter(
    "quote.calculate",
    description="Calculate evidence-backed line items with exact decimals",
    metadata={"effect": "local", "required_actions": ["calculate"],
              "allow_standing_authorization": False},
)
async def _quote_calculate(
    inputs: Dict[str, Any], context: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        return calculate_line_items(
            line_items=inputs.get("line_items") or [],
            currency=str(inputs.get("currency") or ""),
            freight=inputs.get("freight"),
            tax=inputs.get("tax"),
            discount_rules=inputs.get("discount_rules") or [],
            as_of=str(inputs.get("as_of") or ""),
            rounding=str(inputs.get("rounding") or "half_up"),
            scale=int(inputs.get("scale") or 2),
            rounding_authority=str(
                inputs.get("rounding_authority")
                or "currency_minor_unit"),
            source_evidence=inputs.get("source_evidence") or [],
        )
    except QuoteInputError as exc:
        raise NeedsContext({
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
        }) from exc
