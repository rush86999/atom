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
    team_id: Optional[str] = Field(None, description="Explicit team ID")
    workspace_id: Optional[str] = Field(None, description="Explicit workspace ID")
    recursive: bool = Field(False, description="Recursively list subfolders")

class IngestRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    file_id: str = Field(..., description="Zoho WorkDrive file ID")

class IngestFolderRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    folder_id: str = Field(..., description="Root folder ID to ingest")
    team_id: Optional[str] = Field(None, description="Explicit team ID")
    workspace_id: Optional[str] = Field(None, description="Explicit workspace ID")
    recursive: bool = Field(True, description="Recursively ingest subfolders")
    max_files: int = Field(500, description="Maximum files to ingest")

class SyncTeamRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    team_id: Optional[str] = Field(None, description="Explicit team ID")
    workspace_id: Optional[str] = Field(None, description="Explicit workspace ID")
    folder_id: Optional[str] = Field(None, description="Specific folder ID to sync")
    recursive: bool = Field(True, description="Recursively sync subfolders")

class FolderTreeRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    workspace_id: Optional[str] = Field(None, description="Explicit workspace ID")
    team_id: Optional[str] = Field(None, description="Explicit team ID")
    max_depth: int = Field(10, description="Maximum tree depth")

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

@router.get("/team-folders", summary="List team folders across all teams (or specific team)")
async def get_team_folders(request: Request, user_id: Optional[str] = Query(None), team_id: Optional[str] = Query(None)):
    """List all team folders across teams (or specific team).

    Returns: {id, name, team_id, team_name, workspace_id, type}
    """
    try:
        uid = await resolve_user_id(request, user_id)
        folders = await zoho_service.get_team_folders(uid, team_id)
        return router.success_response(data=folders or [])
    except Exception as e:
        logger.error(f"Error fetching Zoho team folders: {e}")
        return router.success_response(data=[])

@router.post("/files/list", summary="List files in a folder, workspace, or team folder")
async def list_files(request_body: FileListRequest, request: Request):
    """List files and folders in a specific parent ID, workspace, or team.

    Supports:
    - parent_id="root" (default): user's private workspace
    - team_id: explicit team's root workspace
    - workspace_id: explicit workspace (personal or team)
    - recursive: recursively list all subfolders
    """
    try:
        uid = await resolve_user_id(request, request_body.user_id)
        files = await zoho_service.list_files(
            uid, request_body.parent_id,
            request_body.team_id, request_body.workspace_id,
            request_body.recursive
        )
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

@router.post("/ingest-folder", summary="Ingest entire folder tree recursively")
async def ingest_folder(request_body: IngestFolderRequest, request: Request):
    """Recursively ingest all parseable files in a folder tree.

    Supports:
    - folder_id: root folder ID (or "root" for workspace root)
    - team_id / workspace_id: explicit team/workspace
    - recursive: traverse subfolders
    - max_files: safety cap
    - file extensions: .docx, .xlsx, .xls, .csv, .pdf, .txt, .md, .pptx
    """
    try:
        uid = await resolve_user_id(request, request_body.user_id)
        result = await zoho_service.ingest_folder_tree(
            uid, request_body.folder_id,
            request_body.team_id, request_body.workspace_id,
            request_body.recursive, max_files=request_body.max_files
        )
        return result
    except Exception as e:
        logger.error(f"Error ingesting Zoho folder tree: {e}")
        raise router.internal_error(message=f"Error ingesting folder: {e}", details={"error": str(e)})

@router.post("/sync-team", summary="Full sync for specific team/workspace/folder")
async def sync_team(request_body: SyncTeamRequest, request: Request):
    """Full dual-pipeline sync for specific team, workspace, or folder.

    Pipeline 1: Ingest parseable files into ATOM memory (LanceDB + GraphRAG)
    Pipeline 2: Refresh Postgres metrics cache

    Supports:
    - team_id: explicit team
    - workspace_id: explicit workspace (personal or team)
    - folder_id: specific folder to sync (with recursive traversal)
    - recursive: traverse subfolders
    """
    try:
        uid = await resolve_user_id(request, request_body.user_id)
        result = await zoho_service.full_sync(
            uid,
            workspace_id=request_body.workspace_id,
            team_id=request_body.team_id,
            folder_id=request_body.folder_id,
            recursive=request_body.recursive
        )
        return result
    except Exception as e:
        logger.error(f"Error syncing Zoho team: {e}")
        raise router.internal_error(message=f"Error syncing team: {e}", details={"error": str(e)})

@router.post("/folder-tree", summary="Get full folder tree for a workspace/team")
async def get_folder_tree(request_body: FolderTreeRequest, request: Request):
    """Get full nested folder tree structure for a workspace/team.

    Returns nested structure: {id, name, type: 'folder', children: [...], file_count}
    Use this to display the full folder hierarchy in the UI.
    """
    try:
        uid = await resolve_user_id(request, request_body.user_id)
        tree = await zoho_service.get_folder_tree(
            uid,
            workspace_id=request_body.workspace_id,
            team_id=request_body.team_id,
            max_depth=request_body.max_depth
        )
        return router.success_response(data=tree)
    except Exception as e:
        logger.error(f"Error fetching Zoho folder tree: {e}")
        return router.success_response(data={"id": "root", "name": "Root", "type": "folder", "children": [], "error": str(e)})

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
