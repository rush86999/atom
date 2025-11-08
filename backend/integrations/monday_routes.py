"""
Monday.com API Routes

This module provides FastAPI routes for Monday.com integration including:
- OAuth 2.0 authentication flow
- Board and item management
- Workspace and user operations
- Webhook management
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from .monday_service import MondayService

logger = logging.getLogger(__name__)

# Initialize router
monday_router = APIRouter(prefix="/monday", tags=["monday"])

# Initialize service
monday_service = MondayService()


# Request/Response Models
class OAuthStartResponse(BaseModel):
    authorization_url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    code: str
    state: str


class OAuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str
    scope: str


class BoardCreateRequest(BaseModel):
    name: str
    board_kind: str = "public"
    workspace_id: Optional[str] = None
    template_id: Optional[str] = None


class ItemCreateRequest(BaseModel):
    board_id: str
    name: str
    column_values: Optional[Dict[str, str]] = None


class ItemUpdateRequest(BaseModel):
    column_values: Dict[str, str]


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    details: Optional[Dict] = None
    error: Optional[str] = None


# Helper function to get access token from request
async def get_access_token(request: Request) -> str:
    """Extract access token from Authorization header"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Missing or invalid Authorization header"
        )
    return auth_header.replace("Bearer ", "")


# OAuth Routes
@monday_router.get("/oauth/start", response_model=OAuthStartResponse)
async def start_oauth_flow(state: Optional[str] = None):
    """Start Monday.com OAuth 2.0 flow"""
    try:
        authorization_url = monday_service.get_authorization_url(state)
        return OAuthStartResponse(
            authorization_url=authorization_url, state=state or "default"
        )
    except Exception as e:
        logger.error(f"Failed to start OAuth flow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@monday_router.post("/oauth/callback", response_model=OAuthTokenResponse)
async def handle_oauth_callback(request: OAuthCallbackRequest):
    """Handle OAuth callback and exchange code for tokens"""
    try:
        token_data = monday_service.exchange_code_for_token(request.code)
        return OAuthTokenResponse(**token_data)
    except Exception as e:
        logger.error(f"Failed to handle OAuth callback: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@monday_router.post("/oauth/refresh")
async def refresh_access_token(refresh_token: str):
    """Refresh access token using refresh token"""
    try:
        token_data = monday_service.refresh_access_token(refresh_token)
        return token_data
    except Exception as e:
        logger.error(f"Failed to refresh access token: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Board Routes
@monday_router.get("/boards")
async def get_boards(
    access_token: str = Depends(get_access_token),
    workspace_id: Optional[str] = Query(None),
):
    """Get all boards from Monday.com"""
    try:
        boards = monday_service.get_boards(access_token, workspace_id)
        return {"boards": boards}
    except Exception as e:
        logger.error(f"Failed to fetch boards: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@monday_router.get("/boards/{board_id}")
async def get_board(board_id: str, access_token: str = Depends(get_access_token)):
    """Get specific board details"""
    try:
        board = monday_service.get_board(access_token, board_id)
        if not board:
            raise HTTPException(status_code=404, detail="Board not found")
        return {"board": board}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch board: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@monday_router.post("/boards", status_code=201)
async def create_board(
    board_data: BoardCreateRequest, access_token: str = Depends(get_access_token)
):
    """Create a new board"""
    try:
        board = monday_service.create_board(
            access_token,
            board_data.name,
            board_data.board_kind,
            board_data.workspace_id,
            board_data.template_id,
        )
        return {"board": board}
    except Exception as e:
        logger.error(f"Failed to create board: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Item Routes
@monday_router.get("/boards/{board_id}/items")
async def get_items(
    board_id: str,
    access_token: str = Depends(get_access_token),
    limit: int = Query(50, ge=1, le=200),
):
    """Get items from a specific board"""
    try:
        items = monday_service.get_items(access_token, board_id, limit)
        return {"items": items}
    except Exception as e:
        logger.error(f"Failed to fetch items: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@monday_router.post("/boards/{board_id}/items", status_code=201)
async def create_item(
    board_id: str,
    item_data: ItemCreateRequest,
    access_token: str = Depends(get_access_token),
):
    """Create a new item on a board"""
    try:
        item = monday_service.create_item(
            access_token, board_id, item_data.name, item_data.column_values
        )
        return {"item": item}
    except Exception as e:
        logger.error(f"Failed to create item: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@monday_router.put("/items/{item_id}")
async def update_item(
    item_id: str,
    update_data: ItemUpdateRequest,
    access_token: str = Depends(get_access_token),
):
    """Update an existing item"""
    try:
        item = monday_service.update_item(
            access_token, item_id, update_data.column_values
        )
        return {"item": item}
    except Exception as e:
        logger.error(f"Failed to update item: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Workspace Routes
@monday_router.get("/workspaces")
async def get_workspaces(access_token: str = Depends(get_access_token)):
    """Get all workspaces"""
    try:
        workspaces = monday_service.get_workspaces(access_token)
        return {"workspaces": workspaces}
    except Exception as e:
        logger.error(f"Failed to fetch workspaces: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# User Routes
@monday_router.get("/users")
async def get_users(
    access_token: str = Depends(get_access_token),
    workspace_id: Optional[str] = Query(None),
):
    """Get users in workspace"""
    try:
        users = monday_service.get_users(access_token, workspace_id)
        return {"users": users}
    except Exception as e:
        logger.error(f"Failed to fetch users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Search Routes
@monday_router.get("/search")
async def search_items(
    access_token: str = Depends(get_access_token),
    query: str = Query(..., min_length=1),
    board_ids: Optional[List[str]] = Query(None),
):
    """Search items across boards"""
    try:
        items = monday_service.search_items(access_token, query, board_ids)
        return {"items": items}
    except Exception as e:
        logger.error(f"Failed to search items: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Health Routes
@monday_router.get("/health", response_model=HealthResponse)
async def health_check(access_token: str = Depends(get_access_token)):
    """Check Monday.com service health"""
    try:
        health_status = monday_service.get_health_status(access_token)
        return HealthResponse(**health_status)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="error", timestamp=datetime.now().isoformat(), error=str(e)
        )


# Webhook Routes (placeholder for future implementation)
@monday_router.post("/webhooks")
async def create_webhook():
    """Create webhook for Monday.com events"""
    # TODO: Implement webhook creation
    return {"message": "Webhook creation not yet implemented"}


@monday_router.delete("/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str):
    """Delete webhook"""
    # TODO: Implement webhook deletion
    return {"message": "Webhook deletion not yet implemented"}
