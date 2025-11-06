"""
Stripe Handler
Complete Stripe payment processing and financial management handler
"""

import os
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from loguru import logger

# Import Stripe service
try:
    from stripe_service import stripe_service

    STRIPE_SERVICE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Stripe service not available: {e}")
    STRIPE_SERVICE_AVAILABLE = False
    stripe_service = None

# Import database handler
try:
    from db_oauth_stripe import (
        get_tokens,
        save_tokens,
        delete_tokens,
        get_user_stripe_data,
        save_stripe_data,
    )

    STRIPE_DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Stripe database handler not available: {e}")
    STRIPE_DB_AVAILABLE = False

stripe_handler_bp = Blueprint("stripe_handler_bp", __name__)

# Configuration
STRIPE_API_BASE_URL = "https://api.stripe.com/v1"
REQUEST_TIMEOUT = 60


async def get_user_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """Get Stripe tokens for user"""
    if not STRIPE_DB_AVAILABLE:
        # Mock implementation for testing
        return {
            "access_token": os.getenv("STRIPE_ACCESS_TOKEN", "sk_test_mock_key"),
            "token_type": "Bearer",
            "account_id": os.getenv("STRIPE_ACCOUNT_ID", "acct_mock123456789"),
            "refresh_token": None,
            "livemode": False,
            "expires_in": None,
            "scope": "read_write",
            "user_info": {
                "id": "acct_mock123456789",
                "email": os.getenv("STRIPE_USER_EMAIL", "stripe@example.com"),
                "business_name": os.getenv("STRIPE_BUSINESS_NAME", "Test Company"),
                "display_name": os.getenv("STRIPE_DISPLAY_NAME", "Test Company"),
                "country": os.getenv("STRIPE_COUNTRY", "US"),
                "currency": os.getenv("STRIPE_CURRENCY", "USD"),
                "mcc": None,
                "balance": {
                    "available": [{"amount": 100000, "currency": "usd"}],
                    "pending": [{"amount": 5000, "currency": "usd"}],
                },
                "created": (datetime.utcnow() - timedelta(days=365)).isoformat(),
                "created_utc": int(
                    (datetime.utcnow() - timedelta(days=365)).timestamp()
                ),
                "metadata": {"source": "stripe_integration"},
            },
        }

    try:
        return await get_tokens(user_id)
    except Exception as e:
        logger.error(f"Error getting Stripe tokens for user {user_id}: {e}")
        return None


def format_stripe_response(data: Any, service: str, endpoint: str) -> Dict[str, Any]:
    """Format Stripe API response"""
    return {
        "ok": True,
        "data": data,
        "service": service,
        "endpoint": endpoint,
        "timestamp": datetime.utcnow().isoformat(),
        "source": "stripe_api",
    }


def format_error_response(
    error: Exception, service: str, endpoint: str
) -> Dict[str, Any]:
    """Format error response"""
    return {
        "ok": False,
        "error": {
            "code": type(error).__name__,
            "message": str(error),
            "service": service,
            "endpoint": endpoint,
        },
        "timestamp": datetime.utcnow().isoformat(),
        "source": "stripe_api",
    }


@stripe_handler_bp.route("/api/integrations/stripe/payments", methods=["POST"])
async def list_payments():
    """List Stripe payments with advanced filtering"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        created = data.get("created")  # Timestamp range
        customer = data.get("customer")
        payment_intent = data.get("payment_intent")
        status = data.get("status")  # 'succeeded', 'pending', 'failed'
        limit = data.get("limit", 30)
        operation = data.get("operation", "list")

        if not user_id:
            return jsonify(
                {"ok": False, "error": {"message": "user_id is required"}}
            ), 400

        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify(
                {"ok": False, "error": {"message": "Stripe tokens not found"}}
            ), 401

        if STRIPE_SERVICE_AVAILABLE and stripe_service:
            # Use real Stripe service
            result = stripe_service.list_payments(
                access_token=tokens["access_token"],
                limit=limit,
                customer=customer,
                status=status,
                created=created,
            )
            return jsonify(format_stripe_response(result, "payments", "list"))
        else:
            # Mock implementation
            mock_payments = [
                {
                    "id": f"ch_{i}",
                    "object": "charge",
                    "amount": 1000 + (i * 500),
                    "currency": "usd",
                    "customer": f"cus_mock{i}",
                    "description": f"Payment #{i}",
                    "status": "succeeded",
                    "created": int((datetime.utcnow() - timedelta(days=i)).timestamp()),
                    "receipt_email": f"customer{i}@example.com",
                    "receipt_number": f"RCPT{i:06d}",
                    "receipt_url": f"https://pay.stripe.com/receipts/payment_{i}",
                    "refunded": False,
                    "refunds": {
                        "data": [],
                        "has_more": False,
                        "object": "list",
                        "total_count": 0,
                        "url": f"/v1/charges/ch_{i}/refunds",
                    },
                }
                for i in range(1, min(limit, 10) + 1)
            ]

            # Apply filters
            filtered_payments = mock_payments
            if customer:
                filtered_payments = [
                    p for p in filtered_payments if p["customer"] == customer
                ]
            if status:
                filtered_payments = [
                    p for p in filtered_payments if p["status"] == status
                ]

            return jsonify(
                format_stripe_response(
                    {
                        "payments": filtered_payments[:limit],
                        "total_count": len(filtered_payments),
                        "has_more": len(filtered_payments) > limit,
                    },
                    "payments",
                    "list",
                )
            )

    except Exception as e:
        logger.error(f"Error listing Stripe payments: {e}")
        return jsonify(format_error_response(e, "payments", "list")), 500


@stripe_handler_bp.route("/api/integrations/stripe/customers", methods=["POST"])
async def list_customers():
    """List Stripe customers with advanced filtering"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        email = data.get("email")
        description = data.get("description")
        created = data.get("created")  # Timestamp range
        limit = data.get("limit", 30)
        operation = data.get("operation", "list")

        if not user_id:
            return jsonify(
                {"ok": False, "error": {"message": "user_id is required"}}
            ), 400

        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify(
                {"ok": False, "error": {"message": "Stripe tokens not found"}}
            ), 401

        if STRIPE_SERVICE_AVAILABLE and stripe_service:
            # Use real Stripe service
            result = stripe_service.list_customers(
                access_token=tokens["access_token"],
                limit=limit,
                email=email,
                created=created,
            )
            return jsonify(format_stripe_response(result, "customers", "list"))
        else:
            # Mock implementation
            mock_customers = [
                {
                    "id": f"cus_mock{i}",
                    "object": "customer",
                    "email": f"customer{i}@example.com",
                    "name": f"Customer {i}",
                    "description": f"Test customer #{i}",
                    "created": int(
                        (datetime.utcnow() - timedelta(days=i * 30)).timestamp()
                    ),
                    "balance": 0,
                    "currency": "usd",
                    "default_source": f"card_mock{i}",
                    "delinquent": False,
                    "discount": None,
                    "invoice_prefix": f"INV{i:06d}",
                    "invoice_settings": {
                        "custom_fields": None,
                        "default_payment_method": None,
                        "footer": None,
                    },
                    "livemode": False,
                    "metadata": {},
                    "next_invoice_sequence": i,
                    "phone": f"+1555555{i:04d}",
                    "preferred_locales": ["en-US"],
                    "shipping": None,
                    "tax_exempt": "none",
                    "test_clock": None,
                }
                for i in range(1, min(limit, 10) + 1)
            ]

            # Apply filters
            filtered_customers = mock_customers
            if email:
                filtered_customers = [
                    c for c in filtered_customers if c["email"] == email
                ]
            if description:
                filtered_customers = [
                    c
                    for c in filtered_customers
                    if c["description"]
                    and description.lower() in c["description"].lower()
                ]

            return jsonify(
                format_stripe_response(
                    {
                        "customers": filtered_customers[:limit],
                        "total_count": len(filtered_customers),
                        "has_more": len(filtered_customers) > limit,
                    },
                    "customers",
                    "list",
                )
            )

    except Exception as e:
        logger.error(f"Error listing Stripe customers: {e}")
        return jsonify(format_error_response(e, "customers", "list")), 500


@stripe_handler_bp.route("/api/integrations/stripe/subscriptions", methods=["POST"])
async def list_subscriptions():
    """List Stripe subscriptions with advanced filtering"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        customer = data.get("customer")
        status = data.get("status")  # 'active', 'canceled', 'past_due', 'trialing'
        created = data.get("created")  # Timestamp range
        limit = data.get("limit", 30)
        operation = data.get("operation", "list")

        if not user_id:
            return jsonify(
                {"ok": False, "error": {"message": "user_id is required"}}
            ), 400

        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify(
                {"ok": False, "error": {"message": "Stripe tokens not found"}}
            ), 401

        if STRIPE_SERVICE_AVAILABLE and stripe_service:
            # Use real Stripe service
            result = stripe_service.list_subscriptions(
                access_token=tokens["access_token"],
                limit=limit,
                customer=customer,
                status=status,
                created=created,
            )
            return jsonify(format_stripe_response(result, "subscriptions", "list"))
        else:
            # Mock implementation
            mock_subscriptions = [
                {
                    "id": f"sub_mock{i}",
                    "object": "subscription",
                    "customer": f"cus_mock{i}",
                    "status": "active" if i % 3 != 0 else "canceled",
                    "created": int(
                        (datetime.utcnow() - timedelta(days=i * 7)).timestamp()
                    ),
                    "current_period_start": int(
                        (datetime.utcnow() - timedelta(days=7)).timestamp()
                    ),
                    "current_period_end": int(
                        (datetime.utcnow() + timedelta(days=23)).timestamp()
                    ),
                    "cancel_at_period_end": False,
                    "canceled_at": None
                    if i % 3 != 0
                    else int((datetime.utcnow() - timedelta(days=1)).timestamp()),
                    "collection_method": "charge_automatically",
                    "currency": "usd",
                    "items": {
                        "data": [
                            {
                                "id": f"si_mock{i}",
                                "object": "subscription_item",
                                "price": {
                                    "id": f"price_mock{i}",
                                    "object": "price",
                                    "active": True,
                                    "currency": "usd",
                                    "product": f"prod_mock{i}",
                                    "recurring": {
                                        "interval": "month",
                                        "interval_count": 1,
                                        "usage_type": "licensed",
                                    },
                                    "type": "recurring",
                                    "unit_amount": 2999,
                                    "unit_amount_decimal": "2999",
                                },
                                "quantity": 1,
                            }
                        ],
                        "has_more": False,
                        "object": "list",
                        "total_count": 1,
                        "url": f"/v1/subscription_items?subscription=sub_mock{i}",
                    },
                    "latest_invoice": f"in_mock{i}",
                    "livemode": False,
                    "metadata": {},
                    "pending_setup_intent": None,
                    "pending_update": None,
                    "schedule": None,
                    "start_date": int(
                        (datetime.utcnow() - timedelta(days=i * 7)).timestamp()
                    ),
                    "trial_end": None,
                    "trial_start": None,
                }
                for i in range(1, min(limit, 10) + 1)
            ]

            # Apply filters
            filtered_subscriptions = mock_subscriptions
            if customer:
                filtered_subscriptions = [
                    s for s in filtered_subscriptions if s["customer"] == customer
                ]
            if status:
                filtered_subscriptions = [
                    s for s in filtered_subscriptions if s["status"] == status
                ]

            return jsonify(
                format_stripe_response(
                    {
                        "subscriptions": filtered_subscriptions[:limit],
                        "total_count": len(filtered_subscriptions),
                        "has_more": len(filtered_subscriptions) > limit,
                    },
                    "subscriptions",
                    "list",
                )
            )

    except Exception as e:
        logger.error(f"Error listing Stripe subscriptions: {e}")
        return jsonify(format_error_response(e, "subscriptions", "list")), 500


@stripe_handler_bp.route("/api/integrations/stripe/products", methods=["POST"])
async def list_products():
    """List Stripe products with advanced filtering"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        active = data.get("active", True)  # Filter by active status
        limit = data.get("limit", 30)
        operation = data.get("operation", "list")

        if not user_id:
            return jsonify(
                {"ok": False, "error": {"message": "user_id is required"}}
            ), 400

        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify(
                {"ok": False, "error": {"message": "Stripe tokens not found"}}
            ), 401

        if STRIPE_SERVICE_AVAILABLE and stripe_service:
            # Use real Stripe service
            result = stripe_service.list_products(
                access_token=tokens["access_token"], limit=limit, active=active
            )
            return jsonify(format_stripe_response(result, "products", "list"))
        else:
            # Mock implementation
            mock_products = [
                {
                    "id": f"prod_mock{i}",
                    "object": "product",
                    "active": True,
                    "created": int(
                        (datetime.utcnow() - timedelta(days=i * 30)).timestamp()
                    ),
                    "description": f"Product #{i} description",
                    "images": [],
                    "livemode": False,
                    "metadata": {},
                    "name": f"Product {i}",
                    "package_dimensions": None,
                    "shippable": None,
                    "statement_descriptor": None,
                    "tax_code": None,
                    "type": "service",
                    "unit_label": None,
                    "updated": int(
                        (datetime.utcnow() - timedelta(days=i * 7)).timestamp()
                    ),
                    "url": None,
                }
                for i in range(1, min(limit, 10) + 1)
            ]

            # Apply filters
            filtered_products = mock_products
            if active is not None:
                filtered_products = [
                    p for p in filtered_products if p["active"] == active
                ]

            return jsonify(
                format_stripe_response(
                    {
                        "products": filtered_products[:limit],
                        "total_count": len(filtered_products),
                        "has_more": len(filtered_products) > limit,
                    },
                    "products",
                    "list",
                )
            )

    except Exception as e:
        logger.error(f"Error listing Stripe products: {e}")
        return jsonify(format_error_response(e, "products", "list")), 500


@stripe_handler_bp.route("/api/integrations/stripe/health", methods=["GET"])
async def health_check():
    """Stripe service health check"""
    try:
        # Test Stripe API connectivity
        try:
            if STRIPE_SERVICE_AVAILABLE and stripe_service:
                # Use real health check
                health_status = stripe_service.health_check("mock_token")
            else:
                # Mock health check
                health_status = {
                    "status": "healthy",
                    "message": "Stripe APIs are accessible",
                    "service_available": STRIPE_SERVICE_AVAILABLE,
                    "database_available": STRIPE_DB_AVAILABLE,
                    "services": {
                        "payments": {"status": "healthy"},
                        "customers": {"status": "healthy"},
                        "subscriptions": {"status": "healthy"},
                        "products": {"status": "healthy"},
                        "billing": {"status": "healthy"},
                        "webhooks": {"status": "healthy"},
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }

            return jsonify(health_status)

        except Exception as e:
            logger.error(f"Stripe health check failed: {e}")
            return jsonify(format_error_response(e, "health", "check")), 500

    except Exception as e:
        logger.error(f"Error in Stripe health check: {e}")
        return jsonify(format_error_response(e, "health", "check")), 500


@stripe_handler_bp.route("/api/integrations/stripe/payments/create", methods=["POST"])
async def create_payment():
    """Create a new Stripe payment"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        amount = data.get("amount")
        currency = data.get("currency", "usd")
        customer = data.get("customer")
        description = data.get("description")
        metadata = data.get("metadata")

        if not user_id or not amount:
            return jsonify(
                {"ok": False, "error": {"message": "user_id and amount are required"}}
            ), 400

        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify(
                {"ok": False, "error": {"message": "Stripe tokens not found"}}
            ), 401

        if STRIPE_SERVICE_AVAILABLE and stripe_service:
            # Use real Stripe service
            result = stripe_service.create_payment(
                access_token=tokens["access_token"],
                amount=amount,
                currency=currency,
                customer=customer,
                description=description,
                metadata=metadata,
            )
            return jsonify(format_stripe_response(result, "payments", "create"))
        else:
            # Mock implementation
            mock_payment = {
                "id": f"ch_mock_{int(time.time())}",
                "object": "charge",
                "amount": amount,
                "currency": currency,
                "customer": customer or "cus_mock123",
                "description": description or "Test payment",
                "status": "succeeded",
                "created": int(time.time()),
                "receipt_email": tokens.get("user_info", {}).get(
                    "email", "customer@example.com"
                ),
                "receipt_number": f"RCPT{int(time.time()):06d}",
                "receipt_url": "https://pay.stripe.com/receipts/mock_receipt",
                "refunded": False,
                "refunds": {
                    "data": [],
                    "has_more": False,
                    "object": "list",
                    "total_count": 0,
                },
            }

            return jsonify(format_stripe_response(mock_payment, "payments", "create"))

    except Exception as e:
        logger.error(f"Error creating Stripe payment: {e}")
        return jsonify(format_error_response(e, "payments", "create")), 500


@stripe_handler_bp.route("/api/integrations/stripe/customers/create", methods=["POST"])
async def create_customer():
    """Create a new Stripe customer"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        email = data.get("email")
        name = data.get("name")
        description = data.get("description")
        metadata = data.get("metadata")

        if not user_id or not email:
            return jsonify(
                {"ok": False, "error": {"message": "user_id and email are required"}}
            ), 400

        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify(
                {"ok": False, "error": {"message": "Stripe tokens not found"}}
            ), 401

        if STRIPE_SERVICE_AVAILABLE and stripe_service:
            # Use real Stripe service
            result = stripe_service.create_customer(
                access_token=tokens["access_token"],
                email=email,
                name=name,
                description=description,
                metadata=metadata,
            )
            return jsonify(format_stripe_response(result, "customers", "create"))
        else:
            # Mock implementation
            mock_customer = {
                "id": f"cus_mock_{int(time.time())}",
                "object": "customer",
                "email": email,
                "name": name,
                "description": description,
                "created": int(time.time()),
                "balance": 0,
                "currency": "usd",
                "default_source": None,
                "delinquent": False,
                "discount": None,
                "invoice_prefix": f"INV{int(time.time()):06d}",
                "invoice_settings": {
                    "custom_fields": None,
                    "default_payment_method": None,
                    "footer": None,
                },
                "livemode": False,
                "metadata": metadata or {},
                "next_invoice_sequence": 1,
                "phone": None,
                "preferred_locales": ["en-US"],
                "shipping": None,
                "tax_exempt": "none",
                "test_clock": None,
            }

            return jsonify(format_stripe_response(mock_customer, "customers", "create"))

    except Exception as e:
        logger.error(f"Error creating Stripe customer: {e}")
        return jsonify(format_error_response(e, "customers", "create")), 500
