"""Runtime row-to-quote-line mapping controls."""
from __future__ import annotations

import pytest

from core.assignment_executor import NeedsContext
from core.quote_rows import (
    estimate_lines_from_calculated_rows,
    lines_from_rows,
)


def _rows():
    return [
        {"sku": "A", "quantity": "2", "unit": "each", "pack": "1",
         "unit_price": "100.00", "currency": "usd", "category": "A",
         "discount_percent": "0", "__row": 2},
        {"sku": "B", "quantity": "3", "unit": "each", "pack": "1",
         "unit_price": "50.00", "currency": "usd", "category": "B",
         "discount_percent": "5", "__row": 3},
    ]


def test_percent_rows_map_to_quote_line_contract():
    lines = lines_from_rows(
        rows=_rows(),
        columns={"item_id": "sku", "pack_size": "pack",
                 "discount": "discount_percent"},
        defaults={"price_basis": "contract"},
        discount_mode="percent",
        discount_authority="price-list:v1",
        source_ref={"resource_id": "file-1", "version": "v1"},
    )
    assert [line["item_id"] for line in lines] == ["A", "B"]
    assert lines[0]["currency"] == "USD"
    assert "discount_rate" not in lines[0]
    assert lines[1]["discount_rate"] == "0.05"
    assert lines[1]["discount_authority"] == "price-list:v1"
    assert lines[1]["source_ref"]["resource_id"] == "file-1"


def test_amount_discount_maps_to_a_rate():
    rows = [{"item_id": "B", "quantity": "2", "unit_price": "100.00",
             "currency": "USD", "discount_percent": "10",
             "__row": 2}]
    lines = lines_from_rows(
        rows=rows, columns={"discount": "discount_percent"},
        discount_mode="amount", discount_authority="approval:1")
    assert lines[0]["discount_rate"] == "0.05"


def test_missing_identity_or_currency_is_a_targeted_gap():
    with pytest.raises(NeedsContext) as exc:
        lines_from_rows(rows=[{"quantity": "1", "unit_price": "1",
                               "currency": "USD"}])
    assert exc.value.gap["concept"] == "quote_row"

    with pytest.raises(NeedsContext) as exc:
        lines_from_rows(rows=[{"item_id": "A", "quantity": "1",
                               "unit_price": "1"}])
    assert "currency" in exc.value.gap["question"]


def test_empty_rows_do_not_become_an_empty_quote():
    with pytest.raises(NeedsContext):
        lines_from_rows(rows=[])


def test_estimate_lines_flatten_calculated_rows():
    rows = [{
        "item_id": "B", "description": "B line", "quantity": "3",
        "unit": "each", "unit_price": "50.00", "discount_rate": "0.05",
        "source_ref": {"resource_id": "file-1"},
        "evidence": [{"row": 3}],
    }]
    lines = estimate_lines_from_calculated_rows(
        rows, account_map={"B": "acct-1"})
    assert lines == [{
        "item_id": "B", "name": "B line", "quantity": "3",
        "rate": "50.00", "unit": "each", "account_id": "acct-1",
        "discount_percent": "5.00",
    }]
