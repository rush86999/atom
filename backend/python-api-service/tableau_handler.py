from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, Any, Optional
import logging
import asyncio
from tableau_service import TableauService
from auth_handler_tableau import get_tableau_oauth_handler
from db_oauth_tableau import get_user_tableau_tokens, is_tableau_token_expired, refresh_tableau_tokens

router = APIRouter(prefix="/api/tableau", tags=["tableau"])
logger = logging.getLogger(__name__)

# Service cache
tableau_service_cache = {}

async def get_tableau_service(request: Request) -> TableauService:
    """Get Tableau service instance with user tokens"""
    try:
        user_id = request.headers.get("x-user-id", "current")
        
        # Get service instance from cache or create new
        cache_key = f"tableau_{user_id}"
        if cache_key not in tableau_service_cache:
            tableau_service_cache[cache_key] = TableauService(user_id)
            
            # Initialize with database pool
            from main_api_app import get_db_pool
            db_pool = await get_db_pool()
            
            # Initialize service
            if not await tableau_service_cache[cache_key].initialize(db_pool):
                # Try to refresh tokens if expired
                tokens = await get_user_tableau_tokens(db_pool, user_id)
                if tokens and await is_tableau_token_expired(db_pool, user_id):
                    oauth_handler = get_tableau_oauth_handler()
                    refresh_result = await oauth_handler.refresh_access_token(tokens["refresh_token"])
                    
                    if refresh_result["success"]:
                        await refresh_tableau_tokens(db_pool, user_id, refresh_result["data"])
                        await tableau_service_cache[cache_key].initialize(db_pool)
                    else:
                        raise HTTPException(status_code=401, detail="Tableau authentication failed")
        
        return tableau_service_cache[cache_key]
        
    except Exception as e:
        logger.error(f"Failed to get Tableau service: {e}")
        raise HTTPException(status_code=500, detail="Tableau service initialization failed")

@router.get("/health")
async def health_check():
    """Health check for Tableau integration"""
    try:
        # Check environment variables
        required_vars = ["TABLEAU_CLIENT_ID", "TABLEAU_CLIENT_SECRET", "ATOM_OAUTH_ENCRYPTION_KEY"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            return {
                "status": "unhealthy",
                "error": f"Missing environment variables: {', '.join(missing_vars)}"
            }
        
        services = {
            "tableau_api": "available",
            "oauth": "available",
            "workbooks": "available",
            "projects": "available",
            "data_sources": "available",
            "views": "available",
            "users": "available"
        }
        
        return {
            "status": "healthy",
            "service": "tableau",
            "services": services,
            "timestamp": "2025-11-07T00:00:00Z"
        }
        
    except Exception as e:
        logger.error(f"Tableau health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@router.get("/auth/url")
async def get_auth_url(request: Request):
    """Get Tableau OAuth authorization URL"""
    try:
        oauth_handler = get_tableau_oauth_handler()
        state = oauth_handler.generate_state()
        
        # Store state in session (in production, use Redis or database)
        auth_url = await oauth_handler.get_authorization_url(state)
        
        return {
            "success": True,
            "auth_url": auth_url,
            "state": state
        }
        
    except Exception as e:
        logger.error(f"Failed to generate Tableau auth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth/callback")
async def auth_callback(request: Request):
    """Handle Tableau OAuth callback"""
    try:
        body = await request.json()
        code = body.get("code")
        state = body.get("state")
        
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code not provided")
        
        oauth_handler = get_tableau_oauth_handler()
        
        # Exchange code for tokens
        token_result = await oauth_handler.exchange_code_for_tokens(code)
        
        if not token_result["success"]:
            raise HTTPException(status_code=400, detail=token_result["error"])
        
        # Get user's Tableau sites
        tokens = token_result["data"]
        sites_result = await oauth_handler.get_user_sites(tokens["access_token"])
        
        if not sites_result["success"]:
            raise HTTPException(status_code=400, detail="Failed to get Tableau sites")
        
        # Store tokens in database
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        token_manager = get_tableau_token_manager()
        
        # Use default site
        default_site = sites_result["data"]["default_site"]
        
        await token_manager.store_tableau_tokens(
            db_pool,
            request.headers.get("x-user-id", "current"),
            "user@tableau.com",  # This would come from user profile
            tokens,
            default_site
        )
        
        # Log activity
        await token_manager.log_tableau_activity(
            db_pool,
            request.headers.get("x-user-id", "current"),
            "oauth_login",
            {
                "site_id": default_site.get("id"),
                "site_name": default_site.get("name"),
                "timestamp": datetime.now().isoformat()
            }
        )
        
        return {
            "success": True,
            "message": "Authentication successful",
            "site": default_site,
            "tokens": {
                "expires_in": tokens["expires_in"],
                "created_at": tokens["created_at"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tableau auth callback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/workbooks")
async def get_workbooks(
    request: Request,
    tableau_service: TableauService = Depends(get_tableau_service)
):
    """Get Tableau workbooks"""
    try:
        body = await request.json()
        page_size = body.get("page_size", 100)
        page_number = body.get("page_number", 1)
        
        result = await tableau_service.get_workbooks(page_size, page_number)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Tableau workbooks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workbooks/{workbook_id}")
async def get_workbook_details(
    workbook_id: str,
    request: Request,
    tableau_service: TableauService = Depends(get_tableau_service)
):
    """Get workbook details"""
    try:
        result = await tableau_service.get_workbook_details(workbook_id)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get workbook details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workbooks/{workbook_id}/views")
async def get_workbook_views(
    workbook_id: str,
    request: Request,
    tableau_service: TableauService = Depends(get_tableau_service)
):
    """Get workbook views"""
    try:
        query_params = dict(request.query_params)
        page_size = int(query_params.get("page_size", 100))
        
        result = await tableau_service.get_workbook_views(workbook_id, page_size)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get workbook views: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workbooks/{workbook_id}/data")
async def get_workbook_data(
    workbook_id: str,
    request: Request,
    tableau_service: TableauService = Depends(get_tableau_service)
):
    """Get workbook data"""
    try:
        query_params = dict(request.query_params)
        view_id = query_params.get("view_id")
        
        result = await tableau_service.get_workbook_data(workbook_id, view_id)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get workbook data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workbooks/{workbook_id}/embed")
async def get_workbook_embed_code(
    workbook_id: str,
    request: Request,
    tableau_service: TableauService = Depends(get_tableau_service)
):
    """Get workbook embed code"""
    try:
        query_params = dict(request.query_params)
        view_id = query_params.get("view_id")
        width = int(query_params.get("width", 800))
        height = int(query_params.get("height", 600))
        
        result = await tableau_service.get_embed_code(workbook_id, view_id, width, height)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get embed code: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects")
async def get_projects(
    request: Request,
    tableau_service: TableauService = Depends(get_tableau_service)
):
    """Get Tableau projects"""
    try:
        body = await request.json()
        page_size = body.get("page_size", 100)
        
        result = await tableau_service.get_projects(page_size)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Tableau projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/create")
async def create_project(
    project_data: Dict[str, Any],
    request: Request,
    tableau_service: TableauService = Depends(get_tableau_service)
):
    """Create a new project"""
    try:
        name = project_data.get("name")
        description = project_data.get("description")
        parent_project_id = project_data.get("parent_project_id")
        
        result = await tableau_service.create_project(name, description, parent_project_id)
        return result
        
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/data-sources")
async def get_data_sources(
    request: Request,
    tableau_service: TableauService = Depends(get_tableau_service)
):
    """Get Tableau data sources"""
    try:
        body = await request.json()
        page_size = body.get("page_size", 100)
        
        result = await tableau_service.get_data_sources(page_size)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Tableau data sources: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/data-sources/{datasource_id}/refresh")
async def refresh_datasource(
    datasource_id: str,
    request: Request,
    tableau_service: TableauService = Depends(get_tableau_service)
):
    """Refresh data source extract"""
    try:
        result = await tableau_service.refresh_extract(datasource_id)
        return result
        
    except Exception as e:
        logger.error(f"Failed to refresh data source: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/users")
async def get_users(
    request: Request,
    tableau_service: TableauService = Depends(get_tableau_service)
):
    """Get Tableau users"""
    try:
        body = await request.json()
        page_size = body.get("page_size", 100)
        
        result = await tableau_service.get_users(page_size)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Tableau users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/workbooks/search")
async def search_workbooks(
    search_data: Dict[str, Any],
    request: Request,
    tableau_service: TableauService = Depends(get_tableau_service)
):
    """Search Tableau workbooks"""
    try:
        query = search_data.get("query")
        page_size = search_data.get("page_size", 50)
        
        if not query:
            raise HTTPException(status_code=400, detail="Search query is required")
        
        result = await tableau_service.search_workbooks(query, page_size)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search Tableau workbooks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/usage/metrics")
async def get_usage_metrics(
    metrics_request: Dict[str, Any],
    request: Request,
    tableau_service: TableauService = Depends(get_tableau_service)
):
    """Get usage metrics"""
    try:
        workbook_id = metrics_request.get("workbook_id")
        days = metrics_request.get("days", 30)
        
        result = await tableau_service.get_usage_metrics(workbook_id, days)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get usage metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logout")
async def logout(request: Request):
    """Logout from Tableau"""
    try:
        user_id = request.headers.get("x-user-id", "current")
        
        # Delete tokens from database
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        token_manager = get_tableau_token_manager()
        
        await token_manager.delete_tableau_tokens(db_pool, user_id)
        
        # Clear service cache
        cache_key = f"tableau_{user_id}"
        if cache_key in tableau_service_cache:
            del tableau_service_cache[cache_key]
        
        return {
            "success": True,
            "message": "Logged out successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to logout from Tableau: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_tableau_stats(
    request: Request,
    tableau_service: TableauService = Depends(get_tableau_service)
):
    """Get Tableau statistics for user"""
    try:
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        token_manager = get_tableau_token_manager()
        
        stats = await token_manager.get_tableau_stats(db_pool, request.headers.get("x-user-id", "current"))
        
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get Tableau stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))