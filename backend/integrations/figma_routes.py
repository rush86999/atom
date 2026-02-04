import logging
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .figma_service import get_figma_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/figma", tags=["figma"])

class FigmaSearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"

class FigmaSearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    timestamp: str

# OAuth Endpoints
@router.get("/oauth/url")
async def get_figma_oauth_url(state: Optional[str] = None):
    """Get Figma OAuth authorization URL"""
    try:
        service = get_figma_service()
        auth_url = service.get_authorization_url(state)
        return {
            "ok": True,
            "authorization_url": auth_url,
            "message": "Redirect user to this URL to authorize Figma access"
        }
    except Exception as e:
        logger.error(f"Error generating Figma OAuth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/oauth/callback")
async def figma_oauth_callback(code: str = Query(...), state: Optional[str] = None):
    """Handle Figma OAuth callback"""
    try:
        service = get_figma_service()
        token_data = await service.exchange_token(code)
        
        return {
            "ok": True,
            "message": "Successfully connected to Figma",
            "user_id": token_data.get("user_id"),
            "expires_in": token_data.get("expires_in")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in Figma OAuth callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/oauth/status")
async def get_figma_oauth_status():
    """Get current Figma OAuth connection status"""
    try:
        service = get_figma_service()
        status = service.get_connection_status()
        return {
            "ok": True,
            **status
        }
    except Exception as e:
        logger.error(f"Error getting Figma OAuth status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# API Endpoints
@router.get("/status")
async def figma_status(user_id: str = "test_user"):
    """Get Figma integration status"""
    service = get_figma_service()
    connection_status = service.get_connection_status()
    
    return {
        "ok": True,
        "service": "figma",
        "user_id": user_id,
        "status": "connected" if connection_status["connected"] else "disconnected",
        "message": "Figma integration is available" if connection_status["connected"] else "Please authenticate with Figma",
        **connection_status
    }

@router.get("/user")
async def get_figma_user():
    """Get authenticated Figma user information"""
    try:
        service = get_figma_service()
        await service.ensure_valid_token()
        user_info = await service.get_user_info()
        return {
            "ok": True,
            **user_info
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Figma user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/files")
async def list_figma_files(team_id: Optional[str] = Query(None), project_id: Optional[str] = Query(None)):
    """
    List Figma files (requires authentication)

    Note: Figma API requires either team_id or project_id to list files.
    Without these parameters, we cannot retrieve files from the API.

    To get your team_id:
    1. Go to Figma and open your team
    2. The team_id is in the URL: https://www.figma.com/files/team/<team_id>/...

    Args:
        team_id: Optional Figma team ID to list files from all projects
        project_id: Optional Figma project ID to list files from a specific project

    Returns:
        List of Figma files with metadata
    """
    try:
        service = get_figma_service()
        await service.ensure_valid_token()

        # If team_id is provided, get all projects and their files
        if team_id:
            projects = await service.get_team_projects(team_id)
            all_files = []

            for project in projects:
                project_files = await service.get_project_files(project['id'])
                for file in project_files:
                    file['project_id'] = project['id']
                    file['project_name'] = project.get('name', 'Unknown')
                all_files.extend(project_files)

            return {
                "ok": True,
                "files": all_files,
                "count": len(all_files),
                "source": "team_projects"
            }

        # If project_id is provided, get files from that project
        elif project_id:
            files = await service.get_project_files(project_id)
            return {
                "ok": True,
                "files": files,
                "count": len(files),
                "source": "project"
            }

        # No context provided - return helpful error
        else:
            return {
                "ok": False,
                "error": "missing_context",
                "message": "Listing files requires either team_id or project_id parameter",
                "usage": {
                    "endpoint": "/api/figma/files?team_id=<YOUR_TEAM_ID>",
                    "alternative": "/api/figma/files?project_id=<YOUR_PROJECT_ID>",
                    "note": "Find your team_id in Figma URL: https://www.figma.com/files/team/<team_id>/..."
                },
                "files": []
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing Figma files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search")
async def figma_search(request: FigmaSearchRequest):
    """Search Figma content (requires authentication)"""
    try:
        service = get_figma_service()
        await service.ensure_valid_token()
        
        logger.info(f"Searching Figma for: {request.query}")

        # Mock results - in production, search using Figma API (if available) or index
        mock_results = [
            {
                "id": "item_001",
                "title": f"Figma Design - {request.query}",
                "type": "file",
                "snippet": f"Design file matching: {request.query}",
            }
        ]

        return FigmaSearchResponse(
            ok=True,
            query=request.query,
            results=mock_results,
            timestamp=datetime.now().isoformat(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching Figma: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/items")
async def list_figma_items(user_id: str = "test_user"):
    """List Figma items (requires authentication)"""
    try:
        service = get_figma_service()
        await service.ensure_valid_token()
        
        return {
            "ok": True,
            "items": [
                {
                    "id": f"item_{i}",
                    "title": f"Figma Item {i}",
                    "status": "active",
                }
                for i in range(1, 6)
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing Figma items: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def figma_health():
    """Health check for Figma integration"""
    service = get_figma_service()
    return await service.health_check()


