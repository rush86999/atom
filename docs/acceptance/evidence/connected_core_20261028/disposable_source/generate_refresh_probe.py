"""Generate the disposable two-sheet refresh probe and its expected manifest.

The workbook carries cross-sheet formulas with cached values so the existing
materializer sees both the formula expression and a usable stored value. Only
the baseline file is intended for upload; the changed-expected file documents
the owner's one-input edit.
"""
from __future__ import annotations

import json
from pathlib import Path

import xlsxwriter

OUT = Path(__file__).resolve().parent
BASELINE = OUT / "refresh_probe_f5f_baseline.xlsx"
CHANGED = OUT / "refresh_probe_f5f_changed_expected.xlsx"
MANIFEST = OUT / "refresh_probe_f5f_manifest.json"

ROWS = [
    ("PROBE-001", 2, 10.0),
    ("PROBE-002", 3, 10.0),
]


def write_workbook(path: Path, first_qty: int) -> None:
    workbook = xlsxwriter.Workbook(str(path))
    workbook.set_properties({
        "title": "Atom disposable connected refresh probe",
        "subject": "Test-only workbook; safe to delete",
        "author": "Atom acceptance",
        "comments": "Two sheets, cross-sheet formula, no production data.",
    })
    bold = workbook.add_format({"bold": True})
    money = workbook.add_format({"num_format": "0.00"})

    inputs = workbook.add_worksheet("Inputs")
    inputs.write_row(0, 0, ["Item", "Qty", "Unit Price"], bold)
    for index, (item, qty, price) in enumerate(ROWS, start=1):
        actual_qty = first_qty if index == 1 else qty
        inputs.write_string(index, 0, item)
        inputs.write_number(index, 1, actual_qty)
        inputs.write_number(index, 2, price)
    inputs.set_column(0, 0, 16)
    inputs.set_column(1, 2, 12)

    calc = workbook.add_worksheet("Calc")
    calc.write_row(0, 0, ["Item", "Qty", "Unit Price", "Line Total"], bold)
    total = 0.0
    for index, (item, qty, price) in enumerate(ROWS, start=1):
        actual_qty = first_qty if index == 1 else qty
        line_total = actual_qty * price
        total += line_total
        calc.write_formula(index, 0, f"=Inputs!A{index + 1}", None, item)
        calc.write_formula(index, 1, f"=Inputs!B{index + 1}", None, actual_qty)
        calc.write_formula(index, 2, f"=Inputs!C{index + 1}", None, price)
        calc.write_formula(
            index, 3,
            f"=Inputs!B{index + 1}*Inputs!C{index + 1}",
            money,
            line_total,
        )
    calc.set_column(0, 0, 16)
    calc.set_column(1, 3, 12)
    workbook.close()
    return total


def decisions(first_qty: int) -> dict:
    rows = []
    for index, (item, qty, price) in enumerate(ROWS):
        actual_qty = first_qty if index == 0 else qty
        total = actual_qty * price
        rows.append({
            "subject": item,
            "qty": actual_qty,
            "unit_price": price,
            "line_total": total,
            "decision": "REVIEW" if total >= 25 else "APPROVE",
        })
    return {
        "rows": rows,
        "total": sum(row["line_total"] for row in rows),
        "decisions": {
            "APPROVE": sum(1 for row in rows if row["decision"] == "APPROVE"),
            "REVIEW": sum(1 for row in rows if row["decision"] == "REVIEW"),
        },
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    baseline_total = write_workbook(BASELINE, 2)
    changed_total = write_workbook(CHANGED, 3)
    baseline = decisions(2)
    changed = decisions(3)
    manifest = {
        "schema": "connected-refresh-probe-1",
        "test_only": True,
        "safe_to_delete": True,
        "onedrive_destination": {
            "folder": "AtomAcceptance/connected-refresh-20261029-0120Z",
            "file": "refresh_probe_f5f_20261029.xlsx",
        },
        "sheets": ["Inputs", "Calc"],
        "baseline_file": BASELINE.name,
        "changed_expected_file": CHANGED.name,
        "baseline": baseline,
        "change": {
            "cell": "Inputs!B2",
            "from": 2,
            "to": 3,
            "only_input_changed": True,
        },
        "changed_expected": changed,
        "formula_cells": {
            "Calc!D2": "=Inputs!B2*Inputs!C2",
            "Calc!D3": "=Inputs!B3*Inputs!C3",
        },
        "assessment": {
            "subject_field": "Item",
            "measure_field": "Line Total",
            "policy": (
                "Use REVIEW when Line Total is at least 25. Use APPROVE "
                "otherwise. Do not infer any other decision."
            ),
            "decision_options": ["APPROVE", "REVIEW"],
            "baseline_expected": baseline["decisions"],
            "changed_expected": changed["decisions"],
        },
        "expected_totals": {
            "baseline": baseline_total,
            "changed": changed_total,
        },
        "stale_on_change": [
            "baseline calculation receipt",
            "baseline assessment receipt",
            "any export or document generated from the baseline canvas revision",
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=1))
    print(json.dumps({
        "baseline_bytes": BASELINE.stat().st_size,
        "changed_bytes": CHANGED.stat().st_size,
        "baseline_total": baseline_total,
        "changed_total": changed_total,
        "manifest": str(MANIFEST),
    }, indent=1))


if __name__ == "__main__":
    main()
