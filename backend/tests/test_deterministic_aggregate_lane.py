# -*- coding: utf-8 -*-
"""Deterministic explicit sum/count controls (2026-10-28).

The captured UI ask must compute from the bound frame before any model
planner is attempted. These controls keep the model entirely unavailable so
a passing result proves the calculation is deterministic.
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from core.dataset_aggregation import aggregate_named_dataset


CAPTURED_ASK = (
    "What is the total Invoice Amount for Open invoices in vendor_loop.csv? "
    "Use a sum and cite the rows."
)


def _write_entry(tmp_path, df, *, name="vendor_loop", file_name="vendor_loop.csv",
                 content_hash="0a84a5f50661bc8a7917d158bcd36cad5b3f0262"):
    path = tmp_path / f"{name.replace(' ', '_')}.parquet"
    df.to_parquet(path, index=False)
    return {
        "dataset_name": f"upload_csv__{name.lower().replace(' ', '_')}",
        "entity_name": name,
        "file_name": file_name,
        "parquet_path": str(path),
        "content_hash": content_hash,
        "columns": [c for c in df.columns if c != "__sheet_row"],
        "row_count": len(df),
    }


def _vendor_frame():
    return pd.DataFrame([
        {"Vendor Ref": "IN-7301", "Invoice Amount": 3200.0,
         "State": "Open", "__sheet_row": 2},
        {"Vendor Ref": "IN-7302", "Invoice Amount": 7000.0,
         "State": "Open", "__sheet_row": 3},
        {"Vendor Ref": "IN-7303", "Invoice Amount": 12000.0,
         "State": "Open", "__sheet_row": 4},
        {"Vendor Ref": "IN-7304", "Invoice Amount": 9999.0,
         "State": "Closed", "__sheet_row": 5},
    ])


@pytest.mark.asyncio
async def test_captured_sum_ask_succeeds_with_model_planner_unavailable(
        tmp_path):
    entry = _write_entry(tmp_path, _vendor_frame())
    result = await aggregate_named_dataset(
        [entry], CAPTURED_ASK, None,
        file_name="vendor_loop.csv",
    )
    assert result["status"] == "complete"
    assert result["complete"] is True
    assert result["operation"] == "sum"
    assert result["measure"] == "Invoice Amount"
    assert result["selected_count"] == 3
    assert result["not_selected_count"] == 1
    # The authoritative fixture is 3200 + 7000 + 12000 = 22200.
    assert result["subtotals"] == {
        "(unstated)": {"rows": 3, "value": "22200.00"}
    }
    assert [row["identity"] for row in result["rows"]] == [
        "IN-7301", "IN-7302", "IN-7303"]
    assert [row["row"] for row in result["rows"]] == [2, 3, 4]
    assert all(row["value_cell"].startswith("B") for row in result["rows"])
    assert result["version"] == entry["content_hash"]
    assert "22200.00" in result["block"]
    assert "IN-7304" not in result["block"]


@pytest.mark.asyncio
async def test_renamed_schema_twin_resolves_the_named_measure(tmp_path):
    df = pd.DataFrame([
        {"Invoice Key": "IN-8101", "Settlement Figure": 3200.0,
         "Lifecycle": "Open", "__sheet_row": 2},
        {"Invoice Key": "IN-8102", "Settlement Figure": 7000.0,
         "Lifecycle": "Open", "__sheet_row": 3},
        {"Invoice Key": "IN-8103", "Settlement Figure": 12000.0,
         "Lifecycle": "Open", "__sheet_row": 4},
        {"Invoice Key": "IN-8104", "Settlement Figure": 1.0,
         "Lifecycle": "Closed", "__sheet_row": 5},
    ])
    entry = _write_entry(
        tmp_path, df, name="renamed_loop", file_name="renamed_loop.csv",
        content_hash="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    result = await aggregate_named_dataset(
        [entry],
        "What is the total Settlement Figure for Open records in "
        "renamed_loop.csv? Use a sum and cite the rows.",
        None,
        file_name="renamed_loop.csv",
    )
    assert result["status"] == "complete"
    assert result["measure"] == "Settlement Figure"
    assert result["selected_count"] == 3
    assert result["subtotals"]["(unstated)"]["value"] == "22200.00"
    assert [row["identity"] for row in result["rows"]] == [
        "IN-8101", "IN-8102", "IN-8103"]


@pytest.mark.asyncio
async def test_ambiguous_measure_refuses_without_choosing_by_position(tmp_path):
    df = pd.DataFrame([
        {"Vendor Ref": "IN-7301", "Invoice Amount": 3200.0,
         "Tax Amount": 320.0, "State": "Open", "__sheet_row": 2},
        {"Vendor Ref": "IN-7302", "Invoice Amount": 7000.0,
         "Tax Amount": 700.0, "State": "Open", "__sheet_row": 3},
    ])
    entry = _write_entry(tmp_path, df)
    result = await aggregate_named_dataset(
        [entry],
        "What is the total of Invoice Amount and Tax Amount for Open invoices "
        "in vendor_loop.csv? Use a sum and cite the rows.",
        None,
        file_name="vendor_loop.csv",
    )
    assert result["status"] == "clarification_required"
    assert "AMBIGUOUS MEASURE" in result["block"]
    assert "Invoice Amount" in result["block"]
    assert "Tax Amount" in result["block"]
    assert "No total was computed" in result["block"]
    assert result["subtotals"] == {}
    assert result["complete"] is False


@pytest.mark.asyncio
async def test_ambiguous_predicate_refuses_without_choosing_a_column(tmp_path):
    df = pd.DataFrame([
        {"Vendor Ref": "IN-7301", "Invoice Amount": 3200.0,
         "State": "Open", "Review State": "Open", "__sheet_row": 2},
    ])
    entry = _write_entry(tmp_path, df)
    result = await aggregate_named_dataset(
        [entry],
        "What is the total Invoice Amount for Open invoices in "
        "vendor_loop.csv? Use a sum and cite the rows.",
        None,
        file_name="vendor_loop.csv",
    )
    assert result["status"] == "clarification_required"
    assert "PREDICATE" in result["block"].upper()
    assert "State" in result["block"]
    assert "No total was computed" in result["block"]


@pytest.mark.asyncio
async def test_missing_numeric_input_remains_a_named_gap(tmp_path):
    df = pd.DataFrame([
        {"Vendor Ref": "IN-7301", "Invoice Amount": 3200.0,
         "State": "Open", "__sheet_row": 2},
        {"Vendor Ref": "IN-7302", "Invoice Amount": None,
         "State": "Open", "__sheet_row": 3},
        {"Vendor Ref": "IN-7303", "Invoice Amount": 12000.0,
         "State": "Open", "__sheet_row": 4},
    ])
    entry = _write_entry(tmp_path, df)
    result = await aggregate_named_dataset(
        [entry], CAPTURED_ASK, None, file_name="vendor_loop.csv")
    assert result["status"] == "partial"
    assert result["complete"] is False
    assert result["selected_count"] == 3
    assert result["known_count"] == 2
    assert result["gaps"] == [{
        "identity": "IN-7302",
        "row": 3,
        "missing": "value (Invoice Amount)",
        "cell": "B3",
    }]
    assert result["subtotals"]["(unstated)"]["value"] == "15200.00"
    assert "Complete/grand total withheld" in result["block"]
    assert "IN-7302" in result["block"]


@pytest.mark.asyncio
async def test_total_covers_rows_beyond_the_display_cap(tmp_path):
    rows = []
    for index in range(260):
        rows.append({
            "Vendor Ref": f"IN-{9000 + index}",
            "Invoice Amount": 1.0,
            "State": "Open",
            "__sheet_row": index + 2,
        })
    rows.append({
        "Vendor Ref": "IN-9999", "Invoice Amount": 999999.0,
        "State": "Closed", "__sheet_row": 262,
    })
    entry = _write_entry(tmp_path, pd.DataFrame(rows))
    result = await aggregate_named_dataset(
        [entry], CAPTURED_ASK, None, file_name="vendor_loop.csv")
    assert result["status"] == "complete"
    assert result["selected_count"] == 260
    assert result["known_count"] == 260
    assert result["subtotals"]["(unstated)"] == {
        "rows": 260, "value": "260.00"}
    assert len(result["rows"]) == 260
    assert result["rows"][-1]["row"] == 261
    assert "210 more contributing row(s) not displayed" in result["block"]
    assert "the totals above include the full selected scope" in result["block"]


@pytest.mark.asyncio
async def test_count_uses_the_same_bound_rows(tmp_path):
    entry = _write_entry(tmp_path, _vendor_frame())
    result = await aggregate_named_dataset(
        [entry],
        "How many Open invoices are in vendor_loop.csv? Use a count.",
        None,
        file_name="vendor_loop.csv",
    )
    assert result["status"] == "complete"
    assert result["operation"] == "count"
    assert result["selected_count"] == 3
    assert result["subtotals"]["(unstated)"] == {
        "rows": 3, "value": "3.00"}
    assert [row["identity"] for row in result["rows"]] == [
        "IN-7301", "IN-7302", "IN-7303"]


@pytest.mark.asyncio
async def test_ambiguous_sheet_and_version_are_clarifications(tmp_path):
    first = _write_entry(tmp_path, _vendor_frame())
    second = _write_entry(
        tmp_path, _vendor_frame(), name="other_sheet",
        file_name="vendor_loop.csv",
        content_hash="cccccccccccccccccccccccccccccccccccccccc")
    result = await aggregate_named_dataset(
        [first, second],
        "What is the total Invoice Amount for Open rows? Use a sum and cite "
        "the rows.",
        None,
        file_name="vendor_loop.csv",
    )
    assert result["status"] == "clarification_required"
    assert "SHEET AMBIGUOUS" in result["block"]

    version_b = dict(first)
    version_b["dataset_name"] = first["dataset_name"] + "_v2"
    version_b["content_hash"] = "dddddddddddddddddddddddddddddddddddddddd"
    result = await aggregate_named_dataset(
        [first, version_b],
        "What is the total Invoice Amount for Open invoices in the "
        "vendor_loop sheet? Use a sum and cite the rows.",
        None,
        file_name="vendor_loop.csv")
    assert result["status"] == "clarification_required"
    assert "VERSION AMBIGUOUS" in result["block"]


@pytest.mark.asyncio
async def test_production_named_file_lane_uses_the_deterministic_total(
        tmp_path, monkeypatch):
    from types import SimpleNamespace

    from core.chat_tool_planner import _datasets_named_file_block

    entry = _write_entry(tmp_path, _vendor_frame())
    entry.update({
        "source": "upload",
        "external_id": "vendor-loop-1",
        "coverage": {"known": True, "truncated": False},
        "ingested_at": "2026-10-28T03:40:55",
    })
    monkeypatch.setattr(
        "core.sheet_dataset_service.sheet_datasets_enabled", lambda: True)
    monkeypatch.setattr(
        "core.sheet_dataset_service.find_entries_sync",
        lambda *args, **kwargs: [entry])
    monkeypatch.setattr(
        "core.sheet_dataset_service.entries_for_file_sync",
        lambda *args, **kwargs: [entry])
    plan = SimpleNamespace()
    block = await _datasets_named_file_block(
        "u1", CAPTURED_ASK,
        {"message": CAPTURED_ASK, "history": [],
         "execution_id": "exec-calc", "session_id": "s-calc"},
        plan=plan, llm_service=None)
    assert block
    assert "22200.00" in block
    assert "IN-7301" in block
    assert "AGGREGATION NOT PLANNED" not in block
    meta = plan._result_meta["datasets_aggregate"]
    assert meta["status"] == "complete"
    assert meta["complete"] is True
    assert meta["selected_count"] == 3
    assert meta["content_hash"] == entry["content_hash"]
    assert plan._result_meta["storage_read"]["identity_verified"] is True


@pytest.mark.asyncio
async def test_unsupported_calculation_still_returns_to_the_planner(tmp_path):
    entry = _write_entry(tmp_path, _vendor_frame())
    # No explicit sum/count word: this is the existing quantity x price /
    # taught-calculation shape, so the deterministic lane must not claim it.
    result = await aggregate_named_dataset(
        [entry],
        "Calculate the line total for Open invoices in vendor_loop.csv.",
        None,
        file_name="vendor_loop.csv",
    )
    assert result["status"] == "error"
    assert "PLANNER UNAVAILABLE" in result["block"]
