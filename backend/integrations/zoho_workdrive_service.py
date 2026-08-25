import os
import json
import asyncio
import logging
import httpx
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from core.database import SessionLocal
from core.connection_service import connection_service
from core.models import IntegrationMetric
from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)

# Parseable file extensions for auto-ingestion
PARSEABLE_EXTS = (".docx", ".xlsx", ".xls", ".csv", ".pdf", ".txt", ".md", ".pptx")

class ZohoWorkDriveService(IntegrationService):
    """
    Zoho WorkDrive Service
    Handles file listing, downloading, and ingestion from Zoho WorkDrive.
    """

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
            response = await self.client.get(f"{self.base_url}/teams", headers=headers)
            response.raise_for_status()
            data = response.json()

            teams = []
            for item in data.get("data", []):
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

            if not teams:
                # GET /teams can be empty for users who are plain members of
                # their org's team (no admin/owner role). Fall back to the
                # org team id advertised on /users/me and fetch it directly.
                me_res = await self.client.get(f"{self.base_url}/users/me", headers=headers)
                if me_res.status_code == 200:
                    me_attrs = me_res.json().get("data", {}).get("attributes", {})
                    tid = me_attrs.get("preferred_team_id")
                    if tid:
                        team_res = await self.client.get(f"{self.base_url}/teams/{tid}", headers=headers)
                        if team_res.status_code == 200:
                            tdata = team_res.json().get("data", {})
                            tattrs = tdata.get("attributes", {})
                            teams.append(
                                {
                                    "id": tdata.get("id") or tid,
                                    "name": tattrs.get("name") or tid,
                                    "type": tdata.get("type", "teams"),
                                    "status": tattrs.get("status") or tattrs.get("shared_status"),
                                    "role": tattrs.get("role_id"),
                                }
                            )
            return teams
        except Exception as e:
            logger.error(f"Failed to list Zoho WorkDrive teams: {e}")
            return []

    async def get_team_folders(self, user_id: str, team_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all team folders across teams (or specific team).

        Returns normalized list: {id, name, team_id, team_name, workspace_id, type}
        """
        token = await self.get_access_token(user_id)
        if not token:
            logger.warning("get_team_folders: No access token for user %s", user_id)
            return []

        try:
            headers = {"Authorization": f"Zoho-oauthtoken {token}"}

            # 1. Get teams (or use provided team_id)
            teams_to_query = []
            if team_id:
                teams_to_query = [{"id": team_id}]
            else:
                teams_res = await self.client.get(f"{self.base_url}/teams", headers=headers)
                logger.debug(f"GET /teams -> {teams_res.status_code}")
                if teams_res.status_code != 200:
                    logger.warning(f"GET /teams failed: {teams_res.status_code} - {teams_res.text[:200]}")
                    return []
                teams_to_query = teams_res.json().get("data", [])
                logger.debug(f"Found {len(teams_to_query)} teams")
                if not teams_to_query:
                    # Plain members may be absent from /teams — fall back to
                    # the org team id advertised on /users/me.
                    me_res = await self.client.get(f"{self.base_url}/users/me", headers=headers)
                    if me_res.status_code == 200:
                        me_attrs = me_res.json().get("data", {}).get("attributes", {})
                        tid = me_attrs.get("preferred_team_id")
                        if tid:
                            teams_to_query = [{"id": tid}]
                            logger.debug("Fell back to preferred_team_id %s from /users/me", tid)

            all_folders = []
            for team in teams_to_query:
                t_id = team.get("id")
                t_name = team.get("attributes", {}).get("name") or team.get("attributes", {}).get("display_name", t_id)

                # 2. Get team folders for this team
                tf_res = await self.client.get(
                    f"{self.base_url}/teams/{t_id}/teamfolders",
                    headers=headers
                )
                logger.debug(f"GET /teams/{t_id}/teamfolders -> {tf_res.status_code}")
                if tf_res.status_code != 200:
                    logger.warning(f"Failed to get teamfolders for team {t_id}: {tf_res.status_code} - {tf_res.text[:300]}")
                    # If 403/401, likely missing scope - log clearly
                    if tf_res.status_code in (401, 403):
                        logger.error("Team folders access denied - check OAuth scopes: WorkDrive.teamfolders.READ required")
                    continue

                tf_data = tf_res.json()
                for item in tf_data.get("data", []):
                    attrs = item.get("attributes", {})
                    workspace = attrs.get("workspace", {})
                    ws_id = workspace.get("id") if isinstance(workspace, dict) else None
                    all_folders.append({
                        "id": item.get("id"),
                        "name": attrs.get("name") or attrs.get("display_name", "Unnamed"),
                        "team_id": t_id,
                        "team_name": t_name,
                        "workspace_id": ws_id,
                        "type": "teamfolder",
                        "description": attrs.get("description"),
                        "created_time": attrs.get("created_time"),
                        "modified_time": attrs.get("modified_time"),
                    })

            logger.info(f"Found {len(all_folders)} team folders across {len(teams_to_query)} teams")
            return all_folders
        except Exception as e:
            logger.error(f"Failed to list Zoho WorkDrive team folders: {e}")
            return []

    async def list_files(self, user_id: str, parent_id: str = "root",
                         team_id: Optional[str] = None,
                         workspace_id: Optional[str] = None,
                         recursive: bool = False) -> List[Dict[str, Any]]:
        """List files in a specific folder, workspace, or team folder.

        Args:
            parent_id: Folder ID, or "root" for workspace root
            team_id: Explicit team ID (browses that team's root workspace)
            workspace_id: Explicit workspace ID (personal or team workspace)
            recursive: If True, recursively list all files in subfolders
        """
        token = await self.get_access_token(user_id)
        if not token:
            return []

        try:
            headers = {
                "Authorization": f"Zoho-oauthtoken {token}",
                "Accept": "application/vnd.api+json",
            }

            target_url = None

            # Explicit workspace takes priority (covers both personal and team workspaces)
            if workspace_id:
                target_url = f"{self.base_url}/workspaces/{workspace_id}/files"
            # Explicit team_id: fetch that team's root workspace
            elif team_id:
                if parent_id and parent_id != "root":
                    # parent_id is a team folder id — list its files directly.
                    target_url = f"{self.base_url}/teamfolders/{parent_id}/files"
                else:
                    # GET /teams/{team_id} -> get workspace_id from team's root workspace
                    team_res = await self.client.get(f"{self.base_url}/teams/{team_id}", headers=headers)
                    if team_res.status_code == 200:
                        team_data = team_res.json().get("data", {})
                        attrs = team_data.get("attributes", {})
                        root_ws = attrs.get("root_workspace", {})
                        ws_id = root_ws.get("id") if isinstance(root_ws, dict) else None
                        if ws_id:
                            target_url = f"{self.base_url}/workspaces/{ws_id}/files"
            # parent_id is "root" or folder ID
            elif not parent_id or parent_id == "root":
                # Default to user's private workspace
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

            # Fallback: parent_id as folder/files
            if not target_url:
                target_url = f"{self.base_url}/files/{parent_id}/files"

            response = await self.client.get(target_url, headers=headers)

            # If /files/{parent_id}/files returns 404/400, try /workspaces/{parent_id}/files as fallback
            if response.status_code in (400, 404) and parent_id != "root":
                ws_fallback_url = f"{self.base_url}/workspaces/{parent_id}/files"
                fallback_res = await self.client.get(ws_fallback_url, headers=headers)
                if fallback_res.status_code == 200:
                    response = fallback_res

            response.raise_for_status()
            data = response.json()

            files = []
            for item in data.get("data", []):
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

            # Recursive traversal if requested. Subfolders are always regular
            # folders (even inside team folders / workspaces), so recurse with
            # plain parent_id — dropping team_id/workspace_id prevents routing
            # subfolders to the teamfolders/workspaces endpoints.
            if recursive:
                all_files = list(files)
                for f in files:
                    if f.get("type") == "folder":
                        subfiles = await self.list_files(
                            user_id, parent_id=f["id"], recursive=True
                        )
                        all_files.extend(subfiles)
                return all_files

            return files
        except Exception as e:
            logger.error(f"Failed to list Zoho WorkDrive files: {e}")
            return []

    async def get_folder_tree(self, user_id: str,
                               workspace_id: Optional[str] = None,
                               team_id: Optional[str] = None,
                               max_depth: int = 10) -> Dict[str, Any]:
        """Get full folder tree structure for a workspace/team.

        Returns nested folder structure: {id, name, type: 'folder', children: [...], file_count}
        """
        token = await self.get_access_token(user_id)
        if not token:
            return {"id": "root", "name": "Root", "type": "folder", "children": [], "error": "No access token"}

        try:
            headers = {
                "Authorization": f"Zoho-oauthtoken {token}",
                "Accept": "application/vnd.api+json",
            }

            # Resolve workspace URL
            target_url = None
            if workspace_id:
                target_url = f"{self.base_url}/workspaces/{workspace_id}/files"
            elif team_id:
                team_res = await self.client.get(f"{self.base_url}/teams/{team_id}", headers=headers)
                if team_res.status_code == 200:
                    team_data = team_res.json().get("data", {})
                    attrs = team_data.get("attributes", {})
                    root_ws = attrs.get("root_workspace", {})
                    ws_id = root_ws.get("id") if isinstance(root_ws, dict) else None
                    if ws_id:
                        target_url = f"{self.base_url}/workspaces/{ws_id}/files"
            else:
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
                return {"id": "root", "name": "Root", "type": "folder", "children": [], "error": "Could not resolve workspace"}

            # Build tree recursively
            async def build_tree(folder_id: str, depth: int) -> Dict[str, Any]:
                if depth > max_depth:
                    return {"id": folder_id, "name": "..." if depth > 0 else "Root", "type": "folder", "children": [], "truncated": True}

                # Get folder contents
                if folder_id == "root":
                    url = target_url
                else:
                    url = f"{self.base_url}/files/{folder_id}/files"

                resp = await self.client.get(url, headers=headers)
                if resp.status_code in (400, 404) and folder_id != "root":
                    fallback = f"{self.base_url}/workspaces/{folder_id}/files"
                    fb = await self.client.get(fallback, headers=headers)
                    if fb.status_code == 200:
                        resp = fb

                if resp.status_code != 200:
                    return {"id": folder_id, "name": "Error", "type": "folder", "children": [], "error": f"HTTP {resp.status_code}"}

                data = resp.json()
                node = {
                    "id": folder_id if folder_id != "root" else target_url.split("/")[-2],
                    "name": "Root" if folder_id == "root" else "Folder",
                    "type": "folder",
                    "children": [],
                    "file_count": 0
                }

                # Get name for non-root
                if folder_id != "root":
                    meta_resp = await self.client.get(f"{self.base_url}/files/{folder_id}", headers=headers)
                    if meta_resp.status_code == 200:
                        meta = meta_resp.json().get("data", {}).get("attributes", {})
                        node["name"] = meta.get("name") or meta.get("display_name") or "Folder"

                for item in data.get("data", []):
                    attrs = item.get("attributes", {})
                    item_type = attrs.get("type", "file")
                    name = attrs.get("name") or attrs.get("display_name", "Untitled")

                    if item_type == "folder":
                        child = await build_tree(item.get("id"), depth + 1)
                        child["name"] = name
                        node["children"].append(child)
                    else:
                        node["file_count"] += 1

                return node

            return await build_tree("root", 0)

        except Exception as e:
            logger.error(f"Failed to build folder tree: {e}")
            return {"id": "root", "name": "Root", "type": "folder", "children": [], "error": str(e)}

    async def download_file(self, user_id: str, file_id: str) -> Optional[bytes]:
        """Download file content from WorkDrive.

        Uses a short-lived client instead of the shared pool: Zoho's
        /download/{id} endpoint redirects to a signed URL and can stall
        indefinitely on a stale keep-alive pooled connection (bytes trickle
        just often enough to defeat httpx's per-read timeout). A fresh
        connection, redirect-following, and a hard total-time cap keep this
        from hanging the request (which previously surfaced as a proxy 500).
        """
        token = await self.get_access_token(user_id)
        if not token:
            return None

        try:
            headers = {"Authorization": f"Zoho-oauthtoken {token}"}
            url = f"{self.base_url}/download/{file_id}"
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True,
            ) as client:
                response = await asyncio.wait_for(
                    client.get(url, headers=headers), timeout=60.0
                )
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Failed to download Zoho WorkDrive file {file_id}: {e}")
            return None

    async def ingest_file_to_memory(self, user_id: str, file_id: str) -> Dict[str, Any]:
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
            )

            if result.get("status") != "ingested":
                # Don't mask skipped/errored parses as success — the UI must
                # tell the user nothing was stored (e.g. unsupported format).
                reason = result.get("reason") or result.get("status") or "unknown"
                logger.warning(f"Ingest skipped for {file_name}: {reason}")
                return {"success": False, "error": f"File not ingested ({reason})"}

            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Failed to ingest Zoho WorkDrive file: {e}")
            return {"success": False, "error": str(e)}

    async def ingest_folder_tree(self, user_id: str,
                                 folder_id: str,
                                 team_id: Optional[str] = None,
                                 workspace_id: Optional[str] = None,
                                 recursive: bool = True,
                                 file_extensions: Tuple[str, ...] = PARSEABLE_EXTS,
                                 max_files: int = 500) -> Dict[str, Any]:
        """Recursively ingest all parseable files in a folder tree.

        Args:
            folder_id: Root folder ID to start ingestion (or "root" for workspace root)
            team_id: Explicit team ID
            workspace_id: Explicit workspace ID
            recursive: If True, traverse subfolders
            file_extensions: Tuple of extensions to ingest
            max_files: Maximum files to ingest (safety cap)

        Returns:
            {success, ingested, errors, files_processed}
        """
        token = await self.get_access_token(user_id)
        if not token:
            return {"success": False, "error": "No Zoho WorkDrive access token. Connect the integration first."}

        try:
            from core.auto_document_ingestion import AutoDocumentIngestionService
            ingestor = AutoDocumentIngestionService()

            ingested = 0
            errors: List[str] = []
            processed = 0

            # Get all files recursively
            all_files = await self.list_files(
                user_id, parent_id=folder_id, team_id=team_id,
                workspace_id=workspace_id, recursive=recursive
            )

            for f in all_files:
                if processed >= max_files:
                    errors.append(f"Max files limit ({max_files}) reached")
                    break

                if f.get("type") != "file":
                    continue

                name = f.get("name", "") or ""
                if not name.lower().endswith(file_extensions):
                    continue

                try:
                    res = await self.ingest_file_to_memory(user_id, f.get("id"))
                    processed += 1
                    if res.get("success"):
                        ingested += 1
                    elif res.get("error"):
                        errors.append(f"{name}: {res['error']}")
                except Exception as file_err:
                    errors.append(f"{name}: {file_err}")

            return {
                "success": True,
                "folder_id": folder_id,
                "files_processed": processed,
                "files_ingested": ingested,
                "errors": errors,
            }
        except Exception as e:
            logger.error(f"Failed to ingest folder tree: {e}")
            return {"success": False, "error": str(e)}

    async def sync_to_postgres_cache(self, user_id: str) -> Dict[str, Any]:
        """Sync Zoho WorkDrive analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric
            
            files = await self.list_files(user_id)
            file_count = len(files)
            
            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("zoho_workdrive_file_count", file_count, "count"),
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

    async def full_sync(self, user_id: str,
                         workspace_id: Optional[str] = None,
                         team_id: Optional[str] = None,
                         folder_id: Optional[str] = None,
                         recursive: bool = True) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Zoho WorkDrive.

        Pipeline 1: Ingest parseable files into Atom memory (LanceDB + GraphRAG)
        via AutoDocumentIngestionService.
        Pipeline 2: Refresh the Postgres metrics cache.

        Args:
            user_id: User ID
            workspace_id: Explicit workspace ID (personal or team workspace)
            team_id: Explicit team ID
            folder_id: Specific folder ID to sync (with recursive traversal)
            recursive: If True, recursively traverse subfolders
        """
        ws_id = workspace_id or user_id
        
        # Use folder_id as root if provided, otherwise "root"
        root_folder = folder_id or "root"
        
        # List files with new parameters
        files = await self.list_files(
            user_id, parent_id=root_folder, team_id=team_id,
            workspace_id=workspace_id, recursive=recursive
        )
        parseable_exts = (".docx", ".xlsx", ".xls", ".csv", ".pdf", ".txt", ".md", ".pptx")

        ingested = 0
        errors: list[str] = []
        try:
            from core.auto_document_ingestion import AutoDocumentIngestionService

            ingestor = AutoDocumentIngestionService()
            for f in files:
                name = f.get("name", "") or ""
                if not name.lower().endswith(parseable_exts):
                    continue
                try:
                    res = await self.ingest_file_to_memory(user_id, f.get("id"))
                    if res.get("success"):
                        ingested += 1
                    elif res.get("error"):
                        errors.append(f"{name}: {res['error']}")
                except Exception as file_err:
                    errors.append(f"{name}: {file_err}")
        except Exception as e:
            logger.error(f"Zoho WorkDrive memory ingestion failed: {e}")
            errors.append(str(e))

        cache_result = await self.sync_to_postgres_cache(user_id)
        return {
            "success": True,
            "workspace_id": ws_id,
            "team_id": team_id,
            "folder_id": folder_id,
            "recursive": recursive,
            "files_found": len(files),
            "files_ingested": ingested,
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

