from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from integrations.zoho_workdrive_service import ZohoWorkDriveService

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/zoho-workdrive", tags=["zoho-workdrive"])

# Initialize service
zoho_service = ZohoWorkDriveService()

# Pydantic models
class FileListRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    parent_id: str = Field("root", description="Parent folder or team ID")

class IngestRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    file_id: str = Field(..., description="Zoho WorkDrive file ID")

@router.get("/teams", summary="List Zoho WorkDrive teams")
async def get_teams(user_id: str = Query(..., description="User ID")):
    """Get teams for the authenticated Zoho user"""
    try:
        teams = await zoho_service.get_teams(user_id)
        return {
            "success": True,
            "data": teams
        }
    except Exception as e:
        logger.error(f"Error fetching Zoho teams: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/files/list", summary="List files in a folder")
async def list_files(request: FileListRequest):
    """List files and folders in a specific parent ID"""
    try:
        files = await zoho_service.list_files(request.user_id, request.parent_id)
        return {
            "success": True,
            "data": files
        }
    except Exception as e:
        logger.error(f"Error listing Zoho files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ingest", summary="Ingest file to ATOM memory")
async def ingest_file(request: IngestRequest):
    """Download and ingest a file into ATOM knowledge base"""
    try:
        result = await zoho_service.ingest_file_to_memory(request.user_id, request.file_id)
        return result
    except Exception as e:
        logger.error(f"Error ingesting Zoho file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health", summary="Zoho WorkDrive health check")
async def health_check():
    """Check if Zoho WorkDrive service is configured"""
    is_configured = all([
        zoho_service.client_id,
        zoho_service.client_secret,
        zoho_service.redirect_uri
    ])
    return {
        "success": True,
        "status": "configured" if is_configured else "unconfigured",
        "message": "Zoho WorkDrive integration is ready" if is_configured else "Zoho credentials missing in environment"
    }
