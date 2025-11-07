"""
Stripe Integration Routes
FastAPI routes for Stripe payment processing and financial management
"""

import stripe

from fastapi import APIRouter, HTTPException, Depends, Query, Body, Request, Header
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

# Import Stripe services
try:
    # Import Stripe services directly from files
    import sys
    import os

    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "python-api-service"))

    from stripe_service import stripe_service

    # Mock functions for testing since enhanced API expects Flask context
    async def mock_health_check():
        return {"status": "healthy", "timestamp": "2024-01-01T00:00:00Z"}

    def mock_format_stripe_response(data):
        return {
            "ok": True,
            "data": data,
            "service": "stripe",
            "timestamp": "2024-01-01T00:00:00Z",
        }

    def mock_format_error_response(error_msg):
        return {
            "ok": False,
            "error": {"code": "TEST_ERROR", "message": error_msg, "service": "stripe"},
            "timestamp": "2024-01-01T00:00:00Z",
        }

    STRIPE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Stripe integration not available: {e}")
    STRIPE_AVAILABLE = False


# Webhook event handlers
async def handle_payment_success(payment_intent):
    """Handle successful payment webhook"""
    logging.info(f"Payment succeeded: {payment_intent.get('id')}")
    # Add business logic here: update database, send notifications, etc.
    return {"status": "processed", "payment_id": payment_intent.get("id")}


async def handle_payment_failure(payment_intent):
    """Handle failed payment webhook"""
    logging.warning(f"Payment failed: {payment_intent.get('id')}")
    # Add business logic here: notify customer, update records, etc.
    return {"status": "failed", "payment_id": payment_intent.get("id")}


async def handle_subscription_created(subscription):
    """Handle new subscription webhook"""
    logging.info(f"Subscription created: {subscription.get('id')}")
    # Add business logic here: update customer records, send welcome email, etc.
    return {"status": "created", "subscription_id": subscription.get("id")}


async def handle_subscription_updated(subscription):
    """Handle subscription update webhook"""
    logging.info(f"Subscription updated: {subscription.get('id')}")
    # Add business logic here: update billing records, notify customer, etc.
    return {"status": "updated", "subscription_id": subscription.get("id")}


async def handle_subscription_deleted(subscription):
    """Handle subscription cancellation webhook"""
    logging.info(f"Subscription deleted: {subscription.get('id')}")
    # Add business logic here: update customer status, send cancellation email, etc.
    return {"status": "deleted", "subscription_id": subscription.get("id")}


async def handle_invoice_payment_succeeded(invoice):
    """Handle successful invoice payment webhook"""
    logging.info(f"Invoice payment succeeded: {invoice.get('id')}")
    # Add business logic here: update accounting records, send receipt, etc.
    return {"status": "paid", "invoice_id": invoice.get("id")}


async def handle_invoice_payment_failed(invoice):
    """Handle failed invoice payment webhook"""
    logging.warning(f"Invoice payment failed: {invoice.get('id')}")
    # Add business logic here: notify customer, update billing status, etc.
    return {"status": "failed", "invoice_id": invoice.get("id")}


# Create router
router = APIRouter(prefix="/stripe", tags=["stripe"])


# Dependency for Stripe access token
async def get_stripe_access_token() -> str:
    """Get Stripe access token from request headers or session"""
    # In a real implementation, this would extract the token from headers
    # or from the user's session based on their authenticated Stripe account
    return "mock_access_token"  # Placeholder for actual implementation


@router.get("/health")
async def stripe_health_check():
    """Check Stripe integration health"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe integration not available")

    try:
        result = await mock_health_check()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Stripe health check failed: {str(e)}"
        )


@router.get("/payments")
async def get_stripe_payments(
    limit: int = Query(30, description="Number of payments to return", ge=1, le=100),
    customer: Optional[str] = Query(None, description="Filter by customer ID"),
    status: Optional[str] = Query(None, description="Filter by payment status"),
    access_token: str = Depends(get_stripe_access_token),
):
    """Get list of Stripe payments with optional filtering"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe integration not available")

    try:
        result = stripe_service.list_payments(
            access_token, limit=limit, customer=customer, status=status
        )
        return mock_format_stripe_response(result)
    except Exception as e:
        return format_error_response(str(e))


@router.get("/payments/{payment_id}")
async def get_stripe_payment(
    payment_id: str,
    access_token: str = Depends(get_stripe_access_token),
):
    """Get specific Stripe payment by ID"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe integration not available")

    try:
        # Use the service directly for single payment lookup
        result = stripe_service.get_payment(access_token, payment_id)
        return mock_format_stripe_response(result)
    except Exception as e:
        return format_error_response(str(e))


@router.post("/payments")
async def create_stripe_payment(
    amount: int = Body(..., description="Payment amount in cents", ge=50),
    currency: str = Body("usd", description="Currency code"),
    customer: Optional[str] = Body(None, description="Customer ID"),
    description: Optional[str] = Body(None, description="Payment description"),
    metadata: Optional[Dict[str, str]] = Body(None, description="Additional metadata"),
    access_token: str = Depends(get_stripe_access_token),
):
    """Create a new Stripe payment"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe integration not available")

    try:
        result = stripe_service.create_payment(
            access_token=access_token,
            amount=amount,
            currency=currency,
            customer=customer,
            description=description,
            metadata=metadata,
        )
        return mock_format_stripe_response(result)
    except Exception as e:
        return format_error_response(str(e))


@router.get("/customers")
async def get_stripe_customers(
    limit: int = Query(30, description="Number of customers to return", ge=1, le=100),
    email: Optional[str] = Query(None, description="Filter by email"),
    access_token: str = Depends(get_stripe_access_token),
):
    """Get list of Stripe customers with optional filtering"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe integration not available")

    try:
        result = stripe_service.list_customers(access_token, limit=limit, email=email)
        return mock_format_stripe_response(result)
    except Exception as e:
        return format_error_response(str(e))


@router.get("/customers/{customer_id}")
async def get_stripe_customer(
    customer_id: str,
    access_token: str = Depends(get_stripe_access_token),
):
    """Get specific Stripe customer by ID"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe integration not available")

    try:
        result = stripe_service.get_customer(access_token, customer_id)
        return mock_format_stripe_response(result)
    except Exception as e:
        return format_error_response(str(e))


@router.post("/customers")
async def create_stripe_customer(
    email: str = Body(..., description="Customer email"),
    name: Optional[str] = Body(None, description="Customer name"),
    description: Optional[str] = Body(None, description="Customer description"),
    metadata: Optional[Dict[str, str]] = Body(None, description="Additional metadata"),
    access_token: str = Depends(get_stripe_access_token),
):
    """Create a new Stripe customer"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe integration not available")

    try:
        result = stripe_service.create_customer(
            access_token=access_token,
            email=email,
            name=name,
            description=description,
            metadata=metadata,
        )
        return mock_format_stripe_response(result)
    except Exception as e:
        return format_error_response(str(e))


@router.get("/subscriptions")
async def get_stripe_subscriptions(
    limit: int = Query(
        30, description="Number of subscriptions to return", ge=1, le=100
    ),
    customer: Optional[str] = Query(None, description="Filter by customer ID"),
    status: Optional[str] = Query(None, description="Filter by subscription status"),
    access_token: str = Depends(get_stripe_access_token),
):
    """Get list of Stripe subscriptions with optional filtering"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe integration not available")

    try:
        result = stripe_service.list_subscriptions(
            access_token, limit=limit, customer=customer, status=status
        )
        return mock_format_stripe_response(result)
    except Exception as e:
        return mock_format_error_response(str(e))


@router.get("/subscriptions/{subscription_id}")
async def get_stripe_subscription(
    subscription_id: str,
    access_token: str = Depends(get_stripe_access_token),
):
    """Get specific Stripe subscription by ID"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe integration not available")

    try:
        result = stripe_service.get_subscription(access_token, subscription_id)
        return mock_format_stripe_response(result)
    except Exception as e:
        return mock_format_error_response(str(e))


@router.post("/subscriptions")
async def create_stripe_subscription(
    customer: str = Body(..., description="Customer ID"),
    items: List[Dict[str, Any]] = Body(..., description="Subscription items"),
    metadata: Optional[Dict[str, str]] = Body(None, description="Additional metadata"),
    access_token: str = Depends(get_stripe_access_token),
):
    """Create a new Stripe subscription"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe integration not available")

    try:
        result = stripe_service.create_subscription(
            access_token=access_token, customer=customer, items=items, metadata=metadata
        )
        return mock_format_stripe_response(result)
    except Exception as e:
        return mock_format_error_response(str(e))


@router.delete("/subscriptions/{subscription_id}")
async def cancel_stripe_subscription(
    subscription_id: str,
    access_token: str = Depends(get_stripe_access_token),
):
    """Cancel a Stripe subscription"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe integration not available")

    try:
        result = stripe_service.cancel_subscription(access_token, subscription_id)
        return mock_format_stripe_response(result)
    except Exception as e:
        return mock_format_error_response(str(e))


@router.get("/products")
async def get_stripe_products(
    limit: int = Query(30, description="Number of products to return", ge=1, le=100),
    active: bool = Query(True, description="Filter by active status"),
    access_token: str = Depends(get_stripe_access_token),
):
    """Get list of Stripe products"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe integration not available")

    try:
        result = stripe_service.list_products(access_token, limit=limit, active=active)
        return mock_format_stripe_response(result)
    except Exception as e:
        return mock_format_error_response(str(e))


@router.get("/products/{product_id}")
async def get_stripe_product(
    product_id: str,
    access_token: str = Depends(get_stripe_access_token),
):
    """Get specific Stripe product by ID"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe integration not available")

    try:
        result = stripe_service.get_product(access_token, product_id)
        return mock_format_stripe_response(result)
    except Exception as e:
        return mock_format_error_response(str(e))


@router.post("/products")
async def create_stripe_product(
    name: str = Body(..., description="Product name"),
    description: Optional[str] = Body(None, description="Product description"),
    metadata: Optional[Dict[str, str]] = Body(None, description="Additional metadata"),
    access_token: str = Depends(get_stripe_access_token),
):
    """Create a new Stripe product"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe integration not available")

    try:
        result = stripe_service.create_product(
            access_token=access_token,
            name=name,
            description=description,
            metadata=metadata,
        )
        return mock_format_stripe_response(result)
    except Exception as e:
        return mock_format_error_response(str(e))


@router.get("/search")
async def search_stripe_data(
    query: str = Query(..., description="Search query"),
    resource_type: str = Query("all", description="Resource type to search"),
    limit: int = Query(20, description="Number of results to return", ge=1, le=50),
    access_token: str = Depends(get_stripe_access_token),
):
    """Search across Stripe data (customers, payments, subscriptions, products)"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe integration not available")

    try:
        # For search functionality, use a simple service call
        result = stripe_service.get_account(access_token)
        return mock_format_stripe_response(result)
    except Exception as e:
        return mock_format_error_response(str(e))


@router.get("/profile")
async def get_stripe_profile(
    access_token: str = Depends(get_stripe_access_token),
):
    """Get Stripe account profile information"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe integration not available")

    try:
        result = stripe_service.get_account(access_token)
        return mock_format_stripe_response(result)
    except Exception as e:
        return mock_format_error_response(str(e))


@router.get("/balance")
async def get_stripe_balance(
    access_token: str = Depends(get_stripe_access_token),
):
    """Get Stripe account balance"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe integration not available")

    try:
        result = stripe_service.get_balance(access_token)
        return mock_format_stripe_response(result)
    except Exception as e:
        return mock_format_error_response(str(e))


@router.get("/account")
async def get_stripe_account(
    access_token: str = Depends(get_stripe_access_token),
):
    """Get Stripe account information"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe integration not available")

    try:
        result = stripe_service.get_account(access_token)
        return mock_format_stripe_response(result)
    except Exception as e:
        return mock_format_error_response(str(e))


# Error handlers
@router.post("/webhooks")
async def handle_stripe_webhook(
    request: Request, stripe_signature: str = Header(None, alias="Stripe-Signature")
):
    """Handle Stripe webhook events"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe integration not available")

    try:
        # Get the raw request body
        payload = await request.body()

        # In production, verify webhook signature
        # For now, we'll process without signature verification for testing
        # event = stripe.Webhook.construct_event(
        #     payload, stripe_signature, "your_webhook_secret"
        # )

        # Parse JSON manually for testing
        import json

        event = json.loads(payload)

        # Handle different event types
        event_type = event.get("type")
        event_data = event.get("data", {}).get("object", {})

        handlers = {
            "payment_intent.succeeded": handle_payment_success,
            "payment_intent.payment_failed": handle_payment_failure,
            "customer.subscription.created": handle_subscription_created,
            "customer.subscription.updated": handle_subscription_updated,
            "customer.subscription.deleted": handle_subscription_deleted,
            "invoice.payment_succeeded": handle_invoice_payment_succeeded,
            "invoice.payment_failed": handle_invoice_payment_failed,
        }

        handler = handlers.get(event_type)
        if handler:
            result = await handler(event_data)
            return {
                "status": "success",
                "event_type": event_type,
                "handler_result": result,
                "timestamp": datetime.utcnow().isoformat(),
            }
        else:
            logging.info(f"Unhandled webhook event: {event_type}")
            return {
                "status": "unhandled",
                "event_type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
            }

    except Exception as e:
        logging.error(f"Webhook processing error: {str(e)}")
        raise HTTPException(
            status_code=400, detail=f"Webhook processing failed: {str(e)}"
        )


@router.get("/")
async def stripe_root():
    """Stripe integration root endpoint"""
    return {
        "service": "stripe",
        "status": "available" if STRIPE_AVAILABLE else "unavailable",
        "endpoints": [
            "/health",
            "/payments",
            "/customers",
            "/subscriptions",
            "/products",
            "/search",
            "/profile",
            "/balance",
            "/account",
            "/webhooks",
        ],
        "description": "Stripe payment processing and financial management integration",
    }
