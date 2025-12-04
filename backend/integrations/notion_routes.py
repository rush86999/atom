import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Auth Type: OAuth2
router = APIRouter(prefix="/api/notion", tags=["notion"])

@router.get("/auth/url")
async def get_auth_url():
    """Get Notion OAuth URL"""
    return {
        "url": "https://api.notion.com/v1/oauth/authorize?client_id=INSERT_CLIENT_ID&response_type=code&owner=user&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fnotion%2Fcallback",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/callback")
async def handle_oauth_callback(code: str):
    """Handle Notion OAuth callback"""
    return {
        "ok": True,
        "status": "success",
        "code": code,
        "message": "Notion authentication successful (mock)",
        "timestamp": datetime.now().isoformat()
    }

class NotionSearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"

class NotionSearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    timestamp: str

@router.get("/status")
async def notion_status(user_id: str = "test_user"):
    """Get Notion integration status"""
    return {
        "ok": True,
        "service": "notion",
        "user_id": user_id,
        "status": "connected",
        "message": "Notion integration is available",
        "timestamp": datetime.now().isoformat(),
    }

@router.post("/search")
async def notion_search(request: NotionSearchRequest):
    """Search Notion pages and databases"""
    logger.info(f"Searching Notion for: {request.query}")

    mock_results = [
        {
            "id": "page_001",
            "title": f"Meeting Notes - {request.query}",
            "type": "page",
            "url": "https://notion.so/mock-page",
            "last_edited": datetime.now().isoformat(),
            "snippet": f"Discussion about {request.query} and project planning",
        }
    ]

    return NotionSearchResponse(
        ok=True,
        query=request.query,
        results=mock_results,
        timestamp=datetime.now().isoformat(),
    )

@router.get("/pages/{page_id}")
async def get_notion_page(page_id: str, user_id: str = "test_user"):
    """Get a specific Notion page"""
    return {
        "ok": True,
        "page_id": page_id,
        "title": f"Sample Notion Page - {page_id}",
        "content": f"This is the content of Notion page {page_id}.",
        "timestamp": datetime.now().isoformat(),
    }
