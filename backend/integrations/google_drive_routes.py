"""
Google Drive Routes for ATOM Platform

This module provides FastAPI routes for Google Drive integration.
It handles API endpoints for file operations, authentication, and search.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .google_drive_service import (
    GoogleDriveAuthResponse,
    GoogleDriveFile,
    GoogleDriveFileList,
    GoogleDriveSearchRequest,
    GoogleDriveService,
)

# Initialize router
google_drive_router = APIRouter(prefix="/google_drive", tags=["Google Drive"])

# Service instance
google_drive_service = GoogleDriveService()


@google_drive_router.get("/auth")
async def google_drive_auth(user_id: str):
    """Initiate Google Drive OAuth flow."""
    result = await google_drive_service.authenticate(user_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return GoogleDriveAuthResponse(**result)


@google_drive_router.get("/files")
async def list_google_drive_files(
    access_token: str,
    folder_id: Optional[str] = None,
    page_size: int = 100,
    page_token: Optional[str] = None,
):
    """List files from Google Drive."""
    result = await google_drive_service.list_files(
        access_token, folder_id, page_size, page_token
    )
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return GoogleDriveFileList(**result["data"])


@google_drive_router.post("/search")
async def search_google_drive_files(
    request: GoogleDriveSearchRequest, access_token: str
):
    """Search files in Google Drive."""
    result = await google_drive_service.search_files(
        access_token, request.query, request.pageSize, request.pageToken
    )
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return GoogleDriveFileList(**result["data"])


@google_drive_router.get("/files/{file_id}")
async def get_google_drive_file_metadata(file_id: str, access_token: str):
    """Get metadata for a specific Google Drive file."""
    result = await google_drive_service.get_file_metadata(access_token, file_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result["data"]


@google_drive_router.get("/files/{file_id}/download")
async def download_google_drive_file(file_id: str, access_token: str):
    """Get download URL for a Google Drive file."""
    result = await google_drive_service.download_file(access_token, file_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result["data"]


@google_drive_router.get("/health")
async def google_drive_health():
    """Health check for Google Drive service."""
    return {
        "status": "healthy",
        "service": "google_drive",
        "timestamp": "2024-01-21T10:00:00Z",
    }


@google_drive_router.get("/capabilities")
async def google_drive_capabilities():
    """Get Google Drive service capabilities."""
    return {
        "service": "google_drive",
        "capabilities": [
            "file_listing",
            "file_search",
            "file_metadata",
            "file_download",
            "folder_navigation",
            "oauth_authentication",
        ],
        "supported_file_types": [
            "documents",
            "spreadsheets",
            "presentations",
            "pdfs",
            "images",
            "videos",
        ],
    }
