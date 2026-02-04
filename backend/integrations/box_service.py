"""
Box Service Integration for ATOM Platform

This module provides Box operations for the main backend API.
It handles authentication, file operations, and integration with the ATOM platform.
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Box API scopes
BOX_SCOPES = [
    "root_readonly",
    "manage_app_users",
    "manage_webhook",
]

# Initialize router
box_router = APIRouter(prefix="/box", tags=["Box"])


# Pydantic models
class BoxFile(BaseModel):
    id: str
    name: str
    type: str
    size: Optional[int] = None
    created_at: Optional[str] = None
    modified_at: Optional[str] = None
    shared_link: Optional[str] = None
    path_collection: Optional[Dict[str, Any]] = None


class BoxFolder(BaseModel):
    id: str
    name: str
    type: str
    created_at: Optional[str] = None
    modified_at: Optional[str] = None
    item_collection: Optional[Dict[str, Any]] = None


class BoxFileList(BaseModel):
    entries: List[BoxFile]
    total_count: int
    offset: int
    limit: int
    next_marker: Optional[str] = None


class BoxSearchRequest(BaseModel):
    query: str
    limit: int = 100
    offset: int = 0


class BoxAuthResponse(BaseModel):
    auth_url: str
    state: str


class BoxService:
    """Box service for handling file operations and authentication."""

    def __init__(self):
        self.service_name = "box"
        self.required_scopes = BOX_SCOPES
        self.base_url = "https://api.box.com/2.0"

    async def authenticate(self, user_id: str) -> Dict[str, Any]:
        """Initialize Box authentication flow."""
        try:
            # In a real implementation, this would generate OAuth URL
            # For now, return mock auth URL
            auth_url = f"https://account.box.com/api/oauth2/authorize?response_type=code&client_id=client_id&scope={'+'.join(self.required_scopes)}"
            return {
                "status": "success",
                "auth_url": auth_url,
                "state": f"box_{user_id}",
            }
        except Exception as e:
            logger.error(f"Box authentication failed: {e}")
            return {"status": "error", "message": f"Authentication failed: {str(e)}"}

    async def list_files(
        self,
        access_token: str,
        folder_id: str = "0",
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List files from Box."""
        try:
            if not access_token or access_token == "mock":
                logger.info("Using mock data - no access token provided")
                mock_files = [
                    {
                        "id": "mock_file_123",
                        "name": "Project Proposal.docx (MOCK)",
                        "type": "file",
                        "size": 1024000,
                        "created_at": "2024-01-15T10:00:00Z",
                        "modified_at": "2024-01-20T14:30:00Z",
                    }
                ]
                return {"status": "success", "data": {"entries": mock_files, "total_count": 1, "offset": offset, "limit": limit, "next_marker": None}, "mode": "mock"}

            # Real Box API call
            import httpx
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {access_token}"}
                url = f"{self.base_url}/folders/{folder_id}/items"
                params = {"limit": limit, "offset": offset, "fields": "id,name,type,size,created_at,modified_at,shared_link,path_collection"}

                response = await client.get(url, headers=headers, params=params, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                return {
                    "status": "success",
                    "data": {
                        "entries": data.get("entries", []),
                        "total_count": data.get("total_count", 0),
                        "offset": data.get("offset", 0),
                        "limit": data.get("limit", limit),
                        "next_marker": data.get("next_marker")
                    },
                    "mode": "real"
                }
        except Exception as e:
            logger.error(f"Box list files failed: {e}")
            return {"status": "error", "message": f"Failed to list files: {str(e)}"}

    async def search_files(
        self,
        access_token: str,
        query: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Search files in Box."""
        try:
            if not access_token or access_token == "mock":
                mock_files = [
                    {
                        "id": "mock_search_file",
                        "name": f"Search Result: {query}.docx (MOCK)",
                        "type": "file",
                        "size": 2048000,
                        "created_at": "2024-01-10T08:00:00Z",
                        "modified_at": "2024-01-12T11:20:00Z",
                    }
                ]
                return {"status": "success", "data": {"entries": mock_files, "total_count": 1, "offset": offset, "limit": limit, "next_marker": None}, "mode": "mock"}

            # Real Box API search
            import httpx
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {access_token}"}
                url = f"{self.base_url}/search"
                params = {"query": query, "limit": limit, "offset": offset}

                response = await client.get(url, headers=headers, params=params, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                return {
                    "status": "success",
                    "data": {
                        "entries": data.get("entries", []),
                        "total_count": data.get("total_count", 0),
                        "offset": data.get("offset", 0),
                        "limit": data.get("limit", limit),
                        "next_marker": data.get("next_marker")
                    },
                    "mode": "real"
                }
        except Exception as e:
            logger.error(f"Box search failed: {e}")
            return {"status": "error", "message": f"Search failed: {str(e)}"}

    async def get_file_metadata(
        self, access_token: str, file_id: str
    ) -> Dict[str, Any]:
        """Get metadata for a specific file."""
        try:
            # Mock implementation
            mock_metadata = {
                "id": file_id,
                "name": f"File {file_id}",
                "type": "file",
                "size": 1024000,
                "created_at": "2024-01-15T10:00:00Z",
                "modified_at": "2024-01-20T14:30:00Z",
                "shared_link": {
                    "url": f"https://app.box.com/s/{file_id}",
                    "download_url": f"https://app.box.com/shared/static/{file_id}.docx",
                },
                "path_collection": {
                    "total_count": 2,
                    "entries": [
                        {"id": "0", "name": "All Files"},
                        {"id": "folder_123", "name": "Project Documents"},
                    ],
                },
                "created_by": {
                    "name": "John Doe",
                    "login": "john.doe@example.com",
                },
                "modified_by": {
                    "name": "Jane Smith",
                    "login": "jane.smith@example.com",
                },
            }

            return {"status": "success", "data": mock_metadata}
        except Exception as e:
            logger.error(f"Box get file metadata failed: {e}")
            return {
                "status": "error",
                "message": f"Failed to get file metadata: {str(e)}",
            }

    async def download_file(self, access_token: str, file_id: str) -> Dict[str, Any]:
        """Get download URL for a file."""
        try:
            # Mock implementation
            download_url = f"{self.base_url}/files/{file_id}/content"
            return {
                "status": "success",
                "data": {
                    "downloadUrl": download_url,
                    "expires_at": "2024-01-21T12:00:00Z",
                },
            }
        except Exception as e:
            logger.error(f"Box download file failed: {e}")
            return {"status": "error", "message": f"Download failed: {str(e)}"}

    async def create_folder(
        self, access_token: str, parent_folder_id: str, folder_name: str
    ) -> Dict[str, Any]:
        """Create a new folder in Box."""
        try:
            # Mock implementation
            new_folder = {
                "id": f"folder_{len(folder_name)}",
                "name": folder_name,
                "type": "folder",
                "created_at": "2024-01-21T10:00:00Z",
                "modified_at": "2024-01-21T10:00:00Z",
                "parent": {"id": parent_folder_id},
            }

            return {"status": "success", "data": new_folder}
        except Exception as e:
            logger.error(f"Box create folder failed: {e}")
            return {"status": "error", "message": f"Failed to create folder: {str(e)}"}


# Service instance
box_service = BoxService()


# API Routes
@box_router.get("/auth")
async def box_auth(user_id: str):
    """Initiate Box OAuth flow."""
    result = await box_service.authenticate(user_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return BoxAuthResponse(**result)


@box_router.get("/files")
async def list_box_files(
    access_token: str,
    folder_id: str = "0",
    limit: int = 100,
    offset: int = 0,
):
    """List files from Box."""
    result = await box_service.list_files(access_token, folder_id, limit, offset)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return BoxFileList(**result["data"])


@box_router.post("/search")
async def search_box_files(request: BoxSearchRequest, access_token: str):
    """Search files in Box."""
    result = await box_service.search_files(
        access_token, request.query, request.limit, request.offset
    )
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return BoxFileList(**result["data"])


@box_router.get("/files/{file_id}")
async def get_box_file_metadata(file_id: str, access_token: str):
    """Get metadata for a specific Box file."""
    result = await box_service.get_file_metadata(access_token, file_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result["data"]


@box_router.get("/files/{file_id}/download")
async def download_box_file(file_id: str, access_token: str):
    """Get download URL for a Box file."""
    result = await box_service.download_file(access_token, file_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result["data"]


@box_router.post("/folders")
async def create_box_folder(access_token: str, parent_folder_id: str, folder_name: str):
    """Create a new folder in Box."""
    result = await box_service.create_folder(
        access_token, parent_folder_id, folder_name
    )
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result["data"]


@box_router.get("/health")
async def box_health():
    """Health check for Box service."""
    return {
        "status": "healthy",
        "service": "box",
        "timestamp": "2024-01-21T10:00:00Z",
    }
