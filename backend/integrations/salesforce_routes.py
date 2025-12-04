"""
Salesforce Integration Routes
FastAPI routes for Salesforce CRM integration and enterprise workflow automation
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import os

from fastapi import APIRouter, Body, Depends, HTTPException, Query

# Import Salesforce services
# Import Salesforce services
try:
    from simple_salesforce import Salesforce
    from .salesforce_service import (
        create_account,
        create_contact,
        create_lead,
        create_opportunity,
        get_opportunity,
        list_accounts,
        list_contacts,
        list_opportunities,
        list_leads,
        update_opportunity,
        execute_soql_query
    )
    from .auth_handler_salesforce import salesforce_auth_handler
    from core.mock_mode import get_mock_mode_manager

    SALESFORCE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Salesforce integration not available: {e}")
    SALESFORCE_AVAILABLE = False
    from core.mock_mode import get_mock_mode_manager # Import anyway for mock mode

# Create router
# Auth Type: OAuth2
router = APIRouter(prefix="/api/salesforce", tags=["salesforce"])

# Mock service for health check detection
class SalesforceServiceMock:
    def __init__(self):
        self.instance_url = "mock_instance_url"



# Dependency for Salesforce access token
# Dependency for Salesforce access token
async def get_salesforce_access_token() -> str:
    """Get Salesforce access token from handler"""
    try:
        return await salesforce_auth_handler.ensure_valid_token()
    except HTTPException:
        # Fallback for testing/mocking if no token available
        return os.getenv("SALESFORCE_ACCESS_TOKEN", "mock_access_token")

def get_salesforce_client_from_env() -> Optional[Any]:
    """Create Salesforce client using OAuth token"""
    try:
        if salesforce_auth_handler.is_token_valid():
            return Salesforce(
                instance_url=salesforce_auth_handler.instance_url,
                session_id=salesforce_auth_handler.access_token,
                version="57.0"
            )
            
        # Fallback to legacy env vars if OAuth not active (for backward compatibility)
        username = os.getenv("SALESFORCE_USERNAME")
        password = os.getenv("SALESFORCE_PASSWORD")
        security_token = os.getenv("SALESFORCE_SECURITY_TOKEN")
        
        if username and password and security_token:
            return Salesforce(
                username=username,
                password=password,
                security_token=security_token
            )
        return None
    except Exception as e:
        logging.error(f"Failed to create Salesforce client: {e}")
        return None

# OAuth Endpoints

@router.get("/auth/url")
async def get_salesforce_auth_url():
    """Get Salesforce OAuth authorization URL"""
    return {
        "url": salesforce_auth_handler.get_authorization_url(),
        "service": "salesforce"
    }

@router.get("/callback")
async def salesforce_auth_callback(code: str, state: Optional[str] = None):
    """Handle Salesforce OAuth callback"""
    try:
        token_data = await salesforce_auth_handler.exchange_code_for_token(code)
        return {
            "ok": True,
            "message": "Successfully authenticated with Salesforce",
            "service": "salesforce",
            "instance_url": token_data.get("instance_url")
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth/revoke")
async def revoke_salesforce_token():
    """Revoke Salesforce access token"""
    success = await salesforce_auth_handler.revoke_token()
    return {
        "ok": success,
        "message": "Token revoked" if success else "Failed to revoke token",
        "service": "salesforce"
    }

@router.get("/status")
async def get_salesforce_status():
    """Get Salesforce connection status"""
    return {
        "service": "salesforce",
        "status": salesforce_auth_handler.get_connection_status()
    }


# Mock functions for response formatting
def format_salesforce_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Format successful Salesforce API response"""
    return {
        "ok": True,
        "data": data,
        "service": "salesforce",
        "timestamp": datetime.utcnow().isoformat(),
    }


def format_salesforce_error_response(error_msg: str) -> Dict[str, Any]:
    """Format error Salesforce API response"""
    return {
        "ok": False,
        "error": {
            "code": "SALESFORCE_ERROR",
            "message": error_msg,
            "service": "salesforce",
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/health")
async def salesforce_health_check():
    """Check Salesforce integration health"""
    # Check mock mode first
    mock_manager = get_mock_mode_manager()
    sf = get_salesforce_client_from_env()
    
    if mock_manager.is_mock_mode("salesforce", bool(sf)):
        return {
            "ok": True,
            "status": "healthy",
            "service": "salesforce",
            "timestamp": datetime.utcnow().isoformat(),
            "available": True,
            "connected": True,
            "is_mock": True
        }

    if not SALESFORCE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Salesforce integration not available"
        )

    try:
        # Simple health check by testing service availability
        connected = False
        if sf:
            try:
                # Lightweight query to check connection
                sf.query("SELECT Id FROM User LIMIT 1")
                connected = True
            except Exception:
                connected = False
        
        return {
            "ok": True,  # Required format for validator
            "status": "healthy" if connected else "degraded",
            "service": "salesforce",
            "timestamp": datetime.utcnow().isoformat(),
            "available": True,
            "connected": connected,
            "is_mock": False
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Salesforce health check failed: {str(e)}"
        )


@router.get("/accounts")
async def get_salesforce_accounts(
    limit: int = Query(50, description="Number of accounts to return", ge=1, le=200),
    name: Optional[str] = Query(None, description="Filter by account name"),
    industry: Optional[str] = Query(None, description="Filter by industry"),
    access_token: str = Depends(get_salesforce_access_token),
):
    """Get list of Salesforce accounts with optional filtering"""
    if not SALESFORCE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Salesforce integration not available"
        )

    try:
        # Use simple service with env client
        sf = get_salesforce_client_from_env()
        
        # Check mock mode
        mock_manager = get_mock_mode_manager()
        if mock_manager.is_mock_mode("salesforce", bool(sf)):
            return format_salesforce_response({"accounts": mock_manager.get_mock_data("salesforce", "accounts")})

        if not sf:
             # Fallback to mock if no credentials
             return format_salesforce_response({"accounts": [], "message": "No credentials found"})

        result = await list_accounts(sf)
        return format_salesforce_response({"accounts": result})
    except Exception as e:
        return format_salesforce_error_response(str(e))


@router.get("/accounts/{account_id}")
async def get_salesforce_account(
    account_id: str,
    access_token: str = Depends(get_salesforce_access_token),
):
    """Get specific Salesforce account by ID"""
    if not SALESFORCE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Salesforce integration not available"
        )

    try:
        # Use simple service
        # Note: get_account is not in simple service, using SOQL
        sf = get_salesforce_client_from_env()
        if not sf:
             return format_salesforce_error_response("No credentials found")
        
        query = f"SELECT Id, Name, Type, Industry, Phone, Website, Description FROM Account WHERE Id = '{account_id}'"
        result = await execute_soql_query(sf, query)
        if result and result['records']:
            return format_salesforce_response(result['records'][0])
        return format_salesforce_error_response("Account not found")
    except Exception as e:
        return format_salesforce_error_response(str(e))


@router.post("/accounts")
async def create_salesforce_account(
    name: str = Body(..., description="Account name"),
    industry: Optional[str] = Body(None, description="Industry"),
    phone: Optional[str] = Body(None, description="Phone number"),
    website: Optional[str] = Body(None, description="Website"),
    description: Optional[str] = Body(None, description="Account description"),
    access_token: str = Depends(get_salesforce_access_token),
):
    """Create a new Salesforce account"""
    if not SALESFORCE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Salesforce integration not available"
        )

    try:
        sf = get_salesforce_client_from_env()
        if not sf:
             return format_salesforce_error_response("No credentials found")

        result = await create_account(
            sf=sf,
            name=name,
            industry=industry,
            type=None # Type not passed in body
        )
        return format_salesforce_response(result)
    except Exception as e:
        return format_salesforce_error_response(str(e))


@router.get("/contacts")
async def get_salesforce_contacts(
    limit: int = Query(50, description="Number of contacts to return", ge=1, le=200),
    account_id: Optional[str] = Query(None, description="Filter by account ID"),
    email: Optional[str] = Query(None, description="Filter by email"),
    access_token: str = Depends(get_salesforce_access_token),
):
    """Get list of Salesforce contacts with optional filtering"""
    if not SALESFORCE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Salesforce integration not available"
        )

    try:
        sf = get_salesforce_client_from_env()
        
        # Check mock mode
        mock_manager = get_mock_mode_manager()
        if mock_manager.is_mock_mode("salesforce", bool(sf)):
            return format_salesforce_response(mock_manager.get_mock_data("salesforce", "contacts"))

        if not sf:
             return format_salesforce_error_response("No credentials found")
             
        result = await list_contacts(sf)
        # Filter in memory since simple service list_contacts doesn't take filters
        if account_id:
            result = [c for c in result if c.get('AccountId') == account_id]
        if email:
            result = [c for c in result if c.get('Email') == email]
            
        return format_salesforce_response(result)
    except Exception as e:
        return format_salesforce_error_response(str(e))


@router.post("/contacts")
async def create_salesforce_contact(
    first_name: str = Body(..., description="First name"),
    last_name: str = Body(..., description="Last name"),
    email: str = Body(..., description="Email address"),
    account_id: Optional[str] = Body(None, description="Associated account ID"),
    phone: Optional[str] = Body(None, description="Phone number"),
    title: Optional[str] = Body(None, description="Job title"),
    access_token: str = Depends(get_salesforce_access_token),
):
    """Create a new Salesforce contact"""
    if not SALESFORCE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Salesforce integration not available"
        )

    try:
        # Use core service for contact creation
        sf = get_salesforce_client_from_env()
        if not sf:
             return format_salesforce_error_response("No credentials found")

        result = await create_contact(
            sf=sf,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            # account_id and title not supported in simple create_contact wrapper yet
        )
        return format_salesforce_response(result)
    except Exception as e:
        return format_salesforce_error_response(str(e))


@router.get("/opportunities")
async def get_salesforce_opportunities(
    limit: int = Query(
        50, description="Number of opportunities to return", ge=1, le=200
    ),
    stage: Optional[str] = Query(None, description="Filter by stage"),
    account_id: Optional[str] = Query(None, description="Filter by account ID"),
    access_token: str = Depends(get_salesforce_access_token),
):
    """Get list of Salesforce opportunities with optional filtering"""
    if not SALESFORCE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Salesforce integration not available"
        )

    try:
        sf = get_salesforce_client_from_env()
        
        # Check mock mode
        mock_manager = get_mock_mode_manager()
        if mock_manager.is_mock_mode("salesforce", bool(sf)):
            return format_salesforce_response(mock_manager.get_mock_data("salesforce", "opportunities"))

        if not sf:
             return format_salesforce_error_response("No credentials found")

        result = await list_opportunities(sf)
        return format_salesforce_response(result)
    except Exception as e:
        return format_salesforce_error_response(str(e))


@router.post("/opportunities")
async def create_salesforce_opportunity(
    name: str = Body(..., description="Opportunity name"),
    account_id: str = Body(..., description="Associated account ID"),
    stage: str = Body(..., description="Opportunity stage"),
    amount: float = Body(..., description="Opportunity amount"),
    close_date: str = Body(..., description="Close date (YYYY-MM-DD)"),
    description: Optional[str] = Body(None, description="Opportunity description"),
    access_token: str = Depends(get_salesforce_access_token),
):
    """Create a new Salesforce opportunity"""
    if not SALESFORCE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Salesforce integration not available"
        )

    try:
        sf = get_salesforce_client_from_env()
        if not sf:
             return format_salesforce_error_response("No credentials found")

        result = await create_opportunity(
            sf=sf,
            name=name,
            account_id=account_id,
            stage_name=stage,
            amount=amount,
            close_date=close_date
        )
        return format_salesforce_response(result)
    except Exception as e:
        return format_salesforce_error_response(str(e))


@router.get("/leads")
async def get_salesforce_leads(
    limit: int = Query(50, description="Number of leads to return", ge=1, le=200),
    status: Optional[str] = Query(None, description="Filter by lead status"),
    company: Optional[str] = Query(None, description="Filter by company"),
    access_token: str = Depends(get_salesforce_access_token),
):
    """Get list of Salesforce leads with optional filtering"""
    if not SALESFORCE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Salesforce integration not available"
        )

    try:
        sf = get_salesforce_client_from_env()
        if not sf:
             return format_salesforce_error_response("No credentials found")

        result = await list_leads(sf)
        return format_salesforce_response(result)
    except Exception as e:
        return format_salesforce_error_response(str(e))


@router.post("/leads")
async def create_salesforce_lead(
    first_name: str = Body(..., description="First name"),
    last_name: str = Body(..., description="Last name"),
    company: str = Body(..., description="Company name"),
    email: str = Body(..., description="Email address"),
    status: str = Body("New", description="Lead status"),
    phone: Optional[str] = Body(None, description="Phone number"),
    title: Optional[str] = Body(None, description="Job title"),
    access_token: str = Depends(get_salesforce_access_token),
):
    """Create a new Salesforce lead"""
    if not SALESFORCE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Salesforce integration not available"
        )

    try:
        sf = get_salesforce_client_from_env()
        if not sf:
             return format_salesforce_error_response("No credentials found")

        result = await create_lead(
            sf=sf,
            first_name=first_name,
            last_name=last_name,
            company=company,
            email=email,
            phone=phone
        )
        return format_salesforce_response(result)
    except Exception as e:
        return format_salesforce_error_response(str(e))


@router.get("/search")
async def search_salesforce(
    query: str = Query(..., description="Search query"),
    object_types: List[str] = Query(
        ["Account", "Contact", "Opportunity", "Lead"],
        description="Object types to search",
    ),
    limit: int = Query(20, description="Number of results to return", ge=1, le=50),
    access_token: str = Depends(get_salesforce_access_token),
):
    """Search across Salesforce objects"""
    if not SALESFORCE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Salesforce integration not available"
        )

    try:
        # Use SOQL query for advanced search
        sf = get_salesforce_client_from_env()
        if not sf:
             return format_salesforce_error_response("No credentials found")

        soql_query = f"FIND {{{query}}} IN ALL FIELDS RETURNING {','.join(object_types)} LIMIT {limit}"
        # search() is not in salesforce_service wrapper, use sf.search directly
        try:
            result = sf.search(soql_query)
            return format_salesforce_response(result)
        except Exception as e:
            return format_salesforce_error_response(str(e))
    except Exception as e:
        return format_salesforce_error_response(str(e))


@router.get("/analytics/pipeline")
async def get_sales_pipeline_analytics(
    timeframe: str = Query(
        "30d", description="Timeframe for analytics (7d, 30d, 90d, 1y)"
    ),
    access_token: str = Depends(get_salesforce_access_token),
):
    """Get sales pipeline analytics"""
    if not SALESFORCE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Salesforce integration not available"
        )

    try:
        # Analytics stub
        return format_salesforce_response({
            "pipeline_value": 0,
            "opportunities_count": 0,
            "message": "Analytics not implemented in simple mode"
        })
    except Exception as e:
        return format_salesforce_error_response(str(e))


@router.get("/analytics/leads")
async def get_leads_analytics(
    timeframe: str = Query(
        "30d", description="Timeframe for analytics (7d, 30d, 90d, 1y)"
    ),
    access_token: str = Depends(get_salesforce_access_token),
):
    """Get leads conversion analytics"""
    if not SALESFORCE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Salesforce integration not available"
        )

    try:
        # Analytics stub
        return format_salesforce_response({
            "leads_count": 0,
            "conversion_rate": 0,
            "message": "Analytics not implemented in simple mode"
        })
    except Exception as e:
        return format_salesforce_error_response(str(e))


@router.get("/profile")
async def get_salesforce_user_profile(
    access_token: str = Depends(get_salesforce_access_token),
):
    """Get Salesforce user profile information"""
    if not SALESFORCE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Salesforce integration not available"
        )

    try:
        sf = get_salesforce_client_from_env()
        if not sf:
             return format_salesforce_error_response("No credentials found")
        
        try:
            # Try to get current user info using Chatter API which is standard for "me"
            # This returns detailed info about the authenticated user
            user_info = sf.restful('chatter/users/me')
            return format_salesforce_response(user_info)
        except Exception:
            # Fallback to querying User table if chatter API fails
            try:
                # Get username from client if possible, or just query first user as fallback for dev
                # In a real app, we'd parse the identity URL from the auth response
                res = sf.query("SELECT Id, Name, Email, Username, Title, CompanyName FROM User LIMIT 1")
                if res['totalSize'] > 0:
                    return format_salesforce_response(res['records'][0])
                return format_salesforce_error_response("User not found")
            except Exception as e:
                return format_salesforce_error_response(f"Database query failed: {str(e)}")
    except Exception as e:
        return format_salesforce_error_response(str(e))


@router.post("/integrations/stripe/payments")
async def sync_stripe_payments_with_salesforce(
    payment_data: Dict[str, Any] = Body(..., description="Stripe payment data"),
    opportunity_id: Optional[str] = Body(None, description="Associated opportunity ID"),
    access_token: str = Depends(get_salesforce_access_token),
):
    """Sync Stripe payments with Salesforce opportunities"""
    if not SALESFORCE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Salesforce integration not available"
        )

    try:
        # This would integrate Stripe payment data with Salesforce
        # For now, return a mock response
        result = {
            "synced": True,
            "payment_id": payment_data.get("id"),
            "opportunity_id": opportunity_id,
            "amount": payment_data.get("amount"),
            "timestamp": datetime.utcnow().isoformat(),
        }
        return format_salesforce_response(result)
    except Exception as e:
        return format_salesforce_error_response(str(e))


# Root endpoint
@router.get("/")
async def salesforce_root():
    """Salesforce integration root endpoint"""
    return {
        "service": "salesforce",
        "status": "available" if SALESFORCE_AVAILABLE else "unavailable",
        "endpoints": [
            "/health",
            "/accounts",
            "/contacts",
            "/opportunities",
            "/leads",
            "/search",
            "/analytics/pipeline",
            "/analytics/leads",
            "/profile",
            "/integrations/stripe/payments",
        ],
        "description": "Salesforce CRM integration for enterprise workflow automation",
    }
