import os
import json
import asyncio
import logging
import time
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

    PAGE_SIZE = 50
    MAX_LIST_ITEMS = 10000
    MAX_WALK_DEPTH = 25
    # Pacing/backoff for the Zoho REST API (see _zoho_get). ~3 req/s keeps a
    # full-tree walk under Zoho's per-DC throttle instead of 429ing it.
    _MIN_API_INTERVAL_SECONDS = 0.35
    _MAX_429_RETRIES = 4
    # Global caps for client-triggered recursive traversal — bound request
    # latency and upstream API calls on large drives.
    MAX_RECURSIVE_ITEMS = 2000
    MAX_TREE_NODES = 1000

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
        # Client-side pacing + 429 bookkeeping for the shared client (see
        # _zoho_get): Zoho throttles per-DC traffic hard, and an unpaced
        # full-tree walk got every listing 429'd into uselessness.
        self._last_zoho_request_at = 0.0
        # One-shot full-sync guard: a second concurrent walk just doubles the
        # API pressure (and 429s the first one).
        self._full_sync_running: set = set()

    async def _zoho_get(self, url: str, *, headers: Dict[str, str],
                        params: Optional[Dict[str, Any]] = None):
        """GET a WorkDrive API URL with pacing and 429 backoff.

        Spaces requests at least _MIN_API_INTERVAL_SECONDS apart and, on 429,
        retries up to _MAX_429_RETRIES times honoring Retry-After (falling
        back to exponential backoff capped at 30s).
        """
        attempt = 0
        while True:
            gap = time.monotonic() - self._last_zoho_request_at
            if gap < self._MIN_API_INTERVAL_SECONDS:
                await asyncio.sleep(self._MIN_API_INTERVAL_SECONDS - gap)
            self._last_zoho_request_at = time.monotonic()
            response = await self.client.get(url, headers=headers, params=params)
            if response.status_code == 429 and attempt < self._MAX_429_RETRIES:
                raw_retry_after = (response.headers.get("Retry-After") or "").strip()
                try:
                    delay = min(float(raw_retry_after), 60.0) if raw_retry_after else min(2.0 ** attempt, 30.0)
                except ValueError:
                    delay = min(2.0 ** attempt, 30.0)
                logger.warning(
                    f"Zoho WorkDrive 429 for {url} — backing off {delay:.1f}s "
                    f"(attempt {attempt + 1}/{self._MAX_429_RETRIES})"
                )
                attempt += 1
                await asyncio.sleep(delay)
                continue
            return response

    def is_full_sync_running(self, user_id: str) -> bool:
        return user_id in self._full_sync_running

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
                    # No cross-user fallback: any active token would serve one
                    # user's WorkDrive to every authenticated user. No row for
                    # THIS user means not connected.
                    return None

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
        Hits GET /api/v1/teams and normalizes the JSON:API response. When the
        listing comes back empty (plain org members without admin/owner role),
        falls back to the org team advertised on /users/me.
        """
        token = await self.get_access_token(user_id)
        if not token:
            return []

        try:
            headers = {"Authorization": f"Zoho-oauthtoken {token}"}
            teams: List[Dict[str, Any]] = []
            # The /teams listing itself can 500 (F7007) when the client lacks
            # WorkDrive.teams.* — that must NOT kill the picker: fall back to
            # the scope-free /users/me org-team id below.
            try:
                offset = 0
                while True:
                    response = await self.client.get(
                        f"{self.base_url}/teams",
                        headers=headers,
                        params={"page[limit]": self.PAGE_SIZE, "page[offset]": offset},
                    )
                    response.raise_for_status()
                    items = response.json().get("data", [])
                    for item in items:
                        teams.append(self._team_from_jsonapi(item))
                    if len(items) < self.PAGE_SIZE or len(teams) >= self.MAX_LIST_ITEMS:
                        break
                    offset += self.PAGE_SIZE
            except Exception as e:
                # Deliberate degradation, not a bug: if a LATER page fails
                # after earlier pages parsed, the partial team list is kept
                # (real teams beat the single org-team fallback) and only the
                # warning below marks the truncation.
                logger.warning(f"GET /teams listing failed ({e}); using org-team fallback")

            if not teams:
                await self._append_org_team_fallback(headers, teams)
            return teams
        except Exception as e:
            logger.error(f"Failed to list Zoho WorkDrive teams: {e}")
            return []

    @staticmethod
    def _team_from_jsonapi(item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize one JSON:API team resource into the picker's team dict."""
        attrs = item.get("attributes", {})
        return {
            "id": item.get("id"),
            "name": attrs.get("name") or attrs.get("display_name"),
            "type": item.get("type", "teams"),
            "status": attrs.get("status"),
            "role": attrs.get("role"),
        }

    async def _append_org_team_fallback(
        self, headers: Dict[str, str], teams: List[Dict[str, Any]]
    ) -> None:
        """Fetch the org team directly when GET /teams lists nothing.

        GET /teams can be empty for users who are plain members of their
        org's team (no admin/owner role). /users/me advertises that team via
        ``preferred_team_id``; fetch it and append it so the picker still
        shows something usable. Failures log a warning and leave ``teams``
        untouched — never raises.
        """
        try:
            me_res = await self.client.get(f"{self.base_url}/users/me", headers=headers)
            if me_res.status_code != 200:
                logger.warning(
                    "Zoho WorkDrive /users/me returned %s; org-team fallback unavailable",
                    me_res.status_code,
                )
                return
            me_attrs = me_res.json().get("data", {}).get("attributes", {})
            tid = me_attrs.get("preferred_team_id")
            if not tid:
                logger.warning(
                    "Zoho WorkDrive /users/me has no preferred_team_id; "
                    "org-team fallback unavailable"
                )
                return

            team_res = await self.client.get(
                f"{self.base_url}/teams/{tid}", headers=headers
            )
            if team_res.status_code != 200:
                # /teams/{id} needs WorkDrive.teams.* (often not granted on
                # the client) — the id alone is enough for the teamfolders
                # listing, so append an id-only entry instead of giving up.
                logger.warning(
                    "Zoho WorkDrive org-team detail for %s returned %s; "
                    "using id-only entry",
                    tid,
                    team_res.status_code,
                )
                teams.append(
                    {
                        "id": tid,
                        "name": "WorkDrive Team",
                        "type": "teams",
                        "status": None,
                        "role": None,
                    }
                )
                return
            tdata = team_res.json().get("data", {})
            tattrs = tdata.get("attributes", {})
            # Deliberately NOT _team_from_jsonapi: the single-team GET /teams/:id
            # response uses different attribute names than the /teams listing
            # (role_id vs role, shared_status as the status fallback). Do not
            # "deduplicate" this into the listing mapper.
            teams.append(
                {
                    "id": tdata.get("id") or tid,
                    "name": tattrs.get("name") or tid,
                    "type": tdata.get("type", "teams"),
                    "status": tattrs.get("status") or tattrs.get("shared_status"),
                    "role": tattrs.get("role_id"),
                }
            )
        except Exception as e:
            logger.warning(f"Zoho WorkDrive org-team fallback failed: {e}")

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
                teams_to_query = []
                try:
                    teams_res = await self.client.get(f"{self.base_url}/teams", headers=headers)
                    logger.debug(f"GET /teams -> {teams_res.status_code}")
                    if teams_res.status_code == 200:
                        teams_to_query = teams_res.json().get("data", [])
                        logger.debug(f"Found {len(teams_to_query)} teams")
                except Exception as e:
                    logger.warning(f"GET /teams failed: {e}")
                if not teams_to_query:
                    # /teams 500s with F7007 when the client lacks
                    # WorkDrive.teams.* (or lists nothing for plain members) —
                    # the org team id on /users/me needs NO teams scope and
                    # teamfolders listing only needs teamfolders.ALL.
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

            # A team folder (team_id + parent_id that is a team folder id) is
            # the precise scope and wins over workspace_id — the UI sends both
            # for a team folder, and /workspaces/{id}/files would otherwise
            # replace the selected folder's file set with the workspace root.
            if team_id and parent_id and parent_id != "root":
                # parent_id is a team folder id — list its files directly.
                target_url = f"{self.base_url}/teamfolders/{parent_id}/files"
            # Explicit workspace (personal or team workspace root)
            elif workspace_id:
                target_url = f"{self.base_url}/workspaces/{workspace_id}/files"
            # Explicit team_id: fetch that team's root workspace
            elif team_id:
                # GET /teams/{team_id} -> get workspace_id from team's root workspace
                team_res = await self._zoho_get(f"{self.base_url}/teams/{team_id}", headers=headers)
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
                user_res = await self._zoho_get(f"{self.base_url}/users/me", headers=headers)
                if user_res.status_code == 200:
                    zoho_uid = user_res.json().get("data", {}).get("id")
                    if zoho_uid:
                        ps_res = await self._zoho_get(f"{self.base_url}/users/{zoho_uid}/privatespace", headers=headers)
                        if ps_res.status_code == 200:
                            ps_data = ps_res.json().get("data", [])
                            if ps_data and len(ps_data) > 0:
                                ws_id = ps_data[0].get("id")
                                target_url = f"{self.base_url}/workspaces/{ws_id}/files"

            # Fallback: parent_id as folder/files
            if not target_url:
                target_url = f"{self.base_url}/files/{parent_id}/files"


            files = []
            offset = 0
            while True:
                response = await self._zoho_get(
                    target_url,
                    headers=headers,
                    params={"page[limit]": self.PAGE_SIZE, "page[offset]": offset},
                )

                # If /files/{parent_id}/files returns 404/400, try /workspaces/{parent_id}/files as fallback
                if response.status_code in (400, 404) and parent_id != "root":
                    ws_fallback_url = f"{self.base_url}/workspaces/{parent_id}/files"
                    fallback_res = await self._zoho_get(
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

            # Recursive traversal if requested. Subfolders are always regular
            # folders (even inside team folders / workspaces), so recurse with
            # plain parent_id — dropping team_id/workspace_id prevents routing
            # subfolders to the teamfolders/workspaces endpoints. The budget
            # caps TOTAL items across the whole recursion, not per folder, so
            # a deep tree can't fan out into unbounded sequential API calls.
            if recursive:
                all_files = list(files)
                for f in files:
                    if len(all_files) >= self.MAX_RECURSIVE_ITEMS:
                        logger.warning(
                            "Recursive listing hit cap of %s items; truncating",
                            self.MAX_RECURSIVE_ITEMS,
                        )
                        break
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

    async def search_files(self, user_or_token: Optional[str],
                           query: Optional[str] = None,
                           limit: int = 20) -> List[Dict[str, Any]]:
        """Search WorkDrive for files/folders by name or content.

        GET /teams/{team_id}/records?search[all]=… is WorkDrive's server-side
        search across each team the user belongs to; ``search[all]`` matches
        file/folder NAMES *and* document content (verified live 2026-09-03:
        "WG350DSAV" surfaced Consolidated Price List 2019.xlsx, whose body
        carries the model string — a filename-only search missed it). The
        generic GET /search endpoint answers 405 Invalid Method on every DC
        tried, and the earlier state of this service had NO search method at
        all while UniversalIntegrationService dispatched searches to it — so
        every planner/registry search raised AttributeError and surfaced as
        "returned nothing usable" (live 2026-09-03: "consolidated price list
        2019" — the workbook sat on the drive while the agent answered it had
        no such file).

        ``user_or_token`` accepts a user id (tokens resolve per user via
        ConnectionService/IntegrationToken, like every other method here) or
        a raw Zoho access token ("1000.<id>.<secret>", >40 chars). Search is
        team-scoped, so the teams of the RESOLVED user are searched; a raw
        token with no user row behind it finds no teams and returns [].

        Fault-isolated like list_files: any failure returns [] so callers
        fall back to ingested-workspace memory search instead of erroring.
        """
        if not query or not str(query).strip():
            return []
        raw = str(user_or_token or "")
        if raw.startswith("1000.") and len(raw) > 40:
            token = raw
        else:
            token = await self.get_access_token(raw)
        if not token:
            return []

        try:
            headers = {
                "Authorization": f"Zoho-oauthtoken {token}",
                "Accept": "application/vnd.api+json",
            }
            # Bound the fan-out: each team costs one paced search request.
            teams = (await self.get_teams(raw))[:5]
            want = max(1, int(limit))
            seen_ids = set()
            files: List[Dict[str, Any]] = []
            for team in teams:
                if len(files) >= want:
                    break
                team_id = team.get("id")
                if not team_id:
                    continue
                try:
                    response = await self._zoho_get(
                        f"{self.base_url}/teams/{team_id}/records",
                        headers=headers,
                        params={
                            "search[all]": str(query),
                            "page[limit]": self.PAGE_SIZE,
                        },
                    )
                    response.raise_for_status()
                    page_items = response.json().get("data", [])
                except Exception as team_err:  # noqa: BLE001 — one team's
                    # failure must not sink the other teams' hits
                    logger.warning(
                        f"WorkDrive team search failed ({team_id}): {team_err}")
                    continue
                for item in page_items:
                    item_id = str(item.get("id") or "")
                    if item_id and item_id in seen_ids:
                        continue
                    seen_ids.add(item_id)
                    attrs = item.get("attributes", {})
                    name = attrs.get("name") or attrs.get("display_name", "Untitled")
                    storage_info = attrs.get("storage_info", {})
                    try:
                        size = int(storage_info.get("size_in_bytes") or attrs.get("size") or 0)
                    except (ValueError, TypeError):
                        size = 0
                    files.append({
                        "id": item.get("id"),
                        "name": name,
                        "type": "folder" if (attrs.get("is_folder") or attrs.get("type") in ("folder", "folders")) else "file",
                        "extension": attrs.get("extn") or attrs.get("extension"),
                        "size": size,
                        "modified_at": attrs.get("modified_time_in_iso8601") or attrs.get("modified_time"),
                    })
                    if len(files) >= want:
                        break
            return files
        except Exception as e:
            logger.error(f"Failed to search Zoho WorkDrive: {e}")
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
            nodes_built = 0

            async def build_tree(folder_id: str, depth: int) -> Dict[str, Any]:
                nonlocal nodes_built
                if depth > max_depth:
                    return {"id": folder_id, "name": "..." if depth > 0 else "Root", "type": "folder", "children": [], "truncated": True}
                if nodes_built >= self.MAX_TREE_NODES:
                    return {"id": folder_id, "name": "...", "type": "folder", "children": [], "truncated": True}

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

                nodes_built += 1
                data = resp.json()
                node = {
                    "id": folder_id if folder_id != "root" else target_url.split("/")[-2],
                    "name": "Root" if folder_id == "root" else "Folder",
                    "type": "folder",
                    "children": [],
                    "file_count": 0
                }

                for item in data.get("data", []):
                    attrs = item.get("attributes", {})
                    item_type = attrs.get("type", "file")
                    name = attrs.get("name") or attrs.get("display_name", "Untitled")

                    if item_type == "folder":
                        child = await build_tree(item.get("id"), depth + 1)
                        # The parent listing already carries the child's name —
                        # no per-folder metadata fetch needed (was N+1).
                        child["name"] = name
                        node["children"].append(child)
                    else:
                        node["file_count"] += 1

                return node

            tree = await build_tree("root", 0)
            if nodes_built >= self.MAX_TREE_NODES:
                logger.warning(
                    "Folder tree hit cap of %s nodes; truncated", self.MAX_TREE_NODES
                )
            return tree

        except Exception as e:
            logger.error(f"Failed to build folder tree: {e}")
            return {"id": "root", "name": "Root", "type": "folder", "children": [], "error": "Failed to build folder tree"}
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

    async def ingest_file_to_memory(
        self,
        user_id: str,
        file_id: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
        explicit: bool = True,
    ) -> Dict[str, Any]:
        """Download a file and process it through the ingestion pipeline.

        explicit=True (default) for user/agent-initiated pulls — never
        content-mode-gated. Bulk walkers pass explicit=False so the
        integration's content mode (hybrid/list_only) is honored.
        """
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
                explicit=explicit,
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
            return {"success": False, "error": "Failed to ingest file"}

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
                    logger.warning(f"Ingest failed for {name}: {file_err}")
                    errors.append(f"{name}: ingest failed")

            return {
                "success": True,
                "folder_id": folder_id,
                "files_processed": processed,
                "files_ingested": ingested,
                "errors": errors,
            }
        except Exception as e:
            logger.error(f"Failed to ingest folder tree: {e}")
            return {"success": False, "error": "Failed to ingest folder tree"}

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
                logger.error(f"Zoho WorkDrive metrics sync failed: {e}")
                return {"success": False, "error": "Failed to sync metrics"}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Zoho WorkDrive PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": "Failed to sync Zoho WorkDrive cache"}

    async def full_sync(self, user_id: str,
                         workspace_id: Optional[str] = None,
                         team_id: Optional[str] = None,
                         folder_id: Optional[str] = None,
                         recursive: bool = True,
                         content_mode: Optional[str] = None) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Zoho WorkDrive.

        Pipeline 1: Ingest every file (all types, all subfolders, private
        workspace + team folders) into Atom memory (LanceDB + GraphRAG) via
        AutoDocumentIngestionService. Unparseable/binary files are attempted
        and skipped gracefully rather than filtered out up front, so any file
        type the parsers support (including OCR-able images, code, json) is
        captured.
        Pipeline 2: Refresh the Postgres metrics cache.

        content_mode: "full" ingests every file's content. "hybrid" (storage-
        drive default) and "list_only" keep the file/folder INDEX fresh but
        skip automatic content ingestion — content lands only via explicit
        user selection (Ingest button) or agent pull. None = look up the
        stored setting.

        Args:
            user_id: User ID
            workspace_id: Explicit workspace ID (personal or team workspace)
            team_id: Explicit team ID
            folder_id: Specific folder ID to sync (with recursive traversal)
            recursive: If True, recursively traverse subfolders
        """
        if content_mode is None:
            try:
                from core.hybrid_data_ingestion import get_hybrid_ingestion_service
                content_mode = get_hybrid_ingestion_service().get_content_mode(
                    "zoho_workdrive"
                )
            except Exception:
                content_mode = "hybrid"
        content_mode = (content_mode or "hybrid").lower()

        # One walk at a time per user: concurrent walks double the API
        # pressure and 429 each other into uselessness.
        if user_id in self._full_sync_running:
            return {"success": False, "error": "sync_already_running"}
        self._full_sync_running.add(user_id)
        try:
            return await self._full_sync_inner(
                user_id, workspace_id=workspace_id, team_id=team_id,
                folder_id=folder_id, recursive=recursive,
                content_mode=content_mode,
            )
        finally:
            self._full_sync_running.discard(user_id)

    async def _full_sync_inner(self, user_id: str,
                               workspace_id: Optional[str] = None,
                               team_id: Optional[str] = None,
                               folder_id: Optional[str] = None,
                               recursive: bool = True,
                               content_mode: str = "hybrid") -> Dict[str, Any]:
        ws_id = workspace_id or user_id


        # Use folder_id as root if provided, otherwise "root"
        root_folder = folder_id or "root"

        # List files with new parameters
        # Scoped sync honors the requested workspace/team/folder scope; an
        # unscoped full sync walks the private workspace AND all team folders
        # (walk_files with no root_ids starts at ["root"] + team folder ids).
        if workspace_id or team_id or folder_id:
            files = await self.list_files(
                user_id, parent_id=root_folder, team_id=team_id,
                workspace_id=workspace_id, recursive=recursive
            )
        else:
            files = await self.walk_files(user_id)


        ingested = 0
        skipped: list[str] = []
        errors: list[str] = []

        if content_mode in ("hybrid", "list_only"):
            # Index-only pass: the walk above refreshed the file/folder index
            # and metrics. Content ingestion happens on demand (user Ingest
            # button / agent pull) — never in bulk, per the content mode.
            skipped.append(
                f"content mode '{content_mode}': {len(files)} files indexed, not ingested"
            )
            logger.info(
                f"WorkDrive sync in '{content_mode}' mode: indexed {len(files)} "
                f"files for {user_id} without content ingestion"
            )
        else:
            try:
                for f in files:
                    name = f.get("name", "") or ""
                    try:
                        meta = {
                            "folder_path": f.get("path") or "",
                            "workdrive_root": f.get("root") or "",
                            "modified_at": f.get("modified_at") or "",
                        }
                        res = await self.ingest_file_to_memory(
                            user_id, f.get("id"), extra_metadata=meta, explicit=False
                        )
                        inner = res.get("result") or {}
                        if res.get("success") and inner.get("status") == "ingested":
                            ingested += 1
                        elif res.get("error"):
                            errors.append(f"{name}: {res['error']}")
                        else:
                            skipped.append(f"{name} ({inner.get('reason') or 'no_text'})")
                    except Exception as file_err:
                        logger.warning(f"Ingest failed for {name}: {file_err}")
                        errors.append(f"{name}: ingest failed")
            except Exception as e:
                logger.error(f"Zoho WorkDrive memory ingestion failed: {e}")
                errors.append("memory ingestion failed")

        cache_result = await self.sync_to_postgres_cache(user_id)
        return {
            "success": True,
            "workspace_id": ws_id,
            "team_id": team_id,
            "folder_id": folder_id,
            "recursive": recursive,
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
                {"id": "search_files", "name": "Search Files"},
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
            "search_files": self.search_files,
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
            return {"success": False, "error": "Operation failed"}


# Create a default instance for hub_sync_service compatibility
zoho_workdrive_service = ZohoWorkDriveService("default", {})

