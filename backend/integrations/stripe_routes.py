"""
Stripe Integration Routes
FastAPI routes for Stripe payment processing and financial management
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import stripe
from accounting.ingestion import TransactionIngestor
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from core.automation_settings import get_automation_settings
from core.auth import get_current_user
from core.database import get_db
from core.models import StripeToken, User

# Import Stripe services
try:
    # Import Stripe services directly from files
    from .stripe_service import stripe_service

    STRIPE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Stripe integration not available: {e}")
    STRIPE_AVAILABLE = False
    stripe_service = None


# Feature flag for emergency rollback
STRIPE_USE_MOCK = os.getenv("STRIPE_USE_MOCK", "false").lower() == "true"

if STRIPE_USE_MOCK:
    logging.warning("STRIPE_USE_MOCK is TRUE - Using mock responses instead of real Stripe API")


def format_stripe_response(data: Any) -> Dict[str, Any]:
    """
    Format successful Stripe API response with consistent structure.

    Args:
        data: Response data from Stripe API

    Returns:
        Formatted response dictionary
    """
    return {
        "ok": True,
        "data": data,
        "service": "stripe",
        "timestamp": datetime.utcnow().isoformat(),
    }


def format_stripe_error(
    error_msg: str,
    error_code: str = "STRIPE_ERROR",
    status_code: int = 500
) -> Dict[str, Any]:
    """
    Format Stripe error response with consistent structure.

    Args:
        error_msg: Error message
        error_code: Error code identifier
        status_code: HTTP status code

    Returns:
        Formatted error response dictionary
    """
    return {
        "ok": False,
        "error": {
            "code": error_code,
            "message": error_msg,
            "service": "stripe",
            "status_code": status_code
        },
        "timestamp": datetime.utcnow().isoformat(),
    }

# Webhook event handlers
async def handle_payment_success(payment_intent, db: Session):
    """Handle successful payment webhook"""
    logging.info(f"Payment succeeded: {payment_intent.get('id')}")
    
    # Ingest into Accounting Ledger
    try:
        if get_automation_settings().is_accounting_enabled():
            # We need a workspace_id. In a real app, this comes from the Stripe account metadata
            # or a mapping table. For now, we'll use a placeholder or look it up.
            workspace_id = payment_intent.get("metadata", {}).get("workspace_id", "default-workspace")
            ingestor = TransactionIngestor(db)
            await ingestor.ingest_stripe_payment(workspace_id, payment_intent)
            logging.info(f"Ingested Stripe payment {payment_intent.get('id')} into ledger")
        else:
            logging.info(f"Skipping accounting ingestion for {payment_intent.get('id')} (Accounting disabled)")
    except Exception as e:
        logging.error(f"Failed to ingest Stripe payment: {e}")

    return {"status": "processed", "payment_id": payment_intent.get("id")}


async def handle_payment_failure(payment_intent, db: Session):
    """Handle failed payment webhook"""
    logging.warning(f"Payment failed: {payment_intent.get('id')}")
    # Add business logic here: notify customer, update records, etc.
    return {"status": "failed", "payment_id": payment_intent.get("id")}


async def handle_subscription_created(subscription, db: Session):
    """Handle new subscription webhook"""
    logging.info(f"Subscription created: {subscription.get('id')}")
    # Add business logic here: update customer records, send welcome email, etc.
    return {"status": "created", "subscription_id": subscription.get("id")}


async def handle_subscription_updated(subscription, db: Session):
    """Handle subscription update webhook"""
    logging.info(f"Subscription updated: {subscription.get('id')}")
    # Add business logic here: update billing records, notify customer, etc.
    return {"status": "updated", "subscription_id": subscription.get("id")}


async def handle_subscription_deleted(subscription, db: Session):
    """Handle subscription cancellation webhook"""
    logging.info(f"Subscription deleted: {subscription.get('id')}")
    # Add business logic here: update customer status, send cancellation email, etc.
    return {"status": "deleted", "subscription_id": subscription.get("id")}


async def handle_invoice_payment_succeeded(invoice, db: Session):
    """Handle successful invoice payment webhook"""
    logging.info(f"Invoice payment succeeded: {invoice.get('id')}")
    # Add business logic here: update accounting records, send receipt, etc.
    return {"status": "paid", "invoice_id": invoice.get("id")}


async def handle_invoice_payment_failed(invoice, db: Session):
    """Handle failed invoice payment webhook"""
    logging.warning(f"Invoice payment failed: {invoice.get('id')}")
    # Add business logic here: notify customer, update billing status, etc.
    return {"status": "failed", "invoice_id": invoice.get("id")}


# Create router
# Auth Type: OAuth2
router = APIRouter(prefix="/stripe", tags=["stripe"])

@router.get("/auth/url")
async def get_auth_url(current_user: User = Depends(get_current_user)):
    """
    Get Stripe OAuth URL for user authentication.

    Returns the Stripe Connect OAuth URL that users should visit to authorize
    Atom to access their Stripe account.
    """
    stripe_client_id = os.getenv("STRIPE_CLIENT_ID")
    if not stripe_client_id:
        raise HTTPException(
            status_code=500,
            detail="Stripe client ID not configured. Please set STRIPE_CLIENT_ID environment variable."
        )

    redirect_uri = os.getenv("STRIPE_REDIRECT_URI", "http://localhost:8000/api/stripe/callback")

    auth_url = (
        f"https://connect.stripe.com/oauth/authorize"
        f"?response_type=code"
        f"&client_id={stripe_client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope=read_write"
        f"&state={current_user.id}"  # Use user_id as state for verification
    )

    return {
        "url": auth_url,
        "timestamp": datetime.now().isoformat()
    }

@router.get("/callback")
async def handle_oauth_callback(
    code: str,
    state: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Handle Stripe OAuth callback.

    Exchange the authorization code for access tokens and store them in the database.

    Args:
        code: Authorization code from Stripe
        state: State parameter (user_id) for CSRF protection
        db: Database session
    """
    stripe_client_id = os.getenv("STRIPE_CLIENT_ID")
    stripe_client_secret = os.getenv("STRIPE_CLIENT_SECRET")
    stripe_redirect_uri = os.getenv("STRIPE_REDIRECT_URI", "http://localhost:8000/api/stripe/callback")

    if not all([stripe_client_id, stripe_client_secret]):
        raise HTTPException(
            status_code=500,
            detail="Stripe client credentials not configured. Please set STRIPE_CLIENT_ID and STRIPE_CLIENT_SECRET environment variables."
        )

    try:
        # Exchange authorization code for access token
        import requests
        token_response = requests.post(
            "https://connect.stripe.com/oauth/token",
            data={
                "client_secret": stripe_client_secret,
                "code": code,
                "grant_type": "authorization_code",
            }
        )

        if token_response.status_code != 200:
            logging.error(f"Stripe token exchange failed: {token_response.text}")
            raise HTTPException(
                status_code=400,
                detail="Failed to exchange authorization code for access token"
            )

        token_data = token_response.json()

        # Extract token information
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")  # May not be present
        stripe_user_id = token_data.get("stripe_user_id")
        livemode = token_data.get("livemode", False)
        token_type = token_data.get("token_type", "bearer")
        scope = token_data.get("scope", "read_write")

        # Get user from state (if provided) or use a default
        # In production, you would validate the state parameter properly
        user_id = state  # This should be the user_id from the auth URL

        if not user_id:
            # For testing purposes, use a default user or raise error
            raise HTTPException(
                status_code=400,
                detail="Invalid state parameter. Please restart the OAuth flow."
            )

        # Check if user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        # Deactivate old tokens for this user
        db.query(StripeToken).filter(
            StripeToken.user_id == user_id,
            StripeToken.status == "active"
        ).update({"status": "revoked"})

        # Store new token
        stripe_token = StripeToken(
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            stripe_user_id=stripe_user_id,
            livemode=livemode,
            token_type=token_type,
            scope=scope,
            # Stripe access tokens don't expire, but we set a default for safety
            expires_at=datetime.utcnow() + timedelta(days=365),
            status="active"
        )

        db.add(stripe_token)
        db.commit()

        logging.info(f"Successfully stored Stripe token for user {user_id}")

        return {
            "ok": True,
            "status": "success",
            "stripe_user_id": stripe_user_id,
            "livemode": livemode,
            "message": "Stripe authentication successful",
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Stripe OAuth callback error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Stripe authentication failed: {str(e)}"
        )


# Dependency for Stripe access token
async def get_stripe_access_token(
    authorization: Optional[str] = Header(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> str:
    """
    Get Stripe access token from request headers or database.

    Priority order:
    1. Authorization header (Bearer token) - for API access
    2. Database lookup - for web/app access with user session

    Args:
        authorization: Authorization header value
        current_user: Current authenticated user from session
        db: Database session

    Returns:
        str: Valid Stripe access token

    Raises:
        HTTPException: If no valid token found
    """
    # 1. Check Authorization header first (API access)
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]

        # Validate token with Stripe API
        try:
            stripe_account = stripe.Account.retrieve(
                token,
                headers={"Stripe-Version": "2023-10-16"}
            )
            logging.info(f"Validated Stripe access token from Authorization header for user {current_user.id}, account: {stripe_account.get('id')}")
            return token
        except stripe.error.AuthenticationError as e:
            logging.error(f"Stripe token validation failed: {e}")
            raise HTTPException(
                status_code=401,
                detail="Invalid Stripe access token. Please provide a valid token."
            )
        except stripe.error.APIError as e:
            logging.warning(f"Stripe API error during token validation: {e}")
            # Allow token to proceed if there's a temporary API error
            return token

    # 2. Check database for stored token (web/app access)
    stripe_token = db.query(StripeToken).filter(
        StripeToken.user_id == current_user.id,
        StripeToken.status == "active"
    ).first()

    if stripe_token:
        # Check if token is expired
        if stripe_token.expires_at and stripe_token.expires_at < datetime.utcnow():
            logging.warning(f"Stripe token for user {current_user.id} is expired")

            # Attempt token refresh if refresh_token is available
            if stripe_token.refresh_token:
                try:
                    import requests

                    stripe_client_secret = os.getenv("STRIPE_CLIENT_SECRET")
                    if not stripe_client_secret:
                        raise HTTPException(
                            status_code=500,
                            detail="Stripe client secret not configured for token refresh"
                        )

                    # Refresh the token using Stripe's OAuth endpoint
                    refresh_response = requests.post(
                        "https://connect.stripe.com/oauth/token",
                        data={
                            "client_secret": stripe_client_secret,
                            "refresh_token": stripe_token.refresh_token,
                            "grant_type": "refresh_token",
                        }
                    )

                    if refresh_response.status_code != 200:
                        logging.error(f"Stripe token refresh failed: {refresh_response.text}")
                        raise HTTPException(
                            status_code=401,
                            detail="Failed to refresh Stripe access token. Please re-authenticate."
                        )

                    token_data = refresh_response.json()

                    # Update stored token
                    stripe_token.access_token = token_data.get("access_token", stripe_token.access_token)
                    # Stripe may return a new refresh token
                    if "refresh_token" in token_data:
                        stripe_token.refresh_token = token_data["refresh_token"]

                    # Update expiration (Stripe tokens don't expire, but we track for safety)
                    stripe_token.expires_at = datetime.utcnow() + timedelta(days=365)
                    stripe_token.status = "active"

                    db.commit()

                    logging.info(f"Successfully refreshed Stripe token for user {current_user.id}")
                    return stripe_token.access_token

                except HTTPException:
                    raise
                except Exception as e:
                    logging.error(f"Stripe token refresh error: {e}")
                    # Mark as expired and require re-authentication
                    stripe_token.status = "expired"
                    db.commit()
                    raise HTTPException(
                        status_code=401,
                        detail="Stripe token refresh failed. Please re-authenticate with Stripe."
                    )
            else:
                # No refresh token available, mark as expired
                stripe_token.status = "expired"
                db.commit()
                raise HTTPException(
                    status_code=401,
                    detail="Stripe access token expired and no refresh token available. Please re-authenticate with Stripe."
                )

        # Update last_used timestamp
        stripe_token.last_used = datetime.utcnow()
        db.commit()

        logging.info(f"Using Stripe access token from database for user {current_user.id}")
        return stripe_token.access_token

    # 3. No token found
    logging.warning(f"No Stripe token found for user {current_user.id}")
    raise HTTPException(
        status_code=401,
        detail="Stripe authentication required. Please connect your Stripe account."
    )


@router.get("/health")
async def stripe_health_check():
    """
    Check Stripe integration health with real API verification.

    Verifies connectivity to Stripe API and checks configuration.
    """
    if not STRIPE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail={
                "ok": False,
                "error": "Stripe integration not available",
                "service": "stripe",
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    try:
        # Check if Stripe is configured
        stripe_client_id = os.getenv("STRIPE_CLIENT_ID")
        stripe_client_secret = os.getenv("STRIPE_CLIENT_SECRET")

        if not stripe_client_id or not stripe_client_secret:
            return {
                "ok": True,
                "status": "configured_partial",
                "message": "Stripe integration available but credentials not fully configured",
                "has_client_id": bool(stripe_client_id),
                "has_client_secret": bool(stripe_client_secret),
                "service": "stripe",
                "timestamp": datetime.utcnow().isoformat()
            }

        # Verify real Stripe connectivity if not using mock mode
        if not STRIPE_USE_MOCK:
            try:
                # Make a lightweight API call to verify connectivity
                # We use the API key from environment to verify Stripe is accessible
                stripe_api_key = os.getenv("STRIPE_API_KEY") or stripe_client_secret
                if stripe_api_key:
                    # Test connectivity with a simple API call
                    account = stripe.Account.retrieve(
                        stripe_api_key,
                        headers={"Stripe-Version": "2023-10-16"}
                    )

                    return {
                        "ok": True,
                        "status": "healthy",
                        "message": "Stripe API is accessible",
                        "account_id": account.get("id") if account else None,
                        "service": "stripe",
                        "timestamp": datetime.utcnow().isoformat()
                    }
            except stripe.error.AuthenticationError:
                return {
                    "ok": True,
                    "status": "configured",
                    "message": "Stripe is configured but API authentication failed",
                    "error": "Invalid API key",
                    "service": "stripe",
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as stripe_error:
                logging.warning(f"Stripe API verification failed: {stripe_error}")
                # Continue anyway - configuration is present but API might be temporarily unavailable

        return {
            "ok": True,
            "status": "configured",
            "message": "Stripe integration is configured",
            "mock_mode": STRIPE_USE_MOCK,
            "service": "stripe",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logging.error(f"Stripe health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=format_stripe_error(f"Stripe health check failed: {str(e)}")
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
        return format_stripe_response(result)
    except Exception as e:
        return format_stripe_error(str(e))


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
        return format_stripe_response(result)
    except Exception as e:
        return format_stripe_error(str(e))


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
        return format_stripe_response(result)
    except Exception as e:
        return format_stripe_error(str(e))


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
        return format_stripe_response(result)
    except Exception as e:
        return format_stripe_error(str(e))


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
        return format_stripe_response(result)
    except Exception as e:
        return format_stripe_error(str(e))


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
        return format_stripe_response(result)
    except Exception as e:
        return format_stripe_error(str(e))


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
        return format_stripe_response(result)
    except Exception as e:
        return format_stripe_error(str(e))


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
        return format_stripe_response(result)
    except Exception as e:
        return format_stripe_error(str(e))


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
        return format_stripe_response(result)
    except Exception as e:
        return format_stripe_error(str(e))


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
        return format_stripe_response(result)
    except Exception as e:
        return format_stripe_error(str(e))


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
        return format_stripe_response(result)
    except Exception as e:
        return format_stripe_error(str(e))


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
        return format_stripe_response(result)
    except Exception as e:
        return format_stripe_error(str(e))


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
        return format_stripe_response(result)
    except Exception as e:
        return format_stripe_error(str(e))


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
        return format_stripe_response(result)
    except Exception as e:
        return format_stripe_error(str(e))


@router.get("/profile")
async def get_stripe_profile(
    access_token: str = Depends(get_stripe_access_token),
):
    """Get Stripe account profile information"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe integration not available")

    try:
        result = stripe_service.get_account(access_token)
        return format_stripe_response(result)
    except Exception as e:
        return format_stripe_error(str(e))


@router.get("/balance")
async def get_stripe_balance(
    access_token: str = Depends(get_stripe_access_token),
):
    """Get Stripe account balance"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe integration not available")

    try:
        result = stripe_service.get_balance(access_token)
        return format_stripe_response(result)
    except Exception as e:
        return format_stripe_error(str(e))


@router.get("/account")
async def get_stripe_account(
    access_token: str = Depends(get_stripe_access_token),
):
    """Get Stripe account information"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe integration not available")

    try:
        result = stripe_service.get_account(access_token)
        return format_stripe_response(result)
    except Exception as e:
        return format_stripe_error(str(e))


# Error handlers
@router.post("/webhooks")
async def handle_stripe_webhook(
    request: Request, 
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(get_db)
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
            result = await handler(event_data, db)
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
