"""datasets.find_all — Excel-style Find All over the ingested catalog.

Every cell containing a value, with file/sheet/CELL ADDRESS/value/formula
and EXACT counts; a complete zero-match scan is scoped-absence evidence
(the absence guard reads the FIND ALL RESULTS marker); an incomplete scan
must never read as one.
"""
import time

import pytest

import core.sheet_dataset_service as sds


def _entry(tmp_path, name, sheet, columns, rows):
    """One catalogued sheet backed by a real parquet file."""
    import pandas as pd

    path = tmp_path / f"{name}__{sheet}.parquet"
    pd.DataFrame(rows, columns=columns).to_parquet(path)
    return {
        "dataset_name": f"{name}::{sheet}",
        "entity_name": sheet,
        "file_name": name,
        "source": "test",
        "source_kind": "file",
        "external_id": f"ext-{name}-{sheet}",
        "parquet_path": str(path),
        "columns": columns,
        "row_count": len(rows),
    }


@pytest.fixture
def catalog(monkeypatch, tmp_path):
    """Two files: the workbook (with formulas sidecar) + an unrelated one."""
    # Column ORDER is the workbook's: data columns first, __sheet_row LAST
    # (that is how the extractor writes frames), and cell letters derive
    # from data-column POSITION (see _column_letters) — 2nd column = B.
    wb = _entry(
        tmp_path, "PRICE VIPUL (6).xlsx", "Sheet1",
        ["LIST", "Factory Price", "Net", sds.SHEET_ROW_COL],
        [
            {"LIST": "header", "Factory Price": 0.0, "Net": 0,
             sds.SHEET_ROW_COL: 1},
            {"LIST": "7519", "Factory Price": 5350.0, "Net": 5625,
             sds.SHEET_ROW_COL: 235},
            {"LIST": "RFQ", "Factory Price": 5350.5, "Net": 1,
             sds.SHEET_ROW_COL: 236},
        ])
    sidecar = sds._formula_sidecar_path(
        tmp_path / __import__("pathlib").Path(wb["parquet_path"]).name)
    sidecar.write_text('{"sheet": "Sheet1", "formulas": '
                       '{"B235": "=A235*1", "C235": "=ROUNDUP(M235,0)"}}')
    other = _entry(
        tmp_path, "parts list.xlsx", "Sheet1",
        ["CODE", "Price", sds.SHEET_ROW_COL],
        [
            {"CODE": "WG-350DSAV", "Price": 5350, sds.SHEET_ROW_COL: 4},
            {"CODE": "other", "Price": 12, sds.SHEET_ROW_COL: 5},
        ])
    entries = [wb, other]
    monkeypatch.setattr(sds, "find_entries_sync",
                        lambda *a, **k: entries)
    return entries


def _scan(catalog, value, **kw):
    return sds.find_all_occurrences_sync(value, **kw)


class TestFindAllCells:
    def test_every_cell_with_address_value_formula(self, catalog):
        out = _scan(catalog, "5350")
        # F235=5350, F236=5350.5 (contains), parts PRICE4=5350 → 3 cells
        assert out["total_matches"] == 3
        cells = {(m["file"], m["cell"]) for m in out["matches"]}
        assert ("PRICE VIPUL (6).xlsx", "B235") in cells  # 2nd data col = B
        assert ("PRICE VIPUL (6).xlsx", "B236") in cells
        assert ("parts list.xlsx", "B4") in cells  # 2nd data col = B
        m = [m for m in out["matches"] if m["cell"] == "B235"][0]
        assert m["value"] == "5350"
        assert m["formula"] == "=A235*1"

    def test_comma_variant_matches_plain_number(self, catalog):
        assert _scan(catalog, "5,350")["total_matches"] == 3

    def test_exact_counts_when_display_capped(self, catalog):
        out = _scan(catalog, "5350", max_matches=1)
        assert out["total_matches"] == 3
        assert len(out["matches"]) == 1
        assert out["truncated"] is True

    def test_file_filter_scopes_the_scan(self, catalog):
        out = _scan(catalog, "5350", file_name="PRICE VIPUL")
        assert out["total_matches"] == 2
        assert all("PRICE VIPUL" in m["file"] for m in out["matches"])

    def test_zero_matches_complete_scan(self, catalog):
        out = _scan(catalog, "ZZZ-NOT-THERE")
        assert out["total_matches"] == 0
        assert out["incomplete"] is False
        assert out["files_scanned"] == 2

    def test_deadline_marks_incomplete_not_empty(self, catalog):
        out = _scan(catalog, "5350", deadline=time.monotonic() - 1)
        assert out["incomplete"] is True
        # "time ran out" must not be mistakable for a definitive empty scan
        assert out["files_scanned"] == 0


class TestRender:
    def test_render_lists_cells_and_counts(self, catalog):
        text = sds.render_find_all_result(_scan(catalog, "5350"))
        assert text.startswith("FIND ALL RESULTS")
        assert "3 cell match(es)" in text
        assert "B235 = 5350" in text
        assert "(formula =A235*1)" in text
        assert "complete scan: 2 file(s)" in text

    def test_render_zero_match_is_scoped_absence(self, catalog):
        text = sds.render_find_all_result(_scan(catalog, "ZZZ-NOT-THERE"))
        assert "0 cell matches" in text
        assert "no cell" in text

    def test_render_incomplete_says_so(self, catalog):
        text = sds.render_find_all_result(
            _scan(catalog, "5350", deadline=time.monotonic() - 1))
        assert "INCOMPLETE scan" in text


class TestAbsenceGuardIntegration:
    def test_complete_zero_match_scan_covers_absence_claim(self, catalog):
        from core.absence_guard import uncovered_absence_claims

        block = sds.render_find_all_result(_scan(catalog, "ZZZ-NOT-THERE"))
        assert uncovered_absence_claims(
            "No spreadsheet cell contains ZZZ-NOT-THERE.", block) == []

    def test_incomplete_scan_never_covers_absence(self, catalog):
        from core.absence_guard import uncovered_absence_claims

        block = sds.render_find_all_result(
            _scan(catalog, "ZZZ-NOT-THERE", deadline=time.monotonic() - 1))
        assert uncovered_absence_claims(
            "No spreadsheet cell contains ZZZ-NOT-THERE.", block)


class TestPlannerSurface:
    def test_find_all_is_an_allowed_datasets_intent_and_described(self):
        from core.chat_tool_planner import _SERVICE_DESCRIPTIONS

        desc = _SERVICE_DESCRIPTIONS["datasets"]
        assert "`find_all` intent" in desc
        assert "Find All" in desc
        assert "cell address" in desc

    def test_scope_regex_splits_value_from_filename(self):
        from core.chat_tool_planner import _FIND_ALL_SCOPE_RE

        m = _FIND_ALL_SCOPE_RE.match("5350 in PRICE VIPUL (6).xlsx")
        assert m.group(1) == "5350"
        assert m.group(2) == "PRICE VIPUL (6).xlsx"
        assert _FIND_ALL_SCOPE_RE.match("just a value") is None
