"""Standalone replay tests for Stripe invoice-payment allocation evidence.

The fixtures below are inline copies of the synthetic replay data.  The test
uses a fake ``httpx.AsyncClient`` so it never touches the environment or the
network.  Every control from the replay is represented exactly once.
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


ACCOUNT = {
    "object": "account",
    "id": "acct_fixture",
}

INVOICE = {
    "object": "invoice",
    "id": "in_fixture",
    "status": "paid",
    "amount_remaining": 0,
    "amount_due": 12345,
    "amount_paid": 12345,
    "currency": "cad",
    "livemode": False,
}

FIRST_PAYMENT = {
    "object": "invoice_payment",
    "id": "inpay_first",
    "invoice": "in_fixture",
    "status": "paid",
    "amount_paid": 10000,
    "currency": "cad",
    "livemode": False,
    "payment": {
        "type": "payment_intent",
        "payment_intent": "pi_first",
    },
}

SECOND_PAYMENT = {
    "object": "invoice_payment",
    "id": "inpay_second",
    "invoice": "in_fixture",
    "status": "paid",
    "amount_paid": 2345,
    "currency": "cad",
    "livemode": False,
    "payment": {
        "type": "payment_intent",
        "payment_intent": "pi_second",
    },
}

LOOKUP_KWARGS = {
    "expected_account_id": "acct_fixture",
    "invoice_id": "in_fixture",
    "currency": "cad",
    "expected_amount_minor_units": 12345,
    "expected_livemode": False,
}

ACCOUNT_PATHS = ["/v1/account"]
INVOICE_PATHS = ACCOUNT_PATHS + ["/v1/invoices/in_fixture"]
PAYMENT_PATHS = INVOICE_PATHS + ["/v1/invoice_payments", "/v1/invoice_payments"]


CASES = [
    pytest.param("exact_two_pages", None, PAYMENT_PATHS, id="exact_two_pages"),
    pytest.param(
        "valid_charge_reference",
        None,
        PAYMENT_PATHS,
        id="valid_charge_reference",
    ),
    pytest.param(
        "same_account_wrong_invoice",
        "invoice id does not match",
        INVOICE_PATHS,
        id="same_account_wrong_invoice",
    ),
    pytest.param(
        "wrong_provider_account",
        "account id does not match",
        ACCOUNT_PATHS,
        id="wrong_provider_account",
    ),
    pytest.param(
        "wrong_currency",
        "currency does not match",
        INVOICE_PATHS,
        id="wrong_currency",
    ),
    pytest.param(
        "live_mode_mismatch",
        "livemode does not match",
        INVOICE_PATHS,
        id="live_mode_mismatch",
    ),
    pytest.param(
        "partial_allocation",
        "allocation subtotal does not match",
        PAYMENT_PATHS,
        id="partial_allocation",
    ),
    pytest.param(
        "positive_remaining",
        "non-zero remaining balance",
        INVOICE_PATHS,
        id="positive_remaining",
    ),
    pytest.param(
        "duplicate_allocation_across_pages",
        "pagination did not advance",
        PAYMENT_PATHS,
        id="duplicate_allocation_across_pages",
    ),
    pytest.param(
        "out_of_band",
        "paid out of band",
        INVOICE_PATHS,
        id="out_of_band",
    ),
    pytest.param(
        "missing_payment_object",
        "no underlying payment",
        PAYMENT_PATHS,
        id="missing_payment_object",
    ),
    pytest.param(
        "missing_payment_intent_id",
        "missing its underlying payment reference",
        PAYMENT_PATHS,
        id="missing_payment_intent_id",
    ),
    pytest.param(
        "payment_record_paid_out_of_band_omitted",
        "recorded external payment",
        PAYMENT_PATHS,
        id="payment_record_paid_out_of_band_omitted",
    ),
    pytest.param(
        "malformed_integer_amount",
        "non-negative integer minor-unit amount",
        PAYMENT_PATHS,
        id="malformed_integer_amount",
    ),
    pytest.param(
        "truncated_after_valid_page",
        "Stripe evidence request failed",
        PAYMENT_PATHS,
        id="truncated_after_valid_page",
    ),
    pytest.param(
        "wrong_allocation_invoice",
        "references a different invoice",
        PAYMENT_PATHS,
        id="wrong_allocation_invoice",
    ),
    pytest.param(
        "unpaid_allocation",
        "not a completed payment",
        PAYMENT_PATHS,
        id="unpaid_allocation",
    ),
    pytest.param(
        "wrong_allocation_mode",
        "livemode does not match",
        PAYMENT_PATHS,
        id="wrong_allocation_mode",
    ),
    pytest.param(
        "missing_allocation_status",
        "not a completed payment",
        PAYMENT_PATHS,
        id="missing_allocation_status",
    ),
    pytest.param(
        "missing_final_pagination",
        "invalid pagination",
        PAYMENT_PATHS,
        id="missing_final_pagination",
    ),
]


def _build_case(case_id):
    """Return a fresh, independent copy of the fixture set for one control."""
    account = copy.deepcopy(ACCOUNT)
    invoice = copy.deepcopy(INVOICE)
    first = copy.deepcopy(FIRST_PAYMENT)
    second = copy.deepcopy(SECOND_PAYMENT)
    second_page_status = 200
    omit_second_has_more = False

    if case_id == "wrong_provider_account":
        account["id"] = "acct_foreign"
    elif case_id == "valid_charge_reference":
        first["payment"] = {"type": "charge", "charge": "ch_first"}
        second["payment"] = {"type": "charge", "charge": "ch_second"}
    elif case_id == "same_account_wrong_invoice":
        invoice["id"] = "in_foreign"
    elif case_id == "wrong_currency":
        invoice["currency"] = "usd"
    elif case_id == "live_mode_mismatch":
        invoice["livemode"] = True
    elif case_id == "positive_remaining":
        invoice["amount_remaining"] = 100
    elif case_id == "out_of_band":
        invoice["paid_out_of_band"] = True
        first["payment"] = {
            "type": "payment_record",
            "payment_record": "pr_manual",
        }
        second["payment"] = copy.deepcopy(first["payment"])
    elif case_id == "missing_payment_object":
        second.pop("payment")
    elif case_id == "missing_payment_intent_id":
        second["payment"] = {"type": "payment_intent"}
    elif case_id == "payment_record_paid_out_of_band_omitted":
        second["payment"] = {
            "type": "payment_record",
            "payment_record": "pr_manual",
        }
    elif case_id == "partial_allocation":
        second["amount_paid"] = 100
    elif case_id == "duplicate_allocation_across_pages":
        second["id"] = "inpay_first"
    elif case_id == "malformed_integer_amount":
        second["amount_paid"] = "2345"
    elif case_id == "truncated_after_valid_page":
        second_page_status = 503
    elif case_id == "wrong_allocation_invoice":
        second["invoice"] = "in_wrong"
    elif case_id == "unpaid_allocation":
        second["status"] = "open"
    elif case_id == "wrong_allocation_mode":
        second["livemode"] = True
    elif case_id == "missing_allocation_status":
        second.pop("status")
    elif case_id == "missing_final_pagination":
        omit_second_has_more = True
    elif case_id != "exact_two_pages":
        raise AssertionError(f"Unknown Stripe replay control: {case_id}")

    return {
        "account": account,
        "invoice": invoice,
        "first": first,
        "second": second,
        "second_page_status": second_page_status,
        "omit_second_has_more": omit_second_has_more,
    }


def _json_response(url, payload, status=200):
    return httpx.Response(
        status,
        json=payload,
        request=httpx.Request("GET", url),
    )


class FakeStripeClient:
    """Minimal async HTTP client matching the two-page Stripe replay."""

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

        assert headers["Authorization"] == "Bearer fixture-only"
        assert headers["Stripe-Version"] == "2026-10-28.endive"

        if endpoint.path == "/v1/account":
            return _json_response(url, self.case["account"])

        if endpoint.path == "/v1/invoices/in_fixture":
            return _json_response(url, self.case["invoice"])

        if endpoint.path == "/v1/invoice_payments":
            assert params["invoice"] == "in_fixture"
            assert params["status"] == "paid"
            assert params["limit"] == 100

            first_page = "starting_after" not in params
            if first_page:
                payment = self.case["first"]
            else:
                assert params["starting_after"] == "inpay_first"
                if self.case["second_page_status"] != 200:
                    return _json_response(
                        url,
                        {"error": {"message": "fixture outage"}},
                        status=self.case["second_page_status"],
                    )
                payment = self.case["second"]

            payload = {
                "object": "list",
                "has_more": first_page,
                "data": [copy.deepcopy(payment)],
            }
            if not first_page and self.case["omit_second_has_more"]:
                payload.pop("has_more")
            return _json_response(url, payload)

        raise AssertionError(f"Unexpected Stripe endpoint {endpoint.path}")


def _assert_verified_evidence(evidence):
    expected_total = FIRST_PAYMENT["amount_paid"] + SECOND_PAYMENT["amount_paid"]

    assert evidence["evidence_type"] == "stripe_invoice_payment_allocation"
    assert evidence["account_id"] == "acct_fixture"
    assert evidence["invoice_id"] == "in_fixture"
    assert evidence["currency"] == "cad"
    assert evidence["livemode"] is False
    assert evidence["amount_minor_units"] == expected_total
    assert evidence["invoice_payment_ids"] == ["inpay_first", "inpay_second"]
    assert evidence["invoice_payment_count"] == 2
    assert evidence["paid_allocation_subtotal"] == expected_total
    assert evidence["paid_allocation_subtotal_minor_units"] == expected_total
    assert evidence["paid_amount_minor_units"] == expected_total
    assert evidence["stripe_api_version"] == "2026-10-28.endive"
    assert "fixture-only" not in json.dumps(evidence)


async def _run_case(case_id, expected_error, expected_paths):
    case = _build_case(case_id)
    adapter = StripeAdapter(None, "fixture-workspace")
    adapter._access_token = "fixture-only"
    client = FakeStripeClient(case)

    with patch(
        "core.integrations.adapters.stripe.httpx.AsyncClient",
        return_value=client,
    ):
        if expected_error is None:
            evidence = await adapter.get_invoice_payment_allocation_evidence(
                **LOOKUP_KWARGS
            )
            _assert_verified_evidence(evidence)
        else:
            with pytest.raises(ValueError) as exc_info:
                await adapter.get_invoice_payment_allocation_evidence(
                    **LOOKUP_KWARGS
                )
            message = str(exc_info.value)
            assert expected_error in message
            assert "fixture-only" not in message

    assert client.paths == expected_paths


@pytest.mark.parametrize("case_id,expected_error,expected_paths", CASES)
def test_stripe_invoice_payment_allocation(case_id, expected_error, expected_paths):
    asyncio.run(_run_case(case_id, expected_error, expected_paths))
