from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from fastapi import Depends, Query
from pydantic import BaseModel, Field

from core.auth import get_current_user, User
from core.base_routes import BaseAPIRouter
from core.ingestion_feedback import record_ingestion_feedback
from integrations.zoho_workdrive_service import ZohoWorkDriveService

logger = logging.getLogger(__name__)

# Round 37 + review follow-up: every Zoho WorkDrive endpoint reads/ingests a
# user's cloud files. These were previously anonymous with a client-supplied
# user_id (cross-user file access). Identity ALWAYS comes from the token — the
# router-level dependency is the enforcement floor for every endpoint below.
router = BaseAPIRouter(
    prefix="/api/zoho-workdrive",
    tags=["zoho-workdrive"],
    dependencies=[Depends(get_current_user)],
)

# Initialize service
zoho_service = ZohoWorkDriveService()

# Pydantic models. None carry user_id: identity comes exclusively from the
# auth token (router-level get_current_user dependency) — a client-supplied
# user_id must never reappear on these surfaces.
class FileListRequest(BaseModel):
    parent_id: str = Field("root", description="Parent folder or team ID")
    team_id: Optional[str] = Field(None, description="Explicit team ID")
    workspace_id: Optional[str] = Field(None, description="Explicit workspace ID")
    recursive: bool = Field(False, description="Recursively list subfolders")

class IngestRequest(BaseModel):
    file_id: str = Field(..., description="Zoho WorkDrive file ID")

class IngestFolderRequest(BaseModel):
    folder_id: Optional[str] = Field(None, description="Root folder ID to ingest (single-folder form)")
    folder_ids: Optional[List[str]] = Field(
        None, min_length=1,
        description="Multiple folder IDs to ingest in one call (batch form; overrides folder_id)"
    )
    team_id: Optional[str] = Field(None, description="Explicit team ID")
    workspace_id: Optional[str] = Field(None, description="Explicit workspace ID")
    recursive: bool = Field(True, description="Recursively ingest subfolders")
    max_files: int = Field(500, ge=1, le=2000, description="Maximum files to ingest")

class SyncTeamRequest(BaseModel):
    team_id: Optional[str] = Field(None, description="Explicit team ID")
    workspace_id: Optional[str] = Field(None, description="Explicit workspace ID")
    folder_id: Optional[str] = Field(None, description="Specific folder ID to sync")
    recursive: bool = Field(True, description="Recursively sync subfolders")

class FolderTreeRequest(BaseModel):
    workspace_id: Optional[str] = Field(None, description="Explicit workspace ID")
    team_id: Optional[str] = Field(None, description="Explicit team ID")
    max_depth: int = Field(10, ge=1, le=25, description="Maximum tree depth")

@router.get("/teams", summary="List Zoho WorkDrive teams")
async def get_teams(current_user: User = Depends(get_current_user)):
    """Get teams for the authenticated Zoho user"""
    try:
        teams = await zoho_service.get_teams(str(current_user.id))
        return router.success_response(data=teams or [])
    except Exception as e:
        logger.error(f"Error fetching Zoho teams: {e}")
        raise router.internal_error(message="Error fetching Zoho teams", details={"error": "Internal error"})

@router.get("/team-folders", summary="List team folders across all teams (or specific team)")
async def get_team_folders(
    team_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    """List all team folders across teams (or specific team).

    Returns: {id, name, team_id, team_name, workspace_id, type}
    """
    try:
        folders = await zoho_service.get_team_folders(str(current_user.id), team_id)
        return router.success_response(data=folders or [])
    except Exception as e:
        logger.error(f"Error fetching Zoho team folders: {e}")
        raise router.internal_error(message="Error fetching Zoho team folders", details={"error": "Internal error"})

@router.post("/files/list", summary="List files in a folder, workspace, or team folder")
async def list_files(request_body: FileListRequest, current_user: User = Depends(get_current_user)):
    """List files and folders in a specific parent ID, workspace, or team.

    Supports:
    - parent_id="root" (default): user's private workspace
    - team_id: explicit team's root workspace
    - workspace_id: explicit workspace (personal or team)
    - recursive: recursively list all subfolders
    """
    try:
        files = await zoho_service.list_files(
            str(current_user.id), request_body.parent_id,
            request_body.team_id, request_body.workspace_id,
            request_body.recursive
        )
        return router.success_response(data=files or [])
    except Exception as e:
        logger.error(f"Error listing Zoho files: {e}")
        raise router.internal_error(message="Error listing Zoho files", details={"error": "Internal error"})

@router.post("/ingest", summary="Ingest file to ATOM memory")
async def ingest_file(request_body: IngestRequest, current_user: User = Depends(get_current_user)):
    """Download and ingest a file into ATOM knowledge base"""
    try:
        result = await zoho_service.ingest_file_to_memory(str(current_user.id), request_body.file_id)
        # Suite apps record under the shared "zoho" sync entry — the key the
        # ingestion-status route reads back for zoho-workdrive.
        record_ingestion_feedback(
            current_user, "zoho", 1 if result.get("success") else 0,
            bool(result.get("success")),
        )
        return result
    except Exception as e:
        logger.error(f"Error ingesting Zoho file: {e}")
        raise router.internal_error(message="Error ingesting Zoho file", details={"error": "Internal error"})

@router.post("/ingest-folder", summary="Ingest entire folder tree(s) recursively")
async def ingest_folder(request_body: IngestFolderRequest, current_user: User = Depends(get_current_user)):
    """Recursively ingest all parseable files in one or more folder trees.

    Supports:
    - folder_id: single root folder ID (or "root" for workspace root)
    - folder_ids: multiple root folder IDs ingested in one call — folders are
      isolated, so one failed tree never aborts the rest (explicit user
      selection, honored regardless of the bulk content-mode setting)
    - team_id / workspace_id: explicit team/workspace
    - recursive: traverse subfolders
    - max_files: safety cap (per folder in batch form)
    - file extensions: .docx, .xlsx, .xls, .csv, .pdf, .txt, .md, .pptx
    """
    ids = list(request_body.folder_ids) if request_body.folder_ids else (
        [request_body.folder_id] if request_body.folder_id else []
    )
    if not ids:
        raise router.validation_error(
            field="folder_id",
            message="folder_id or folder_ids is required",
        )

    try:
        if len(ids) == 1:
            result = await zoho_service.ingest_folder_tree(
                str(current_user.id), ids[0],
                request_body.team_id, request_body.workspace_id,
                request_body.recursive, max_files=request_body.max_files
            )
            record_ingestion_feedback(
                current_user, "zoho",
                int(result.get("files_ingested") or 0) if result.get("success") else 0,
                bool(result.get("success")),
            )
            return result

        results = []
        total_ingested = 0
        for fid in ids:
            try:
                res = await zoho_service.ingest_folder_tree(
                    str(current_user.id), fid,
                    request_body.team_id, request_body.workspace_id,
                    request_body.recursive, max_files=request_body.max_files
                )
            except Exception as folder_err:
                logger.error(f"Error ingesting Zoho folder tree {fid}: {folder_err}")
                res = {"success": False, "folder_id": fid, "error": "Failed to ingest folder tree"}
            if res.get("success"):
                total_ingested += res.get("files_ingested", 0) or 0
            results.append({"folder_id": fid, **res})

        record_ingestion_feedback(
            current_user, "zoho", total_ingested,
            any(r.get("success") for r in results),
        )
        return {
            "success": any(r.get("success") for r in results),
            "folders_requested": len(ids),
            "folders_succeeded": sum(1 for r in results if r.get("success")),
            "files_ingested": total_ingested,
            "results": results,
        }
    except Exception as e:
        logger.error(f"Error ingesting Zoho folder tree: {e}")
        raise router.internal_error(message="Error ingesting folder", details={"error": "Internal error"})

@router.post("/sync-team", summary="Full sync for specific team/workspace/folder")
async def sync_team(request_body: SyncTeamRequest, current_user: User = Depends(get_current_user)):
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
        result = await zoho_service.full_sync(
            str(current_user.id),
            workspace_id=request_body.workspace_id,
            team_id=request_body.team_id,
            folder_id=request_body.folder_id,
            recursive=request_body.recursive
        )
        return result
    except Exception as e:
        logger.error(f"Error syncing Zoho team: {e}")
        raise router.internal_error(message="Error syncing team", details={"error": "Internal error"})

@router.post("/folder-tree", summary="Get full folder tree for a workspace/team")
async def get_folder_tree(request_body: FolderTreeRequest, current_user: User = Depends(get_current_user)):
    """Get full nested folder tree structure for a workspace/team.

    Returns nested structure: {id, name, type: 'folder', children: [...], file_count}
    Use this to display the full folder hierarchy in the UI.
    """
    try:
        tree = await zoho_service.get_folder_tree(
            str(current_user.id),
            workspace_id=request_body.workspace_id,
            team_id=request_body.team_id,
            max_depth=request_body.max_depth
        )
        return router.success_response(data=tree)
    except Exception as e:
        logger.error(f"Error fetching Zoho folder tree: {e}")
        raise router.internal_error(message="Error fetching Zoho folder tree", details={"error": "Internal error"})

@router.post("/full-sync", summary="Full ingestion sync of the entire WorkDrive tree")
async def full_sync(current_user: User = Depends(get_current_user)):
    """Walk every subfolder of the private workspace AND all team folders
    (paginated), attempt every file type through the parser chain, and write
    to Atom memory (LanceDB + GraphRAG) with folder-path context. Also
    refreshes the Postgres metrics cache."""
    try:
        # Identity always comes from the token — never from a client-supplied
        # user_id, and never a silent demo-user fallback.
        result = await zoho_service.full_sync(str(current_user.id))
        record_ingestion_feedback(
            current_user, "zoho-workdrive",
            int((result or {}).get("files_ingested") or 0),
            bool(isinstance(result, dict) and result.get("success")),
        )
        return result
    except Exception as e:
        logger.error(f"Error running Zoho WorkDrive full sync: {e}")
        raise router.internal_error(message="Error running Zoho WorkDrive full sync", details={"error": "Internal error"})

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
