from dataclasses import replace
from unittest.mock import AsyncMock

import pytest

from integrations import stripe_routes as route
from tests.test_stripe_invoice_connection import (
    ACCOUNT_ID, ADMIN_ID, TENANT_ID, WORKSPACE_ID, atom_harness,
)


@pytest.mark.parametrize("scenario", [
    "valid", "drift", "wrong_payout", "wrong_account", "wrong_mode",
    "wrong_pairs", "wrong_type", "unavailable",
])
def test_signed_payout_route_checks_pairs_and_binding(atom_harness, monkeypatch, scenario):
    link = route._InvoiceLinkSnapshot(
        user_id=ADMIN_ID, tenant_id=TENANT_ID, workspace_id=WORKSPACE_ID,
        local_invoice_id="synthetic-invoice", connection_id="synthetic-link",
        account_id=ACCOUNT_ID, mode="test", livemode=False, currency="usd",
        total_minor_units=123, external_invoice_id="in_fixture", restricted_key="synthetic-only",
    )
    snapshot = route._PaymentEvidenceSnapshot(link, "synthetic-binding", 1)
    requests = []

    def resolve(db, actor_id, invoice_id):
        route._resolve_active_workspace_admin_scope(db, actor_id)
        assert invoice_id == snapshot.link.local_invoice_id
        return replace(snapshot, binding_revision=2) if scenario == "drift" and requests else snapshot

    pairs = [{"charge_id": "ch_fixture", "balance_transaction_id": "txn_fixture"}]
    lineage = {
        "evidence_type": "stripe_invoice_payment_allocation_lineage",
        "account_id": ACCOUNT_ID, "invoice_id": "in_fixture", "currency": "usd",
        "livemode": False, "amount_minor_units": 123, "invoice_payment_ids": ["inpay_fixture"],
        "invoice_payment_count": 1, "paid_allocation_subtotal_minor_units": 123,
        "stripe_api_version": "fixture", "charge_balance_transaction_pairs": pairs,
    }
    membership = {
        "evidence_type": "stripe_payout_membership", "account_id": ACCOUNT_ID,
        "payout_id": "po_fixture", "currency": "usd", "livemode": False,
        "charge_balance_transaction_pairs": pairs, "pair_count": 1,
        "bank_payout_reference": {"status": "available", "value": "synthetic-private-trace",
                                  "destination_id": "ba_private_fixture", "amount_minor_units": 456},
    }

    changes = {
        "wrong_payout": {"payout_id": "po_other"},
        "wrong_account": {"account_id": "acct_other"},
        "wrong_mode": {"livemode": True},
        "wrong_pairs": {"charge_balance_transaction_pairs": [
            {"charge_id": "ch_other", "balance_transaction_id": "txn_fixture"},
        ]},
        "wrong_type": {"evidence_type": "invalid"},
        "unavailable": {"bank_payout_reference": {"status": "unavailable"}},
    }
    membership = {**membership, **changes.get(scenario, {})}

    class Adapter:
        get_invoice_payment_allocation_evidence = AsyncMock(
            return_value={**lineage, "evidence_type": "stripe_invoice_payment_allocation"})

        async def _get_invoice_payment_allocation_lineage_evidence(self, **kwargs):
            requests.append("lineage")
            assert kwargs["expected_account_id"] == ACCOUNT_ID
            assert kwargs["invoice_id"] == "in_fixture"
            return lineage

        async def _verify_stripe_payout_membership(self, **kwargs):
            requests.append("payout")
            assert kwargs["expected_pairs"] == pairs
            assert kwargs["payout_id"] == "po_fixture"
            assert kwargs["include_bank_payout_reference"] is True
            return membership

    adapter = Adapter()
    monkeypatch.setattr(route, "_resolve_payment_evidence_snapshot", resolve)
    monkeypatch.setattr(route, "_invoice_preview_adapter", lambda *_: adapter)
    path = "/api/integrations/stripe/invoice-links/synthetic-invoice/payment-evidence"
    def get(token, selector):
        return atom_harness.client.get(path, params={"payout_id": selector},
            headers={"Authorization": f"Bearer {token}"})

    default = atom_harness.client.get(path, headers={
        "Authorization": f"Bearer {atom_harness.admin_token}",
    })
    assert default.status_code == 200, default.text
    assert default.json()["evidence_scope"] == "payment_allocation_only"
    assert "payout" not in default.json()
    assert "bank_settlement" not in default.json()
    assert not requests
    assert adapter.get_invoice_payment_allocation_evidence.await_count == 1
    adapter.get_invoice_payment_allocation_evidence.reset_mock()

    denied = get(atom_harness.member_token, "po_fixture")
    assert denied.status_code == 403
    assert not requests
    invalid = get(atom_harness.admin_token, " po_fixture")
    assert invalid.status_code in {400, 422}
    assert not requests
    received = get(atom_harness.admin_token, "po_fixture")
    assert requests == ["lineage", "payout"]
    assert adapter.get_invoice_payment_allocation_evidence.await_count == 0
    if scenario not in {"valid", "unavailable"}:
        assert received.status_code == 409
    else:
        assert received.status_code == 200, received.text
        proof = received.json()["payout_proof"]
        assert proof == {
            "payout_id": "po_fixture", "membership_verified": True,
            "bank_reference_status": "unavailable" if scenario == "unavailable" else "available",
            "bank_settlement_status": "unverified",
        }
        assert {key: value for key, value in received.json().items()
                if key != "payout_proof"} == default.json()
        assert "ch_fixture" not in received.text
        assert "txn_fixture" not in received.text
        if scenario == "unavailable":
            assert "unavailable" in received.text
    assert "synthetic-private-trace" not in received.text
    assert "ba_private_fixture" not in received.text
