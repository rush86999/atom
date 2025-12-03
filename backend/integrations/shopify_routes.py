import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Auth Type: OAuth2
router = APIRouter(prefix="/api/shopify", tags=["shopify"])

@router.get("/auth/url")
async def get_auth_url():
    """Get Shopify OAuth URL"""
    return {
        "url": "https://{shop}.myshopify.com/admin/oauth/authorize?client_id=INSERT_CLIENT_ID&scope=read_products,read_orders&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fshopify%2Fcallback",
        "timestamp": "2025-11-09T17:25:00Z"
    }

@router.get("/callback")
async def handle_oauth_callback(code: str):
    """Handle Shopify OAuth callback"""
    return {
        "ok": True,
        "status": "success",
        "code": code,
        "message": "Shopify authentication successful (mock)",
        "timestamp": "2025-11-09T17:25:00Z"
    }

class ShopifySearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"

class ShopifySearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    timestamp: str

@router.get("/status")
async def shopify_status(user_id: str = "test_user"):
    """Get Shopify integration status"""
    return {
        "ok": True,
        "service": "shopify",
        "user_id": user_id,
        "status": "connected",
        "message": "Shopify integration is available",
        "timestamp": "2025-11-09T17:25:00Z",
    }

@router.post("/search")
async def shopify_search(request: ShopifySearchRequest):
    """Search Shopify content"""
    logger.info(f"Searching Shopify for: {request.query}")

    mock_results = [
        {
            "id": "item_001",
            "title": f"Sample Shopify Result - {request.query}",
            "type": "item",
            "snippet": f"This is a sample result from Shopify for query: {request.query}",
        }
    ]

    return ShopifySearchResponse(
        ok=True,
        query=request.query,
        results=mock_results,
        timestamp="2025-11-09T17:25:00Z",
    )

@router.get("/items")
async def list_shopify_items(user_id: str = "test_user"):
    """List Shopify items"""
    return {
        "ok": True,
        "items": [
            {
                "id": f"item_{i}",
                "title": f"Shopify Item {i}",
                "status": "active",
            }
            for i in range(1, 6)
        ],
        "timestamp": "2025-11-09T17:25:00Z",
    }
