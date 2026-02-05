from datetime import datetime
import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .gitlab_service import GitLabService

logger = logging.getLogger(__name__)

# Create router
# Auth Type: OAuth2
router = APIRouter(prefix="/api/gitlab", tags=["gitlab"])

@router.get("/auth/url")
async def get_auth_url():
    """Get GitLab OAuth URL"""
    return {
        "url": "https://gitlab.com/oauth/authorize?client_id=INSERT_CLIENT_ID&redirect_uri=REDIRECT_URI&response_type=code",
        "timestamp": datetime.now().isoformat()
    }

# Initialize service
gitlab_service = GitLabService()

class GitlabAuthRequest(BaseModel):
    code: str
    redirect_uri: str

class GitlabSearchRequest(BaseModel):
    query: str

@router.post("/auth/callback")
async def gitlab_auth_callback(auth_request: GitlabAuthRequest):
    """Exchange authorization code for access token"""
    try:
        token_data = await gitlab_service.exchange_token(auth_request.code, auth_request.redirect_uri)
        return {
            "ok": True,
            "data": token_data,
            "service": "gitlab"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/user")
async def get_user(access_token: str = Query(..., description="Access Token")):
    """Get authenticated user info"""
    user = await gitlab_service.get_user(access_token)
    return {"ok": True, "data": user}

@router.get("/projects")
async def list_projects(
    access_token: str = Query(..., description="Access Token"),
    limit: int = Query(20, ge=1, le=100)
):
    """List GitLab projects"""
    projects = await gitlab_service.get_projects(access_token, limit)
    return {"ok": True, "data": projects, "count": len(projects)}

@router.get("/issues")
async def list_issues(
    access_token: str = Query(..., description="Access Token"),
    project_id: Optional[str] = Query(None, description="Project ID filter"),
    limit: int = Query(20, ge=1, le=100)
):
    """List GitLab issues"""
    issues = await gitlab_service.get_issues(access_token, project_id, limit)
    return {"ok": True, "data": issues, "count": len(issues)}

@router.post("/search")
async def gitlab_search(
    request: GitlabSearchRequest,
    access_token: str = Query(..., description="Access Token")
):
    """Search GitLab projects"""
    results = await gitlab_service.search_projects(access_token, request.query)
    return {
        "ok": True,
        "query": request.query,
        "results": results,
        "count": len(results)
    }

@router.get("/status")
async def gitlab_status():
    """Get GitLab integration status"""
    return {
        "ok": True,
        "service": "gitlab",
        "status": "active",
        "version": "1.0.0",
        "mode": "real"
    }

@router.get("/")
async def gitlab_root():
    """GitLab integration root endpoint"""
    return {
        "service": "gitlab",
        "status": "active",
        "endpoints": [
            "/auth/callback",
            "/user",
            "/projects",
            "/issues",
            "/search",
            "/status"
        ]
    }
