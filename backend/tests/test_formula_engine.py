# -*- coding: utf-8 -*-
"""The general formula engine (round 70): one supported formula
language, two input formats (references and explicit named inputs),
Decimal determinism, precise unsupported/missing results — and NO
business concepts. Expected values are hand-derived or produced by the
independent `formulas` engine; they are never echoes of the
implementation."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from decimal import Decimal

import pytest

from core.formula_engine import (
    CellBook, FormulaInputError, evaluate_expression, evaluate_reference,
    excel_round,
)


class TestFormulaLanguage:
    """The explicit supported language — arithmetic, functions,
    precision, rounding — over explicit named inputs."""

    def test_precedence_and_constants_as_decimals(self):
        r = evaluate_expression("2 + 3 * 4")
        assert r.status == "computed"
        assert r.value == Decimal("14")
        # a decimal literal stays exact, never float-noised
        r = evaluate_expression("0.1 + 0.2")
        assert r.value == Decimal("0.3")

    def test_division_precision(self):
        r = evaluate_expression("10 / 4")
        assert r.value == Decimal("2.5")
        r = evaluate_expression("1 / 3")
        assert str(r.value).startswith("0.3333")

    def test_integer_power_supported_noninteger_refused(self):
        assert evaluate_expression("2 ^ 10").value == Decimal("1024")
        r = evaluate_expression("2 ^ 0.5")
        assert r.status == "incomplete"
        assert "exponent" in r.unsupported

    def test_functions(self):
        assert evaluate_expression("ROUNDUP(1.001, 0)").value == \
            Decimal("2")
        assert evaluate_expression("ROUNDDOWN(1.999, 0)").value == \
            Decimal("1")
        assert evaluate_expression("ROUND(2.5, 0)").value == Decimal("3")
        assert evaluate_expression("ROUND(-2.5, 0)").value == \
            Decimal("-3")   # half away from zero, like the spreadsheet
        assert evaluate_expression("INT(-1.5)").value == Decimal("-2")
        assert evaluate_expression("ABS(-4)").value == Decimal("4")
        assert evaluate_expression("MIN(3, 1, 2)").value == Decimal("1")
        assert evaluate_expression("MAX(3, 1, 2)").value == Decimal("3")
        assert evaluate_expression("SUM(1, 2, 3)").value == Decimal("6")

    def test_rounding_boundaries_and_signs(self):
        # exactly on an integer: ROUNDUP is a no-op
        assert excel_round(Decimal("675"), 0, "up") == Decimal("675")
        # just above: bumps
        assert excel_round(Decimal("675.000001"), 0, "up") == \
            Decimal("676")
        # away from zero for negatives
        assert excel_round(Decimal("-675.1"), 0, "up") == Decimal("-676")
        assert excel_round(Decimal("-675.1"), 0, "down") == \
            Decimal("-675")
        # decimal places
        assert excel_round(Decimal("67.5027"), 2, "up") == \
            Decimal("67.51")

    def test_missing_input_named_precisely(self):
        r = evaluate_expression("hours * rate", {"hours": 3})
        assert r.status == "incomplete"
        assert "'rate'" in r.missing
        assert r.value is None

    def test_unsupported_function_named_precisely(self):
        r = evaluate_expression('IF(x > 1, 2, 3)', {"x": 2})
        assert r.status == "incomplete"
        assert "IF()" in r.unsupported
        assert "not in the supported function set" in r.unsupported
        r = evaluate_expression("VLOOKUP(a, b, c)", {"a": 1})
        assert "VLOOKUP()" in r.unsupported

    def test_unsupported_syntax_named(self):
        r = evaluate_expression("SUM(A1:A9)")
        assert r.status == "incomplete"
        assert "syntax outside the supported language" in r.unsupported
        r = evaluate_expression("5%")
        assert r.status == "incomplete"

    def test_non_numeric_input_is_a_precise_result(self):
        r = evaluate_expression("x + 1", {"x": "soon"})
        assert r.status == "incomplete"
        assert "not numeric" in r.unsupported

    def test_division_by_zero_is_a_precise_result(self):
        r = evaluate_expression("10 / zero", {"zero": 0})
        assert r.status == "incomplete"
        assert "divides by zero" in r.unsupported

    def test_unit_annotation_recorded_not_interpreted(self):
        r = evaluate_expression(
            "hours * rate", {"hours": 17.5, "rate": 150},
            units={"hours": "hour", "rate": "CAD/hour"},
            output_unit="CAD")
        assert r.status == "computed"
        assert r.value == Decimal("2625.0")
        assert r.unit == "CAD"
        by_name = {d.cell: d for d in r.dependencies}
        assert by_name["hours"].unit == "hour"
        assert by_name["rate"].unit == "CAD/hour"

    def test_explicit_input_shadows_cell_shaped_name(self):
        # 'H1' looks like a cell reference; an explicit input wins.
        r = evaluate_expression("H1 * 2", {"H1": 21})
        assert r.status == "computed"
        assert r.value == Decimal("42")

    def test_steps_replay_the_operations(self):
        r = evaluate_expression(
            "ROUNDUP((a + b) * 2, 0)", {"a": 1.2, "b": 1.3})
        assert [s["op"] for s in r.steps] == ["add", "multiply",
                                              "round_up"]
        assert r.value == Decimal("5")  # hand: (1.2+1.3)*2 = 5 exactly


class TestNonPricingFormulas:
    """The owner's materially-different NON-pricing formulas through
    the SAME execution path the pricing application uses — the engine
    has no concept of price, vendor or freight; these are just
    formulas with named inputs."""

    def test_service_estimate(self):
        # 17.5 hours at 150/hr plus 0 materials, rounded up whole
        r = evaluate_expression(
            "ROUNDUP(hours * rate + materials, 0)",
            {"hours": 17.5, "rate": 150, "materials": 0},
            units={"hours": "hour", "rate": "CAD/hour",
                   "materials": "CAD"},
            output_unit="CAD")
        assert r.status == "computed"
        assert r.value == Decimal("2625")

    def test_inventory_reorder_point(self):
        # demand x lead time + safety stock
        r = evaluate_expression(
            "demand * lead_time + safety_stock",
            {"demand": 40, "lead_time": 3, "safety_stock": 120},
            output_unit="units")
        assert r.status == "computed"
        assert r.value == Decimal("240")

    def test_operations_effective_capacity(self):
        # nameplate capacity x utilization percent
        r = evaluate_expression(
            "capacity * utilization / 100",
            {"capacity": 400, "utilization": 82.5},
            output_unit="parts/hour")
        assert r.status == "computed"
        assert r.value == Decimal("330")

    def test_same_formula_through_the_reference_format(self):
        """One execution path, both input formats: the SAME service
        estimate as cell references in a workbook, cross-checked
        against the independent `formulas` engine."""
        import tempfile

        from openpyxl import Workbook

        from core.formula_engine import verify_with_formulas_engine, \
            workbook_grid_from_bytes

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "estimates.xlsx")
            wb = Workbook()
            ws = wb.active
            ws.title = "Estimates"
            ws["A1"] = 17.5   # hours
            ws["B1"] = 150    # rate
            ws["C1"] = 0      # materials
            ws["D1"] = "=ROUNDUP(A1*B1+C1, 0)"
            wb.save(path)
            with open(path, "rb") as fh:
                content = fh.read()
            grid = workbook_grid_from_bytes(content)
            d = grid["estimates"]
            book = CellBook("Estimates", d["formulas"], d["values"])
            r = evaluate_reference("Estimates", "D1", book,
                                   row_of_interest=1)
            assert r.status == "computed", r.missing
            assert r.value == Decimal("2625")
            deps = {x.cell: x for x in r.dependencies}
            assert deps["A1"].role == "input"
            assert deps["D1"].role == "intermediate"
            oracle = verify_with_formulas_engine(
                content, "Estimates", "D1")
            assert oracle is not None
            assert abs(float(oracle) - 2625.0) < 0.01


class TestReferenceFormat:
    """The reference (workbook) input format: cross-sheet resolution,
    blank operands, lost-formula flagging, cycles, fail-closed
    behavior."""

    def _book(self):
        return CellBook(
            "Main",
            {"B2": "=A2*$P$1", "C2": "=B2+'Side'!A1",
             "D2": "=C2+X2", "F2": "=F2+1", "G2": "=SUM(H2:J2)"},
            {"A2": "10", "X2": ""},
            empty={"X2"})

    def test_cross_sheet_and_blank_operand(self):
        book = self._book()
        book.overlay({"P1": "2"}, "frame")
        side = CellBook("Side", {}, {"A1": "5"})
        provider = lambda name: (  # noqa: E731
            side if name.lower() == "side" else None)
        r = evaluate_reference("Main", "D2", book, provider,
                               row_of_interest=2)
        # 10*2 + 5 + blank(0) = 25
        assert r.status == "computed"
        assert r.value == Decimal("25")
        by = {(d.sheet, d.cell): d for d in r.dependencies}
        assert by[("Side", "A1")].role == "reference"
        assert by[("Main", "X2")].value == "0"
        assert "blank" in (by[("Main", "X2")].note or "").lower()

    def test_missing_reference_named(self):
        r = evaluate_reference("Main", "B2", self._book(), None,
                               row_of_interest=2)
        # $P$1 has no value, no formula, not blank
        assert r.status == "incomplete"
        assert "P1" in r.missing
        assert ("Main", "P1") in r.missing_references

    def test_unresolvable_cross_sheet_named(self):
        book = self._book()
        book.overlay({"P1": "2"}, "frame")
        r = evaluate_reference("Main", "C2", book, None,
                               row_of_interest=2)
        assert r.status == "incomplete"
        assert "Side" in r.missing

    def test_circular_reference_refused(self):
        r = evaluate_reference("Main", "F2", self._book(), None,
                               row_of_interest=2)
        assert r.status == "incomplete"
        assert "circular" in r.unsupported

    def test_range_syntax_unsupported(self):
        r = evaluate_reference("Main", "G2", self._book(), None,
                               row_of_interest=2)
        assert r.status == "incomplete"
        assert "SUM(H2:J2)" in r.unsupported

    def test_output_result_types_are_structural(self):
        """A missing OUTPUT formula never yields a computed result:
        metadata decides between incomplete (formula cell, body
        missing), stored_value (established literal) and incomplete
        (no metadata — a live read decides)."""
        # metadata says formula cell, body unavailable -> INCOMPLETE
        book = CellBook("Main", {}, {"B2": "20"}, empty=set(),
                        formula_cells={"B2"})
        r = evaluate_reference("Main", "B2", book, None,
                               row_of_interest=2)
        assert r.status == "incomplete"
        assert "formula cell" in r.missing
        assert r.value is None and r.steps == []
        # metadata says literal -> STORED VALUE observation, no steps,
        # no arithmetic claimed
        book = CellBook("Main", {"B3": "=A3*2"}, {"A2": "10", "B2": "20"},
                        empty=set(), formula_cells={"B3"})
        r = evaluate_reference("Main", "B2", book, None,
                               row_of_interest=2)
        assert r.status == "stored_value"
        assert r.value == Decimal("20")
        assert r.steps == []
        assert r.dependencies[0].note and \
            "not computed" in r.dependencies[0].note
        # no metadata at all -> INCOMPLETE (never a completed
        # calculation from the cache)
        book = CellBook("Main", {"B3": "=A3*2"}, {"A2": "10", "B2": "20"},
                        empty=set())
        r = evaluate_reference("Main", "B2", book, None,
                               row_of_interest=2)
        assert r.status == "incomplete"
        assert "no metadata to establish" in r.missing

    def test_literal_cell_has_no_calculation_and_inputs_role_in_chain(
            self):
        # A cell with no formula anywhere in its column is a typed
        # literal: evaluate_reference honestly reports there is no
        # calculation for it (the application layer surfaces the stored
        # value as an observation instead).
        book = CellBook("Main", {}, {"A2": "4777"}, empty=set())
        r = evaluate_reference("Main", "A2", book, None,
                               row_of_interest=2)
        assert r.status == "incomplete"
        assert "has no formula" in r.missing
        # ...but as an OPERAND of a formula, the same cell is an input
        book2 = CellBook("Main", {"B2": "=A2*2"}, {"A2": "4777"})
        r2 = evaluate_reference("Main", "B2", book2, None,
                                row_of_interest=2)
        assert r2.status == "computed"
        assert r2.value == Decimal("9554")
        by = {d.cell: d for d in r2.dependencies}
        assert by["A2"].role == "input"
        assert r2.cache_substituted == []

    def test_non_numeric_cell_operand_is_precise_result(self):
        book = CellBook("Main", {"B2": "=A2*2"}, {"A2": "n/a"})
        r = evaluate_reference("Main", "B2", book, None,
                               row_of_interest=2)
        assert r.status == "incomplete"
        assert "non-numeric" in r.unsupported

    def test_origin_recorded_verbatim(self):
        r = evaluate_expression(
            "1 + 1", origin={"source": "lesson:L9", "version": "v3"})
        assert r.origin == {"source": "lesson:L9", "version": "v3"}


class TestSharedFormulaTranslation:
    """The raw-XML reader's shared-formula expansion: a dependent cell
    evaluates the master's formula shifted by its offset (the package's
    own declaration — Excel semantics, not inference)."""

    def test_relative_shift_and_absolute_pin(self):
        from core.formula_engine import _translate_shared_formula

        # master at E24: =ROUNDUP(W24,0) with $-pinned W
        out = _translate_shared_formula(
            "E24", "=ROUNDUP($W$24,0)", "E25")
        assert out == "=ROUNDUP($W$24,0)"      # absolute stays
        out = _translate_shared_formula(
            "E24", "=ROUNDUP(W24,0)", "E25")
        assert out == "=ROUNDUP(W25,0)"        # relative shifts
        out = _translate_shared_formula(
            "K25", "=SUM(I25*$AB$1)", "K226")
        assert out == "=SUM(I226*$AB$1)"       # row shifts, $AB$1 pins
        out = _translate_shared_formula(
            "S25", "=M25+N25+P25+Q25+R25", "S226")
        assert out == "=M226+N226+P226+Q226+R226"

    def test_column_component_shifts_too(self):
        from core.formula_engine import _translate_shared_formula

        out = _translate_shared_formula(
            "B2", "=A2*2", "C2")
        assert out == "=B2*2"

    def test_offsheet_left_alone(self):
        from core.formula_engine import _translate_shared_formula

        # A1 referenced from a master at B1 -> dependent A0 is invalid;
        # the token stays untouched rather than inventing an address.
        out = _translate_shared_formula("B1", "=A1+1", "A1")
        assert out == "=A1+1"

    def test_raw_xml_grid_expands_shared_dependents(self, tmp_path):
        """A package whose E-column master carries the body and whose
        dependents are bodyless shared cells yields per-row formulas
        through the raw-XML fallback (values AND formulas)."""
        import zipfile
        from xml.etree.ElementTree import Element, SubElement, tostring

        NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

        def _sheet_xml():
            root = Element(f"{{{NS}}}worksheet")
            sd = SubElement(root, f"{{{NS}}}sheetData")
            r = SubElement(sd, f"{{{NS}}}row", {"r": "24"})
            for ref, val in (("W24", "10.4"), ("E24", None)):
                c = SubElement(r, f"{{{NS}}}c", {"r": ref})
                if ref == "E24":
                    f_el = SubElement(c, f"{{{NS}}}f",
                                      {"t": "shared", "si": "7",
                                       "ref": "E24:E26"})
                    f_el.text = "ROUNDUP(W24,0)"
                else:
                    v = SubElement(c, f"{{{NS}}}v")
                    v.text = val
            r25 = SubElement(sd, f"{{{NS}}}row", {"r": "25"})
            w25 = SubElement(r25, f"{{{NS}}}c", {"r": "W25"})
            v25 = SubElement(w25, f"{{{NS}}}v")
            v25.text = "7408.9777"
            e25 = SubElement(r25, f"{{{NS}}}c", {"r": "E25"})
            SubElement(e25, f"{{{NS}}}f",
                       {"t": "shared", "si": "7"})
            v = SubElement(e25, f"{{{NS}}}v")
            v.text = "7409"
            return tostring(root, xml_declaration=True,
                            encoding="UTF-8")

        path = tmp_path / "shared.xlsx"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr(
                "[Content_Types].xml",
                '<?xml version="1.0"?><Types xmlns="http://schemas.'
                'openxmlformats.org/package/2006/content-types"/>')
            zf.writestr("xl/workbook.xml", (
                '<?xml version="1.0"?><workbook xmlns="http://schemas.'
                'openxmlformats.org/spreadsheetml/2006/main" xmlns:r="'
                'http://schemas.openxmlformats.org/officeDocument/2006/'
                'relationships"><sheets><sheet name="Main" r:id="rId1"/>'
                "</sheets></workbook>"))
            zf.writestr("xl/_rels/workbook.xml.rels", (
                '<?xml version="1.0"?><Relationships xmlns="http://'
                'schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.'
                'openxmlformats.org/officeDocument/2006/relationships/'
                'worksheet" Target="worksheets/sheet1.xml"/></Relationships>'))
            zf.writestr("xl/worksheets/sheet1.xml", _sheet_xml())

        from core.formula_engine import CellBook, _raw_xml_grid, \
            evaluate_reference

        grid = _raw_xml_grid(open(path, "rb").read())
        d = grid["main"]
        assert d["formulas"]["E25"] == "=ROUNDUP(W25,0)"
        book = CellBook("Main", d["formulas"], d["values"])
        r = evaluate_reference("Main", "E25", book, row_of_interest=25)
        assert r.status == "computed"
        assert r.value == Decimal("7409")
        assert r.cache_substituted == []
