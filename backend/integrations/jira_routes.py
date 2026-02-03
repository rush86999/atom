import logging
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Auth Type: OAuth2
router = APIRouter(prefix="/api/jira", tags=["jira"])

@router.get("/auth/url")
async def get_auth_url():
    """Get Jira OAuth URL"""
    return {
        "url": "https://auth.atlassian.com/authorize?audience=api.atlassian.com&client_id=INSERT_CLIENT_ID&scope=read%3Ajira-work%20write%3Ajira-work&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fjira%2Fcallback&state=test_state&response_type=code&prompt=consent",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/callback")
async def handle_oauth_callback(code: str):
    """Handle Jira OAuth callback"""
    return {
        "ok": True,
        "status": "success",
        "code": code,
        "message": "Jira authentication successful (mock)",
        "timestamp": datetime.now().isoformat()
    }

class JiraSearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"

class JiraSearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    timestamp: str

@router.get("/status")
async def jira_status(user_id: str = "test_user"):
    """Get Jira integration status"""
    return {
        "ok": True,
        "service": "jira",
        "user_id": user_id,
        "status": "connected",
        "message": "Jira integration is available",
        "timestamp": datetime.now().isoformat(),
    }

@router.post("/search")
async def jira_search(request: JiraSearchRequest):
    """Search Jira content"""
    logger.info(f"Searching Jira for: {request.query}")

    mock_results = [
        {
            "id": "item_001",
            "title": f"Sample Jira Result - {request.query}",
            "type": "item",
            "snippet": f"This is a sample result from Jira for query: {request.query}",
        }
    ]

    return JiraSearchResponse(
        ok=True,
        query=request.query,
        results=mock_results,
        timestamp=datetime.now().isoformat(),
    )

@router.get("/items")
async def list_jira_items(user_id: str = "test_user"):
    """List Jira items"""
    return {
        "ok": True,
        "items": [
            {
                "id": f"item_{i}",
                "title": f"Jira Item {i}",
                "status": "active",
            }
            for i in range(1, 6)
        ],
        "timestamp": datetime.now().isoformat(),
    }
