# -*- coding: utf-8 -*-
"""The shared table-selection boundary.

A request to list named columns for rows matching a condition is a
SELECTION: it must resolve the sheet's real headers and values, execute a
read-only selection, and render the validated rows. It is not an item lookup
and it does not assume quantity x price.

Regressions:
* the exact captured grants CSV (3 Submitted rows; Withdrawn excluded);
* a renamed schema and a different domain (helpdesk) through the same code;
* a model-written table cannot become the delivered factual result;
* a lookup receipt cannot satisfy a selection completion contract.
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from core.pending_file_task import classify_file_operation, is_aggregate_request
from core.table_selection import (
    deliver_selection,
    is_table_selection_request,
    render_selection,
    select_named_dataset,
    selection_receipt,
)


def _entry(tmp_path, df, sheet, file_name):
    path = tmp_path / f"{sheet}.parquet"
    df.to_parquet(path, index=False)
    return {
        "dataset_name": f"upload_{sheet.lower()}",
        "entity_name": sheet,
        "file_name": file_name,
        "parquet_path": str(path),
        "content_hash": f"hash-{sheet}",
        "columns": [c for c in df.columns if c != "__sheet_row"],
        "row_count": len(df),
        "source": "upload",
    }


def _grants(tmp_path):
    return _entry(tmp_path, pd.DataFrame([
        {"Application Ref": "GR-2026-014", "Applicant": "Northwind Literacy Trust",
         "Requested Amount": 12000, "Stage": "Submitted", "__sheet_row": 2},
        {"Application Ref": "GR-2026-021", "Applicant": "Harbour Youth Collective",
         "Requested Amount": 7000, "Stage": "Submitted", "__sheet_row": 3},
        {"Application Ref": "GR-2026-033", "Applicant": "Meadow Arts Network",
         "Requested Amount": 4800, "Stage": "Submitted", "__sheet_row": 4},
        {"Application Ref": "GR-2026-040", "Applicant": "Westgate Skills Co-op",
         "Requested Amount": 15000, "Stage": "Withdrawn", "__sheet_row": 5},
    ]), "grants_loop", "grants_loop.csv")


def test_selection_classifier_is_generic():
    positive = [
        "List Application Ref and Requested Amount for Submitted rows.",
        "show the Case Ref and Ask Amount for Open rows",
        "list the rows where Stage is Closed",
        "return Ticket and Hours for Open entries",
    ]
    negative = [
        "find GR-2026-014",
        "show ticket HD-88",
        "total the requested amount for submitted applications",
        "how many open tickets are there",
        "what does the applications sheet say about GR-2026-033",
    ]
    for ask in positive:
        assert is_table_selection_request(ask) is True, ask
        assert is_aggregate_request(ask) is False, ask
        assert classify_file_operation(ask) == "table_select", ask
    for ask in negative:
        assert is_table_selection_request(ask) is False, ask
    assert classify_file_operation("total the requested amount by stage") == "aggregate"
    assert classify_file_operation("find GR-2026-014") == "read"


def test_exact_grants_selection(tmp_path):
    entry = _grants(tmp_path)
    result = select_named_dataset(
        [entry],
        "List Application Ref and Requested Amount for Submitted rows.",
    )
    assert result["status"] == "complete"
    assert result["columns"] == ["Application Ref", "Requested Amount"]
    assert result["predicate"] == {
        "column": "Stage", "operator": "=", "value": "Submitted"}
    assert result["selected_count"] == 3
    assert [r["row"] for r in result["rows"]] == [2, 3, 4]
    assert result["rows"][0]["cells"] == {
        "Application Ref": "GR-2026-014", "Requested Amount": 12000}
    assert result["rows"][1]["cells"] == {
        "Application Ref": "GR-2026-021", "Requested Amount": 7000}
    assert result["rows"][2]["cells"] == {
        "Application Ref": "GR-2026-033", "Requested Amount": 4800}
    rendered = render_selection(result, result["source"])
    assert "GR-2026-014" in rendered
    assert "GR-2026-040" not in rendered
    assert "12000" in rendered and "7000" in rendered and "4800" in rendered


def test_renamed_schema_twin(tmp_path):
    entry = _entry(tmp_path, pd.DataFrame([
        {"Case Ref": "C-101", "Ask Amount": 900, "Stage": "Open", "__sheet_row": 2},
        {"Case Ref": "C-102", "Ask Amount": 450, "Stage": "Closed", "__sheet_row": 3},
        {"Case Ref": "C-103", "Ask Amount": 1200, "Stage": "Open", "__sheet_row": 4},
    ]), "cases", "cases.csv")
    result = select_named_dataset(
        [entry], "show the Case Ref and Ask Amount for Open rows")
    assert result["status"] == "complete"
    assert result["columns"] == ["Case Ref", "Ask Amount"]
    assert result["predicate"]["column"] == "Stage"
    assert [r["cells"]["Case Ref"] for r in result["rows"]] == ["C-101", "C-103"]
    assert "C-102" not in render_selection(result, result["source"])


def test_different_domain_twin(tmp_path):
    entry = _entry(tmp_path, pd.DataFrame([
        {"Ticket": "HD-88", "State": "Open", "Hours": 1.5, "__sheet_row": 2},
        {"Ticket": "HD-91", "State": "Open", "Hours": 2.25, "__sheet_row": 3},
        {"Ticket": "HD-97", "State": "Closed", "Hours": 9, "__sheet_row": 4},
    ]), "tickets", "helpdesk.csv")
    result = select_named_dataset(
        [entry], "return Ticket and Hours for Open entries")
    assert result["status"] == "complete"
    assert result["columns"] == ["Ticket", "Hours"]
    assert [r["cells"]["Ticket"] for r in result["rows"]] == ["HD-88", "HD-91"]
    assert result["rows"][0]["cells"]["Hours"] == 1.5


def test_model_table_never_becomes_the_delivered_facts(tmp_path):
    entry = _grants(tmp_path)
    result = select_named_dataset(
        [entry],
        "List Application Ref and Requested Amount for Submitted rows.",
    )
    fabricated = (
        "| reference | amount |\n| Roper-011 | 12000 |\n| Tennsmith-001 | 5500 |\n"
        "| GL001 | 8000 |\n| GL002 | 12000 |"
    )
    delivered = deliver_selection(result, result["source"], model_text=fabricated)
    assert delivered["ok"] is True
    for bad in ("Roper-011", "Tennsmith-001", "GL001", "GL002"):
        assert bad not in delivered["message"]
    assert delivered["diagnostics"]["rejected_model_table"] == fabricated
    assert "GR-2026-014" in delivered["message"]


def test_completion_requires_bound_selection_and_delivery(tmp_path):
    entry = _grants(tmp_path)
    result = select_named_dataset(
        [entry],
        "List Application Ref and Requested Amount for Submitted rows.",
    )
    not_delivered = selection_receipt(result, result["source"], delivered=False)
    delivered = selection_receipt(result, result["source"], delivered=True)
    assert not_delivered["ok"] is False
    assert delivered["ok"] is True
    assert delivered["checks"] == {
        "source_bound": True, "columns_resolved": True,
        "predicate_resolved": True, "row_references": True,
        "delivered": True,
    }

    # An item-lookup-shaped receipt has none of the selection evidence.
    lookup_receipt = {
        "status": "complete", "columns": [], "predicate": None,
        "rows": [], "selected_count": 0,
    }
    assert selection_receipt(
        lookup_receipt, {"file_name": "grants_loop.csv",
                         "content_hash": "hash"},
        delivered=True)["ok"] is False


def test_ambiguous_predicate_is_a_clarification(tmp_path):
    entry = _entry(tmp_path, pd.DataFrame([
        {"Ref": "A-1", "Stage": "Open", "Region": "North", "__sheet_row": 2},
        {"Ref": "A-2", "Stage": "Closed", "Region": "South", "__sheet_row": 3},
    ]), "amb", "amb.csv")
    result = select_named_dataset(
        [entry], "list the rows for Open in North")
    assert result["status"] == "clarification_required"
    assert result["reason"] in {"ambiguous_predicate", "ambiguous_value"}
    assert "CLARIFICATION" in result["block"]


@pytest.mark.asyncio
async def test_production_named_file_lane_selects_and_renders(tmp_path):
    """The planner's named-file lane dispatches to table_select, not items."""
    from types import SimpleNamespace
    from unittest.mock import patch

    from core.chat_tool_planner import _datasets_named_file_block

    entry = _grants(tmp_path)
    catalog = [entry]
    ask = ("List Application Ref and Requested Amount for Submitted rows "
           "in grants_loop.csv.")
    plan = SimpleNamespace(_result_meta={})
    with patch("core.sheet_dataset_service.sheet_datasets_enabled",
               return_value=True), \
         patch("core.sheet_dataset_service.find_entries_sync",
               return_value=list(catalog)), \
         patch("core.sheet_dataset_service.entries_for_file_sync",
               return_value=list(catalog)):
        block = await _datasets_named_file_block(
            "u1", "grants_loop.csv",
            {"message": ask, "workspace_id": "default"},
            plan=plan,
        )
    assert block
    assert "GR-2026-014" in block
    assert "GR-2026-021" in block
    assert "GR-2026-033" in block
    assert "GR-2026-040" not in block
    assert "Roper-011" not in block and "GL001" not in block
    storage = plan._result_meta["storage_read"]
    record = plan._result_meta["table_selection"]
    assert storage["completed"] is True
    assert storage["identity_verified"] is True
    assert storage["datasets_search"]["selection"] is True
    assert record["columns"] == ["Application Ref", "Requested Amount"]
    assert record["predicate"]["column"] == "Stage"
    assert record["predicate"]["value"] == "Submitted"
    assert [r["row"] for r in record["rows"]] == [2, 3, 4]
    assert "GR-2026-014" in storage["rendered_answer"]


def test_selection_response_contract_rejects_model_tables():
    """The route guard: only a bound selection receipt satisfies the ask."""
    from core.table_selection import selection_response_ok

    ask = "List Application Ref and Requested Amount for Submitted rows."
    assert selection_response_ok(ask, {}) is False
    assert selection_response_ok(ask, {
        "table_selection": {
            "status": "complete", "columns": [], "rows": [],
        }
    }) is False
    # A lookup receipt is not a selection.
    assert selection_response_ok(ask, {
        "workbook_read": {"targets": ["GR-2026-014"]}
    }) is False
    good = {
        "status": "complete",
        "columns": ["Application Ref", "Requested Amount"],
        "predicate": {"column": "Stage", "operator": "=", "value": "Submitted"},
        "rows": [{"row": 2, "cells": {"Application Ref": "GR-2026-014"}}],
        "source": {"file_name": "grants_loop.csv", "content_hash": "abc"},
    }
    assert selection_response_ok(ask, {"table_selection": good}) is True
    # Non-selection asks are outside this contract.
    assert selection_response_ok("find GR-2026-014", {}) is True
