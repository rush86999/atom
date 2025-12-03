import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Auth Type: OAuth2
router = APIRouter(prefix="/api/teams", tags=["teams"])

@router.get("/auth/url")
async def get_auth_url():
    """Get Teams OAuth URL"""
    return {
        "url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id=INSERT_CLIENT_ID&response_type=code&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fteams%2Fcallback&response_mode=query&scope=User.Read%20Team.ReadBasic.All",
        "timestamp": "2025-11-09T17:25:00Z"
    }

@router.get("/callback")
async def handle_oauth_callback(code: str):
    """Handle Teams OAuth callback"""
    return {
        "ok": True,
        "status": "success",
        "code": code,
        "message": "Teams authentication successful (mock)",
        "timestamp": "2025-11-09T17:25:00Z"
    }

class TeamsSearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"

class TeamsSearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    timestamp: str

@router.get("/status")
async def teams_status(user_id: str = "test_user"):
    """Get Teams integration status"""
    return {
        "ok": True,
        "service": "teams",
        "user_id": user_id,
        "status": "connected",
        "message": "Teams integration is available",
        "timestamp": "2025-11-09T17:25:00Z",
    }

@router.post("/search")
async def teams_search(request: TeamsSearchRequest):
    """Search Teams content"""
    logger.info(f"Searching Teams for: {request.query}")

    mock_results = [
        {
            "id": "item_001",
            "title": f"Sample Teams Result - {request.query}",
            "type": "item",
            "snippet": f"This is a sample result from Teams for query: {request.query}",
        }
    ]

    return TeamsSearchResponse(
        ok=True,
        query=request.query,
        results=mock_results,
        timestamp="2025-11-09T17:25:00Z",
    )

@router.get("/items")
async def list_teams_items(user_id: str = "test_user"):
    """List Teams items"""
    return {
        "ok": True,
        "items": [
            {
                "id": f"item_{i}",
                "title": f"Teams Item {i}",
                "status": "active",
            }
            for i in range(1, 6)
        ],
        "timestamp": "2025-11-09T17:25:00Z",
    }
