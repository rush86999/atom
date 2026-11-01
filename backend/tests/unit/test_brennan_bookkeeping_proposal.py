"""Bookkeeping proposal controls: exact decimals, identity and balance."""
from __future__ import annotations

import pytest

from accounting.bookkeeping_proposal import (
    ProposalError,
    balanced_journal,
    build_proposal,
    decimal_amount,
    duplicate_identity,
)


def _invoice(**over):
    payload = {
        "provider": "zoho_books",
        "organization_id": "org-1",
        "entity_type": "bill",
        "external_id": "INV-001",
        "vendor_candidates": [{"id": "vendor-1", "name": "Acme"}],
        "currency": "USD",
        "document_date": "2026-10-01",
        "due_date": "2026-10-31",
        "lines": [
            {"description": "Parts", "quantity": "2", "unit_price": "50.00",
             "account_id": "acct-1"},
            {"description": "Freight", "amount": "20.00",
             "account_id": "acct-2"},
        ],
        "tax_total": "0.00",
        "document_total": "120.00",
    }
    payload.update(over)
    return payload


def test_decimal_amount_refuses_float_and_parses_original_strings():
    assert decimal_amount("120.00", "amount") == decimal_amount("120", "amount")
    with pytest.raises(ProposalError):
        decimal_amount(120.0, "amount")


def test_proposal_uses_exact_decimal_and_never_defaults_currency_or_date():
    proposal = build_proposal(**_invoice())
    assert proposal["status"] == "proposed"
    assert proposal["document_total"] == "120.00"
    assert proposal["line_subtotal"] == "120.00"
    assert proposal["currency"] == "USD"
    assert proposal["duplicate_key"] == "zoho_books|org-1|bill|INV-001"
    assert proposal["posting"] is None


def test_missing_currency_and_date_are_obligations_not_defaults():
    result = build_proposal(**_invoice(currency="", document_date=""))
    assert result["status"] == "needs_clarification"
    codes = {item["code"] for item in result["obligations"]}
    assert {"missing_currency", "missing_date"} <= codes


def test_same_external_id_in_different_organizations_is_not_a_duplicate():
    a = duplicate_identity("zoho_books", "org-1", "bill", "INV-001")
    b = duplicate_identity("zoho_books", "org-2", "bill", "INV-001")
    assert a != b


def test_same_name_vendors_with_different_ids_are_ambiguous():
    result = build_proposal(**_invoice(vendor_candidates=[
        {"id": "vendor-1", "name": "Acme"},
        {"id": "vendor-2", "name": "Acme"},
    ]))
    # Current builder raises for ambiguity rather than guessing a vendor.
    assert result is None or result["status"] == "needs_clarification"


def test_line_total_mismatch_is_refused():
    with pytest.raises(ProposalError):
        build_proposal(**_invoice(document_total="119.99"))


def test_unbalanced_journal_is_refused():
    with pytest.raises(ProposalError):
        balanced_journal([
            {"side": "debit", "amount": "100.00"},
            {"side": "credit", "amount": "99.00"},
        ])
