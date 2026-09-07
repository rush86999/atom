"""
Box Service Integration for ATOM Platform

Real Box Content API v2.0 integration over httpx. Token resolution mirrors
the OneDrive/Google Drive/Dropbox connectors: an explicit ``access_token``
argument (routes pass this), a config-injected token (universal integration
service), or the ``BOX_ACCESS_TOKEN`` env var (dev convenience).

All public methods preserve the {"status", "data"/"message"} envelope so
existing routes and callers continue to work unchanged.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from core.integration_service import IntegrationService
from core.integrations.token_store import resolve_integration_token

logger = logging.getLogger(__name__)

# Box API scopes
BOX_SCOPES = [
    "root_readonly",
    "manage_app_users",
    "manage_webhook",
]

BOX_AUTH_BASE = "https://account.box.com/api/oauth2/authorize"


def _success(data: Any) -> Dict[str, Any]:
    return {"status": "success", "data": data}


def _error(message: str) -> Dict[str, Any]:
    return {"status": "error", "message": message}


class BoxService(IntegrationService):
    """Box service backed by the real Box Content API (api.box.com/2.0)."""

    MAX_WALK_DEPTH = 25
    MAX_WALK_ITEMS = 10000

    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        super().__init__(tenant_id=tenant_id, config=config)
        self.service_name = "box"
        self.required_scopes = BOX_SCOPES
        self.base_url = "https://api.box.com/2.0"
        # access_token may be injected via config (universal_integration_service)
        self.access_token = config.get("access_token")

    def _resolve_token(self, access_token: Optional[str]) -> Optional[str]:
        return access_token or self.access_token or os.getenv("BOX_ACCESS_TOKEN")

    async def get_access_token(self, user_id: str) -> Optional[str]:
        """Resolve a usable Box token from the stored IntegrationToken row.

        The unified OAuth connect flow (/api/v1/auth/oauth/box/callback)
        writes an encrypted IntegrationToken for provider ``box``. Mirrors the
        Zoho WorkDrive pattern: expired tokens are refreshed with the stored
        refresh token and persisted.
        """
        return await resolve_integration_token(user_id, ("box",), self._refresh)

    async def _refresh(self, refresh_token: Optional[str]) -> Optional[Dict[str, Any]]:
        """Exchange a refresh token for a fresh access token (Box OAuth2)."""
        if not refresh_token:
            return None
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url.replace('api.box.com/2.0', 'api.box.com')}/oauth2/token",
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "client_id": os.getenv("BOX_CLIENT_ID"),
                        "client_secret": os.getenv("BOX_CLIENT_SECRET"),
                    },
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to refresh Box token: {e}")
            return None

    def get_capabilities(self) -> Dict[str, Any]:
        """Return the capabilities of the Box service."""
        return {
            "operations": [
                {"id": "list_files", "description": "List files from Box"},
                {"id": "walk_files", "description": "Walk all files recursively"},
                {"id": "search_files", "description": "Search files in Box"},
                {"id": "get_file_metadata", "description": "Get file metadata"},
                {"id": "download_file", "description": "Get download URL for a file"},
                {"id": "ingest_file_to_memory", "description": "Ingest file to ATOM memory"},
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
            "list_files": self.list_files,
            "walk_files": self.walk_files,
            "search_files": self.search_files,
            "get_file_metadata": self.get_file_metadata,
            "download_file": self.download_file,
            "ingest_file_to_memory": self.ingest_file_to_memory,
            "create_folder": self.create_folder,
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

    # -------------------------------------------------------------------------
    # HTTP helpers
    # -------------------------------------------------------------------------

    async def _box_get(
        self, access_token: str, url: str, params: Optional[dict] = None
    ) -> Dict[str, Any]:
        """Authenticated Box GET returning parsed JSON."""
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

    async def _box_post(
        self, access_token: str, url: str, json_body: dict
    ) -> Dict[str, Any]:
        """Authenticated Box POST returning parsed JSON."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                json=json_body,
            )
            response.raise_for_status()
            if response.status_code == 204 or not response.content:
                return {}
            return response.json()

    async def _box_get_bytes(
        self, access_token: str, url: str
    ) -> bytes:
        """Authenticated Box GET returning raw bytes (follows the download
        redirect to dl.boxcloud.com)."""
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(
                url, headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            return response.content

    # -------------------------------------------------------------------------
    # Auth
    # -------------------------------------------------------------------------

    async def authenticate(self, user_id: str) -> Dict[str, Any]:
        """Generate the Box OAuth2 authorization URL."""
        try:
            client_id = os.getenv("BOX_CLIENT_ID")
            if not client_id:
                return _error("BOX_CLIENT_ID not configured")
            redirect_uri = os.getenv(
                "BOX_REDIRECT_URI",
                "http://localhost:8001/api/v1/auth/oauth/box/callback",
            )
            params = {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "state": f"box_{user_id}",
            }
            auth_url = f"{BOX_AUTH_BASE}?{urlencode(params)}"
            return {
                "status": "success",
                "auth_url": auth_url,
                "state": f"box_{user_id}",
            }
        except Exception as e:
            logger.error(f"Box authentication failed: {e}")
            return {"status": "error", "message": f"Authentication failed: {str(e)}"}

    # -------------------------------------------------------------------------
    # File operations (real Box Content API)
    # -------------------------------------------------------------------------

    async def list_files(
        self,
        access_token: str,
        folder_id: str = "0",
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List files/folders in a Box folder (GET /folders/{id}/items)."""
        token = self._resolve_token(access_token)
        if not token:
            return _error("No access token provided")
        try:
            data = await self._box_get(
                token,
                f"{self.base_url}/folders/{folder_id}/items",
                params={"limit": min(limit, 1000), "offset": offset},
            )
            entries = data.get("entries", [])
            return _success({
                "entries": entries,
                "total_count": data.get("total_count", len(entries)),
                "offset": data.get("offset", offset),
                "limit": data.get("limit", limit),
                "next_marker": None,
            })
        except httpx.HTTPStatusError as e:
            logger.error(f"Box list_files HTTP error: {e.response.status_code} {e.response.text[:200]}")
            return _error(f"Failed to list files: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Box list files failed: {e}")
            return _error(f"Failed to list files: {str(e)}")

    async def search_files(
        self,
        access_token: str,
        query: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Search files in Box (GET /search)."""
        token = self._resolve_token(access_token)
        if not token:
            return _error("No access token provided")
        try:
            data = await self._box_get(
                token,
                f"{self.base_url}/search",
                params={"query": query, "limit": min(limit, 200), "offset": offset},
            )
            entries = data.get("entries", [])
            return _success({
                "entries": entries,
                "total_count": data.get("total_count", len(entries)),
                "offset": offset,
                "limit": limit,
                "next_marker": None,
            })
        except httpx.HTTPStatusError as e:
            logger.error(f"Box search HTTP error: {e.response.status_code}")
            return _error(f"Search failed: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Box search failed: {e}")
            return _error(f"Search failed: {str(e)}")

    async def get_file_metadata(
        self, access_token: str, file_id: str
    ) -> Dict[str, Any]:
        """Get metadata for a specific file (GET /files/{id})."""
        token = self._resolve_token(access_token)
        if not token:
            return _error("No access token provided")
        try:
            data = await self._box_get(token, f"{self.base_url}/files/{file_id}")
            return _success(data)
        except httpx.HTTPStatusError as e:
            logger.error(f"Box get_file_metadata HTTP error: {e.response.status_code}")
            return _error(f"Failed to get file metadata: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Box get file metadata failed: {e}")
            return _error(f"Failed to get file metadata: {str(e)}")

    async def download_file(self, access_token: str, file_id: str) -> Dict[str, Any]:
        """Download a file from Box, returning content as base64.

        We inline the content (base64) because Box download URLs are
        pre-authenticated and short-lived — mirroring the OneDrive connector.
        """
        import base64 as _b64

        token = self._resolve_token(access_token)
        if not token:
            return _error("No access token provided")
        try:
            content = await self._box_get_bytes(
                token, f"{self.base_url}/files/{file_id}/content"
            )
            return _success({
                "downloadUrl": f"{self.base_url}/files/{file_id}/content",
                "content_b64": _b64.b64encode(content).decode("ascii"),
                "size": len(content),
            })
        except httpx.HTTPStatusError as e:
            logger.error(f"Box download_file HTTP error: {e.response.status_code}")
            return _error(f"Download failed: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Box download file failed: {e}")
            return _error(f"Download failed: {str(e)}")

    async def download_file_bytes(
        self, access_token: str, file_id: str
    ) -> Optional[bytes]:
        """Download raw bytes for a file. Convenience method for ingestion."""
        token = self._resolve_token(access_token)
        if not token:
            return None
        try:
            return await self._box_get_bytes(
                token, f"{self.base_url}/files/{file_id}/content"
            )
        except Exception as e:
            logger.error(f"Box download_file_bytes failed: {e}")
            return None

    async def _download_file_bytes(
        self, access_token: str, file_id: str
    ) -> Optional[bytes]:
        """Private alias used by ingest_file_to_memory (patchable in tests)."""
        return await self.download_file_bytes(access_token, file_id)

    async def create_folder(
        self, access_token: str, parent_folder_id: str, folder_name: str
    ) -> Dict[str, Any]:
        """Create a new folder in Box (POST /folders)."""
        token = self._resolve_token(access_token)
        if not token:
            return _error("No access token provided")
        try:
            data = await self._box_post(
                token,
                f"{self.base_url}/folders",
                {"name": folder_name, "parent": {"id": parent_folder_id}},
            )
            return _success(data)
        except httpx.HTTPStatusError as e:
            logger.error(f"Box create_folder HTTP error: {e.response.status_code} {e.response.text[:200]}")
            return _error(f"Failed to create folder: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Box create folder failed: {e}")
            return _error(f"Failed to create folder: {str(e)}")

    # -------------------------------------------------------------------------
    # Recursive walk + memory ingestion
    # -------------------------------------------------------------------------

    async def walk_files(
        self,
        access_token: str,
        folder_id: str = "0",
        max_depth: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Recursively walk Box and return every file with its folder path.

        Descends into every subfolder up to ``max_depth`` (default
        MAX_WALK_DEPTH), following offset pagination within each folder so
        large folders are not truncated to the first page. Each returned
        entry is a Box file object plus ``path`` (full folder path) and
        ``depth``. Per-folder listing errors are logged and skipped so one
        inaccessible folder cannot abort the whole walk.
        """
        max_depth = max_depth if max_depth is not None else self.MAX_WALK_DEPTH
        token = self._resolve_token(access_token)
        if not token:
            return []

        seen_folders: set = set()
        out: List[Dict[str, Any]] = []

        async def _list_all(fid: str) -> List[Dict[str, Any]]:
            # Follow offset pagination until exhausted (capped by MAX_WALK_ITEMS).
            items: List[Dict[str, Any]] = []
            offset = 0
            while len(items) < self.MAX_WALK_ITEMS:
                data = await self._box_get(
                    token,
                    f"{self.base_url}/folders/{fid}/items",
                    params={"limit": 1000, "offset": offset},
                )
                page = data.get("entries", [])
                items.extend(page)
                if len(page) < 1000:
                    break
                offset += 1000
            return items

        async def _walk(fid: str, path: str, depth: int) -> None:
            if depth > max_depth or fid in seen_folders:
                return
            seen_folders.add(fid)
            try:
                entries = await _list_all(fid)
            except Exception as e:
                logger.warning(f"Box walk skipped folder {fid}: {e}")
                return
            for entry in entries:
                if not entry.get("id"):
                    continue
                if entry.get("type") == "folder":
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
    ) -> Dict[str, Any]:
        """Download a file and process it through the ingestion pipeline.

        Every file type is attempted; the parser chain decides what is
        extractable and skips gracefully otherwise.
        """
        token = self._resolve_token(access_token)
        if not token:
            return {"success": False, "error": "No access token provided"}

        # Private alias — the single download seam (patched in tests).
        content = await self._download_file_bytes(token, file_id)
        if content is None:
            return {"success": False, "error": "Failed to download file"}

        try:
            file_name = "unknown"
            meta_res = await self.get_file_metadata(token, file_id)
            if meta_res.get("status") == "success":
                file_name = meta_res["data"].get("name") or "unknown"

            from core.auto_document_ingestion import AutoDocumentIngestionService
            ingestor = AutoDocumentIngestionService()
            result = await ingestor.process_file_bytes(
                content,
                file_name=file_name,
                source="box",
                user_id=self.tenant_id,
                extra_metadata=extra_metadata,
                external_id=file_id,
            )
            # Shared semantics (core.auto_document_ingestion): unchanged
            # re-ingests are success no-ops; unsupported formats and write
            # failures must NOT be masked as success.
            from core.auto_document_ingestion import interpret_ingest_result
            return {**interpret_ingest_result(result), "result": result}
        except Exception as e:
            logger.error(f"Failed to ingest Box file {file_id}: {e}")
            return {"success": False, "error": str(e)}

    async def sync_to_postgres_cache(self, workspace_id: str, access_token: str) -> Dict[str, Any]:
        """Sync Box analytics to PostgreSQL IntegrationMetric table."""
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
                    ("box_file_count", file_count, "count"),
                    ("box_folder_count", folder_count, "count"),
                ]

                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        workspace_id=workspace_id,
                        integration_type="box",
                        metric_key=key
                    ).first()

                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            workspace_id=workspace_id,
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
        """Trigger full dual-pipeline sync for Box.

        Pipeline 1: Ingest every file (all types, all subfolders, pagination
        followed) into Atom memory (LanceDB + GraphRAG) with folder-path
        context stamped into the memory metadata.
        Pipeline 2: Refresh the Postgres metrics cache.

        ``access_token`` may be None — the token is then resolved from the
        stored IntegrationToken for ``workspace_id`` (unified OAuth flow).
        """
        token = self._resolve_token(access_token)
        if not token:
            token = await self.get_access_token(workspace_id)
        if not token:
            return {"success": False, "error": "No Box access token. Connect the integration first."}

        files = await self.walk_files(token)

        ingested = 0
        skipped: list[str] = []
        errors: list[str] = []
        for f in files:
            name = f.get("name", "") or ""
            try:
                meta = {
                    "folder_path": f.get("path") or "",
                    "modified_at": f.get("modified_at") or "",
                }
                res = await self.ingest_file_to_memory(access_token, f.get("id"), extra_metadata=meta)
                inner = res.get("result") or {}
                if res.get("success") and inner.get("status") == "ingested":
                    ingested += 1
                elif res.get("error"):
                    errors.append(f"{name}: {res['error']}")
                else:
                    skipped.append(f"{name} ({inner.get('reason') or 'no_text'})")
            except Exception as file_err:
                errors.append(f"{name}: {file_err}")

        cache_result = await self.sync_to_postgres_cache(workspace_id, token)
        return {
            "success": True,
            "workspace_id": workspace_id,
            "files_found": len(files),
            "files_ingested": ingested,
            "files_skipped": skipped,
            "postgres_cache": cache_result,
            "errors": errors,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Module-level singleton (routes import this as box_service)
box_service = BoxService()
