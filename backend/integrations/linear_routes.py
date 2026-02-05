"""
Linear Integration Routes for ATOM Platform
Uses the real linear_service.py for all GraphQL operations
"""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .linear_service import linear_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/linear", tags=["linear"])


# Pydantic models
class CreateIssueRequest(BaseModel):
    title: str
    team_id: str
    description: Optional[str] = None
    assignee_id: Optional[str] = None
    priority: Optional[int] = None


class SearchRequest(BaseModel):
    query: str
    team_id: Optional[str] = None


@router.get("/auth/url")
async def get_auth_url(redirect_uri: str = "http://localhost:8000/api/linear/callback"):
    """Get Linear OAuth URL"""
    url = linear_service.get_authorization_url(redirect_uri)
    return {"url": url, "timestamp": datetime.now().isoformat()}


@router.get("/callback")
async def handle_oauth_callback(code: str, redirect_uri: str = "http://localhost:8000/api/linear/callback"):
    """Handle Linear OAuth callback"""
    try:
        tokens = await linear_service.exchange_token(code, redirect_uri)
        return {"ok": True, "status": "success", **tokens, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"ok": False, "status": "error", "message": str(e), "timestamp": datetime.now().isoformat()}


@router.get("/viewer")
async def get_viewer(access_token: Optional[str] = None):
    """Get current user information"""
    try:
        viewer = await linear_service.get_viewer(access_token)
        return {"ok": True, "viewer": viewer, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/issues")
async def get_issues(
    access_token: Optional[str] = None,
    first: int = 50,
    team_id: Optional[str] = None
):
    """Get Linear issues"""
    try:
        issues = await linear_service.get_issues(access_token, first, team_id)
        return {"ok": True, "issues": issues, "count": len(issues), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/issues")
async def create_issue(request: CreateIssueRequest, access_token: Optional[str] = None):
    """Create a new Linear issue"""
    try:
        issue = await linear_service.create_issue(
            title=request.title,
            team_id=request.team_id,
            access_token=access_token,
            description=request.description,
            priority=request.priority,
            assignee_id=request.assignee_id
        )
        return {"ok": True, "issue": issue, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/teams")
async def get_teams(access_token: Optional[str] = None, first: int = 50):
    """Get Linear teams"""
    try:
        teams = await linear_service.get_teams(access_token, first)
        return {"ok": True, "teams": teams, "count": len(teams), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects")
async def get_projects(access_token: Optional[str] = None, first: int = 50):
    """Get Linear projects"""
    try:
        projects = await linear_service.get_projects(access_token, first)
        return {"ok": True, "projects": projects, "count": len(projects), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_issues(request: SearchRequest, access_token: Optional[str] = None):
    """Search Linear issues"""
    try:
        issues = await linear_service.get_issues(access_token, team_id=request.team_id)
        # Filter by query in title/description
        filtered = [i for i in issues if request.query.lower() in (i.get("title", "") + i.get("description", "")).lower()]
        return {"ok": True, "query": request.query, "results": filtered, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"ok": True, "query": request.query, "results": [], "timestamp": datetime.now().isoformat()}


@router.get("/status")
async def linear_status(user_id: str = "test_user"):
    """Get Linear integration status"""
    health = await linear_service.health_check()
    return {
        "ok": health.get("ok", True),
        "service": "linear",
        "user_id": user_id,
        "status": "connected" if linear_service.client_id else "not_configured",
        "message": "Linear integration is available",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/health")
async def linear_health():
    """Health check for Linear integration"""
    health = await linear_service.health_check()
    return {
        "status": "healthy" if health.get("ok") else "unhealthy",
        "service": "linear",
        "configured": bool(linear_service.client_id),
        "timestamp": datetime.now().isoformat()
    }
