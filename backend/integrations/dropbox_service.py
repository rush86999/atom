
import os
import logging
import asyncio
import sys
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import base64

# The dropbox SDK is OPTIONAL (requirements.txt has it commented out) — the
# OAuth handler (auth_handler_dropbox.py) is SDK-free and always works, so the
# connect/status journey must not crash just because the SDK is absent.
# Guarded like integrations/twitter_routes.py (TWITTER_AVAILABLE): module-level
# import never fails; SDK-dependent methods raise/return a clear error at call
# time. Round 80b: without this guard the registry reported dropbox "not
# available" and /api/dropbox/* 404'd even for SDK-free endpoints.
#
# NOTE: the module-level binding is re-resolved lazily at call time via
# _current_dropbox() — the wave-93 suites inject a fake dropbox SDK into
# sys.modules BEFORE importing this module, and some sessions boot the real
# app first (module cached with dropbox=None), so a static flag would leave
# the fakes inert. sys.modules.get("dropbox") picks up either the real SDK,
# a test fake, or nothing (fallback to the guarded module binding).
try:
    import dropbox
    from dropbox.exceptions import ApiError, AuthError
    _DROPBOX_SDK_AVAILABLE = True
except ImportError:
    dropbox = None  # type: ignore[assignment]
    ApiError = None  # type: ignore[assignment,misc]
    AuthError = None  # type: ignore[assignment,misc]
    _DROPBOX_SDK_AVAILABLE = False


def _current_dropbox() -> Any:
    """Re-resolve the dropbox SDK module (real, test-fake, or None)."""
    return sys.modules.get("dropbox") or dropbox


def _sdk_available() -> bool:
    return _current_dropbox() is not None

from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)

class DropboxService(IntegrationService):
    """Standardized Dropbox API integration service"""

    def __init__(self, tenant_id: str = "default",
                 config: Optional[Dict[str, Any]] = None):
        if config is None:
            config = {}
        super().__init__(tenant_id=tenant_id, config=config)
        self.api_base_url = "https://api.dropboxapi.com/2"
        self.client_id = self.config.get("dropbox_client_id") or os.getenv("DROPBOX_APP_KEY")
        self.client_secret = self.config.get("dropbox_client_secret") or os.getenv("DROPBOX_APP_SECRET")
        self.access_token = self.config.get("access_token")

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "operations": [
                {"id": "list_files", "name": "List Files"},
                {"id": "walk_files", "name": "Walk All Files (Recursive)"},
                {"id": "search_files", "name": "Search Files"},
                {"id": "download_file", "name": "Download File"},
                {"id": "upload_file", "name": "Upload File"},
                {"id": "create_folder", "name": "Create Folder"},
                {"id": "delete_item", "name": "Delete Item"},
                {"id": "ingest_file_to_memory", "name": "Ingest File to ATOM Memory"},
                {"id": "full_sync", "name": "Full Sync"},
                {"id": "get_space_usage", "name": "Get Space Usage"}
            ],
            "required_params": [],
            "rate_limits": {"requests_per_minute": 100},
            "supports_webhooks": True
        }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        try:
            token = parameters.get("access_token") or self.access_token
            if not token:
                return {"success": False, "error": "Missing Dropbox access token"}
            if not _sdk_available():
                return {"success": False, "error": "Dropbox SDK not installed (pip install dropbox)"}
            _dbx_mod = _current_dropbox()

            dbx = _dbx_mod.Dropbox(token)
            
            if operation == "list_files":
                path = parameters.get("path", "")
                res = dbx.files_list_folder(path)
                entries = [{"id": e.id if hasattr(e, "id") else None, "name": e.name, "path": e.path_display, "type": "folder" if isinstance(e, _dbx_mod.files.FolderMetadata) else "file"} for e in res.entries]
                return {"success": True, "result": {"entries": entries, "cursor": res.cursor, "has_more": res.has_more}}
                
            elif operation == "search_files":
                query = parameters.get("query", "")
                res = dbx.files_search_v2(query)
                matches = [{"name": m.metadata.get_metadata().name, "path": m.metadata.get_metadata().path_display} for m in res.matches]
                return {"success": True, "result": {"matches": matches, "has_more": res.has_more}}
                
            elif operation == "get_space_usage":
                res = dbx.users_get_space_usage()
                return {"success": True, "result": {"used": res.used, "allocation": str(res.allocation)}}
                
            else:
                raise NotImplementedError(f"Operation {operation} not supported for Dropbox")
        except Exception as e:
            return {"success": False, "error": str(e)}

    def health_check(self) -> Dict[str, Any]:
        """Synchronous health check for Dropbox service"""
        try:
            is_healthy = bool(self.access_token or self.client_id)
            return {
                "ok": is_healthy,
                "status": "healthy" if is_healthy else "unhealthy",
                "healthy": is_healthy,
                "service": "dropbox",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
            return {"ok": False, "status": "unhealthy", "healthy": False, "service": "dropbox", "error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}

    # ─────────────────────────────────────────────────────────────────────────
    # Direct operation methods (wave 93) — dropbox_routes.py calls these with
    # an explicit access_token (resolved via DropboxAuthHandler). All were
    # MISSING from the service, so every route 500'd with AttributeError.
    # Implemented with the dropbox SDK in the same style as execute_operation;
    # errors propagate to the route layer (which maps them to 500).
    # ─────────────────────────────────────────────────────────────────────────

    def _get_dropbox_client(self, access_token: Optional[str]) -> Any:
        """Build a dropbox SDK client for the given access token."""
        _dbx_mod = _current_dropbox()
        if _dbx_mod is None:
            raise RuntimeError("Dropbox SDK not installed (pip install dropbox)")
        if not access_token:
            raise ValueError("No Dropbox access token available")
        return _dbx_mod.Dropbox(access_token)

    def _metadata_to_dict(self, entry: Any) -> Dict[str, Any]:
        """Convert a FileMetadata/FolderMetadata entry to a plain dict."""
        data: Dict[str, Any] = {
            "id": entry.id,
            "name": entry.name,
            "path": entry.path_display,
            "path_lower": entry.path_lower,
        }
        _dbx_mod = _current_dropbox()
        if _dbx_mod and isinstance(entry, _dbx_mod.files.FolderMetadata):
            data[".tag"] = "folder"
            data["shared_folder_id"] = getattr(entry, "shared_folder_id", None)
        elif "FolderMetadata" in type(entry).__name__:
            # SDK-less environments (tests, partial installs) still tag folders.
            data[".tag"] = "folder"
        else:
            data[".tag"] = "file"
            data["size"] = getattr(entry, "size", None)
            data["rev"] = getattr(entry, "rev", None)
            data["is_downloadable"] = getattr(entry, "is_downloadable", True)
            data["content_hash"] = getattr(entry, "content_hash", None)
            # Update-detection input: the funnel stamps this as the
            # freshness baseline so source-side edits trigger re-ingest.
            data["server_modified"] = str(
                getattr(entry, "server_modified", None) or ""
            )
        return data

    async def list_folder(
        self,
        path: str = "",
        access_token: Optional[str] = None,
        recursive: bool = False,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List files and folders in a path (wave 93).

        Follows the list_folder cursor until has_more is False so large
        folders are not truncated to the first page.
        """
        dbx = self._get_dropbox_client(access_token)
        entries: List[Any] = []
        result = dbx.files_list_folder(path, recursive=recursive, limit=limit)
        entries.extend(result.entries)
        while result.has_more:
            result = dbx.files_list_folder_continue(result.cursor)
            entries.extend(result.entries)
        return [self._metadata_to_dict(e) for e in entries]

    async def walk_files(
        self,
        access_token: Optional[str] = None,
        path: str = "",
        max_depth: int = 25,
    ) -> List[Dict[str, Any]]:
        """Recursively list every file under ``path`` with its folder path.

        Uses Dropbox's native recursive listing (server-side recursion), then
        stamps ``folder_path`` from each entry's own path_display. Depth is
        enforced locally as a safety cap.
        """
        entries = await self.list_folder(
            path=path, access_token=access_token, recursive=True, limit=500
        )
        out: List[Dict[str, Any]] = []
        for entry in entries:
            if entry.get(".tag") != "file":
                continue
            full = entry.get("path") or f"/{entry.get('name', '')}"
            if full.count("/") - 1 > max_depth:
                continue
            entry["folder_path"] = full.rsplit("/", 1)[0]
            out.append(entry)
        return out

    async def ingest_file_to_memory(
        self,
        path: str,
        access_token: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Download a file and process it through the ingestion pipeline.

        Every file type is attempted; the parser chain decides what is
        extractable and skips gracefully otherwise.
        """
        try:
            content = await self.download_file(path, access_token)
        except Exception as e:
            return {"success": False, "error": f"Failed to download file: {e}"}

        try:
            file_name = path.rsplit("/", 1)[-1] or "unknown"
            from core.auto_document_ingestion import AutoDocumentIngestionService
            ingestor = AutoDocumentIngestionService()
            result = await ingestor.process_file_bytes(
                content,
                file_name=file_name,
                source="dropbox",
                user_id=self.tenant_id,
                extra_metadata=extra_metadata,
                external_id=path,  # Dropbox identity: full path
            )
            # Shared semantics (core.auto_document_ingestion): unchanged
            # re-ingests are success no-ops; unsupported formats and write
            # failures must NOT be masked as success.
            from core.auto_document_ingestion import interpret_ingest_result
            return {**interpret_ingest_result(result), "result": result}
        except Exception as e:
            logger.error(f"Failed to ingest Dropbox file {path}: {e}")
            return {"success": False, "error": str(e)}

    async def full_sync(self, workspace_id: str, access_token: Optional[str] = None) -> Dict[str, Any]:
        """Ingest every file (all types, all subfolders) into Atom memory.

        Mirrors the OneDrive/Google Drive/Zoho WorkDrive full syncs: walk the
        full tree, attempt every file, stamp folder-path context into the
        memory metadata.
        """
        files = await self.walk_files(access_token=access_token)

        ingested = 0
        skipped: list[str] = []
        errors: list[str] = []
        for f in files:
            name = f.get("name", "") or ""
            path = f.get("path") or f"/{name}"
            try:
                meta = {
                    "folder_path": f.get("folder_path") or "",
                    # Update-detection baseline (same key WorkDrive/Box/
                    # OneDrive/GDrive walkers pass; the funnel parses it).
                    "modified_at": f.get("server_modified") or "",
                }
                res = await self.ingest_file_to_memory(path, access_token, extra_metadata=meta)
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
            "success": True,
            "workspace_id": workspace_id,
            "files_found": len(files),
            "files_ingested": ingested,
            "files_skipped": skipped,
            "errors": errors,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def upload_file(
        self,
        path: str,
        file_content: bytes,
        access_token: Optional[str] = None,
        autorename: bool = True,
    ) -> Dict[str, Any]:
        """Upload file bytes to Dropbox (wave 93)."""
        dbx = self._get_dropbox_client(access_token)
        result = dbx.files_upload(
            file_content, path,
            mode=_current_dropbox().files.WriteMode.overwrite, autorename=autorename,
        )
        return self._metadata_to_dict(result)

    async def download_file(
        self, path: str, access_token: Optional[str] = None
    ) -> bytes:
        """Download a file from Dropbox, returning raw bytes (wave 93)."""
        dbx = self._get_dropbox_client(access_token)
        _metadata, response = dbx.files_download(path)
        content: bytes = response.content
        return content

    async def search(
        self,
        query: str,
        access_token: Optional[str] = None,
        path: str = "",
        max_results: int = 50,
        file_extensions: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Search files in Dropbox (wave 93)."""
        dbx = self._get_dropbox_client(access_token)
        options = _current_dropbox().files.SearchOptions(
            path=path, max_results=max_results,
            file_extensions=file_extensions)
        result = dbx.files_search_v2(query, options=options)
        matches = []
        for match in result.matches:
            metadata = match.metadata
            if hasattr(metadata, "get_metadata"):
                metadata = metadata.get_metadata()
            if metadata is not None:
                matches.append(self._metadata_to_dict(metadata))
        return matches

    async def create_folder(
        self, path: str, access_token: Optional[str] = None, autorename: bool = True
    ) -> Dict[str, Any]:
        """Create a folder in Dropbox (wave 93)."""
        dbx = self._get_dropbox_client(access_token)
        result = dbx.files_create_folder_v2(path, autorename=autorename)
        return self._metadata_to_dict(result.metadata)

    async def delete_item(
        self, path: str, access_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete a file or folder from Dropbox (wave 93)."""
        dbx = self._get_dropbox_client(access_token)
        result = dbx.files_delete_v2(path)
        return self._metadata_to_dict(result.metadata)

    async def move_item(
        self,
        from_path: str,
        to_path: str,
        access_token: Optional[str] = None,
        autorename: bool = True,
        allow_ownership_transfer: bool = False,
    ) -> Dict[str, Any]:
        """Move a file or folder in Dropbox (wave 93)."""
        dbx = self._get_dropbox_client(access_token)
        result = dbx.files_move_v2(
            from_path, to_path, autorename=autorename,
            allow_ownership_transfer=allow_ownership_transfer)
        return self._metadata_to_dict(result.metadata)

    async def copy_item(
        self,
        from_path: str,
        to_path: str,
        access_token: Optional[str] = None,
        autorename: bool = True,
        allow_ownership_transfer: bool = False,
    ) -> Dict[str, Any]:
        """Copy a file or folder in Dropbox (wave 93)."""
        dbx = self._get_dropbox_client(access_token)
        result = dbx.files_copy_v2(
            from_path, to_path, autorename=autorename,
            allow_ownership_transfer=allow_ownership_transfer)
        return self._metadata_to_dict(result.metadata)

    async def create_shared_link(
        self,
        path: str,
        access_token: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a shared link for a file or folder (wave 93)."""
        dbx = self._get_dropbox_client(access_token)
        link_settings = None
        if settings:
            link_settings = _current_dropbox().sharing.SharedLinkSettings(**settings)
        result = dbx.sharing_create_shared_link_with_settings(
            path, link_settings)
        return {
            "url": result.url,
            "name": result.name,
            "path": result.path_lower,
            "preview_type": getattr(result, "preview_type", None),
        }

    async def get_account_info(
        self, access_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get the connected Dropbox account profile (wave 93)."""
        dbx = self._get_dropbox_client(access_token)
        result = dbx.users_get_current_account()
        name = getattr(result, "name", None)
        return {
            "account_id": result.account_id,
            "email": result.email,
            "email_verified": result.email_verified,
            "name": {
                "given_name": getattr(name, "given_name", None),
                "surname": getattr(name, "surname", None),
                "display_name": getattr(name, "display_name", None),
            },
            "country": getattr(result, "country", None),
            "locale": getattr(result, "locale", None),
            "referral_link": getattr(result, "referral_link", None),
        }

    async def get_space_usage(
        self, access_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get the connected Dropbox account space usage (wave 93)."""
        dbx = self._get_dropbox_client(access_token)
        result = dbx.users_get_space_usage()
        allocation = getattr(result, "allocation", None)
        return {
            "used": result.used,
            "allocation": allocation.to_dict()
            if allocation and hasattr(allocation, "to_dict")
            else str(allocation),
        }

    async def get_metadata(
        self, path: str, access_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get metadata for a single file or folder (wave 93)."""
        dbx = self._get_dropbox_client(access_token)
        result = dbx.files_get_metadata(path)
        return self._metadata_to_dict(result)


# Global singleton — dropbox_routes.py imports this name (wave 93: the
# singleton was missing, so the routes module could not even import).
dropbox_service = DropboxService()
