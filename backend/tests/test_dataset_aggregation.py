# -*- coding: utf-8 -*-
"""Spreadsheet selection/aggregation controls (2026-10-25 work order).

The arithmetic is proven with a controlled, already-validated plan before
any model is involved. The same executor/aggregator serves the natural-
language path.
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from core.dataset_aggregation import execute_validated_aggregate_plan


def _entries(tmp_path):
    po = pd.DataFrame([
        {"PO ID": "0007", "Status": "Approved", "Qty": 3.0,
         "Unit Price": 1250.00, "Currency": "CAD", "__sheet_row": 2},
        {"PO ID": "0012", "Status": "Approved", "Qty": 5.0,
         "Unit Price": 800.00, "Currency": "CAD", "__sheet_row": 3},
        {"PO ID": "0019", "Status": "Approved", "Qty": 2.0,
         "Unit Price": 150.00, "Currency": "CAD", "__sheet_row": 4},
        {"PO ID": "0024", "Status": "Cancelled", "Qty": 10.0,
         "Unit Price": 500.00, "Currency": "CAD", "__sheet_row": 5},
        {"PO ID": "0031", "Status": "Approved", "Qty": 4.0,
         "Unit Price": 999.99, "Currency": "USD", "__sheet_row": 6},
    ])
    adj = pd.DataFrame([
        {"PO ID": "0007", "Status": "Approved", "Qty": 1.0,
         "Unit Price": 100.00, "Currency": "CAD", "__sheet_row": 2},
        {"PO ID": "0012", "Status": "Approved", "Qty": -1.0,
         "Unit Price": 800.00, "Currency": "CAD", "__sheet_row": 3},
        {"PO ID": "0040", "Status": "Cancelled", "Qty": 2.0,
         "Unit Price": 250.00, "Currency": "CAD", "__sheet_row": 4},
        {"PO ID": "0055", "Status": "Approved", "Qty": None,
         "Unit Price": 75.00, "Currency": "CAD", "__sheet_row": 5},
    ])
    entries = []
    for name, df in (("PO Register", po), ("Adjustments", adj)):
        path = tmp_path / f"{name.replace(' ', '_')}.parquet"
        df.to_parquet(path, index=False)
        entries.append({
            "dataset_name": f"upload_spreadsheet_job__{name.lower().replace(' ', '_')}",
            "entity_name": name,
            "file_name": "spreadsheet_job_20261025.xlsx",
            "parquet_path": str(path),
            "content_hash": "abc123",
            "columns": [c for c in df.columns if c != "__sheet_row"],
            "row_count": len(df),
        })
    return entries


def _plan(entry, sql, roles=None):
    return {
        "dataset_name": entry["dataset_name"],
        "sql": sql,
        "identity_column": "PO ID",
        "quantity_column": "Qty",
        "price_column": "Unit Price",
        "currency_column": "Currency",
        "status_column": "Status",
        **(roles or {}),
    }


@pytest.mark.asyncio
async def test_po_register_approved_totals_and_provenance(tmp_path):
    entries = _entries(tmp_path)
    po = next(e for e in entries if e["entity_name"] == "PO Register")
    result = await execute_validated_aggregate_plan(
        entries,
        _plan(po, 'SELECT "__sheet_row", "PO ID", "Status", "Qty", '
                   '"Unit Price", "Currency" FROM df '
                   'WHERE "Status" = \'Approved\''),
        "PO Register sheet approved totals by currency",
        file_name="spreadsheet_job_20261025.xlsx",
    )
    assert result["status"] == "complete"
    assert result["complete"] is True
    assert result["selected_count"] == 4
    assert result["known_count"] == 4
    assert result["gaps"] == []
    assert result["subtotals"]["CAD"] == {
        "rows": 3, "quantity": "10.0", "value": "8050.00"
    }
    assert result["subtotals"]["USD"] == {
        "rows": 1, "quantity": "4.0", "value": "3999.96"
    }
    ids = [r["identity"] for r in result["rows"]]
    assert "0024" not in ids, "cancelled distractor must be excluded"
    assert all(i in ids for i in ("0007", "0012", "0019", "0031"))
    assert result["rows"][0]["row"] == 2
    assert result["rows"][0]["quantity_cell"] == "C2"
    assert result["rows"][0]["price_cell"] == "D2"


@pytest.mark.asyncio
async def test_adjustments_missing_quantity_is_named_and_no_total(tmp_path):
    entries = _entries(tmp_path)
    adj = next(e for e in entries if e["entity_name"] == "Adjustments")
    result = await execute_validated_aggregate_plan(
        entries,
        _plan(adj, 'SELECT "__sheet_row", "PO ID", "Status", "Qty", '
                   '"Unit Price", "Currency" FROM df '
                   'WHERE "Status" = \'Approved\''),
        "Adjustments sheet approved totals",
        file_name="spreadsheet_job_20261025.xlsx",
    )
    assert result["status"] == "partial"
    assert result["complete"] is False
    assert result["selected_count"] == 3
    assert result["known_count"] == 2
    assert result["subtotals"]["CAD"] == {
        "rows": 2, "quantity": "0.0", "value": "-700.00"
    }
    assert result["gaps"] == [{
        "identity": "0055", "row": 5, "missing": "quantity", "cell": "C5"
    }]
    assert "Complete/grand total withheld" in result["block"]
    assert "-700.00 CAD" in result["block"]
    assert "0055" in result["block"]


@pytest.mark.asyncio
async def test_explicit_sheet_binding_cannot_fall_back(tmp_path):
    entries = _entries(tmp_path)
    po = next(e for e in entries if e["entity_name"] == "PO Register")
    result = await execute_validated_aggregate_plan(
        entries,
        _plan(po, 'SELECT "__sheet_row", "PO ID", "Status", "Qty", '
                   '"Unit Price", "Currency" FROM df '
                   'WHERE "Status" = \'Approved\''),
        "Adjustments sheet approved totals",
        file_name="spreadsheet_job_20261025.xlsx",
    )
    assert result["status"] == "error"
    assert "SHEET" in result["block"].upper()
    assert "No total" in result["block"]


def test_operation_classification_is_general():
    from core.pending_file_task import (
        classify_file_operation,
        is_aggregate_request,
    )

    assert classify_file_operation(
        "Look at the PO Register sheet and select the approved rows. "
        "Calculate the total quantity and total value by currency."
    ) == "aggregate"
    assert classify_file_operation(
        "What is the price of item 0007?"
    ) != "aggregate"
    assert classify_file_operation(
        "calculate formula for workbook.xlsx Sheet1 cell D8"
    ) == "formula_reference"
    assert is_aggregate_request("filter the rows where status is open") is True


@pytest.mark.asyncio
async def test_natural_language_plan_uses_same_executor(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import core.llm.pinned_planning as pp
    from core.dataset_aggregation import aggregate_named_dataset

    entries = _entries(tmp_path)
    po = next(e for e in entries if e["entity_name"] == "PO Register")
    plan = SimpleNamespace(
        dataset_name=po["dataset_name"],
        sql=('SELECT "__sheet_row", "PO ID", "Status", "Qty", '
             '"Unit Price", "Currency" FROM df '
             'WHERE "Status" = \'Approved\''),
        identity_column="PO ID",
        quantity_column="Qty",
        price_column="Unit Price",
        currency_column="Currency",
        status_column="Status",
        note="",
    )

    async def fake_plan(*args, **kwargs):
        return plan

    monkeypatch.setattr(pp, "pinned_structured_call", fake_plan)
    monkeypatch.setattr(
        pp, "resolve_pinned_provider_model", lambda *a, **k: {}
    )
    result = await aggregate_named_dataset(
        entries,
        "Look at the PO Register sheet and select the approved rows. "
        "Calculate total quantity and total value by currency.",
        object(),
        file_name="spreadsheet_job_20261025.xlsx",
    )
    assert result["complete"] is True
    assert result["subtotals"]["CAD"]["value"] == "8050.00"
    assert result["subtotals"]["USD"]["value"] == "3999.96"


@pytest.mark.asyncio
async def test_missing_quantity_through_nl_plan(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import core.llm.pinned_planning as pp
    from core.dataset_aggregation import aggregate_named_dataset

    entries = _entries(tmp_path)
    adj = next(e for e in entries if e["entity_name"] == "Adjustments")
    plan = SimpleNamespace(
        dataset_name=adj["dataset_name"],
        sql=('SELECT "__sheet_row", "PO ID", "Status", "Qty", '
             '"Unit Price", "Currency" FROM df '
             'WHERE "Status" = \'Approved\''),
        identity_column="PO ID",
        quantity_column="Qty",
        price_column="Unit Price",
        currency_column="Currency",
        status_column="Status",
        note="",
    )

    async def fake_plan(*args, **kwargs):
        return plan

    monkeypatch.setattr(pp, "pinned_structured_call", fake_plan)
    monkeypatch.setattr(
        pp, "resolve_pinned_provider_model", lambda *a, **k: {}
    )
    result = await aggregate_named_dataset(
        entries,
        "Adjustments sheet approved rows total; name missing inputs.",
        object(),
        file_name="spreadsheet_job_20261025.xlsx",
    )
    assert result["complete"] is False
    assert result["gaps"][0]["identity"] == "0055"
    assert result["gaps"][0]["missing"] == "quantity"
    assert result["subtotals"]["CAD"]["value"] == "-700.00"
    assert "Complete/grand total withheld" in result["block"]


@pytest.mark.asyncio
async def test_processing_limit_withholds_total(tmp_path):
    entries = _entries(tmp_path)
    po = next(e for e in entries if e["entity_name"] == "PO Register")
    result = await execute_validated_aggregate_plan(
        entries,
        _plan(po, 'SELECT "__sheet_row", "PO ID", "Status", "Qty", '
                   '"Unit Price", "Currency" FROM df '
                   'WHERE "Status" = \'Approved\''),
        "PO Register sheet approved totals",
        file_name="spreadsheet_job_20261025.xlsx",
        max_rows=2,
    )
    assert result["status"] == "error"
    assert "PROCESSING LIMIT" in result["block"]
    assert "no total was computed" in result["block"]


@pytest.mark.asyncio
async def test_missing_explicit_sheet_is_reported_not_substituted(tmp_path):
    entries = _entries(tmp_path)
    po = next(e for e in entries if e["entity_name"] == "PO Register")
    result = await execute_validated_aggregate_plan(
        entries,
        _plan(po, 'SELECT "__sheet_row", "PO ID", "Status", "Qty", '
                   '"Unit Price", "Currency" FROM df'),
        "Location Detail sheet totals",
        file_name="spreadsheet_job_20261025.xlsx",
    )
    assert result["status"] == "error"
    assert "SHEET" in result["block"].upper()


def _sheet_entries(tmp_path, names, file_name="Adjustments.xlsx"):
    entries = []
    for name in names:
        df = pd.DataFrame([
            {"ID": "A1", "Qty": 1.0, "Price": 2.0, "Currency": "CAD",
             "__sheet_row": 2},
        ])
        path = tmp_path / f"{name.replace(' ', '_')}.parquet"
        df.to_parquet(path, index=False)
        entries.append({
            "dataset_name": f"wb__{name.lower().replace(' ', '_')}",
            "entity_name": name,
            "file_name": file_name,
            "parquet_path": str(path),
            "content_hash": "abc123",
            "columns": [c for c in df.columns if c != "__sheet_row"],
            "row_count": len(df),
        })
    return entries


def _simple_plan(entry):
    return {
        "dataset_name": entry["dataset_name"],
        "sql": ('SELECT "__sheet_row", "ID", "Qty", "Price", "Currency" '
                'FROM df'),
        "identity_column": "ID",
        "quantity_column": "Qty",
        "price_column": "Price",
        "currency_column": "Currency",
        "status_column": "",
    }


def test_operation_classifier_does_not_divert_lookups_or_refresh():
    from core.pending_file_task import classify_file_operation

    assert classify_file_operation(
        "Where is PO 0007 in the workbook?") == "read"
    assert classify_file_operation(
        "Find item 0055 where quantity is missing") == "read"
    assert classify_file_operation(
        "refresh the workbook and give me approved totals by currency"
    ) == "refresh"
    assert classify_file_operation(
        "re-read the workbook and show totals by status") == "re-run"
    assert classify_file_operation(
        "list the approved rows in the PO Register") == "aggregate"
    assert classify_file_operation(
        "Calculate the approved totals for the workbook.") == "aggregate"


@pytest.mark.asyncio
async def test_sheet_names_are_whole_token_and_filename_is_not_a_sheet(tmp_path):
    # "po" must not match inside "report"; the filename stem must not
    # bind a sheet named Adjustments.
    entries = _sheet_entries(tmp_path, ["PO", "Adjustments"])
    po = entries[0]
    result = await execute_validated_aggregate_plan(
        entries, _simple_plan(po),
        "report totals for the approved rows",
    )
    assert result["status"] == "error"
    assert "no sheet was named" in result["block"]

    result = await execute_validated_aggregate_plan(
        entries, _simple_plan(po), "Adjustments.xlsx approved totals")
    assert result["status"] == "error"
    assert "no sheet was named" in result["block"]

    result = await execute_validated_aggregate_plan(
        entries, _simple_plan(po), "totals for the sheet")
    assert result["status"] == "error"
    assert "without naming it" in result["block"]


@pytest.mark.asyncio
async def test_nested_sheet_names_resolve_to_longest(tmp_path):
    entries = _sheet_entries(tmp_path, ["PO", "PO Register"])
    long_entry = next(e for e in entries if e["entity_name"] == "PO Register")
    result = await execute_validated_aggregate_plan(
        entries, _simple_plan(long_entry),
        "total approved rows in the PO Register sheet",
    )
    assert result["status"] == "complete"
    assert result["sheet"] == "PO Register"


@pytest.mark.asyncio
async def test_explicit_missing_sheet_phrase_is_reported(tmp_path):
    entries = _sheet_entries(tmp_path, ["PO Register"])
    result = await execute_validated_aggregate_plan(
        entries, _simple_plan(entries[0]),
        "total approved rows in the Location Detail sheet",
    )
    assert result["status"] == "error"
    assert "SHEET NOT FOUND" in result["block"]


@pytest.mark.asyncio
async def test_sql_requires_sheet_row_and_rejects_distinct_union_paths(tmp_path):
    entries = _entries(tmp_path)
    po = next(e for e in entries if e["entity_name"] == "PO Register")
    cases = {
        "missing_sheet_row": 'SELECT "PO ID", "Qty" FROM df',
        "distinct": 'SELECT DISTINCT "PO ID" FROM df',
        "union": ('SELECT "__sheet_row", "PO ID" FROM df UNION ALL '
                  'SELECT "__sheet_row", "PO ID" FROM df'),
        "path": "SELECT * FROM '/tmp/secret.parquet'",
    }
    for label, sql in cases.items():
        result = await execute_validated_aggregate_plan(
            entries, _plan(po, sql), "PO Register sheet approved totals")
        assert result["status"] == "error", label
        assert "No total was computed" in result["block"]


def test_quoted_keyword_columns_are_not_rejected():
    from core.dataset_aggregation import _selection_sql_violation

    ok = ('SELECT "__sheet_row", "PO ID", "Count", "Min", "Max" '
          'FROM df WHERE "Status" = \'Approved\'')
    assert _selection_sql_violation(ok) is None
    assert _selection_sql_violation(
        'SELECT "__sheet_row" FROM "df"') is None
    assert _selection_sql_violation(
        'SELECT "__sheet_row" FROM df ORDER BY "row" NULLS LAST') is None
    assert _selection_sql_violation(
        'SELECT DISTINCT "__sheet_row" FROM df') is not None
    assert _selection_sql_violation(
        "SELECT * FROM '/tmp/secret.parquet'") is not None


@pytest.mark.asyncio
async def test_string_nan_inf_and_null_currency_are_gaps():
    from core.dataset_aggregation import aggregate_selected_rows

    records = [
        {"__sheet_row": 2, "ID": "A", "Qty": "nan", "Price": 1.0,
         "Currency": "CAD"},
        {"__sheet_row": 3, "ID": "B", "Qty": "Infinity", "Price": 1.0,
         "Currency": "CAD"},
        {"__sheet_row": 4, "ID": "C", "Qty": 1.0, "Price": 1.0,
         "Currency": "NULL"},
        {"__sheet_row": 5, "ID": "D", "Qty": 1.0, "Price": 1.0,
         "Currency": "CAD"},
    ]
    result = aggregate_selected_rows(
        records, ["ID", "Qty", "Price", "Currency"],
        {"identity_column": "ID", "quantity_column": "Qty",
         "price_column": "Price", "currency_column": "Currency"},
        sheet="Sheet1", file_name="x.xlsx", version="v",
    )
    assert result["complete"] is False
    assert result["known_count"] == 1
    assert result["subtotals"]["CAD"]["quantity"] == "1.0"
    missing = {(g["identity"], g["missing"]) for g in result["gaps"]}
    assert ("A", "quantity") in missing
    assert ("B", "quantity") in missing
    assert ("C", "currency") in missing


@pytest.mark.asyncio
async def test_duplicate_sheet_rows_are_rejected():
    from core.dataset_aggregation import aggregate_selected_rows

    records = [
        {"__sheet_row": 2, "ID": "A", "Qty": 1.0, "Price": 1.0,
         "Currency": "CAD"},
        {"__sheet_row": 2, "ID": "A", "Qty": 1.0, "Price": 1.0,
         "Currency": "CAD"},
    ]
    result = aggregate_selected_rows(
        records, ["ID", "Qty", "Price", "Currency"],
        {"identity_column": "ID", "quantity_column": "Qty",
         "price_column": "Price", "currency_column": "Currency"},
        sheet="Sheet1", file_name="x.xlsx", version="v",
    )
    assert result["status"] == "error"
    assert "DUPLICATE ROWS" in result["block"]


@pytest.mark.asyncio
async def test_truncated_materialization_withholds_total(tmp_path):
    entries = _entries(tmp_path)
    po = next(e for e in entries if e["entity_name"] == "PO Register")
    po["coverage"] = {
        "known": True, "source_row_count": 100,
        "materialized_row_count": 5, "truncated": True, "row_cap": 5,
    }
    result = await execute_validated_aggregate_plan(
        entries, _plan(po, 'SELECT "__sheet_row", "PO ID", "Qty" '
                          'FROM df'), "PO Register sheet approved totals")
    assert result["status"] == "error"
    assert "TRUNCATED" in result["block"]


def test_display_cap_keeps_completeness_and_totals():
    from core.dataset_aggregation import aggregate_selected_rows

    records = [
        {"__sheet_row": idx + 2, "ID": f"ID{idx}", "Qty": 1.0,
         "Price": 2.0, "Currency": "CAD"}
        for idx in range(60)
    ]
    result = aggregate_selected_rows(
        records, ["ID", "Qty", "Price", "Currency"],
        {"identity_column": "ID", "quantity_column": "Qty",
         "price_column": "Price", "currency_column": "Currency"},
        sheet="Sheet1", file_name="x.xlsx", version="v",
        source_row_count=60,
    )
    block = result["block"]
    assert result["subtotals"]["CAD"]["value"] == "120.00"
    assert "10 more contributing row(s) not displayed" in block
    assert block.index("Completeness: complete") < block.index(
        "Contributing rows:")


def test_formula_grammar_prefers_neutral_and_handles_row_qualification():
    from core.pricing_calculation import _FORMULA_QUERY_RE, _WB_QUERY_RE

    q = "calculate formula for bk.xlsx BurrKing row 8 cell D8"
    match = _FORMULA_QUERY_RE.search(q)
    assert match is not None
    assert match.group("file1") == "bk.xlsx"
    assert match.group("sheet1") == "BurrKing"
    assert match.group("row1") == "8"
    assert _WB_QUERY_RE.search(q) is None

    q2 = "calculate cell D8 in bk.xlsx Sheet1"
    match2 = _FORMULA_QUERY_RE.search(q2)
    assert match2 is not None
    assert match2.group("cell2") == "D8"
    assert match2.group("file2") == "bk.xlsx"
    assert match2.group("sheet2") == "Sheet1"


@pytest.mark.asyncio
async def test_neutral_formula_rejects_priced_scope_before_lookup():
    from core.pricing_calculation import calculate_workbook_from_query

    block = await calculate_workbook_from_query(
        "calculate formula for x.xlsx Sheet1 cell D8 "
        "currency=CAD item=Widget",
        None, None,
    )
    assert block is not None
    assert "NEUTRAL ARITHMETIC ONLY" in block
    assert "no priced result was recorded" in block


@pytest.mark.asyncio
async def test_multiple_active_versions_are_rejected(tmp_path):
    entries = _entries(tmp_path)
    po = next(e for e in entries if e["entity_name"] == "PO Register")
    version_b = dict(po)
    version_b["content_hash"] = "def456"
    version_b["dataset_name"] = po["dataset_name"] + "_v2"
    entries.append(version_b)
    result = await execute_validated_aggregate_plan(
        entries, _plan(po, 'SELECT "__sheet_row", "PO ID" FROM df'),
        "PO Register sheet approved totals")
    assert result["status"] == "error"
    assert "WORKBOOK VERSION AMBIGUOUS" in result["block"]


@pytest.mark.asyncio
async def test_space_containing_filename_does_not_leave_sheet_words(tmp_path):
    entries = _sheet_entries(
        tmp_path, ["PO", "PO Register"], file_name="PO Register.xlsx")
    result = await execute_validated_aggregate_plan(
        entries, _simple_plan(entries[0]),
        "PO Register.xlsx — select the approved rows")
    assert result["status"] == "error"
    assert "no sheet was named" in result["block"]

    long_entry = next(e for e in entries if e["entity_name"] == "PO Register")
    result = await execute_validated_aggregate_plan(
        entries, _simple_plan(long_entry),
        "PO Register sheet approved totals")
    assert result["status"] == "complete"
    assert result["sheet"] == "PO Register"


@pytest.mark.asyncio
async def test_required_inputs_cannot_be_coalesced_or_filtered_out(tmp_path):
    entries = _entries(tmp_path)
    adj = next(e for e in entries if e["entity_name"] == "Adjustments")
    cases = {
        "coalesce": ('SELECT "__sheet_row", "PO ID", '
                     'COALESCE("Qty", 0) AS "Qty", "Unit Price", '
                     '"Currency" FROM df WHERE "Status" = \'Approved\''),
        "ifnull": ('SELECT "__sheet_row", "PO ID", '
                   'IFNULL("Qty", 0) AS "Qty", "Unit Price", '
                   '"Currency" FROM df WHERE "Status" = \'Approved\''),
        "is_not_null": ('SELECT "__sheet_row", "PO ID", "Qty", '
                        '"Unit Price", "Currency" FROM df '
                        'WHERE "Status" = \'Approved\' AND "Qty" IS NOT NULL'),
        "qty_filter": ('SELECT "__sheet_row", "PO ID", "Qty", '
                       '"Unit Price", "Currency" FROM df '
                       'WHERE "Status" = \'Approved\' AND "Qty" > 0'),
    }
    for label, sql in cases.items():
        result = await execute_validated_aggregate_plan(
            entries, _plan(adj, sql), "Adjustments sheet approved totals")
        assert result["status"] == "error", label
        assert "No total was computed" in result["block"]


@pytest.mark.asyncio
async def test_generic_sheet_words_do_not_bind_without_a_sheet_cue(tmp_path):
    entries = _sheet_entries(tmp_path, ["Summary", "Adjustments"])
    result = await execute_validated_aggregate_plan(
        entries, _simple_plan(entries[0]),
        "give me a summary of the approved rows and total by currency")
    assert result["status"] == "error"
    assert "no sheet was named" in result["block"]

    result = await execute_validated_aggregate_plan(
        entries, _simple_plan(entries[0]), "Summary sheet approved totals")
    assert result["status"] == "complete"
    assert result["sheet"] == "Summary"

    entries = _sheet_entries(tmp_path, ["Totals", "Adjustments"])
    result = await execute_validated_aggregate_plan(
        entries, _simple_plan(entries[0]), "show the totals by currency")
    assert result["status"] == "error"
    assert "no sheet was named" in result["block"]

    entries = _sheet_entries(tmp_path, ["Approved", "Adjustments"])
    result = await execute_validated_aggregate_plan(
        entries, _simple_plan(entries[0]), "select the approved rows")
    assert result["status"] == "error"
    assert "no sheet was named" in result["block"]


def test_neutral_stored_value_adds_no_pricing_authorization(monkeypatch):
    import core.task_lifecycle as tl
    from core.pricing_calculation import CalculationResult, record_calculation

    calls = []
    monkeypatch.setattr(
        tl, "add_unresolved_questions",
        lambda *a, **k: calls.append((a, k)))

    class FakeLifecycle:
        def create_operation(self, *a, **k):
            return {"operation_id": "op-1", "status": "pending"}

        def transition_operation(self, *a, **k):
            return None

        def attach_operation_field(self, *a, **k):
            return None

    result = CalculationResult(
        status="stored_value",
        verification={"stored_value": "5", "stored_value_note": "literal"},
        workbook={"neutral": True, "file": "BK.xlsx", "sheet": "BurrKing",
                  "output_cell": "D8"},
    )
    record_calculation(
        FakeLifecycle(), "run-1", "BurrKing row 8", result, neutral=True)
    assert calls == []


@pytest.mark.asyncio
async def test_refresh_reread_replaces_aggregate_receipt(monkeypatch):
    import types
    from integrations.chat_orchestrator import ChatOrchestrator

    class FakeUIS:
        async def execute(self, *a, **k):
            return {"status": "success", "data": {"found": True,
                                                  "served": True}}

    monkeypatch.setattr(
        "integrations.universal_integration_service."
        "UniversalIntegrationService", FakeUIS)

    orchestrator = object.__new__(ChatOrchestrator)
    new_record = {
        "file_name": "wb.xlsx", "sheet": "PO Register",
        "content_hash": "h2", "complete": True,
        "subtotals": {"CAD": {"rows": 1, "quantity": "1", "value": "42.00"}},
        "gaps": [],
    }

    async def fake_reread(pending_task, history, user_id, session_id,
                          workspace_id, deadline):
        return {
            "ok": True,
            "block": "REFRESHED BLOCK",
            "rendered_answer": "REFRESHED ANSWER",
            "meta": {"datasets_aggregate": new_record},
            "identity": {
                "service": "datasets", "source": "zoho_workdrive",
                "resource_id": "r1", "file_id": "r1",
                "content_hash": "h2", "ingested_at": "new",
            },
            "identity_verified": True,
            "coverage_complete": True,
            "retrieval_complete": True,
            "datasets_aggregate": True,
            "aggregate_record": new_record,
            "formula_reference": False,
            "structured_result": None,
        }

    monkeypatch.setattr(orchestrator, "_direct_confirmed_file_read",
                        fake_reread)
    result = {
        "block": "OLD BLOCK",
        "rendered_answer": "OLD ANSWER",
        "identity": {
            "service": "zoho_workdrive", "resource_id": "r1",
            "file_id": "r1", "content_hash": "h1", "ingested_at": "old",
        },
        "meta": {"datasets_aggregate": {"content_hash": "h1"}},
        "datasets_aggregate": True,
        "aggregate_record": {"content_hash": "h1"},
        "retrieval_complete": True,
    }
    pending = {
        "refresh_attempted": False,
        "resolved_file": {"file_name": "wb.xlsx"},
        "original_message": "refresh the workbook totals",
    }
    verdict = await orchestrator._verify_source_freshness(
        result, pending, "u1", "default", None)
    assert verdict["status"] == "refreshed"
    assert result["rendered_answer"] == "REFRESHED ANSWER"
    assert result["aggregate_record"] == new_record
    assert result["datasets_aggregate"] is True


@pytest.mark.asyncio
async def test_sql_projections_cannot_supply_calculation_inputs(tmp_path):
    entries = _entries(tmp_path)
    adj = next(e for e in entries if e["entity_name"] == "Adjustments")

    # An aliased projection is rejected outright (no-alias policy).
    case_alias_sql = (
        'SELECT "__sheet_row", '
        'CASE WHEN "Qty" > 0 THEN "Qty" '
        'WHEN "Qty" <= 0 THEN "Qty" '
        'WHEN "Qty" IS DISTINCT FROM 0 THEN 1 END AS "Qty", '
        '"Unit Price", "Currency", "Status" FROM df '
        'WHERE "Status" = \'Approved\'')
    result = await execute_validated_aggregate_plan(
        entries, _plan(adj, case_alias_sql),
        "Adjustments sheet approved totals")
    assert result["status"] == "error"
    assert "SQL REJECTED" in result["block"]

    # An UNALIASED CASE projection is ignored; the authoritative frame
    # keeps 0055's missing quantity and no invented 75 CAD appears.
    case_sql = (
        'SELECT "__sheet_row", '
        'CASE WHEN "Qty" > 0 THEN "Qty" '
        'WHEN "Qty" <= 0 THEN "Qty" '
        'WHEN "Qty" IS DISTINCT FROM 0 THEN 1 END, '
        '"Unit Price", "Currency", "Status" FROM df '
        'WHERE "Status" = \'Approved\'')
    result = await execute_validated_aggregate_plan(
        entries, _plan(adj, case_sql), "Adjustments sheet approved totals")
    assert result["status"] == "partial"
    assert result["known_count"] == 2
    assert result["subtotals"]["CAD"]["value"] == "-700.00"
    assert result["gaps"] == [{
        "identity": "0055", "row": 5, "missing": "quantity", "cell": "C5"
    }]
    assert "75.00" not in result["block"]

    # A constant projection (no alias) is ignored too.
    price_sql = (
        'SELECT "__sheet_row", "Qty", 999, '
        '"Currency", "Status" FROM df WHERE "Status" = \'Approved\'')
    result = await execute_validated_aggregate_plan(
        entries, _plan(adj, price_sql), "Adjustments sheet approved totals")
    assert result["status"] == "partial"
    assert result["subtotals"]["CAD"]["value"] == "-700.00"
    assert result["gaps"][0]["identity"] == "0055"


@pytest.mark.asyncio
async def test_row_identity_must_be_plain_integer_not_expression(tmp_path):
    entries = _entries(tmp_path)
    po = next(e for e in entries if e["entity_name"] == "PO Register")
    for sql in (
        'SELECT 999 AS "__sheet_row" FROM df',
        'SELECT 2.5 AS "__sheet_row" FROM df',
        'SELECT CAST("__sheet_row" AS INTEGER) AS "__sheet_row" FROM df',
        'SELECT "__sheet_row" + 0 AS "__sheet_row" FROM df',
        'WITH x AS (SELECT 2 AS __sheet_row) SELECT __sheet_row FROM x',
        'SELECT __sheet_row FROM (SELECT 2 AS __sheet_row) x',
        'SELECT __sheet_row FROM df, df d',
        # Review bypasses: a line comment split the hand parser, and a
        # dollar-quoted string hid the real derived-table FROM.
        ('SELECT CASE WHEN "PO ID" = \'0007\' THEN 2 '
         'WHEN "PO ID" = \'0012\' THEN 3 '
         'WHEN "PO ID" = \'0055\' THEN 4 END --,\n'
         '__sheet_row FROM df WHERE "Status" = \'Approved\''),
        ('SELECT "__sheet_row", $$ from df $$ FROM '
         '(SELECT unnest([2,3,4]) AS "__sheet_row") x'),
        'SELECT "__sheet_row" FROM df USING SAMPLE 2 ROWS (reservoir, 7)',
        'SELECT "__sheet_row" FROM df USING SAMPLE 10 PERCENT',
        ('SELECT "__sheet_row" FROM df WHERE "__sheet_row" IN '
         '(SELECT "__sheet_row" FROM df USING SAMPLE 2 ROWS '
         '(reservoir, 7))'),
        'SELECT "__SHEET_ROW" FROM df',
    ):
        result = await execute_validated_aggregate_plan(
            entries, _plan(po, sql), "PO Register sheet approved totals")
        assert result["status"] == "error", sql
        assert "No total was computed" in result["block"]


@pytest.mark.asyncio
async def test_planner_sheet_row_identity_is_corrected_to_business_key(tmp_path):
    entries = _entries(tmp_path)
    adj = next(e for e in entries if e["entity_name"] == "Adjustments")
    plan = _plan(
        adj,
        'SELECT "PO ID", "__sheet_row" FROM df WHERE "Status" = \'Approved\'',
        {"identity_column": "__sheet_row"},
    )
    result = await execute_validated_aggregate_plan(
        entries, plan, "Adjustments sheet approved totals")
    assert result["gaps"][0]["identity"] == "0055"
    assert [r["identity"] for r in result["rows"]] == ["0007", "0012"]
    assert all(r["identity_source"] == "identity_column"
               for r in result["rows"])


@pytest.mark.asyncio
async def test_nl_plan_projection_cannot_substitute_values(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import core.llm.pinned_planning as pp
    from core.dataset_aggregation import aggregate_named_dataset

    entries = _entries(tmp_path)
    adj = next(e for e in entries if e["entity_name"] == "Adjustments")
    plan = SimpleNamespace(
        dataset_name=adj["dataset_name"],
        sql=('SELECT "__sheet_row", '
             'CASE WHEN "Qty" > 0 THEN "Qty" '
             'WHEN "Qty" <= 0 THEN "Qty" '
             'WHEN "Qty" IS DISTINCT FROM 0 THEN 1 END, '
             '"Unit Price", "Currency", "Status" FROM df '
             'WHERE "Status" = \'Approved\''),
        identity_column="PO ID",
        quantity_column="Qty",
        price_column="Unit Price",
        currency_column="Currency",
        status_column="Status",
        note="",
    )

    async def fake_plan(*args, **kwargs):
        return plan

    monkeypatch.setattr(pp, "pinned_structured_call", fake_plan)
    monkeypatch.setattr(
        pp, "resolve_pinned_provider_model", lambda *a, **k: {}
    )
    result = await aggregate_named_dataset(
        entries,
        "Adjustments sheet approved rows total; name missing inputs.",
        object(),
        file_name="spreadsheet_job_20261025.xlsx",
    )
    assert result["status"] == "partial"
    assert result["gaps"] == [{
        "identity": "0055", "row": 5, "missing": "quantity", "cell": "C5"
    }]
    assert result["subtotals"]["CAD"]["value"] == "-700.00"
    assert "75.00" not in result["block"]


@pytest.mark.asyncio
async def test_case_variant_header_cannot_shadow_meta_row(tmp_path):
    # A user header __SHEET_ROW survives normalization; DuckDB then
    # renames the real meta __sheet_row to __sheet_row_1. The executor
    # must fail closed rather than read the lookalike as row identity.
    df = pd.DataFrame([
        {"__SHEET_ROW": 5, "PO ID": "0024", "Status": "Approved",
         "Qty": 10.0, "Unit Price": 500.0, "Currency": "CAD"},
        {"__SHEET_ROW": 2, "PO ID": "0007", "Status": "Approved",
         "Qty": 3.0, "Unit Price": 1250.0, "Currency": "CAD"},
    ])
    df["__sheet_row"] = [2, 3]
    path = tmp_path / "collision.parquet"
    df.to_parquet(path, index=False)
    entry = {
        "dataset_name": "wb_collision",
        "entity_name": "Sheet1",
        "file_name": "collision.xlsx",
        "parquet_path": str(path),
        "content_hash": "abc123",
        "columns": list(df.columns),
        "row_count": len(df),
    }
    result = await execute_validated_aggregate_plan(
        [entry],
        {
            "dataset_name": "wb_collision",
            "sql": ('SELECT "__sheet_row", "PO ID", "Status", "Qty", '
                    '"Unit Price", "Currency" FROM df '
                    'WHERE "Status" = \'Approved\''),
            "identity_column": "PO ID",
            "quantity_column": "Qty",
            "price_column": "Unit Price",
            "currency_column": "Currency",
            "status_column": "Status",
        },
        "Sheet1 approved totals",
    )
    assert result["status"] == "error"
    assert "ROW PROVENANCE MISSING" in result["block"]


@pytest.mark.asyncio
async def test_missing_planner_role_is_inferred_from_frame(tmp_path):
    entries = _entries(tmp_path)
    adj = next(e for e in entries if e["entity_name"] == "Adjustments")
    plan = _plan(
        adj,
        'SELECT "__sheet_row" FROM df WHERE "Status" = \'Approved\'',
        {"quantity_column": ""},
    )
    result = await execute_validated_aggregate_plan(
        entries, plan, "Adjustments sheet approved totals")
    assert result["status"] == "partial"
    assert result["gaps"] == [{
        "identity": "0055", "row": 5, "missing": "quantity", "cell": "C5"
    }]
    assert result["subtotals"]["CAD"]["value"] == "-700.00"


@pytest.mark.asyncio
async def test_missing_role_inference_cannot_bypass_required_column_guard(
        tmp_path):
    entries = _entries(tmp_path)
    adj = next(e for e in entries if e["entity_name"] == "Adjustments")
    plan = _plan(
        adj,
        'SELECT "__sheet_row" FROM df WHERE "Status" = \'Approved\' '
        'AND "Qty" > 0',
        {"quantity_column": ""},
    )
    result = await execute_validated_aggregate_plan(
        entries, plan, "Adjustments sheet approved totals")
    assert result["status"] == "error"
    assert "SQL REJECTED" in result["block"]
    assert "required input column 'Qty'" in result["block"]


@pytest.mark.asyncio
async def test_ambiguous_normalized_role_names_fail_closed(tmp_path):
    df = pd.DataFrame([
        {"PO ID": "0007", "Status": "Approved", "Qty": 1.0,
         "Qty.": 10.0, "Unit Price": 2.0, "Currency": "CAD",
         "__sheet_row": 2},
    ])
    path = tmp_path / "ambiguous_roles.parquet"
    df.to_parquet(path, index=False)
    entry = {
        "dataset_name": "wb_ambiguous",
        "entity_name": "Sheet1",
        "file_name": "ambiguous.xlsx",
        "parquet_path": str(path),
        "content_hash": "abc123",
        "columns": list(df.columns),
        "row_count": len(df),
    }
    result = await execute_validated_aggregate_plan(
        [entry],
        {
            "dataset_name": "wb_ambiguous",
            "sql": 'SELECT "__sheet_row" FROM df',
            "identity_column": "PO ID",
            "quantity_column": "",
            "price_column": "Unit Price",
            "currency_column": "Currency",
            "status_column": "Status",
        },
        "Sheet1 approved totals",
    )
    assert result["status"] == "error"
    assert "REQUIRED COLUMN NOT IDENTIFIED" in result["block"]


@pytest.mark.asyncio
async def test_required_column_guard_uses_ast_not_token_boundaries(tmp_path):
    entries = _entries(tmp_path)
    adj = next(e for e in entries if e["entity_name"] == "Adjustments")
    for predicate in (
        '"PO ID" <> \'limit\' AND "Qty" > 0',
        '/* limit */ "Qty" > 0',
        '"Credit Limit" > 0 AND "Qty" > 0',
    ):
        plan = _plan(
            adj,
            'SELECT "__sheet_row" FROM df WHERE "Status" = \'Approved\' '
            f'AND {predicate}',
            {"quantity_column": ""},
        )
        result = await execute_validated_aggregate_plan(
            entries, plan, "Adjustments sheet approved totals")
        assert result["status"] == "error", predicate
        assert "required input column 'Qty'" in result["block"]


@pytest.mark.asyncio
async def test_meta_row_cannot_be_a_calculation_role(tmp_path):
    df = pd.DataFrame([
        {"PO ID": "0007", "Status": "Approved", "Unit Price": 1250.0,
         "Currency": "CAD", "__sheet_row": 2},
    ])
    path = tmp_path / "no_qty.parquet"
    df.to_parquet(path, index=False)
    entry = {
        "dataset_name": "wb_no_qty",
        "entity_name": "Sheet1",
        "file_name": "no_qty.xlsx",
        "parquet_path": str(path),
        "content_hash": "abc123",
        "columns": list(df.columns),
        "row_count": len(df),
    }
    result = await execute_validated_aggregate_plan(
        [entry],
        {
            "dataset_name": "wb_no_qty",
            "sql": 'SELECT "__sheet_row" FROM df WHERE "Status" = \'Approved\'',
            "identity_column": "PO ID",
            "quantity_column": "__sheet_row",
            "price_column": "Unit Price",
            "currency_column": "Currency",
            "status_column": "Status",
        },
        "Sheet1 approved totals",
    )
    assert result["status"] == "error"
    assert "REQUIRED COLUMN NOT IDENTIFIED" in result["block"]


@pytest.mark.asyncio
async def test_predicate_aliases_columns_and_positionals_are_rejected(tmp_path):
    entries = _entries(tmp_path)
    adj = next(e for e in entries if e["entity_name"] == "Adjustments")
    cases = {
        "select_alias": (
            'SELECT "__sheet_row", "Qty" AS q FROM df '
            'WHERE "Status" = \'Approved\' AND q > 0'),
        "columns": (
            'SELECT "__sheet_row" FROM df WHERE "Status" = \'Approved\' '
            'AND COLUMNS(\'^Qty$\') > 0'),
        "positional": (
            'SELECT "__sheet_row" FROM df WHERE "Status" = \'Approved\' '
            'AND #3 > 0'),
        "nested_alias": (
            'SELECT "__sheet_row" FROM df WHERE EXISTS '
            '(SELECT 1, "Qty" AS q FROM df d '
            'WHERE d."Status" = \'Approved\' AND q > 0)'),
        "struct_extract": (
            'SELECT "__sheet_row" FROM df WHERE "Status" = \'Approved\' '
            'AND struct_extract(df, \'Qty\') IS DISTINCT FROM NULL'),
        "array_extract": (
            'SELECT "__sheet_row" FROM df WHERE "Status" = \'Approved\' '
            'AND df[\'Qty\'] IS DISTINCT FROM NULL'),
        "struct_dot": (
            'SELECT "__sheet_row" FROM df WHERE "Status" = \'Approved\' '
            'AND (df).Qty IS DISTINCT FROM NULL'),
        "random": (
            'SELECT "__sheet_row" FROM df WHERE "Status" = \'Approved\' '
            'AND random() < 0.6'),
        "struct_values": (
            'SELECT "__sheet_row" FROM df WHERE "Status" = \'Approved\' '
            'AND list_contains(struct_values(df), 75)'),
    }
    for label, sql in cases.items():
        result = await execute_validated_aggregate_plan(
            entries, _plan(adj, sql), "Adjustments sheet approved totals")
        assert result["status"] == "error", label
        assert "SQL REJECTED" in result["block"]
