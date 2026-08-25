import os
import json
import logging
import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from core.database import SessionLocal
from core.connection_service import connection_service
from core.models import IntegrationMetric
from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)

class ZohoWorkDriveService(IntegrationService):
    """
    Zoho WorkDrive Service
    Handles file listing, downloading, and ingestion from Zoho WorkDrive.
    """

    PAGE_SIZE = 50
    MAX_LIST_ITEMS = 10000
    MAX_WALK_DEPTH = 25

    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        super().__init__(tenant_id=tenant_id, config=config)
        
        # Use regional overrides if present
        accounts_base = os.getenv("ZOHO_ACCOUNTS_BASE") or os.getenv("ZOHO_CRM_ACCOUNTS_URL", "https://accounts.zoho.com")
        accounts_base = accounts_base.rstrip("/")
        workdrive_base = "https://workdrive.zoho.com"
        
        # Region mapping
        if "zohocloud.ca" in accounts_base or ".zoho.ca" in accounts_base:
            workdrive_base = "https://workdrive.zohocloud.ca"
        elif ".zoho.in" in accounts_base:
            workdrive_base = "https://workdrive.zoho.in"
        elif ".zoho.eu" in accounts_base:
            workdrive_base = "https://workdrive.zoho.eu"
        elif ".zoho.com.au" in accounts_base:
            workdrive_base = "https://workdrive.zoho.com.au"
        elif ".zoho.com.cn" in accounts_base:
            workdrive_base = "https://workdrive.zoho.com.cn"
        elif ".zoho.jp" in accounts_base:
            workdrive_base = "https://workdrive.zoho.jp"

        self.base_url = f"{workdrive_base}/api/v1"
        self.accounts_url = f"{accounts_base}/oauth/v2"
        self.client_id = config.get("client_id") or os.getenv("ZOHO_CLIENT_ID")
        self.client_secret = config.get("client_secret") or os.getenv("ZOHO_CLIENT_SECRET")
        self.redirect_uri = config.get("redirect_uri") or os.getenv("ZOHO_REDIRECT_URI")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_access_token(self, user_id: str) -> Optional[str]:
        """Fetch access token for user using ConnectionService"""
        try:
            # Find a zoho_workdrive or generic zoho connection
            connections = connection_service.get_connections(user_id, "zoho_workdrive")
            if not connections:
                connections = connection_service.get_connections(user_id, "zoho")

            if not connections:
                # The unified OAuth connect flow writes IntegrationToken rows,
                # not UserConnection rows — fall back to those (see
                # _integration_token_access_token).
                return await self._integration_token_access_token(user_id)

            # Use the first active connection
            conn_id = connections[0]["id"]
            creds = await connection_service.get_connection_credentials(conn_id, user_id)

            if creds and creds.get("access_token"):
                return creds["access_token"]
            return None
        except Exception as e:
            logger.error(f"Error getting Zoho access token: {e}")
            return None

    async def _integration_token_access_token(self, user_id: str) -> Optional[str]:
        """Fallback token source for the unified OAuth connect flow.

        The v1 OAuth callback writes IntegrationToken rows (provider
        ``zoho_workdrive``, then generic ``zoho``) — it does NOT create
        UserConnection rows. Without this fallback, WorkDrive's file/team
        journeys silently return []/None after the documented connect flow
        while the other three Zoho services work. Mirrors the expiry check +
        refresh used elsewhere so the same auto-refresh behaviour holds."""
        try:
            from core.models import IntegrationToken

            db = SessionLocal()
            try:
                token_record = None
                for provider in ("zoho_workdrive", "zoho"):
                    token_record = (
                        db.query(IntegrationToken)
                        .filter(
                            IntegrationToken.user_id == user_id,
                            IntegrationToken.provider == provider,
                            IntegrationToken.status == "active",
                        )
                        .first()
                    )
                    if token_record:
                        break

                if not token_record:
                    for provider in ("zoho_workdrive", "zoho"):
                        token_record = (
                            db.query(IntegrationToken)
                            .filter(
                                IntegrationToken.provider == provider,
                                IntegrationToken.status == "active",
                            )
                            .first()
                        )
                        if token_record:
                            break

                if not token_record:
                    return None

                from datetime import datetime, timezone, timedelta

                now = datetime.now(timezone.utc)
                expires_at = token_record.expires_at
                if expires_at and expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)

                if not expires_at or expires_at < (now + timedelta(minutes=2)):
                    if token_record.refresh_token:
                        from core.privsec.token_encryption import (
                            decrypt_token,
                            encrypt_token,
                        )

                        refresh_plain = (
                            decrypt_token(token_record.refresh_token, allow_plaintext=True)
                            if token_record.refresh_token
                            else None
                        )
                        new_tokens = await self._refresh(refresh_plain)
                        if new_tokens:
                            token_record.access_token = encrypt_token(new_tokens["access_token"])
                            token_record.expires_at = datetime.now(timezone.utc) + timedelta(
                                seconds=new_tokens.get("expires_in", 3600)
                            )
                            db.commit()
                            return decrypt_token(token_record.access_token, allow_plaintext=True)
                    return None

                from core.privsec.token_encryption import decrypt_token

                return decrypt_token(token_record.access_token, allow_plaintext=True)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error getting Zoho WorkDrive integration token: {e}")
            return None

    async def _refresh(self, refresh_token: Optional[str]) -> Optional[Dict[str, Any]]:
        """Exchange a refresh token for a fresh access token (Zoho OAuth2)."""
        if not refresh_token:
            return None
        try:
            data = {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
            }
            response = await self.client.post(
                f"{self.accounts_url}/token", data=data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to refresh Zoho WorkDrive token: {e}")
            return None

    async def get_teams(self, user_id: str) -> List[Dict[str, Any]]:
        """List WorkDrive teams for the user (Team Folders root).

        Required by the /teams route and the frontend ingestion picker.
        Hits GET /api/v1/teams and normalizes the JSON:API response.
        """
        token = await self.get_access_token(user_id)
        if not token:
            return []

        try:
            headers = {"Authorization": f"Zoho-oauthtoken {token}"}
            teams = []
            offset = 0
            # JSON:API pagination — loop until a page comes back short/empty so
            # large teams are not silently truncated to the first page.
            while True:
                response = await self.client.get(
                    f"{self.base_url}/teams",
                    headers=headers,
                    params={"page[limit]": self.PAGE_SIZE, "page[offset]": offset},
                )
                response.raise_for_status()
                items = response.json().get("data", [])
                for item in items:
                    attrs = item.get("attributes", {})
                    teams.append(
                        {
                            "id": item.get("id"),
                            "name": attrs.get("name") or attrs.get("display_name"),
                            "type": item.get("type", "teams"),
                            "status": attrs.get("status"),
                            "role": attrs.get("role"),
                        }
                    )
                if len(items) < self.PAGE_SIZE or len(teams) >= self.MAX_LIST_ITEMS:
                    break
                offset += self.PAGE_SIZE
            return teams
        except Exception as e:
            logger.error(f"Failed to list Zoho WorkDrive teams: {e}")
            return []

    async def list_files(self, user_id: str, parent_id: str = "root") -> List[Dict[str, Any]]:
        """List files in a specific folder or 'root' (user's private workspace)."""
        token = await self.get_access_token(user_id)
        if not token:
            return []
        
        try:
            headers = {
                "Authorization": f"Zoho-oauthtoken {token}",
                "Accept": "application/vnd.api+json",
            }
            
            target_url = None
            if not parent_id or parent_id == "root":
                # Get user ID from /users/me then fetch private space workspace
                user_res = await self.client.get(f"{self.base_url}/users/me", headers=headers)
                if user_res.status_code == 200:
                    zoho_uid = user_res.json().get("data", {}).get("id")
                    if zoho_uid:
                        ps_res = await self.client.get(f"{self.base_url}/users/{zoho_uid}/privatespace", headers=headers)
                        if ps_res.status_code == 200:
                            ps_data = ps_res.json().get("data", [])
                            if ps_data and len(ps_data) > 0:
                                ws_id = ps_data[0].get("id")
                                target_url = f"{self.base_url}/workspaces/{ws_id}/files"

            if not target_url:
                target_url = f"{self.base_url}/files/{parent_id}/files"

            files = []
            offset = 0
            while True:
                response = await self.client.get(
                    target_url,
                    headers=headers,
                    params={"page[limit]": self.PAGE_SIZE, "page[offset]": offset},
                )

                # If /files/{parent_id}/files returns 404/400, try /workspaces/{parent_id}/files as fallback
                if response.status_code in (400, 404) and parent_id != "root":
                    ws_fallback_url = f"{self.base_url}/workspaces/{parent_id}/files"
                    fallback_res = await self.client.get(
                        ws_fallback_url,
                        headers=headers,
                        params={"page[limit]": self.PAGE_SIZE, "page[offset]": offset},
                    )
                    if fallback_res.status_code == 200:
                        response = fallback_res

                response.raise_for_status()
                data = response.json()

                page_items = data.get("data", [])
                for item in page_items:
                    attrs = item.get("attributes", {})
                    item_type = attrs.get("type", "file")
                    extn = attrs.get("extn") or attrs.get("extension")
                    name = attrs.get("name") or attrs.get("display_name", "Untitled")

                    # Determine file size
                    storage_info = attrs.get("storage_info", {})
                    size = storage_info.get("size_in_bytes") or attrs.get("size") or 0
                    try:
                        size = int(size)
                    except (ValueError, TypeError):
                        size = 0

                    if name == "root" and item_type == "folder":
                        continue

                    files.append({
                        "id": item.get("id"),
                        "name": name,
                        "type": "folder" if item_type == "folder" else "file",
                        "extension": extn,
                        "size": size,
                        "modified_at": attrs.get("modified_time_in_iso8601") or attrs.get("modified_time")
                    })

                if len(page_items) < self.PAGE_SIZE or len(files) >= self.MAX_LIST_ITEMS:
                    break
                offset += self.PAGE_SIZE
            return files
        except Exception as e:
            logger.error(f"Failed to list Zoho WorkDrive files: {e}")
            return []

    async def get_team_folder_ids(self, user_id: str) -> List[str]:
        """Return the IDs of all team folders (shared workspaces) across the
        user's teams. Team folders are the shared-drive counterpart to the
        private workspace and are the usual home of collaborative content."""
        token = await self.get_access_token(user_id)
        if not token:
            return []
        headers = {"Authorization": f"Zoho-oauthtoken {token}"}
        folder_ids: List[str] = []
        try:
            teams = await self.get_teams(user_id)
            for team in teams:
                team_id = team.get("id")
                if not team_id:
                    continue
                offset = 0
                while True:
                    resp = await self.client.get(
                        f"{self.base_url}/teams/{team_id}/teamfolders",
                        headers=headers,
                        params={"page[limit]": self.PAGE_SIZE, "page[offset]": offset},
                    )
                    resp.raise_for_status()
                    items = resp.json().get("data", [])
                    folder_ids.extend(i.get("id") for i in items if i.get("id"))
                    if len(items) < self.PAGE_SIZE:
                        break
                    offset += self.PAGE_SIZE
        except Exception as e:
            logger.warning(f"Failed to list Zoho WorkDrive team folders: {e}")
        return folder_ids

    async def walk_files(
        self,
        user_id: str,
        root_ids: Optional[List[str]] = None,
        max_depth: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Recursively walk WorkDrive and return every file with its folder path.

        Starts at the user's private workspace (and all team folders when
        ``root_ids`` is not given), descending into every subfolder up to
        ``max_depth`` (default MAX_WALK_DEPTH). Each returned entry is a
        ``list_files`` item plus ``path`` (the full folder path) and ``depth``.
        Folder-listing errors on individual branches are logged and skipped so
        one inaccessible folder cannot abort the whole walk.
        """
        max_depth = max_depth if max_depth is not None else self.MAX_WALK_DEPTH
        if root_ids is None:
            root_ids = ["root"] + await self.get_team_folder_ids(user_id)

        seen_folders: set = set()
        out: List[Dict[str, Any]] = []

        async def _walk(folder_id: str, path: str, depth: int, label: str) -> None:
            if folder_id in seen_folders or depth > max_depth:
                return
            seen_folders.add(folder_id)
            try:
                entries = await self.list_files(user_id, folder_id)
            except Exception as e:
                logger.warning(f"WorkDrive walk skipped {label} ({folder_id}): {e}")
                return
            for entry in entries:
                if not entry.get("id"):
                    continue
                if entry.get("type") == "folder":
                    await _walk(entry["id"], f"{path}/{entry.get('name', '')}", depth + 1, label)
                else:
                    entry["path"] = path
                    entry["depth"] = depth
                    entry["root"] = label
                    out.append(entry)

        for rid in root_ids:
            label = "private" if rid == "root" else rid
            await _walk(rid, "", 0, label)
        return out

    async def download_file(self, user_id: str, file_id: str) -> Optional[bytes]:
        """Download file content from WorkDrive"""
        token = await self.get_access_token(user_id)
        if not token:
            return None
        
        try:
            headers = {"Authorization": f"Zoho-oauthtoken {token}"}
            url = f"{self.base_url}/download/{file_id}"
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Failed to download Zoho WorkDrive file {file_id}: {e}")
            return None

    async def ingest_file_to_memory(
        self,
        user_id: str,
        file_id: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Download a file and process it through the ingestion pipeline"""
        token = await self.get_access_token(user_id)
        if not token:
            return {"success": False, "error": "No Zoho WorkDrive access token. Connect the integration first."}

        content = await self.download_file(user_id, file_id)
        if not content:
            return {"success": False, "error": "Failed to download file"}

        try:
            # Fetch file metadata to get the real name (reuse the already-resolved token).
            headers = {"Authorization": f"Zoho-oauthtoken {token}"}
            resp = await self.client.get(f"{self.base_url}/files/{file_id}", headers=headers)
            resp.raise_for_status()
            meta = resp.json().get("data", {}).get("attributes", {})
            file_name = meta.get("name", "unknown")

            from core.auto_document_ingestion import AutoDocumentIngestionService
            ingestor = AutoDocumentIngestionService()

            result = await ingestor.process_file_bytes(
                content,
                file_name=file_name,
                source="zoho_workdrive",
                user_id=user_id,
                extra_metadata=extra_metadata,
                external_id=file_id,
            )

            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Failed to ingest Zoho WorkDrive file: {e}")
            return {"success": False, "error": str(e)}

    async def sync_to_postgres_cache(self, user_id: str) -> Dict[str, Any]:
        """Sync Zoho WorkDrive analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric
            
            files = await self.walk_files(user_id)
            file_count = len(files)
            folder_paths = {f.get("path") or "" for f in files if f.get("path")}
            folder_count = max(len(folder_paths), 0)

            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("zoho_workdrive_file_count", file_count, "count"),
                    ("zoho_workdrive_folder_count", folder_count, "count"),
                ]
                
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        workspace_id=user_id,
                        integration_type="zoho_workdrive",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            workspace_id=user_id,
                            integration_type="zoho_workdrive",
                            metric_key=key,
                            value=float(value),
                            unit=unit
                        )
                        db.add(metric)
                    metrics_synced += 1
                
                db.commit()
            except Exception as e:
                db.rollback()
                return {"success": False, "error": str(e)}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Zoho WorkDrive PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": str(e)}

    async def full_sync(self, user_id: str, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Zoho WorkDrive.

        Pipeline 1: Ingest every file (all types, all subfolders, private
        workspace + team folders) into Atom memory (LanceDB + GraphRAG) via
        AutoDocumentIngestionService. Unparseable/binary files are attempted
        and skipped gracefully rather than filtered out up front, so any file
        type the parsers support (including OCR-able images, code, json) is
        captured.
        Pipeline 2: Refresh the Postgres metrics cache.
        """
        ws_id = workspace_id or user_id
        files = await self.walk_files(user_id)

        ingested = 0
        skipped: list[str] = []
        errors: list[str] = []
        try:
            for f in files:
                name = f.get("name", "") or ""
                try:
                    meta = {
                        "folder_path": f.get("path") or "",
                        "workdrive_root": f.get("root") or "",
                        "modified_at": f.get("modified_at") or "",
                    }
                    res = await self.ingest_file_to_memory(user_id, f.get("id"), extra_metadata=meta)
                    inner = res.get("result") or {}
                    if res.get("success") and inner.get("status") == "ingested":
                        ingested += 1
                    elif res.get("error"):
                        errors.append(f"{name}: {res['error']}")
                    else:
                        skipped.append(f"{name} ({inner.get('reason') or 'no_text'})")
                except Exception as file_err:
                    errors.append(f"{name}: {file_err}")
        except Exception as e:
            logger.error(f"Zoho WorkDrive memory ingestion failed: {e}")
            errors.append(str(e))

        cache_result = await self.sync_to_postgres_cache(user_id)
        return {
            "success": True,
            "workspace_id": ws_id,
            "files_found": len(files),
            "files_ingested": ingested,
            "files_skipped": skipped,
            "postgres_cache": cache_result,
            "errors": errors,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # -------------------------------------------------------------------------
    # IntegrationService abstract-method implementations
    # -------------------------------------------------------------------------
    def get_capabilities(self) -> Dict[str, Any]:
        """Return the capabilities of the Zoho WorkDrive service."""
        return {
            "operations": [
                {"id": "list_files", "name": "List Files"},
                {"id": "walk_files", "name": "Walk All Files (Recursive)"},
                {"id": "download_file", "name": "Download File"},
                {"id": "ingest_file_to_memory", "name": "Ingest File to Memory"},
                {"id": "get_teams", "name": "Get Teams"},
                {"id": "full_sync", "name": "Full Sync"},
            ],
            "required_params": ["access_token"],
            "rate_limits": {"requests_per_minute": 100},
            "supports_webhooks": False,
        }

    async def health_check(self) -> Dict[str, Any]:
        """Check if the Zoho WorkDrive service is healthy."""
        return {
            "healthy": True,
            "status": "healthy",
            "service": "zoho_workdrive",
            "message": "Zoho WorkDrive service is operational",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a Zoho WorkDrive operation."""
        operations = {
            "list_files": self.list_files,
            "walk_files": self.walk_files,
            "download_file": self.download_file,
            "ingest_file_to_memory": self.ingest_file_to_memory,
            "get_teams": self.get_teams,
            "full_sync": self.full_sync,
        }
        if operation not in operations:
            return {"success": False, "error": f"Unknown operation: {operation}"}
        try:
            user_id = (context or {}).get("user_id") or parameters.get("user_id") or self.tenant_id
            fn = operations[operation]
            result = await fn(user_id, **{k: v for k, v in parameters.items() if k != "user_id"})
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Zoho WorkDrive operation {operation} failed: {e}")
            return {"success": False, "error": str(e)}


# Create a default instance for hub_sync_service compatibility
zoho_workdrive_service = ZohoWorkDriveService("default", {})

