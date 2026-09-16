# -*- coding: utf-8 -*-
"""Derivation formulas must follow the MATCHED rows.

The formula sidecar exists so "how was this price derived" is answerable from the
workbook rather than from memory. Two capping bugs made it answer a different
question:

1. ``load_formulas_for_parquet(max_cells=60)`` — the dict is in A1 order, so 60
   cells covered roughly the first five rows. A row-235 derivation ask rendered
   the formulas of unrelated early rows and none of its own (live 2026-09-16).
2. ``render_dataset_answer`` emitted ``list(formulas.items())[:40]`` — again the
   first cells of the sheet, regardless of which rows the SQL matched. Worse than
   missing: it looks like the answer.

These tests pin the contract: cells are selected by the row numbers present in the
result, and unmatched rows only ever appear as clearly-labelled context.
"""
import pytest

from core.sheet_dataset_service import (
    SHEET_ROW_COL,
    load_formulas_for_parquet,
    render_dataset_answer,
)


def _result(formulas, rows):
    return {
        "file_name": "wb.xlsx",
        "entity_name": "Sheet1",
        "source_modified_at": "2026-09-11",
        "sql": "SELECT * FROM sheet WHERE row = 235",
        "columns": ["LIST", "F", "N"],
        "rows": rows,
        "row_count": len(rows),
        "formulas": formulas,
    }


class TestMatchedRowFormulas:
    SHEET = {
        "G2": "=0.75*F2", "N2": "=ROUNDUP(M2,0)",
        "G235": "=F235*0.9", "I235": "=H235+700", "K235": "=J235*1.02",
        "L235": "=K235/0.87", "M235": "=L235/0.86", "N235": "=ROUNDUP(M235,0)",
    }

    def test_matched_rows_formulas_are_emitted(self):
        out = render_dataset_answer(
            _result(self.SHEET, [{SHEET_ROW_COL: 235, "LIST": 7519.0, "F": 5350}])
        )
        for cell in ("G235", "I235", "K235", "L235", "M235", "N235"):
            assert cell in out, f"{cell} missing from the derivation block"

    def test_early_row_formulas_do_not_displace_the_match(self):
        """The bug: the sheet's first cells were printed instead of the match's."""
        out = render_dataset_answer(
            _result(self.SHEET, [{SHEET_ROW_COL: 235, "LIST": 7519.0}])
        )
        matched_line = [l for l in out.splitlines() if l.startswith("FORMULAS FOR")][0]
        assert "G235" in matched_line
        assert "G2=" not in matched_line

    def test_other_rows_are_labelled_as_context(self):
        out = render_dataset_answer(
            _result(self.SHEET, [{SHEET_ROW_COL: 235, "LIST": 7519.0}])
        )
        if "OTHER ROWS' FORMULAS" in out:
            ctx = [l for l in out.splitlines() if l.startswith("OTHER ROWS'")][0]
            assert "not this row" in ctx
            assert "G235" not in ctx

    def test_no_formulas_means_no_formula_line(self):
        out = render_dataset_answer(_result({}, [{SHEET_ROW_COL: 1}]))
        assert "FORMULAS" not in out

    def test_row_without_formulas_does_not_crash(self):
        out = render_dataset_answer(_result({"G9": "=F9*2"}, [{SHEET_ROW_COL: 4}]))
        assert "FORMULAS FOR" not in out  # nothing matched row 4


class TestFormulaLoader:
    def test_missing_sidecar_is_empty(self, tmp_path):
        assert load_formulas_for_parquet(str(tmp_path / "nope.parquet")) == {}

    def test_full_sheet_is_loaded_not_the_first_rows(self):
        """A real workbook's formulas must all be available to the renderer.

        Uses the live sidecar when present; otherwise asserts the default is no
        longer a small cap, which is the regression this guards.
        """
        import inspect

        sig = inspect.signature(load_formulas_for_parquet)
        assert sig.parameters["max_cells"].default >= 1000, (
            "a small default covers only the first rows and silently answers a "
            "derivation question about a different row"
        )


class TestProbeBoundaryAndRowColumn:
    """Probe correctness fixes found by running real derivation asks.

    Three separate ways a *wrong* file won the catalog probe, each of which made
    the dataset lane answer a question about a different spreadsheet:

    1. the internal `__sheet_row` column rode into the concatenated probe text,
       so a query for 5350 matched every file that merely HAS a row 5350;
    2. a pure-number token matched inside float tails — every hit for the model
       code "5216" was a substring of "15.521625000000002";
    3. a numeric cell storing 7519.0 was rejected once (2) was fixed, because the
       boundary rule forbade a trailing decimal that is part of the same number.
    """

    def test_row_number_column_is_not_scanned(self):
        import inspect

        from core import sheet_dataset_service as svc

        for fn in (svc._duckdb_probe_entry, svc._pandas_probe_entry):
            src = inspect.getsource(fn)
            assert "SHEET_ROW_COL" in src, (
                f"{fn.__name__} must exclude the internal row-number column from "
                "the scanned text — otherwise row numbers masquerade as values"
            )

    def test_numeric_cell_with_decimal_tail_still_matches(self):
        """'7519.0' is the number 7519, not a longer one."""
        import re

        token = "7519"
        assert re.search(rf"(?<![0-9.]){re.escape(token)}(?![0-9])", "LIST Price=7519.0")
        # ...while genuine neighbours still do not match
        assert not re.search(rf"(?<![0-9.]){re.escape(token)}(?![0-9])", "No.=017519")
        assert not re.search(rf"(?<![0-9.]){re.escape(token)}(?![0-9])", "c=15.521625000000002")
        assert not re.search(rf"(?<![0-9.]){re.escape(token)}(?![0-9])", "id=75190")


class TestNameContextIsSeparateFromFigureContext:
    """History may supply FIGURES; it must never NAME a file.

    An incidental history word that appears in one catalogued file name ("the
    vendor quote" -> "vendor") became a spurious named file, and the derivation
    lane resolved every probe to that unrelated form (live 2026-09-16).
    """

    def test_signature_separates_the_two_contexts(self):
        import inspect

        from core.sheet_dataset_service import search_all_datasets_sync

        params = inspect.signature(search_all_datasets_sync).parameters
        assert "context_texts" in params
        assert "name_context_texts" in params, (
            "figure context and name context must be separable, or history words "
            "hijack file selection"
        )

    def test_name_context_defaults_to_the_query_alone(self, monkeypatch):
        from core import sheet_dataset_service as svc

        seen = {}

        def _fake_name_tokens(texts, max_tokens=2):
            seen["texts"] = list(texts)
            return []

        monkeypatch.setattr(svc, "distinctive_name_tokens", _fake_name_tokens)
        monkeypatch.setattr(svc, "find_entries_sync", lambda *a, **k: [])
        svc.search_all_datasets_sync(
            "how was the price derived", None, None, 2, 10,
            ["history says the vendor quote was 5,350.00"],
        )
        assert seen.get("texts") == ["how was the price derived"], (
            "history leaked into name matching"
        )
