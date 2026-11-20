"""Synthetic transport tests for private Stripe allocation lineage evidence.

The fixtures are inline and served through ``httpx.MockTransport``. No test
touches the network, environment credentials, or live Stripe objects.
"""

import asyncio
import copy
import json
import sys
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

import httpx
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.integrations.adapters.stripe import StripeAdapter  # noqa: E402


ACCESS_TOKEN = "fixture-lineage-only"

ACCOUNT = {
    "object": "account",
    "id": "acct_fixture",
}

INVOICE = {
    "object": "invoice",
    "id": "in_fixture",
    "status": "paid",
    "amount_remaining": 0,
    "amount_paid": 12345,
    "currency": "usd",
    "livemode": False,
}

FIRST_PAYMENT = {
    "object": "invoice_payment",
    "id": "inpay_pi",
    "invoice": "in_fixture",
    "status": "paid",
    "amount_paid": 10000,
    "currency": "usd",
    "livemode": False,
    "payment": {
        "type": "payment_intent",
        "payment_intent": "pi_shared",
    },
}

SECOND_PAYMENT = {
    "object": "invoice_payment",
    "id": "inpay_charge",
    "invoice": "in_fixture",
    "status": "paid",
    "amount_paid": 2345,
    "currency": "usd",
    "livemode": False,
    "payment": {
        "type": "charge",
        "charge": "ch_direct",
    },
}

INTENT = {
    "object": "payment_intent",
    "id": "pi_shared",
    "status": "succeeded",
    "amount": 12000,
    "amount_received": 12000,
    "currency": "usd",
    "livemode": False,
    "latest_charge": "ch_from_pi",
}

PI_CHARGE = {
    "object": "charge",
    "id": "ch_from_pi",
    "status": "succeeded",
    "captured": True,
    "paid": True,
    "refunded": False,
    "amount_refunded": 0,
    "disputed": False,
    "amount": 12000,
    "currency": "usd",
    "livemode": False,
    "payment_intent": "pi_shared",
    "balance_transaction": "txn_from_pi",
}

DIRECT_CHARGE = {
    "object": "charge",
    "id": "ch_direct",
    "status": "succeeded",
    "captured": True,
    "paid": True,
    "refunded": False,
    "amount_refunded": 0,
    "disputed": False,
    "amount": 2345,
    "currency": "usd",
    "livemode": False,
    "payment_intent": None,
    "balance_transaction": "txn_direct",
}

PAIRS = [
    {"charge_id": "ch_from_pi", "balance_transaction_id": "txn_from_pi"},
    {"charge_id": "ch_direct", "balance_transaction_id": "txn_direct"},
]

LOOKUP_KWARGS = {
    "expected_account_id": "acct_fixture",
    "invoice_id": "in_fixture",
    "currency": "usd",
    "expected_amount_minor_units": 12345,
    "expected_livemode": False,
}

ACCOUNT_PATHS = ["/v1/account"]
INVOICE_PATHS = ACCOUNT_PATHS + ["/v1/invoices/in_fixture"]
ALLOCATION_PATHS = INVOICE_PATHS + [
    "/v1/invoice_payments",
    "/v1/invoice_payments",
]
PI_PATHS = ALLOCATION_PATHS + ["/v1/payment_intents/pi_shared"]
PI_CHARGE_PATHS = PI_PATHS + ["/v1/charges/ch_from_pi"]
DIRECT_CHARGE_PATHS = PI_CHARGE_PATHS + ["/v1/charges/ch_direct"]


CASES = [
    pytest.param("exact_lineage", None, DIRECT_CHARGE_PATHS, id="exact_lineage"),
    pytest.param(
        "wrong_account",
        "account id does not match",
        ACCOUNT_PATHS,
        id="wrong_account",
    ),
    pytest.param(
        "wrong_invoice",
        "invoice id does not match",
        INVOICE_PATHS,
        id="wrong_invoice",
    ),
    pytest.param(
        "payment_intent_id_mismatch",
        "payment intent id does not match",
        PI_PATHS,
        id="payment_intent_id_mismatch",
    ),
    pytest.param(
        "payment_intent_not_succeeded",
        "not in succeeded status",
        PI_PATHS,
        id="payment_intent_not_succeeded",
    ),
    pytest.param(
        "payment_intent_wrong_currency",
        "currency does not match",
        PI_PATHS,
        id="payment_intent_wrong_currency",
    ),
    pytest.param(
        "payment_intent_wrong_mode",
        "livemode does not match",
        PI_PATHS,
        id="payment_intent_wrong_mode",
    ),
    pytest.param(
        "payment_intent_unsupported_amount",
        "does not support",
        PI_PATHS,
        id="payment_intent_unsupported_amount",
    ),
    pytest.param(
        "payment_intent_received_exceeds_amount",
        "received amount exceeds",
        PI_PATHS,
        id="payment_intent_received_exceeds_amount",
    ),
    pytest.param(
        "payment_intent_missing_latest_charge",
        "has no latest charge",
        PI_PATHS,
        id="payment_intent_missing_latest_charge",
    ),
    pytest.param(
        "payment_intent_malformed_latest_charge",
        "latest charge reference is malformed",
        PI_PATHS,
        id="payment_intent_malformed_latest_charge",
    ),
    pytest.param(
        "charge_id_mismatch",
        "charge id does not match",
        PI_CHARGE_PATHS,
        id="charge_id_mismatch",
    ),
    pytest.param(
        "charge_not_succeeded",
        "not in succeeded status",
        PI_CHARGE_PATHS,
        id="charge_not_succeeded",
    ),
    pytest.param(
        "charge_not_captured",
        "not captured",
        PI_CHARGE_PATHS,
        id="charge_not_captured",
    ),
    pytest.param(
        "charge_not_paid",
        "not paid",
        PI_CHARGE_PATHS,
        id="charge_not_paid",
    ),
    pytest.param(
        "charge_refunded",
        "has been refunded",
        PI_CHARGE_PATHS,
        id="charge_refunded",
    ),
    pytest.param(
        "charge_partially_refunded",
        "has been refunded",
        PI_CHARGE_PATHS,
        id="charge_partially_refunded",
    ),
    pytest.param(
        "charge_disputed",
        "is disputed",
        PI_CHARGE_PATHS,
        id="charge_disputed",
    ),
    pytest.param(
        "charge_missing_refunded",
        "charge.refunded must be an explicit boolean",
        PI_CHARGE_PATHS,
        id="charge_missing_refunded",
    ),
    pytest.param(
        "charge_missing_amount_refunded",
        "charge.amount_refunded must be a non-negative integer minor-unit amount",
        PI_CHARGE_PATHS,
        id="charge_missing_amount_refunded",
    ),
    pytest.param(
        "charge_missing_disputed",
        "charge.disputed must be an explicit boolean",
        PI_CHARGE_PATHS,
        id="charge_missing_disputed",
    ),
    pytest.param(
        "direct_charge_missing_refunded",
        "charge.refunded must be an explicit boolean",
        DIRECT_CHARGE_PATHS,
        id="direct_charge_missing_refunded",
    ),
    pytest.param(
        "direct_charge_missing_amount_refunded",
        "charge.amount_refunded must be a non-negative integer minor-unit amount",
        DIRECT_CHARGE_PATHS,
        id="direct_charge_missing_amount_refunded",
    ),
    pytest.param(
        "direct_charge_missing_disputed",
        "charge.disputed must be an explicit boolean",
        DIRECT_CHARGE_PATHS,
        id="direct_charge_missing_disputed",
    ),
    pytest.param(
        "charge_wrong_currency",
        "currency does not match",
        PI_CHARGE_PATHS,
        id="charge_wrong_currency",
    ),
    pytest.param(
        "charge_wrong_mode",
        "livemode does not match",
        PI_CHARGE_PATHS,
        id="charge_wrong_mode",
    ),
    pytest.param(
        "charge_backreference_mismatch",
        "does not reference the expected payment intent",
        PI_CHARGE_PATHS,
        id="charge_backreference_mismatch",
    ),
    pytest.param(
        "charge_amount_mismatch_intent",
        "does not match the payment intent amount",
        PI_CHARGE_PATHS,
        id="charge_amount_mismatch_intent",
    ),
    pytest.param(
        "direct_charge_amount_mismatch",
        "does not match the expected amount",
        DIRECT_CHARGE_PATHS,
        id="direct_charge_amount_mismatch",
    ),
    pytest.param(
        "direct_charge_missing_balance_transaction",
        "has no balance transaction",
        DIRECT_CHARGE_PATHS,
        id="direct_charge_missing_balance_transaction",
    ),
    pytest.param(
        "direct_charge_malformed_balance_transaction",
        "balance transaction reference is malformed",
        DIRECT_CHARGE_PATHS,
        id="direct_charge_malformed_balance_transaction",
    ),
    pytest.param(
        "truncated_invoice_payment_page",
        "Stripe evidence request failed",
        ALLOCATION_PATHS,
        id="truncated_invoice_payment_page",
    ),
]


def _build_case(case_id):
    account = copy.deepcopy(ACCOUNT)
    invoice = copy.deepcopy(INVOICE)
    first_payment = copy.deepcopy(FIRST_PAYMENT)
    second_payment = copy.deepcopy(SECOND_PAYMENT)
    intent = copy.deepcopy(INTENT)
    pi_charge = copy.deepcopy(PI_CHARGE)
    direct_charge = copy.deepcopy(DIRECT_CHARGE)
    second_page_status = 200

    if case_id == "wrong_account":
        account["id"] = "acct_foreign"
    elif case_id == "wrong_invoice":
        invoice["id"] = "in_foreign"
    elif case_id == "payment_intent_id_mismatch":
        intent["id"] = "pi_foreign"
    elif case_id == "payment_intent_not_succeeded":
        intent["status"] = "requires_action"
    elif case_id == "payment_intent_wrong_currency":
        intent["currency"] = "cad"
    elif case_id == "payment_intent_wrong_mode":
        intent["livemode"] = True
    elif case_id == "payment_intent_unsupported_amount":
        intent["amount"] = 9999
        intent["amount_received"] = 9999
    elif case_id == "payment_intent_received_exceeds_amount":
        intent["amount_received"] = intent["amount"] + 1
    elif case_id == "payment_intent_missing_latest_charge":
        intent.pop("latest_charge")
    elif case_id == "payment_intent_malformed_latest_charge":
        intent["latest_charge"] = {
            "object": "invoice",
            "id": "ch_from_pi",
        }
    elif case_id == "charge_id_mismatch":
        pi_charge["id"] = "ch_foreign"
    elif case_id == "charge_not_succeeded":
        pi_charge["status"] = "pending"
    elif case_id == "charge_not_captured":
        pi_charge["captured"] = False
    elif case_id == "charge_not_paid":
        pi_charge["paid"] = False
    elif case_id == "charge_refunded":
        pi_charge["refunded"] = True
    elif case_id == "charge_partially_refunded":
        pi_charge["amount_refunded"] = 1
    elif case_id == "charge_disputed":
        pi_charge["disputed"] = True
    elif case_id == "charge_missing_refunded":
        pi_charge.pop("refunded")
    elif case_id == "charge_missing_amount_refunded":
        pi_charge.pop("amount_refunded")
    elif case_id == "charge_missing_disputed":
        pi_charge.pop("disputed")
    elif case_id == "direct_charge_missing_refunded":
        direct_charge.pop("refunded")
    elif case_id == "direct_charge_missing_amount_refunded":
        direct_charge.pop("amount_refunded")
    elif case_id == "direct_charge_missing_disputed":
        direct_charge.pop("disputed")
    elif case_id == "charge_wrong_currency":
        pi_charge["currency"] = "cad"
    elif case_id == "charge_wrong_mode":
        pi_charge["livemode"] = True
    elif case_id == "charge_backreference_mismatch":
        pi_charge["payment_intent"] = "pi_foreign"
    elif case_id == "charge_amount_mismatch_intent":
        pi_charge["amount"] = intent["amount"] + 1
    elif case_id == "direct_charge_amount_mismatch":
        direct_charge["amount"] = 2344
    elif case_id == "direct_charge_missing_balance_transaction":
        direct_charge.pop("balance_transaction")
    elif case_id == "direct_charge_malformed_balance_transaction":
        direct_charge["balance_transaction"] = {
            "object": "charge",
            "id": "txn_direct",
        }
    elif case_id == "truncated_invoice_payment_page":
        second_page_status = 503
    elif case_id != "exact_lineage":
        raise AssertionError(f"Unknown lineage control: {case_id}")

    return {
        "account": account,
        "invoice": invoice,
        "first_payment": first_payment,
        "second_payment": second_payment,
        "intent": intent,
        "pi_charge": pi_charge,
        "direct_charge": direct_charge,
        "second_page_status": second_page_status,
    }


def _json_response(url, payload, status=200):
    return httpx.Response(
        status,
        json=payload,
        request=httpx.Request("GET", url),
    )


class FakeStripeClient:
    """Minimal async client serving the synthetic two-payment lineage replay."""

    def __init__(self, case):
        self.case = case
        self.paths = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc_info):
        return None

    async def get(self, url, params=None, headers=None, **_kwargs):
        endpoint = urlparse(url)
        assert endpoint.scheme == "https"
        assert endpoint.netloc == "api.stripe.com"
        self.paths.append(endpoint.path)

        assert headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"
        assert headers["Stripe-Version"] == "2026-10-28.endive"

        if endpoint.path == "/v1/account":
            return _json_response(url, self.case["account"])

        if endpoint.path == "/v1/invoices/in_fixture":
            return _json_response(url, self.case["invoice"])

        if endpoint.path == "/v1/payment_intents/pi_shared":
            return _json_response(url, self.case["intent"])

        if endpoint.path == "/v1/charges/ch_from_pi":
            return _json_response(url, self.case["pi_charge"])

        if endpoint.path == "/v1/charges/ch_direct":
            return _json_response(url, self.case["direct_charge"])

        if endpoint.path == "/v1/invoice_payments":
            assert params["invoice"] == "in_fixture"
            assert params["status"] == "paid"
            assert params["limit"] == 100

            first_page = "starting_after" not in params
            if first_page:
                payment = self.case["first_payment"]
            else:
                assert params["starting_after"] == "inpay_pi"
                if self.case["second_page_status"] != 200:
                    return _json_response(
                        url,
                        {"error": {"message": "fixture outage"}},
                        status=self.case["second_page_status"],
                    )
                payment = self.case["second_payment"]

            return _json_response(
                url,
                {
                    "object": "list",
                    "has_more": first_page,
                    "data": [copy.deepcopy(payment)],
                },
            )

        raise AssertionError(f"Unexpected Stripe endpoint {endpoint.path}")


async def _invoke(
    case, method_name="_get_invoice_payment_allocation_lineage_evidence"
):
    adapter = StripeAdapter(None, "fixture-workspace")
    adapter._access_token = ACCESS_TOKEN
    client = FakeStripeClient(case)

    with patch(
        "core.integrations.adapters.stripe.httpx.AsyncClient",
        return_value=client,
    ):
        method = getattr(adapter, method_name)
        return await method(**LOOKUP_KWARGS), client


async def _run_case(case_id, expected_error, expected_paths):
    case = _build_case(case_id)
    if expected_error is None:
        evidence, client = await _invoke(case)
        assert evidence["evidence_type"] == (
            "stripe_invoice_payment_allocation_lineage"
        )
        assert evidence["account_id"] == "acct_fixture"
        assert evidence["invoice_id"] == "in_fixture"
        assert evidence["currency"] == "usd"
        assert evidence["livemode"] is False
        assert evidence["amount_minor_units"] == 12345
        assert evidence["invoice_payment_ids"] == ["inpay_pi", "inpay_charge"]
        assert evidence["invoice_payment_count"] == 2
        assert evidence["charge_balance_transaction_pairs"] == PAIRS
        assert evidence["pairs"] == PAIRS
        assert evidence["pair_count"] == 2
        assert evidence["charge_ids"] == ["ch_from_pi", "ch_direct"]
        assert evidence["balance_transaction_ids"] == [
            "txn_from_pi",
            "txn_direct",
        ]
        assert evidence["payments"][0] == {
            "invoice_payment_id": "inpay_pi",
            "amount_paid_minor_units": 10000,
            "payment_type": "payment_intent",
            "payment_intent_id": "pi_shared",
            "charge_id": "ch_from_pi",
            "balance_transaction_id": "txn_from_pi",
        }
        assert evidence["payments"][1] == {
            "invoice_payment_id": "inpay_charge",
            "amount_paid_minor_units": 2345,
            "payment_type": "charge",
            "payment_intent_id": None,
            "charge_id": "ch_direct",
            "balance_transaction_id": "txn_direct",
        }
        assert evidence["stripe_api_version"] == "2026-10-28.endive"
        assert ACCESS_TOKEN not in json.dumps(evidence)
        assert "pi_shared" not in json.dumps(evidence["charge_balance_transaction_pairs"])
    else:
        adapter = StripeAdapter(None, "fixture-workspace")
        adapter._access_token = ACCESS_TOKEN
        client = FakeStripeClient(case)
        with patch(
            "core.integrations.adapters.stripe.httpx.AsyncClient",
            return_value=client,
        ):
            with pytest.raises(ValueError) as exc_info:
                await adapter._get_invoice_payment_allocation_lineage_evidence(
                    **LOOKUP_KWARGS
                )
        message = str(exc_info.value)
        assert expected_error in message
        assert ACCESS_TOKEN not in message

    assert client.paths == expected_paths


@pytest.mark.parametrize("case_id,expected_error,expected_paths", CASES)
def test_stripe_invoice_allocation_lineage(
    case_id, expected_error, expected_paths
):
    asyncio.run(_run_case(case_id, expected_error, expected_paths))


def test_public_allocation_response_is_unchanged():
    async def run():
        evidence, client = await _invoke(
            _build_case("exact_lineage"),
            "get_invoice_payment_allocation_evidence",
        )
        assert evidence == {
            "evidence_type": "stripe_invoice_payment_allocation",
            "account_id": "acct_fixture",
            "invoice_id": "in_fixture",
            "currency": "usd",
            "amount_minor_units": 12345,
            "livemode": False,
            "invoice_payment_ids": ["inpay_pi", "inpay_charge"],
            "invoice_payment_count": 2,
            "paid_allocation_subtotal": 12345,
            "paid_allocation_subtotal_minor_units": 12345,
            "paid_amount_minor_units": 12345,
            "stripe_api_version": "2026-10-28.endive",
        }
        assert client.paths == INVOICE_PATHS + [
            "/v1/invoice_payments",
            "/v1/invoice_payments",
        ]
        assert "reference" not in json.dumps(evidence)
        assert ACCESS_TOKEN not in json.dumps(evidence)

    asyncio.run(run())
