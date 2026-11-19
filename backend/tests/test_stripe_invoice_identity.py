import os
import sys
import unittest
from unittest.mock import patch

import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.integrations.adapters.stripe import (  # noqa: E402
    _STRIPE_INVOICE_ALLOCATION_API_VERSION,
    StripeAdapter,
)

ACCESS_TOKEN = "sk_test_invoice_identity"
ACCOUNT_ID = "acct_test_identity"
INVOICE_ID = "in_test_identity"
CURRENCY = "usd"
TOTAL_MINOR_UNITS = 12345
INVOICE_NUMBER = "INV-0007"


def _account_payload():
    return {
        "id": ACCOUNT_ID,
        "object": "account",
        "email": "owner@example.com",
    }


def _invoice_payload():
    return {
        "id": INVOICE_ID,
        "object": "invoice",
        "currency": "usd",
        "livemode": False,
        "total": TOTAL_MINOR_UNITS,
        "number": INVOICE_NUMBER,
        # These fields are deliberately present to prove they are not used as
        # payment/settlement proof and are not echoed to the caller.
        "status": "open",
        "paid": False,
        "amount_paid": 0,
        "amount_remaining": TOTAL_MINOR_UNITS,
        "customer": "cus_private",
        "customer_email": "payer@example.com",
        "payment_intent": "pi_private",
        "charge": "ch_private",
    }


class StripeInvoiceIdentityPreviewTests(unittest.IsolatedAsyncioTestCase):
    def _call_kwargs(self, **overrides):
        values = {
            "expected_account_id": ACCOUNT_ID,
            "invoice_id": INVOICE_ID,
            "currency": CURRENCY,
            "expected_total_minor_units": TOTAL_MINOR_UNITS,
            "expected_livemode": False,
        }
        values.update(overrides)
        return values

    def _handler(self, *, account=None, invoice=None, requests=None):
        account_payload = _account_payload() if account is None else account
        invoice_payload = _invoice_payload() if invoice is None else invoice
        if requests is None:
            requests = []

        def handler(request):
            requests.append(request)
            if request.url.path == "/v1/account":
                return httpx.Response(200, json=account_payload)
            if request.url.path == f"/v1/invoices/{INVOICE_ID}":
                return httpx.Response(200, json=invoice_payload)
            return httpx.Response(
                404,
                json={"error": {"message": "unexpected path"}},
            )

        return handler, requests

    async def _invoke(self, handler, *, token=ACCESS_TOKEN, **kwargs):
        adapter = StripeAdapter(db=None, workspace_id="ws_test")
        adapter._access_token = token
        original_async_client = httpx.AsyncClient

        def client_factory(*args, **client_kwargs):
            client_kwargs["transport"] = httpx.MockTransport(handler)
            return original_async_client(*args, **client_kwargs)

        with patch(
            "core.integrations.adapters.stripe.httpx.AsyncClient",
            new=client_factory,
        ):
            return await adapter.get_invoice_identity_preview(**kwargs)

    async def test_returns_only_exact_identity_facts_after_account_probe(self):
        handler, requests = self._handler()

        result = await self._invoke(handler, **self._call_kwargs())

        self.assertEqual(
            result,
            {
                "account_id": ACCOUNT_ID,
                "invoice_id": INVOICE_ID,
                "currency": CURRENCY,
                "total_minor_units": TOTAL_MINOR_UNITS,
                "livemode": False,
                "invoice_number": INVOICE_NUMBER,
            },
        )
        self.assertEqual(
            [request.url.path for request in requests],
            ["/v1/account", f"/v1/invoices/{INVOICE_ID}"],
        )
        for request in requests:
            self.assertEqual(request.method, "GET")
            self.assertEqual(
                request.headers.get("Authorization"),
                f"Bearer {ACCESS_TOKEN}",
            )
            self.assertEqual(
                request.headers.get("Stripe-Version"),
                _STRIPE_INVOICE_ALLOCATION_API_VERSION,
            )
            self.assertEqual(request.url.query, b"")

    async def test_requires_access_token_before_any_request(self):
        handler, requests = self._handler()

        with self.assertRaisesRegex(ValueError, "access token"):
            await self._invoke(handler, token=None, **self._call_kwargs())

        self.assertEqual(requests, [])

    async def test_rejects_invalid_explicit_inputs_before_any_request(self):
        cases = [
            ("account id", {"expected_account_id": ""}, "expected_account_id"),
            ("invoice id", {"invoice_id": "in_../bad"}, "invoice_id"),
            ("currency", {"currency": "US"}, "currency"),
            (
                "float total",
                {"expected_total_minor_units": 1.5},
                "expected_total_minor_units",
            ),
            (
                "negative total",
                {"expected_total_minor_units": -1},
                "expected_total_minor_units",
            ),
            (
                "boolean total",
                {"expected_total_minor_units": True},
                "expected_total_minor_units",
            ),
            ("livemode", {"expected_livemode": "test"}, "expected_livemode"),
        ]

        for label, overrides, expected_message in cases:
            with self.subTest(label=label):
                handler, requests = self._handler()
                with self.assertRaisesRegex(ValueError, expected_message):
                    await self._invoke(handler, **self._call_kwargs(**overrides))
                self.assertEqual(requests, [])

    async def test_rejects_wrong_account_without_reading_invoice(self):
        account = _account_payload()
        account["id"] = "acct_other"
        handler, requests = self._handler(account=account)

        with self.assertRaisesRegex(ValueError, "account id"):
            await self._invoke(handler, **self._call_kwargs())

        self.assertEqual([request.url.path for request in requests], ["/v1/account"])

    async def test_rejects_wrong_invoice_id(self):
        invoice = _invoice_payload()
        invoice["id"] = "in_other"
        handler, _ = self._handler(invoice=invoice)

        with self.assertRaisesRegex(ValueError, "invoice id"):
            await self._invoke(handler, **self._call_kwargs())

    async def test_rejects_non_invoice_object(self):
        invoice = _invoice_payload()
        invoice["object"] = "payment_intent"
        handler, _ = self._handler(invoice=invoice)

        with self.assertRaisesRegex(ValueError, "invoice object"):
            await self._invoke(handler, **self._call_kwargs())

    async def test_rejects_wrong_currency_mode_or_total(self):
        cases = [
            ("currency", "currency", "eur", "currency"),
            ("mode", "livemode", True, "mode"),
            ("total", "total", TOTAL_MINOR_UNITS + 1, "total"),
        ]

        for label, field, value, expected_message in cases:
            with self.subTest(label=label):
                invoice = _invoice_payload()
                invoice[field] = value
                handler, _ = self._handler(invoice=invoice)
                with self.assertRaisesRegex(ValueError, expected_message):
                    await self._invoke(handler, **self._call_kwargs())

    async def test_rejects_malformed_invoice_total(self):
        for label, value in (
            ("missing", None),
            ("string", "12345"),
            ("boolean", True),
            ("negative", -1),
        ):
            with self.subTest(label=label):
                invoice = _invoice_payload()
                if label == "missing":
                    del invoice["total"]
                else:
                    invoice["total"] = value
                handler, _ = self._handler(invoice=invoice)
                with self.assertRaisesRegex(ValueError, "invoice.total"):
                    await self._invoke(handler, **self._call_kwargs())


if __name__ == "__main__":
    unittest.main()
