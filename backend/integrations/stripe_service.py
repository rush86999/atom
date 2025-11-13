"""
Stripe Service
Complete Stripe payment processing and financial management service
"""

import os
import json
import time
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from loguru import logger


class StripeService:
    """Stripe API service for payment processing and financial management"""

    def __init__(self):
        self.api_base_url = "https://api.stripe.com/v1"
        self.timeout = 60
        self.max_retries = 3
        self.retry_delay = 1

    def _get_headers(self, access_token: str) -> Dict[str, str]:
        """Get headers for Stripe API requests"""
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "ATOM-Agent/1.0",
        }

    def _make_request(
        self,
        method: str,
        endpoint: str,
        access_token: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make authenticated request to Stripe API with retry logic"""
        url = f"{self.api_base_url}/{endpoint}"
        headers = self._get_headers(access_token)

        for attempt in range(self.max_retries):
            try:
                if method.upper() == "GET":
                    response = requests.get(
                        url, headers=headers, params=params, timeout=self.timeout
                    )
                elif method.upper() == "POST":
                    response = requests.post(
                        url, headers=headers, data=data, timeout=self.timeout
                    )
                elif method.upper() == "DELETE":
                    response = requests.delete(
                        url, headers=headers, timeout=self.timeout
                    )
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"Stripe API request failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                raise

    def list_payments(
        self,
        access_token: str,
        limit: int = 30,
        customer: Optional[str] = None,
        status: Optional[str] = None,
        created: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """List Stripe payments with filtering"""
        params = {"limit": limit}
        if customer:
            params["customer"] = customer
        if status:
            params["status"] = status
        if created:
            if "gte" in created:
                params["created[gte]"] = created["gte"]
            if "lte" in created:
                params["created[lte]"] = created["lte"]

        return self._make_request("GET", "charges", access_token, params=params)

    def get_payment(self, access_token: str, payment_id: str) -> Dict[str, Any]:
        """Get specific payment by ID"""
        return self._make_request("GET", f"charges/{payment_id}", access_token)

    def create_payment(
        self,
        access_token: str,
        amount: int,
        currency: str = "usd",
        customer: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Create a new payment"""
        data = {
            "amount": amount,
            "currency": currency,
        }
        if customer:
            data["customer"] = customer
        if description:
            data["description"] = description
        if metadata:
            for key, value in metadata.items():
                data[f"metadata[{key}]"] = str(value)

        return self._make_request("POST", "charges", access_token, data=data)

    def list_customers(
        self,
        access_token: str,
        limit: int = 30,
        email: Optional[str] = None,
        created: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """List Stripe customers with filtering"""
        params = {"limit": limit}
        if email:
            params["email"] = email
        if created:
            if "gte" in created:
                params["created[gte]"] = created["gte"]
            if "lte" in created:
                params["created[lte]"] = created["lte"]

        return self._make_request("GET", "customers", access_token, params=params)

    def get_customer(self, access_token: str, customer_id: str) -> Dict[str, Any]:
        """Get specific customer by ID"""
        return self._make_request("GET", f"customers/{customer_id}", access_token)

    def create_customer(
        self,
        access_token: str,
        email: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Create a new customer"""
        data = {"email": email}
        if name:
            data["name"] = name
        if description:
            data["description"] = description
        if metadata:
            for key, value in metadata.items():
                data[f"metadata[{key}]"] = str(value)

        return self._make_request("POST", "customers", access_token, data=data)

    def update_customer(
        self,
        access_token: str,
        customer_id: str,
        name: Optional[str] = None,
        email: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Update customer information"""
        data = {}
        if name:
            data["name"] = name
        if email:
            data["email"] = email
        if description:
            data["description"] = description
        if metadata:
            for key, value in metadata.items():
                data[f"metadata[{key}]"] = str(value)

        return self._make_request(
            "POST", f"customers/{customer_id}", access_token, data=data
        )

    def list_subscriptions(
        self,
        access_token: str,
        limit: int = 30,
        customer: Optional[str] = None,
        status: Optional[str] = None,
        created: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """List Stripe subscriptions with filtering"""
        params = {"limit": limit}
        if customer:
            params["customer"] = customer
        if status:
            params["status"] = status
        if created:
            if "gte" in created:
                params["created[gte]"] = created["gte"]
            if "lte" in created:
                params["created[lte]"] = created["lte"]

        return self._make_request("GET", "subscriptions", access_token, params=params)

    def get_subscription(
        self, access_token: str, subscription_id: str
    ) -> Dict[str, Any]:
        """Get specific subscription by ID"""
        return self._make_request(
            "GET", f"subscriptions/{subscription_id}", access_token
        )

    def create_subscription(
        self,
        access_token: str,
        customer: str,
        items: List[Dict],
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Create a new subscription"""
        data = {
            "customer": customer,
        }

        # Add subscription items
        for i, item in enumerate(items):
            if "price" in item:
                data[f"items[{i}][price]"] = item["price"]
            if "quantity" in item:
                data[f"items[{i}][quantity]"] = str(item["quantity"])

        if metadata:
            for key, value in metadata.items():
                data[f"metadata[{key}]"] = str(value)

        return self._make_request("POST", "subscriptions", access_token, data=data)

    def cancel_subscription(
        self, access_token: str, subscription_id: str
    ) -> Dict[str, Any]:
        """Cancel a subscription"""
        return self._make_request(
            "DELETE", f"subscriptions/{subscription_id}", access_token
        )

    def list_products(
        self, access_token: str, limit: int = 30, active: bool = True
    ) -> Dict[str, Any]:
        """List Stripe products"""
        params = {"limit": limit, "active": str(active).lower()}
        return self._make_request("GET", "products", access_token, params=params)

    def get_product(self, access_token: str, product_id: str) -> Dict[str, Any]:
        """Get specific product by ID"""
        return self._make_request("GET", f"products/{product_id}", access_token)

    def create_product(
        self,
        access_token: str,
        name: str,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Create a new product"""
        data = {"name": name}
        if description:
            data["description"] = description
        if metadata:
            for key, value in metadata.items():
                data[f"metadata[{key}]"] = str(value)

        return self._make_request("POST", "products", access_token, data=data)

    def list_prices(
        self, access_token: str, limit: int = 30, active: bool = True
    ) -> Dict[str, Any]:
        """List Stripe prices"""
        params = {"limit": limit, "active": str(active).lower()}
        return self._make_request("GET", "prices", access_token, params=params)

    def create_price(
        self,
        access_token: str,
        product: str,
        unit_amount: int,
        currency: str = "usd",
        recurring: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Create a new price"""
        data = {
            "product": product,
            "unit_amount": unit_amount,
            "currency": currency,
        }
        if recurring:
            if "interval" in recurring:
                data["recurring[interval]"] = recurring["interval"]
            if "interval_count" in recurring:
                data["recurring[interval_count]"] = str(recurring["interval_count"])

        if metadata:
            for key, value in metadata.items():
                data[f"metadata[{key}]"] = str(value)

        return self._make_request("POST", "prices", access_token, data=data)

    def get_balance(self, access_token: str) -> Dict[str, Any]:
        """Get account balance"""
        return self._make_request("GET", "balance", access_token)

    def get_account(self, access_token: str) -> Dict[str, Any]:
        """Get account information"""
        return self._make_request("GET", "account", access_token)

    def health_check(self, access_token: str) -> Dict[str, Any]:
        """Perform health check by making a simple API call"""
        try:
            # Make a lightweight API call to verify connectivity
            response = self._make_request("GET", "balance", access_token)
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "response_time": "fast",  # Would be calculated in real implementation
                "api_version": "2023-10-16",  # Current Stripe API version
            }
        except Exception as e:
            logger.error(f"Stripe health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }


# Global service instance
stripe_service = StripeService()
