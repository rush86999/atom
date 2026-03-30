"""
Stripe Integration Adapter

Provides OAuth-based integration with Stripe for payment and billing operations.
"""

import logging
import os
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


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
