"""Desired-state verification controls for commercial readbacks.

The controls separate effect observation (a remote id exists) from desired-
state verification (the complete authorized object was read back).  A sparse
readback is incomplete, not proof of no effect; a wrong line/customer/total is
a mismatch and must never trigger a second create.
"""
from __future__ import annotations

import asyncio

import pytest

from core.commercial_readback import (
    verify_bill_readback,
    verify_estimate_readback,
)


def _expected_estimate(**over):
    value = {
        "customer_id": "customer-1",
        "currency_code": "USD",
        "date": "2026-11-01",
        "reference_number": "RFQ-1",
        "total": "200.00",
        "sub_total": "200.00",
        "tax_total": "0.00",
        "line_items": [{
            "item_id": "A", "quantity": "2", "rate": "100.00",
            "account_id": "acct-1", "unit": "ea", "pack_size": "1",
        }],
    }
    value.update(over)
    return value


def _observed_estimate(**over):
    value = {
        "estimate_id": "est-1",
        "estimate_number": "EST-0001",
        "customer_id": "customer-1",
        "currency_code": "USD",
        "date": "2026-11-01",
        "reference_number": "RFQ-1",
        "total": "200.00",
        "sub_total": "200.00",
        "tax_total": "0.00",
        "line_items": [{
            "line_item_id": "line-1", "item_id": "A",
            "quantity": "2.00", "rate": "100.000",
            "account_id": "acct-1", "unit": "ea", "pack_size": "1",
        }],
    }
    value.update(over)
    return value


def _verify(expected=None, observed=None):
    return verify_estimate_readback(
        expected or _expected_estimate(),
        observed or _observed_estimate(),
        organization_id="org-1")


def test_fully_matching_estimate_is_verified():
    result = _verify()
    assert result["status"] == "verified"
    assert result["effect"] == "observed"
    assert result["mismatches"] == []
    assert result["missing_fields"] == []
    assert result["observed_remote_id"] == "est-1"


def test_id_and_total_only_is_incomplete_not_verified():
    result = _verify(observed={"estimate_id": "est-1", "total": "200.00"})
    assert result["status"] == "incomplete"
    assert result["effect"] == "observed"
    missing = set(result["missing_fields"])
    assert {"customer_id", "currency_code", "date", "reference_number",
            "line_items"} <= missing


def test_wrong_customer_is_a_mismatch():
    result = _verify(observed=_observed_estimate(customer_id="customer-2"))
    assert result["status"] == "mismatch"
    assert any(item["field"] == "customer_id"
               for item in result["mismatches"])


def test_wrong_currency_and_date_are_mismatches():
    result = _verify(observed=_observed_estimate(
        currency_code="CAD", date="2026-12-01"))
    fields = {item["field"] for item in result["mismatches"]}
    assert {"currency_code", "date"} <= fields


def test_wrong_item_with_same_total_is_a_mismatch():
    observed = _observed_estimate(line_items=[{
        "line_item_id": "line-1", "item_id": "B",
        "quantity": "1", "rate": "200.00", "account_id": "acct-1",
        "unit": "ea", "pack_size": "1",
    }])
    result = _verify(observed=observed)
    assert result["status"] == "mismatch"
    assert any("identity" in item["field"] for item in result["mismatches"])


def test_wrong_quantity_or_rate_with_same_total_is_a_mismatch():
    observed = _observed_estimate(line_items=[{
        "line_item_id": "line-1", "item_id": "A",
        "quantity": "1", "rate": "200.00", "account_id": "acct-1",
        "unit": "ea", "pack_size": "1",
    }])
    result = _verify(observed=observed)
    fields = {item["field"] for item in result["mismatches"]}
    assert "line_items[0].quantity" in fields
    assert "line_items[0].rate" in fields


def test_missing_expected_line_is_a_mismatch_when_lines_are_partial():
    expected = _expected_estimate(line_items=[
        {"item_id": "A", "quantity": "1", "rate": "100.00"},
        {"item_id": "B", "quantity": "1", "rate": "100.00"},
    ])
    observed = _observed_estimate(line_items=[
        {"item_id": "A", "quantity": "1", "rate": "100.00"},
    ])
    result = _verify(expected=expected, observed=observed)
    assert result["status"] == "mismatch"
    assert any("line_items[1].identity" in item["field"]
               for item in result["mismatches"])


def test_extra_observed_line_is_a_mismatch():
    observed = _observed_estimate(line_items=[
        {"item_id": "A", "quantity": "2", "rate": "100.00",
         "account_id": "acct-1", "unit": "ea", "pack_size": "1"},
        {"item_id": "B", "quantity": "1", "rate": "50.00",
         "account_id": "acct-1", "unit": "ea", "pack_size": "1"},
    ])
    result = _verify(observed=observed)
    assert result["status"] == "mismatch"
    assert any(item["field"] == "line_items.extra"
               for item in result["mismatches"])


def test_changed_discount_and_tax_are_mismatches():
    expected = _expected_estimate(
        tax_total="10.00",
        line_items=[{"item_id": "A", "quantity": "2", "rate": "100.00",
                     "discount_percent": "5", "tax_percentage": "5"}])
    observed = _observed_estimate(
        tax_total="10.00",
        line_items=[{"item_id": "A", "quantity": "2", "rate": "100.00",
                     "discount_amount": "12.00", "tax_percentage": "0"}])
    result = _verify(expected=expected, observed=observed)
    fields = {item["field"] for item in result["mismatches"]}
    assert "line_items[0].discount" in fields
    assert "line_items[0].tax.percent" in fields


def test_equivalent_percentage_and_amount_discount_is_accepted():
    expected = _expected_estimate(line_items=[
        {"item_id": "A", "quantity": "2", "rate": "100.00",
         "discount_percent": "5"}])
    observed = _observed_estimate(line_items=[
        {"item_id": "A", "quantity": "2", "rate": "100.00",
         "discount_amount": "10.00"}])
    result = _verify(expected=expected, observed=observed)
    assert result["status"] == "verified", result


def test_equivalent_decimal_formatting_and_reordered_lines_are_accepted():
    expected = _expected_estimate(line_items=[
        {"item_id": "A", "quantity": "2", "rate": "100.00"},
        {"item_id": "B", "quantity": "3", "rate": "50.00"},
    ])
    observed = _observed_estimate(line_items=[
        {"item_id": "B", "quantity": "3.000", "rate": "50.0"},
        {"item_id": "A", "quantity": "2.00", "rate": "100.000"},
    ])
    result = _verify(expected=expected, observed=observed)
    assert result["status"] == "verified", result


def test_duplicate_lines_are_a_multiset_not_a_set():
    expected = _expected_estimate(line_items=[
        {"item_id": "A", "quantity": "1", "rate": "100.00"},
        {"item_id": "A", "quantity": "2", "rate": "100.00"},
    ])
    observed = _observed_estimate(line_items=[
        {"item_id": "A", "quantity": "2", "rate": "100.00"},
        {"item_id": "A", "quantity": "1", "rate": "100.00"},
    ])
    assert _verify(expected=expected, observed=observed)["status"] == "verified"

    missing_duplicate = _observed_estimate(line_items=[
        {"item_id": "A", "quantity": "1", "rate": "100.00"},
    ])
    assert _verify(expected=expected, observed=missing_duplicate)[
        "status"] == "mismatch"


def _expected_bill():
    proposal = {
        "document_total": "120.00",
        "line_subtotal": "120.00",
        "tax_total": "0.00",
        "credit_total": "0.00",
    }
    payload = {
        "vendor_id": "vendor-1", "currency_code": "USD",
        "date": "2026-11-01", "due_date": "2026-12-01",
        "reference_number": "INV-1", "bill_number": "INV-1",
        "line_items": [
            {"name": "Parts", "quantity": "2", "rate": "50.00",
             "account_id": "acct-1"},
            {"name": "Freight", "quantity": "1", "rate": "20.00",
             "account_id": "acct-2"},
        ],
    }
    return proposal, payload


def _observed_bill():
    proposal, payload = _expected_bill()
    return {
        "bill_id": "bill-1", "bill_number": "INV-1",
        "reference_number": "INV-1", "vendor_id": "vendor-1",
        "date": "2026-11-01", "due_date": "2026-12-01",
        "currency_code": "USD", "total": "120.00",
        "sub_total": "120.00", "tax_total": "0.00",
        "discount_total": "0.00",
        "line_items": [
            {"line_item_id": "l1", "name": "Parts", "quantity": "2.00",
             "rate": "50.000", "account_id": "acct-1"},
            {"line_item_id": "l2", "name": "Freight", "quantity": "1",
             "rate": "20.00", "account_id": "acct-2"},
        ],
    }


def test_bill_full_match_and_wrong_vendor_line():
    proposal, payload = _expected_bill()
    result = verify_bill_readback(
        proposal, payload, _observed_bill(), organization_id="org-1")
    assert result["status"] == "verified"

    wrong = _observed_bill()
    wrong["vendor_id"] = "vendor-2"
    wrong["line_items"][0]["rate"] = "49.00"
    result = verify_bill_readback(
        proposal, payload, wrong, organization_id="org-1")
    fields = {item["field"] for item in result["mismatches"]}
    assert "vendor_id" in fields
    assert "line_items[0].rate" in fields


def test_bill_sparse_readback_is_incomplete():
    proposal, payload = _expected_bill()
    result = verify_bill_readback(
        proposal, payload, {"bill_id": "bill-1", "total": "120.00"},
        organization_id="org-1")
    assert result["status"] == "incomplete"
    assert "vendor_id" in result["missing_fields"]
    assert "line_items" in result["missing_fields"]
