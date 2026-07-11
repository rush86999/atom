"""
OneDrive Service Integration for ATOM Platform

Real Microsoft Graph API integration for OneDrive file operations.
Replaces the previous mock implementation. Token resolution is DB-backed
via ConnectionService (which auto-refreshes expired tokens), mirroring the
Zoho WorkDrive pattern. All public methods preserve the {"status", "data"/"message"}
envelope so existing routes and callers continue to work unchanged.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from core.connection_service import connection_service
from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)

# Microsoft Graph API scopes for OneDrive
ONEDRIVE_SCOPES = [
    "Files.Read",
    "Files.Read.All",
    "Files.ReadWrite",
    "Sites.Read.All",
    "offline_access",
]

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

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


def _error(message: str, **extra: Any) -> Dict[str, Any]:
    return {"status": "error", "message": message, **extra}


def _success(data: Any) -> Dict[str, Any]:
    return {"status": "success", "data": data}


class OneDriveService(IntegrationService):
    """Real OneDrive service backed by the Microsoft Graph API."""

    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        super().__init__(tenant_id=tenant_id, config=config)
        self.service_name = "onedrive"
        self.required_scopes = ONEDRIVE_SCOPES
        self.base_url = GRAPH_BASE_URL
        # access_token may be injected via config (e.g. by universal_integration_service)
        self.access_token = config.get("access_token")

    # -------------------------------------------------------------------------
    # OAuth / token resolution
    # -------------------------------------------------------------------------

    async def get_access_token(self, user_id: str) -> Optional[str]:
        """Resolve a usable Graph access token from stored connections.

        Tries an explicit ``onedrive`` connection first, then falls back to the
        shared ``microsoft365`` connection (same Azure AD app covers both).
        ConnectionService auto-refreshes expired tokens transparently.
        """
        for integration_id in ("onedrive", "microsoft365"):
            connections = connection_service.get_connections(user_id, integration_id)
            if not connections:
                continue
            conn_id = connections[0]["id"]
            creds = await connection_service.get_connection_credentials(conn_id, user_id)
            if creds and creds.get("access_token"):
                return creds["access_token"]
        return None

    async def authenticate(self, user_id: str) -> Dict[str, Any]:
        """Generate the Microsoft OAuth authorization URL for OneDrive."""
        try:
            client_id = os.getenv("MICROSOFT_CLIENT_ID")
            redirect_uri = os.getenv(
                "MICROSOFT_REDIRECT_URI",
                "http://localhost:8001/api/auth/microsoft/callback",
            )
            if not client_id:
                return _error("MICROSOFT_CLIENT_ID not configured")

            params = {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": " ".join(self.required_scopes),
                "state": f"onedrive_{user_id}",
                "response_mode": "query",
            }
            auth_url = (
                "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
                f"?{urlencode(params)}"
            )
            return {"status": "success", "auth_url": auth_url, "state": f"onedrive_{user_id}"}
        except Exception as e:
            logger.error(f"OneDrive authentication failed: {e}")
            return _error(f"Authentication failed: {e}")

    # -------------------------------------------------------------------------
    # Graph helpers
    # -------------------------------------------------------------------------

    async def _graph_get(self, access_token: str, url: str) -> Dict[str, Any]:
        """Perform an authenticated Graph GET, returning parsed JSON or raising."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url, headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            if response.status_code == 204 or not response.content:
                return {}
            return response.json()

    async def _graph_get_bytes(self, access_token: str, url: str) -> bytes:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                url, headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            return response.content

    def _resolve_token(self, access_token: Optional[str]) -> Optional[str]:
        return access_token or self.access_token

    # -------------------------------------------------------------------------
    # Capabilities / health / dispatch
    # -------------------------------------------------------------------------

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
        return {
            "healthy": True,
            "status": "healthy",
            "service": "onedrive",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "OneDrive service is operational",
        }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a OneDrive operation."""
        operations = {
            "list_files": self.list_files,
            "search_files": self.search_files,
            "get_file_metadata": self.get_file_metadata,
            "download_file": self.download_file,
        }

        if operation not in operations:
            return {
                "success": False,
                "error": f"Unknown operation: {operation}",
                "details": {"operation": operation},
            }

        try:
            result = await operations[operation](**parameters)
            if result.get("status") == "success":
                return {"success": True, "result": result.get("data")}
            return {"success": False, "error": result.get("message", "Unknown error")}
        except Exception as e:
            logger.error(f"OneDrive operation {operation} failed: {e}")
            return {"success": False, "error": str(e), "details": {"operation": operation}}

    # -------------------------------------------------------------------------
    # File operations (real Graph API)
    # -------------------------------------------------------------------------

    async def list_files(
        self,
        access_token: str,
        folder_id: Optional[str] = None,
        page_size: int = 100,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List files/folders from OneDrive via Graph API."""
        token = self._resolve_token(access_token)
        if not token:
            return _error("No access token provided")

        try:
            # folder_id may be an item id; empty/None means root.
            if folder_id:
                url = f"{self.base_url}/me/drive/items/{folder_id}/children"
            else:
                url = f"{self.base_url}/me/drive/root/children"

            params_list: List[str] = [f"$top={page_size}"]
            if page_token:
                # page_token is the raw skip/$skiptoken value from a previous nextLink
                params_list.append(page_token if page_token.startswith("$") else f"$skiptoken={page_token}")
            url = f"{url}?{'&'.join(params_list)}"

            data = await self._graph_get(token, url)
            value = data.get("value", [])
            next_link = data.get("@odata.nextLink")
            logger.info(f"Listed {len(value)} OneDrive items")
            return _success({"value": value, "nextLink": next_link})
        except httpx.HTTPStatusError as e:
            logger.error(f"OneDrive list_files HTTP error: {e.response.status_code} {e.response.text[:200]}")
            return _error(f"Failed to list files: {e.response.status_code}")
        except Exception as e:
            logger.error(f"OneDrive list_files failed: {e}")
            return _error(f"Failed to list files: {e}")

    async def list_drive_items(
        self, access_token: str, path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return a bare list of items for a given path (used by universal service).

        Unlike :meth:`list_files`, this returns a plain list (no envelope) so the
        universal integration service can iterate and filter in Python.
        """
        token = self._resolve_token(access_token)
        if not token:
            return []
        try:
            if path:
                url = f"{self.base_url}/me/drive/root:/{path}:/children"
            else:
                url = f"{self.base_url}/me/drive/root/children"
            data = await self._graph_get(token, url)
            return data.get("value", [])
        except Exception as e:
            logger.error(f"OneDrive list_drive_items failed: {e}")
            return []

    async def search_files(
        self,
        access_token: str,
        query: str,
        page_size: int = 100,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search files in OneDrive via Graph API."""
        token = self._resolve_token(access_token)
        if not token:
            return _error("No access token provided")

        try:
            # Graph search is keyword-based (no wildcards needed).
            from urllib.parse import quote
            url = f"{self.base_url}/me/drive/root/search(q='{quote(query)}')?$top={page_size}"
            data = await self._graph_get(token, url)
            value = data.get("value", [])
            next_link = data.get("@odata.nextLink")
            logger.info(f"OneDrive search '{query}' returned {len(value)} results")
            return _success({"value": value, "nextLink": next_link})
        except httpx.HTTPStatusError as e:
            logger.error(f"OneDrive search HTTP error: {e.response.status_code}")
            return _error(f"Search failed: {e.response.status_code}")
        except Exception as e:
            logger.error(f"OneDrive search failed: {e}")
            return _error(f"Search failed: {e}")

    async def get_file_metadata(
        self, access_token: str, file_id: str
    ) -> Dict[str, Any]:
        """Get metadata for a specific file via Graph API."""
        token = self._resolve_token(access_token)
        if not token:
            return _error("No access token provided")
        try:
            data = await self._graph_get(token, f"{self.base_url}/me/drive/items/{file_id}")
            return _success(data)
        except httpx.HTTPStatusError as e:
            logger.error(f"OneDrive get_file_metadata HTTP error: {e.response.status_code}")
            return _error(f"Failed to get file metadata: {e.response.status_code}")
        except Exception as e:
            logger.error(f"OneDrive get file metadata failed: {e}")
            return _error(f"Failed to get file metadata: {e}")

    async def download_file(self, access_token: str, file_id: str) -> Dict[str, Any]:
        """Download a file from OneDrive, returning content as base64.

        Returns ``{"downloadUrl": ..., "content_b64": ..., "size": N}``. We inline
        the content (base64) because the Graph pre-authenticated download URLs
        expire quickly and are not safe to hand back to a caller for later use.
        """
        import base64 as _b64

        token = self._resolve_token(access_token)
        if not token:
            return _error("No access token provided")
        try:
            content = await self._graph_get_bytes(
                token, f"{self.base_url}/me/drive/items/{file_id}/content"
            )
            return _success(
                {
                    "downloadUrl": f"{self.base_url}/me/drive/items/{file_id}/content",
                    "content_b64": _b64.b64encode(content).decode("ascii"),
                    "size": len(content),
                }
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"OneDrive download_file HTTP error: {e.response.status_code}")
            return _error(f"Download failed: {e.response.status_code}")
        except Exception as e:
            logger.error(f"OneDrive download file failed: {e}")
            return _error(f"Download failed: {e}")

    async def download_file_bytes(self, access_token: str, file_id: str) -> Optional[bytes]:
        """Download raw bytes for a file. Convenience method for ingestion paths."""
        token = self._resolve_token(access_token)
        if not token:
            return None
        try:
            return await self._graph_get_bytes(
                token, f"{self.base_url}/me/drive/items/{file_id}/content"
            )
        except Exception as e:
            logger.error(f"OneDrive download_file_bytes failed: {e}")
            return None

    async def upload_file(
        self, access_token: str, file_name: str, content: bytes, folder_path: str = ""
    ) -> Dict[str, Any]:
        """Upload a file to OneDrive (simple upload, < 4MB)."""
        token = self._resolve_token(access_token)
        if not token:
            return _error("No access token provided")
        try:
            if folder_path:
                url = f"{self.base_url}/me/drive/root:/{folder_path}/{file_name}:/content"
            else:
                url = f"{self.base_url}/me/drive/root:/{file_name}:/content"
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.put(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/octet-stream",
                    },
                    content=content,
                )
                response.raise_for_status()
                return _success(response.json())
        except httpx.HTTPStatusError as e:
            logger.error(f"OneDrive upload_file HTTP error: {e.response.status_code}")
            return _error(f"Upload failed: {e.response.status_code}")
        except Exception as e:
            logger.error(f"OneDrive upload failed: {e}")
            return _error(f"Upload failed: {e}")

    # -------------------------------------------------------------------------
    # Sync / cache
    # -------------------------------------------------------------------------

    async def sync_to_postgres_cache(self, workspace_id: str, access_token: str) -> Dict[str, Any]:
        """Sync OneDrive analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric

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
                        metric_key=key,
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
                            unit=unit,
                        )
                        db.add(metric)
                    metrics_synced += 1

                db.commit()
                logger.info(
                    f"Synced {metrics_synced} OneDrive metrics to PostgreSQL cache for workspace {workspace_id}"
                )
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
        """Trigger full dual-pipeline sync for OneDrive."""
        cache_result = await self.sync_to_postgres_cache(workspace_id, access_token)
        return {
            "success": True,
            "workspace_id": workspace_id,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Module-level singleton: restored so legacy imports (e.g. microsoft365_learner)
# keep working. Prefer the registry for new code.
onedrive_service = OneDriveService(tenant_id="system", config={})
