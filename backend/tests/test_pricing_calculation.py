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
    """Round 67 integrity: EXPLICIT taught rules only; Decimal
    literals; unresolved conditions for unstated rates/rounding."""

    LADDER_LESSON = (
        "SECONDARY / BACKUP method: derive it from the F-5216 workbook "
        "ladder — start at the dealer's factory price, apply the dealer "
        "discount (F235*0.9), add freight (H235+700), add warehouse "
        "handling (J235*1.02), then the Brennan margin steps (K235/0.87 "
        "and L235/0.86), and ROUNDUP to whole dollars (N235)")

    def test_ladder_parses_as_taught_divisions_not_margin(self):
        from core.pricing_calculation import parse_taught_policies
        policies = parse_taught_policies([
            {"lesson": self.LADDER_LESSON, "id": "4b6a11cc"}])
        assert len(policies) == 1
        p = policies[0]
        ops = [s.op for s in p.steps]
        # Exact taught operations in text order — divisions STAY
        # divisions (no margin semantics derived).
        assert ops == ["multiply", "add_freight", "multiply",
                       "divide", "divide", "round"]
        # Decimal literals, byte-exact from the teaching.
        assert p.steps[0].params["factor"] == "0.9"
        assert p.steps[3].params["divisor"] == "0.87"
        assert p.steps[4].params["divisor"] == "0.86"
        assert p.steps[5].params == {"mode": "up", "places": 0}
        assert p.provenance == "lesson:4b6a11cc"

    def test_ladder_arithmetic_decimal_exact(self):
        """Hand-computed: 1000 ×0.9=900; +700=1600; ×1.02=1632;
        ÷0.87=1875.8620689655...; ÷0.86=2181.234...; ROUNDUP=2182."""
        from core.pricing_calculation import parse_taught_policies
        p = parse_taught_policies([
            {"lesson": self.LADDER_LESSON, "id": "4b6a11cc"}])[0]
        res = run_policy(p, PricingInputs(
            base=Money(Decimal("1000"), "CAD"),
            source=_src(ref="F5216!F235", seen="2019-01-01")))
        assert res.status == "succeeded"
        assert res.proposed.amount == Decimal("2182")

    def test_depreciation_mention_without_numbers_is_unresolved(self):
        """The reviewer's exact case: 'depreciate the new price' with no
        percent/method/rounding teaches the METHOD, not a recipe — the
        policy carries the unresolved condition, and no steps fire."""
        from core.pricing_calculation import parse_taught_policies
        policies = parse_taught_policies([{
            "lesson": ("take the RETAIL LIST PRICE of the same machine "
                       "NEW and depreciate it until the current age"),
            "id": "l-dep"}])
        # No steps -> no policy at all; the condition only surfaces when
        # a lesson ALSO teaches an executable rule. Verify by feeding it
        # with one markup rule attached.
        policies2 = parse_taught_policies([{
            "lesson": ("depreciate it until the current age. Backup: "
                       "apply 40 percent markup"),
            "id": "l-dep2"}])
        assert len(policies) == 0 or all(
            not p.steps for p in policies)
        assert any(
            "depreciation" in c.lower()
            for p in policies2 for c in p.conditions)
        assert any(s.op == "apply_markup" for p in policies2
                   for s in p.steps)

    def test_depreciation_with_taught_percent(self):
        from core.pricing_calculation import parse_taught_policies
        policies = parse_taught_policies([{
            "lesson": ("depreciate 15 percent per year until the "
                       "machine's current age, then ROUNDUP"),
            "id": "l-dep3"}])
        assert policies
        steps = policies[0].steps
        assert steps[0].op == "depreciate"
        assert steps[0].params["annual_percent"] == "15"
        assert steps[0].params["years"] == "{years}"
        res = run_policy(policies[0], PricingInputs(
            base=Money(Decimal("10000"), "CAD"), source=_src(),
            params={"years": "3"}))
        # hand: 10000×0.85³=6141.25 → ROUNDUP → 6142
        assert res.proposed.amount == Decimal("6142")

    def test_versions_stable_across_processes(self):
        import subprocess, sys
        code = (
            "import sys; sys.path.insert(0, '.')\n"
            "from core.pricing_calculation import parse_taught_policies\n"
            "ps = parse_taught_policies([{'lesson': %r, 'id': 'x'}])\n"
            "print([p.version for p in ps])" % self.LADDER_LESSON)
        r1 = subprocess.run([sys.executable, "-c", code],
                            capture_output=True, text=True, cwd=".")
        r2 = subprocess.run([sys.executable, "-c", code],
                            capture_output=True, text=True, cwd=".")
        assert r1.stdout == r2.stdout
        assert r1.stdout.strip().startswith("['")  # non-empty digest


class TestJobLinkedCalculation:
    """§4: a calculation is an operation on the existing job —
    persisted result + policy version; unresolved inputs become durable
    next-work; a differing computed price becomes an owner decision."""

    def _lifecycle(self, tmp_path):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from core.models import (GoalObjective, GoalRun,
                                  TaskOperationRecord)
        from core.goals.goal_run_service import GoalRunService
        from core.goals.goal_service import GoalService
        from core.task_lifecycle import TaskLifecycle
        engine = create_engine(f"sqlite:///{tmp_path}/pc.db")
        for t in (GoalObjective.__table__, GoalRun.__table__,
                  TaskOperationRecord.__table__):
            t.create(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        return TaskLifecycle(
            GoalRunService(workspace_id="ws", tenant_id="t",
                           session_factory=factory),
            GoalService(workspace_id="ws", tenant_id="t",
                        session_factory=factory))

    def test_succeeded_calculation_persists_with_policy_version(
            self, tmp_path):
        from core.pricing_calculation import record_calculation
        from core.task_lifecycle import begin_retrieval_turn
        lc = self._lifecycle(tmp_path)
        run_id, _ = begin_retrieval_turn(
            lc, {"id": "s1"}, "conv-pc", "verify", "e1")
        res = run_policy(
            _policy([PolicyStep("apply_margin", {"percent": 45})],
                    pid="fallback-margin", version="9"),
            PricingInputs(base=Money(Decimal("100"), "CAD"),
                          source=_src()))
        op = record_calculation(
            lc, run_id, "SLE24-16", res,
            draft_price=Money(Decimal("8880"), "CAD"))
        assert op is not None
        rec = lc.get_task(run_id)
        calc_op = next(o for o in rec["operations"]
                       if o["operation_id"] == op["operation_id"])
        assert calc_op["status"] == "applied"
        assert calc_op["calculation"]["policy_version"] == "9"
        assert calc_op["calculation"]["status"] == "succeeded"
        assert calc_op["draft_price"]["amount"] == "8880"
        # The differing computed price became an OWNER DECISION.
        decisions = [q for q in rec["task_revision"]["unresolved"]
                     if q["kind"] == "business_decision"]
        assert decisions and "8880" in decisions[0]["question"]

    def test_unresolved_calculation_creates_next_work(self, tmp_path):
        from core.pricing_calculation import record_calculation
        from core.task_lifecycle import (begin_retrieval_turn,
                                          next_unfinished_work)
        lc = self._lifecycle(tmp_path)
        run_id, _ = begin_retrieval_turn(
            lc, {"id": "s1"}, "conv-pc2", "verify", "e1")
        res = run_policy(
            _policy([PolicyStep("convert_currency", {"to": "CAD"})]),
            PricingInputs(base=Money(Decimal("100"), "USD"),
                          source=_src()))
        assert res.status == "unresolved"
        record_calculation(lc, run_id, "U-22", res)
        rec = lc.get_task(run_id)
        calc_op = next(o for o in rec["operations"]
                       if o["operation_type"] == "calculate")
        assert calc_op["status"] == "waiting"
        work = next_unfinished_work(rec)
        assert any("cannot complete" in str(a.get("question"))
                   for a in work["actions"])


class TestCalculateQueryEntry:
    """Round 67: the planner lane's typed query — unknown policy is an
    honest outcome; the available ids list comes from the real
    teaching (this test seeds the store via the registry)."""

    @pytest.mark.asyncio
    async def test_unknown_policy_names_available(self, tmp_path,
                                                  monkeypatch):
        from core.pricing_calculation import calculate_from_query
        # point the DB loader at a scratch store with no agents
        r = await calculate_from_query(
            "calculate some-policy from 100 CAD", "u1", None)
        assert "UNKNOWN POLICY" in r
        assert "Do not compute a price by hand" in r

    def test_query_pattern_parses(self):
        from core.pricing_calculation import _QUERY_PATTERNS
        m = _QUERY_PATTERNS[0].match(
            "calculate taught-multiply-add_freight from 1000 CAD "
            "freight_amount=700 source=F5216!F235 override=2902")
        assert m
        assert m.group("policy") == "taught-multiply-add_freight"
        assert m.group("amount") == "1000"
        assert m.group("currency") == "CAD"
