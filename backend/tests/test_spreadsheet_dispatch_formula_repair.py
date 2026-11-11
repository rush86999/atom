"""Spreadsheet dispatch/formula required-input controls.

Failure-first on the parent: a candidate token in an aggregate ask short-
circuits `answer_from_datasets` as an item probe, and a formula total treats
a blank required input as zero. Both must use the existing aggregate/SQL and
CellBook paths, never a parallel engine.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pandas as pd
import pytest

import core.sheet_dataset_service as sds
from core.dataset_aggregation import looks_like_aggregate_request
from core.formula_engine import FormulaResult
from core.pricing_calculation import workbook_calculation_result


def test_required_formula_gaps_name_missing_quantity():
    from core.dataset_aggregation import required_formula_input_gaps

    dependencies = [
        SimpleNamespace(sheet="Adjustments", cell="C5"),
        SimpleNamespace(sheet="Adjustments", cell="D5"),
        SimpleNamespace(sheet="Adjustments", cell="C2"),
    ]
    gaps = required_formula_input_gaps(
        ["PO ID", "Status", "Qty", "Unit Price", "Currency"],
        dependencies,
        {"C5"},
        values={"A5": "0055"},
        sheet_name="Adjustments",
    )
    assert gaps == [{
        "identity": "0055",
        "row": 5,
        "missing": "quantity",
        "cell": "C5",
    }]


def test_aggregate_query_is_recognized_before_probe():
    assert looks_like_aggregate_request(
        "PO Register approved rows total by currency for 0055") is True


@pytest.mark.asyncio
async def test_answer_from_datasets_dispatches_aggregate_before_probe(
    monkeypatch,
):
    entries = [{
        "dataset_name": "upload__po_register",
        "entity_name": "PO Register",
        "file_name": "spreadsheet_job_20261025.xlsx",
        "parquet_path": "/tmp/not-read-in-this-routing-test.parquet",
        "content_hash": "h1",
    }]
    monkeypatch.setattr(sds, "entries_for_file_sync", lambda *a, **k: entries)
    monkeypatch.setattr(sds, "_copy_is_fresh", lambda *a, **k: True)
    probes = []

    def _probe(*args, **kwargs):
        probes.append(args)
        return {"rows": [{"id": "wrong-item-probe"}]}

    monkeypatch.setattr(sds, "_probe_sheet_hits", _probe)
    aggregate_calls = []

    async def _aggregate(entries_arg, query, llm_service, **kwargs):
        aggregate_calls.append((entries_arg, query))
        return {
            "status": "complete",
            "block": "AGGREGATE BLOCK: CAD 8050.00",
            "sheet": "PO Register",
            "subtotals": {"CAD": {"value": "8050.00"}},
            "version": "h1",
        }

    monkeypatch.setattr(
        "core.dataset_aggregation.aggregate_named_dataset", _aggregate)

    result = await sds.answer_from_datasets(
        "upload", "file-1",
        "PO Register approved totals by currency for 0055",
        llm_service=object(),
    )

    assert result is not None
    assert result["aggregate_block"] == "AGGREGATE BLOCK: CAD 8050.00"
    assert result["rows"] == []
    assert probes == [], "aggregate request must not run the item probe"
    assert aggregate_calls, "aggregate executor was not called"
    assert "AGGREGATE BLOCK" in sds.render_dataset_answer(result)


def test_formula_result_exposes_required_input_gaps_without_value():
    gaps = [{
        "identity": "0055", "row": 5, "missing": "quantity", "cell": "C5",
    }]
    calc = FormulaResult(
        reference="Adjustments!D5",
        status="incomplete",
        missing="required input gap(s): quantity at C5; no complete total was computed",
        required_input_gaps=gaps,
    )
    result = workbook_calculation_result(calc, neutral=True)
    assert result.status == "incomplete"
    assert result.verification["required_input_gaps"] == gaps
    assert "computed_value" not in result.verification


@pytest.mark.asyncio
async def test_calculate_formula_refuses_blank_required_input(
    tmp_path, monkeypatch,
):
    import core.pricing_calculation as pc

    parquet = tmp_path / "adjustments.parquet"
    pd.DataFrame([
        {"PO ID": "0055", "Status": "Approved", "Qty": 2.0,
         "Unit Price": 75.0, "Currency": "CAD", "__sheet_row": 2},
        {"PO ID": "0007", "Status": "Approved", "Qty": None,
         "Unit Price": 100.0, "Currency": "CAD", "__sheet_row": 3},
    ]).to_parquet(parquet, index=False)
    entry = {
        "dataset_name": "upload__adjustments",
        "entity_name": "Adjustments",
        "file_name": "book.xlsx",
        "parquet_path": str(parquet),
        "content_hash": "h1",
        "columns": ["PO ID", "Status", "Qty", "Unit Price", "Currency"],
        "source": "upload",
    }

    class FakeBooks:
        def __init__(self, *_args, **_kwargs):
            self.prefer_hash = ""
            self._books = {}

        def entry_for(self, _sheet):
            return entry

        def problem_for(self, _sheet):
            return None

        def _load_entries(self):
            return [entry]

        def provider(self, _sheet):
            return None

    monkeypatch.setattr(pc, "_FileSheetBooks", FakeBooks)
    monkeypatch.setattr(pc, "_workspace_lessons", lambda *a, **k: [])
    monkeypatch.setattr(
        "core.sheet_dataset_service.load_formulas_for_parquet",
        lambda _path: {"D4": "=C2*D2+C3*D3"},
    )

    block = await pc.calculate_workbook_from_query(
        "calculate formula for book.xlsx Adjustments cell D4",
        user_id="u-1", workspace_id="ws-1",
    )
    assert block is not None
    assert "required input gap" in block
    assert "no complete total" in block
    assert "computed_value" not in block
