"""Deterministic A/B/C workbooks for the mapping acceptance harness.

Expected totals are computed here from fixture values, not product code.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pandas as pd

A_ROWS = [
    {"Item": "A-1", "Qty": 2, "Unit Price": 10.0, "Currency": "USD"},
    {"Item": "A-2", "Qty": 3, "Unit Price": 20.0, "Currency": "USD"},
]
B_ROWS = [
    {"SKU": "B-1", "Quantity": 2, "Amount": 15.0, "Discount": 1.0, "Currency": "USD", "Note": ""},
    {"SKU": "B-2", "Quantity": 3, "Amount": 20.0, "Discount": 2.0, "Currency": "USD", "Note": "renamed"},
]
C_ROWS = [
    {"Product": "C-1", "Qty": 1, "Value": 40.0, "Note": ""},
    {"Product": "C-2", "Qty": 2, "Value": 25.0, "Note": "blank qty"},
    {"Product": "C-3", "Qty": None, "Value": 10.0, "Note": "missing qty"},
]


def expected_sum(rows, column):
    total = sum(
        Decimal(str(row[column])) for row in rows
        if row.get(column) is not None)
    return f"{total:.2f}"


def build(root: Path):
    from decimal import Decimal

    root.mkdir(parents=True, exist_ok=True)
    a = root / "workbook_a.xlsx"
    b = root / "workbook_b.xlsx"
    c = root / "workbook_c.xlsx"
    pd.DataFrame(A_ROWS).to_excel(a, index=False)
    pd.DataFrame(B_ROWS).to_excel(b, index=False)
    pd.DataFrame(C_ROWS).to_excel(c, index=False)
    return {
        "a": str(a), "b": str(b), "c": str(c),
        "a_expected": expected_sum(A_ROWS, "Unit Price"),
        "b_expected": expected_sum(B_ROWS, "Amount"),
        "c_expected": expected_sum(C_ROWS, "Value"),
        "b_ambiguous_columns": ["Amount", "Discount"],
        "units": "USD",
    }
