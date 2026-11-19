"""Mocked transport tests for Stripe payout membership evidence."""

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


ACCOUNT = {"object": "account", "id": "acct_fixture"}

PAYOUT = {
    "object": "payout",
    "id": "po_fixture",
    "amount": 12345,
    "automatic": True,
    "method": "standard",
    "status": "paid",
    "currency": "usd",
    "livemode": False,
    "balance_transaction": "txn_payout",
    "reconciliation_status": "completed",
    "reversed_by": None,
    "failure_balance_transaction": None,
}

FIRST_TRANSACTION = {
    "object": "balance_transaction",
    "id": "txn_first",
    "type": "charge",
    "source": "ch_first",
    "currency": "usd",
    "status": "available",
}

SECOND_TRANSACTION = {
    "object": "balance_transaction",
    "id": "txn_second",
    "type": "charge",
    "source": "ch_second",
    "currency": "usd",
    "status": "available",
}

PAIRS = [
    {"charge_id": "ch_first", "balance_transaction_id": "txn_first"},
    {"charge_id": "ch_second", "balance_transaction_id": "txn_second"},
]

LOOKUP_KWARGS = {
    "expected_account_id": "acct_fixture",
    "payout_id": "po_fixture",
    "currency": "usd",
    "expected_livemode": False,
    "expected_pairs": PAIRS,
}

ACCOUNT_PATHS = ["/v1/account"]
PAYOUT_PATHS = ACCOUNT_PATHS + ["/v1/payouts/po_fixture"]
TRANSACTION_PATHS = PAYOUT_PATHS + [
    "/v1/balance_transactions",
    "/v1/balance_transactions",
]

CASES = [
    pytest.param("exact_two_pages", None, TRANSACTION_PATHS, id="exact_two_pages"),
    pytest.param(
        "wrong_account",
        "account id does not match",
        ACCOUNT_PATHS,
        id="wrong_account",
    ),
    pytest.param(
        "wrong_payout",
        "payout id does not match",
        PAYOUT_PATHS,
        id="wrong_payout",
    ),
    pytest.param(
        "not_automatic",
        "not an automatic payout",
        PAYOUT_PATHS,
        id="not_automatic",
    ),
    pytest.param(
        "not_standard",
        "method is not standard",
        PAYOUT_PATHS,
        id="not_standard",
    ),
    pytest.param(
        "not_paid",
        "not in paid status",
        PAYOUT_PATHS,
        id="not_paid",
    ),
    pytest.param(
        "unreconciled",
        "reconciliation is not completed",
        PAYOUT_PATHS,
        id="unreconciled",
    ),
    pytest.param(
        "reversed",
        "has been reversed",
        PAYOUT_PATHS,
        id="reversed",
    ),
    pytest.param(
        "wrong_currency",
        "currency does not match",
        PAYOUT_PATHS,
        id="wrong_currency",
    ),
    pytest.param(
        "wrong_charge_source",
        "source/charge id does not match",
        TRANSACTION_PATHS,
        id="wrong_charge_source",
    ),
    pytest.param(
        "duplicate_transaction",
        "pagination did not advance",
        TRANSACTION_PATHS,
        id="duplicate_transaction",
    ),
    pytest.param(
        "pagination_gap",
        "pagination contains a gap",
        TRANSACTION_PATHS,
        id="pagination_gap",
    ),
    pytest.param(
        "truncated_page",
        "Stripe evidence request failed",
        TRANSACTION_PATHS,
        id="truncated_page",
    ),
]


def _build_case(case_id):
    account = copy.deepcopy(ACCOUNT)
    payout = copy.deepcopy(PAYOUT)
    first = copy.deepcopy(FIRST_TRANSACTION)
    second = copy.deepcopy(SECOND_TRANSACTION)
    second_page_status = 200
    second_page_empty = False

    if case_id == "wrong_account":
        account["id"] = "acct_foreign"
    elif case_id == "wrong_payout":
        payout["id"] = "po_foreign"
    elif case_id == "not_automatic":
        payout["automatic"] = False
    elif case_id == "not_standard":
        payout["method"] = "instant"
    elif case_id == "not_paid":
        payout["status"] = "in_transit"
    elif case_id == "unreconciled":
        payout["reconciliation_status"] = "in_progress"
    elif case_id == "reversed":
        payout["reversed_by"] = "txn_reversal"
    elif case_id == "wrong_currency":
        payout["currency"] = "cad"
    elif case_id == "wrong_charge_source":
        second["source"] = "ch_foreign"
    elif case_id == "duplicate_transaction":
        second["id"] = "txn_first"
    elif case_id == "pagination_gap":
        second_page_empty = True
    elif case_id == "truncated_page":
        second_page_status = 503
    elif case_id != "exact_two_pages":
        raise AssertionError(f"Unknown payout membership control: {case_id}")

    return {
        "account": account,
        "payout": payout,
        "first": first,
        "second": second,
        "second_page_status": second_page_status,
        "second_page_empty": second_page_empty,
    }


def _json_response(url, payload, status=200):
    return httpx.Response(
        status,
        json=payload,
        request=httpx.Request("GET", url),
    )


class FakeStripeClient:
    """Minimal async HTTP client for the two-page payout replay."""

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

        if endpoint.path == "/v1/payouts/po_fixture":
            return _json_response(url, self.case["payout"])

        if endpoint.path == "/v1/balance_transactions":
            assert params["payout"] == "po_fixture"
            assert params["limit"] == 100

            first_page = "starting_after" not in params
            if first_page:
                transaction = self.case["first"]
            else:
                assert params["starting_after"] == "txn_first"
                if self.case["second_page_status"] != 200:
                    return _json_response(
                        url,
                        {"error": {"message": "fixture outage"}},
                        status=self.case["second_page_status"],
                    )
                transaction = self.case["second"]

            data = (
                []
                if not first_page and self.case["second_page_empty"]
                else [copy.deepcopy(transaction)]
            )
            return _json_response(
                url,
                {
                    "object": "list",
                    "has_more": first_page,
                    "data": data,
                },
            )

        raise AssertionError(f"Unexpected Stripe endpoint {endpoint.path}")


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
            evidence = await adapter._verify_stripe_payout_membership(
                **LOOKUP_KWARGS
            )
            assert evidence["evidence_type"] == "stripe_payout_membership"
            assert evidence["account_id"] == "acct_fixture"
            assert evidence["payout_id"] == "po_fixture"
            assert evidence["currency"] == "usd"
            assert evidence["livemode"] is False
            assert evidence["charge_balance_transaction_pairs"] == PAIRS
            assert evidence["pair_count"] == 2
            assert evidence["balance_transaction_ids"] == [
                "txn_first",
                "txn_second",
            ]
            assert evidence["matched_balance_transaction_ids"] == [
                "txn_first",
                "txn_second",
            ]
            assert evidence["stripe_api_version"] == "2026-10-28.endive"
            assert "fixture-only" not in json.dumps(evidence)
        else:
            with pytest.raises(ValueError) as exc_info:
                await adapter._verify_stripe_payout_membership(
                    **LOOKUP_KWARGS
                )
            message = str(exc_info.value)
            assert expected_error in message
            assert "fixture-only" not in message

    assert client.paths == expected_paths


@pytest.mark.parametrize("case_id,expected_error,expected_paths", CASES)
def test_stripe_payout_membership(case_id, expected_error, expected_paths):
    asyncio.run(_run_case(case_id, expected_error, expected_paths))
