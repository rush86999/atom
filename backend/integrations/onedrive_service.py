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
from core.integrations.token_store import resolve_integration_token

logger = logging.getLogger(__name__)

# Microsoft Graph API scopes for OneDrive (delegated user-level scopes only — no *.All to avoid requiring admin consent)
ONEDRIVE_SCOPES = [
    "https://graph.microsoft.com/Files.Read",
    "https://graph.microsoft.com/Files.ReadWrite",
    "https://graph.microsoft.com/User.Read",
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

    MAX_WALK_DEPTH = 25
    MAX_WALK_ITEMS = 10000

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
        """Resolve a usable Graph access token from IntegrationToken or stored connections.

        1. IntegrationToken (providers onedrive, microsoft, outlook, microsoft365; auto-refreshed).
        2. ConnectionService (UserConnection) — legacy in-app connections.

        Deliberately NO process-wide env fallback: a shared
        ONEDRIVE/MICROSOFT_ACCESS_TOKEN would let any authenticated user without
        their own grant operate on the env-owner's OneDrive (user isolation).
        """
        token = await resolve_integration_token(
            user_id, ("onedrive", "microsoft", "outlook", "microsoft365"), self._refresh
        )
        if token:
            return token
        for integration_id in ("onedrive", "microsoft365", "microsoft", "outlook"):
            connections = connection_service.get_connections(user_id, integration_id)
            if not connections:
                continue
            conn_id = connections[0]["id"]
            creds = await connection_service.get_connection_credentials(conn_id, user_id)
            if creds and creds.get("access_token"):
                return creds["access_token"]
        return None

    async def _refresh(self, refresh_token: Optional[str]) -> Optional[Dict[str, Any]]:
        """Exchange a refresh token for a fresh Microsoft Graph access token."""
        if not refresh_token:
            return None
        try:
            tenant = os.getenv("MICROSOFT_TENANT_ID") or "common"
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "client_id": os.getenv("MICROSOFT_CLIENT_ID"),
                        "client_secret": os.getenv("MICROSOFT_CLIENT_SECRET"),
                        "scope": " ".join(self.required_scopes),
                    },
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to refresh OneDrive token: {e}")
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
            return _error("Authentication failed")

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
        # /content replies 302 to a pre-authed CDN URL — follow it (httpx
        # drops the Authorization header on cross-host redirects by default).
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
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
                {"id": "walk_files", "description": "Walk all files recursively"},
                {"id": "search_files", "description": "Search files in OneDrive"},
                {"id": "get_file_metadata", "description": "Get file metadata"},
                {"id": "download_file", "description": "Get download URL for a file"},
                {"id": "ingest_file_to_memory", "description": "Ingest file to ATOM memory"},
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
            "walk_files": self.walk_files,
            "search_files": self.search_files,
            "get_file_metadata": self.get_file_metadata,
            "download_file": self.download_file,
            "ingest_file_to_memory": self.ingest_file_to_memory,
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
            return _error("Failed to list files")

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
            return _error("Search failed")

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
            return _error("Failed to get file metadata")

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
            return _error("Download failed")

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

    async def _download_file_bytes(self, access_token: str, file_id: str) -> Optional[bytes]:
        """Private alias used by ingest_file_to_memory (patchable in tests)."""
        return await self.download_file_bytes(access_token, file_id)

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
        """Recursively walk OneDrive and return every file with its folder path.

        Descends into every subfolder up to ``max_depth`` (default
        MAX_WALK_DEPTH), following @odata.nextLink pagination within each
        folder so large folders are not truncated to the first page. Each
        returned entry is a Graph drive item plus ``path`` (full folder path)
        and ``depth``. Per-folder listing errors are logged and skipped so one
        inaccessible folder cannot abort the whole walk.
        """
        max_depth = max_depth if max_depth is not None else self.MAX_WALK_DEPTH
        token = self._resolve_token(access_token)
        if not token:
            return []

        seen_folders: set = set()
        out: List[Dict[str, Any]] = []

        async def _list_all(item_id: Optional[str]) -> List[Dict[str, Any]]:
            # Follow nextLink pagination until exhausted (capped by MAX_WALK_ITEMS).
            items: List[Dict[str, Any]] = []
            url = (
                f"{self.base_url}/me/drive/items/{item_id}/children?$top=200"
                if item_id
                else f"{self.base_url}/me/drive/root/children?$top=200"
            )
            while url and len(items) < self.MAX_WALK_ITEMS:
                data = await self._graph_get(token, url)
                items.extend(data.get("value", []))
                url = data.get("@odata.nextLink")
            return items

        async def _walk(item_id: Optional[str], path: str, depth: int) -> None:
            if depth > max_depth:
                return
            key = item_id or "root"
            if key in seen_folders:
                return
            seen_folders.add(key)
            try:
                entries = await _list_all(item_id)
            except Exception as e:
                logger.warning(f"OneDrive walk skipped folder {key}: {e}")
                return
            for entry in entries:
                if not entry.get("id"):
                    continue
                if "folder" in entry:
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

        Every file type is attempted; the parser chain decides what is
        extractable and skips gracefully otherwise.
        role: optional AI-employee role tag (canvas-scoped loads pass the
        attached hire's category) for role-aware recall.
        """
        token = self._resolve_token(access_token)
        if not token:
            return {"success": False, "error": "No access token provided"}

        # Private alias — the single download seam (patched in tests).
        content = await self._download_file_bytes(token, file_id)
        if content is None:
            return {"success": False, "error": "Failed to download file"}

        try:
            meta_res = await self.get_file_metadata(token, file_id)
            file_name = "unknown"
            if meta_res.get("status") == "success":
                file_name = meta_res["data"].get("name") or "unknown"

            from core.auto_document_ingestion import AutoDocumentIngestionService
            ingestor = AutoDocumentIngestionService()
            result = await ingestor.process_file_bytes(
                content,
                file_name=file_name,
                source="onedrive",
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
            logger.error(f"Failed to ingest OneDrive file {file_id}: {e}")
            return {"success": False, "error": str(e)}

    async def sync_to_postgres_cache(self, workspace_id: str, access_token: str) -> Dict[str, Any]:
        """Sync OneDrive analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric

            files = await self.walk_files(access_token)
            file_count = len(files)
            folder_count = len({f.get("path") or "" for f in files if f.get("path")})

            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("onedrive_file_count", file_count, "count"),
                    ("onedrive_folder_count", folder_count, "count"),
                ]

                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        workspace_id=workspace_id,
                        integration_type="onedrive",
                        metric_key=key,
                    ).first()

                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            workspace_id=workspace_id,
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
                return {"success": False, "error": "Failed to save OneDrive metrics"}
            finally:
                db.close()

            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"OneDrive PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": "OneDrive cache sync failed"}

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
        tally = await self._ingest_walked_files(access_token, files, "lastModifiedDateTime", role=role)
        return {
            "success": True,
            "folder_id": folder_id,
            "folder_name": folder_name,
            **tally,
        }

    async def full_sync(self, workspace_id: str, access_token: str) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for OneDrive.

        Pipeline 1: Ingest every file (all types, all subfolders, pagination
        followed) into Atom memory (LanceDB + GraphRAG) with folder-path
        context stamped into the memory metadata.
        Pipeline 2: Refresh the Postgres metrics cache.
        """
        files = await self.walk_files(access_token)
        tally = await self._ingest_walked_files(access_token, files, "lastModifiedDateTime")

        cache_result = await self.sync_to_postgres_cache(workspace_id, access_token)
        return {
            "success": True,
            "workspace_id": workspace_id,
            **tally,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Module-level singleton: restored so legacy imports (e.g. microsoft365_learner)
# keep working. Prefer the registry for new code.
onedrive_service = OneDriveService(tenant_id="system", config={})
