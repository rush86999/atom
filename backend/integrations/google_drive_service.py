"""
Google Drive Service Integration for ATOM Platform

Real Google Drive API v3 integration. Replaces the previous mock implementation.

Token resolution mirrors the OneDrive/WorkDrive pattern:
1. An explicit ``access_token`` passed by the caller (routes do this).
2. A DB-backed connection via ConnectionService (auto-refreshes), looked up by
   ``user_id`` for integrations ``google_drive`` then ``google``.
3. The ``GOOGLE_DRIVE_ACCESS_TOKEN`` env var (dev/convenience).

All public methods preserve the {"status", "data"/"message"} envelope and the
{files:[...], nextPageToken} list shape so existing routes, the universal
integration service, and MCP callers continue to work unchanged.
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

# Google Drive API v3 scopes. drive.file is required for write/upload operations;
# drive.readonly covers read; drive.metadata.readonly is a narrower read scope.
GOOGLE_DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
]

DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"

# Initialize router
google_drive_router = APIRouter(prefix="/google_drive", tags=["Google Drive"])


# Pydantic models
class GoogleDriveFile(BaseModel):
    id: str
    name: str
    mimeType: Optional[str] = None
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


def _success(data: Any) -> Dict[str, Any]:
    return {"status": "success", "data": data}


def _error(message: str, **extra: Any) -> Dict[str, Any]:
    return {"status": "error", "message": message, **extra}


# Fields we request for list/search/metadata (reduces payload, standardizes shape).
_FILE_FIELDS = (
    "id,name,mimeType,webViewLink,createdTime,modifiedTime,size,"
    "owners(displayName,emailAddress)"
)


class GoogleDriveService(IntegrationService):
    """Real Google Drive service backed by the Drive API v3 REST endpoints."""

    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        super().__init__(tenant_id=tenant_id, config=config)
        self.service_name = "google_drive"
        self.required_scopes = GOOGLE_DRIVE_SCOPES
        # access_token may be injected via config (used by universal_integration_service
        # which reads getattr(service, 'access_token', None)).
        self.access_token = config.get("access_token")

    # -------------------------------------------------------------------------
    # Token resolution
    # -------------------------------------------------------------------------

    async def get_access_token(self, user_id: str) -> Optional[str]:
        """Resolve a Drive access token from stored connections or env.

        Tries a ``google_drive`` connection first, then the shared ``google``
        connection (the generic Google OAuth app covers Drive when the right
        scopes were granted). ConnectionService auto-refreshes expired tokens.
        """
        for integration_id in ("google_drive", "google"):
            connections = connection_service.get_connections(user_id, integration_id)
            if not connections:
                continue
            conn_id = connections[0]["id"]
            creds = await connection_service.get_connection_credentials(conn_id, user_id)
            if creds and creds.get("access_token"):
                return creds["access_token"]
        # Dev convenience fallback.
        return os.getenv("GOOGLE_DRIVE_ACCESS_TOKEN")

    async def authenticate(self, user_id: str) -> Dict[str, Any]:
        """Generate the Google OAuth authorization URL for Drive."""
        try:
            client_id = os.getenv("GOOGLE_CLIENT_ID")
            redirect_uri = os.getenv(
                "GOOGLE_REDIRECT_URI",
                "http://localhost:8001/api/v1/auth/oauth/google/callback",
            )
            if not client_id:
                return _error("GOOGLE_CLIENT_ID not configured")

            params = {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": " ".join(self.required_scopes),
                "access_type": "offline",  # request a refresh token
                "prompt": "consent",  # force consent so refresh_token is always issued
                "state": f"google_drive_{user_id}",
            }
            auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
            return {"status": "success", "auth_url": auth_url, "state": f"google_drive_{user_id}"}
        except Exception as e:
            logger.error(f"Google Drive authentication failed: {e}")
            return _error(f"Authentication failed: {e}")

    def _resolve_token(self, access_token: Optional[str]) -> Optional[str]:
        return access_token or self.access_token

    async def _drive_get(
        self, access_token: str, url: str, params: Optional[dict] = None
    ) -> Dict[str, Any]:
        """Authenticated Drive API GET returning parsed JSON."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
            response.raise_for_status()
            if response.status_code == 204 or not response.content:
                return {}
            return response.json()

    async def _drive_get_bytes(self, access_token: str, url: str, params: Optional[dict] = None) -> bytes:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
            response.raise_for_status()
            return response.content

    # -------------------------------------------------------------------------
    # Capabilities / health / dispatch
    # -------------------------------------------------------------------------

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "operations": [
                {"id": "list_files", "name": "List Files"},
                {"id": "search_files", "name": "Search Files"},
                {"id": "get_file_metadata", "name": "Get File Metadata"},
                {"id": "download_file", "name": "Download File"},
                {"id": "sync_to_postgres_cache", "name": "Sync to Postgres Cache"},
                {"id": "full_sync", "name": "Full Sync"},
            ],
            "required_params": ["access_token"],
            "rate_limits": {"requests_per_minute": 100},
            "supports_webhooks": True,
        }

    async def health_check(self) -> Dict[str, Any]:
        try:
            if not (self.access_token or os.getenv("GOOGLE_DRIVE_ACCESS_TOKEN")):
                return {"status": "unhealthy", "message": "No access token configured"}
            return {"status": "healthy", "service": "google_drive"}
        except Exception as e:
            return {"status": "unhealthy", "message": str(e)}

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        operations = {
            "list_files": self.list_files,
            "search_files": self.search_files,
            "get_file_metadata": self.get_file_metadata,
            "download_file": self.download_file,
        }
        if operation not in operations:
            return {"success": False, "error": f"Unknown operation: {operation}"}
        try:
            result = await operations[operation](**parameters)
            if result.get("status") == "success":
                return {"success": True, "result": result.get("data")}
            return {"success": False, "error": result.get("message", "Unknown error")}
        except Exception as e:
            logger.error(f"Google Drive operation {operation} failed: {e}")
            return {"success": False, "error": str(e), "details": {"operation": operation}}

    # -------------------------------------------------------------------------
    # File operations (real Drive API v3)
    # -------------------------------------------------------------------------

    async def list_files(
        self,
        access_token: str,
        folder_id: Optional[str] = None,
        page_size: int = 100,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List files/folders from Google Drive via Drive API v3."""
        token = self._resolve_token(access_token)
        if not token:
            return _error("No access token provided")
        try:
            params: Dict[str, Any] = {
                "pageSize": min(page_size, 1000),
                "fields": f"nextPageToken,files({_FILE_FIELDS})",
                "orderBy": "modifiedTime desc",
            }
            if folder_id and folder_id != "root":
                # Filter to children of a specific folder.
                params["q"] = f"'{folder_id}' in parents and trashed = false"
            else:
                params["q"] = "trashed = false"
            if page_token:
                params["pageToken"] = page_token

            data = await self._drive_get(token, f"{DRIVE_API_BASE}/files", params=params)
            files = data.get("files", [])
            next_page = data.get("nextPageToken")
            logger.info(f"Listed {len(files)} Google Drive items")
            return _success({"files": files, "nextPageToken": next_page})
        except httpx.HTTPStatusError as e:
            logger.error(f"Google Drive list_files HTTP error: {e.response.status_code}")
            return _error(f"Failed to list files: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Google Drive list_files failed: {e}")
            return _error(f"Failed to list files: {e}")

    async def search_files(
        self,
        access_token: str,
        query: str,
        page_size: int = 100,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search files in Google Drive via Drive API v3."""
        token = self._resolve_token(access_token)
        if not token:
            return _error("No access token provided")
        try:
            # Escape single quotes in the query for the Drive q-syntax.
            safe_query = query.replace("'", "\\'")
            params: Dict[str, Any] = {
                "pageSize": min(page_size, 1000),
                "fields": f"nextPageToken,files({_FILE_FIELDS})",
                "q": f"fullText contains '{safe_query}' and trashed = false",
            }
            if page_token:
                params["pageToken"] = page_token

            data = await self._drive_get(token, f"{DRIVE_API_BASE}/files", params=params)
            files = data.get("files", [])
            next_page = data.get("nextPageToken")
            logger.info(f"Google Drive search '{query}' returned {len(files)} results")
            return _success({"files": files, "nextPageToken": next_page})
        except httpx.HTTPStatusError as e:
            logger.error(f"Google Drive search HTTP error: {e.response.status_code}")
            return _error(f"Search failed: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Google Drive search failed: {e}")
            return _error(f"Search failed: {e}")

    async def get_file_metadata(
        self, access_token: str, file_id: str
    ) -> Dict[str, Any]:
        """Get metadata for a specific file via Drive API v3."""
        token = self._resolve_token(access_token)
        if not token:
            return _error("No access token provided")
        try:
            data = await self._drive_get(
                token,
                f"{DRIVE_API_BASE}/files/{file_id}",
                params={"fields": _FILE_FIELDS, "supportsAllDrives": "true"},
            )
            return _success(data)
        except httpx.HTTPStatusError as e:
            logger.error(f"Google Drive get_file_metadata HTTP error: {e.response.status_code}")
            return _error(f"Failed to get file metadata: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Google Drive get file metadata failed: {e}")
            return _error(f"Failed to get file metadata: {e}")

    async def download_file(self, access_token: str, file_id: str) -> Dict[str, Any]:
        """Download a file from Google Drive, returning content as base64.

        Uses the ``?alt=media`` endpoint. Google Docs/Sheets/Slides (native Google
        formats) are exported as their Office equivalents.
        """
        import base64 as _b64

        token = self._resolve_token(access_token)
        if not token:
            return _error("No access token provided")
        try:
            # First fetch metadata to detect Google Docs formats (need export).
            meta_res = await self.get_file_metadata(token, file_id)
            mime = None
            if meta_res.get("status") == "success":
                mime = meta_res["data"].get("mimeType", "")

            export_map = {
                "application/vnd.google-apps.document": (
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "docx",
                ),
                "application/vnd.google-apps.spreadsheet": (
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "xlsx",
                ),
                "application/vnd.google-apps.presentation": (
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    "pptx",
                ),
            }

            if mime in export_map:
                export_mime, _ = export_map[mime]
                content = await self._drive_get_bytes(
                    token,
                    f"{DRIVE_API_BASE}/files/{file_id}/export",
                    params={"mimeType": export_mime},
                )
            else:
                content = await self._drive_get_bytes(
                    token,
                    f"{DRIVE_API_BASE}/files/{file_id}",
                    params={"alt": "media"},
                )

            return _success(
                {
                    "downloadUrl": f"{DRIVE_API_BASE}/files/{file_id}?alt=media",
                    "content_b64": _b64.b64encode(content).decode("ascii"),
                    "size": len(content),
                    "mimeType": mime,
                }
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"Google Drive download_file HTTP error: {e.response.status_code}")
            return _error(f"Download failed: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Google Drive download file failed: {e}")
            return _error(f"Download failed: {e}")

    async def download_file_bytes(self, access_token: str, file_id: str) -> Optional[bytes]:
        """Download raw bytes for a file. Convenience method for ingestion paths."""
        token = self._resolve_token(access_token)
        if not token:
            return None
        try:
            # Detect Google Docs formats for export.
            meta_res = await self.get_file_metadata(token, file_id)
            mime = None
            if meta_res.get("status") == "success":
                mime = meta_res["data"].get("mimeType", "")

            export_map = {
                "application/vnd.google-apps.document": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/vnd.google-apps.spreadsheet": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.google-apps.presentation": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            }
            if mime in export_map:
                return await self._drive_get_bytes(
                    token,
                    f"{DRIVE_API_BASE}/files/{file_id}/export",
                    params={"mimeType": export_map[mime]},
                )
            return await self._drive_get_bytes(
                token, f"{DRIVE_API_BASE}/files/{file_id}", params={"alt": "media"}
            )
        except Exception as e:
            logger.error(f"Google Drive download_file_bytes failed: {e}")
            return None

    async def upload_file(
        self, access_token: str, file_name: str, content: bytes, folder_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Upload a file to Google Drive via the simple multipart upload (< 5MB)."""
        token = self._resolve_token(access_token)
        if not token:
            return _error("No access token provided")
        try:
            # For simplicity use the media upload endpoint (metadata + content in one PUT).
            metadata: Dict[str, Any] = {"name": file_name}
            if folder_id:
                metadata["parents"] = [folder_id]
            url = (
                f"{DRIVE_API_BASE}/files"
                "?uploadType=multipart"
                "&fields=id,name,mimeType,webViewLink"
            )
            import json as _json

            boundary = "atom-drive-314159"
            body = (
                f"--{boundary}\r\n"
                'Content-Type: application/json; charset=UTF-8\r\n\r\n'
                f"{_json.dumps(metadata)}\r\n"
                f"--{boundary}\r\n"
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode() + content + f"\r\n--{boundary}--".encode()

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": f"multipart/related; boundary={boundary}",
                    },
                    content=body,
                )
                response.raise_for_status()
                return _success(response.json())
        except httpx.HTTPStatusError as e:
            logger.error(f"Google Drive upload_file HTTP error: {e.response.status_code}")
            return _error(f"Upload failed: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Google Drive upload failed: {e}")
            return _error(f"Upload failed: {e}")

    # -------------------------------------------------------------------------
    # Sync / cache
    # -------------------------------------------------------------------------

    async def sync_to_postgres_cache(self, workspace_id: str, access_token: str) -> Dict[str, Any]:
        """Sync Google Drive analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric

            files_res = await self.list_files(access_token)
            if files_res["status"] == "error":
                return {"success": False, "error": files_res["message"]}

            files = files_res["data"].get("files", [])
            file_count = len(files)
            docs_count = sum(
                1 for f in files if "document" in f.get("mimeType", "")
            )
            sheets_count = sum(
                1 for f in files if "spreadsheet" in f.get("mimeType", "")
            )

            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("google_drive_file_count", file_count, "count"),
                    ("google_drive_docs_count", docs_count, "count"),
                    ("google_drive_sheets_count", sheets_count, "count"),
                ]
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        tenant_id=workspace_id,
                        integration_type="google_drive",
                        metric_key=key,
                    ).first()
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        db.add(
                            IntegrationMetric(
                                tenant_id=workspace_id,
                                integration_type="google_drive",
                                metric_key=key,
                                value=float(value),
                                unit=unit,
                            )
                        )
                    metrics_synced += 1
                db.commit()
                logger.info(
                    f"Synced {metrics_synced} Google Drive metrics for workspace {workspace_id}"
                )
            except Exception as e:
                db.rollback()
                return {"success": False, "error": str(e)}
            finally:
                db.close()

            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Google Drive PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": str(e)}

    async def full_sync(self, workspace_id: str, access_token: str) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Google Drive."""
        cache_result = await self.sync_to_postgres_cache(workspace_id, access_token)
        return {
            "success": True,
            "workspace_id": workspace_id,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Module-level singleton: restored so legacy imports (e.g. auto_document_ingestion)
# keep working. Prefer the registry / explicit instantiation for new code.
google_drive_service = GoogleDriveService(tenant_id="system", config={})
