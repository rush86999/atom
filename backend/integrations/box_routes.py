"""
Box Integration Routes for ATOM Platform
Uses the real box_service.py for all operations
"""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .box_service import box_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/box", tags=["box"])


# Pydantic models
class BoxAuthRequest(BaseModel):
    code: str
    redirect_uri: str


class BoxSearchRequest(BaseModel):
    query: str
    limit: int = 100
    offset: int = 0


class BoxUploadRequest(BaseModel):
    name: str
    parent_folder_id: str = "0"
    content: Optional[str] = None


@router.get("/auth/url")
async def get_auth_url(user_id: str = "default"):
    """Get Box OAuth URL"""
    try:
        result = await box_service.authenticate(user_id)
        return {"url": result.get("auth_url", ""), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Failed to generate auth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files")
async def get_files(
    access_token: str,
    folder_id: str = Query("0", description="Folder ID"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get Box files from a folder"""
    try:
        result = await box_service.list_files(access_token, folder_id, limit, offset)
        return {"ok": True, "files": result, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/{file_id}")
async def get_file_metadata(file_id: str, access_token: str):
    """Get metadata for a specific file"""
    try:
        result = await box_service.get_file_metadata(access_token, file_id)
        return {"ok": True, "file": result, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{file_id}")
async def download_file(file_id: str, access_token: str):
    """Get download URL for a file"""
    try:
        result = await box_service.download_file(access_token, file_id)
        return {"ok": True, **result, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/folders")
async def create_folder(
    access_token: str,
    folder_name: str,
    parent_folder_id: str = "0"
):
    """Create a new folder"""
    try:
        result = await box_service.create_folder(access_token, parent_folder_id, folder_name)
        return {"ok": True, "folder": result, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_files(request: BoxSearchRequest, access_token: str):
    """Search Box content"""
    try:
        result = await box_service.search_files(
            access_token, 
            request.query, 
            request.limit, 
            request.offset
        )
        return {"ok": True, "results": result, "query": request.query, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def box_status(user_id: str = "test_user"):
    """Get Box integration status"""
    return {
        "ok": True,
        "service": "box",
        "user_id": user_id,
        "status": "connected",
        "message": "Box integration is available",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/health")
async def box_health():
    """Health check for Box integration"""
    return {
        "status": "healthy",
        "service": "box",
        "timestamp": datetime.now().isoformat(),
        "capabilities": ["files", "folders", "search", "download"]
    }
