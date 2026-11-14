"""A counted row is not a currency amount.

Goal 8 regression: the shared assignment evidence composer treated every
per-currency aggregate bucket as the fact's unit, so a deterministic ``count``
over currency-bearing source rows rendered as ``count of rows: 3.00 USD``.
A count is measured in rows; the source currency only groups the counted rows.
Monetary sums must keep their currency unit and the provenance labels/rows.
"""
from __future__ import annotations

from core.assignment_executor import (
    _collect_evidence,
    _compose_evidence_content,
)

SOURCE = {
    "file_name": "scotch-parts.xlsx",
    "sheet": "US$ SCOTCH PARTS",
    "dataset_name": "scotch_parts_price_list",
    "resource_id": "acceptance-scotch-entry",
    "source_version": "a" * 40,
}
LABEL = "scotch-parts.xlsx / US$ SCOTCH PARTS"


def _count_result() -> dict:
    return {
        "status": "applied",
        "operation": "count",
        "measure": "rows",
        "value": "3",
        "unit": "rows",
        "subtotals": {"USD": {"rows": 3, "value": "3.00"}},
        "rows": [
            {"identity": "SC-1", "identity_source": "identity_column",
             "row": 2, "value": "1", "currency": "USD", "value_cell": ""},
            {"identity": "SC-2", "identity_source": "identity_column",
             "row": 3, "value": "1", "currency": "USD", "value_cell": ""},
            {"identity": "SC-3", "identity_source": "identity_column",
             "row": 4, "value": "1", "currency": "USD", "value_cell": ""},
        ],
        "source": dict(SOURCE),
        "source_label": LABEL,
        "selected_count": 3,
        "evidence": [{
            "kind": "connected_aggregate",
            **SOURCE,
            "operation": "count",
            "measure": "rows",
            "subtotals": {"USD": {"rows": 3, "value": "3.00"}},
            "sheet_rows": [2, 3, 4],
        }],
    }


def _sum_result() -> dict:
    return {
        "status": "applied",
        "operation": "sum",
        "measure": "Total",
        "value": "85.00",
        "unit": "USD",
        "subtotals": {"USD": {"rows": 3, "value": "85.00"}},
        "rows": [
            {"identity": "SC-1", "identity_source": "identity_column",
             "row": 2, "value": "20.00", "currency": "USD",
             "value_cell": "E2"},
            {"identity": "SC-2", "identity_source": "identity_column",
             "row": 3, "value": "60.00", "currency": "USD",
             "value_cell": "E3"},
            {"identity": "SC-3", "identity_source": "identity_column",
             "row": 4, "value": "5.00", "currency": "USD",
             "value_cell": "E4"},
        ],
        "source": dict(SOURCE),
        "source_label": LABEL,
        "selected_count": 3,
        "evidence": [{
            "kind": "connected_aggregate",
            **SOURCE,
            "operation": "sum",
            "measure": "Total",
            "subtotals": {"USD": {"rows": 3, "value": "85.00"}},
            "sheet_rows": [2, 3, 4],
        }],
    }


def _context() -> dict:
    return {
        "objective": "Count the records in the scotch parts price list",
        "sources": [{"binding": dict(SOURCE)}],
        "previous_results": {
            "source-1": _count_result(),
            "source-2": _sum_result(),
        },
    }


def test_count_fact_is_measured_in_rows_not_source_currency():
    facts = _collect_evidence(_context())["facts"]
    by_step = {fact["step_id"]: fact for fact in facts}

    count_fact = by_step["source-1"]
    assert count_fact["value"] == "3"
    assert count_fact["unit"] == "rows"
    assert count_fact["label"] == "count of rows: 3"
    assert "USD" not in count_fact["label"]
    assert "3.00" not in count_fact["label"]

    # Monetary sums are untouched: value, currency unit and label.
    sum_fact = by_step["source-2"]
    assert sum_fact["value"] == "85.00"
    assert sum_fact["unit"] == "USD"
    assert sum_fact["label"] == "sum of Total: 85.00 USD"


def test_count_presentation_keeps_provenance_without_a_currency_amount():
    content = _compose_evidence_content(
        "presentation", {"result_step_ids": ["source-1"]}, _context())

    assert "count of rows: 3" in content
    assert "3.00 USD" not in content
    assert "count of rows: 3.00" not in content
    # Provenance and per-row citations survive the unit correction.
    assert "scotch-parts.xlsx" in content
    assert "US$ SCOTCH PARTS" in content
    assert "scotch_parts_price_list" in content
    assert "acceptance-scotch-entry" in content
    assert all(identity in content for identity in ("SC-1", "SC-2", "SC-3"))


def test_count_document_summary_uses_the_same_row_unit():
    content = _compose_evidence_content(
        "document", {"result_step_ids": ["source-1"]}, _context())

    assert "- count of rows: 3" in content
    assert "3.00 USD" not in content
    assert "scotch-parts.xlsx / US$ SCOTCH PARTS" in content
    assert "Row set: source-1" in content


def test_count_without_a_top_level_value_falls_back_to_subtotal_rows():
    result = _count_result()
    result.pop("value")
    context = {
        "objective": "Count records",
        "sources": [],
        "previous_results": {"source-1": result},
    }
    fact = _collect_evidence(context)["facts"][0]
    assert fact["value"] == "3"
    assert fact["unit"] == "rows"
    assert fact["label"] == "count of rows: 3"


def test_unstated_currency_rows_still_count_with_row_unit():
    result = _count_result()
    result["subtotals"] = {"(unstated)": {"rows": 3, "value": "3.00"}}
    result["value"] = "3"
    context = {
        "objective": "Count records",
        "sources": [],
        "previous_results": {"source-1": result},
    }
    fact = _collect_evidence(context)["facts"][0]
    assert fact["unit"] == "rows"
    assert fact["label"] == "count of rows: 3"
    assert "(unstated)" not in fact["label"]
