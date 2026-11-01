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
from decimal import Decimal
from itertools import product

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


# ---------------------------------------------------------------------------
# Completion-based discount oracle.
#
# A partial line is only allowed to return a governing rule when EVERY fully
# specified completion prices the line identically. The oracle builds its own
# Decimal-based pricing key rather than reusing the production signature.
# ---------------------------------------------------------------------------

_PRICING_FIELDS = ("cap", "cap_amount", "max_discount", "basis")


def _pricing_key(rule):
    if rule is None:
        return ("no_rule",)
    rate = Decimal(str(rule.get("rate"))).normalize()
    extras = tuple(sorted(
        (field, str(rule[field]))
        for field in _PRICING_FIELDS
        if rule.get(field) not in (None, "")))
    return ("rule", str(rate), extras)


def _completion_outcomes(partial, rules, domain, as_of_values=("",)):
    outcomes = set()
    # Only fill fields the partial input actually leaves open. A specified
    # value is never overwritten by the oracle.
    fields = sorted(
        field for field in domain
        if partial.get(field) in (None, ""))
    for values in product(*(domain[field] for field in fields)):
        line = dict(partial)
        line.update(dict(zip(fields, values)))
        for as_of in as_of_values:
            try:
                rule = resolve_discount_rule(line, rules, as_of=as_of)
            except NeedsContext as exc:
                assert exc.gap["concept"] == "discount_rule_conflict"
                outcomes.add(("conflict",))
            else:
                outcomes.add(_pricing_key(rule))
    return outcomes


def _assert_completion_sound(partial, rules, domain, as_of_values=("",)):
    """A confident partial result must agree with every completion."""
    outcomes = _completion_outcomes(partial, rules, domain, as_of_values)
    try:
        rule = resolve_discount_rule(partial, rules, as_of=as_of_values[0])
    except NeedsContext as exc:
        return exc
    assert len(outcomes) == 1, (
        f"partial decision {_pricing_key(rule)} disagrees with completions "
        f"{sorted(map(str, outcomes))}")
    assert _pricing_key(rule) in outcomes
    return rule


def _qualification_rules():
    return [
        {"name": "general", "rate": "0.05"},
        {"lesson_id": "licensed", "revision": 1,
         "name": "licensed customer", "when": {"qualification": "licensed"},
         "rate": "0.10"},
    ]


def test_missing_qualification_blocks_a_lower_specificity_established_rule():
    rules = _qualification_rules()
    line = _line("B", qualification="")
    with pytest.raises(NeedsContext) as excinfo:
        resolve_discount_rule(line, rules)
    gap = excinfo.value.gap
    assert gap["concept"] == "discount_scope"
    assert "qualification" in gap["question"]
    outcomes = _completion_outcomes(
        line, rules, {"qualification": ["licensed", "unlicensed"]})
    assert outcomes == {_pricing_key({"rate": "0.05"}),
                        _pricing_key({"rate": "0.10"})}
    # No arithmetic may happen before the clarification is answered.
    with pytest.raises(NeedsContext):
        _calculate(lines=[line], discount_rules=rules)


@pytest.mark.parametrize("qualification,rate,expected_total", [
    ("licensed", "0.10", "90.00"),
    ("unlicensed", "0.05", "95.00"),
])
def test_established_qualification_selects_the_governing_rule(
        qualification, rate, expected_total):
    rules = _qualification_rules()
    line = _line("B", quantity="1", qualification=qualification)
    resolved = _assert_completion_sound(
        line, rules, {"qualification": ["licensed", "unlicensed"]})
    assert resolved["rate"] == rate
    result = _calculate(
        lines=[line], freight="0", tax={"basis": "none"},
        discount_rules=rules)
    assert result["value"] == expected_total


def test_more_specific_unknown_rule_with_a_different_result_clarifies():
    rules = [
        {"name": "general", "rate": "0.05"},
        {"name": "enterprise licensed", "when": {
            "qualification": "licensed", "customer_type": "enterprise"},
         "rate": "0.20"},
    ]
    line = _line("B", qualification="", customer_type="enterprise")
    with pytest.raises(NeedsContext) as excinfo:
        resolve_discount_rule(line, rules)
    assert excinfo.value.gap["concept"] == "discount_scope"
    assert "qualification" in excinfo.value.gap["question"]
    outcomes = _completion_outcomes(
        line, rules, {"qualification": ["licensed", "unlicensed"]})
    assert len(outcomes) == 2


def test_equally_specific_established_rules_disagree_is_a_conflict():
    rules = [
        {"name": "A", "when": {"category": "B", "customer": "Acme"},
         "rate": "0.05"},
        {"name": "B", "when": {"category": "B", "customer": "Acme"},
         "rate": "0.10"},
    ]
    line = _line("B", category="B", customer="Acme")
    with pytest.raises(NeedsContext) as excinfo:
        resolve_discount_rule(line, rules)
    assert excinfo.value.gap["concept"] == "discount_rule_conflict"
    assert excinfo.value.gap["kind"] == "business_decision"


def test_known_false_condition_excludes_the_exception_without_asking():
    rules = [
        {"name": "general", "rate": "0.05"},
        {"name": "west licensed", "when": {
            "qualification": "licensed", "region": "West"}, "rate": "0.20"},
    ]
    line = _line("B", qualification="", region="East")
    resolved = _assert_completion_sound(
        line, rules, {"qualification": ["licensed", "unlicensed"]})
    assert resolved["rate"] == "0.05"


def test_missing_field_no_rule_uses_is_not_a_question():
    rules = [{"name": "general", "rate": "0.05"}]
    line = _line("B", region=None, tier=None, qualification=None)
    resolved = _assert_completion_sound(line, rules, {})
    assert resolved["rate"] == "0.05"


def test_decimal_equivalent_rates_do_not_conflict_or_ask():
    rules = [
        {"name": "general", "rate": "0.05"},
        {"name": "licensed", "when": {"qualification": "licensed"},
         "rate": "0.050"},
    ]
    line = _line("B", qualification="")
    resolved = _assert_completion_sound(
        line, rules, {"qualification": ["licensed", "unlicensed"]})
    assert resolved["rate"] == "0.05"
    assert _pricing_key(resolved) == _pricing_key({"rate": "0.050"})


def test_missing_effective_date_that_changes_applicability_clarifies():
    rules = [
        {"name": "general", "rate": "0.05"},
        {"name": "licensed from 2026", "when": {"qualification": "licensed"},
         "effective_from": "2026-01-01", "rate": "0.10"},
    ]
    line = _line("B", qualification="licensed")
    with pytest.raises(NeedsContext) as excinfo:
        resolve_discount_rule(line, rules, as_of="")
    assert excinfo.value.gap["concept"] == "discount_scope"
    assert "effective date" in excinfo.value.gap["question"]
    outcomes = _completion_outcomes(
        line, rules, {}, as_of_values=("2025-12-31", "2026-01-01"))
    assert len(outcomes) == 2


def test_unknown_rules_with_equivalent_pricing_need_no_redundant_question():
    rules = [
        {"name": "general", "rate": "0.05"},
        {"name": "licensed", "when": {"qualification": "licensed"},
         "rate": "0.050"},
    ]
    line = _line("B", qualification="")
    resolved = _assert_completion_sound(
        line, rules, {"qualification": ["licensed", "unlicensed"]})
    assert resolved["rate"] == "0.05"


def test_decimal_equivalent_percentage_rates_do_not_conflict_or_ask():
    rules = [
        {"name": "A", "when": {"category": "B", "customer": "Acme"},
         "rate": "0.05"},
        {"name": "B", "when": {"category": "B", "customer": "Acme"},
         "rate": "0.050"},
    ]
    line = _line("B", category="B", customer="Acme")
    resolved = _assert_completion_sound(line, rules, {})
    assert resolved["rate"] == "0.05"


def test_monetary_cap_refuses_instead_of_being_ignored():
    rules = [{"name": "capped", "when": {}, "rate": "0.10", "cap": "5.00"}]
    with pytest.raises(NeedsContext) as exc:
        resolve_discount_rule(_line("A"), rules)
    assert exc.value.gap["concept"] == "discount_rule_unsupported"
    assert "cap" in exc.value.gap["question"]


def test_fixed_discount_type_refuses():
    rules = [{"name": "fixed", "when": {}, "rate": "0.10",
              "discount_type": "fixed"}]
    with pytest.raises(NeedsContext) as exc:
        resolve_discount_rule(_line("A"), rules)
    assert exc.value.gap["concept"] == "discount_rule_unsupported"


def test_unsupported_basis_and_unknown_material_field_refuse():
    for rule in (
            {"name": "basis", "when": {}, "rate": "0.10",
             "basis": "tier_amount"},
            {"name": "unknown", "when": {}, "rate": "0.10",
             "tier_override": "gold"}):
        with pytest.raises(NeedsContext) as exc:
            resolve_discount_rule(_line("A"), [rule])
        assert exc.value.gap["concept"] == "discount_rule_unsupported"


def test_cap_currency_or_unit_ambiguity_refuses():
    rules = [{"name": "cap", "when": {}, "rate": "0.10",
              "cap": {"amount": "5.00", "currency": "CAD"}}]
    with pytest.raises(NeedsContext) as exc:
        resolve_discount_rule(_line("A"), rules)
    assert exc.value.gap["concept"] == "discount_rule_unsupported"


def test_supported_rule_receipt_preserves_normalized_pricing():
    result = _calculate(lines=[_line("A")], discount_rules=[{
        "lesson_id": "lesson-a", "revision": 4, "when": {},
        "rate": "0.050", "discount_type": "percentage", "basis": "rate",
    }])
    rule = result["rows"][0]["discount_rule"]
    assert rule["pricing"] == {
        "rate": "0.05", "discount_type": "percent", "basis": "rate"}
    assert rule["revision"] == 4
    assert result["calculation_receipt"]["discount_rules"][0]["pricing"] == (
        rule["pricing"])


def test_dated_unknown_rule_with_equivalent_pricing_is_not_a_question():
    rules = [
        {"name": "general", "rate": "0.05"},
        {"name": "licensed from 2026", "when": {"qualification": "licensed"},
         "effective_from": "2026-01-01", "rate": "0.050"},
    ]
    line = _line("B", qualification="")
    resolved = _assert_completion_sound(line, rules, {})
    assert resolved["rate"] == "0.05"


def test_missing_qualifier_is_never_treated_as_false():
    # A confident 5% here would silently skip a live 10% possibility.
    rules = _qualification_rules()
    line = _line("B", qualification="")
    with pytest.raises(NeedsContext):
        resolve_discount_rule(line, rules)
    assert resolve_discount_rule(
        _line("B", qualification="unlicensed"), rules)["rate"] == "0.05"
    assert resolve_discount_rule(
        _line("B", qualification="licensed"), rules)["rate"] == "0.10"


# ---------------------------------------------------------------------------
# Durable discount obligations: the answer is bound to one line, one field,
# one teaching revision and one source version. It resumes the original work;
# a wrong-line or stale answer is refused.
# ---------------------------------------------------------------------------


def _quote_inputs(line, rules, *, source_version="v1"):
    return {
        "line_items": [line],
        "currency": "USD",
        "freight": "0",
        "tax": {"basis": "none"},
        "discount_rules": list(rules),
        "source_evidence": [{
            "resource_id": "price-list",
            "source_version": source_version,
        }],
    }


def _quote_context(*, teaching="teach-r1", resolved=None, gap_ids=None):
    return {
        "teaching": {"revision": teaching},
        "step": {"gap_ids": list(gap_ids or [])},
        "sources": [],
        "resolved_gaps": list(resolved or []),
    }


def _resolved_gap(gap, answer, *, question_id="gap-1",
                  resolved_at="2026-11-01T12:00:00+00:00"):
    return {
        "question_id": question_id,
        "status": "resolved",
        "concept": gap["concept"],
        "step_id": "calculate",
        "inputs": gap["inputs"],
        "resolution": answer,
        "resolution_value": answer,
        "resolved_at": resolved_at,
    }


def _quote_gap(inputs, context):
    from core.assignment_quote import _quote_calculate

    with pytest.raises(NeedsContext) as excinfo:
        asyncio.run(_quote_calculate(inputs, context))
    return excinfo.value.gap


def test_resolved_discount_answer_resumes_the_bound_line():
    from core.assignment_quote import _quote_calculate

    rules = _qualification_rules()
    inputs = _quote_inputs(
        _line("B", quantity="1", qualification=""), rules)
    gap = _quote_gap(inputs, _quote_context())
    binding = gap["inputs"]["quote_discount"]
    assert binding["line_item_id"] == "B"
    assert binding["missing_fields"] == ["qualification"]
    assert binding["teaching_revision"] == "teach-r1"
    assert [rule["lesson_id"] for rule in binding["candidate_rules"]] == [
        None, "licensed"]
    assert binding["candidate_rules"][1]["revision"] == 1
    assert binding["source_versions"] == [{
        "scope": "source_evidence",
        "resource_id": "price-list",
        "source_version": "v1",
    }]
    assert gap["affected_subjects"] == ["B"]

    context = _quote_context(
        resolved=[_resolved_gap(gap, "licensed")], gap_ids=["gap-1"])
    result = asyncio.run(_quote_calculate(inputs, context))
    assert result["value"] == "90.00"
    assert result["rows"][0]["discount_rate"] == "0.10"
    assert result["rows"][0]["discount_rule"]["lesson_id"] == "licensed"
    # The caller's input is not mutated; the answer is attempt-local evidence.
    assert inputs["line_items"][0]["qualification"] == ""


def test_wrong_line_answer_is_refused_instead_of_transferred():
    rules = _qualification_rules()
    line_b = _line("B", qualification="")
    gap = _quote_gap(
        _quote_inputs(line_b, rules), _quote_context())
    line_a = _line("A", qualification="")
    fresh = _quote_gap(
        _quote_inputs(line_a, rules),
        _quote_context(
            resolved=[_resolved_gap(gap, "licensed")],
            gap_ids=["gap-1"]))
    assert fresh["concept"] == "discount_scope"
    assert fresh["inputs"]["quote_discount"]["line_item_id"] == "A"


@pytest.mark.parametrize("change,reason", [
    ({"teaching": "teach-r2"}, "teaching revision changed"),
    ({"source_version": "v2"}, "source version changed"),
])
def test_stale_answer_triggers_reassessment_not_transfer(change, reason):
    rules = _qualification_rules()
    inputs = _quote_inputs(
        _line("B", quantity="1", qualification=""), rules)
    gap = _quote_gap(inputs, _quote_context())
    stale_inputs = _quote_inputs(
        _line("B", qualification=""),
        rules,
        source_version=change.get("source_version", "v1"))
    context = _quote_context(
        teaching=change.get("teaching", "teach-r1"),
        resolved=[_resolved_gap(gap, "licensed")],
        gap_ids=["gap-1"])
    reassessment = _quote_gap(stale_inputs, context)
    assert reassessment["concept"] == "discount_reassessment_required"
    assert reason in reassessment["reason"]
    binding = reassessment["inputs"]["quote_discount"]
    assert binding["line_item_id"] == "B"
    assert binding["missing_fields"] == ["qualification"]
    assert binding["teaching_revision"] == change.get("teaching", "teach-r1")


def test_conflict_answer_selects_one_candidate_and_resumes():
    from core.assignment_quote import _quote_calculate

    rules = [
        {"name": "A", "when": {"category": "B", "customer": "Acme"},
         "rate": "0.05"},
        {"name": "B", "when": {"category": "B", "customer": "Acme"},
         "rate": "0.10"},
    ]
    inputs = _quote_inputs(
        _line("B", quantity="1", category="B", customer="Acme"), rules)
    gap = _quote_gap(inputs, _quote_context())
    assert gap["concept"] == "discount_rule_conflict"
    context = _quote_context(
        resolved=[_resolved_gap(gap, "A")], gap_ids=["gap-1"])
    result = asyncio.run(_quote_calculate(inputs, context))
    assert result["value"] == "95.00"
    assert result["rows"][0]["discount_rate"] == "0.05"
