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
from core.integrations.token_store import resolve_integration_token

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

    MAX_WALK_DEPTH = 25
    MAX_WALK_ITEMS = 10000

    _GDOCS_EXPORT_EXT = {
        "application/vnd.google-apps.document": "docx",
        "application/vnd.google-apps.spreadsheet": "xlsx",
        "application/vnd.google-apps.presentation": "pptx",
    }

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
        """Resolve a Drive access token from the unified-OAuth IntegrationToken
        row, then stored connections, then env.

        1. IntegrationToken (providers google/gmail/google_drive — what the
           /api/v1/auth/oauth/google/callback flow writes; auto-refreshed).
        2. ConnectionService (UserConnection) — legacy in-app connections.
        3. GOOGLE_DRIVE_ACCESS_TOKEN env var (dev/convenience).
        """
        token = await resolve_integration_token(
            user_id, ("google", "google_drive", "gmail"), self._refresh
        )
        if token:
            return token
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

    async def _refresh(self, refresh_token: Optional[str]) -> Optional[Dict[str, Any]]:
        """Exchange a refresh token for a fresh access token (Google OAuth2)."""
        if not refresh_token:
            return None
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                    },
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to refresh Google Drive token: {e}")
            return None

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
            return _error("Authentication failed")

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
                {"id": "walk_files", "name": "Walk All Files (Recursive)"},
                {"id": "search_files", "name": "Search Files"},
                {"id": "get_file_metadata", "name": "Get File Metadata"},
                {"id": "download_file", "name": "Download File"},
                {"id": "ingest_file_to_memory", "name": "Ingest File to ATOM Memory"},
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
            logger.error(f"Google Drive health check failed: {e}")
            return {"status": "unhealthy", "message": "Google Drive health check failed"}

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        operations = {
            "list_files": self.list_files,
            "walk_files": self.walk_files,
            "search_files": self.search_files,
            "get_file_metadata": self.get_file_metadata,
            "download_file": self.download_file,
            "ingest_file_to_memory": self.ingest_file_to_memory,
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
            return {"success": False, "error": "Google Drive operation failed", "details": {"operation": operation}}

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
            return _error("Failed to list files")

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
            return _error("Search failed")

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
            return _error("Failed to get file metadata")

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
            return _error("Download failed")

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
            return _error("Upload failed")

    # -------------------------------------------------------------------------
    # Sync / cache
    # -------------------------------------------------------------------------

    async def walk_files(
        self,
        access_token: str,
        folder_id: Optional[str] = None,
        max_depth: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Recursively walk Google Drive and return every file with its path.

        Descends into every subfolder up to ``max_depth`` (default
        MAX_WALK_DEPTH), following nextPageToken pagination within each folder
        so large folders are not truncated to the first page. Each returned
        entry is a Drive file resource plus ``path`` (full folder path) and
        ``depth``. Per-folder listing errors are logged and skipped so one
        inaccessible folder cannot abort the whole walk.
        """
        max_depth = max_depth if max_depth is not None else self.MAX_WALK_DEPTH
        token = self._resolve_token(access_token)
        if not token:
            return []

        seen_folders: set = set()
        out: List[Dict[str, Any]] = []

        async def _list_all(parent: Optional[str]) -> List[Dict[str, Any]]:
            items: List[Dict[str, Any]] = []
            page_token: Optional[str] = None
            while len(items) < self.MAX_WALK_ITEMS:
                params: Dict[str, Any] = {
                    "pageSize": 1000,
                    "fields": f"nextPageToken,files({_FILE_FIELDS})",
                    # None means the true root folder — filter to its children
                    # only, otherwise the walk double-counts nested files.
                    "q": (
                        f"'{parent or 'root'}' in parents and trashed = false"
                    ),
                }
                if page_token:
                    params["pageToken"] = page_token
                data = await self._drive_get(token, f"{DRIVE_API_BASE}/files", params=params)
                items.extend(data.get("files", []))
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
            return items

        async def _walk(parent: Optional[str], path: str, depth: int) -> None:
            if depth > max_depth:
                return
            key = parent or "root"
            if key in seen_folders:
                return
            seen_folders.add(key)
            try:
                entries = await _list_all(parent)
            except Exception as e:
                logger.warning(f"Google Drive walk skipped folder {key}: {e}")
                return
            for entry in entries:
                if not entry.get("id"):
                    continue
                if entry.get("mimeType") == "application/vnd.google-apps.folder":
                    await _walk(entry["id"], f"{path}/{entry.get('name', '')}", depth + 1)
                else:
                    entry["path"] = path
                    entry["depth"] = depth
                    out.append(entry)

        await _walk(folder_id, "", 0)
        return out

    async def ingest_file_to_memory(
        self,
        access_token: str,
        file_id: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
        role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Download a file and process it through the ingestion pipeline.

        Every file type is attempted; Google-native Docs/Sheets/Slides are
        exported to their Office equivalents before parsing, and anything the
        parser chain cannot extract is skipped gracefully.
        role: optional AI-employee role tag (canvas-scoped loads pass the
        attached hire's category) for role-aware recall.
        """
        token = self._resolve_token(access_token)
        if not token:
            return {"success": False, "error": "No access token provided"}

        content = await self.download_file_bytes(token, file_id)
        if content is None:
            return {"success": False, "error": "Failed to download file"}

        try:
            file_name = "unknown"
            meta_res = await self.get_file_metadata(token, file_id)
            if meta_res.get("status") == "success":
                file_name = meta_res["data"].get("name") or "unknown"
                # Exported Google-native files arrive as Office bytes but the
                # name lacks an extension — append it so the parser dispatches.
                mime = meta_res["data"].get("mimeType", "")
                ext = self._GDOCS_EXPORT_EXT.get(mime)
                if ext and "." not in file_name:
                    file_name = f"{file_name}.{ext}"

            from core.auto_document_ingestion import AutoDocumentIngestionService
            ingestor = AutoDocumentIngestionService()
            result = await ingestor.process_file_bytes(
                content,
                file_name=file_name,
                source="google_drive",
                user_id=self.tenant_id,
                extra_metadata=extra_metadata,
                external_id=file_id,
                role=role,
            )
            # Shared semantics (core.auto_document_ingestion): unchanged
            # re-ingests are success no-ops; unsupported formats and write
            # failures must NOT be masked as success.
            from core.auto_document_ingestion import interpret_ingest_result
            return {**interpret_ingest_result(result), "result": result}
        except Exception as e:
            logger.error(f"Failed to ingest Google Drive file {file_id}: {e}")
            return {"success": False, "error": str(e)}

    async def sync_to_postgres_cache(self, workspace_id: str, access_token: str) -> Dict[str, Any]:
        """Sync Google Drive analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric

            files = await self.walk_files(access_token)
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
                        workspace_id=workspace_id,
                        integration_type="google_drive",
                        metric_key=key,
                    ).first()
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        db.add(
                            IntegrationMetric(
                                workspace_id=workspace_id,
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
                logger.error(f"Error saving Google Drive metrics to Postgres: {e}")
                db.rollback()
                return {"success": False, "error": "Failed to save Google Drive metrics"}
            finally:
                db.close()

            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Google Drive PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": "Google Drive cache sync failed"}

    async def _ingest_walked_files(
        self, access_token: str, files: List[Dict[str, Any]], modified_field: str,
        role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Ingest walked files into memory with folder-path context.

        Shared tally loop for full_sync (whole drive) and
        ingest_folder_to_memory (selected subtrees).
        """
        ingested = 0
        skipped: list[str] = []
        errors: list[str] = []
        for f in files:
            name = f.get("name", "") or ""
            try:
                meta = {
                    "folder_path": f.get("path") or "",
                    "modified_at": f.get(modified_field) or "",
                }
                res = await self.ingest_file_to_memory(
                    access_token, f.get("id"), extra_metadata=meta, role=role
                )
                inner = res.get("result") or {}
                if res.get("success") and inner.get("status") == "ingested":
                    ingested += 1
                elif res.get("error"):
                    errors.append(f"{name}: {res['error']}")
                else:
                    skipped.append(f"{name} ({inner.get('reason') or 'no_text'})")
            except Exception as file_err:
                errors.append(f"{name}: {file_err}")
        return {
            "files_found": len(files),
            "files_ingested": ingested,
            "files_skipped": skipped,
            "errors": errors,
        }

    async def ingest_folder_to_memory(
        self,
        access_token: str,
        folder_id: str,
        folder_name: Optional[str] = None,
        role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Recursively ingest one folder subtree into Atom memory.

        User-selected folder ingestion ("Ingest folders") — the same
        walk + parse pipeline as full_sync, scoped to the chosen folder.
        role: optional AI-employee role tag (canvas-scoped loads pass the
        attached hire's category) for role-aware recall.
        """
        files = await self.walk_files(access_token, folder_id=folder_id or None)
        tally = await self._ingest_walked_files(access_token, files, "modifiedTime", role=role)
        return {
            "success": True,
            "folder_id": folder_id,
            "folder_name": folder_name,
            **tally,
        }

    async def full_sync(self, workspace_id: str, access_token: str) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Google Drive.

        Pipeline 1: Ingest every file (all types, all subfolders, pagination
        followed) into Atom memory (LanceDB + GraphRAG) with folder-path
        context stamped into the memory metadata.
        Pipeline 2: Refresh the Postgres metrics cache.
        """
        files = await self.walk_files(access_token)
        tally = await self._ingest_walked_files(access_token, files, "modifiedTime")

        cache_result = await self.sync_to_postgres_cache(workspace_id, access_token)
        return {
            "success": True,
            "workspace_id": workspace_id,
            **tally,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Module-level singleton: restored so legacy imports (e.g. auto_document_ingestion)
# keep working. Prefer the registry / explicit instantiation for new code.
google_drive_service = GoogleDriveService(tenant_id="system", config={})
