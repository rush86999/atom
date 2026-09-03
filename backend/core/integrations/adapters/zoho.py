"""
Universal Zoho Integration Adapter

Provides OAuth-based integration with Zoho CRM, Books, Projects, and Inventory 
across multiple Data Centers (US, EU, IN, AU, CN) with intelligent Auto-DC discovery.
"""

import logging
import os
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

class ZohoAdapter:
    """
    Universal Adapter for Zoho ecosystem.
    
    Supports:
    - Multi-DC resolution via api_domain auto-detection
    - Multi-App support (CRM, Books, Projects, Inventory)
    - OAuth 2.0 flow with token refresh
    - Unified Entity Data Mapping
    """

    # Zoho Multi-App Base Path mapping
    MODULE_PATH_MAP = {
        "crm": "/crm/v2",
        "books": "/books/v3",
        "inventory": "/inventory/v1",
        "projects": "/restapi/v1"
    }
    
    # Global Auth URL
    DEFAULT_AUTH_URL = "https://accounts.zoho.com/oauth/v2/auth"
    DEFAULT_TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"

    def __init__(self, db=None, workspace_id: str = "default", instance_url: Optional[str] = None):
        self.db = db
        self.workspace_id = workspace_id
        self.instance_url = instance_url or os.getenv("ZOHO_DEFAULT_API_DOMAIN", "https://www.zohoapis.com")
        self.service_name = "zoho"
        
        # OAuth credentials
        self.client_id = os.getenv("ZOHO_CLIENT_ID")
        self.client_secret = os.getenv("ZOHO_CLIENT_SECRET")
        self.redirect_uri = os.getenv("ZOHO_REDIRECT_URI")

        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        # Row id of the loaded token — refresh updates by id so a NULL/drifted
        # workspace_id can't silently drop the refreshed credentials.
        self._token_row_id: Optional[str] = None
        # Set by every fetch call: None on success, "ExcType: msg" on failure.
        # The hybrid sync reads it to keep the incremental cursor from
        # advancing over a module that silently returned [] because of an
        # error (fetchers keep their [] -on-error contract).
        self.last_error: Optional[str] = None

    def _get_base_url(self, module: str = "crm") -> str:
        """Dynamically derive the base URL for a specific Zoho module and DC."""
        module = module.lower()
        base = self.instance_url.rstrip("/")
        
        if module == "projects":
            domain_suffix = base.split(".")[-1]
            return f"https://projectsapi.zoho.{domain_suffix}/restapi/v1"
            
        path = self.MODULE_PATH_MAP.get(module, "/crm/v2")
        return f"{base}{path}"

    async def _load_token(self):
        """Load OAuth tokens from database for the current workspace"""
        if not self.db:
            return
            
        from core.models import IntegrationToken
        from sqlalchemy import or_

        # workspace_id on stored rows may be NULL (rows written before
        # workspace stamping / the unified OAuth callback) — treat them as
        # belonging to every workspace so already-connected pilots keep
        # working after upgrade (RED→GREEN journey fix: NULL rows made
        # ensure_token() miss and every data call ran unauthenticated).
        token = self.db.query(IntegrationToken).filter(
            IntegrationToken.provider == "zoho",
            or_(
                IntegrationToken.workspace_id == self.workspace_id,
                IntegrationToken.workspace_id.is_(None),
            ),
        ).first()
        if not token:
            # Fallback: the callback stamps rows under the user's resolved
            # workspace while callers construct this adapter with whatever
            # workspace/tenant convention they hold — when the two drift the
            # scoped lookup misses and every data call ran unauthenticated.
            # Resolve like outlook_service does: any active grant for this
            # provider (single-operator semantics), never a revoked one.
            token = self.db.query(IntegrationToken).filter(
                IntegrationToken.provider == "zoho",
                IntegrationToken.status == "active",
            ).first()
        
        if token:
            from core.privsec.token_encryption import decrypt_token
            # getattr: test fakes duck-type the row without an id column.
            self._token_row_id = getattr(token, "id", None)
            self._access_token = decrypt_token(token.access_token, allow_plaintext=True)
            self._refresh_token = decrypt_token(token.refresh_token, allow_plaintext=True) if token.refresh_token else None
            self._token_expires_at = token.expires_at
            # SQLite returns naive datetimes even for timezone-aware columns —
            # normalize or ensure_token() crashes comparing against aware now
            # (RED→GREEN journey fix: "can't compare offset-naive and
            # offset-aware datetimes" → every fresh-connect sync fetched 0).
            if self._token_expires_at and self._token_expires_at.tzinfo is None:
                self._token_expires_at = self._token_expires_at.replace(tzinfo=timezone.utc)

            if token.instance_url:
                self.instance_url = token.instance_url

    async def refresh_token(self) -> bool:
        """Refresh Zoho access token using refresh token"""
        if not self._refresh_token:
            return False

        # Refresh MUST hit the same datacenter that issued the grant. Prefer
        # ZOHO_ACCOUNTS_BASE (deploy-time config), then the accounts base the
        # OAuth callback recorded on the token row, then the .com default —
        # otherwise a non-.com account (e.g. zohocloud.ca) gets a .com token
        # that 401s against its regional API.
        token_url = os.getenv("ZOHO_ACCOUNTS_BASE", "").strip().rstrip("/")
        if token_url:
            token_url = f"{token_url}/oauth/v2/token"
        else:
            token_url = self.DEFAULT_TOKEN_URL
            try:
                if self.db:
                    from core.models import IntegrationToken
                    _meta_row = self.db.query(IntegrationToken).filter(
                        IntegrationToken.workspace_id == self.workspace_id,
                        IntegrationToken.provider == "zoho",
                    ).first()
                    accounts_base = ((_meta_row.credential_metadata or {}).get("accounts_base")
                                     if _meta_row and _meta_row.credential_metadata else None)
                    if accounts_base:
                        token_url = f"{str(accounts_base).rstrip('/')}/oauth/v2/token"
            except Exception:
                pass

        try:
            async with httpx.AsyncClient() as client:
                data = {
                    "refresh_token": self._refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token"
                }
                response = await client.post(token_url, data=data)
                response.raise_for_status()
                
                token_data = response.json()
                self._access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 3600)
                self._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                
                # Update DB — by the row id actually loaded (workspace-stamped
                # queries miss rows with NULL/drifted workspace_id, dropping
                # the refreshed credentials on the floor).
                if self.db:
                    from core.models import IntegrationToken
                    token = None
                    if self._token_row_id:
                        token = self.db.query(IntegrationToken).filter(
                            IntegrationToken.id == self._token_row_id
                        ).first()
                    if token is None:
                        token = self.db.query(IntegrationToken).filter(
                            IntegrationToken.workspace_id == self.workspace_id,
                            IntegrationToken.provider == "zoho"
                        ).first()
                    if token:
                        from core.privsec.token_encryption import encrypt_token, stamp_credential_metadata
                        token.access_token = encrypt_token(self._access_token)
                        token.expires_at = self._token_expires_at
                        stamp_credential_metadata(token)
                        # One grant covers the whole suite: fan the fresh
                        # access token out to the record rows so no family
                        # provider serves a stale token after a canonical-row
                        # refresh (mirrors the connect-time token fan-out).
                        # Best-effort — a fan-out failure must never fail the
                        # canonical refresh. WorkDrive is excluded —
                        # ZohoWorkDriveService manages its own row's refresh
                        # lifecycle.
                        try:
                            enc_access = token.access_token
                            family_filter = [
                                IntegrationToken.provider.in_(
                                    ("zoho_crm", "zoho_books", "zoho_inventory")
                                ),
                                IntegrationToken.status == "active",
                            ]
                            # Single-tenant rows may lack a tenant — match on
                            # it only when the refreshed row carries one.
                            tenant_id = getattr(token, "tenant_id", None)
                            if tenant_id:
                                family_filter.append(
                                    IntegrationToken.tenant_id == tenant_id
                                )
                            family = self.db.query(IntegrationToken).filter(
                                *family_filter
                            ).all()
                            for other in family:
                                other.access_token = enc_access
                                other.expires_at = self._token_expires_at
                                stamp_credential_metadata(other)
                        except Exception as fan_out_err:
                            logger.warning(
                                f"Zoho token family fan-out skipped: {fan_out_err}"
                            )
                        self.db.commit()
                
                return True
        except Exception as e:
            logger.error(f"Zoho token refresh failed: {e}")
            return False

    # Refresh BEFORE expiry rather than at the 401: Zoho access tokens live
    # one hour, and a sync that starts in the token's last minutes used to
    # run its later modules unauthenticated. 5 min mirrors the base-adapter
    # pattern in the SaaS tree (refresh when <300 s remain).
    REFRESH_MARGIN_SECONDS = 300

    async def ensure_token(self):
        """Ensure we have a valid access token — refreshing proactively when
        the remaining lifetime dips under REFRESH_MARGIN_SECONDS."""
        if not self._access_token:
            await self._load_token()

        if not self._access_token:
            return

        # No stored expiry (legacy row) — the old contract applies: nothing
        # measurable to refresh against. The 401-retry in _authed_get_json
        # still covers an unexpectedly rejected token.
        if self._token_expires_at is None:
            return
        seconds_left = (
            self._token_expires_at - datetime.now(timezone.utc)
        ).total_seconds()
        if seconds_left >= self.REFRESH_MARGIN_SECONDS:
            return
        await self.refresh_token()

    async def _authed_get_json(
        self,
        client: "httpx.AsyncClient",
        url: str,
        params: Optional[Dict[str, Any]] = None,
        modified_since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """GET with the current access token; on 401 force one refresh and retry.

        A sync that outlives its access token used to abort the module with a
        silent empty return; the single retry keeps long syncs intact. 204/304
        (no records modified — the normal incremental answer) becomes {}.
        """
        headers = {"Authorization": f"Zoho-oauthtoken {self._access_token}"}
        if modified_since is not None:
            # CRM list endpoints take If-Modified-Since (ISO 8601).
            headers["If-Modified-Since"] = modified_since.astimezone(
                timezone.utc
            ).isoformat()
        response = await client.get(url, headers=headers, params=params)
        if response.status_code == 401 and await self.refresh_token():
            headers["Authorization"] = f"Zoho-oauthtoken {self._access_token}"
            response = await client.get(url, headers=headers, params=params)
        if response.status_code in (204, 304):
            return {}
        response.raise_for_status()
        return response.json() or {}

    @staticmethod
    def _format_books_ts(value: datetime) -> str:
        """Books/Inventory last_modified_time filter — ISO 8601 with a
        colon-less offset (2026-09-02T13:04:59+0000)."""
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")

    async def get_oauth_url(self, scopes: Optional[List[str]] = None) -> str:
        """Generate Zoho OAuth authorization URL with expanded scopes"""
        if not scopes:
            scopes = [
                "ZohoCRM.modules.ALL",
                "ZohoCRM.users.READ",
                "ZohoBooks.fullaccess.all",
                "ZohoProjects.projects.ALL",
                "ZohoInventory.fullaccess.all",
                # WorkDrive scopes are `WorkDrive.`-prefixed — the
                # `ZohoWorkDrive.` prefix is rejected ("Scope does not
                # exist"; live-verified against accounts.zohocloud.ca).
                "WorkDrive.files.ALL",
            ]
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": ",".join(scopes),
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "state": self.workspace_id
        }
        
        return f"{self.DEFAULT_AUTH_URL}?{urlencode(params)}"

    async def get_leads(self, limit: int = 100, modified_since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Fetch leads from Zoho CRM (If-Modified-Since incremental when a
        cursor is given)"""
        self.last_error = None
        try:
            base_url = self._get_base_url("crm")
            async with httpx.AsyncClient() as client:
                data = await self._authed_get_json(
                    client,
                    f"{base_url}/Leads",
                    params={"per_page": limit},
                    modified_since=modified_since,
                )
                return [self._map_lead(l) for l in data.get("data", [])]
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            logger.error(f"Zoho CRM lead fetch failed: {e}")
            return []

    async def get_deals(self, limit: int = 100, modified_since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Fetch deals from Zoho CRM (If-Modified-Since incremental when a
        cursor is given)"""
        self.last_error = None
        try:
            base_url = self._get_base_url("crm")
            async with httpx.AsyncClient() as client:
                data = await self._authed_get_json(
                    client,
                    f"{base_url}/Deals",
                    params={"per_page": limit},
                    modified_since=modified_since,
                )
                return [self._map_deal(d) for d in data.get("data", [])]
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            logger.error(f"Zoho CRM deal fetch failed: {e}")
            return []

    # Books/Inventory list endpoints cap per_page at 100.
    _BOOKS_PER_PAGE_CAP = 100

    async def _fetch_books_pages(
        self,
        client: "httpx.AsyncClient",
        url: str,
        organization_id: str,
        limit: int,
        results_key: str,
        modified_since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Page a Books/Inventory list endpoint up to `limit` raw records.

        Zoho Books/Inventory paginate with page/per_page and report
        page_context.has_more_page. The previous single request passed an
        undocumented page_size param, so at most the first page (25 records
        at the API default) ever came back — orgs with more invoices/items/
        sales orders than that never saw the rest ingested.
        """
        records: List[Dict[str, Any]] = []
        per_page = min(max(limit, 1), self._BOOKS_PER_PAGE_CAP)
        page = 1
        while len(records) < limit:
            params: Dict[str, Any] = {
                "organization_id": organization_id,
                "page": page,
                "per_page": per_page,
            }
            if modified_since is not None:
                params["last_modified_time"] = self._format_books_ts(modified_since)
            data = await self._authed_get_json(client, url, params=params)
            batch = data.get(results_key, [])
            records.extend(batch)
            has_more = bool((data.get("page_context") or {}).get("has_more_page"))
            if len(batch) < per_page or not has_more:
                break
            page += 1
        return records[:limit]

    async def get_invoices(self, organization_id: str, limit: int = 100, modified_since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Fetch invoices from Zoho Books (all pages up to `limit`,
        last_modified_time incremental when a cursor is given)"""
        self.last_error = None
        try:
            base_url = self._get_base_url("books")
            async with httpx.AsyncClient() as client:
                raw = await self._fetch_books_pages(
                    client, f"{base_url}/invoices", organization_id, limit, "invoices",
                    modified_since=modified_since,
                )
                return [self._map_invoice(i) for i in raw]
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            logger.error(f"Zoho Books invoice fetch failed: {e}")
            return []

    async def get_portals(self) -> List[Dict[str, Any]]:
        """Fetch all portals from Zoho Projects"""
        self.last_error = None
        try:
            base_url = self._get_base_url("projects")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/portals/",
                    headers={"Authorization": f"Zoho-oauthtoken {self._access_token}"}
                )
                response.raise_for_status()
                data = response.json().get("portals", [])
                return [self._map_portal(p) for p in data]
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            logger.error(f"Zoho Projects portal fetch failed: {e}")
            return []

    async def get_projects(self, portal_id: str) -> List[Dict[str, Any]]:
        """Fetch all projects from a Zoho Projects portal"""
        self.last_error = None
        try:
            base_url = self._get_base_url("projects")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/portal/{portal_id}/projects/",
                    headers={"Authorization": f"Zoho-oauthtoken {self._access_token}"}
                )
                response.raise_for_status()
                data = response.json().get("projects", [])
                return [self._map_project(p) for p in data]
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            logger.error(f"Zoho Projects project fetch failed: {e}")
            return []

    async def get_tasks(self, portal_id: str, project_id: str) -> List[Dict[str, Any]]:
        """Fetch tasks from Zoho Projects"""
        self.last_error = None
        try:
            base_url = self._get_base_url("projects")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/portal/{portal_id}/projects/{project_id}/tasks/",
                    headers={"Authorization": f"Zoho-oauthtoken {self._access_token}"}
                )
                response.raise_for_status()
                data = response.json().get("tasks", [])
                return [self._map_task(t) for t in data]
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            logger.error(f"Zoho Projects task fetch failed: {e}")
            return []

    async def get_items(self, organization_id: str, limit: int = 100, modified_since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Fetch items from Zoho Inventory (all pages up to `limit`,
        last_modified_time incremental when a cursor is given)"""
        self.last_error = None
        try:
            base_url = self._get_base_url("inventory")
            async with httpx.AsyncClient() as client:
                raw = await self._fetch_books_pages(
                    client, f"{base_url}/items", organization_id, limit, "items",
                    modified_since=modified_since,
                )
                return [self._map_inventory_item(i) for i in raw]
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            logger.error(f"Zoho Inventory item fetch failed: {e}")
            return []

    async def get_sales_orders(self, organization_id: str, limit: int = 100, modified_since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Fetch sales orders from Zoho Inventory (all pages up to `limit`,
        last_modified_time incremental when a cursor is given)"""
        self.last_error = None
        try:
            base_url = self._get_base_url("inventory")
            async with httpx.AsyncClient() as client:
                raw = await self._fetch_books_pages(
                    client, f"{base_url}/salesorders", organization_id, limit, "salesorders",
                    modified_since=modified_since,
                )
                return [self._map_sales_order(s) for s in raw]
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            logger.error(f"Zoho Inventory sales order fetch failed: {e}")
            return []

    async def get_organizations(self, module: str = "books") -> List[Dict[str, Any]]:
        """Fetch the orgs (workspaces) a Zoho Books/Inventory account owns.

        The Books/Inventory sync paths are gated on an organization_id; this
        endpoint is how the sync discovers it automatically after connect
        (the OAuth callback has no org context)."""
        try:
            base_url = self._get_base_url(module)
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/organizations",
                    headers={"Authorization": f"Zoho-oauthtoken {self._access_token}"},
                )
                response.raise_for_status()
                data = response.json().get("organizations", [])
                return [
                    {
                        "organization_id": o.get("organization_id"),
                        "name": o.get("name"),
                    }
                    for o in data
                    if o.get("organization_id")
                ]
        except Exception as e:
            logger.error(f"Zoho {module} organizations fetch failed: {e}")
            return []

    # --- Write operations (agent-managed CRM mutations) ---

    async def create_lead(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        base_url = self._get_base_url("crm")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/Leads",
                headers={"Authorization": f"Zoho-oauthtoken {self._access_token}"},
                json={"data": [data]}
            )
            response.raise_for_status()
            result = response.json()
            if result.get("data") and result["data"][0].get("code") == "SUCCESS":
                return {"id": result["data"][0]["details"]["id"], "status": "created"}
            return None

    async def update_lead(self, lead_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        base_url = self._get_base_url("crm")
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{base_url}/Leads/{lead_id}",
                headers={"Authorization": f"Zoho-oauthtoken {self._access_token}"},
                json={"data": [fields]}
            )
            response.raise_for_status()
            return {"id": lead_id, "status": "updated"}

    async def create_deal(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        base_url = self._get_base_url("crm")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/Deals",
                headers={"Authorization": f"Zoho-oauthtoken {self._access_token}"},
                json={"data": [data]}
            )
            response.raise_for_status()
            result = response.json()
            if result.get("data") and result["data"][0].get("code") == "SUCCESS":
                return {"id": result["data"][0]["details"]["id"], "status": "created"}
            return None

    async def update_deal(self, deal_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        base_url = self._get_base_url("crm")
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{base_url}/Deals/{deal_id}",
                headers={"Authorization": f"Zoho-oauthtoken {self._access_token}"},
                json={"data": [fields]}
            )
            response.raise_for_status()
            return {"id": deal_id, "status": "updated"}

    def _map_lead(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Zoho Lead"""
        return {
            "id": raw.get("id"),
            "type": "lead",
            "name": raw.get("Full_Name"),
            "email": raw.get("Email"),
            "company": raw.get("Company"),
            "status": raw.get("Lead_Status"),
            "source": "zoho_crm",
            "raw_metadata": raw
        }

    def _map_deal(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Zoho Deal"""
        return {
            "id": raw.get("id"),
            "type": "deal",
            "name": raw.get("Deal_Name"),
            "amount": raw.get("Amount"),
            "stage": raw.get("Stage"),
            "close_date": raw.get("Closing_Date"),
            "source": "zoho_crm",
            "raw_metadata": raw
        }

    def _map_invoice(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Zoho Books Invoice"""
        return {
            "id": raw.get("invoice_id"),
            "type": "invoice",
            "number": raw.get("invoice_number"),
            "customer_name": raw.get("customer_name"),
            "amount": raw.get("total"),
            "status": raw.get("status"),
            "due_date": raw.get("due_date"),
            "source": "zoho_books",
            "raw_metadata": raw
        }

    def _map_portal(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Zoho Projects Portal"""
        return {
            "id": raw.get("id_string"),
            "type": "portal",
            "name": raw.get("name"),
            "is_default": raw.get("is_default", False),
            "source": "zoho_projects",
            "raw_metadata": raw
        }

    def _map_project(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Zoho Projects Project"""
        return {
            "id": raw.get("id_string"),
            "type": "project",
            "name": raw.get("name"),
            "status": raw.get("status"),
            "owner_name": raw.get("owner_name"),
            "created_at": raw.get("created_date_format"),
            "source": "zoho_projects",
            "raw_metadata": raw
        }

    def _map_task(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Zoho Projects Task"""
        return {
            "id": raw.get("id_string"),
            "type": "task",
            "name": raw.get("name"),
            "description": raw.get("description"),
            "status": raw.get("status", {}).get("name"),
            "priority": raw.get("priority"),
            "due_date": raw.get("end_date"),
            "source": "zoho_projects",
            "raw_metadata": raw
        }

    def _map_inventory_item(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Zoho Inventory Item"""
        return {
            "id": raw.get("item_id"),
            "type": "inventory_item",
            "name": raw.get("name"),
            "sku": raw.get("sku"),
            "description": raw.get("description"),
            "price": raw.get("rate"),
            "stock_on_hand": raw.get("stock_on_hand"),
            "unit": raw.get("unit"),
            "source": "zoho_inventory",
            "raw_metadata": raw
        }

    def _map_sales_order(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Zoho Inventory Sales Order"""
        return {
            "id": raw.get("salesorder_id"),
            "type": "sales_order",
            "number": raw.get("salesorder_number"),
            "customer_name": raw.get("customer_name"),
            "amount": raw.get("total"),
            "status": raw.get("status"),
            "date": raw.get("date"),
            "source": "zoho_inventory",
            "raw_metadata": raw
        }
