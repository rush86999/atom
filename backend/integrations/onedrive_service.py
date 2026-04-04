"""
OneDrive Service Integration for ATOM Platform

This module provides OneDrive operations for the main backend API.
It handles authentication, file operations, and integration with the ATOM platform.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)

# Microsoft Graph API scopes for OneDrive
ONEDRIVE_SCOPES = [
    "Files.Read",
    "Files.Read.All",
    "Files.ReadWrite",
    "Sites.Read.All",
]

# Initialize router
onedrive_router = APIRouter(prefix="/onedrive", tags=["OneDrive"])


# Pydantic models
class OneDriveFile(BaseModel):
    id: str
    name: str
    webUrl: Optional[str] = None
    createdDateTime: Optional[str] = None
    lastModifiedDateTime: Optional[str] = None
    size: Optional[int] = None
    file: Optional[Dict[str, Any]] = None
    folder: Optional[Dict[str, Any]] = None


class OneDriveFileList(BaseModel):
    value: List[OneDriveFile]
    nextLink: Optional[str] = None


class OneDriveSearchRequest(BaseModel):
    query: str
    pageSize: int = 100
    pageToken: Optional[str] = None


class OneDriveAuthResponse(BaseModel):
    auth_url: str
    state: str


class OneDriveService(IntegrationService):
    """OneDrive service for handling file operations and authentication."""

    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        super().__init__(tenant_id=tenant_id, config=config)
        self.service_name = "onedrive"
        self.required_scopes = ONEDRIVE_SCOPES
        self.base_url = "https://graph.microsoft.com/v1.0/me/drive"
        self.access_token = config.get("access_token")

    def get_capabilities(self) -> Dict[str, Any]:
        """Return the capabilities of the OneDrive service."""
        return {
            "operations": [
                {"id": "list_files", "description": "List files from OneDrive"},
                {"id": "search_files", "description": "Search files in OneDrive"},
                {"id": "get_file_metadata", "description": "Get file metadata"},
                {"id": "download_file", "description": "Get download URL for a file"},
                {"id": "sync_to_postgres_cache", "description": "Sync metrics to PostgreSQL"},
                {"id": "full_sync", "description": "Full sync operation"},
            ],
            "required_params": ["access_token"],
            "optional_params": [],
            "rate_limits": {"requests_per_minute": 100},
            "supports_webhooks": True,
        }

    async def health_check(self) -> Dict[str, Any]:
        """Health check for OneDrive service."""
        try:
            return {
                "healthy": True,
                "status": "healthy",
                "service": "onedrive",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "OneDrive service is operational",
            }
        except Exception as e:
            return {
                "healthy": False,
                "status": "unhealthy",
                "service": "onedrive",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a OneDrive operation."""
        operations = {
            "list_files": self._execute_list_files,
            "search_files": self._execute_search_files,
            "get_file_metadata": self._execute_get_file_metadata,
            "download_file": self._execute_download_file,
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
            logger.error(f"OneDrive operation {operation} failed: {e}")
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

    async def authenticate(self, user_id: str) -> Dict[str, Any]:
        """Initialize OneDrive authentication flow."""
        try:
            # In a real implementation, this would generate OAuth URL
            # For now, return mock auth URL
            auth_url = f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?scope={'+'.join(self.required_scopes)}"
            return {
                "status": "success",
                "auth_url": auth_url,
                "state": f"onedrive_{user_id}",
            }
        except Exception as e:
            logger.error(f"OneDrive authentication failed: {e}")
            return {"status": "error", "message": f"Authentication failed: {str(e)}"}

    async def list_files(
        self,
        access_token: str,
        folder_id: Optional[str] = None,
        page_size: int = 100,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List files from OneDrive."""
        try:
            # Mock implementation - in real scenario, use Microsoft Graph API
            mock_files = [
                {
                    "id": "file1",
                    "name": "Project Document.docx",
                    "webUrl": "https://onedrive.live.com/redir?resid=file1",
                    "createdDateTime": "2024-01-15T10:00:00Z",
                    "lastModifiedDateTime": "2024-01-20T14:30:00Z",
                    "size": 1024000,
                    "file": {
                        "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    },
                },
                {
                    "id": "file2",
                    "name": "Meeting Notes.pdf",
                    "webUrl": "https://onedrive.live.com/redir?resid=file2",
                    "createdDateTime": "2024-01-18T09:15:00Z",
                    "lastModifiedDateTime": "2024-01-19T16:45:00Z",
                    "size": 512000,
                    "file": {"mimeType": "application/pdf"},
                },
                {
                    "id": "folder1",
                    "name": "Project Files",
                    "webUrl": "https://onedrive.live.com/redir?resid=folder1",
                    "createdDateTime": "2024-01-10T08:00:00Z",
                    "lastModifiedDateTime": "2024-01-15T12:00:00Z",
                    "folder": {"childCount": 5},
                },
            ]

            return {
                "status": "success",
                "data": {"value": mock_files, "nextLink": None},
            }
        except Exception as e:
            logger.error(f"OneDrive list files failed: {e}")
            return {"status": "error", "message": f"Failed to list files: {str(e)}"}

    async def search_files(
        self,
        access_token: str,
        query: str,
        page_size: int = 100,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search files in OneDrive."""
        try:
            # Mock implementation
            mock_files = [
                {
                    "id": "file3",
                    "name": f"Search Result for {query}.docx",
                    "webUrl": f"https://onedrive.live.com/redir?resid=file3",
                    "createdDateTime": "2024-01-10T08:00:00Z",
                    "lastModifiedDateTime": "2024-01-12T11:20:00Z",
                    "size": 2048000,
                    "file": {
                        "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    },
                }
            ]

            return {
                "status": "success",
                "data": {"value": mock_files, "nextLink": None},
            }
        except Exception as e:
            logger.error(f"OneDrive search failed: {e}")
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
                "webUrl": f"https://onedrive.live.com/redir?resid={file_id}",
                "createdDateTime": "2024-01-15T10:00:00Z",
                "lastModifiedDateTime": "2024-01-20T14:30:00Z",
                "size": 1024000,
                "file": {
                    "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                },
                "createdBy": {
                    "user": {"displayName": "User Name", "email": "user@example.com"}
                },
            }

            return {"status": "success", "data": mock_metadata}
        except Exception as e:
            logger.error(f"OneDrive get file metadata failed: {e}")
            return {
                "status": "error",
                "message": f"Failed to get file metadata: {str(e)}",
            }

    async def download_file(self, access_token: str, file_id: str) -> Dict[str, Any]:
        """Get download URL for a file."""
        try:
            # Mock implementation
            download_url = f"{self.base_url}/items/{file_id}/content"
            return {
                "status": "success",
                "data": {
                    "downloadUrl": download_url,
                    "expiration": "2024-01-21T12:00:00Z",
                },
            }
        except Exception as e:
            logger.error(f"OneDrive download file failed: {e}")
            return {"status": "error", "message": f"Download failed: {str(e)}"}

    async def sync_to_postgres_cache(self, workspace_id: str, access_token: str) -> Dict[str, Any]:
        """Sync OneDrive analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric
            
            # List files to get counts
            files_res = await self.list_files(access_token)
            if files_res["status"] == "error":
                return {"success": False, "error": files_res["message"]}
                
            items = files_res["data"].get("value", [])
            file_count = sum(1 for item in items if "file" in item)
            folder_count = sum(1 for item in items if "folder" in item)
            
            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("onedrive_file_count", file_count, "count"),
                    ("onedrive_folder_count", folder_count, "count"),
                ]
                
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        tenant_id=workspace_id,
                        integration_type="onedrive",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            tenant_id=workspace_id,
                            integration_type="onedrive",
                            metric_key=key,
                            value=float(value),
                            unit=unit
                        )
                        db.add(metric)
                    metrics_synced += 1
                
                db.commit()
                logger.info(f"Synced {metrics_synced} OneDrive metrics to PostgreSQL cache for workspace {workspace_id}")
            except Exception as e:
                logger.error(f"Error saving OneDrive metrics to Postgres: {e}")
                db.rollback()
                return {"success": False, "error": str(e)}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"OneDrive PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": str(e)}

    async def full_sync(self, workspace_id: str, access_token: str) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for OneDrive"""
        # Pipeline 1: Atom Memory
        # Triggered via onedrive_memory_ingestion or similar
        
        # Pipeline 2: Postgres Cache
        cache_result = await self.sync_to_postgres_cache(workspace_id, access_token)
        
        return {
            "success": True,
            "workspace_id": workspace_id,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

# Service instance removed - use IntegrationRegistry instead
# onedrive_service = OneDriveService(tenant_id="system", config={})
