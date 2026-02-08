"""
Plaid Integration Routes for ATOM Platform
Uses the real plaid_service.py for all banking operations
"""

from datetime import datetime
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Import the real Plaid service
from .plaid_service import plaid_service

logger = logging.getLogger(__name__)

# Auth Type: OAuth2 + Link
router = APIRouter(prefix="/api/plaid", tags=["plaid"])


# Pydantic models
class LinkTokenRequest(BaseModel):
    user_id: str
    client_name: str = "ATOM Platform"
    country_codes: Optional[List[str]] = None
    products: Optional[List[str]] = None


class PublicTokenExchangeRequest(BaseModel):
    public_token: str


class TransactionsRequest(BaseModel):
    access_token: str
    start_date: str
    end_date: str
    count: int = 100
    offset: int = 0


class AccessTokenRequest(BaseModel):
    access_token: str


@router.post("/link/token/create")
async def create_link_token(request: LinkTokenRequest):
    """Create a Link token for Plaid Link initialization"""
    try:
        result = await plaid_service.create_link_token(
            user_id=request.user_id,
            client_name=request.client_name,
            country_codes=request.country_codes,
            products=request.products
        )
        return {
            "ok": True,
            **result,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create link token: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/item/public_token/exchange")
async def exchange_public_token(request: PublicTokenExchangeRequest):
    """Exchange a public token for an access token"""
    try:
        result = await plaid_service.exchange_public_token(request.public_token)
        return {
            "ok": True,
            **result,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to exchange public token: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/accounts/get")
async def get_accounts(request: AccessTokenRequest):
    """Get accounts for a connected item"""
    try:
        result = await plaid_service.get_accounts(request.access_token)
        return {
            "ok": True,
            **result,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/accounts/balance/get")
async def get_balance(request: AccessTokenRequest):
    """Get real-time balance for accounts"""
    try:
        result = await plaid_service.get_balance(request.access_token)
        return {
            "ok": True,
            **result,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transactions/get")
async def get_transactions(request: TransactionsRequest):
    """Get transactions for an item"""
    try:
        result = await plaid_service.get_transactions(
            access_token=request.access_token,
            start_date=request.start_date,
            end_date=request.end_date,
            count=request.count,
            offset=request.offset
        )
        return {
            "ok": True,
            **result,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get transactions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/identity/get")
async def get_identity(request: AccessTokenRequest):
    """Get identity information for accounts"""
    try:
        result = await plaid_service.get_identity(request.access_token)
        return {
            "ok": True,
            **result,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get identity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/item/remove")
async def remove_item(request: AccessTokenRequest):
    """Remove an item (disconnect bank connection)"""
    try:
        result = await plaid_service.remove_item(request.access_token)
        return {
            "ok": True,
            **result,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove item: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def plaid_status():
    """Status check for Plaid integration"""
    health = await plaid_service.health_check()
    return {
        "ok": health.get("ok", True),
        "status": "active" if plaid_service.client_id else "not_configured",
        "service": "plaid",
        "environment": plaid_service.environment,
        "version": "1.0.0",
        "business_value": {
            "financial_insights": True,
            "expense_tracking": True,
            "budget_management": True,
            "account_aggregation": True,
            "transaction_history": True
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/health")
async def plaid_health():
    """Health check for Plaid integration"""
    health = await plaid_service.health_check()
    return {
        "status": "healthy" if health.get("ok") else "unhealthy",
        "service": "plaid",
        "configured": bool(plaid_service.client_id and plaid_service.secret),
        "environment": plaid_service.environment,
        "capabilities": [
            "link_token_creation",
            "account_access",
            "balance_check",
            "transactions",
            "identity_verification"
        ],
        "timestamp": datetime.now().isoformat()
    }


# Legacy endpoints for backward compatibility
@router.get("/auth/url")
async def get_auth_url():
    """Get Plaid Link URL (redirects to link token creation)"""
    return {
        "message": "Use POST /api/plaid/link/token/create to generate a Link token",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/callback")
async def handle_oauth_callback(public_token: str):
    """Handle Plaid Link callback"""
    try:
        result = await plaid_service.exchange_public_token(public_token)
        return {
            "ok": True,
            "status": "success",
            **result,
            "message": "Plaid authentication successful",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "ok": False,
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }
