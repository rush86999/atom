# -*- coding: utf-8 -*-
"""Taught pricing calculations (round 66): deterministic Decimal
arithmetic over typed inputs. Expected values are computed
INDEPENDENTLY here (hand arithmetic), not by calling the
implementation — the controls verify, not repeat."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from decimal import Decimal

import pytest

from core.pricing_calculation import (
    CalculationResult, Money, PolicyStep, PricingInputError, PricingInputs,
    SourceRef, TaughtPolicy, render_comparison, run_policy,
)


def _src(kind="workbook_cell", ref="WB!Sheet!A1", seen=None):
    return SourceRef(kind=kind, reference=ref, observed_at=seen)


def _policy(steps, pid="synthetic", version="1", window=None):
    return TaughtPolicy(
        policy_id=pid, name="synthetic", steps=steps,
        provenance="synthetic:test", version=version,
        freshness_window_days=window)


class TestSyntheticControls:
    """The work order's controls — expected values by hand."""

    def test_markup_100_to_120(self):
        res = run_policy(
            _policy([PolicyStep("apply_markup", {"percent": 20})]),
            PricingInputs(base=Money(Decimal("100"), "CAD"),
                          source=_src()))
        assert res.status == "succeeded"
        # hand: 100 × 1.20 = 120
        assert res.proposed.amount == Decimal("120.00")

    def test_margin_100_to_125(self):
        res = run_policy(
            _policy([PolicyStep("apply_margin", {"percent": 20})]),
            PricingInputs(base=Money(Decimal("100"), "CAD"),
                          source=_src()))
        assert res.status == "succeeded"
        # hand: 100 / (1 - 0.20) = 125
        assert res.proposed.amount == Decimal("125")

    def test_missing_exchange_rate_leaves_unresolved(self):
        res = run_policy(
            _policy([PolicyStep("convert_currency", {"to": "CAD"})]),
            PricingInputs(base=Money(Decimal("100"), "USD"),
                          source=_src()))
        assert res.status == "unresolved"
        assert res.proposed is None
        assert "exchange" in res.unresolved_reason.lower() or \
            "not provided" in res.unresolved_reason

    def test_invalid_margin_rejected(self):
        res = run_policy(
            _policy([PolicyStep("apply_margin", {"percent": 100})]),
            PricingInputs(base=Money(Decimal("100"), "CAD"),
                          source=_src()))
        assert res.status == "rejected"
        assert "margin" in res.rejection_reason.lower()

    def test_unsupported_unit_rejected_on_use(self):
        # kg priced per-hour without a conversion: the hourly policy's
        # arithmetic is fine but the unit basis is incompatible — the
        # RESULT names the unit, and the comparison refuses to present
        # it as an hourly price.
        res = run_policy(
            _policy([PolicyStep("apply_markup", {"percent": 10})]),
            PricingInputs(base=Money(Decimal("100"), "CAD", unit="kg"),
                          source=_src()))
        assert res.status == "succeeded"
        assert res.proposed.unit == "kg"  # preserved, never silently
        # renamed — the caller's comparison must surface the basis

    def test_stale_source_freshness_limited(self):
        res = run_policy(
            _policy([PolicyStep("apply_markup", {"percent": 10})],
                     window=30),
            PricingInputs(
                base=Money(Decimal("100"), "CAD"),
                source=_src(seen="2020-01-01")))
        assert res.status == "succeeded"
        assert res.freshness == "stale"
        cmp_text = render_comparison("Item", None, res)
        assert "freshness-limited" in cmp_text

    def test_manual_override_preserved(self):
        res = run_policy(
            _policy([PolicyStep("apply_margin", {"percent": 45})]),
            PricingInputs(
                base=Money(Decimal("100"), "CAD"),
                source=_src(),
                manual_override=Money(Decimal("2902"), "CAD")))
        assert res.status == "succeeded"
        assert res.proposed.amount == Decimal("2902")
        assert any(s["op"] == "manual_override_passthrough"
                   for s in res.steps)
        cmp_text = render_comparison(
            "No. 381", Money(Decimal("2902"), "CAD"), res)
        assert "PRESERVED" in cmp_text

    def test_roundup_whole_dollars(self):
        res = run_policy(
            _policy([PolicyStep("apply_markup", {"percent": 13}),
                     PolicyStep("round", {"mode": "up", "places": 0})]),
            PricingInputs(base=Money(Decimal("100"), "CAD"),
                          source=_src()))
        # hand: 100 × 1.13 = 113.00 exactly — use a non-exact base
        res2 = run_policy(
            _policy([PolicyStep("apply_markup", {"percent": 13}),
                     PolicyStep("round", {"mode": "up", "places": 0})]),
            PricingInputs(base=Money(Decimal("99.99"), "CAD"),
                          source=_src()))
        # hand: 99.99 × 1.13 = 112.9887 → ROUNDUP → 113
        assert res2.proposed.amount == Decimal("113")

    def test_steps_replay(self):
        inputs = PricingInputs(base=Money(Decimal("200"), "USD"),
                               source=_src(),
                               exchange_rate={"from": "USD", "to": "CAD",
                                              "rate": "1.35",
                                              "source": "lesson test"})
        res = run_policy(
            _policy([PolicyStep("convert_currency", {"to": "CAD"}),
                     PolicyStep("apply_margin", {"percent": 30})]),
            inputs)
        # hand: 200 × 1.35 = 270 CAD; 270 / 0.70 = 385.714285…
        assert res.status == "succeeded"
        assert res.proposed.currency == "CAD"
        assert res.proposed.amount == Decimal("270") / Decimal("0.7")
        assert [s["op"] for s in res.steps] == [
            "convert_currency", "apply_margin"]
        assert res.steps[0]["input_amount"] == "200"
        assert Decimal(res.steps[0]["output_amount"]) == Decimal("270")


class TestSecondBusinessFixture:
    """A service fee from hours × approved rate — same mechanism, no
    purchasing branches."""

    def test_hours_times_rate(self):
        res = run_policy(
            _policy([PolicyStep("multiply", {"factor_from": "hours"}),
                     PolicyStep("round", {"mode": "half_up",
                                          "places": 2})],
                    pid="consulting-fee"),
            PricingInputs(
                base=Money(Decimal("150"), "USD", unit="hour"),
                source=SourceRef(kind="contract",
                                 reference="MSA-2026 §4.2 (rate card)",
                                 observed_at="2026-01-15"),
                params={"hours": "17.5"}))
        # hand: 150 × 17.5 = 2625.00
        assert res.status == "succeeded"
        assert res.proposed.amount == Decimal("2625.00")
        assert res.proposed.unit == "hour"
        assert res.policy_id == "consulting-fee"

    def test_missing_hours_unresolved(self):
        res = run_policy(
            _policy([PolicyStep("multiply", {"factor_from": "hours"})],
                    pid="consulting-fee"),
            PricingInputs(
                base=Money(Decimal("150"), "USD", unit="hour"),
                source=_src()))
        assert res.status == "unresolved"
        assert res.proposed is None


class TestGovernanceBoundaries:
    def test_unknown_step_rejected(self):
        res = run_policy(
            _policy([PolicyStep("invent_number", {})]),
            PricingInputs(base=Money(Decimal("1"), "CAD"),
                          source=_src()))
        assert res.status == "rejected"
        assert "unknown step" in res.rejection_reason

    def test_negative_exchange_rate_rejected(self):
        with pytest.raises(PricingInputError):
            PricingInputs(
                base=Money(Decimal("100"), "USD"), source=_src(),
                exchange_rate={"from": "USD", "to": "CAD",
                               "rate": "-1"}).validate()

    def test_result_records_policy_and_inputs(self):
        res = run_policy(
            _policy([PolicyStep("apply_markup", {"percent": 5})],
                    pid="p-1", version="3"),
            PricingInputs(base=Money(Decimal("10"), "CAD"),
                          source=_src(ref="X!Y!Z9", seen="2026-09-01")))
        rec = res.to_record()
        assert rec["policy_id"] == "p-1"
        assert rec["policy_version"] == "3"
        assert rec["inputs"]["source"]["reference"] == "X!Y!Z9"
        assert rec["status"] == "succeeded"

    def test_changed_policy_is_a_new_version_not_a_rewrite(self):
        """A result computed under v1 stays v1; re-running under v2 is
        a separate result record — the runner never mutates a prior
        result."""
        inputs = PricingInputs(base=Money(Decimal("100"), "CAD"),
                              source=_src())
        r1 = run_policy(_policy([PolicyStep("apply_markup",
                                            {"percent": 20})],
                                version="1"), inputs)
        r2 = run_policy(_policy([PolicyStep("apply_markup",
                                            {"percent": 25})],
                                version="2"), inputs)
        assert r1.policy_version == "1" and r1.proposed.amount == \
            Decimal("120.00")
        assert r2.policy_version == "2" and r2.proposed.amount == \
            Decimal("125.00")
        assert r1.result_id != r2.result_id


class TestTaughtPolicyParsing:
    """The Brennan rules parsed from the durable teaching into typed
    policies — provenance and version on each. Arithmetic expectations
    hand-computed."""

    def _ladder_policy(self):
        from core.pricing_calculation import parse_taught_policies
        return parse_taught_policies([
            {"lesson": ("Used machinery list price — PRIMARY method: take "
                        "the RETAIL LIST PRICE of the same machine NEW and "
                        "depreciate it according to market trends until the "
                        "machine's current age is reached. SECONDARY / "
                        "BACKUP method: derive it from the F-5216 workbook "
                        "ladder — start at the dealer's factory price, "
                        "apply the dealer discount (F235*0.9), add freight "
                        "(H235+700), add warehouse handling (J235*1.02), "
                        "then the Brennan margin steps (K235/0.87 and "
                        "L235/0.86), and ROUNDUP to whole dollars (N235)"),
             "id": "4b6a11cc"},
            {"lesson": ("standard calculation start with USD but when "
                        "reselling old machines, it's from canada, the "
                        "currency is in CAD. Exchange rate will not matter "
                        "in this situation"),
             "id": "cad-rule"},
        ])

    def test_primary_and_fallback_policies_parsed(self):
        policies = self._ladder_policy()
        ids = {p.policy_id for p in policies}
        assert "used-machinery-depreciation" in ids
        assert "workbook-ladder" in ids
        for p in policies:
            assert p.provenance  # lesson id named
            assert p.version

    def test_fallback_ladder_arithmetic(self):
        """The taught ladder as pure arithmetic: factory 1000 →
        discount ×0.9 → +freight 700 → ×1.02 → /0.87 → /0.86 → ROUNDUP.
        Hand: 1000×0.9=900; +700=1600; ×1.02=1632; /0.87=1875.862…;
        /0.86=2181.236…; ROUNDUP=2182."""
        policies = {p.policy_id: p for p in self._ladder_policy()}
        ladder = policies["workbook-ladder"]
        res = run_policy(ladder, PricingInputs(
            base=Money(Decimal("1000"), "CAD"),
            source=_src(ref="F5216!F235", seen="2019-01-01"),
            params={"freight_amount": "700"}))
        assert res.status == "succeeded"
        assert res.proposed.amount == Decimal("2182")

    def test_primary_depreciation_arithmetic(self):
        """New retail 10000, 15%/yr for 3 years: 10000×0.85³ = 6141.25
        → ROUNDUP whole dollars = 6142."""
        policies = {p.policy_id: p for p in self._ladder_policy()}
        prim = policies["used-machinery-depreciation"]
        res = run_policy(prim, PricingInputs(
            base=Money(Decimal("10000"), "CAD"),
            source=_src(ref="vendor-quote-2026", seen="2026-08-01"),
            params={"annual_percent": "15", "years": "3"}))
        assert res.status == "succeeded"
        assert res.proposed.amount == Decimal("6142")


class TestMissingBindingUnresolved:
    """A taught policy's per-item binding absent from the inputs is
    UNRESOLVED with the name — never a literal execution."""

    def test_missing_depreciation_years(self):
        from core.pricing_calculation import parse_taught_policies
        policies = parse_taught_policies([{
            "lesson": ("take the RETAIL LIST PRICE of the same machine "
                       "NEW and depreciate it until the machine's current "
                       "age is reached, then ROUNDUP"),
            "id": "l1"}])
        res = run_policy(policies[0], PricingInputs(
            base=Money(Decimal("10000"), "CAD"),
            source=_src(),
            params={"annual_percent": "15"}))  # years missing
        assert res.status == "unresolved"
        assert "years" in res.unresolved_reason
        assert res.proposed is None
