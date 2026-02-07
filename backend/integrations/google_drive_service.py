"""
Google Drive Service Integration for ATOM Platform

This module provides Google Drive operations for the main backend API.
It handles authentication, file operations, and integration with the ATOM platform.
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Google API scopes for Drive
GOOGLE_DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
]

# Initialize router
google_drive_router = APIRouter(prefix="/google_drive", tags=["Google Drive"])


# Pydantic models
class GoogleDriveFile(BaseModel):
    id: str
    name: str
    mimeType: str
    webViewLink: Optional[str] = None
    createdTime: Optional[str] = None
    modifiedTime: Optional[str] = None
    size: Optional[int] = None


class GoogleDriveFileList(BaseModel):
    files: List[GoogleDriveFile]
    nextPageToken: Optional[str] = None


class GoogleDriveSearchRequest(BaseModel):
    query: str
    pageSize: int = 100
    pageToken: Optional[str] = None


class GoogleDriveAuthResponse(BaseModel):
    auth_url: str
    state: str


class GoogleDriveService:
    """Google Drive service for handling file operations and authentication."""

    def __init__(self):
        self.service_name = "google_drive"
        self.required_scopes = GOOGLE_DRIVE_SCOPES

    async def authenticate(self, user_id: str) -> Dict[str, Any]:
        """Initialize Google Drive authentication flow."""
        try:
            # In a real implementation, this would generate OAuth URL
            # For now, return mock auth URL
            auth_url = f"https://accounts.google.com/o/oauth2/auth?scope={'+'.join(self.required_scopes)}"
            return {
                "status": "success",
                "auth_url": auth_url,
                "state": f"google_drive_{user_id}",
            }
        except Exception as e:
            logger.error(f"Google Drive authentication failed: {e}")
            return {"status": "error", "message": f"Authentication failed: {str(e)}"}

    async def list_files(
        self,
        access_token: str,
        folder_id: Optional[str] = None,
        page_size: int = 100,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List files from Google Drive."""
        try:
            # Validate access token
            if not access_token or access_token == "mock" or access_token == "fake_token":
                logger.error("Invalid or mock access token provided")
                return {
                    "status": "error",
                    "code": 401,
                    "message": "Invalid Google OAuth token. Please authenticate with Google Drive."
                }

            # Real Google Drive API call
            import httpx
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {access_token}"}
                params = {
                    "pageSize": page_size,
                    "fields": "nextPageToken,files(id,name,mimeType,webViewLink,createdTime,modifiedTime,size)"
                }
                if folder_id:
                    params["q"] = f"'{folder_id}' in parents"
                if page_token:
                    params["pageToken"] = page_token

                response = await client.get(
                    "https://www.googleapis.com/drive/v3/files",
                    headers=headers,
                    params=params,
                    timeout=30.0
                )

                if response.status_code == 401:
                    logger.error("Google Drive authentication failed (401)")
                    return {
                        "status": "error",
                        "code": 401,
                        "message": "Authentication failed. Please re-authenticate with Google Drive."
                    }

                response.raise_for_status()
                data = response.json()
                return {
                    "status": "success",
                    "data": {"files": data.get("files", []), "nextPageToken": data.get("nextPageToken")}
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"Google Drive API error: {e.response.status_code} - {e.response.text}")
            return {
                "status": "error",
                "code": e.response.status_code,
                "message": f"Google Drive API error: {e.response.text}"
            }
        except Exception as e:
            logger.error(f"Google Drive list files failed: {e}")
            return {"status": "error", "message": f"Failed to list files: {str(e)}"}


    async def search_files(
        self,
        access_token: str,
        query: str,
        page_size: int = 100,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search files in Google Drive."""
        try:
            # Validate access token
            if not access_token or access_token == "mock" or access_token == "fake_token":
                logger.error("Invalid or mock access token provided for search")
                return {
                    "status": "error",
                    "code": 401,
                    "message": "Invalid Google OAuth token. Please authenticate with Google Drive."
                }

            # Real Google Drive API search
            import httpx
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {access_token}"}
                params = {
                    "pageSize": page_size,
                    "q": f"name contains '{query}'",
                    "fields": "nextPageToken,files(id,name,mimeType,webViewLink,createdTime,modifiedTime,size)"
                }
                if page_token:
                    params["pageToken"] = page_token

                response = await client.get(
                    "https://www.googleapis.com/drive/v3/files",
                    headers=headers,
                    params=params,
                    timeout=30.0
                )

                if response.status_code == 401:
                    logger.error("Google Drive authentication failed (401) for search")
                    return {
                        "status": "error",
                        "code": 401,
                        "message": "Authentication failed. Please re-authenticate with Google Drive."
                    }

                response.raise_for_status()
                data = response.json()
                return {
                    "status": "success",
                    "data": {"files": data.get("files", []), "nextPageToken": data.get("nextPageToken")}
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"Google Drive search API error: {e.response.status_code} - {e.response.text}")
            return {
                "status": "error",
                "code": e.response.status_code,
                "message": f"Google Drive API error: {e.response.text}"
            }
        except Exception as e:
            logger.error(f"Google Drive search failed: {e}")
            return {"status": "error", "message": f"Search failed: {str(e)}"}

    async def get_file_metadata(
        self, access_token: str, file_id: str
    ) -> Dict[str, Any]:
        """Get metadata for a specific file."""
        try:
            if not access_token or access_token == "mock":
                # Fallback to mock data
                mock_metadata = {
                    "id": file_id,
                    "name": f"File {file_id} (MOCK)",
                    "mimeType": "application/vnd.google-apps.document",
                    "webViewLink": f"https://drive.google.com/file/d/{file_id}/view",
                    "createdTime": "2024-01-15T10:00:00Z",
                    "modifiedTime": "2024-01-20T14:30:00Z",
                    "size": 1024000,
                    "owners": [{"displayName": "Mock User", "emailAddress": "mock@example.com"}],
                }
                return {"status": "success", "data": mock_metadata, "mode": "mock"}

            # Real Google Drive API call
            import httpx
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {access_token}"}
                params = {
                    "fields": "id,name,mimeType,webViewLink,createdTime,modifiedTime,size,owners"
                }
                response = await client.get(
                    f"https://www.googleapis.com/drive/v3/files/{file_id}",
                    headers=headers,
                    params=params,
                    timeout=30.0
                )
                response.raise_for_status()
                return {"status": "success", "data": response.json(), "mode": "real"}
        except Exception as e:
            logger.error(f"Google Drive get file metadata failed: {e}")
            return {"status": "error", "message": f"Failed to get file metadata: {str(e)}"}


# Service instance
google_drive_service = GoogleDriveService()


# API Routes
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


@google_drive_router.get("/health")
async def google_drive_health():
    """Health check for Google Drive service."""
    return {
        "status": "healthy",
        "service": "google_drive",
        "timestamp": "2024-01-21T10:00:00Z",
        "timestamp": "2024-01-21T10:00:00Z",
    }
