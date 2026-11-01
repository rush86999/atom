"""Deterministic line-item quote calculation controls.

The expected 362.50 is an independent fixture value, not produced by the
production calculator before the assertion is written:

    A = 2 * 100.00            = 200.00
    B = 3 * 50.00, 5% on B    = 142.50
    freight                   =  20.00
    tax (explicit none)       =   0.00
    total                     = 362.50
"""
from __future__ import annotations

import asyncio

import pytest

from core.assignment_executor import NeedsContext
from core.assignment_quote import (
    QuoteInputError,
    calculate_line_items,
    resolve_discount_rule,
)


def _line(item_id="A", **overrides):
    line = {
        "item_id": item_id,
        "quantity": "2",
        "unit": "each",
        "pack_size": "1",
        "unit_price": "100.00",
        "price_basis": "contract",
        "currency": "USD",
        "category": "A",
    }
    line.update(overrides)
    return line


def _calculate(lines=None, **overrides):
    payload = {
        "line_items": lines or [
            _line("A"),
            _line("B", quantity="3", unit_price="50.00", category="B"),
        ],
        "currency": "USD",
        "freight": "20.00",
        "tax": {"basis": "none"},
        "rounding": "half_up",
        "scale": 2,
        "rounding_authority": "agreement:round-half-up-2dp",
        "discount_rules": [{
            "lesson_id": "lesson-b-discount",
            "revision": 3,
            "when": {"category": "B"},
            "rate": "0.05",
        }],
    }
    payload.update(overrides)
    return calculate_line_items(**payload)


def test_exact_362_50_fixture_with_discount_only_on_b():
    result = _calculate()
    assert result["value"] == "362.50"
    assert result["currency"] == "USD"
    receipt = result["calculation_receipt"]
    assert receipt["subtotal"] == "342.50"
    assert receipt["freight"] == "20.00"
    assert receipt["tax"]["amount"] == "0"
    assert receipt["total"] == "362.50"
    assert [row["net"] for row in result["rows"]] == ["200.00", "142.50"]
    assert [row["discount_amount"] for row in result["rows"]] == [
        "0.00", "7.50"]
    assert receipt["line_evidence"][0]["item_id"] == "A"
    assert receipt["rounding_authority"] == "agreement:round-half-up-2dp"


def test_more_specific_taught_exception_wins_over_broad_rule():
    rules = [
        {"name": "standard", "rate": "0.02"},
        {"name": "category exception", "when": {"category": "B"},
         "rate": "0.10"},
    ]
    line = _line("B", quantity="1", unit_price="100.00", category="B")
    resolved = resolve_discount_rule(line, rules)
    assert resolved["rate"] == "0.10"
    result = _calculate(
        lines=[line], freight="0", tax={"basis": "none"},
        discount_rules=rules)
    assert result["value"] == "90.00"


def test_equally_specific_conflicting_rules_do_not_arbitrarily_win():
    rules = [
        {"name": "A", "when": {"category": "B", "customer": "Acme"},
         "rate": "0.05"},
        {"name": "B", "when": {"category": "B", "customer": "Acme"},
         "rate": "0.10"},
    ]
    with pytest.raises(NeedsContext) as excinfo:
        resolve_discount_rule(
            _line("B", category="B", customer="Acme"), rules)
    assert excinfo.value.gap["concept"] == "discount_rule_conflict"
    assert excinfo.value.gap["kind"] == "business_decision"


def test_scoped_rule_with_missing_qualifier_asks_instead_of_ignoring_it():
    rules = [{"name": "category exception", "when": {"category": "B"},
              "rate": "0.05"}]
    with pytest.raises(NeedsContext) as excinfo:
        resolve_discount_rule(_line("B", category=""), rules)
    assert excinfo.value.gap["concept"] == "discount_scope"
    assert "category" in excinfo.value.gap["question"]


def test_expired_discount_rule_is_not_applied():
    rules = [{"name": "old", "rate": "0.05",
              "effective_to": "2025-12-31"}]
    assert resolve_discount_rule(
        _line("A"), rules, as_of="2026-11-01") is None


def test_same_sku_with_different_packaging_requires_clarification():
    lines = [
        _line("SKU-1", pack_size="10"),
        _line("SKU-1", pack_size="25"),
    ]
    with pytest.raises(NeedsContext) as excinfo:
        _calculate(lines=lines, discount_rules=[])
    assert excinfo.value.gap["concept"] == "packaging_identity"


def test_missing_currency_and_tax_are_never_defaulted():
    with pytest.raises(QuoteInputError):
        _calculate(currency="")
    with pytest.raises(QuoteInputError):
        _calculate(tax=None)
    with pytest.raises(QuoteInputError):
        _calculate(tax={})
    with pytest.raises(QuoteInputError):
        _calculate(freight=None)
    with pytest.raises(NeedsContext):
        _calculate(lines=[_line("A", price_basis="")])


def test_invalid_amounts_are_refused_without_implicit_repair():
    for bad in ("0", "-2"):
        with pytest.raises(QuoteInputError):
            _calculate(lines=[_line("A", quantity=bad)],
                       discount_rules=[])
    for bad in ("NaN", "Infinity", "-1"):
        with pytest.raises(QuoteInputError):
            _calculate(lines=[_line("A", unit_price=bad)],
                       discount_rules=[])
    with pytest.raises(QuoteInputError):
        _calculate(lines=[_line("A", currency="CAD")],
                   discount_rules=[])


def test_adapter_maps_invalid_inputs_to_a_typed_gap():
    from core.assignment_quote import _quote_calculate

    with pytest.raises(NeedsContext) as excinfo:
        asyncio.run(_quote_calculate(
            {"line_items": [_line("A", currency="CAD")],
             "currency": "USD", "freight": "0",
             "tax": {"basis": "none"}}, {}))
    assert excinfo.value.gap["concept"] == "quote_input"


def test_missing_exception_context_asks_when_it_changes_the_discount():
    rules = [
        {"name": "general", "when": {}, "rate": "0.05"},
        {"name": "licensed", "when": {"qualification": "licensed"},
         "rate": "0.10"},
    ]
    with pytest.raises(NeedsContext) as exc:
        resolve_discount_rule({"item_id": "A", "qualification": ""}, rules)
    assert "qualification" in exc.value.gap.get("question", "").lower()
    assert exc.value.gap["inputs"]["missing_fields"] == ["qualification"]
    assert resolve_discount_rule(
        {"item_id": "A", "qualification": "licensed"}, rules)["rate"] == "0.10"
    assert resolve_discount_rule(
        {"item_id": "A", "qualification": "unlicensed"}, rules)["rate"] == "0.05"


def test_definitively_excluded_exception_does_not_block():
    rules = [
        {"name": "general", "when": {}, "rate": "0.05"},
        {"name": "licensed", "when": {"qualification": "licensed"},
         "rate": "0.10"},
    ]
    assert resolve_discount_rule(
        {"item_id": "A", "qualification": "unlicensed"}, rules)["name"] == (
        "general")


def test_more_specific_unknown_different_behavior_asks():
    rules = [
        {"name": "general", "when": {}, "rate": "0.05"},
        {"name": "tier", "when": {"customer_tier": "gold"},
         "rate": "0.20"},
    ]
    with pytest.raises(NeedsContext):
        resolve_discount_rule({"item_id": "A"}, rules)


def test_equivalent_numeric_rates_do_not_ask_or_conflict():
    rules = [
        {"name": "general", "when": {}, "rate": "5"},
        {"name": "licensed", "when": {"qualification": "licensed"},
         "rate": "5.00"},
    ]
    assert resolve_discount_rule(
        {"item_id": "A", "qualification": ""}, rules)["name"] == "general"


def test_unknown_effective_date_asks_when_it_changes_applicability():
    rules = [
        {"name": "general", "when": {}, "rate": "0.05"},
        {"name": "promo", "when": {}, "rate": "0.10",
         "effective_from": "2026-01-01", "effective_to": "2026-12-31"},
    ]
    with pytest.raises(NeedsContext) as exc:
        resolve_discount_rule({"item_id": "A"}, rules, as_of="")
    assert "effective_date" in exc.value.gap["inputs"]["missing_fields"]


def test_unknown_rule_with_same_pricing_behavior_does_not_ask():
    rules = [
        {"name": "general", "when": {}, "rate": "5"},
        {"name": "same", "when": {"customer_tier": "gold"}, "rate": "5.00"},
    ]
    assert resolve_discount_rule({"item_id": "A"}, rules)["name"] == "general"


def test_equally_specific_established_rules_still_conflict():
    rules = [
        {"name": "a", "when": {"customer_tier": "gold"}, "rate": "0.05"},
        {"name": "b", "when": {"customer_tier": "gold"}, "rate": "0.10"},
    ]
    with pytest.raises(NeedsContext) as exc:
        resolve_discount_rule({"item_id": "A", "customer_tier": "gold"}, rules)
    assert exc.value.gap.get("concept") == "discount_rule_conflict"
