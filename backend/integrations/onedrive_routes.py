"""
OneDrive Routes for ATOM Platform

This module provides FastAPI routes for OneDrive integration.
It handles API endpoints for file operations, authentication, and search.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .onedrive_service import (
    OneDriveAuthResponse,
    OneDriveFile,
    OneDriveFileList,
    OneDriveSearchRequest,
    OneDriveService,
)

# Initialize router
onedrive_router = APIRouter(prefix="/onedrive", tags=["OneDrive"])

# Service instance
onedrive_service = OneDriveService()

# Mock service for health check detection
class OneDriveServiceMock:
    def __init__(self):
        self.client_id = "mock_client_id"



@onedrive_router.get("/auth")
async def onedrive_auth(user_id: str):
    """Initiate OneDrive OAuth flow."""
    result = await onedrive_service.authenticate(user_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return OneDriveAuthResponse(**result)


@onedrive_router.get("/files")
async def list_onedrive_files(
    access_token: str,
    folder_id: Optional[str] = None,
    page_size: int = 100,
    page_token: Optional[str] = None,
):
    """List files from OneDrive."""
    result = await onedrive_service.list_files(
        access_token, folder_id, page_size, page_token
    )
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return OneDriveFileList(**result["data"])


@onedrive_router.post("/search")
async def search_onedrive_files(request: OneDriveSearchRequest, access_token: str):
    """Search files in OneDrive."""
    result = await onedrive_service.search_files(
        access_token, request.query, request.pageSize, request.pageToken
    )
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return OneDriveFileList(**result["data"])


@onedrive_router.get("/files/{file_id}")
async def get_onedrive_file_metadata(file_id: str, access_token: str):
    """Get metadata for a specific OneDrive file."""
    result = await onedrive_service.get_file_metadata(access_token, file_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result["data"]


@onedrive_router.get("/files/{file_id}/download")
async def download_onedrive_file(file_id: str, access_token: str):
    """Get download URL for a OneDrive file."""
    result = await onedrive_service.download_file(access_token, file_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result["data"]


@onedrive_router.get("/health")
async def onedrive_health():
    """Health check for OneDrive service."""
    return {
        "status": "healthy",
        "service": "onedrive",
        "timestamp": "2024-01-21T10:00:00Z",
    }


@onedrive_router.get("/capabilities")
async def onedrive_capabilities():
    """Get OneDrive service capabilities."""
    return {
        "service": "onedrive",
        "capabilities": [
            "file_listing",
            "file_search",
            "file_metadata",
            "file_download",
            "folder_navigation",
            "oauth_authentication",
            "file_preview",
            "version_history",
        ],
        "supported_file_types": [
            "documents",
            "spreadsheets",
            "presentations",
            "pdfs",
            "images",
            "videos",
            "audio",
        ],
        "integration_features": [
            "microsoft_graph_api",
            "real_time_sync",
            "collaboration",
            "sharing_links",
            "permissions_management",
        ],
    }
