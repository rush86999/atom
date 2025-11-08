"""
Bitbucket API Routes

FastAPI routes for Bitbucket integration providing:
- OAuth 2.0 authentication flow
- Repository and branch management
- Pull request and code review operations
- Pipeline and deployment management
- Team and workspace collaboration
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from .bitbucket_service import BitbucketService

logger = logging.getLogger(__name__)

# Initialize router
bitbucket_router = APIRouter(prefix="/bitbucket", tags=["bitbucket"])

# Initialize service
bitbucket_service = BitbucketService()


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


class PullRequestCreateRequest(BaseModel):
    title: str
    source_branch: str
    destination_branch: str = "main"
    description: str = ""
    reviewers: Optional[List[str]] = None


class IssueCreateRequest(BaseModel):
    title: str
    content: str = ""
    kind: str = "bug"
    priority: str = "major"


class PipelineTriggerRequest(BaseModel):
    branch: str = "main"
    variables: Optional[Dict[str, str]] = None


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    user: Optional[str] = None
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
@bitbucket_router.get("/oauth/start", response_model=OAuthStartResponse)
async def start_oauth_flow(state: Optional[str] = None):
    """Start Bitbucket OAuth 2.0 flow"""
    try:
        authorization_url = bitbucket_service.get_authorization_url(state)
        return OAuthStartResponse(
            authorization_url=authorization_url, state=state or "default"
        )
    except Exception as e:
        logger.error(f"Failed to start OAuth flow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@bitbucket_router.post("/oauth/callback", response_model=OAuthTokenResponse)
async def handle_oauth_callback(request: OAuthCallbackRequest):
    """Handle OAuth callback and exchange code for tokens"""
    try:
        token_data = bitbucket_service.exchange_code_for_token(request.code)
        return OAuthTokenResponse(**token_data)
    except Exception as e:
        logger.error(f"Failed to handle OAuth callback: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@bitbucket_router.post("/oauth/refresh")
async def refresh_access_token(refresh_token: str):
    """Refresh access token using refresh token"""
    try:
        token_data = bitbucket_service.refresh_access_token(refresh_token)
        return token_data
    except Exception as e:
        logger.error(f"Failed to refresh access token: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Workspace Routes
@bitbucket_router.get("/workspaces")
async def get_workspaces(access_token: str = Depends(get_access_token)):
    """Get all workspaces for the authenticated user"""
    try:
        workspaces = bitbucket_service.get_workspaces(access_token)
        return {"workspaces": workspaces}
    except Exception as e:
        logger.error(f"Failed to fetch workspaces: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Repository Routes
@bitbucket_router.get("/repositories")
async def get_repositories(
    access_token: str = Depends(get_access_token),
    workspace: Optional[str] = Query(None),
):
    """Get repositories from workspace or user"""
    try:
        repositories = bitbucket_service.get_repositories(access_token, workspace)
        return {"repositories": repositories}
    except Exception as e:
        logger.error(f"Failed to fetch repositories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@bitbucket_router.get("/repositories/{workspace}/{repo_slug}")
async def get_repository(
    workspace: str,
    repo_slug: str,
    access_token: str = Depends(get_access_token),
):
    """Get specific repository details"""
    try:
        repository = bitbucket_service.get_repository(
            access_token, workspace, repo_slug
        )
        if not repository:
            raise HTTPException(status_code=404, detail="Repository not found")
        return {"repository": repository}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch repository: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Branch Routes
@bitbucket_router.get("/repositories/{workspace}/{repo_slug}/branches")
async def get_branches(
    workspace: str,
    repo_slug: str,
    access_token: str = Depends(get_access_token),
):
    """Get branches for a repository"""
    try:
        branches = bitbucket_service.get_branches(access_token, workspace, repo_slug)
        return {"branches": branches}
    except Exception as e:
        logger.error(f"Failed to fetch branches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Pull Request Routes
@bitbucket_router.get("/repositories/{workspace}/{repo_slug}/pull-requests")
async def get_pull_requests(
    workspace: str,
    repo_slug: str,
    access_token: str = Depends(get_access_token),
    state: str = Query("OPEN", regex="^(OPEN|MERGED|DECLINED|SUPERSEDED)$"),
):
    """Get pull requests for a repository"""
    try:
        pull_requests = bitbucket_service.get_pull_requests(
            access_token, workspace, repo_slug, state
        )
        return {"pull_requests": pull_requests}
    except Exception as e:
        logger.error(f"Failed to fetch pull requests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@bitbucket_router.get("/repositories/{workspace}/{repo_slug}/pull-requests/{pr_id}")
async def get_pull_request(
    workspace: str,
    repo_slug: str,
    pr_id: str,
    access_token: str = Depends(get_access_token),
):
    """Get specific pull request details"""
    try:
        pull_request = bitbucket_service.get_pull_request(
            access_token, workspace, repo_slug, pr_id
        )
        if not pull_request:
            raise HTTPException(status_code=404, detail="Pull request not found")
        return {"pull_request": pull_request}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch pull request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@bitbucket_router.post(
    "/repositories/{workspace}/{repo_slug}/pull-requests", status_code=201
)
async def create_pull_request(
    workspace: str,
    repo_slug: str,
    pr_data: PullRequestCreateRequest,
    access_token: str = Depends(get_access_token),
):
    """Create a new pull request"""
    try:
        pull_request = bitbucket_service.create_pull_request(
            access_token,
            workspace,
            repo_slug,
            pr_data.title,
            pr_data.source_branch,
            pr_data.destination_branch,
            pr_data.description,
            pr_data.reviewers,
        )
        return {"pull_request": pull_request}
    except Exception as e:
        logger.error(f"Failed to create pull request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Commit Routes
@bitbucket_router.get("/repositories/{workspace}/{repo_slug}/commits")
async def get_commits(
    workspace: str,
    repo_slug: str,
    access_token: str = Depends(get_access_token),
    branch: Optional[str] = Query(None),
):
    """Get commits for a repository"""
    try:
        commits = bitbucket_service.get_commits(
            access_token, workspace, repo_slug, branch
        )
        return {"commits": commits}
    except Exception as e:
        logger.error(f"Failed to fetch commits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Pipeline Routes
@bitbucket_router.get("/repositories/{workspace}/{repo_slug}/pipelines")
async def get_pipelines(
    workspace: str,
    repo_slug: str,
    access_token: str = Depends(get_access_token),
):
    """Get pipelines for a repository"""
    try:
        pipelines = bitbucket_service.get_pipelines(access_token, workspace, repo_slug)
        return {"pipelines": pipelines}
    except Exception as e:
        logger.error(f"Failed to fetch pipelines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@bitbucket_router.post("/repositories/{workspace}/{repo_slug}/pipelines/trigger")
async def trigger_pipeline(
    workspace: str,
    repo_slug: str,
    pipeline_data: PipelineTriggerRequest,
    access_token: str = Depends(get_access_token),
):
    """Trigger a pipeline for a repository"""
    try:
        pipeline = bitbucket_service.trigger_pipeline(
            access_token,
            workspace,
            repo_slug,
            pipeline_data.branch,
            pipeline_data.variables,
        )
        return {"pipeline": pipeline}
    except Exception as e:
        logger.error(f"Failed to trigger pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Issue Routes
@bitbucket_router.get("/repositories/{workspace}/{repo_slug}/issues")
async def get_issues(
    workspace: str,
    repo_slug: str,
    access_token: str = Depends(get_access_token),
):
    """Get issues for a repository"""
    try:
        issues = bitbucket_service.get_issues(access_token, workspace, repo_slug)
        return {"issues": issues}
    except Exception as e:
        logger.error(f"Failed to fetch issues: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@bitbucket_router.post("/repositories/{workspace}/{repo_slug}/issues", status_code=201)
async def create_issue(
    workspace: str,
    repo_slug: str,
    issue_data: IssueCreateRequest,
    access_token: str = Depends(get_access_token),
):
    """Create a new issue"""
    try:
        issue = bitbucket_service.create_issue(
            access_token,
            workspace,
            repo_slug,
            issue_data.title,
            issue_data.content,
            issue_data.kind,
            issue_data.priority,
        )
        return {"issue": issue}
    except Exception as e:
        logger.error(f"Failed to create issue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Search Routes
@bitbucket_router.get("/search/code")
async def search_code(
    access_token: str = Depends(get_access_token),
    query: str = Query(..., min_length=1),
    workspace: Optional[str] = Query(None),
):
    """Search code across repositories"""
    try:
        results = bitbucket_service.search_code(access_token, query, workspace)
        return {"results": results}
    except Exception as e:
        logger.error(f"Failed to search code: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# User Routes
@bitbucket_router.get("/user")
async def get_user_info(access_token: str = Depends(get_access_token)):
    """Get current user information"""
    try:
        user_info = bitbucket_service.get_user_info(access_token)
        return {"user": user_info}
    except Exception as e:
        logger.error(f"Failed to fetch user info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Webhook Routes
@bitbucket_router.get("/repositories/{workspace}/{repo_slug}/webhooks")
async def get_webhooks(
    workspace: str,
    repo_slug: str,
    access_token: str = Depends(get_access_token),
):
    """Get webhooks for a repository"""
    try:
        webhooks = bitbucket_service.get_webhooks(access_token, workspace, repo_slug)
        return {"webhooks": webhooks}
    except Exception as e:
        logger.error(f"Failed to fetch webhooks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Health Routes
@bitbucket_router.get("/health", response_model=HealthResponse)
async def health_check(access_token: str = Depends(get_access_token)):
    """Check Bitbucket service health"""
    try:
        health_status = bitbucket_service.get_health_status(access_token)
        return HealthResponse(**health_status)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="error", timestamp=datetime.now().isoformat(), error=str(e)
        )


# Analytics Routes
@bitbucket_router.get("/analytics/summary")
async def get_analytics_summary(access_token: str = Depends(get_access_token)):
    """Get analytics summary for Bitbucket integration"""
    try:
        # Get basic metrics
        workspaces = bitbucket_service.get_workspaces(access_token)
        repositories = bitbucket_service.get_repositories(access_token)
        user_info = bitbucket_service.get_user_info(access_token)

        return {
            "summary": {
                "total_workspaces": len(workspaces),
                "total_repositories": len(repositories),
                "user": user_info.get("display_name"),
                "account_type": user_info.get("type"),
                "created_at": user_info.get("created_on"),
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to fetch analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
