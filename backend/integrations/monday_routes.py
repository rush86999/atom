from datetime import datetime
import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Auth Type: OAuth2
router = APIRouter(prefix="/api/monday", tags=["monday"])

@router.get("/auth/url")
async def get_auth_url():
    """Get Monday OAuth URL"""
    return {
        "url": "https://auth.monday.com/oauth2/authorize?client_id=INSERT_CLIENT_ID&response_type=code&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fmonday%2Fcallback",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/callback")
async def handle_oauth_callback(code: str):
    """Handle Monday OAuth callback"""
    return {
        "ok": True,
        "status": "success",
        "code": code,
        "message": "Monday authentication successful (mock)",
        "timestamp": datetime.now().isoformat()
    }

class MondaySearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"

@router.get("/status")
async def monday_status(user_id: str = "test_user"):
    """Get Monday integration status"""
    return {
        "ok": True,
        "service": "monday",
        "user_id": user_id,
        "status": "connected",
        "message": "Monday integration is available",
        "timestamp": datetime.now().isoformat(),
    }

@router.post("/search")
async def monday_search(request: MondaySearchRequest):
    """Search Monday boards and items"""
    return {
        "ok": True,
        "query": request.query,
        "results": [
            {
                "id": "board_001",
                "title": f"Project Board - {request.query}",
                "type": "board",
                "items_count": 15,
            }
        ],
        "timestamp": datetime.now().isoformat(),
    }
