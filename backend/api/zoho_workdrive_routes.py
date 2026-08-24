from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from fastapi import Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from core.auth import get_current_user, get_optional_current_user, User
from core.base_routes import BaseAPIRouter
from integrations.zoho_workdrive_service import ZohoWorkDriveService

logger = logging.getLogger(__name__)

router = BaseAPIRouter(
    prefix="/api/zoho-workdrive",
    tags=["zoho-workdrive"],
)

# Initialize service
zoho_service = ZohoWorkDriveService()

# Pydantic models
class FileListRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    parent_id: str = Field("root", description="Parent folder or team ID")

class IngestRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    file_id: str = Field(..., description="Zoho WorkDrive file ID")

async def resolve_user_id(request: Request, user_id: Optional[str] = None) -> str:
    """Extract authenticated user ID or fall back to parameter/demo user."""
    try:
        user = await get_current_user(request=request)
        if user and user.id:
            return user.id
    except Exception:
        pass
    return user_id or "demo-user"

@router.get("/teams", summary="List Zoho WorkDrive teams")
async def get_teams(request: Request, user_id: Optional[str] = Query(None)):
    """Get teams for the authenticated Zoho user"""
    try:
        uid = await resolve_user_id(request, user_id)
        teams = await zoho_service.get_teams(uid)
        return router.success_response(data=teams or [])
    except Exception as e:
        logger.error(f"Error fetching Zoho teams: {e}")
        return router.success_response(data=[])

@router.post("/files/list", summary="List files in a folder")
async def list_files(request_body: FileListRequest, request: Request):
    """List files and folders in a specific parent ID"""
    try:
        uid = await resolve_user_id(request, request_body.user_id)
        files = await zoho_service.list_files(uid, request_body.parent_id)
        return router.success_response(data=files or [])
    except Exception as e:
        logger.error(f"Error listing Zoho files: {e}")
        return router.success_response(data=[])

@router.post("/ingest", summary="Ingest file to ATOM memory")
async def ingest_file(request_body: IngestRequest, request: Request):
    """Download and ingest a file into ATOM knowledge base"""
    try:
        uid = await resolve_user_id(request, request_body.user_id)
        result = await zoho_service.ingest_file_to_memory(uid, request_body.file_id)
        return result
    except Exception as e:
        logger.error(f"Error ingesting Zoho file: {e}")
        raise router.internal_error(message=f"Error ingesting Zoho file: {e}", details={"error": str(e)})

@router.post("/full-sync", summary="Full ingestion sync of the entire WorkDrive tree")
async def full_sync(
    http_request: Request,
    user_id: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """Walk every subfolder of the private workspace AND all team folders
    (paginated), attempt every file type through the parser chain, and write
    to Atom memory (LanceDB + GraphRAG) with folder-path context. Also
    refreshes the Postgres metrics cache."""
    try:
        # Proper dependency-injected user (the resolve_user_id helper calls
        # get_current_user directly, whose Depends defaults never resolve, so
        # it silently falls back to demo-user).
        uid = str(current_user.id) if current_user else (user_id or "demo-user")
        result = await zoho_service.full_sync(uid)
        return result
    except Exception as e:
        logger.error(f"Error running Zoho WorkDrive full sync: {e}")
        return {"success": False, "error": str(e)}


@router.get("/health", summary="Zoho WorkDrive health check")
async def health_check():
    """Check if Zoho WorkDrive service is configured"""
    is_configured = all([
        zoho_service.client_id,
        zoho_service.client_secret,
        zoho_service.redirect_uri
    ])
    return router.success_response(
        data={
            "status": "configured" if is_configured else "unconfigured"
        },
        message="Zoho WorkDrive integration is ready" if is_configured else "Zoho credentials missing in environment"
    )
