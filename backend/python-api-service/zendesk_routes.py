"""
ATOM Zendesk Integration Routes
FastAPI routes for Zendesk customer support integration
Following ATOM API patterns and conventions
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from loguru import logger
import asyncio

from zendesk_service import create_zendesk_service, ZendeskServiceEnhanced
from db_oauth_zendesk import create_zendesk_db_handler, ZendeskOAuthToken
from auth_handler_zendesk import ZendeskAuthHandler

# Create router
router = APIRouter(prefix="/api/zendesk", tags=["zendesk"])

# Global instances
zendesk_service = create_zendesk_service()
db_handler = create_zendesk_db_handler()
auth_handler = ZendeskAuthHandler()

# Dependencies
async def get_access_token(user_id: str) -> str:
    """Get access token for user"""
    tokens = await db_handler.get_tokens(user_id)
    if not tokens:
        raise HTTPException(status_code=401, detail="Zendesk not authenticated for this user")
    
    # Check if token is expired and refresh if needed
    if await db_handler.is_token_expired(user_id):
        if tokens.refresh_token:
            try:
                new_tokens = await auth_handler.refresh_access_token(tokens.refresh_token)
                await db_handler.save_tokens(ZendeskOAuthToken(
                    user_id=user_id,
                    access_token=new_tokens["access_token"],
                    refresh_token=new_tokens["refresh_token"],
                    token_type=new_tokens["token_type"],
                    expires_in=new_tokens["expires_in"]
                ))
                return new_tokens["access_token"]
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                raise HTTPException(status_code=401, detail="Token expired and refresh failed")
        else:
            raise HTTPException(status_code=401, detail="Token expired and no refresh token available")
    
    return tokens.access_token

# Ticket management endpoints
@router.get("/tickets")
async def get_tickets(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(30, ge=1, le=100, description="Number of tickets to return"),
    status: Optional[str] = Query(None, description="Ticket status filter"),
    priority: Optional[str] = Query(None, description="Ticket priority filter"),
    assigned: bool = Query(False, description="Filter assigned tickets only")
):
    """Get list of tickets with optional filtering"""
    try:
        access_token = await get_access_token(user_id)
        result = await zendesk_service.get_tickets(
            access_token=access_token,
            limit=limit,
            status=status,
            priority=priority,
            assigned=assigned
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "zendesk",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tickets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tickets/{ticket_id}")
async def get_ticket(
    ticket_id: int,
    user_id: str = Query(..., description="User ID")
):
    """Get specific ticket by ID"""
    try:
        access_token = await get_access_token(user_id)
        result = await zendesk_service.get_ticket(ticket_id, access_token)
        
        return {
            "ok": True,
            "data": result,
            "service": "zendesk",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tickets")
async def create_ticket(
    ticket_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Create a new support ticket"""
    try:
        access_token = await get_access_token(user_id)
        
        result = await zendesk_service.create_ticket(
            access_token=access_token,
            subject=ticket_data.get("subject", ""),
            comment=ticket_data.get("comment", ""),
            priority=ticket_data.get("priority"),
            assignee_id=ticket_data.get("assignee_id"),
            requester_email=ticket_data.get("requester_email"),
            tags=ticket_data.get("tags")
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "zendesk",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Ticket created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create ticket: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/tickets/{ticket_id}")
async def update_ticket(
    ticket_id: int,
    update_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Update existing ticket"""
    try:
        access_token = await get_access_token(user_id)
        
        result = await zendesk_service.update_ticket(
            ticket_id=ticket_id,
            access_token=access_token,
            comment=update_data.get("comment"),
            status=update_data.get("status"),
            priority=update_data.get("priority"),
            assignee_id=update_data.get("assignee_id")
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "zendesk",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Ticket updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tickets/{ticket_id}/comments")
async def add_ticket_comment(
    ticket_id: int,
    comment_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Add comment to ticket"""
    try:
        access_token = await get_access_token(user_id)
        
        result = await zendesk_service.add_comment_to_ticket(
            ticket_id=ticket_id,
            access_token=access_token,
            comment=comment_data.get("comment", ""),
            public=comment_data.get("public", True),
            author_id=comment_data.get("author_id")
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "zendesk",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Comment added successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add comment to ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# User management endpoints
@router.get("/users")
async def get_users(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(30, ge=1, le=100, description="Number of users to return"),
    role: Optional[str] = Query(None, description="User role filter")
):
    """Get list of users with optional role filtering"""
    try:
        access_token = await get_access_token(user_id)
        result = await zendesk_service.get_users(
            access_token=access_token,
            limit=limit,
            role=role
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "zendesk",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/{user_zendesk_id}")
async def get_user(
    user_zendesk_id: int,
    user_id: str = Query(..., description="User ID")
):
    """Get specific user by ID"""
    try:
        access_token = await get_access_token(user_id)
        result = await zendesk_service.get_user(user_zendesk_id, access_token)
        
        return {
            "ok": True,
            "data": result,
            "service": "zendesk",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user {user_zendesk_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/users")
async def create_user(
    user_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Create a new user"""
    try:
        access_token = await get_access_token(user_id)
        
        result = await zendesk_service.create_user(
            access_token=access_token,
            name=user_data.get("name", ""),
            email=user_data.get("email", ""),
            phone=user_data.get("phone"),
            organization_id=user_data.get("organization_id"),
            role=user_data.get("role", "end-user")
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "zendesk",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "User created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Organization management endpoints
@router.get("/organizations")
async def get_organizations(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(30, ge=1, le=100, description="Number of organizations to return")
):
    """Get list of organizations"""
    try:
        access_token = await get_access_token(user_id)
        result = await zendesk_service.get_organizations(
            access_token=access_token,
            limit=limit
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "zendesk",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get organizations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/organizations/{org_id}")
async def get_organization(
    org_id: int,
    user_id: str = Query(..., description="User ID")
):
    """Get specific organization by ID"""
    try:
        access_token = await get_access_token(user_id)
        result = await zendesk_service.get_organization(org_id, access_token)
        
        return {
            "ok": True,
            "data": result,
            "service": "zendesk",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get organization {org_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Search and analytics endpoints
@router.get("/search/tickets")
async def search_tickets(
    query: str = Query(..., description="Search query"),
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(30, ge=1, le=100, description="Number of results to return")
):
    """Search tickets by query"""
    try:
        access_token = await get_access_token(user_id)
        result = await zendesk_service.search_tickets(
            access_token=access_token,
            query=query,
            limit=limit
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "zendesk",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search tickets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/tickets")
async def get_ticket_analytics(
    user_id: str = Query(..., description="User ID"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
):
    """Get ticket metrics and analytics"""
    try:
        access_token = await get_access_token(user_id)
        
        # Parse dates if provided
        start_dt = None
        end_dt = None
        if start_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        result = await zendesk_service.get_ticket_metrics(
            access_token=access_token,
            start_date=start_dt,
            end_date=end_dt
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "zendesk",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        logger.error(f"Failed to get ticket analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Authentication endpoints
@router.post("/auth/save")
async def save_auth_data(
    auth_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Save authentication data"""
    try:
        # Save tokens
        tokens_data = auth_data.get("tokens", {})
        tokens = ZendeskOAuthToken(
            user_id=user_id,
            access_token=tokens_data.get("access_token"),
            refresh_token=tokens_data.get("refresh_token"),
            token_type=tokens_data.get("token_type", "Bearer"),
            expires_in=tokens_data.get("expires_in", 3600),
            scope=tokens_data.get("scope", "")
        )
        
        success = await db_handler.save_tokens(tokens)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save tokens")
        
        # Save user data
        user_data_dict = auth_data.get("user", {})
        from db_oauth_zendesk import ZendeskUserData
        user_data = ZendeskUserData(
            user_id=user_id,
            zendesk_user_id=user_data_dict.get("id"),
            email=user_data_dict.get("email"),
            name=user_data_dict.get("name"),
            role=user_data_dict.get("role"),
            phone=user_data_dict.get("phone"),
            organization_id=user_data_dict.get("organization_id"),
            photo_url=user_data_dict.get("photo_url"),
            time_zone=user_data_dict.get("time_zone"),
            subdomain=auth_data.get("subdomain")
        )
        
        await db_handler.save_user_data(user_data)
        
        return {
            "ok": True,
            "message": "Authentication data saved successfully",
            "service": "zendesk",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save auth data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/auth/status")
async def get_auth_status(user_id: str = Query(..., description="User ID")):
    """Get authentication status"""
    try:
        tokens = await db_handler.get_tokens(user_id)
        user_data = await db_handler.get_user_data(user_id)
        is_expired = await db_handler.is_token_expired(user_id)
        
        return {
            "ok": True,
            "data": {
                "authenticated": bool(tokens) and not is_expired,
                "user": user_data,
                "tokens_exist": bool(tokens),
                "token_expired": is_expired
            },
            "service": "zendesk",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get auth status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/auth")
async def revoke_auth(user_id: str = Query(..., description="User ID")):
    """Revoke authentication"""
    try:
        # Get tokens for revocation
        tokens = await db_handler.get_tokens(user_id)
        if tokens and tokens.access_token:
            await auth_handler.revoke_token(tokens.access_token)
        
        # Delete from database
        await db_handler.delete_tokens(user_id)
        
        return {
            "ok": True,
            "message": "Authentication revoked successfully",
            "service": "zendesk",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to revoke auth: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
@router.get("/health")
async def health_check():
    """Zendesk integration health check"""
    try:
        # Check service configuration
        config_status = bool(
            zendesk_service.config.subdomain and
            zendesk_service.config.email and
            zendesk_service.config.token
        )
        
        return {
            "ok": True,
            "data": {
                "service": "zendesk",
                "status": "healthy" if config_status else "misconfigured",
                "configured": config_status,
                "database_connected": db_handler is not None,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Zendesk health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Export router
def register_zendesk_routes(app):
    """Register Zendesk API routes"""
    app.include_router(router)
    logger.info("Zendesk API routes registered")