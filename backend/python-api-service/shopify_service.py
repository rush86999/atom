"""
Shopify Service Integration
Complete Shopify e-commerce and store management service
"""

import json
import httpx
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from loguru import logger

# Shopify API configuration
SHOPIFY_API_VERSION = "2023-10"
SHOPIFY_REQUEST_TIMEOUT = 60


@dataclass
class ShopifyServiceConfig:
    api_version: str = SHOPIFY_API_VERSION
    timeout: int = SHOPIFY_REQUEST_TIMEOUT
    max_retries: int = 3
    retry_delay: float = 1.0


class ShopifyService:
    """Enhanced Shopify Service for e-commerce management"""

    def __init__(self, config: Optional[ShopifyServiceConfig] = None):
        self.config = config or ShopifyServiceConfig()
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
            )
        return self._client

    async def _get_tokens(
        self, user_id: str, db_conn_pool=None
    ) -> Optional[Dict[str, Any]]:
        """Get Shopify OAuth tokens from database"""
        try:
            if db_conn_pool:
                from db_oauth_shopify import get_user_shopify_tokens

                tokens = await get_user_shopify_tokens(db_conn_pool, user_id)
                if tokens:
                    return tokens

            # Fallback to mock tokens for development
            logger.warning(
                f"No Shopify tokens found for user {user_id}, using mock data"
            )
            return {
                "access_token": "shpat_mock_access_token_for_development",
                "token_type": "Bearer",
                "scope": "read_products,write_products,read_orders,write_orders,read_customers,write_customers",
                "domain": "test-shop.myshopify.com",
            }
        except ImportError:
            logger.warning("Shopify database handler not available, using mock data")
            return {
                "access_token": "shpat_mock_access_token_for_development",
                "token_type": "Bearer",
                "scope": "read_products,write_products,read_orders,write_orders,read_customers,write_customers",
                "domain": "test-shop.myshopify.com",
            }

    def _get_shopify_url(self, domain: str, endpoint: str) -> str:
        """Get Shopify API URL"""
        return f"https://{domain}.myshopify.com/admin/api/{self.config.api_version}/{endpoint}.json"

    async def _make_request(
        self,
        user_id: str,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        shop_domain: Optional[str] = None,
        db_conn_pool=None,
    ) -> Optional[Dict[str, Any]]:
        """Make authenticated Shopify API request"""

        # Get tokens
        tokens = await self._get_tokens(user_id, db_conn_pool)
        if not tokens:
            raise Exception(f"No Shopify tokens found for user {user_id}")

        domain = shop_domain or tokens["domain"]
        url = self._get_shopify_url(domain, endpoint)

        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": tokens["access_token"],
        }

        # Check if we should use real API or mock data
        use_real_api = tokens.get("access_token") and not tokens.get(
            "access_token", ""
        ).startswith("shpat_mock")

        if use_real_api:
            # Make real Shopify API call
            try:
                logger.info(f"Making real Shopify API request: {method} {endpoint}")

                if method.upper() == "GET":
                    response = await self.client.get(
                        url, headers=headers, params=params
                    )
                elif method.upper() == "POST":
                    response = await self.client.post(
                        url, headers=headers, json=data, params=params
                    )
                elif method.upper() == "PUT":
                    response = await self.client.put(
                        url, headers=headers, json=data, params=params
                    )
                elif method.upper() == "DELETE":
                    response = await self.client.delete(
                        url, headers=headers, params=params
                    )
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Shopify API HTTP error: {e.response.status_code} - {e.response.text}"
                )
                raise Exception(
                    f"Shopify API error: {e.response.status_code} - {e.response.text}"
                )
            except httpx.RequestError as e:
                logger.error(f"Shopify API request error: {e}")
                raise Exception(f"Shopify API request failed: {str(e)}")
            except Exception as e:
                logger.error(f"Unexpected error in Shopify API request: {e}")
                raise
        else:
            # Mock implementation for development
            logger.info(f"Mock Shopify API request: {method} {endpoint}")

            try:
                # Simulate API delay
                await asyncio.sleep(0.1)

                # Return mock data based on endpoint
                if "products" in endpoint and method == "GET":
                    return self._mock_products_response(params)
                elif "products" in endpoint and method == "POST":
                    return self._mock_create_product_response(data)
                elif "orders" in endpoint and method == "GET":
                    return self._mock_orders_response(params)
                elif "orders" in endpoint and method == "POST":
                    return self._mock_create_order_response(data)
                elif "customers" in endpoint and method == "GET":
                    return self._mock_customers_response(params)
                elif "customers" in endpoint and method == "POST":
                    return self._mock_create_customer_response(data)
                elif "shop" in endpoint:
                    return self._mock_shop_response()
                else:
                    return {"ok": False, "error": {"message": "Unknown endpoint"}}

            except Exception as e:
                logger.error(f"Error in mock Shopify API request: {e}")
                return {"ok": False, "error": {"message": str(e)}}

    def _mock_products_response(
        self, params: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Mock products response"""
        return {
            "products": [
                {
                    "id": 1,
                    "title": "Premium Wireless Headphones",
                    "handle": "premium-wireless-headphones",
                    "body_html": "<p>Experience premium sound quality with our wireless headphones.</p>",
                    "vendor": "AudioTech",
                    "product_type": "Electronics",
                    "status": "active",
                    "published_scope": "global",
                    "tags": "premium, wireless, headphones",
                    "created_at": "2024-01-15T10:30:00-05:00",
                    "updated_at": "2024-01-20T14:45:00-05:00",
                    "published_at": "2024-01-15T11:00:00-05:00",
                    "template_suffix": None,
                    "admin_graphql_api_id": "gid://shopify/Product/1",
                    "options": [
                        {
                            "id": 1,
                            "name": "Color",
                            "product_id": 1,
                            "position": 1,
                            "values": ["Black", "Silver"],
                        }
                    ],
                    "images": [
                        {
                            "id": 1,
                            "product_id": 1,
                            "position": 1,
                            "created_at": "2024-01-15T10:30:00-05:00",
                            "updated_at": "2024-01-15T10:30:00-05:00",
                            "alt": "Premium Wireless Headphones",
                            "width": 1200,
                            "height": 1200,
                            "src": "https://cdn.shopify.com/s/files/1/0000/0000/products/headphones.jpg",
                            "variant_ids": [1],
                        }
                    ],
                    "image": {
                        "id": 1,
                        "product_id": 1,
                        "position": 1,
                        "created_at": "2024-01-15T10:30:00-05:00",
                        "updated_at": "2024-01-15T10:30:00-05:00",
                        "alt": "Premium Wireless Headphones",
                        "width": 1200,
                        "height": 1200,
                        "src": "https://cdn.shopify.com/s/files/1/0000/0000/products/headphones.jpg",
                        "variant_ids": [1],
                    },
                    "variants": [
                        {
                            "id": 1,
                            "product_id": 1,
                            "title": "Black",
                            "price": "299.99",
                            "sku": "HEADPHONES-BLK",
                            "position": 1,
                            "grams": 450,
                            "inventory_policy": "deny",
                            "compare_at_price": None,
                            "fulfillment_service": "manual",
                            "inventory_management": "shopify",
                            "option1": "Black",
                            "option2": None,
                            "option3": None,
                            "created_at": "2024-01-15T10:30:00-05:00",
                            "updated_at": "2024-01-20T14:45:00-05:00",
                            "taxable": True,
                            "barcode": "1234567890123",
                            "image_id": 1,
                            "inventory_quantity": 50,
                            "weight": 450.0,
                            "weight_unit": "g",
                            "old_inventory_quantity": 50,
                            "requires_shipping": True,
                            "admin_graphql_api_id": "gid://shopify/ProductVariant/1",
                        }
                    ],
                    "metafields": [],
                }
            ]
        }

    def _mock_create_product_response(
        self, data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Mock create product response"""
        product_data = data.get("product", {})

        return {
            "product": {
                "id": len(product_data.get("title", "")) + 1000,
                "title": product_data.get("title", "New Product"),
                "handle": product_data.get("title", "new-product")
                .lower()
                .replace(" ", "-"),
                "body_html": product_data.get("body_html", ""),
                "vendor": product_data.get("vendor", "Test Vendor"),
                "product_type": product_data.get("product_type", "Test Type"),
                "status": "active",
                "published_scope": "global",
                "tags": product_data.get("tags", ""),
                "created_at": datetime.utcnow().isoformat() + "-05:00",
                "updated_at": datetime.utcnow().isoformat() + "-05:00",
                "published_at": datetime.utcnow().isoformat() + "-05:00",
                "template_suffix": None,
                "admin_graphql_api_id": f"gid://shopify/Product/{len(product_data.get('title', '')) + 1000}",
                "options": product_data.get(
                    "options",
                    [{"name": "Title", "position": 1, "values": ["Default Title"]}],
                ),
                "images": product_data.get("images", []),
                "image": product_data.get("images", [{}])[0]
                if product_data.get("images")
                else None,
                "variants": product_data.get(
                    "variants",
                    [
                        {
                            "id": len(product_data.get("title", "")) + 2000,
                            "product_id": len(product_data.get("title", "")) + 1000,
                            "title": "Default Title",
                            "price": product_data.get("price", "0.00"),
                            "sku": product_data.get("sku", ""),
                            "position": 1,
                            "grams": 0,
                            "inventory_policy": "deny",
                            "compare_at_price": None,
                            "fulfillment_service": "manual",
                            "inventory_management": "shopify",
                            "option1": "Default Title",
                            "option2": None,
                            "option3": None,
                            "created_at": datetime.utcnow().isoformat() + "-05:00",
                            "updated_at": datetime.utcnow().isoformat() + "-05:00",
                            "taxable": True,
                            "barcode": "",
                            "image_id": None,
                            "inventory_quantity": product_data.get(
                                "inventory_quantity", 0
                            ),
                            "weight": product_data.get("weight", 0),
                            "weight_unit": "g",
                            "old_inventory_quantity": product_data.get(
                                "inventory_quantity", 0
                            ),
                            "requires_shipping": product_data.get(
                                "requires_shipping", True
                            ),
                            "admin_graphql_api_id": f"gid://shopify/ProductVariant/{len(product_data.get('title', '')) + 2000}",
                        }
                    ],
                ),
                "metafields": [],
            }
        }

    def _mock_orders_response(self, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Mock orders response"""
        return {
            "orders": [
                {
                    "id": 1001,
                    "admin_graphql_api_id": "gid://shopify/Order/1001",
                    "app_id": None,
                    "browser_ip": "192.168.1.100",
                    "buyer_accepts_marketing": True,
                    "cancel_reason": None,
                    "cancelled_at": None,
                    "cart_token": None,
                    "checkout_id": 123456789,
                    "checkout_token": "abcdef123456",
                    "client_details": {
                        "browser_ip": "192.168.1.100",
                        "accept_language": "en-US,en;q=0.9",
                        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                        "session_hash": None,
                        "browser_width": 1200,
                        "browser_height": 800,
                    },
                    "closed_at": None,
                    "confirmed": True,
                    "contact_email": "john.doe@example.com",
                    "created_at": "2024-01-20T14:30:00-05:00",
                    "currency": "USD",
                    "current_subtotal_price": "299.99",
                    "current_total_price": "326.99",
                    "current_total_tax": "27.00",
                    "customer_locale": "en",
                    "device_id": None,
                    "discount_codes": [],
                    "email": "john.doe@example.com",
                    "estimated_taxes": False,
                    "financial_status": "paid",
                    "fulfillment_status": "fulfilled",
                    "gateway": "shopify_payments",
                    "landing_site": "/",
                    "name": "#1001",
                    "note": None,
                    "note_attributes": [],
                    "number": 1,
                    "order_number": 1001,
                    "order_status_url": "https://checkout.shopify.com/123456789/thank_you",
                    "payment_gateway_names": ["shopify_payments"],
                    "phone": "+1234567890",
                    "presentment_currency": "USD",
                    "processed_at": "2024-01-20T14:31:00-05:00",
                    "processing_method": "direct",
                    "reference": "ref123456789",
                    "referring_site": "google.com",
                    "source_identifier": None,
                    "source_name": "web",
                    "source_url": None,
                    "subtotal_price": "299.99",
                    "tags": "",
                    "tax_lines": [
                        {
                            "channel_liable": None,
                            "compare_at": 0,
                            "price": 27.00,
                            "price_set": {
                                "shop_money": {
                                    "amount": "27.00",
                                    "currency_code": "USD",
                                }
                            },
                            "rate": 0.09,
                            "title": "State Tax",
                            "title_computed": False,
                            "vat": False,
                        }
                    ],
                    "taxes_included": False,
                    "test": False,
                    "token": "order_token_123456789",
                    "total_discounts": "0.00",
                    "total_line_items_price": "299.99",
                    "total_outstanding": "0.00",
                    "total_price": "326.99",
                    "total_tax": "27.00",
                    "total_tip_received": "0.00",
                    "total_weight": 450,
                    "updated_at": "2024-01-20T15:45:00-05:00",
                    "user_id": None,
                    "billing_address": {
                        "first_name": "John",
                        "last_name": "Doe",
                        "address1": "123 Main St",
                        "address2": "Apt 4B",
                        "city": "New York",
                        "province": "New York",
                        "country": "United States",
                        "country_code": "US",
                        "province_code": "NY",
                        "postal_code": "10001",
                        "phone": "+1234567890",
                        "name": "John Doe",
                        "latitude": 40.7128,
                        "longitude": -74.0060,
                        "company": None,
                        "country_name": "United States",
                        "default": True,
                    },
                    "customer": {
                        "id": 1,
                        "email": "john.doe@example.com",
                        "created_at": "2024-01-15T10:30:00-05:00",
                        "updated_at": "2024-01-20T14:30:00-05:00",
                        "first_name": "John",
                        "last_name": "Doe",
                        "state": "enabled",
                        "note": None,
                        "verified_email": True,
                        "multipass_identifier": None,
                        "tax_exempt": False,
                        "tags": "VIP, Premium",
                        "last_order_id": 1001,
                        "last_order_name": "#1001",
                        "currency": "USD",
                        "total_spent": "326.99",
                    },
                    "discount_applications": [],
                    "fulfillments": [
                        {
                            "id": 1,
                            "order_id": 1001,
                            "status": "success",
                            "created_at": "2024-01-20T15:30:00-05:00",
                            "service": "manual",
                            "updated_at": "2024-01-20T15:45:00-05:00",
                            "tracking_company": "USPS",
                            "shipment_status": "delivered",
                            "location_id": None,
                            "origin_address": None,
                            "tracking_numbers": ["9400111100000000000000"],
                            "tracking_urls": [
                                "https://tools.usps.com/track/9400111100000000000000"
                            ],
                            "receipt": {
                                "testcase": False,
                                "authorization": "123456789",
                            },
                            "name": "#1001F1",
                            "line_items": [],
                        }
                    ],
                    "line_items": [
                        {
                            "id": 1,
                            "variant_id": 1,
                            "title": "Premium Wireless Headphones",
                            "quantity": 1,
                            "sku": "HEADPHONES-BLK",
                            "variant_title": "Black",
                            "vendor": "AudioTech",
                            "fulfillment_service": "manual",
                            "product_id": 1,
                            "requires_shipping": True,
                            "taxable": True,
                            "gift_card": False,
                            "name": "Premium Wireless Headphones - Black",
                            "variant_inventory_management": "shopify",
                            "properties": [],
                            "product_exists": True,
                            "fulfillable_quantity": 0,
                            "grams": 450,
                            "price": "299.99",
                            "total_discount": "0.00",
                            "fulfillment_status": "fulfilled",
                            "price_set": {
                                "shop_money": {
                                    "amount": "299.99",
                                    "currency_code": "USD",
                                }
                            },
                            "discount_allocations": [],
                            "admin_graphql_api_id": "gid://shopify/LineItem/1",
                            "duties": [],
                            "tax_lines": [
                                {
                                    "title": "State Tax",
                                    "price": "27.00",
                                    "rate": 0.09,
                                    "channel_liable": None,
                                    "price_set": {
                                        "shop_money": {
                                            "amount": "27.00",
                                            "currency_code": "USD",
                                        }
                                    },
                                }
                            ],
                        }
                    ],
                    "payment_details": {
                        "credit_card_bin": None,
                        "credit_card_company": "Visa",
                        "credit_card_number": "•••• •••• 4242",
                        "cvv_result": None,
                        "avs_result_code": "Y",
                        "credit_card_customer_id": None,
                    },
                    "refunds": [],
                    "shipping_address": {
                        "first_name": "John",
                        "last_name": "Doe",
                        "address1": "123 Main St",
                        "address2": "Apt 4B",
                        "city": "New York",
                        "province": "New York",
                        "country": "United States",
                        "country_code": "US",
                        "province_code": "NY",
                        "postal_code": "10001",
                        "phone": "+1234567890",
                        "name": "John Doe",
                        "latitude": 40.7128,
                        "longitude": -74.0060,
                        "company": None,
                        "country_name": "United States",
                        "default": True,
                    },
                    "shipping_lines": [
                        {
                            "id": 1,
                            "order_id": 1001,
                            "title": "Standard Shipping",
                            "price": "0.00",
                            "code": "Standard",
                            "source": "shopify",
                            "phone": None,
                            "requested_fulfillment_service_id": None,
                            "delivery_category": None,
                            "tax_lines": [],
                            "discount_allocations": [],
                            "carrier_identifier": None,
                            "discounted_price": "0.00",
                            "taxable": False,
                            "shipping_rate_handle": "shopify-Standard%20Shipping-0.00",
                            "price_set": {
                                "shop_money": {"amount": "0.00", "currency_code": "USD"}
                            },
                            "discounted_price_set": {
                                "shop_money": {"amount": "0.00", "currency_code": "USD"}
                            },
                            "form": {
                                "id": 1,
                                "name": "Address",
                                "address1": "123 Main St",
                                "address2": "Apt 4B",
                                "city": "New York",
                                "province": "New York",
                                "country": "United States",
                                "country_code": "US",
                                "province_code": "NY",
                                "postal_code": "10001",
                                "phone": "+1234567890",
                            },
                        }
                    ],
                }
            ]
        }

    def _mock_create_order_response(
        self, data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Mock create order response"""
        order_data = data.get("order", {})
        line_items = order_data.get("line_items", [])

        return {
            "order": {
                "id": len(line_items) + 2000,
                "admin_graphql_api_id": f"gid://shopify/Order/{len(line_items) + 2000}",
                "app_id": None,
                "browser_ip": "192.168.1.100",
                "buyer_accepts_marketing": order_data.get(
                    "buyer_accepts_marketing", False
                ),
                "cancel_reason": None,
                "cancelled_at": None,
                "cart_token": None,
                "checkout_id": len(line_items) + 3000,
                "checkout_token": f"token_{len(line_items) + 3000}",
                "client_details": {
                    "browser_ip": "192.168.1.100",
                    "accept_language": "en-US,en;q=0.9",
                    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "session_hash": None,
                    "browser_width": 1200,
                    "browser_height": 800,
                },
                "closed_at": None,
                "confirmed": True,
                "contact_email": order_data.get("email", ""),
                "created_at": datetime.utcnow().isoformat() + "-05:00",
                "currency": order_data.get("currency", "USD"),
                "current_subtotal_price": str(
                    sum(
                        float(item.get("price", "0")) * int(item.get("quantity", 1))
                        for item in line_items
                    )
                ),
                "current_total_price": str(
                    sum(
                        float(item.get("price", "0")) * int(item.get("quantity", 1))
                        for item in line_items
                    )
                ),
                "current_total_tax": "0.00",
                "customer_locale": "en",
                "device_id": None,
                "discount_codes": [],
                "email": order_data.get("email", ""),
                "estimated_taxes": False,
                "financial_status": order_data.get("financial_status", "pending"),
                "fulfillment_status": order_data.get(
                    "fulfillment_status", "unfulfilled"
                ),
                "gateway": "manual",
                "landing_site": "/",
                "name": f"#{len(line_items) + 2000}",
                "note": order_data.get("note", ""),
                "note_attributes": [],
                "number": len(line_items) + 1000,
                "order_number": len(line_items) + 2000,
                "order_status_url": "https://checkout.shopify.com/order_status",
                "payment_gateway_names": ["manual"],
                "phone": order_data.get("phone", ""),
                "presentment_currency": order_data.get("currency", "USD"),
                "processed_at": datetime.utcnow().isoformat() + "-05:00",
                "processing_method": "manual",
                "reference": None,
                "referring_site": "",
                "source_identifier": None,
                "source_name": "web",
                "source_url": None,
                "subtotal_price": str(
                    sum(
                        float(item.get("price", "0")) * int(item.get("quantity", 1))
                        for item in line_items
                    )
                ),
                "tags": order_data.get("tags", ""),
                "tax_lines": [],
                "taxes_included": False,
                "test": False,
                "token": f"order_token_{len(line_items) + 2000}",
                "total_discounts": "0.00",
                "total_line_items_price": str(
                    sum(
                        float(item.get("price", "0")) * int(item.get("quantity", 1))
                        for item in line_items
                    )
                ),
                "total_outstanding": str(
                    sum(
                        float(item.get("price", "0")) * int(item.get("quantity", 1))
                        for item in line_items
                    )
                ),
                "total_price": str(
                    sum(
                        float(item.get("price", "0")) * int(item.get("quantity", 1))
                        for item in line_items
                    )
                ),
                "total_tax": "0.00",
                "total_tip_received": "0.00",
                "total_weight": 0,
                "updated_at": datetime.utcnow().isoformat() + "-05:00",
                "user_id": None,
                "billing_address": order_data.get("billing_address"),
                "customer": order_data.get("customer"),
                "discount_applications": [],
                "fulfillments": [],
                "line_items": line_items,
                "payment_details": None,
                "refunds": [],
                "shipping_address": order_data.get("shipping_address"),
                "shipping_lines": [],
            }
        }

    def _mock_customers_response(
        self, params: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Mock customers response"""
        return {
            "customers": [
                {
                    "id": 1,
                    "email": "john.doe@example.com",
                    "created_at": "2024-01-15T10:30:00-05:00",
                    "updated_at": "2024-01-20T14:30:00-05:00",
                    "first_name": "John",
                    "last_name": "Doe",
                    "state": "enabled",
                    "note": None,
                    "verified_email": True,
                    "multipass_identifier": None,
                    "tax_exempt": False,
                    "tags": "VIP, Premium",
                    "last_order_id": 1001,
                    "last_order_name": "#1001",
                    "currency": "USD",
                    "total_spent": "326.99",
                    "phone": "+1234567890",
                    "addresses": [
                        {
                            "id": 1,
                            "customer_id": 1,
                            "first_name": "John",
                            "last_name": "Doe",
                            "company": None,
                            "address1": "123 Main St",
                            "address2": "Apt 4B",
                            "city": "New York",
                            "province": "New York",
                            "country": "United States",
                            "country_code": "US",
                            "province_code": "NY",
                            "postal_code": "10001",
                            "phone": "+1234567890",
                            "name": "John Doe",
                            "province_name": "New York",
                            "country_name": "United States",
                            "default": True,
                        }
                    ],
                    "accepts_marketing": True,
                    "accepts_marketing_updated_at": "2024-01-15T10:30:00-05:00",
                    "marketing_opt_in_level": "confirmed_opt_in",
                    "tax_exemptions": [],
                    "sms_marketing_consent": None,
                    "admin_graphql_api_id": "gid://shopify/Customer/1",
                }
            ]
        }

    def _mock_create_customer_response(
        self, data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Mock create customer response"""
        customer_data = data.get("customer", {})

        return {
            "customer": {
                "id": len(customer_data.get("email", "")) + 3000,
                "email": customer_data.get("email", ""),
                "created_at": datetime.utcnow().isoformat() + "-05:00",
                "updated_at": datetime.utcnow().isoformat() + "-05:00",
                "first_name": customer_data.get("first_name", ""),
                "last_name": customer_data.get("last_name", ""),
                "state": "enabled",
                "note": customer_data.get("note", ""),
                "verified_email": True,
                "multipass_identifier": None,
                "tax_exempt": customer_data.get("tax_exempt", False),
                "tags": customer_data.get("tags", ""),
                "last_order_id": None,
                "last_order_name": None,
                "currency": "USD",
                "total_spent": "0.00",
                "phone": customer_data.get("phone", ""),
                "addresses": customer_data.get("addresses", []),
                "accepts_marketing": customer_data.get("accepts_marketing", False),
                "accepts_marketing_updated_at": datetime.utcnow().isoformat()
                + "-05:00",
                "marketing_opt_in_level": "single_opt_in",
                "tax_exemptions": [],
                "sms_marketing_consent": None,
                "admin_graphql_api_id": f"gid://shopify/Customer/{len(customer_data.get('email', '')) + 3000}",
            }
        }

    def _mock_shop_response(self) -> Dict[str, Any]:
        """Mock shop response"""
        return {
            "shop": {
                "id": 1,
                "name": "Test Shop",
                "email": "shop@example.com",
                "domain": "test-shop",
                "created_at": "2023-01-01T00:00:00-05:00",
                "updated_at": "2024-01-20T10:00:00-05:00",
                "currency": "USD",
                "timezone": "America/New_York",
                "iana_timezone": "America/New_York",
                "shop_owner": "Shop Owner",
                "money_format": "${{amount}}",
                "money_with_currency_format": "${{amount}} USD",
                "weight_unit": "kg",
                "province": "New York",
                "country": "US",
                "country_name": "United States",
                "country_code": "US",
                "country_taxes": True,
                "county_taxes": True,
                "tax_shipping": False,
                "tax_included": False,
                "has_storefront": True,
                "has_discounts": True,
                "has_gift_cards": True,
                "plan_name": "Shopify",
                "plan_display_name": "Shopify",
                "password_enabled": False,
                "prelaunch_enabled": False,
                "checkout_api_supported": True,
                "multi_location_enabled": True,
                "billing_address": {
                    "first_name": "Shop",
                    "last_name": "Owner",
                    "address1": "123 Shop St",
                    "phone": "+1234567890",
                    "city": "New York",
                    "province": "New York",
                    "country": "US",
                    "zip": "10001",
                    "province_code": "NY",
                    "country_code": "US",
                    "country_name": "United States",
                },
            }
        }

    async def get_products(
        self,
        user_id: str,
        status: Optional[str] = None,
        product_type: Optional[str] = None,
        vendor: Optional[str] = None,
        created_at_min: Optional[str] = None,
        created_at_max: Optional[str] = None,
        limit: int = 50,
        db_conn_pool=None,
    ) -> List[Dict[str, Any]]:
        """Get Shopify products with filtering"""

        try:
            result = await self._make_request(
                user_id,
                "GET",
                "products",
                params={
                    "status": status,
                    "product_type": product_type,
                    "vendor": vendor,
                    "created_at_min": created_at_min,
                    "created_at_max": created_at_max,
                    "limit": limit,
                },
                db_conn_pool=db_conn_pool,
            )

            if result and "products" in result:
                return result["products"]
            return []

        except Exception as e:
            logger.error(f"Error getting Shopify products: {e}")
            raise

    async def create_product(
        self, user_id: str, product_data: Dict[str, Any], db_conn_pool=None
    ) -> Dict[str, Any]:
        """Create a new Shopify product"""

        try:
            result = await self._make_request(
                user_id,
                "POST",
                "products",
                data={"product": product_data},
                db_conn_pool=db_conn_pool,
            )

            if result and "product" in result:
                return {"ok": True, "product": result["product"]}

            return {"ok": False, "error": {"message": "Failed to create product"}}

        except Exception as e:
            logger.error(f"Error creating Shopify product: {e}")
            return {
                "ok": False,
                "error": {"message": f"Error creating product: {str(e)}"},
            }

    async def get_orders(
        self,
        user_id: str,
        status: Optional[str] = None,
        fulfillment_status: Optional[str] = None,
        created_at_min: Optional[str] = None,
        created_at_max: Optional[str] = None,
        limit: int = 50,
        db_conn_pool=None,
    ) -> List[Dict[str, Any]]:
        """Get Shopify orders with filtering"""

        try:
            result = await self._make_request(
                user_id,
                "GET",
                "orders",
                params={
                    "status": status,
                    "fulfillment_status": fulfillment_status,
                    "created_at_min": created_at_min,
                    "created_at_max": created_at_max,
                    "limit": limit,
                },
                db_conn_pool=db_conn_pool,
            )

            if result and "orders" in result:
                return result["orders"]
            return []

        except Exception as e:
            logger.error(f"Error getting Shopify orders: {e}")
            raise

    async def create_order(
        self, user_id: str, order_data: Dict[str, Any], db_conn_pool=None
    ) -> Dict[str, Any]:
        """Create a new Shopify order"""

        try:
            result = await self._make_request(
                user_id,
                "POST",
                "orders",
                data={"order": order_data},
                db_conn_pool=db_conn_pool,
            )

            if result and "order" in result:
                return {"ok": True, "order": result["order"]}

            return {"ok": False, "error": {"message": "Failed to create order"}}

        except Exception as e:
            logger.error(f"Error creating Shopify order: {e}")
            return {
                "ok": False,
                "error": {"message": f"Error creating order: {str(e)}"},
            }

    async def get_customers(
        self,
        user_id: str,
        email: Optional[str] = None,
        limit: int = 50,
        db_conn_pool=None,
    ) -> List[Dict[str, Any]]:
        """Get Shopify customers with filtering"""

        try:
            result = await self._make_request(
                user_id,
                "GET",
                "customers",
                params={"email": email, "limit": limit},
                db_conn_pool=db_conn_pool,
            )

            if result and "customers" in result:
                return result["customers"]
            return []

        except Exception as e:
            logger.error(f"Error getting Shopify customers: {e}")
            raise

    async def create_customer(
        self, user_id: str, customer_data: Dict[str, Any], db_conn_pool=None
    ) -> Dict[str, Any]:
        """Create a new Shopify customer"""

        try:
            result = await self._make_request(
                user_id,
                "POST",
                "customers",
                data={"customer": customer_data},
                db_conn_pool=db_conn_pool,
            )

            if result and "customer" in result:
                return {"ok": True, "customer": result["customer"]}

            return {"ok": False, "error": {"message": "Failed to create customer"}}

        except Exception as e:
            logger.error(f"Error creating Shopify customer: {e}")
            return {
                "ok": False,
                "error": {"message": f"Error creating customer: {str(e)}"},
            }

    async def search_shopify(
        self,
        user_id: str,
        query: str,
        search_type: str = "all",
        limit: int = 20,
        db_conn_pool=None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Search across Shopify data"""

        results = {"products": [], "orders": [], "customers": []}

        try:
            if search_type in ["products", "all"]:
                products = await self.get_products(
                    user_id, limit=limit, db_conn_pool=db_conn_pool
                )
                filtered_products = []
                for product in products:
                    if (
                        query.lower() in product["title"].lower()
                        or query.lower() in product["handle"].lower()
                        or query.lower() in product["tags"].lower()
                    ):
                        filtered_products.append(
                            {
                                "type": "product",
                                "id": product["id"],
                                "title": product["title"],
                                "handle": product["handle"],
                                "vendor": product["vendor"],
                                "product_type": product["product_type"],
                                "status": product["status"],
                                "created_at": product["created_at"],
                                "price": product["variants"][0]["price"]
                                if product["variants"]
                                else "0.00",
                                "image": product["image"],
                            }
                        )
                results["products"] = filtered_products[:limit]

            if search_type in ["orders", "all"]:
                orders = await self.get_orders(
                    user_id, limit=limit, db_conn_pool=db_conn_pool
                )
                filtered_orders = []
                for order in orders:
                    if (
                        query.lower() in order["name"].lower()
                        or query.lower() in (order["email"] or "").lower()
                        or query.lower() in order["tags"].lower()
                    ):
                        filtered_orders.append(
                            {
                                "type": "order",
                                "id": order["id"],
                                "name": order["name"],
                                "email": order["email"],
                                "total_price": order["total_price"],
                                "financial_status": order["financial_status"],
                                "fulfillment_status": order["fulfillment_status"],
                                "created_at": order["created_at"],
                            }
                        )
                results["orders"] = filtered_orders[:limit]

            if search_type in ["customers", "all"]:
                customers = await self.get_customers(
                    user_id, limit=limit, db_conn_pool=db_conn_pool
                )
                filtered_customers = []
                for customer in customers:
                    if (
                        query.lower() in customer["email"].lower()
                        or query.lower() in (customer["first_name"] or "").lower()
                        or query.lower() in (customer["last_name"] or "").lower()
                        or query.lower() in customer["tags"].lower()
                    ):
                        filtered_customers.append(
                            {
                                "type": "customer",
                                "id": customer["id"],
                                "email": customer["email"],
                                "first_name": customer["first_name"],
                                "last_name": customer["last_name"],
                                "state": customer["state"],
                                "total_spent": customer["total_spent"],
                                "created_at": customer["created_at"],
                            }
                        )
                results["customers"] = filtered_customers[:limit]

            return results

        except Exception as e:
            logger.error(f"Error searching Shopify: {e}")
            return results

    async def get_shop_info(self, user_id: str, db_conn_pool=None) -> Dict[str, Any]:
        """Get shop information"""

        try:
            result = await self._make_request(
                user_id, "GET", "shop", db_conn_pool=db_conn_pool
            )

            if result and "shop" in result:
                return {"ok": True, "shop": result["shop"]}

            return {"ok": False, "error": {"message": "Failed to get shop information"}}

        except Exception as e:
            logger.error(f"Error getting shop information: {e}")
            return {
                "ok": False,
                "error": {"message": f"Error getting shop information: {str(e)}"},
            }

    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None


async def get_shopify_client(
    user_id: str, db_conn_pool=None
) -> Optional[ShopifyService]:
    """
    Get authenticated Shopify client for user

    Args:
        user_id: The user ID to get Shopify client for
        db_conn_pool: Database connection pool for token lookup

    Returns:
        ShopifyService instance or None if authentication fails
    """
    try:
        # Create Shopify service instance
        service = ShopifyService()

        # Test connection by getting shop info
        shop_info = await service.get_shop_info(user_id, db_conn_pool)

        if shop_info.get("ok"):
            logger.info(f"Successfully connected to Shopify for user {user_id}")
            return service
        else:
            logger.warning(
                f"Failed to connect to Shopify for user {user_id}: {shop_info.get('error', {}).get('message', 'Unknown error')}"
            )
            return None

    except Exception as e:
        logger.error(f"Error getting Shopify client for user {user_id}: {e}")
        return None


# Global Shopify service instance
shopify_service = ShopifyService()

# Export service and functions
__all__ = [
    "ShopifyService",
    "ShopifyServiceConfig",
    "shopify_service",
    "get_shopify_client",
]
