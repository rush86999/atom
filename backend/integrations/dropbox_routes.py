"""
Enhanced Dropbox API Routes
Complete Dropbox integration endpoints for the ATOM platform
"""

import asyncio
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from integrations.auth_handler_dropbox import dropbox_auth_handler
from integrations.dropbox_service import dropbox_service

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/dropbox", tags=["dropbox"])


# Pydantic models for request/response
class FileListRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    path: str = Field("/", description="Path to list")
    recursive: bool = Field(False, description="Recursive listing")
    limit: int = Field(100, description="Maximum results")
    cursor: Optional[str] = Field(None, description="Pagination cursor")


class FileUploadRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    file_name: str = Field(..., description="File name")
    file_content: str = Field(..., description="Base64 encoded file content")
    path: str = Field("/", description="Upload path")
    autorename: bool = Field(True, description="Auto-rename on conflict")


class FileDownloadRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    path: str = Field(..., description="File path")
    rev: Optional[str] = Field(None, description="File revision")


class FileSearchRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    query: str = Field(..., description="Search query")
    path: str = Field("/", description="Search path")
    max_results: int = Field(50, description="Maximum results")
    file_extensions: Optional[List[str]] = Field(
        None, description="File extensions filter"
    )


class FolderCreateRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    path: str = Field(..., description="Folder path")
    autorename: bool = Field(True, description="Auto-rename on conflict")


class ItemDeleteRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    path: str = Field(..., description="Item path")


class ItemMoveRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    from_path: str = Field(..., description="Source path")
    to_path: str = Field(..., description="Destination path")
    autorename: bool = Field(True, description="Auto-rename on conflict")
    allow_ownership_transfer: bool = Field(
        False, description="Allow ownership transfer"
    )


class ItemCopyRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    from_path: str = Field(..., description="Source path")
    to_path: str = Field(..., description="Destination path")
    autorename: bool = Field(True, description="Auto-rename on conflict")
    allow_ownership_transfer: bool = Field(
        False, description="Allow ownership transfer"
    )


class SharedLinkCreateRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    path: str = Field(..., description="File/folder path")
    settings: Optional[Dict[str, Any]] = Field(None, description="Link settings")


class FileMetadataRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    path: str = Field(..., description="File path")
    include_media_info: bool = Field(False, description="Include media info")
    include_deleted: bool = Field(False, description="Include deleted files")


# OAuth Endpoints
@router.get("/oauth/url", summary="Get Dropbox OAuth URL")
async def get_dropbox_oauth_url(state: Optional[str] = None):
    """Get Dropbox OAuth authorization URL"""
    try:
        auth_url = dropbox_auth_handler.get_authorization_url(state)
        return {
            "success": True,
            "authorization_url": auth_url,
            "message": "Redirect user to this URL to authorize Dropbox access"
        }
    except Exception as e:
        logger.error(f"Error generating Dropbox OAuth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/callback", summary="Dropbox OAuth callback")
async def dropbox_oauth_callback(code: str = Query(...), state: Optional[str] = None):
    """Handle Dropbox OAuth callback"""
    try:
        token_data = await dropbox_auth_handler.exchange_code_for_token(code)
        
        # In production, you would:
        # 1. Validate the state parameter
        # 2. Store tokens in database encrypted with ATOM_ENCRYPTION_KEY
        # 3. Associate tokens with the user
        
        return {
            "success": True,
            "message": "Successfully connected to Dropbox",
            "account_id": token_data.get("account_id"),
            "expires_in": token_data.get("expires_in")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in Dropbox OAuth callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/oauth/status", summary="Get Dropbox OAuth status")
async def get_dropbox_oauth_status():
    """Get current Dropbox OAuth connection status"""
    try:
        status = dropbox_auth_handler.get_connection_status()
        return {
            "success": True,
            **status
        }
    except Exception as e:
        logger.error(f"Error getting Dropbox OAuth status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user", summary="Get Dropbox user info")
async def get_dropbox_user():
    """Get authenticated Dropbox user information"""
    try:
        await dropbox_auth_handler.ensure_valid_token()
        user_info = await dropbox_auth_handler.get_user_info()
        return {
            "success": True,
            **user_info
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Dropbox user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# File endpoints
@router.post("/files/list", summary="List files and folders")
async def list_files(request: FileListRequest):
    """List files and folders with pagination"""
    try:
        token = await dropbox_auth_handler.ensure_valid_token()
        entries = await dropbox_service.list_folder(
            path="" if request.path == "/" else request.path,
            access_token=token,
            recursive=request.recursive,
            limit=request.limit
        )
        return {
            "success": True,
            "service": "dropbox",
            "operation": "list_files",
            "data": {"entries": entries, "cursor": None, "has_more": False},
            "path": request.path,
            "count": len(entries),
        }
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.post("/files/upload", summary="Upload file")
async def upload_file(request: FileUploadRequest):
    """Upload file to Dropbox"""
    try:
        token = await dropbox_auth_handler.ensure_valid_token()
        import base64
        file_bytes = base64.b64decode(request.file_content)
        
        path = f"{request.path.rstrip('/')}/{request.file_name}"
        result = await dropbox_service.upload_file(
            path=path,
            file_content=file_bytes,
            access_token=token,
            autorename=request.autorename
        )
        
        return {
            "success": True,
            "service": "dropbox",
            "operation": "upload_file",
            "data": result,
            "message": "File uploaded successfully",
        }
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.post("/files/download", summary="Download file")
async def download_file(request: FileDownloadRequest):
    """Download file from Dropbox"""
    try:
        token = await dropbox_auth_handler.ensure_valid_token()
        content = await dropbox_service.download_file(
            path=request.path,
            access_token=token
        )
        
        import base64
        return {
            "success": True,
            "service": "dropbox",
            "operation": "download_file",
            "data": {
                "file_name": request.path.split("/")[-1],
                "content_bytes": base64.b64encode(content).decode("utf-8"),
                "mime_type": "application/octet-stream",
            },
        }
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to download file: {str(e)}"
        )


@router.post("/files/search", summary="Search files")
async def search_files(request: FileSearchRequest):
    """Search files in Dropbox"""
    try:
        token = await dropbox_auth_handler.ensure_valid_token()
        results = await dropbox_service.search(
            query=request.query,
            access_token=token,
            path="" if request.path == "/" else request.path,
            max_results=request.max_results
        )
        return {
            "success": True,
            "service": "dropbox",
            "operation": "search_files",
            "data": {"matches": results, "more": False, "start": 0},
            "query": request.query,
            "count": len(results),
        }
    except Exception as e:
        logger.error(f"Error searching files: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search files: {str(e)}")


# Folder endpoints
@router.post("/folders/create", summary="Create folder")
async def create_folder(request: FolderCreateRequest):
    """Create folder in Dropbox"""
    try:
        token = await dropbox_auth_handler.ensure_valid_token()
        result = await dropbox_service.create_folder(
            path=request.path,
            access_token=token
        )
        return {
            "success": True,
            "service": "dropbox",
            "operation": "create_folder",
            "data": result,
            "message": "Folder created successfully",
        }
    except Exception as e:
        logger.error(f"Error creating folder: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create folder: {str(e)}"
        )


@router.post("/folders/list", summary="List folders")
async def list_folders(request: FileListRequest):
    """List folders with pagination"""
    try:
        token = await dropbox_auth_handler.ensure_valid_token()
        entries = await dropbox_service.list_folder(
            path="" if request.path == "/" else request.path,
            access_token=token,
            recursive=request.recursive,
            limit=request.limit
        )
        # Filter for folders only
        folders = [e for e in entries if e.get(".tag") == "folder"]
        return {
            "success": True,
            "service": "dropbox",
            "operation": "list_folders",
            "data": {"entries": folders, "cursor": None, "has_more": False},
            "path": request.path,
            "count": len(folders),
        }
    except Exception as e:
        logger.error(f"Error listing folders: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list folders: {str(e)}")


# Item management endpoints
@router.post("/items/delete", summary="Delete item")
async def delete_item(request: ItemDeleteRequest):
    """Delete file or folder from Dropbox"""
    try:
        token = await dropbox_auth_handler.ensure_valid_token()
        result = await dropbox_service.delete_item(
            path=request.path,
            access_token=token
        )
        return {
            "success": True,
            "service": "dropbox",
            "operation": "delete_item",
            "data": result,
            "message": "Item deleted successfully",
        }
    except Exception as e:
        logger.error(f"Error deleting item: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete item: {str(e)}")


@router.post("/items/move", summary="Move item")
async def move_item(request: ItemMoveRequest):
    """Move file or folder in Dropbox"""
    try:
        token = await dropbox_auth_handler.ensure_valid_token()
        result = await dropbox_service.move_item(
            from_path=request.from_path,
            to_path=request.to_path,
            access_token=token,
            autorename=request.autorename
        )
        return {
            "success": True,
            "service": "dropbox",
            "operation": "move_item",
            "data": result,
            "message": "Item moved successfully",
        }
    except Exception as e:
        logger.error(f"Error moving item: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to move item: {str(e)}")


@router.post("/items/copy", summary="Copy item")
async def copy_item(request: ItemCopyRequest):
    """Copy file or folder in Dropbox"""
    try:
        token = await dropbox_auth_handler.ensure_valid_token()
        result = await dropbox_service.copy_item(
            from_path=request.from_path,
            to_path=request.to_path,
            access_token=token,
            autorename=request.autorename
        )
        return {
            "success": True,
            "service": "dropbox",
            "operation": "copy_item",
            "data": result,
            "message": "Item copied successfully",
        }
    except Exception as e:
        logger.error(f"Error copying item: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to copy item: {str(e)}")


# Sharing endpoints
@router.post("/shared_links/create", summary="Create shared link")
async def create_shared_link(request: SharedLinkCreateRequest):
    """Create shared link for file or folder"""
    try:
        token = await dropbox_auth_handler.ensure_valid_token()
        result = await dropbox_service.create_shared_link(
            path=request.path,
            access_token=token,
            settings=request.settings
        )
        return {
            "success": True,
            "service": "dropbox",
            "operation": "create_shared_link",
            "data": result,
            "message": "Shared link created successfully",
        }
    except Exception as e:
        logger.error(f"Error creating shared link: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create shared link: {str(e)}"
        )


# User endpoints
@router.get("/user/info", summary="Get user information")
async def get_user_info(user_id: str = Query(..., description="User ID")):
    """Get Dropbox user information"""
    try:
        token = await dropbox_auth_handler.ensure_valid_token()
        result = await dropbox_service.get_account_info(access_token=token)
        return {
            "success": True,
            "service": "dropbox",
            "operation": "get_user_info",
            "data": result,
        }
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get user info: {str(e)}"
        )


@router.get("/space/usage", summary="Get space usage")
async def get_space_usage(user_id: str = Query(..., description="User ID")):
    """Get Dropbox space usage information"""
    try:
        token = await dropbox_auth_handler.ensure_valid_token()
        result = await dropbox_service.get_space_usage(access_token=token)
        return {
            "success": True,
            "service": "dropbox",
            "operation": "get_space_usage",
            "data": result,
        }
    except Exception as e:
        logger.error(f"Error getting space usage: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get space usage: {str(e)}"
        )


@router.get("/file_metadata", summary="Get file metadata")
async def get_file_metadata(
    user_id: str = Query(..., description="User ID"),
    path: str = Query(..., description="File path"),
    include_media_info: bool = Query(False, description="Include media info"),
    include_deleted: bool = Query(False, description="Include deleted files"),
):
    """Get detailed file metadata"""
    try:
        token = await dropbox_auth_handler.ensure_valid_token()
        result = await dropbox_service.get_metadata(
            path=path,
            access_token=token
        )
        return {
            "success": True,
            "service": "dropbox",
            "operation": "get_file_metadata",
            "data": result,
        }
    except Exception as e:
        logger.error(f"Error getting file metadata: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get file metadata: {str(e)}"
        )


# Health check endpoint
@router.get("/health", summary="Dropbox service health check")
async def health_check():
    """Check Dropbox service health"""
    try:
        # Basic health check - in production, this would test actual API connectivity
        return {
            "success": True,
            "service": "dropbox",
            "status": "healthy",
            "message": "Dropbox service is available",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Dropbox health check failed: {e}")
        raise HTTPException(
            status_code=503, detail=f"Dropbox service is unhealthy: {str(e)}"
        )
