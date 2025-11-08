from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, Any, Optional
import logging
import asyncio
from hubspot_service import HubSpotService
from auth_handler_hubspot import get_hubspot_oauth_handler
from db_oauth_hubspot import get_user_hubspot_tokens, is_hubspot_token_expired, refresh_hubspot_tokens

router = APIRouter(prefix="/api/hubspot", tags=["hubspot"])
logger = logging.getLogger(__name__)

# Service cache
hubspot_service_cache = {}

async def get_hubspot_service(request: Request) -> HubSpotService:
    """Get HubSpot service instance with user tokens"""
    try:
        user_id = request.headers.get("x-user-id", "current")
        
        # Get service instance from cache or create new
        cache_key = f"hubspot_{user_id}"
        if cache_key not in hubspot_service_cache:
            hubspot_service_cache[cache_key] = HubSpotService(user_id)
            
            # Initialize with database pool
            from main_api_app import get_db_pool
            db_pool = await get_db_pool()
            
            # Initialize service
            if not await hubspot_service_cache[cache_key].initialize(db_pool):
                # Try to refresh tokens if expired
                tokens = await get_user_hubspot_tokens(db_pool, user_id)
                if tokens and await is_hubspot_token_expired(db_pool, user_id):
                    oauth_handler = get_hubspot_oauth_handler()
                    refresh_result = await oauth_handler.refresh_access_token(tokens["refresh_token"])
                    
                    if refresh_result["success"]:
                        await refresh_hubspot_tokens(db_pool, user_id, refresh_result["data"])
                        await hubspot_service_cache[cache_key].initialize(db_pool)
                    else:
                        raise HTTPException(status_code=401, detail="HubSpot authentication failed")
        
        return hubspot_service_cache[cache_key]
        
    except Exception as e:
        logger.error(f"Failed to get HubSpot service: {e}")
        raise HTTPException(status_code=500, detail="HubSpot service initialization failed")

@router.get("/health")
async def health_check():
    """Health check for HubSpot integration"""
    try:
        # Check environment variables
        required_vars = ["HUBSPOT_CLIENT_ID", "HUBSPOT_CLIENT_SECRET", "ATOM_OAUTH_ENCRYPTION_KEY"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            return {
                "status": "unhealthy",
                "error": f"Missing environment variables: {', '.join(missing_vars)}"
            }
        
        services = {
            "crm": "available",
            "contacts": "available",
            "companies": "available",
            "deals": "available",
            "tickets": "available",
            "pipelines": "available",
            "search": "available",
            "oauth": "available"
        }
        
        return {
            "status": "healthy",
            "service": "hubspot",
            "services": services,
            "timestamp": "2025-11-07T00:00:00Z"
        }
        
    except Exception as e:
        logger.error(f"HubSpot health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@router.get("/auth/url")
async def get_auth_url(request: Request):
    """Get HubSpot OAuth authorization URL"""
    try:
        oauth_handler = get_hubspot_oauth_handler()
        state = oauth_handler.generate_state()
        
        # Store state in session (in production, use Redis or database)
        auth_url = await oauth_handler.get_authorization_url(state)
        
        return {
            "success": True,
            "auth_url": auth_url,
            "state": state
        }
        
    except Exception as e:
        logger.error(f"Failed to generate HubSpot auth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth/callback")
async def auth_callback(request: Request):
    """Handle HubSpot OAuth callback"""
    try:
        body = await request.json()
        code = body.get("code")
        state = body.get("state")
        
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code not provided")
        
        oauth_handler = get_hubspot_oauth_handler()
        
        # Exchange code for tokens
        token_result = await oauth_handler.exchange_code_for_tokens(code)
        
        if not token_result["success"]:
            raise HTTPException(status_code=400, detail=token_result["error"])
        
        # Get user info
        tokens = token_result["data"]
        user_info_result = await oauth_handler.get_user_info(tokens["access_token"])
        
        if not user_info_result["success"]:
            raise HTTPException(status_code=400, detail="Failed to get HubSpot user info")
        
        # Store tokens in database
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        token_manager = get_hubspot_token_manager()
        
        user_info = user_info_result["data"]
        
        await token_manager.store_hubspot_tokens(
            db_pool,
            request.headers.get("x-user-id", "current"),
            "user@hubspot.com",  # This would come from user profile
            user_info.get("hub_id", "default"),
            tokens
        )
        
        # Log activity
        await token_manager.log_hubspot_activity(
            db_pool,
            request.headers.get("x-user-id", "current"),
            "oauth_login",
            {
                "hub_id": user_info.get("hub_id"),
                "user_id": user_info.get("user_id"),
                "timestamp": datetime.now().isoformat()
            }
        )
        
        return {
            "success": True,
            "message": "Authentication successful",
            "user_info": user_info,
            "tokens": {
                "expires_in": tokens["expires_in"],
                "created_at": tokens["created_at"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HubSpot auth callback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Contacts endpoints
@router.post("/contacts")
async def get_contacts(
    request: Request,
    hubspot_service: HubSpotService = Depends(get_hubspot_service)
):
    """Get HubSpot contacts"""
    try:
        body = await request.json()
        limit = body.get("limit", 100)
        after = body.get("after")
        properties = body.get("properties")
        
        result = await hubspot_service.get_contacts(limit, after, properties)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get HubSpot contacts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/contacts/create")
async def create_contact(
    contact_data: Dict[str, Any],
    request: Request,
    hubspot_service: HubSpotService = Depends(get_hubspot_service)
):
    """Create a new contact"""
    try:
        result = await hubspot_service.create_contact(contact_data)
        return result
        
    except Exception as e:
        logger.error(f"Failed to create contact: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/contacts/{contact_id}")
async def update_contact(
    contact_id: str,
    contact_data: Dict[str, Any],
    request: Request,
    hubspot_service: HubSpotService = Depends(get_hubspot_service)
):
    """Update contact"""
    try:
        result = await hubspot_service.update_contact(contact_id, contact_data)
        return result
        
    except Exception as e:
        logger.error(f"Failed to update contact: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/contacts/{contact_id}")
async def delete_contact(
    contact_id: str,
    request: Request,
    hubspot_service: HubSpotService = Depends(get_hubspot_service)
):
    """Delete contact"""
    try:
        result = await hubspot_service.delete_contact(contact_id)
        return result
        
    except Exception as e:
        logger.error(f"Failed to delete contact: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Companies endpoints
@router.post("/companies")
async def get_companies(
    request: Request,
    hubspot_service: HubSpotService = Depends(get_hubspot_service)
):
    """Get HubSpot companies"""
    try:
        body = await request.json()
        limit = body.get("limit", 100)
        after = body.get("after")
        properties = body.get("properties")
        
        result = await hubspot_service.get_companies(limit, after, properties)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get HubSpot companies: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/companies/create")
async def create_company(
    company_data: Dict[str, Any],
    request: Request,
    hubspot_service: HubSpotService = Depends(get_hubspot_service)
):
    """Create a new company"""
    try:
        result = await hubspot_service.create_company(company_data)
        return result
        
    except Exception as e:
        logger.error(f"Failed to create company: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Deals endpoints
@router.post("/deals")
async def get_deals(
    request: Request,
    hubspot_service: HubSpotService = Depends(get_hubspot_service)
):
    """Get HubSpot deals"""
    try:
        body = await request.json()
        limit = body.get("limit", 100)
        after = body.get("after")
        properties = body.get("properties")
        
        result = await hubspot_service.get_deals(limit, after, properties)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get HubSpot deals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/deals/create")
async def create_deal(
    deal_data: Dict[str, Any],
    request: Request,
    hubspot_service: HubSpotService = Depends(get_hubspot_service)
):
    """Create a new deal"""
    try:
        result = await hubspot_service.create_deal(deal_data)
        return result
        
    except Exception as e:
        logger.error(f"Failed to create deal: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Tickets endpoints
@router.post("/tickets")
async def get_tickets(
    request: Request,
    hubspot_service: HubSpotService = Depends(get_hubspot_service)
):
    """Get HubSpot tickets"""
    try:
        body = await request.json()
        limit = body.get("limit", 100)
        after = body.get("after")
        properties = body.get("properties")
        
        result = await hubspot_service.get_tickets(limit, after, properties)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get HubSpot tickets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Pipelines endpoints
@router.post("/pipelines/{object_type}")
async def get_pipelines(
    object_type: str,
    request: Request,
    hubspot_service: HubSpotService = Depends(get_hubspot_service)
):
    """Get HubSpot pipelines"""
    try:
        result = await hubspot_service.get_pipelines(object_type)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get HubSpot pipelines: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Search endpoints
@router.post("/search/{object_type}")
async def search_objects(
    object_type: str,
    search_data: Dict[str, Any],
    request: Request,
    hubspot_service: HubSpotService = Depends(get_hubspot_service)
):
    """Search HubSpot objects"""
    try:
        query = search_data.get("query")
        limit = search_data.get("limit", 50)
        
        if not query:
            raise HTTPException(status_code=400, detail="Search query is required")
        
        result = await hubspot_service.search_objects(object_type, query, limit)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search HubSpot objects: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Analytics endpoints
@router.post("/analytics/stats")
async def get_engagement_stats(
    analytics_request: Dict[str, Any],
    request: Request,
    hubspot_service: HubSpotService = Depends(get_hubspot_service)
):
    """Get engagement statistics"""
    try:
        start_date = analytics_request.get("start_date")
        end_date = analytics_request.get("end_date")
        
        result = await hubspot_service.get_engagement_stats(start_date, end_date)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get engagement stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_hubspot_stats(
    request: Request,
    hubspot_service: HubSpotService = Depends(get_hubspot_service)
):
    """Get HubSpot statistics for user"""
    try:
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        token_manager = get_hubspot_token_manager()
        
        stats = await token_manager.get_hubspot_stats(db_pool, request.headers.get("x-user-id", "current"))
        
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get HubSpot stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logout")
async def logout(request: Request):
    """Logout from HubSpot"""
    try:
        user_id = request.headers.get("x-user-id", "current")
        
        # Delete tokens from database
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        token_manager = get_hubspot_token_manager()
        
        await token_manager.delete_hubspot_tokens(db_pool, user_id)
        
        # Clear service cache
        cache_key = f"hubspot_{user_id}"
        if cache_key in hubspot_service_cache:
            del hubspot_service_cache[cache_key]
        
        return {
            "success": True,
            "message": "Logged out successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to logout from HubSpot: {e}")
        raise HTTPException(status_code=500, detail=str(e))