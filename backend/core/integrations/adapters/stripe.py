"""
Stripe Integration Adapter

Provides OAuth-based integration with Stripe for payment and billing operations.
"""

import logging
import os
import re
import httpx
from dataclasses import dataclass
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


@dataclass(frozen=True)
class _StripeInvoicePaymentReference:
    """Typed, private reference from one paid invoice-payment allocation.

    This deliberately carries only the provider identifiers needed to walk the
    allocation -> PaymentIntent/Charge -> balance-transaction lineage. It never
    carries a raw Stripe payload, token, or customer/payment detail.
    """

    invoice_payment_id: str
    amount_paid: int
    payment_type: str
    provider_reference_id: str


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
            provider_reference_id = self._require_stripe_identifier(
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
            provider_reference_id = self._require_stripe_identifier(
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

        reference = _StripeInvoicePaymentReference(
            invoice_payment_id=payment_id,
            amount_paid=amount_paid,
            payment_type=payment_type,
            provider_reference_id=provider_reference_id,
        )
        return {
            "id": payment_id,
            "amount_paid": amount_paid,
            "reference": reference,
        }

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
        payment_references: List[_StripeInvoicePaymentReference] = []
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
                payment_references.append(validated["reference"])
                paid_subtotal += validated["amount_paid"]

            if not has_more:
                return {
                    "invoice_payment_ids": payment_ids,
                    "payment_references": payment_references,
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

    @staticmethod
    def _stripe_charge_balance_transaction_id(
        charge: Dict[str, Any],
    ) -> str:
        transaction = charge.get("balance_transaction")
        if isinstance(transaction, str):
            try:
                return StripeAdapter._require_stripe_identifier(
                    transaction, "charge.balance_transaction"
                )
            except ValueError as exc:
                raise ValueError(
                    "Stripe charge balance transaction reference is malformed"
                ) from exc
        if isinstance(transaction, dict):
            if (
                "object" in transaction
                and transaction.get("object") != "balance_transaction"
            ):
                raise ValueError(
                    "Stripe charge balance transaction reference is malformed"
                )
            try:
                return StripeAdapter._require_stripe_identifier(
                    transaction.get("id"), "charge.balance_transaction.id"
                )
            except ValueError as exc:
                raise ValueError(
                    "Stripe charge balance transaction reference is malformed"
                ) from exc
        if transaction is None:
            raise ValueError("Stripe charge has no balance transaction")
        raise ValueError("Stripe charge balance transaction reference is malformed")

    def _validate_stripe_payment_intent_lineage(
        self,
        intent: Dict[str, Any],
        payment_intent_id: str,
        currency: str,
        expected_livemode: bool,
        allocation_amount_minor_units: int,
    ) -> Dict[str, Any]:
        if intent.get("id") != payment_intent_id:
            raise ValueError(
                "Stripe payment intent id does not match the expected payment intent"
            )
        if "object" in intent and intent.get("object") != "payment_intent":
            raise ValueError("Stripe response is not a payment intent object")

        if intent.get("status") != "succeeded":
            raise ValueError("Stripe payment intent is not in succeeded status")

        self._require_matching_currency(intent, currency)
        self._require_matching_livemode(intent, expected_livemode)

        amount = self._require_minor_units(
            intent.get("amount"), "payment_intent.amount"
        )
        if amount == 0:
            raise ValueError("Stripe payment intent has no amount")

        if "amount_received" in intent:
            amount_received = self._require_minor_units(
                intent.get("amount_received"), "payment_intent.amount_received"
            )
            if amount_received > amount:
                raise ValueError(
                    "Stripe payment intent received amount exceeds its amount"
                )
        else:
            # Stripe always includes amount_received, but synthetic fixtures
            # may only provide the intent amount. In that case the intent
            # amount is the upper bound of the money it can support.
            amount_received = amount

        if amount_received < allocation_amount_minor_units:
            raise ValueError(
                "Stripe payment intent amount does not support the invoice "
                "payment allocation"
            )

        latest_charge = intent.get("latest_charge")
        if isinstance(latest_charge, str):
            try:
                latest_charge_id = self._require_stripe_identifier(
                    latest_charge, "payment_intent.latest_charge"
                )
            except ValueError as exc:
                raise ValueError(
                    "Stripe payment intent latest charge reference is malformed"
                ) from exc
        elif isinstance(latest_charge, dict):
            if (
                "object" in latest_charge
                and latest_charge.get("object") != "charge"
            ):
                raise ValueError(
                    "Stripe payment intent latest charge reference is malformed"
                )
            try:
                latest_charge_id = self._require_stripe_identifier(
                    latest_charge.get("id"), "payment_intent.latest_charge.id"
                )
            except ValueError as exc:
                raise ValueError(
                    "Stripe payment intent latest charge reference is malformed"
                ) from exc
        elif latest_charge is None:
            raise ValueError("Stripe payment intent has no latest charge")
        else:
            raise ValueError(
                "Stripe payment intent latest charge reference is malformed"
            )

        return {
            "id": payment_intent_id,
            "amount": amount,
            "amount_received": amount_received,
            "latest_charge_id": latest_charge_id,
        }

    def _validate_stripe_charge_lineage(
        self,
        charge: Dict[str, Any],
        charge_id: str,
        currency: str,
        expected_livemode: bool,
        allocation_amount_minor_units: int,
        *,
        shared_payment_intent: bool,
        expected_payment_intent_id: Optional[str] = None,
        expected_payment_intent_amount: Optional[int] = None,
    ) -> str:
        if charge.get("id") != charge_id:
            raise ValueError("Stripe charge id does not match the expected charge")
        if "object" in charge and charge.get("object") != "charge":
            raise ValueError("Stripe response is not a charge object")

        if charge.get("status") != "succeeded":
            raise ValueError("Stripe charge is not in succeeded status")

        if self._optional_bool(charge, "captured", "charge.captured") is not True:
            raise ValueError("Stripe charge is not captured")
        if self._optional_bool(charge, "paid", "charge.paid") is not True:
            raise ValueError("Stripe charge is not paid")

        refunded = self._require_bool(charge.get("refunded"), "charge.refunded")
        if refunded:
            raise ValueError("Stripe charge has been refunded")
        amount_refunded = self._require_minor_units(
            charge.get("amount_refunded"), "charge.amount_refunded"
        )
        if amount_refunded != 0:
            raise ValueError("Stripe charge has been refunded")

        disputed = self._require_bool(charge.get("disputed"), "charge.disputed")
        if disputed:
            raise ValueError("Stripe charge is disputed")

        self._require_matching_currency(charge, currency)
        self._require_matching_livemode(charge, expected_livemode)

        amount = self._require_minor_units(charge.get("amount"), "charge.amount")
        if amount == 0:
            raise ValueError("Stripe charge has no amount")

        if shared_payment_intent:
            if amount < allocation_amount_minor_units:
                raise ValueError(
                    "Stripe charge amount does not support the invoice payment "
                    "allocation"
                )

            if expected_payment_intent_id is not None:
                reference = charge.get("payment_intent")
                if isinstance(reference, str):
                    referenced_payment_intent_id = reference
                elif isinstance(reference, dict):
                    if (
                        "object" in reference
                        and reference.get("object") != "payment_intent"
                    ):
                        raise ValueError(
                            "Stripe charge has an invalid payment intent reference"
                        )
                    referenced_payment_intent_id = reference.get("id")
                elif reference is None:
                    referenced_payment_intent_id = None
                else:
                    raise ValueError(
                        "Stripe charge has an invalid payment intent reference"
                    )

                if referenced_payment_intent_id != expected_payment_intent_id:
                    raise ValueError(
                        "Stripe charge does not reference the expected payment "
                        "intent"
                    )

            if (
                expected_payment_intent_amount is not None
                and amount != expected_payment_intent_amount
            ):
                raise ValueError(
                    "Stripe charge amount does not match the payment intent amount"
                )
        else:
            if amount != allocation_amount_minor_units:
                raise ValueError(
                    "Stripe charge amount does not match the expected amount"
                )

        return self._stripe_charge_balance_transaction_id(charge)

    async def _get_invoice_payment_allocation_lineage_evidence(
        self,
        *,
        expected_account_id: str,
        invoice_id: str,
        currency: str,
        expected_amount_minor_units: int,
        expected_livemode: bool,
    ) -> Dict[str, Any]:
        """
        Read private invoice-allocation -> charge -> balance-transaction lineage.

        This is an opt-in, read-only helper built on the exact paid
        invoice-payment allocation evidence. It follows the typed underlying
        reference from each allocation to its PaymentIntent (plus exact
        ``latest_charge``) or directly to a Charge, validates the full identity,
        state, amount, currency, and account mode, and returns the exact
        ``(charge_id, balance_transaction_id)`` pair suitable for the existing
        payout-membership check.

        A shared PaymentIntent can fund more than one invoice allocation, so an
        allocation amount is never assumed to equal the entire charge amount.
        The public allocation response is unchanged; no raw provider payload or
        credential is returned. Raises ``ValueError`` when lineage cannot be
        verified exactly.
        """
        if not self._access_token:
            raise ValueError("Stripe access token not available")

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
                _STRIPE_INVOICE_PAYMENT_PAGE_LIMIT,
            )

            payment_references = allocation.get("payment_references")
            if not isinstance(payment_references, list) or not payment_references:
                raise ValueError("Stripe invoice has no invoice payment allocations")

            paid_subtotal = allocation["paid_allocation_subtotal_minor_units"]
            if paid_subtotal != amount_minor_units:
                raise ValueError(
                    "Stripe paid invoice allocation subtotal does not match the "
                    "expected amount"
                )

            pairs: List[Dict[str, str]] = []
            payments: List[Dict[str, Any]] = []

            for reference in payment_references:
                if not isinstance(reference, _StripeInvoicePaymentReference):
                    raise ValueError("Stripe invoice payment reference is malformed")

                if reference.payment_type == "payment_intent":
                    intent_path = (
                        "/payment_intents/"
                        f"{quote(reference.provider_reference_id, safe='')}"
                    )
                    intent = await self._stripe_evidence_get(
                        client, intent_path, headers
                    )
                    intent_facts = self._validate_stripe_payment_intent_lineage(
                        intent,
                        reference.provider_reference_id,
                        currency_code,
                        livemode,
                        reference.amount_paid,
                    )

                    charge_id = intent_facts["latest_charge_id"]
                    charge_path = f"/charges/{quote(charge_id, safe='')}"
                    charge = await self._stripe_evidence_get(
                        client, charge_path, headers
                    )
                    balance_transaction_id = self._validate_stripe_charge_lineage(
                        charge,
                        charge_id,
                        currency_code,
                        livemode,
                        reference.amount_paid,
                        shared_payment_intent=True,
                        expected_payment_intent_id=reference.provider_reference_id,
                        expected_payment_intent_amount=intent_facts["amount"],
                    )
                    payment_intent_id: Optional[str] = (
                        reference.provider_reference_id
                    )
                else:
                    charge_id = reference.provider_reference_id
                    charge_path = f"/charges/{quote(charge_id, safe='')}"
                    charge = await self._stripe_evidence_get(
                        client, charge_path, headers
                    )
                    balance_transaction_id = self._validate_stripe_charge_lineage(
                        charge,
                        charge_id,
                        currency_code,
                        livemode,
                        reference.amount_paid,
                        shared_payment_intent=False,
                    )
                    payment_intent_id = None

                pairs.append(
                    {
                        "charge_id": charge_id,
                        "balance_transaction_id": balance_transaction_id,
                    }
                )
                payments.append(
                    {
                        "invoice_payment_id": reference.invoice_payment_id,
                        "amount_paid_minor_units": reference.amount_paid,
                        "payment_type": reference.payment_type,
                        "payment_intent_id": payment_intent_id,
                        "charge_id": charge_id,
                        "balance_transaction_id": balance_transaction_id,
                    }
                )

        return {
            "evidence_type": "stripe_invoice_payment_allocation_lineage",
            "account_id": account_id,
            "invoice_id": provider_invoice_id,
            "currency": currency_code,
            "livemode": livemode,
            "amount_minor_units": amount_minor_units,
            "invoice_payment_ids": allocation["invoice_payment_ids"],
            "invoice_payment_count": len(allocation["invoice_payment_ids"]),
            "paid_allocation_subtotal": paid_subtotal,
            "paid_allocation_subtotal_minor_units": paid_subtotal,
            "paid_amount_minor_units": paid_subtotal,
            "payments": payments,
            "payment_count": len(payments),
            "charge_balance_transaction_pairs": pairs,
            "pairs": pairs,
            "pair_count": len(pairs),
            "charge_ids": [pair["charge_id"] for pair in pairs],
            "balance_transaction_ids": [
                pair["balance_transaction_id"] for pair in pairs
            ],
            "balance_transaction_count": len(pairs),
            "stripe_api_version": _STRIPE_INVOICE_ALLOCATION_API_VERSION,
        }

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

    async def get_invoice_identity_preview(
        self,
        *,
        expected_account_id: str,
        invoice_id: str,
        currency: str,
        expected_total_minor_units: int,
        expected_livemode: bool,
    ) -> Dict[str, Any]:
        """
        Read exact Stripe invoice identity facts for an audited link preview.

        This is an opt-in, read-only helper. It probes the connected account and
        retrieves the one requested invoice directly; it never lists invoices,
        reads payment allocations, mutates Stripe, or writes local state.

        The caller must explicitly supply the expected connected account,
        invoice, currency, invoice total (integer minor units), and livemode.
        The ``total`` field is the invoice's documented total, independent of
        payments or settlement. Raises ``ValueError`` on malformed input or a
        response that does not exactly match all expected identity facts. On
        success it returns only the identity facts suitable for authorized
        human confirmation.
        """
        if not self._access_token:
            raise ValueError("Stripe access token not available")

        account_id = self._require_stripe_identifier(
            expected_account_id, "expected_account_id"
        )
        provider_invoice_id = self._require_stripe_identifier(
            invoice_id, "invoice_id"
        )
        currency_code = self._require_iso_currency(currency, "currency")
        total_minor_units = self._require_minor_units(
            expected_total_minor_units, "expected_total_minor_units"
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

        if invoice.get("id") != provider_invoice_id:
            raise ValueError("Stripe invoice id does not match the expected invoice")
        if invoice.get("object") != "invoice":
            raise ValueError("Stripe response is not an invoice object")

        self._require_matching_currency(invoice, currency_code)
        self._require_matching_livemode(invoice, livemode)

        actual_total = self._require_minor_units(invoice.get("total"), "invoice.total")
        if actual_total != total_minor_units:
            raise ValueError(
                "Stripe invoice total does not match the expected total"
            )

        invoice_number = invoice.get("number")
        if invoice_number is not None and (
            not isinstance(invoice_number, str) or not invoice_number
        ):
            raise ValueError("Stripe invoice number is malformed")

        return {
            "account_id": account_id,
            "invoice_id": provider_invoice_id,
            "currency": currency_code,
            "total_minor_units": total_minor_units,
            "livemode": livemode,
            "invoice_number": invoice_number,
        }

    @staticmethod
    def _stripe_balance_transaction_charge_id(
        transaction: Dict[str, Any],
    ) -> Optional[str]:
        source = transaction.get("source")
        if isinstance(source, str):
            return source
        if isinstance(source, dict):
            if "object" in source and source.get("object") != "charge":
                return None
            source_id = source.get("id")
            return source_id if isinstance(source_id, str) else None
        return None

    async def _verify_stripe_payout_membership(
        self,
        *,
        expected_account_id: str,
        payout_id: str,
        currency: str,
        expected_livemode: bool,
        expected_pairs: List[Any],
    ) -> Dict[str, Any]:
        """
        Verify exact charge/balance-transaction membership in one known payout.

        The caller supplies the trusted connected account, automatic standard
        payout id, currency, livemode, and the exact ``(charge_id,
        balance_transaction_id)`` pairs from an upstream payment proof. This
        helper reads the payout and its payout-filtered balance transactions
        directly; it does not list unrelated transactions, infer settlement,
        assert bank receipt, mutate Stripe, or write local state.

        Raises ``ValueError`` for malformed input, a payout that is not an
        automatic standard paid payout with completed reconciliation and no
        reversal or failure, non-exact account/currency/livemode facts,
        incomplete or duplicate pagination, or any supplied pair that is not
        present exactly once with the expected charge source.
        """
        if not self._access_token:
            raise ValueError("Stripe access token not available")

        account_id = self._require_stripe_identifier(
            expected_account_id, "expected_account_id"
        )
        provider_payout_id = self._require_stripe_identifier(payout_id, "payout_id")
        currency_code = self._require_iso_currency(currency, "currency")
        livemode = self._require_bool(expected_livemode, "expected_livemode")

        if (
            not isinstance(expected_pairs, (list, tuple))
            or not expected_pairs
        ):
            raise ValueError(
                "Stripe payout membership requires at least one supplied "
                "charge/balance transaction pair"
            )

        pairs: List[Dict[str, str]] = []
        expected_by_transaction_id: Dict[str, str] = {}
        seen_pair_keys = set()
        seen_charge_ids = set()
        seen_transaction_ids = set()
        for index, pair in enumerate(expected_pairs):
            if isinstance(pair, dict):
                charge_id = pair.get("charge_id")
                transaction_id = pair.get("balance_transaction_id")
            elif isinstance(pair, (list, tuple)) and len(pair) == 2:
                charge_id, transaction_id = pair
            else:
                raise ValueError(
                    f"Stripe payout membership pair {index} is malformed"
                )

            charge_id = self._require_stripe_identifier(
                charge_id, f"pairs[{index}].charge_id"
            )
            transaction_id = self._require_stripe_identifier(
                transaction_id, f"pairs[{index}].balance_transaction_id"
            )

            pair_key = (charge_id, transaction_id)
            if pair_key in seen_pair_keys:
                raise ValueError("Duplicate Stripe payout membership pair")
            if charge_id in seen_charge_ids:
                raise ValueError("Duplicate Stripe payout membership charge ids")
            if transaction_id in seen_transaction_ids:
                raise ValueError(
                    "Duplicate Stripe payout membership balance transaction ids"
                )
            seen_pair_keys.add(pair_key)
            seen_charge_ids.add(charge_id)
            seen_transaction_ids.add(transaction_id)
            expected_by_transaction_id[transaction_id] = charge_id
            pairs.append(
                {
                    "charge_id": charge_id,
                    "balance_transaction_id": transaction_id,
                }
            )

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Stripe-Version": _STRIPE_INVOICE_ALLOCATION_API_VERSION,
        }
        page_limit = _STRIPE_INVOICE_PAYMENT_PAGE_LIMIT

        async with httpx.AsyncClient() as client:
            account = await self._stripe_evidence_get(client, "/account", headers)
            if account.get("id") != account_id:
                raise ValueError(
                    "Stripe account id does not match the expected account id"
                )
            if "object" in account and account.get("object") != "account":
                raise ValueError("Stripe response is not an account object")

            payout_path = f"/payouts/{quote(provider_payout_id, safe='')}"
            payout = await self._stripe_evidence_get(
                client, payout_path, headers
            )

            if payout.get("id") != provider_payout_id:
                raise ValueError(
                    "Stripe payout id does not match the expected payout"
                )
            if "object" in payout and payout.get("object") != "payout":
                raise ValueError("Stripe response is not a payout object")

            automatic = self._require_bool(
                payout.get("automatic"), "payout.automatic"
            )
            if automatic is not True:
                raise ValueError("Stripe payout is not an automatic payout")
            if payout.get("method") != "standard":
                raise ValueError("Stripe payout method is not standard")
            if payout.get("status") != "paid":
                raise ValueError("Stripe payout is not in paid status")
            if payout.get("reconciliation_status") != "completed":
                raise ValueError("Stripe payout reconciliation is not completed")
            if payout.get("reversed_by") is not None:
                raise ValueError("Stripe payout has been reversed")
            if payout.get("failure_balance_transaction") is not None:
                raise ValueError(
                    "Stripe payout has a failure balance transaction"
                )

            self._require_matching_currency(payout, currency_code)
            self._require_matching_livemode(payout, livemode)

            observed_transaction_ids: List[str] = []
            observed_transaction_id_set = set()
            matched_transaction_ids = set()
            source_mismatch_transaction_ids = set()
            seen_cursors = set()
            starting_after: Optional[str] = None
            previous_page_had_more = False

            for _ in range(_STRIPE_INVOICE_PAYMENT_MAX_PAGES):
                params: Dict[str, Any] = {
                    "payout": provider_payout_id,
                    "limit": page_limit,
                }
                if starting_after is not None:
                    params["starting_after"] = starting_after

                page = await self._stripe_evidence_get(
                    client, "/balance_transactions", headers, params
                )

                data = page.get("data")
                if not isinstance(data, list):
                    raise ValueError(
                        "Stripe balance transactions response has no data list"
                    )

                has_more = page.get("has_more")
                if not isinstance(has_more, bool):
                    raise ValueError(
                        "Stripe balance transactions response has invalid "
                        "pagination"
                    )

                if previous_page_had_more and not data:
                    raise ValueError(
                        "Stripe balance transactions pagination contains a gap"
                    )

                if starting_after is not None and data:
                    first_item = data[0]
                    if (
                        isinstance(first_item, dict)
                        and first_item.get("id") == starting_after
                    ):
                        raise ValueError(
                            "Stripe balance transactions pagination did not "
                            "advance"
                        )

                for transaction in data:
                    if not isinstance(transaction, dict):
                        raise ValueError(
                            "Stripe balance transaction entry is malformed"
                        )

                    transaction_id = self._require_stripe_identifier(
                        transaction.get("id"), "balance_transaction.id"
                    )
                    if (
                        "object" in transaction
                        and transaction.get("object") != "balance_transaction"
                    ):
                        raise ValueError(
                            "Stripe response is not a balance transaction object"
                        )

                    self._require_matching_currency(transaction, currency_code)
                    if "livemode" in transaction:
                        self._require_matching_livemode(transaction, livemode)

                    if transaction_id in observed_transaction_id_set:
                        raise ValueError(
                            "Duplicate Stripe balance transaction ids"
                        )
                    observed_transaction_id_set.add(transaction_id)
                    observed_transaction_ids.append(transaction_id)

                    expected_charge_id = expected_by_transaction_id.get(
                        transaction_id
                    )
                    if expected_charge_id is None:
                        continue

                    charge_id = self._stripe_balance_transaction_charge_id(
                        transaction
                    )
                    transaction_type = transaction.get("type")
                    if (
                        charge_id != expected_charge_id
                        or (
                            transaction_type is not None
                            and transaction_type != "charge"
                        )
                    ):
                        source_mismatch_transaction_ids.add(transaction_id)
                    else:
                        matched_transaction_ids.add(transaction_id)

                if not has_more:
                    break

                if not data:
                    raise ValueError(
                        "Stripe balance transactions pagination contains a gap"
                    )

                last_item = data[-1]
                last_id = (
                    last_item.get("id")
                    if isinstance(last_item, dict)
                    else None
                )
                if not isinstance(last_id, str) or not last_id:
                    raise ValueError(
                        "Stripe balance transactions pagination has no cursor"
                    )
                if last_id == starting_after or last_id in seen_cursors:
                    raise ValueError(
                        "Stripe balance transactions pagination is cyclic"
                    )

                seen_cursors.add(last_id)
                starting_after = last_id
                previous_page_had_more = True
            else:
                raise ValueError(
                    "Stripe balance transactions pagination exceeded the safety "
                    "limit"
                )

        if source_mismatch_transaction_ids:
            raise ValueError(
                "Stripe balance transaction source/charge id does not match the "
                "expected charge for payout membership"
            )

        missing_pairs = [
            pair
            for pair in pairs
            if pair["balance_transaction_id"] not in matched_transaction_ids
        ]
        if missing_pairs:
            raise ValueError(
                "Stripe balance transaction is not a member of the payout "
                "(payout does not contain the expected charge balance "
                "transaction pair)"
            )

        return {
            "evidence_type": "stripe_payout_membership",
            "account_id": account_id,
            "payout_id": provider_payout_id,
            "currency": currency_code,
            "livemode": livemode,
            "charge_balance_transaction_pairs": pairs,
            "pair_count": len(pairs),
            "charge_ids": [pair["charge_id"] for pair in pairs],
            "balance_transaction_ids": observed_transaction_ids,
            "balance_transaction_count": len(observed_transaction_ids),
            "matched_balance_transaction_ids": [
                pair["balance_transaction_id"] for pair in pairs
            ],
            "stripe_api_version": _STRIPE_INVOICE_ALLOCATION_API_VERSION,
        }
