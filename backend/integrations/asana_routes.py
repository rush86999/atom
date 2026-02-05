"""
Enhanced Asana API Routes
Complete Asana integration endpoints for the ATOM platform
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .asana_service import asana_service

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/asana", tags=["asana"])

from core.oauth_handler import ASANA_OAUTH_CONFIG, OAuthHandler
from core.token_storage import token_storage


# Pydantic models for request/response
class TaskCreate(BaseModel):
    name: str = Field(..., description="Task name")
    description: Optional[str] = Field(None, description="Task description")
    due_on: Optional[str] = Field(None, description="Due date (YYYY-MM-DD)")
    assignee: Optional[str] = Field(None, description="Assignee user GID")
    projects: Optional[List[str]] = Field(
        default_factory=list, description="Project GIDs"
    )
    workspace: Optional[str] = Field(None, description="Workspace GID")


class TaskUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Task name")
    description: Optional[str] = Field(None, description="Task description")
    completed: Optional[bool] = Field(None, description="Completion status")
    due_on: Optional[str] = Field(None, description="Due date (YYYY-MM-DD)")
    assignee: Optional[str] = Field(None, description="Assignee user GID")


class CommentCreate(BaseModel):
    text: str = Field(..., description="Comment text")


class SearchQuery(BaseModel):
    query: str = Field(..., description="Search query")
    workspace_gid: str = Field(..., description="Workspace GID")
    limit: Optional[int] = Field(20, description="Result limit")


# Helper function to extract access token
async def get_access_token(user_id: Optional[str] = Query(None, description="User ID")) -> str:
    """
    Extract access token for user.
    Uses centralized token storage and handles automatic refresh.
    """
    # 1. Try to get from persistent storage
    stored_token = token_storage.get_token("asana")
    
    if stored_token:
        # Check if expired
        if token_storage.is_token_expired("asana"):
            logger.info("Asana token expired, attempting refresh...")
            try:
                if stored_token.get("refresh_token"):
                    handler = OAuthHandler(ASANA_OAUTH_CONFIG)
                    new_tokens = await handler.refresh_access_token(stored_token["refresh_token"])
                    
                    # Merge and save
                    for key, value in stored_token.items():
                        if key not in new_tokens:
                            new_tokens[key] = value
                    
                    token_storage.save_token("asana", new_tokens)
                    return new_tokens["access_token"]
            except Exception as e:
                logger.error(f"Failed to refresh Asana token: {e}")
        
        return stored_token["access_token"]
        
    # 2. Check environment variable for production/local dev
    import os
    env_token = os.getenv("ASANA_ACCESS_TOKEN")
    if env_token:
        return env_token

    # 3. No token found - raise proper error
    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "production":
        raise HTTPException(
            status_code=401,
            detail="Asana access token not found. Please provide ASANA_ACCESS_TOKEN environment variable "
            "or complete OAuth authentication to connect your Asana account."
        )
    else:
        # In development, provide a more helpful error message
        raise HTTPException(
            status_code=401,
            detail="Asana access token not found. Please set ASANA_ACCESS_TOKEN environment variable, "
            "or complete OAuth flow at POST /api/asana/auth/token to connect your Asana account."
        )

@router.post("/auth/token")
async def set_access_token(token: str = Body(..., embed=True), user_id: str = Body(None, embed=True)):
    """Set access token for a user (for testing/development)"""
    token_storage.save_token("asana", {"access_token": token, "user_id": user_id})
    return {"status": "success", "message": "Token stored successfully"}


@router.get("/health")
async def asana_health(access_token: str = Depends(get_access_token)):
    """Check Asana API connectivity"""
    try:
        result = await asana_service.health_check(access_token)
        if not result["ok"]:
            raise HTTPException(status_code=503, detail=result["error"])
        return {
            "success": True,
            "ok": True,
            "service": "asana",
            "status": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Asana health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Asana health check failed: {str(e)}"
        )


@router.get("/user/profile")
async def get_user_profile(access_token: str = Depends(get_access_token)):
    """Get current Asana user profile"""
    result = await asana_service.get_user_profile(access_token)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/workspaces")
async def get_workspaces(access_token: str = Depends(get_access_token)):
    """Get user's Asana workspaces"""
    result = await asana_service.get_workspaces(access_token)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/projects")
async def get_projects(
    access_token: str = Depends(get_access_token),
    workspace_gid: Optional[str] = Query(None, description="Workspace GID"),
    team_gid: Optional[str] = Query(None, description="Team GID"),
    limit: int = Query(50, description="Number of projects to return"),
):
    """Get projects from workspace or team"""
    result = await asana_service.get_projects(
        access_token, workspace_gid, team_gid, limit
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/tasks")
async def get_tasks(
    access_token: str = Depends(get_access_token),
    project_gid: Optional[str] = Query(None, description="Project GID"),
    workspace_gid: Optional[str] = Query(None, description="Workspace GID"),
    assignee: Optional[str] = Query(None, description="Assignee user GID"),
    completed_since: Optional[str] = Query(None, description="Completed since date"),
    limit: int = Query(50, description="Number of tasks to return"),
):
    """Get tasks from project or workspace"""
    result = await asana_service.get_tasks(
        access_token, project_gid, workspace_gid, assignee, completed_since, limit
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/tasks")
async def create_task(
    task_data: TaskCreate, access_token: str = Depends(get_access_token)
):
    """Create a new task in Asana"""
    result = await asana_service.create_task(access_token, task_data.dict())
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.put("/tasks/{task_gid}")
async def update_task(
    task_gid: str, updates: TaskUpdate, access_token: str = Depends(get_access_token)
):
    """Update an existing task"""
    result = await asana_service.update_task(
        access_token, task_gid, updates.dict(exclude_none=True)
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/teams")
async def get_teams(
    access_token: str = Depends(get_access_token),
    workspace_gid: str = Query(..., description="Workspace GID"),
    limit: int = Query(50, description="Number of teams to return"),
):
    """Get teams in a workspace"""
    result = await asana_service.get_teams(access_token, workspace_gid, limit)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/users")
async def get_users(
    access_token: str = Depends(get_access_token),
    workspace_gid: str = Query(..., description="Workspace GID"),
    limit: int = Query(50, description="Number of users to return"),
):
    """Get users in a workspace"""
    result = await asana_service.get_users(access_token, workspace_gid, limit)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/search")
async def search_tasks(
    search_query: SearchQuery, access_token: str = Depends(get_access_token)
):
    """Search for tasks in workspace"""
    result = await asana_service.search_tasks(
        access_token, search_query.workspace_gid, search_query.query, search_query.limit
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/tasks/{task_gid}/stories")
async def get_task_stories(
    task_gid: str,
    access_token: str = Depends(get_access_token),
    limit: int = Query(20, description="Number of stories to return"),
):
    """Get stories (comments) for a task"""
    result = await asana_service.get_task_stories(access_token, task_gid, limit)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/tasks/{task_gid}/comments")
async def add_task_comment(
    task_gid: str, comment: CommentCreate, access_token: str = Depends(get_access_token)
):
    """Add a comment to a task"""
    result = await asana_service.add_task_comment(access_token, task_gid, comment.text)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/status")
async def get_integration_status(access_token: str = Depends(get_access_token)):
    """Get comprehensive Asana integration status"""
    try:
        # Check connectivity and get user info
        health_result = await asana_service.health_check(access_token)

        if health_result["ok"]:
            # Get workspaces to show available data
            workspaces_result = await asana_service.get_workspaces(access_token)

            return {
                "ok": True,
                "connected": True,
                "user": health_result.get("user"),
                "workspaces": workspaces_result.get("workspaces", [])
                if workspaces_result["ok"]
                else [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "Asana integration is active and connected",
            }
        else:
            return {
                "ok": False,
                "connected": False,
                "error": health_result.get("error"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "Asana integration is disconnected",
            }

    except Exception as e:
        logger.error(f"Failed to get integration status: {e}")
        return {
            "ok": False,
            "connected": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "Failed to check integration status",
        }


# Error handlers
@router.get("/error-test")
async def error_test():
    """Test endpoint for error handling"""
    raise HTTPException(status_code=400, detail="This is a test error")


# Webhook endpoints (for future implementation)
@router.post("/webhooks")
async def create_webhook():
    """Create Asana webhook (future implementation)"""
    return {"message": "Webhook creation endpoint - not yet implemented"}


@router.delete("/webhooks/{webhook_gid}")
async def delete_webhook(webhook_gid: str):
    """Delete Asana webhook (future implementation)"""
    return {
        "message": f"Webhook deletion endpoint for {webhook_gid} - not yet implemented"
    }
