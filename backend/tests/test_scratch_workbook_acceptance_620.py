# -*- coding: utf-8 -*-
"""SCRATCH regression for GitHub issue 620 (not committed).

Exercises the production deterministic named-workbook read directly:
inspect_dataset_entries -> build_targets_from_scan -> build_structured_record
-> present_from_record.

Pins the acceptance criteria:
1. exact cell coordinates and the price basis as the column header verbatim;
2. one status per requested item (found / ambiguous / absent);
3. no value from another source (a second workbook holding the same item at
   a different price) is substituted into the answer.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pandas as pd
import pytest

from core.answer_presentation import (
    build_structured_record,
    build_targets_from_scan,
    present_from_record,
)
from core.workbook_read_artifact import inspect_dataset_entries

ASK = (
    "find the prices for U-22, SLE24-16, GSL48-16, U-38 and 381 "
    "in Consolidated Price List 2019.xlsx"
)
TARGETS = ["U-22", "SLE24-16", "GSL48-16", "U-38", "381"]


def _entry(path: str, sheet: str, file_name: str = "Consolidated Price List 2019.xlsx",
           external_id: str = "u8ai1e3a4ceb"):
    return {
        "source": "zoho_workdrive",
        "external_id": external_id,
        "file_name": file_name,
        "entity_name": sheet,
        "parquet_path": path,
        "row_count": None,
        "coverage": {"known": True, "truncated": False},
        "content_hash": "ff2597d26f",
        "ingested_at": "2026-09-07T23:06:19",
    }


def _frame(rows):
    return pd.DataFrame(rows)


@pytest.fixture()
def workbook(tmp_path):
    linmac = tmp_path / "linmac.parquet"
    _frame([
        {"__sheet_row": 26, "Model": "U-22", "Description": "Rotary machine",
         "List Price": 1777.0, "Dealer": 1776.96},
    ]).to_parquet(linmac)

    tennsmith = tmp_path / "tennsmith.parquet"
    _frame([
        {"__sheet_row": 101, "MODEL": "SLE24-16",
         "Catalog No": "SL-101", "DESCRIPTION": "Slitter",
         "Type": "Single wheel", "PRICE": 8880,
         "U.S. LIST": 4500.0, "U.S. COST": 3600.0},
        {"__sheet_row": 106, "MODEL": "GSL48-16",
         "Catalog No": "GS-106", "DESCRIPTION": "Slitter",
         "Type": "Gang", "PRICE": 14166},
    ]).to_parquet(tennsmith)

    # A second, unrelated source holding U-22 at a DIFFERENT price. If the
    # answer cites 9999 or names this file, a source substitution happened.
    other = tmp_path / "sept.parquet"
    _frame([
        {"__sheet_row": 7, "Item": "U-22", "Price": 9999},
    ]).to_parquet(other)

    return {
        "entries": [_entry(str(linmac), "LINMAC"),
                    _entry(str(tennsmith), "Tennsmith")],
        "other": _entry(str(other), "Sept2026", "Sept 2026 Email Prices.xlsx",
                        external_id="sept-eid"),
    }


def test_scratch_exact_cell_price_basis_per_item_and_no_substitution(workbook):
    artifact = inspect_dataset_entries(
        workbook["entries"],
        "Consolidated Price List 2019.xlsx",
        query=ASK,
        targets=TARGETS,
        requested_fields=["price"],
        content_hash="ff2597d26f",
        content_hash_algorithm="sha1",
        ingested_at="2026-09-07T23:06:19",
        provider="zoho_workdrive",
        resource_id="u8ai1e3a4ceb",
    )
    outcomes = {
        o["target"]: o for o in artifact["coverage"]["outcomes"]
    }
    # per-item status
    assert outcomes["U-22"]["status"] == "found"
    assert outcomes["SLE24-16"]["status"] == "found"
    assert outcomes["GSL48-16"]["status"] == "found"
    assert outcomes["U-38"]["status"] == "absent"
    assert outcomes["381"]["status"] in ("absent", "ambiguous")

    # exact cell + basis from the scan
    u22 = outcomes["U-22"]["evidence"][0]
    assert u22["sheet"] == "LINMAC"
    assert u22["cell"] == "A26"
    by_cell = {v["cell"]: v for v in u22["values"]}
    assert by_cell["C26"]["value"] == "1777.0"
    assert by_cell["C26"]["price_basis"] == "List Price"

    targets = build_targets_from_scan(
        TARGETS, outcomes, {}, requested_fields=["price"])
    record = build_structured_record(
        source_identity={
            "file_name": "Consolidated Price List 2019.xlsx",
            "service": "datasets",
            "source": "zoho_workdrive",
            "resource_id": "u8ai1e3a4ceb",
            "content_hash": "ff2597d26f",
            "ingested_at": "2026-09-07T23:06:19",
            "live_vs_saved": "saved copy",
            "evidence_kind": "materialized_copy",
        },
        evidence_revision="ff2597d26f:2026-09-07T23:06:19",
        attempt_id="attempt-scratch",
        evidence_action="new_read",
        requested_items=TARGETS,
        requested_fields=["price"],
        targets=targets,
        coverage={"indexed_sheets": 2, "scanned_sheets": 2},
    )
    rendered = present_from_record(record)
    answer = rendered["answer"]

    # exact cell + verbatim basis in the delivered answer
    assert "C26" in answer
    assert "'List Price'" in answer
    assert "1,777" in answer
    assert "E101" in answer and "'PRICE'" in answer and "8,880" in answer
    assert "E106" in answer and "14,166" in answer
    # per-item status survives delivery
    assert "- **U-38**" in answer and "no match in this copy" in answer
    assert "- **U-22**" in answer and "- **SLE24-16**" in answer
    # no source substitution
    assert "9999" not in answer
    assert "Sept 2026" not in answer
    assert "Consolidated Price List 2019.xlsx" in answer


def test_scratch_general_read_has_no_implicit_price_field():
    """A record with NO requested fields keeps the row's ranked values;
    delivery must not re-invent a price filter (the record builder stopped
    doing so in 2f3e0cd38 — the renderer had not)."""
    from core.answer_presentation import typed_value

    values = [
        {"col": "B5", "basis": "PRICE", **typed_value(250)},
        {"col": "C5", "basis": "Weight kg", **typed_value(12)},
        {"col": "D5", "basis": "Lead Time days", **typed_value(9)},
    ]
    targets = [{
        "item": "AX-1",
        "aliases": [],
        "identity": {"status": "single", "candidates": [{
            "ref": "Specs!R5",
            "values": values,
            "identity": {"status": "bound", "references": [
                {"sheet": "Specs", "cell": "A5", "row": 5,
                 "value": "AX-1"}]},
        }]},
        "field": {"status": "multiple", "values": values},
        "retrieval": {"status": "searched", "error_category": None},
    }]
    record = build_structured_record(
        source_identity={"file_name": "Generic Spec.xlsx",
                         "live_vs_saved": "saved copy"},
        evidence_revision="generic-hash:2026-09-01",
        attempt_id="attempt-generic",
        evidence_action="new_read",
        requested_items=["AX-1"],
        requested_fields=[],
        targets=targets,
        coverage={"indexed_sheets": 1},
    )
    answer = present_from_record(record)["answer"]
    assert "AX-1" in answer
    assert "PRICE" in answer and "250" in answer
    assert "Weight kg" in answer and "12" in answer
    assert "Lead Time days" in answer and "9" in answer


def test_scratch_ambiguous_item_is_not_guessed(tmp_path):
    """A code present on two rows stays an explicit ambiguity: both exact
    cells are listed and no one value is presented as the answer."""
    a = tmp_path / "dup_a.parquet"
    b = tmp_path / "dup_b.parquet"
    pd.DataFrame([{"__sheet_row": 10, "Model": "DUP-1", "PRICE": 100}]
                 ).to_parquet(a)
    pd.DataFrame([{"__sheet_row": 20, "Model": "DUP-1", "PRICE": 200}]
                 ).to_parquet(b)
    entries = [_entry(str(a), "SheetA"), _entry(str(b), "SheetB")]
    ask = "price of DUP-1 in Consolidated Price List 2019.xlsx"
    artifact = inspect_dataset_entries(
        entries, "Consolidated Price List 2019.xlsx",
        query=ask, targets=["DUP-1"], requested_fields=["price"],
        content_hash="ff2597d26f")
    outcome = artifact["coverage"]["outcomes"][0]
    assert outcome["status"] == "ambiguous"
    assert len(outcome["evidence"]) == 2
    cells = {(e["sheet"], e["cell"]) for e in outcome["evidence"]}
    assert cells == {("SheetA", "A10"), ("SheetB", "A20")}

    targets = build_targets_from_scan(
        ["DUP-1"], {"DUP-1": outcome}, {}, requested_fields=["price"])
    record = build_structured_record(
        source_identity={"file_name": "Consolidated Price List 2019.xlsx"},
        evidence_revision="rev", attempt_id="attempt-dup",
        evidence_action="new_read", requested_items=["DUP-1"],
        requested_fields=["price"], targets=targets,
        coverage={"indexed_sheets": 2},
    )
    answer = present_from_record(record)["answer"]
    assert "2 possible rows" in answer and "which one" in answer.lower()
    assert "100" in answer and "200" in answer  # both candidates shown


def test_scratch_named_file_lane_scopes_to_the_designated_workbook(
        workbook, tmp_path):
    """The lane's own resolution: a near-name copy and another year's list
    are catalogued too; only the exactly named workbook may answer."""
    import types
    from unittest.mock import patch

    import core.chat_tool_planner as planner

    copy = tmp_path / "copy.parquet"
    _frame([
        {"__sheet_row": 3, "Model": "U-22", "List Price": 4321},
    ]).to_parquet(copy)

    old = tmp_path / "old.parquet"
    _frame([
        {"__sheet_row": 9, "Model": "U-22", "List Price": 1111},
    ]).to_parquet(old)

    designated = workbook["entries"]
    near_copy = _entry(
        str(copy), "Linmac Update",
        "Copy of Consolidated Price List 2019.xlsx Linmac Update.xlsx",
        external_id="copy-eid")
    older = _entry(
        str(old), "2015", "Consolidated Price List 2015.xlsx",
        external_id="2015-eid")
    catalog = list(designated) + [near_copy, older, workbook["other"]]

    def entries_for(source, external_id):
        return [e for e in catalog
                if e["source"] == source and e["external_id"] == external_id]

    plan = types.SimpleNamespace()
    with (
        patch("core.sheet_dataset_service.sheet_datasets_enabled",
              return_value=True),
        patch("core.sheet_dataset_service.find_entries_sync",
              return_value=list(catalog)),
        patch("core.sheet_dataset_service.entries_for_file_sync",
              side_effect=entries_for),
        patch("core.integrations.token_store.connected_source_grant_state",
              return_value="active"),
    ):
        block = planner._datasets_named_file_block
        import asyncio
        block = asyncio.run(block(
            "u1", ASK,
            {"message": ASK, "workspace_id": "ws1", "history": []},
            plan=plan))

    assert block
    for foreign in ("4,321", "4321", "1,111", "1111", "9,999", "9999"):
        assert foreign not in block, f"substituted value {foreign}"
    assert "Copy of Consolidated" not in block
    assert "Consolidated Price List 2015" not in block
    assert "Sept 2026" not in block
    # exact cell + basis for the designated workbook's rows
    assert "C26=1777.0" in block and "List Price" in block
    # one row per requested item
    for item in TARGETS:
        assert f"| {item} |" in block


def test_scratch_confirmation_resumes_the_named_read_without_reasking(
        workbook, tmp_path):
    """The confirmation lane (the path a 'that filename is correct' turn
    takes) runs the SAME deterministic read from the pending task and never
    re-asks permission or substitutes another file."""
    from unittest.mock import AsyncMock, patch

    import integrations.chat_orchestrator as chat
    from core.pending_file_task import build_pending_task

    copy = tmp_path / "copy.parquet"
    _frame([
        {"__sheet_row": 3, "Model": "U-22", "List Price": 4321},
    ]).to_parquet(copy)
    near_copy = _entry(
        str(copy), "Linmac Update",
        "Copy of Consolidated Price List 2019.xlsx Linmac Update.xlsx",
        external_id="copy-eid")
    catalog = list(workbook["entries"]) + [near_copy, workbook["other"]]

    def entries_for(source, external_id):
        return [e for e in catalog
                if e["source"] == source and e["external_id"] == external_id]

    orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
    orch.ai_engines = {}
    orch.llm_service = None
    task = build_pending_task(
        ASK, "consolidated price list 2019.xlsx")
    intent = {"reader": "datasets", "state": "resolved",
              "sources": [{"reader": "datasets",
                           "mention": "consolidated price list 2019.xlsx"}]}
    with (
        patch("core.named_file_resolution.resolve_named_file_intent",
              new=AsyncMock(return_value=intent)),
        patch("core.sheet_dataset_service.sheet_datasets_enabled",
              return_value=True),
        patch("core.sheet_dataset_service.find_entries_sync",
              return_value=list(catalog)),
        patch("core.sheet_dataset_service.entries_for_file_sync",
              side_effect=entries_for),
        patch("core.integrations.token_store.connected_source_grant_state",
              return_value="active"),
    ):
        import asyncio
        result = asyncio.run(orch._direct_confirmed_file_read(
            task, [], "u1", "s1", "ws1", execution_id="e-confirm"))

    assert result["ok"] is True
    assert result["identity_verified"] is True
    assert result["structured_result"]
    from core.answer_presentation import present_from_record
    answer = present_from_record(result["structured_result"])["answer"]
    # exact cell + basis, per item
    assert "C26" in answer and "'List Price'" in answer and "1,777" in answer
    assert "- **U-38**" in answer and "no match" in answer
    # no substitution and no re-ask
    assert "4,321" not in answer and "9,999" not in answer
    assert "Sept 2026" not in answer
    assert "reconnect" not in answer.lower()
    assert "is that the right file" not in answer.lower()
