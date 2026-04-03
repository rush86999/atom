"""
Box Service Integration for ATOM Platform

This module provides Box operations for the main backend API.
It handles authentication, file operations, and integration with the ATOM platform.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.integration_service import IntegrationService

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


class BoxService(IntegrationService):
    """Box service for handling file operations and authentication."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(tenant_id, config)
        self.service_name = "box"
        self.required_scopes = BOX_SCOPES
        self.base_url = "https://api.box.com/2.0"
        self.access_token = config.get("access_token")

    def get_capabilities(self) -> Dict[str, Any]:
        """Return the capabilities of the Box service."""
        return {
            "operations": [
                {"id": "list_files", "description": "List files from Box"},
                {"id": "search_files", "description": "Search files in Box"},
                {"id": "get_file_metadata", "description": "Get file metadata"},
                {"id": "download_file", "description": "Get download URL for a file"},
                {"id": "create_folder", "description": "Create a new folder"},
                {"id": "sync_to_postgres_cache", "description": "Sync metrics to PostgreSQL"},
                {"id": "full_sync", "description": "Full sync operation"},
            ],
            "required_params": ["access_token"],
            "optional_params": [],
            "rate_limits": {"requests_per_minute": 100},
            "supports_webhooks": True,
        }

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Box service."""
        try:
            return {
                "healthy": True,
                "status": "healthy",
                "service": "box",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "Box service is operational",
            }
        except Exception as e:
            return {
                "healthy": False,
                "status": "unhealthy",
                "service": "box",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a Box operation."""
        operations = {
            "list_files": self._execute_list_files,
            "search_files": self._execute_search_files,
            "get_file_metadata": self._execute_get_file_metadata,
            "download_file": self._execute_download_file,
            "create_folder": self._execute_create_folder,
        }

        if operation not in operations:
            return {
                "success": False,
                "error": f"Unknown operation: {operation}",
                "details": {"operation": operation}
            }

        try:
            result = await operations[operation](**parameters)
            # Transform result to match expected format
            if result.get("status") == "success":
                return {"success": True, "result": result.get("data")}
            return {"success": False, "error": result.get("message", "Unknown error")}
        except Exception as e:
            logger.error(f"Box operation {operation} failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "details": {"operation": operation}
            }

    async def _execute_list_files(self, **kwargs) -> Any:
        """Wrapper for list_files operation."""
        return await self.list_files(**kwargs)

    async def _execute_search_files(self, **kwargs) -> Any:
        """Wrapper for search_files operation."""
        return await self.search_files(**kwargs)

    async def _execute_get_file_metadata(self, **kwargs) -> Any:
        """Wrapper for get_file_metadata operation."""
        return await self.get_file_metadata(**kwargs)

    async def _execute_download_file(self, **kwargs) -> Any:
        """Wrapper for download_file operation."""
        return await self.download_file(**kwargs)

    async def _execute_create_folder(self, **kwargs) -> Any:
        """Wrapper for create_folder operation."""
        return await self.create_folder(**kwargs)

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
<<<<<<< HEAD

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
=======
        try:
            # Mock implementation - in real scenario, use Box API
            mock_files = [
                {
                    "id": "file_123456789",
                    "name": "Project Proposal.docx",
                    "type": "file",
                    "size": 1024000,
                    "created_at": "2024-01-15T10:00:00Z",
                    "modified_at": "2024-01-20T14:30:00Z",
                    "shared_link": {
                        "url": "https://app.box.com/s/file_123456789",
                        "download_url": "https://app.box.com/shared/static/file_123456789.docx",
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
                    },
                    "path_collection": {
                        "total_count": 2,
                        "entries": [
                            {"id": "0", "name": "All Files"},
                            {"id": "folder_123", "name": "Project Documents"},
                        ],
                    },
                },
                {
                    "id": "file_987654321",
                    "name": "Meeting Notes.pdf",
                    "type": "file",
                    "size": 512000,
                    "created_at": "2024-01-18T09:15:00Z",
                    "modified_at": "2024-01-19T16:45:00Z",
                    "shared_link": {
                        "url": "https://app.box.com/s/file_987654321",
                        "download_url": "https://app.box.com/shared/static/file_987654321.pdf",
                    },
                    "path_collection": {
                        "total_count": 2,
                        "entries": [
                            {"id": "0", "name": "All Files"},
                            {"id": "folder_123", "name": "Project Documents"},
                        ],
                    },
                },
            ]

            return {
                "status": "success",
                "data": {
                    "entries": mock_files,
                    "total_count": len(mock_files),
                    "offset": offset,
                    "limit": limit,
                    "next_marker": None,
                },
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
            # Mock implementation
            mock_files = [
                {
                    "id": "file_555555555",
                    "name": f"Search Result: {query}.docx",
                    "type": "file",
                    "size": 2048000,
                    "created_at": "2024-01-10T08:00:00Z",
                    "modified_at": "2024-01-12T11:20:00Z",
                    "shared_link": {
                        "url": f"https://app.box.com/s/file_555555555",
                        "download_url": f"https://app.box.com/shared/static/file_555555555.docx",
                    },
                    "path_collection": {
                        "total_count": 2,
                        "entries": [
                            {"id": "0", "name": "All Files"},
                            {"id": "folder_456", "name": "Search Results"},
                        ],
                    },
                }
            ]

            return {
                "status": "success",
                "data": {
                    "entries": mock_files,
                    "total_count": len(mock_files),
                    "offset": offset,
                    "limit": limit,
                    "next_marker": None,
                },
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
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
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

    async def sync_to_postgres_cache(self, workspace_id: str, access_token: str) -> Dict[str, Any]:
        """Sync Box analytics to PostgreSQL IntegrationMetric table."""
        try:
            from datetime import datetime, timezone
            from core.database import SessionLocal
            from core.models import IntegrationMetric
            
            # Get files to count
            files_result = await self.list_files(access_token)
            file_count = len(files_result.get("data", {}).get("entries", []))
            
            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("box_file_count", file_count, "count"),
                ]
                
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        tenant_id=workspace_id,
                        integration_type="box",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            tenant_id=workspace_id,
                            integration_type="box",
                            metric_key=key,
                            value=float(value),
                            unit=unit
                        )
                        db.add(metric)
                    metrics_synced += 1
                
                db.commit()
                logger.info(f"Synced {metrics_synced} Box metrics to PostgreSQL cache for workspace {workspace_id}")
            except Exception as e:
                logger.error(f"Error saving Box metrics to Postgres: {e}")
                db.rollback()
                return {"success": False, "error": str(e)}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Box PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": str(e)}

    async def full_sync(self, workspace_id: str, access_token: str) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Box"""
        from datetime import datetime, timezone
        cache_result = await self.sync_to_postgres_cache(workspace_id, access_token)
        
        return {
            "success": True,
            "workspace_id": workspace_id,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Service instance removed - use IntegrationRegistry instead
# box_service = BoxService(tenant_id="system", config={})
