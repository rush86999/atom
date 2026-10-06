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


# ---------------------------------------------------------------------------
# Rounds 69-70: workbook-grounded pricing as an APPLICATION over the
# general formula engine (core.formula_engine). The engine evaluates;
# this surface authorizes (teaching), attaches money/freshness/
# provenance, and blocks incomplete calculations from ever publishing
# a price. Fidelity numbers are hand-derived and cross-checked against
# the independent `formulas` engine; they are never echoes of the
# implementation.
# ---------------------------------------------------------------------------

_LIVE_2019 = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "sheet_datasets", "default", "ce61dd3d40ca")

_SKIP_LIVE = not os.path.isdir(_LIVE_2019)


def _build_burrking_fixture(path):
    """A workbook reproducing the live BurrKing structure: a parameter
    column in the AB region (incl. the cross-sheet AB8 =
    'Exchange-Index'!H4), the multiply ladder, literal additions
    (electrical, EMPTY freight cells, flat via a bare $-param formula),
    terminal ROUNDUP — and rows binding DIFFERENT parameter cells
    (row 225 -> $AB$18/$AB$41; row 325 -> $AB$2). Boundary rows land
    ROUNDUP exactly on / just above an integer; row 60 carries an
    unsupported IF(); row 61 references an unresolvable $AZ$1."""
    from openpyxl import Workbook

    wb = Workbook()
    xi = wb.active
    xi.title = "Exchange-Index"
    xi["H4"] = 1.45

    bk = wb.create_sheet("BurrKing")
    bk["AB1"] = 0.675
    bk["AB2"] = 0.72
    bk["AB8"] = "='Exchange-Index'!H4"
    bk["AB11"] = 1.03
    bk["AB15"] = 150
    bk["AB18"] = 175
    bk["AB36"] = 1.1364
    bk["AB41"] = 1.2
    bk["AB42"] = 1.25

    def chain(row, cost, electrical, disc, flat_param, final_param):
        bk[f"H{row}"] = cost
        bk[f"I{row}"] = f"=SUM(H{row}*1)"
        bk[f"K{row}"] = f"=SUM(I{row}*{disc})"
        bk[f"L{row}"] = f"=SUM(K{row}*$AB$8)"
        bk[f"M{row}"] = f"=SUM(L{row}*$AB$11)"
        bk[f"N{row}"] = electrical
        # P and Q stay EMPTY — the blank-operand rule
        bk[f"R{row}"] = f"={flat_param}"
        bk[f"S{row}"] = f"=M{row}+N{row}+P{row}+Q{row}+R{row}"
        bk[f"U{row}"] = f"=S{row}*$AB$36"
        bk[f"W{row}"] = f"=U{row}*{final_param}"
        bk[f"E{row}"] = f"=ROUNDUP(W{row},0)"

    chain(25, 4777, 250, "$AB$1", "$AB$15", "$AB$42")   # the live row
    chain(225, 3000, 250, "$AB$1", "$AB$18", "$AB$41")  # other params
    chain(325, 1000, 250, "$AB$2", "$AB$15", "$AB$42")  # AB2 discount

    bk["H50"] = 1000
    bk["K50"] = "=SUM(H50*$AB$1)"
    bk["E50"] = "=ROUNDUP(K50,0)"       # 675 exactly — ROUNDUP no-op
    bk["H51"] = 1000.001
    bk["K51"] = "=SUM(H51*$AB$1)"
    bk["E51"] = "=ROUNDUP(K51,0)"       # 675.000675 -> 676
    bk["H52"] = 100.004
    bk["K52"] = "=SUM(H52*$AB$1)"
    bk["E52"] = "=ROUNDUP(K52,2)"       # 67.5027 -> 67.51 at 2 places

    bk["H60"] = 500
    bk["W60"] = "=U60*1.1"
    bk["U60"] = "=H60*2"
    bk["E60"] = '=IF(H60>5, W60, W60*2)'   # IF() unsupported — named
    bk["H61"] = 200
    bk["K61"] = "=SUM(H61*$AZ$1)"          # AZ1 has no value anywhere

    ts = wb.create_sheet("Tennsmith")
    ts["A106"] = "GSL48-16"
    ts["E106"] = 14318

    wb.save(path)
    return path


class _Fixture:
    """The fixture workbook materialized the way the app sees it: the
    formula sidecar through the app's OWN extractor, references
    through the engine's live-grid reader (openpyxl translates shared
    formulas; data_only yields literals — an openpyxl-written file has
    no cached formula results, which is exactly the durable-frame
    situation)."""

    def __init__(self, tmp_path):
        from core.formula_engine import workbook_grid_from_bytes
        from core.sheet_dataset_service import _extract_formula_map

        self.path = str(_build_burrking_fixture(tmp_path / "bk.xlsx"))
        with open(self.path, "rb") as fh:
            content = fh.read()
        self.sidecars = _extract_formula_map(content, "xlsx")
        grid = workbook_grid_from_bytes(content)
        self.books = {
            name: {"formulas": d["formulas"], "values": d["values"]}
            for name, d in grid.items()}
        self.empties = self._used_range_blanks()
        self._oracle = None

    def _used_range_blanks(self):
        """Spreadsheet blank semantics for the fixture: a cell inside
        the sheet's used range with no value is BLANK (the known-blank
        set a materialized frame carries)."""
        from openpyxl import load_workbook
        from openpyxl.utils import get_column_letter, range_boundaries

        out = {}
        wb = load_workbook(self.path, read_only=True)
        try:
            for ws in wb.worksheets:
                key = " ".join(str(ws.title).lower().split())
                vals = self.books.get(key, {}).get("values", {})
                blanks = set()
                try:
                    mc, mr, xc, xr = range_boundaries(
                        ws.calculate_dimension())
                except Exception:  # noqa: BLE001 — no dimension, no blanks
                    out[key] = blanks
                    continue
                for col in range(mc, min(xc, 40) + 1):
                    letter = get_column_letter(col)
                    for row in range(mr, min(xr, 500) + 1):
                        addr = f"{letter}{row}"
                        if addr not in vals:
                            blanks.add(addr)
                out[key] = blanks
        finally:
            wb.close()
        return out

    def sidecar(self, sheet):
        return self.sidecars.get(sheet, {})

    def book(self, sheet, extra_values=None, drop_formulas=()):
        from core.formula_engine import CellBook

        d = self.books[sheet.strip().lower()]
        formulas = {k: v for k, v in d["formulas"].items()
                    if k not in set(drop_formulas)}
        values = dict(d["values"])
        values.update(extra_values or {})
        return CellBook(sheet, formulas, values,
                        self.empties.get(sheet.strip().lower()))

    def provider(self, extra_xi=None):
        from core.formula_engine import CellBook

        d = self.books["exchange-index"]
        values = dict(d["values"])
        values.update(extra_xi or {})
        xi = CellBook("Exchange-Index", self.sidecar("Exchange-Index"),
                      values)
        return lambda name: (
            xi if name.strip().lower() == "exchange-index" else None)

    def oracle(self, sheet, cell):
        """The INDEPENDENT evaluation: the repo's declared `formulas`
        engine compiles the whole workbook and calculates the cell."""
        import os

        if self._oracle is None:
            import formulas as _f

            model = _f.ExcelModel().loads(self.path).finish()
            self._oracle = {str(k).upper(): v
                            for k, v in model.calculate().items()}
        key = (f"'[{os.path.basename(self.path)}]"
               f"{sheet.strip()}'!{cell}").upper()
        val = self._oracle.get(key)
        if hasattr(val, "value") and not isinstance(
                val, (int, float, bool, str)):
            val = val.value  # Ranges -> scalar
        while isinstance(val, (list, tuple)) and len(val) == 1:
            val = val[0]
        if hasattr(val, "item") and not isinstance(
                val, (int, float, bool, str)):
            val = val.item()
        return float(val)


class TestWorkbookFidelity:
    """The pricing application over the engine: reconstruction
    byte-exact against independent evaluations, and fail-closed with
    the exact gap named."""

    @pytest.fixture(scope="class")
    def fixture(self, tmp_path_factory):
        return _Fixture(tmp_path_factory.mktemp("bk"))

    def _calc(self, fixture, row, sheet="BurrKing"):
        from core.formula_engine import evaluate_reference

        return evaluate_reference(
            sheet, f"E{row}", fixture.book(sheet),
            fixture.provider(), row_of_interest=row,
            origin={"file": "bk.xlsx", "sheet": sheet,
                    "row": str(row), "output_cell": f"E{row}",
                    "version": "fixturev1"})

    def test_demonstrated_row_replays_byte_exact(self, fixture):
        """The live row's own structure: 4777 x 0.675 x 1.45 (via the
        CROSS-SHEET Exchange-Index!H4) x 1.03 + 250 + 0 + 0 + 150,
        x 1.1364 x 1.25, ROUNDUP -> 7409 (hand-derived; equals the live
        workbook's cached output)."""
        calc = self._calc(fixture, 25)
        assert calc.status == "computed", calc.missing or calc.unsupported
        assert calc.value == Decimal("7409")
        assert abs(fixture.oracle("BurrKing", "E25") - 7409.0) < 0.01

    def test_row_binding_different_parameters(self, fixture):
        """Row 225 binds $AB$18 (flat 175) and $AB$41 (1.2) — NOT row
        25's cells: per-row parameter binding comes from the row's OWN
        formulas."""
        calc = self._calc(fixture, 225)
        assert calc.status == "computed", calc.missing or calc.unsupported
        deps = {f"{d.sheet}!{d.cell}" for d in calc.dependencies}
        assert "BurrKing!AB18" in deps and "BurrKing!AB41" in deps
        assert "BurrKing!AB15" not in deps and "BurrKing!AB42" not in deps
        oracle = round(fixture.oracle("BurrKing", "E225"), 6)
        assert abs(float(calc.value) - oracle) < 0.01, (
            float(calc.value), oracle)

    def test_second_discount_parameter(self, fixture):
        """Row 325 prices through $AB$2 (0.72) — the sheet's second
        discount column, reconstructed per row."""
        calc = self._calc(fixture, 325)
        assert calc.status == "computed"
        deps = {f"{d.sheet}!{d.cell}" for d in calc.dependencies}
        assert "BurrKing!AB2" in deps and "BurrKing!AB1" not in deps
        oracle = round(fixture.oracle("BurrKing", "E325"), 6)
        assert abs(float(calc.value) - oracle) < 0.01

    def test_literal_additions_and_blank_operands(self, fixture):
        """Electrical 250 is a row literal; the freight cells are EMPTY
        and count as 0 under the blank rule (recorded as such, with a
        note — never silently); the flat comes through a bare
        $AB$15 formula."""
        calc = self._calc(fixture, 25)
        by_cell = {f"{d.sheet}!{d.cell}": d for d in calc.dependencies}
        assert by_cell["BurrKing!N25"].value == "250"
        assert by_cell["BurrKing!N25"].role == "input"
        for c in ("P25", "Q25"):
            dep = by_cell[f"BurrKing!{c}"]
            assert dep.value == "0"
            assert "blank" in (dep.note or "").lower()
        assert by_cell["BurrKing!R25"].value == "150"
        assert by_cell["BurrKing!AB15"].value == "150"
        adds = [s for s in calc.steps if s["op"] == "add"]
        assert len(adds) == 4  # M+N, +P, +Q, +R

    def test_cross_sheet_parameter_pair_recorded(self, fixture):
        """AB8 is itself a formula pointing at Exchange-Index!H4 — both
        ends of the cross-sheet dependency are recorded."""
        calc = self._calc(fixture, 25)
        by_key = {(d.sheet, d.cell): d for d in calc.dependencies}
        assert ("BurrKing", "AB8") in by_key
        xi = by_key.get(("Exchange-Index", "H4"))
        assert xi is not None and xi.value == "1.45"
        assert xi.role == "reference"

    def test_rounding_boundaries(self, fixture):
        """ROUNDUP is a no-op exactly on an integer, bumps just above
        one, and respects the formula's own decimal places."""
        exact = self._calc(fixture, 50)
        assert exact.value == Decimal("675")
        above = self._calc(fixture, 51)
        assert above.value == Decimal("676")
        places = self._calc(fixture, 52)
        assert places.value == Decimal("67.51")
        for row, val in ((50, 675.0), (51, 676.0), (52, 67.51)):
            assert abs(fixture.oracle("BurrKing", f"E{row}") - val) < 0.01

    def test_unsupported_formula_is_incomplete_never_partial(self, fixture):
        """IF() is outside the supported language: the calculation comes
        back INCOMPLETE naming IF(), with NO value and — through the
        pricing adapter — NO proposed price."""
        from core.pricing_calculation import workbook_calculation_result

        calc = self._calc(fixture, 60)
        assert calc.status == "incomplete"
        assert "IF()" in (calc.unsupported or "")
        assert calc.value is None
        res = workbook_calculation_result(calc, item_label="row 60")
        assert res.status == "incomplete"
        assert res.proposed is None
        assert "IF()" in res.missing_dependency
        text = render_comparison("row 60", None, res)
        assert "NOT COMPUTED" in text and "IF()" in text
        assert "No partial result" in text

    def test_missing_parameter_names_the_exact_cell(self, fixture):
        """$AZ$1 has no value anywhere: the exact reference is named
        and offered as the live-read target."""
        from core.formula_engine import evaluate_reference

        book = fixture.book("BurrKing")
        calc = evaluate_reference(
            "BurrKing", "K61", book, fixture.provider(),
            row_of_interest=61,
            origin={"file": "bk.xlsx", "sheet": "BurrKing",
                    "row": "61", "output_cell": "K61",
                    "version": "fixturev1"})
        assert calc.status == "incomplete"
        assert "BurrKing!AZ1" in calc.missing
        assert ("BurrKing", "AZ1") in calc.missing_references

    def test_literal_sheet_has_no_calculation(self, fixture):
        """A sheet of typed values has no formula to reconstruct — the
        honest outcome (the lane reports the stored value as an
        observation instead)."""
        from core.formula_engine import evaluate_reference

        book = fixture.book("Tennsmith")
        calc = evaluate_reference(
            "Tennsmith", "E106", book, None, row_of_interest=106,
            origin={"file": "bk.xlsx", "sheet": "Tennsmith",
                    "row": "106", "output_cell": "E106",
                    "version": "fixturev1"})
        assert calc.status == "incomplete"
        assert "has no formula" in calc.missing

    def test_cache_substitution_is_flagged_not_silent(self, fixture):
        """When the sidecar loses a formula (the shared-formula
        dependent case) but a stored value exists, the value is used
        AND FLAGGED — never presented as reconstructed arithmetic."""
        from core.formula_engine import evaluate_reference
        from core.pricing_calculation import workbook_calculation_result

        book = fixture.book(
            "BurrKing",
            extra_values={"S25": "5215.7534125"},
            drop_formulas=("S25",))
        calc = evaluate_reference(
            "BurrKing", "E25", book, fixture.provider(),
            row_of_interest=25,
            origin={"file": "bk.xlsx", "sheet": "BurrKing",
                    "row": "25", "output_cell": "E25",
                    "version": "fixturev1"})
        assert calc.status == "computed"
        assert calc.value == Decimal("7409")
        assert "BurrKing!S25" in calc.cache_substituted
        res = workbook_calculation_result(calc, item_label="r25")
        assert res.verification["cache_substituted_cells"] == \
            ["BurrKing!S25"]
        text = render_comparison("r25", None, res)
        assert "STORED values" in text

    def test_result_record_carries_identity_and_dependencies(self, fixture):
        """The record retains workbook version, sheet, row, output cell
        and every dependency — not just sheet scope."""
        from core.pricing_calculation import workbook_calculation_result

        calc = self._calc(fixture, 25)
        res = workbook_calculation_result(
            calc, item_label="90703",
            authorized_by={"lesson_id": "L1", "version": "abc123"})
        rec = res.to_record()
        assert rec["workbook"]["file"] == "bk.xlsx"
        assert rec["workbook"]["sheet"] == "BurrKing"
        assert rec["workbook"]["row"] == "25"
        assert rec["workbook"]["output_cell"] == "E25"
        assert rec["workbook"]["version"] == "fixturev1"
        assert rec["workbook"]["authorized_by"]["lesson_id"] == "L1"
        roles = {d["role"] for d in rec["dependencies"]}
        assert roles == {"input", "reference", "intermediate"}


class TestWorkbookAuthorization:
    """Teaching authorizes WHEN a workbook calculation applies — the
    governance gate. Structural matching only."""

    def test_lesson_naming_file_and_sheet_authorizes(self):
        from core.pricing_calculation import authorized_workbook_basis

        lessons = [{
            "id": "L1",
            "lesson": ("For BurrKing machines, calculate the price from "
                       "the Consolidated Price List 2019.xlsx workbook, "
                       "BurrKing sheet.")}]
        auth = authorized_workbook_basis(
            lessons, "Consolidated Price List 2019.xlsx", "BurrKing")
        assert auth and auth["lesson_id"] == "L1"
        assert len(auth["version"]) == 12

    def test_file_alone_or_sheet_alone_does_not_authorize(self):
        from core.pricing_calculation import authorized_workbook_basis

        only_file = [{
            "id": "L2",
            "lesson": "Prices come from the Consolidated Price List "
                      "2019 workbook."}]
        assert authorized_workbook_basis(
            only_file, "Consolidated Price List 2019.xlsx",
            "BurrKing") is None
        only_sheet = [{
            "id": "L3",
            "lesson": "BurrKing items get the ladder treatment."}]
        assert authorized_workbook_basis(
            only_sheet, "Consolidated Price List 2019.xlsx",
            "BurrKing") is None

    def test_different_sheet_is_not_authorized(self):
        from core.pricing_calculation import authorized_workbook_basis

        lessons = [{
            "id": "L4",
            "lesson": ("Price Tennsmith rows from the Consolidated "
                       "Price List 2019 workbook Tennsmith sheet.")}]
        assert authorized_workbook_basis(
            lessons, "Consolidated Price List 2019.xlsx",
            "BurrKing") is None

    def test_underscore_and_space_forms_match(self):
        from core.pricing_calculation import authorized_workbook_basis

        lessons = [{
            "id": "L5",
            "lesson": "use consolidated_price_list_2019 for burrking"}]
        assert authorized_workbook_basis(
            lessons, "Consolidated Price List 2019.xlsx",
            "BurrKing") is not None


@pytest.fixture
def fake_catalog(tmp_path, monkeypatch):
    """A minimal parquet+sidecar catalog the lane can read, with
    columns at their TRUE letters (the grid maps by order): a
    BurrKing sheet (param cells in the AB column at their own rows,
    the row-25 inputs, the cached output) and an Exchange-Index
    sheet (H4 = 1.45) for the cross-sheet parameter; plus a
    Tennsmith sheet of typed literals."""
    import json

    import pandas as pd
    from openpyxl.utils import get_column_letter

    from core import pricing_calculation as pc

    d = tmp_path
    fx_ = _Fixture(d)

    def parquet(path, cells):
        # cells: {row: {letter: value}} — blanks elsewhere; all
        # values stored as strings (mixed int/'' breaks parquet,
        # and the grid reads Decimal from strings anyway).
        rows = sorted(cells)
        cols = [get_column_letter(i) for i in range(1, 29)]
        data = {c: [str(cells[r].get(c, "")) for r in rows]
                for c in cols}
        data["__sheet_row"] = rows
        pd.DataFrame(data).to_parquet(path)

    bk_parquet = d / "bk.parquet"
    parquet(bk_parquet, {
        1: {"AB": 0.675}, 2: {"AB": 0.72}, 8: {"AB": 1.45},
        11: {"AB": 1.03}, 15: {"AB": 150}, 36: {"AB": 1.1364},
        42: {"AB": 1.25},
        25: {"H": 4777, "N": 250, "P": "", "Q": "", "E": 7409}})
    (d / "bk.parquet.formulas.json").write_text(json.dumps(
        {"sheet": "BurrKing",
         "formulas": fx_.sidecar("BurrKing")}))
    xi_parquet = d / "xi.parquet"
    parquet(xi_parquet, {4: {"H": 1.45}})
    (d / "xi.parquet.formulas.json").write_text(
        json.dumps({"sheet": "Exchange-Index", "formulas": {}}))
    ts_parquet = d / "ts.parquet"
    parquet(ts_parquet, {106: {"A": "GSL48-16", "E": 14318}})
    (d / "ts.parquet.formulas.json").write_text(
        json.dumps({"sheet": "Tennsmith", "formulas": {}}))

    entries = {
        "burrking": {
            "entity_name": "BurrKing",
            "parquet_path": str(bk_parquet),
            "content_hash": "fakehash000001",
            "source": "upload",
            "external_id": "sha1:x",
            "source_modified_at": None},
        "exchange-index": {
            "entity_name": "Exchange-Index",
            "parquet_path": str(xi_parquet),
            "content_hash": "fakehash000001",
            "source": "upload",
            "external_id": "sha1:x",
            "source_modified_at": None},
        "tennsmith": {
            "entity_name": "Tennsmith",
            "parquet_path": str(ts_parquet),
            "content_hash": "fakehash000002",
            "source": "upload",
            "external_id": "sha1:y",
            "source_modified_at": None}}

    class _FakeBooks:
        def __init__(self, file_name, workspace_id, prefer_hash=""):
            self._books = {}
            self.live_grid = None

        def entry_for(self, sheet_name):
            return entries.get(
                " ".join(str(sheet_name).lower().split()))

        def problem_for(self, sheet_name):
            return None

        def _load_entries(self):
            return list(entries.values())

        def provider(self, sheet_name):
            from core.formula_engine import (CellBook,
                                             sheet_grid_from_parquet)
            from core.sheet_dataset_service import \
                load_formulas_for_parquet

            key = " ".join(str(sheet_name).lower().split())
            if key not in entries:
                return None
            values, empty = sheet_grid_from_parquet(
                entries[key]["parquet_path"])
            return CellBook(
                entries[key]["entity_name"],
                load_formulas_for_parquet(
                    entries[key]["parquet_path"]), values, empty)

    monkeypatch.setattr(pc, "_FileSheetBooks", _FakeBooks)
    return entries


class TestWorkbookLane:
    """The planner lane's workbook entry — authorization refusal and
    the literal-sheet observation, with the catalog faked (no DB)."""

    @pytest.mark.asyncio
    async def test_refuses_without_teaching(self, fake_catalog,
                                            monkeypatch):
        from core import pricing_calculation as pc

        monkeypatch.setattr(pc, "_workspace_lessons",
                            lambda *a, **k: [])
        block = await pc.calculate_workbook_from_query(
            "calculate price for bk.xlsx BurrKing row 25 cell E25",
            "u1", None)
        assert block and "NOT AUTHORIZED" in block
        assert "teaching authorizes" in block

    @pytest.mark.asyncio
    async def test_authorized_request_completes(self, fake_catalog,
                                                monkeypatch):
        from core import pricing_calculation as pc

        monkeypatch.setattr(pc, "_workspace_lessons", lambda *a, **k: [{
            "id": "L1",
            "lesson": "price burrking rows from bk.xlsx"}])
        block = await pc.calculate_workbook_from_query(
            "calculate price for bk.xlsx BurrKing row 25 cell E25",
            "u1", None)
        assert block
        assert "CAD 7409" in block
        assert "authorized by teaching" in block
        assert "workbook version fakehash000" in block

    @pytest.mark.asyncio
    async def test_literal_sheet_is_stored_value_not_computed(
            self, fake_catalog, monkeypatch, tmp_path):
        """The stored-value case renders unmistakably as STORED VALUE —
        NOT COMPUTED. The literal status is ESTABLISHED by workbook
        metadata (no <f> on the cell), which arrives through the live
        read — durable-only state cannot claim it."""
        from core import pricing_calculation as pc

        monkeypatch.setattr(pc, "_workspace_lessons", lambda *a, **k: [{
            "id": "L2",
            "lesson": "tennsmith prices come from bk.xlsx tennsmith"}])
        # make the source downloadable and serve the real fixture bytes
        fake_catalog["tennsmith"]["source"] = "zoho_workdrive"
        fake_catalog["tennsmith"]["external_id"] = "wd-1"
        fx_ = _Fixture(tmp_path)
        with open(fx_.path, "rb") as fh:
            content = fh.read()

        async def _fake_download(user_id, ext_id, workspace_id=None):
            return content

        monkeypatch.setattr(pc, "_download_workbook_bytes",
                            _fake_download)
        import core.formula_engine as fe
        monkeypatch.setattr(fe, "verify_with_formulas_engine",
                            lambda *a, **k: None)
        block = await pc.calculate_workbook_from_query(
            "calculate price for bk.xlsx Tennsmith row 106 cell E106",
            "u1", None)
        assert block and "STORED VALUE, NOT COMPUTED" in block
        assert "14318" in block
        assert "cannot satisfy a calculation obligation" in block
        assert "no formula was evaluated" in block

    def test_workbook_query_pattern(self):
        from core.pricing_calculation import _WB_QUERY_RE

        m = _WB_QUERY_RE.match(
            "calculate price for Consolidated Price List 2019.xlsx "
            "BurrKing row 25 cell E25 item=90703 currency=CAD")
        assert m
        assert m.group("file") == (
            "Consolidated Price List 2019.xlsx")
        assert m.group("sheet") == "BurrKing"
        assert m.group("row") == "25" and m.group("cell") == "E25"


@pytest.mark.skipif(_SKIP_LIVE, reason="live 2019 dataset not present")
class TestLiveWorkbookData:
    """The REAL 2019 workbook's materialized sidecar+frame: the
    demonstrated row reconstructed byte-exact against the sheet's own
    cached output, with the live-read overlays the lane performs."""

    @staticmethod
    def _load():
        import json

        from core.formula_engine import sheet_grid_from_parquet

        base = _LIVE_2019 + "/"
        formulas = json.load(open(
            base + "zoho_workdrive_consolidated_price_list_2019__"
                   "burrking.parquet.formulas.json"))["formulas"]
        values, empty = sheet_grid_from_parquet(
            base + "zoho_workdrive_consolidated_price_list_2019__"
                   "burrking.parquet")
        return formulas, values, empty

    @staticmethod
    def _live_overlays():
        """The cells the live read supplies: the AB1/AB2 parameters
        (Excel rows 1-2, consumed as the frame's headers) and the
        three shared-formula dependents the sidecar lost (E25, I25,
        S25 — their neighbors carry bodies)."""
        return ({"AB1": "0.675", "AB2": "0.72"},
                {"E25": "=ROUNDUP(W25,0)", "I25": "=SUM(H25*1)",
                 "S25": "=M25+N25+P25+Q25+R25"})

    def _provider(self):
        import json

        from core.formula_engine import CellBook, sheet_grid_from_parquet

        base = _LIVE_2019 + "/"
        xi_f = json.load(open(
            base + "zoho_workdrive_consolidated_price_list_2019__"
                   "exchange_index.parquet.formulas.json"))["formulas"]
        xi_v, xi_e = sheet_grid_from_parquet(
            base + "zoho_workdrive_consolidated_price_list_2019__"
                   "exchange_index.parquet")
        xi = CellBook("Exchange-Index", xi_f, xi_v, xi_e)
        xi.overlay({"H4": "1.45"}, "live_read")
        return lambda name: (
            xi if name.strip().lower() == "exchange-index" else None)

    def test_demonstrated_row_byte_exact(self):
        from core.formula_engine import CellBook, evaluate_reference
        from core.pricing_calculation import workbook_calculation_result

        formulas, values, empty = self._load()
        live_vals, live_formulas = self._live_overlays()
        book = CellBook("BurrKing", formulas, values, empty)
        book.overlay(live_vals, "live_read", formulas=live_formulas)
        calc = evaluate_reference(
            "BurrKing", "E25", book, self._provider(),
            row_of_interest=25, cached_value=values.get("E25"),
            origin={"file": "Consolidated Price List 2019.xlsx",
                    "sheet": "BurrKing", "row": "25",
                    "output_cell": "E25", "version": "ce61dd3d40ca"})
        assert calc.status == "computed", calc.missing
        # byte-exact against the sheet's own computed value
        assert calc.value == Decimal("7409")
        assert calc.cached_value == "7409"
        res = workbook_calculation_result(calc, item_label="90703")
        assert res.verification["matches_cached"] is True
        assert res.proposed.amount == Decimal("7409")
        assert not calc.cache_substituted
        deps = {(d.sheet, d.cell) for d in calc.dependencies}
        assert ("Exchange-Index", "H4") in deps
        assert ("BurrKing", "AB8") in deps

    def test_without_live_read_the_output_is_never_completed(self):
        """No live overlays: the sidecar lost E25's formula and durable
        state has no metadata to establish the cell — the result is
        INCOMPLETE (a live read decides), NEVER a completed calculation
        from the stored cache. A lost INTERMEDIATE (S25) under a
        surviving output formula still computes, with S25 flagged."""
        from core.formula_engine import CellBook, evaluate_reference
        from core.pricing_calculation import workbook_calculation_result

        formulas, values, empty = self._load()
        vals = dict(values)
        vals.update({"AB1": "0.675", "AB11": "1.03", "AB15": "150",
                     "AB36": "1.1364", "AB42": "1.25"})  # params, but
        # NO live formulas for E25/I25/S25
        book = CellBook("BurrKing", formulas, vals, empty)
        calc = evaluate_reference(
            "BurrKing", "E25", book, self._provider(),
            row_of_interest=25, cached_value=values.get("E25"),
            origin={"file": "Consolidated Price List 2019.xlsx",
                    "sheet": "BurrKing", "row": "25",
                    "output_cell": "E25", "version": "ce61dd3d40ca"})
        assert calc.status == "incomplete"
        assert calc.value is None and calc.steps == []
        assert "no metadata to establish" in calc.missing
        res = workbook_calculation_result(calc, item_label="90703")
        assert res.status == "incomplete"
        assert res.proposed is None
        assert "7409" not in str(res.verification)  # no self-comparison
        # A lost INTERMEDIATE (S25) under a surviving output formula:
        # the chain walks, S25's stored value stands in for arithmetic
        # we do not have — flagged, and the ROUNDUP step DOES run. The
        # cached-output cross-check then marks itself NOT fully
        # independent (a substituted operand appears on both sides).
        book2 = CellBook("BurrKing", formulas, vals, empty)
        book2.overlay(
            {}, "live_read",
            formulas={"E25": "=ROUNDUP(W25,0)", "I25": "=SUM(H25*1)"})
        calc2 = evaluate_reference(
            "BurrKing", "E25", book2, self._provider(),
            row_of_interest=25, cached_value=values.get("E25"),
            origin={"file": "Consolidated Price List 2019.xlsx",
                    "sheet": "BurrKing", "row": "25",
                    "output_cell": "E25", "version": "ce61dd3d40ca"})
        assert calc2.status == "computed"
        assert calc2.value == Decimal("7409")
        assert "BurrKing!S25" in calc2.cache_substituted
        assert any(s["op"] == "round_up" for s in calc2.steps)
        res2 = workbook_calculation_result(calc2, item_label="90703")
        assert res2.verification["matches_cached"] is True
        assert res2.verification["fully_independent"] is False

    def test_row_without_frame_param_blocks_with_exact_name(self):
        """AB1/AB2 (Excel rows 1-2, consumed as the frame's headers)
        are NOT in durable state: without them the calculation is
        INCOMPLETE naming exactly the cell — never a guessed
        discount."""
        from core.formula_engine import CellBook, evaluate_reference

        formulas, values, empty = self._load()
        book = CellBook("BurrKing", formulas, dict(values), empty)
        calc = evaluate_reference(
            "BurrKing", "E225", book, self._provider(),
            row_of_interest=225, cached_value=values.get("E225"),
            origin={"file": "Consolidated Price List 2019.xlsx",
                    "sheet": "BurrKing", "row": "225",
                    "output_cell": "E225", "version": "ce61dd3d40ca"})
        assert calc.status == "incomplete"
        assert "BurrKing!AB1" in calc.missing
        assert ("BurrKing", "AB1") in calc.missing_references

    def test_other_parameter_rows_byte_exact(self):
        """The REAL workbook's other parameter bindings, byte-exact
        against its own cached outputs (hand-checked first): row 225
        binds $AB$18=423 and $AB$41=1.1765 (-> 25010); row 325 binds
        $AB$2=0.72 with an EMPTY electrical cell (-> 1300). Only AB1 /
        AB2 come from outside the frame."""
        from core.formula_engine import CellBook, evaluate_reference

        formulas, values, empty = self._load()
        for row, extra, out_cell, expected in (
                (225, {"AB1": "0.675"}, "E225", "25010"),
                (325, {"AB2": "0.72"}, "E325", "1300")):
            book = CellBook("BurrKing", formulas, values, empty)
            book.overlay(extra, "live_read")
            calc = evaluate_reference(
                "BurrKing", out_cell, book, self._provider(),
                row_of_interest=row, cached_value=values.get(out_cell),
                origin={"file": "Consolidated Price List 2019.xlsx",
                        "sheet": "BurrKing", "row": str(row),
                        "output_cell": out_cell,
                        "version": "ce61dd3d40ca"})
            assert calc.status == "computed", calc.missing
            assert calc.value == Decimal(expected), (row, calc.value)
            assert calc.cached_value == expected
        # row 225 bound ITS parameters, not row 25's
        book = CellBook("BurrKing", formulas, values, empty)
        book.overlay({"AB1": "0.675"}, "live_read")
        calc = evaluate_reference(
            "BurrKing", "E225", book, self._provider(),
            row_of_interest=225,
            origin={"file": "Consolidated Price List 2019.xlsx",
                    "sheet": "BurrKing", "row": "225",
                    "output_cell": "E225", "version": "ce61dd3d40ca"})
        deps = {f"{d.sheet}!{d.cell}" for d in calc.dependencies}
        assert "BurrKing!AB18" in deps and "BurrKing!AB41" in deps


class TestRound71Contracts:
    """The owner's closeout contracts: structural result types on the
    JOB (a stored value cannot satisfy a calculation obligation),
    ambiguous-version refusal, the named-input expression lane, and
    the lane's durable job recording."""

    def _lifecycle(self, tmp_path):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from core.models import GoalObjective, GoalRun, \
            TaskOperationRecord
        from core.goals.goal_run_service import GoalRunService
        from core.goals.goal_service import GoalService
        from core.task_lifecycle import TaskLifecycle
        engine = create_engine(f"sqlite:///{tmp_path}/r71.db")
        for t in (GoalObjective.__table__, GoalRun.__table__,
                  TaskOperationRecord.__table__):
            t.create(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        return TaskLifecycle(
            GoalRunService(workspace_id="ws", tenant_id="t",
                           session_factory=factory),
            GoalService(workspace_id="ws", tenant_id="t",
                        session_factory=factory))

    def test_stored_value_cannot_satisfy_calculation_obligation(
            self, tmp_path):
        """record_calculation maps a stored-value observation to a
        WAITING operation with a question that says the obligation is
        NOT satisfied — never 'applied'."""
        from core.formula_engine import CellBook, evaluate_reference
        from core.pricing_calculation import (record_calculation,
                                              workbook_calculation_result)
        from core.task_lifecycle import (begin_retrieval_turn,
                                         next_unfinished_work)
        lc = self._lifecycle(tmp_path)
        run_id, _ = begin_retrieval_turn(
            lc, {"id": "s1"}, "conv-r71", "verify", "e1")
        book = CellBook("Tennsmith", {}, {"E106": "14318"},
                        formula_cells=set())
        calc = evaluate_reference(
            "Tennsmith", "E106", book, None, row_of_interest=106,
            origin={"file": "bk.xlsx", "sheet": "Tennsmith",
                    "row": "106", "output_cell": "E106",
                    "version": "v1"})
        assert calc.status == "stored_value"
        res = workbook_calculation_result(calc, item_label="GSL48-16")
        assert res.status == "stored_value"
        assert res.proposed is None
        assert res.verification["stored_value"] == "14318"
        # no self-comparison is offered as verification
        assert "matches_cached" not in res.verification
        op = record_calculation(lc, run_id, "GSL48-16", res)
        rec = lc.get_task(run_id)
        calc_op = next(o for o in rec["operations"]
                       if o["operation_id"] == op["operation_id"])
        assert calc_op["status"] == "waiting"  # NOT applied
        assert calc_op["calculation"]["status"] == "stored_value"
        work = next_unfinished_work(rec)
        q = next(a for a in work["actions"]
                 if "cannot be satisfied" in str(a.get("question")))
        assert "STORED VALUE" in q["question"]

    def test_clean_computation_verification_is_independent(self):
        from core.formula_engine import CellBook, evaluate_reference
        from core.pricing_calculation import workbook_calculation_result
        book = CellBook("Main", {"B2": "=A2*2"}, {"A2": "10"})
        calc = evaluate_reference("Main", "B2", book, None,
                                  row_of_interest=2,
                                  cached_value="20")
        assert calc.status == "computed"
        assert calc.cache_substituted == []
        res = workbook_calculation_result(calc, item_label="x")
        assert res.verification["matches_cached"] is True
        assert res.verification["fully_independent"] is True

    @pytest.mark.asyncio
    async def test_expression_lane_computes_named_inputs(self):
        from core.pricing_calculation import calculate_expression_from_query

        block = await calculate_expression_from_query(
            "calculate expression ROUNDUP(hours*rate + materials, 0) "
            "with hours=17.5 rate=150 materials=0", "u1", None)
        assert block and "2625" in block
        assert "hours=17.5" in block and "rate=150" in block
        assert "formula engine" in block

    @pytest.mark.asyncio
    async def test_expression_lane_missing_input_named(self):
        from core.pricing_calculation import calculate_expression_from_query

        block = await calculate_expression_from_query(
            "calculate expression demand*lead_time + safety_stock "
            "with demand=40 lead_time=3", "u1", None)
        assert block and "NOT COMPUTED" in block
        assert "'safety_stock'" in block

    @pytest.mark.asyncio
    async def test_ambiguous_version_refused(self, fake_catalog,
                                             monkeypatch):
        """Two ACTIVE versions of one sheet: the lane refuses and
        names the candidates — never chooses by query order."""
        from core import pricing_calculation as pc

        fake_catalog["burrking2"] = dict(fake_catalog["burrking"],
                                         content_hash="otherhash99")
        # rebuild entries through a books class that exposes both
        base_entries = dict(fake_catalog)

        class _AmbiguousBooks(pc._FileSheetBooks):
            def _load_entries(self):
                return [base_entries["burrking"],
                        base_entries["burrking2"]]

            def entry_for(self, sheet_name):
                self._load_entries()
                return None

            def problem_for(self, sheet_name):
                return ("multiple active workbook versions for sheet "
                        "'BurrKing' (fakehash000001, otherhash99)")

        monkeypatch.setattr(pc, "_FileSheetBooks", _AmbiguousBooks)
        monkeypatch.setattr(pc, "_workspace_lessons", lambda *a, **k: [{
            "id": "L1", "lesson": "price burrking rows from bk.xlsx"}])
        block = await pc.calculate_workbook_from_query(
            "calculate price for bk.xlsx BurrKing row 25 cell E25",
            "u1", None)
        assert block and "AMBIGUOUS WORKBOOK VERSION" in block
        assert "no calculation was run" in block

    @pytest.mark.asyncio
    async def test_lane_records_calculation_on_active_job(
            self, fake_catalog, monkeypatch):
        """The lane persists onto the conversation's ACTIVE job run:
        identity, inputs, dependencies, result type and provenance."""
        from core import pricing_calculation as pc

        monkeypatch.setattr(pc, "_workspace_lessons", lambda *a, **k: [{
            "id": "L1", "lesson": "price burrking rows from bk.xlsx"}])

        recorded = {}

        class _FakeLifecycle:
            def find_active_task(self, conv):
                recorded["conversation"] = conv
                return {"run_id": "run-xyz"}

            def get_task(self, run_id):
                return None

        import types
        fake_lc = _FakeLifecycle()
        monkeypatch.setattr(
            pc, "record_calculation",
            lambda lifecycle, run_id, item, result:
                recorded.update(run_id=run_id, item=item,
                                status=result.status,
                                policy=result.policy_id,
                                deps=len(result.dependencies),
                                authorized=(
                                    result.workbook.get(
                                        "authorized_by") or {}).get(
                                    "lesson_id")))
        import integrations.chat_orchestrator as orch
        monkeypatch.setattr(
            orch, "_task_lifecycle_for",
            lambda tenant, ws: fake_lc)
        block = await pc.calculate_workbook_from_query(
            "calculate price for bk.xlsx BurrKing row 25 cell E25",
            "u1", None, conversation_id="conv-9")
        assert block and "CAD 7409" in block
        assert recorded["conversation"] == "conv-9"
        assert recorded["run_id"] == "run-xyz"
        assert recorded["status"] == "succeeded"
        assert recorded["policy"] == "workbook:BurrKing!E25"
        assert recorded["deps"] >= 15
        assert recorded["authorized"] == "L1"
