import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Auth Type: OAuth2
router = APIRouter(prefix="/api/xero", tags=["xero"])

@router.get("/auth/url")
async def get_auth_url():
    """Get Xero OAuth URL"""
    return {
        "url": "https://login.xero.com/identity/connect/authorize?response_type=code&client_id=INSERT_CLIENT_ID&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fxero%2Fcallback&scope=openid profile email accounting.transactions",
        "timestamp": "2025-11-09T17:25:00Z"
    }

@router.get("/callback")
async def handle_oauth_callback(code: str):
    """Handle Xero OAuth callback"""
    return {
        "ok": True,
        "status": "success",
        "code": code,
        "message": "Xero authentication successful (mock)",
        "timestamp": "2025-11-09T17:25:00Z"
    }

class XeroSearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"

class XeroSearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    timestamp: str

@router.get("/status")
async def xero_status(user_id: str = "test_user"):
    """Get Xero integration status"""
    return {
        "ok": True,
        "service": "xero",
        "user_id": user_id,
        "status": "connected",
        "message": "Xero integration is available",
        "timestamp": "2025-11-09T17:25:00Z",
    }

@router.post("/search")
async def xero_search(request: XeroSearchRequest):
    """Search Xero content"""
    logger.info(f"Searching Xero for: {request.query}")

    mock_results = [
        {
            "id": "item_001",
            "title": f"Sample Xero Result - {request.query}",
            "type": "item",
            "snippet": f"This is a sample result from Xero for query: {request.query}",
        }
    ]

    return XeroSearchResponse(
        ok=True,
        query=request.query,
        results=mock_results,
        timestamp="2025-11-09T17:25:00Z",
    )

@router.get("/items")
async def list_xero_items(user_id: str = "test_user"):
    """List Xero items"""
    return {
        "ok": True,
        "items": [
            {
                "id": f"item_{i}",
                "title": f"Xero Item {i}",
                "status": "active",
            }
            for i in range(1, 6)
        ],
        "timestamp": "2025-11-09T17:25:00Z",
    }
