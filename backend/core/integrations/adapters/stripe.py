"""
Stripe Integration Adapter

Provides OAuth-based integration with Stripe for payment and billing operations.
"""

import logging
import os
import re
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

logger = logging.getLogger(__name__)

# This evidence read is deliberately pinned to the version that defines the
# invoice-payment allocation shape it relies on.  Older adapter methods keep
# using their existing (unpinned) request behavior.
_STRIPE_INVOICE_ALLOCATION_API_VERSION = "2026-10-28.endive"
_STRIPE_INVOICE_PAYMENT_PAGE_LIMIT = 100
_STRIPE_INVOICE_PAYMENT_MAX_PAGES = 1000

_STRIPE_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,255}$")
_ISO_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")


class StripeAdapter:
    """
    Adapter for Stripe OAuth integration.

    Supports:
    - OAuth 2.0 authentication
    - Payment and charge management
    - Customer and subscription operations
    - Invoice and billing access
    """

    def __init__(self, db, workspace_id: str):
        self.db = db
        self.workspace_id = workspace_id
        self.service_name = "stripe"
        self.base_url = "https://api.stripe.com/v1"

        # OAuth credentials from environment
        self.client_id = os.getenv("STRIPE_CLIENT_ID")
        self.client_secret = os.getenv("STRIPE_SECRET_KEY")
        self.redirect_uri = os.getenv("STRIPE_REDIRECT_URI")

        # Token storage
        self._access_token: Optional[str] = None
        _refresh_token: Optional[str] = None
        _stripe_user_id: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    async def get_oauth_url(self) -> str:
        """
        Generate Stripe OAuth authorization URL.

        Returns:
            Authorization URL to redirect user to Stripe OAuth consent screen
        """
        if not self.client_id:
            raise ValueError("STRIPE_CLIENT_ID not configured")

        # Stripe OAuth endpoint
        auth_url = "https://connect.stripe.com/oauth/authorize"

        # Build authorization URL
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "read_write",
            "state": self.workspace_id,  # Use workspace_id as state
        }

        auth_url_with_params = f"{auth_url}?{urlencode(params)}"

        logger.info(f"Generated Stripe OAuth URL for workspace {self.workspace_id}")
        return auth_url_with_params

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange OAuth authorization code for access token.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Token response with access_token, refresh_token, stripe_user_id, etc.
        """
        if not self.client_id or not self.client_secret:
            raise ValueError("Stripe OAuth credentials not configured")

        token_url = "https://connect.stripe.com/oauth/token"

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, data=data)
                response.raise_for_status()

                token_data = response.json()

                # Store tokens
                self._access_token = token_data.get("access_token")
                _refresh_token = token_data.get("refresh_token")
                _stripe_user_id = token_data.get("stripe_user_id")

                logger.info(f"Successfully obtained Stripe access token for workspace {self.workspace_id}")
                return token_data

        except httpx.HTTPStatusError as e:
            logger.error(f"Stripe token exchange failed: {e}")
            raise

    async def test_connection(self) -> bool:
        """
        Test the Stripe API connection.

        Returns:
            True if connection successful, False otherwise
        """
        if not self._access_token:
            return False

        try:
            async with httpx.AsyncClient() as client:
                # Test by getting account info
                response = await client.get(
                    f"{self.base_url}/account",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    }
                )
                response.raise_for_status()

                logger.info(f"Stripe connection test successful for workspace {self.workspace_id}")
                return True

        except Exception as e:
            logger.error(f"Stripe connection test failed: {e}")
            return False

    async def get_customers(self, limit: int = 20, starting_after: str = None) -> List[Dict[str, Any]]:
        """
        Retrieve Stripe customers.

        Args:
            limit: Maximum number of results
            starting_after: Cursor for pagination

        Returns:
            List of customer objects
        """
        if not self._access_token:
            raise ValueError("Stripe access token not available")

        try:
            params = {"limit": limit}
            if starting_after:
                params["starting_after"] = starting_after

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/customers",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    params=params
                )
                response.raise_for_status()

                data = response.json()
                customers = data.get("data", [])

                logger.info(f"Retrieved {len(customers)} Stripe customers for workspace {self.workspace_id}")
                return customers

        except Exception as e:
            logger.error(f"Failed to retrieve Stripe customers: {e}")
            raise

    async def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """
        Retrieve a specific Stripe customer by ID.

        Args:
            customer_id: Stripe customer ID

        Returns:
            Customer details
        """
        if not self._access_token:
            raise ValueError("Stripe access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/customers/{customer_id}",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    }
                )
                response.raise_for_status()

                customer = response.json()

                logger.info(f"Retrieved Stripe customer {customer_id} for workspace {self.workspace_id}")
                return customer

        except Exception as e:
            logger.error(f"Failed to retrieve Stripe customer {customer_id}: {e}")
            raise

    async def create_customer(self, name: str = None, email: str = None,
                             description: str = None, **metadata) -> Dict[str, Any]:
        """
        Create a new Stripe customer.

        Args:
            name: Customer name
            email: Customer email
            description: Customer description
            **metadata: Additional metadata

        Returns:
            Created customer object
        """
        if not self._access_token:
            raise ValueError("Stripe access token not available")

        try:
            customer_data = {}
            if name:
                customer_data["name"] = name
            if email:
                customer_data["email"] = email
            if description:
                customer_data["description"] = description
            if metadata:
                customer_data["metadata"] = metadata

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/customers",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    json=customer_data
                )
                response.raise_for_status()

                customer = response.json()

                logger.info(f"Created Stripe customer {customer.get('id')} for workspace {self.workspace_id}")
                return customer

        except Exception as e:
            logger.error(f"Failed to create Stripe customer: {e}")
            raise

    async def get_charges(self, limit: int = 20, created: Dict[str, int] = None) -> List[Dict[str, Any]]:
        """
        Retrieve Stripe charges.

        Args:
            limit: Maximum number of results
            created: Date range filter {"gte": timestamp, "lte": timestamp}

        Returns:
            List of charge objects
        """
        if not self._access_token:
            raise ValueError("Stripe access token not available")

        try:
            params = {"limit": limit}
            if created:
                for key, value in created.items():
                    params[f"created[{key}]"] = value

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/charges",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    params=params
                )
                response.raise_for_status()

                data = response.json()
                charges = data.get("data", [])

                logger.info(f"Retrieved {len(charges)} Stripe charges for workspace {self.workspace_id}")
                return charges

        except Exception as e:
            logger.error(f"Failed to retrieve Stripe charges: {e}")
            raise

    async def list_charges_paged(
        self, limit: int = 25, starting_after: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve one page of Stripe charges WITH pagination visibility.

        Stripe list responses carry ``has_more`` and page by ``starting_after=<last
        object id>`` — get_charges drops both, so a 100K-charge account looks
        exhausted after the first page. Returns
        ``{"data": [...], "has_more": bool, "next_page_token": str|None}``
        where ``next_page_token`` is the last charge id to resume from
        (Stripe's own cursor spelling).
        """
        if not self._access_token:
            raise ValueError("Stripe access token not available")

        try:
            params: Dict[str, Any] = {"limit": max(1, min(int(limit), 100))}
            if starting_after:
                params["starting_after"] = starting_after

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/charges",
                    headers={"Authorization": f"Bearer {self._access_token}"},
                    params=params,
                )
                response.raise_for_status()

                data = response.json()
                charges = data.get("data", [])
                has_more = bool(data.get("has_more"))
                next_token = charges[-1].get("id") if has_more and charges else None
                return {
                    "data": charges,
                    "has_more": has_more,
                    "next_page_token": next_token,
                }

        except Exception as e:
            logger.error(f"Failed to retrieve Stripe charges (paged): {e}")
            raise

    async def search_charges(
        self, query: str, limit: int = 25,
    ) -> Dict[str, Any]:
        """
        Server-side Stripe charge search (GET /v1/charges/search).

        Stripe's Search API matches the query server-side (email, customer,
        amount ranges, free text) over the WHOLE account — the previous
        pattern (list the newest N charges, filter client-side) could only
        ever find matches inside that newest page. Query strings with
        Stripe's ``key:"value"`` syntax pass through; plain terms are
        matched as free text by Stripe.

        Returns the same paged shape as list_charges_paged
        (``next_page_token`` is the ``next_page`` cursor from the search
        response).
        """
        if not self._access_token:
            raise ValueError("Stripe access token not available")

        try:
            params = {"query": str(query or "").strip(), "limit": max(1, min(int(limit), 100))}
            if not params["query"]:
                return {"data": [], "has_more": False, "next_page_token": None}

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/charges/search",
                    headers={"Authorization": f"Bearer {self._access_token}"},
                    params=params,
                )
                response.raise_for_status()

                data = response.json()
                return {
                    "data": data.get("data", []),
                    "has_more": bool(data.get("has_more")),
                    "next_page_token": data.get("next_page"),
                }

        except Exception as e:
            logger.error(f"Failed to search Stripe charges: {e}")
            raise

    async def create_charge(self, amount: int, currency: str, customer: str = None,
                           description: str = None, **metadata) -> Dict[str, Any]:
        """
        Create a new Stripe charge.

        Args:
            amount: Amount in cents/pennies
            currency: Currency code (e.g., "usd")
            customer: Customer ID
            description: Charge description
            **metadata: Additional metadata

        Returns:
            Created charge object
        """
        if not self._access_token:
            raise ValueError("Stripe access token not available")

        try:
            charge_data = {
                "amount": amount,
                "currency": currency,
            }
            if customer:
                charge_data["customer"] = customer
            if description:
                charge_data["description"] = description
            if metadata:
                charge_data["metadata"] = metadata

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/charges",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    json=charge_data
                )
                response.raise_for_status()

                charge = response.json()

                logger.info(f"Created Stripe charge {charge.get('id')} for workspace {self.workspace_id}")
                return charge

        except Exception as e:
            logger.error(f"Failed to create Stripe charge: {e}")
            raise

    async def get_invoices(self, limit: int = 20, customer: str = None) -> List[Dict[str, Any]]:
        """
        Retrieve Stripe invoices.

        Args:
            limit: Maximum number of results
            customer: Filter by customer ID

        Returns:
            List of invoice objects
        """
        if not self._access_token:
            raise ValueError("Stripe access token not available")

        try:
            params = {"limit": limit}
            if customer:
                params["customer"] = customer

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/invoices",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    params=params
                )
                response.raise_for_status()

                data = response.json()
                invoices = data.get("data", [])

                logger.info(f"Retrieved {len(invoices)} Stripe invoices for workspace {self.workspace_id}")
                return invoices

        except Exception as e:
            logger.error(f"Failed to retrieve Stripe invoices: {e}")
            raise

    async def get_subscriptions(self, limit: int = 20, customer: str = None) -> List[Dict[str, Any]]:
        """
        Retrieve Stripe subscriptions.

        Args:
            limit: Maximum number of results
            customer: Filter by customer ID

        Returns:
            List of subscription objects
        """
        if not self._access_token:
            raise ValueError("Stripe access token not available")

        try:
            params = {"limit": limit}
            if customer:
                params["customer"] = customer

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/subscriptions",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    params=params
                )
                response.raise_for_status()

                data = response.json()
                subscriptions = data.get("data", [])

                logger.info(f"Retrieved {len(subscriptions)} Stripe subscriptions for workspace {self.workspace_id}")
                return subscriptions

        except Exception as e:
            logger.error(f"Failed to retrieve Stripe subscriptions: {e}")
            raise

    async def create_payment_intent(self, amount: int, currency: str, customer: str = None,
                                   metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create a payment intent for Stripe payments.

        Args:
            amount: Amount in cents/pennies
            currency: Currency code (e.g., "usd")
            customer: Customer ID
            metadata: Additional metadata

        Returns:
            Created payment intent object
        """
        if not self._access_token:
            raise ValueError("Stripe access token not available")

        try:
            intent_data = {
                "amount": amount,
                "currency": currency,
            }
            if customer:
                intent_data["customer"] = customer
            if metadata:
                intent_data["metadata"] = metadata

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/payment_intents",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    json=intent_data
                )
                response.raise_for_status()

                intent = response.json()

                logger.info(f"Created Stripe payment intent {intent.get('id')} for workspace {self.workspace_id}")
                return intent

        except Exception as e:
            logger.error(f"Failed to create Stripe payment intent: {e}")
            raise

    @staticmethod
    def _require_stripe_identifier(value: Any, field: str) -> str:
        if not isinstance(value, str) or not _STRIPE_SAFE_ID_RE.fullmatch(value):
            raise ValueError(
                f"{field} must be a non-empty, URL-safe Stripe identifier"
            )
        return value

    @staticmethod
    def _require_iso_currency(value: Any, field: str) -> str:
        if not isinstance(value, str) or not _ISO_CURRENCY_RE.fullmatch(value):
            raise ValueError(f"{field} must be a three-letter ISO currency code")
        return value.lower()

    @staticmethod
    def _require_minor_units(value: Any, field: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{field} must be a non-negative integer minor-unit amount")
        return value

    @staticmethod
    def _require_bool(value: Any, field: str) -> bool:
        if not isinstance(value, bool):
            raise ValueError(f"{field} must be an explicit boolean")
        return value

    @staticmethod
    def _optional_bool(container: Dict[str, Any], key: str, field: str) -> Optional[bool]:
        if key not in container:
            return None
        return StripeAdapter._require_bool(container[key], field)

    @staticmethod
    def _require_matching_currency(container: Dict[str, Any], currency: str) -> None:
        actual = container.get("currency")
        if (
            not isinstance(actual, str)
            or not _ISO_CURRENCY_RE.fullmatch(actual)
            or actual.lower() != currency
        ):
            raise ValueError("Stripe currency does not match the expected currency")

    @staticmethod
    def _require_matching_livemode(container: Dict[str, Any], livemode: bool) -> None:
        actual = container.get("livemode")
        if not isinstance(actual, bool) or actual != livemode:
            raise ValueError("Stripe livemode does not match the expected mode")

    async def _stripe_evidence_get(
        self,
        client: httpx.AsyncClient,
        path: str,
        headers: Dict[str, str],
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            request_kwargs: Dict[str, Any] = {"headers": headers}
            if params is not None:
                request_kwargs["params"] = params
            response = await client.get(
                f"{self.base_url}{path}",
                **request_kwargs,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise ValueError(f"Stripe evidence request failed for {path}: {exc}") from exc
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Stripe returned malformed JSON for {path}: {exc}") from exc

        if not isinstance(payload, dict):
            raise ValueError(f"Stripe returned a non-object response for {path}")
        return payload

    def _validate_stripe_invoice_allocation(
        self,
        invoice: Dict[str, Any],
        invoice_id: str,
        currency: str,
        expected_amount_minor_units: int,
        expected_livemode: bool,
    ) -> None:
        if invoice.get("id") != invoice_id:
            raise ValueError("Stripe invoice id does not match the expected invoice")

        if "object" in invoice and invoice.get("object") != "invoice":
            raise ValueError("Stripe response is not an invoice object")

        if invoice.get("status") != "paid":
            raise ValueError("Stripe invoice is not in paid status")

        paid_flag = self._optional_bool(invoice, "paid", "invoice.paid")
        if paid_flag is False:
            raise ValueError("Stripe invoice is not paid")

        amount_remaining = invoice.get("amount_remaining")
        if (
            isinstance(amount_remaining, bool)
            or not isinstance(amount_remaining, int)
            or amount_remaining != 0
        ):
            raise ValueError("Stripe invoice has a non-zero remaining balance")

        self._require_matching_currency(invoice, currency)
        self._require_matching_livemode(invoice, expected_livemode)

        paid_out_of_band = self._optional_bool(
            invoice, "paid_out_of_band", "invoice.paid_out_of_band"
        )
        if paid_out_of_band is True:
            raise ValueError("Stripe invoice was paid out of band")

        if "amount_paid" in invoice:
            invoice_amount_paid = self._require_minor_units(
                invoice.get("amount_paid"), "invoice.amount_paid"
            )
            if invoice_amount_paid != expected_amount_minor_units:
                raise ValueError(
                    "Stripe invoice paid amount does not match the expected amount"
                )

    def _validate_stripe_invoice_payment(
        self,
        payment: Dict[str, Any],
        invoice_id: str,
        currency: str,
        expected_livemode: bool,
    ) -> Dict[str, Any]:
        payment_id = self._require_stripe_identifier(
            payment.get("id"), "invoice_payment.id"
        )

        if "object" in payment and payment.get("object") != "invoice_payment":
            raise ValueError("Stripe response is not an invoice payment object")

        invoice_reference = payment.get("invoice")
        if isinstance(invoice_reference, str):
            referenced_invoice_id = invoice_reference
        elif isinstance(invoice_reference, dict):
            if (
                "object" in invoice_reference
                and invoice_reference.get("object") != "invoice"
            ):
                raise ValueError(
                    "Stripe invoice payment has an ambiguous invoice reference"
                )
            if "currency" in invoice_reference:
                self._require_matching_currency(invoice_reference, currency)
            if "livemode" in invoice_reference:
                self._require_matching_livemode(
                    invoice_reference, expected_livemode
                )
            referenced_invoice_id = invoice_reference.get("id")
        else:
            referenced_invoice_id = None
        if referenced_invoice_id != invoice_id:
            raise ValueError(
                "Stripe invoice payment references a different invoice"
            )

        self._require_matching_currency(payment, currency)
        self._require_matching_livemode(payment, expected_livemode)

        if payment.get("status") != "paid":
            raise ValueError("Stripe invoice payment is not a completed payment")

        payment_reference = payment.get("payment")
        if not isinstance(payment_reference, dict) or not payment_reference:
            raise ValueError("Stripe invoice payment has no underlying payment")

        payment_type = payment_reference.get("type")
        if not isinstance(payment_type, str) or not payment_type:
            raise ValueError("Stripe invoice payment has an ambiguous payment type")

        if payment_type == "payment_record":
            raise ValueError(
                "Stripe invoice payment is a recorded external payment, not a "
                "Stripe-collected payment"
            )
        if payment_type == "out_of_band":
            raise ValueError("Stripe invoice payment was paid out of band")
        if payment_type not in ("charge", "payment_intent"):
            raise ValueError("Stripe invoice payment has an invalid payment type")

        reference_key = "charge" if payment_type == "charge" else "payment_intent"
        present_reference_keys = [
            key
            for key in ("charge", "payment_intent", "payment_record")
            if payment_reference.get(key) not in (None, "", {})
        ]
        if len(present_reference_keys) > 1:
            raise ValueError(
                "Stripe invoice payment has an ambiguous payment reference"
            )
        if present_reference_keys and present_reference_keys[0] != reference_key:
            raise ValueError(
                "Stripe invoice payment type does not match its payment reference"
            )

        provider_reference = payment_reference.get(reference_key)
        if isinstance(provider_reference, str):
            self._require_stripe_identifier(
                provider_reference,
                f"invoice_payment.payment.{reference_key}",
            )
        elif isinstance(provider_reference, dict):
            if (
                "object" in provider_reference
                and provider_reference.get("object") != reference_key
            ):
                raise ValueError(
                    "Stripe invoice payment has an invalid payment reference object"
                )
            self._require_stripe_identifier(
                provider_reference.get("id"),
                f"invoice_payment.payment.{reference_key}.id",
            )
        else:
            raise ValueError(
                "Stripe invoice payment is missing its underlying payment reference"
            )

        amount_paid = self._require_minor_units(
            payment.get("amount_paid"), "invoice_payment.amount_paid"
        )
        if amount_paid == 0:
            raise ValueError("Stripe invoice payment has no paid amount")

        if "amount_requested" in payment:
            amount_requested = self._require_minor_units(
                payment.get("amount_requested"), "invoice_payment.amount_requested"
            )
            if amount_requested != amount_paid:
                raise ValueError("Stripe invoice payment allocation is partial")

        return {"id": payment_id, "amount_paid": amount_paid}

    async def _collect_stripe_invoice_payments(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        invoice_id: str,
        currency: str,
        expected_livemode: bool,
        page_limit: int,
    ) -> Dict[str, Any]:
        payment_ids: List[str] = []
        seen_payment_ids = set()
        seen_cursors = set()
        paid_subtotal = 0
        starting_after: Optional[str] = None
        previous_page_had_more = False

        for _ in range(_STRIPE_INVOICE_PAYMENT_MAX_PAGES):
            params: Dict[str, Any] = {
                "invoice": invoice_id,
                "limit": page_limit,
                "status": "paid",
            }
            if starting_after is not None:
                params["starting_after"] = starting_after

            page = await self._stripe_evidence_get(
                client, "/invoice_payments", headers, params
            )

            data = page.get("data")
            if not isinstance(data, list):
                raise ValueError("Stripe invoice payments response has no data list")

            has_more = page.get("has_more")
            if not isinstance(has_more, bool):
                raise ValueError("Stripe invoice payments response has invalid pagination")

            if previous_page_had_more and not data:
                raise ValueError("Stripe invoice payments pagination contains a gap")

            if starting_after is not None and data:
                first_item = data[0]
                if isinstance(first_item, dict) and first_item.get("id") == starting_after:
                    raise ValueError(
                        "Stripe invoice payments pagination did not advance"
                    )

            for payment in data:
                if not isinstance(payment, dict):
                    raise ValueError("Stripe invoice payment entry is malformed")
                validated = self._validate_stripe_invoice_payment(
                    payment, invoice_id, currency, expected_livemode
                )
                payment_id = validated["id"]
                if payment_id in seen_payment_ids:
                    raise ValueError("Duplicate Stripe invoice payment ids")
                seen_payment_ids.add(payment_id)
                payment_ids.append(payment_id)
                paid_subtotal += validated["amount_paid"]

            if not has_more:
                return {
                    "invoice_payment_ids": payment_ids,
                    "paid_allocation_subtotal_minor_units": paid_subtotal,
                }

            if not data:
                raise ValueError("Stripe invoice payments pagination contains a gap")

            last_item = data[-1]
            last_id = last_item.get("id") if isinstance(last_item, dict) else None
            if not isinstance(last_id, str) or not last_id:
                raise ValueError("Stripe invoice payments pagination has no cursor")
            if last_id == starting_after or last_id in seen_cursors:
                raise ValueError("Stripe invoice payments pagination is cyclic")

            seen_cursors.add(last_id)
            starting_after = last_id
            previous_page_had_more = True

        raise ValueError("Stripe invoice payments pagination exceeded the safety limit")

    async def get_invoice_payment_allocation_evidence(
        self,
        *,
        expected_account_id: str,
        invoice_id: str,
        currency: str,
        expected_amount_minor_units: int,
        expected_livemode: bool,
    ) -> Dict[str, Any]:
        """
        Read exact Stripe invoice-payment allocation evidence.

        This is an opt-in, read-only verification helper. It does not settle
        payouts, admit workflows, mutate Stripe, or write local state. The
        service must supply the expected connected account, invoice, currency,
        paid amount (integer minor units), and livemode explicitly.

        Raises ``ValueError`` when the inputs or Stripe response are malformed,
        ambiguous, partial, out of band, or do not exactly match the expected
        allocation. On success it returns only the verified allocation facts.
        """
        if not self._access_token:
            raise ValueError("Stripe access token not available")

        page_limit = _STRIPE_INVOICE_PAYMENT_PAGE_LIMIT

        account_id = self._require_stripe_identifier(
            expected_account_id, "expected_account_id"
        )
        provider_invoice_id = self._require_stripe_identifier(
            invoice_id, "invoice_id"
        )
        currency_code = self._require_iso_currency(currency, "currency")
        amount_minor_units = self._require_minor_units(
            expected_amount_minor_units, "expected_amount_minor_units"
        )
        if amount_minor_units == 0:
            raise ValueError(
                "expected_amount_minor_units must be a positive paid amount"
            )
        livemode = self._require_bool(expected_livemode, "expected_livemode")

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Stripe-Version": _STRIPE_INVOICE_ALLOCATION_API_VERSION,
        }

        async with httpx.AsyncClient() as client:
            account = await self._stripe_evidence_get(client, "/account", headers)
            if account.get("id") != account_id:
                raise ValueError(
                    "Stripe account id does not match the expected account id"
                )
            if "object" in account and account.get("object") != "account":
                raise ValueError("Stripe response is not an account object")

            invoice_path = f"/invoices/{quote(provider_invoice_id, safe='')}"
            invoice = await self._stripe_evidence_get(client, invoice_path, headers)
            self._validate_stripe_invoice_allocation(
                invoice,
                provider_invoice_id,
                currency_code,
                amount_minor_units,
                livemode,
            )

            allocation = await self._collect_stripe_invoice_payments(
                client,
                headers,
                provider_invoice_id,
                currency_code,
                livemode,
                page_limit,
            )

        payment_ids = allocation["invoice_payment_ids"]
        if not payment_ids:
            raise ValueError("Stripe invoice has no invoice payment allocations")

        paid_subtotal = allocation["paid_allocation_subtotal_minor_units"]
        if paid_subtotal != amount_minor_units:
            raise ValueError(
                "Stripe paid invoice allocation subtotal does not match the expected amount"
            )

        return {
            "evidence_type": "stripe_invoice_payment_allocation",
            "account_id": account_id,
            "invoice_id": provider_invoice_id,
            "currency": currency_code,
            "amount_minor_units": amount_minor_units,
            "livemode": livemode,
            "invoice_payment_ids": payment_ids,
            "invoice_payment_count": len(payment_ids),
            "paid_allocation_subtotal": paid_subtotal,
            "paid_allocation_subtotal_minor_units": paid_subtotal,
            "paid_amount_minor_units": paid_subtotal,
            "stripe_api_version": _STRIPE_INVOICE_ALLOCATION_API_VERSION,
        }
