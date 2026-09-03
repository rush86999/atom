import logging
import os
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from urllib.parse import urlparse
import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

from core.integration_service import IntegrationService

# Resolved organization ids keyed by tenant — Zoho Inventory has no
# "who am I" without an organization_id on every call, and this workspace
# never had ZOHO_ORG_ID configured. Populated lazily from the live
# /orgganizations lookup in _resolve_organization.
_ORG_CACHE: Dict[str, str] = {}

# Inventory API hosts for the no-api_domain fallback. Zoho's newer data
# centers consolidated onto the zohoapis domain (the OAuth token response's
# api_domain, e.g. https://www.zohoapis.ca) with the service path appended
# (/inventory/v1) — the classic inventory.zoho.<suffix> hosts don't exist
# for every DC (inventory.zoho.ca has no DNS record) and the zohocloud.ca
# hosts 400 with "Use the zohoapis domain for API requests" (live
# 2026-09-03).
_SPECIAL_INVENTORY_HOSTS = {
    "ca": "https://www.zohoapis.ca/inventory/v1",
}


class ZohoInventoryService(IntegrationService):
    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        super().__init__(tenant_id=tenant_id, config=config)
        self.base_url = "https://inventory.zoho.com/api/v1"
        self.client_id = config.get("client_id") or os.getenv("ZOHO_INVENTORY_CLIENT_ID") or os.getenv("ZOHO_CLIENT_ID")
        self.client_secret = config.get("client_secret") or os.getenv("ZOHO_INVENTORY_CLIENT_SECRET") or os.getenv("ZOHO_CLIENT_SECRET")
        self.access_token = config.get("access_token")
        self.organization_id = config.get("organization_id") or os.getenv("ZOHO_ORG_ID")
        self.client = httpx.AsyncClient(timeout=30.0)

    # ---- IntegrationService abstract-method implementations ----
    # Satisfies the ABC contract from core.integration_service so the class
    # can be instantiated by ServiceFactory / routers.

    def get_capabilities(self) -> Dict[str, Any]:
        """Return the operations this Zoho service exposes."""
        return {
            "operations": ['get_items', 'search_items', 'get_inventory_levels', 'check_stock'],
            "required_params": ["access_token"],
            "optional_params": ["organization_id", "tenant_id"],
            "rate_limits": {"requests_per_minute": 100},
            "supports_webhooks": False,
        }

    def health_check(self) -> Dict[str, Any]:
        """Return a basic health snapshot (token presence + base URL)."""
        from datetime import datetime, timezone
        return {
            "healthy": bool(getattr(self, "access_token", None)),
            "message": "connected" if getattr(self, "access_token", None) else "no access token configured",
            "last_check": datetime.now(timezone.utc).isoformat(),
            "base_url": getattr(self, "base_url", None),
        }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Dispatch a named operation to the service's existing methods."""
        try:
            if operation == "get_items":
                return {"success": True, "result": await self.get_items()}
            if operation in ("search_items", "search"):
                return {"success": True, "result": await self.search_items(
                    parameters.get("query", ""), limit=parameters.get("limit", 8))}
            if operation == "get_inventory_levels":
                return {"success": True, "result": await self.get_inventory_levels()}
            return {
                "success": False,
                "error": f"Unsupported operation: {operation}",
                "supported": ['get_items', 'search_items', 'get_inventory_levels'],
            }
        except Exception as exc:
            return {"success": False, "error": "Zoho Inventory operation failed"}

    async def _get_active_token(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None) -> Optional[str]:
        """Get a valid access token, refreshing if necessary.

        Resolution order: the acting USER's IntegrationToken row first (the
        unified OAuth connect flow keys rows by user_id — a tenant-scoped
        lookup with tenant 'default' missed them, so every agent-planned
        inventory search died on "no access token" while the integration was
        connected, live 2026-09-03), then the tenant row for system contexts.
        """
        tid = tenant_id or getattr(self, "session_id", None) or self.tenant_id
        if not tid and not user_id:
            return self.access_token or os.getenv("ZOHO_INVENTORY_ACCESS_TOKEN")

        from core.database import SessionLocal
        from core.models import IntegrationToken
        from datetime import datetime, timezone, timedelta

        # BUG FIX: SessionLocal() was created OUTSIDE the try block, so a DB
        # session failure propagated to the caller instead of returning None
        # as the "Error retrieving ... token" handler intends.
        try:
            db = SessionLocal()
        except Exception as e:
            logger.error(f"Error retrieving Zoho Inventory token (user={user_id} tenant={tid}): {e}")
            return None
        try:
            token_record = None
            if user_id:
                # No cross-user fallback: any active token would serve one
                # user's Zoho data to every authenticated user (same policy
                # as zoho_workdrive_service._integration_token_access_token).
                for provider in ("zoho_inventory", "zoho"):
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
            if token_record is None:
                token_record = db.query(IntegrationToken).filter(
                    IntegrationToken.tenant_id == tid,
                    IntegrationToken.provider == "zoho_inventory"
                ).first()

            if not token_record:
                return None

            now = datetime.now(timezone.utc)
            expires_at = token_record.expires_at
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if not expires_at or expires_at < (now + timedelta(minutes=2)):
                if token_record.refresh_token:
                    from core.privsec.token_encryption import decrypt_token, encrypt_token, stamp_credential_metadata
                    refresh_plain = decrypt_token(token_record.refresh_token, allow_plaintext=True) if token_record.refresh_token else None
                    new_tokens = await self.refresh_token(refresh_plain)
                    # .get, not [ ]: a failed refresh returns a truthy error
                    # payload ({"error": ...}) — indexing it raised
                    # KeyError('access_token') and masked the real problem
                    # ("refresh failed") as a token-store error.
                    new_access = (new_tokens or {}).get("access_token")
                    if new_access:
                        token_record.access_token = encrypt_token(new_access)
                        token_record.expires_at = datetime.now(timezone.utc) + timedelta(seconds=new_tokens.get("expires_in", 3600))
                        stamp_credential_metadata(token_record)
                        db.commit()
                        # Decrypt before returning — the row stores ciphertext;
                        # returning it verbatim handed Zoho an encrypted blob
                        # as the bearer token.
                        return decrypt_token(token_record.access_token, allow_plaintext=True)
                return None

            from core.privsec.token_encryption import decrypt_token
            return decrypt_token(token_record.access_token, allow_plaintext=True)
        except Exception as e:
            logger.error(f"Error retrieving Zoho Inventory token for tenant {tid}: {e}")
            return None
        finally:
            db.close()

    async def refresh_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """Refresh Zoho Inventory access token using refresh token"""
        try:
            token_url = "https://accounts.zoho.com/oauth/v2/token"
            data = {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
            }

            response = await self.client.post(token_url, data=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to refresh Zoho Inventory token: {e}")
            return None

    async def _datacenter_suffix(self, tenant_id: Optional[str] = None) -> str:
        """Datacenter suffix ('ca', 'com', 'com.au', ...) of this workspace's
        Zoho grant. Tokens are DC-scoped: a .ca-issued token 401s against the
        .com API, so the inventory host must follow the grant. The OAuth
        callback stamps the token response's api_domain (e.g.
        https://www.zohoapis.ca) on the canonical 'zoho' token row only —
        the fanned-out zoho_inventory row gets instance_url=None — so fall
        back to that row (single-operator semantics, mirroring ZohoAdapter)."""
        domain = (
            self.config.get("api_domain")
            or self.config.get("instance_url")
            or os.getenv("ZOHO_INVENTORY_API_DOMAIN")
            or os.getenv("ZOHO_API_DOMAIN")
        )
        if not domain:
            try:
                from core.database import SessionLocal
                from core.models import IntegrationToken

                db = SessionLocal()
                try:
                    tid = tenant_id or self.tenant_id
                    row = None
                    if tid:
                        row = db.query(IntegrationToken).filter(
                            IntegrationToken.provider == "zoho_inventory",
                            IntegrationToken.tenant_id == tid,
                            IntegrationToken.status == "active",
                        ).first()
                    if row and row.instance_url:
                        domain = row.instance_url
                    else:
                        canonical = db.query(IntegrationToken).filter(
                            IntegrationToken.provider == "zoho",
                            IntegrationToken.status == "active",
                        ).first()
                        if canonical and canonical.instance_url:
                            domain = canonical.instance_url
                finally:
                    db.close()
            except Exception as e:
                logger.debug(f"datacenter lookup fell back to default: {e}")
        host = urlparse(domain).netloc if domain and "://" in str(domain) else (domain or "")
        if "zohoapis." in host:
            return host.split("zohoapis.", 1)[1]
        if ".zoho." in host:
            return host.rsplit(".zoho.", 1)[1]
        return "com"

    async def _api_domain(self, tenant_id: Optional[str] = None) -> Optional[str]:
        """The datacenter API domain Zoho itself instructs this workspace to
        use — the OAuth token response's api_domain, stamped by the callback
        onto the canonical 'zoho' token row's instance_url (the fanned-out
        zoho_inventory row gets instance_url=None, hence the fallback)."""
        domain = (
            self.config.get("api_domain")
            or self.config.get("instance_url")
            or os.getenv("ZOHO_INVENTORY_API_DOMAIN")
            or os.getenv("ZOHO_API_DOMAIN")
        )
        if domain:
            return str(domain).rstrip("/")
        try:
            from core.database import SessionLocal
            from core.models import IntegrationToken

            db = SessionLocal()
            try:
                tid = tenant_id or self.tenant_id
                row = None
                if tid:
                    row = db.query(IntegrationToken).filter(
                        IntegrationToken.provider == "zoho_inventory",
                        IntegrationToken.tenant_id == tid,
                        IntegrationToken.status == "active",
                    ).first()
                if row and row.instance_url:
                    domain = row.instance_url
                else:
                    canonical = db.query(IntegrationToken).filter(
                        IntegrationToken.provider == "zoho",
                        IntegrationToken.status == "active",
                    ).first()
                    if canonical and canonical.instance_url:
                        domain = canonical.instance_url
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"api domain lookup failed: {e}")
        return str(domain).rstrip("/") if domain else None

    async def _inventory_base(self, tenant_id: Optional[str] = None) -> str:
        """Datacenter-correct Inventory API base URL for this workspace.
        Preferred form: <api_domain>/inventory/v1 (what Zoho's own error
        messages instruct). Falls back to the classic host pattern, with
        special cases for DCs where that pattern doesn't resolve."""
        domain = await self._api_domain(tenant_id)
        if domain:
            return f"{domain}/inventory/v1"
        suffix = await self._datacenter_suffix(tenant_id)
        special = _SPECIAL_INVENTORY_HOSTS.get(suffix)
        if special:
            return special
        return f"https://inventory.zoho.{suffix}/api/v1"

    async def _resolve_organization(
        self,
        tenant_id: Optional[str] = None,
        token: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> Optional[str]:
        """Organization id for Inventory calls: explicit config/env first
        (ZOHO_ORG_ID), then a cached value, then one live lookup — the
        orgganizations endpoint under both of Zoho's historical spellings —
        cached for the process lifetime so each turn costs no extra call."""
        org = self.organization_id or os.getenv("ZOHO_ORG_ID")
        if org:
            return org
        key = tenant_id or self.tenant_id or "default"
        cached = _ORG_CACHE.get(key)
        if cached:
            return cached
        if not (token and base_url):
            return None
        headers = {"Authorization": f"Zoho-oauthtoken {token}"}
        # /organizations works on the zohoapis domain; /orgganizations is the
        # legacy inventory.zoho.<dc> spelling — kept as a fallback.
        for path in ("/organizations", "/orgganizations"):
            try:
                response = await self.client.get(f"{base_url}{path}", headers=headers)
                if response.status_code != 200:
                    # Surface WHY (DC mismatch, expiry, wrong endpoint) — a
                    # silent skip here is how inventory lookups failed
                    # invisibly for weeks.
                    logger.warning(
                        f"org lookup {base_url}{path} -> HTTP {response.status_code}: "
                        f"{str(response.text)[:160]}")
                    continue
                orgs = response.json().get("organizations") or []
                if orgs:
                    resolved = str(orgs[0].get("organization_id"))
                    _ORG_CACHE[key] = resolved
                    logger.info(f"Resolved Zoho Inventory organization_id for tenant {key}")
                    return resolved
            except Exception as e:
                logger.warning(f"org lookup via {path} failed: {type(e).__name__}: {e}")
        return None

    @staticmethod
    def _slim_item(item: Dict[str, Any]) -> Dict[str, Any]:
        """Project an Inventory item to the fields a stock answer needs.
        The chat tool harness renders results into a ~2500-char prompt block,
        so full item payloads truncate to a single item."""
        return {
            "item_id": item.get("item_id"),
            "name": item.get("name"),
            "sku": item.get("sku"),
            "stock_on_hand": item.get("stock_on_hand", 0),
            "available_stock": item.get("available_stock", 0),
            "rate": item.get("rate"),
            "description": (item.get("description") or "")[:160] or None,
        }

    async def search_items(
        self,
        query: str,
        token: Optional[str] = None,
        organization_id: Optional[str] = None,
        limit: int = 8,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search live Zoho Inventory items by name/SKU (search_text + pagination).

        This is the live leg the chat tool planner intends when it plans
        zoho_inventory.search — until now that action matched no handler and
        every "Zoho Inventory search" answer was really the ingested-file
        memory search (live 2026-09-03: WG-350DSAV in stock, agent said
        "no live stock records").

        ``user_id`` (the acting user from the executor context) resolves the
        OAuth token per-user; without it the tenant lookup runs and — for
        agent turns, where the tenant is 'default' but the token rows are
        user-keyed — finds nothing.

        Never raises: an empty result lets the planner's memory fallback run
        instead of dead-ending the turn."""
        query = (query or "").strip()
        if not query:
            return []
        try:
            active_token = (
                token
                or self.access_token
                or os.getenv("ZOHO_INVENTORY_ACCESS_TOKEN")
                or await self._get_active_token(self.tenant_id, user_id=user_id)
            )
            if not active_token:
                logger.warning("zoho_inventory.search_items: no access token available")
                return []
            base_url = await self._inventory_base()
            active_org = organization_id or await self._resolve_organization(
                token=active_token, base_url=base_url,
            )
            if not active_org:
                logger.warning("zoho_inventory.search_items: no organization_id resolved")
                return []

            headers = {"Authorization": f"Zoho-oauthtoken {active_token}"}
            items: List[Dict[str, Any]] = []
            page = 1
            while page <= 10:  # hard cap: 10 x 100 items covers any sane catalog
                response = await self.client.get(
                    f"{base_url}/items",
                    headers=headers,
                    params={
                        "organization_id": active_org,
                        "search_text": query,
                        "per_page": 100,
                        "page": page,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                for item in payload.get("items", []):
                    items.append(self._slim_item(item))
                    if len(items) >= limit:
                        break
                if len(items) >= limit:
                    break
                page_context = payload.get("page_context") or {}
                if not page_context.get("has_more_page"):
                    break
                page += 1
            return items
        except Exception as e:
            logger.warning(f"zoho_inventory.search_items({query!r}) failed: {type(e).__name__}: {e}")
            return []

    async def get_items(self, token: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch items list for pricing and availability checks"""
        try:
            active_token = token or self.access_token
            active_org = organization_id or self.organization_id

            if not active_token:
                # Same resolution chain search_items uses: explicit arg >
                # config > env > the tenant's stored OAuth grant (the DB
                # row is where the token actually lives in production).
                active_token = await self._get_active_token(self.tenant_id)
            if not active_token:
                 raise HTTPException(status_code=401, detail="Not authenticated")
            if not active_org:
                active_org = await self._resolve_organization(
                    token=active_token,
                    base_url=await self._inventory_base(),
                )
            if not active_org:
                 raise HTTPException(status_code=400, detail="Organization ID required")

            # DC-correct host: the legacy self.base_url (.com) 401s for tokens
            # issued by any other data center (live 2026-09-03).
            headers = {"Authorization": f"Zoho-oauthtoken {active_token}"}
            response = await self.client.get(
                f"{await self._inventory_base()}/items",
                headers=headers,
                params={"organization_id": active_org},
            )
            response.raise_for_status()
            return response.json().get("items", [])
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch Zoho Inventory items: {e}")
            return []

    async def check_stock(self, item_id: str, token: Optional[str] = None, organization_id: Optional[str] = None) -> Dict[str, Any]:
        """Check current stock levels for an item"""
        try:
            active_token = token or self.access_token
            active_org = organization_id or self.organization_id

            if not active_token:
                 raise HTTPException(status_code=401, detail="Not authenticated")
            if not active_org:
                 raise HTTPException(status_code=400, detail="Organization ID required")

            params = {"organization_id": active_org}
            headers = {"Authorization": f"Zoho-oauthtoken {active_token}"}
            response = await self.client.get(f"{self.base_url}/items/{item_id}", headers=headers, params=params)
            response.raise_for_status()
            item = response.json().get("item", {})
            return {
                "item_id": item_id,
                "name": item.get("name"),
                "stock_on_hand": item.get("stock_on_hand", 0),
                "available_stock": item.get("available_stock", 0)
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to check stock for {item_id}: {e}")
            return {"error": "Failed to check stock"}

    async def get_inventory_levels(self, token: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch inventory levels for all active items"""
        try:
            items = await self.get_items(token, organization_id)
            inventory = []
            for item in items:
                inventory.append({
                    "sku": item.get("sku"),
                    "name": item.get("name"),
                    "available": item.get("stock_on_hand", 0),
                    "platform": "zoho"
                })
            return inventory
        except Exception as e:
            logger.error(f"Failed to get Zoho inventory levels: {e}")
            return []

    async def sync_to_postgres_cache(self, user_id: str, access_token: str, organization_id: str) -> Dict[str, Any]:
        """Sync Zoho Inventory analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric
            
            # Fetch Items to get total count
            items = await self.get_items(access_token, organization_id)
            item_count = len(items)
            
            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("zoho_inventory_item_count", item_count, "count"),
                ]
                
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        workspace_id=user_id,
                        integration_type="zoho_inventory",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            workspace_id=user_id,
                            integration_type="zoho_inventory",
                            metric_key=key,
                            value=float(value),
                            unit=unit
                        )
                        db.add(metric)
                    metrics_synced += 1
                
                db.commit()
                logger.info(f"Synced {metrics_synced} Zoho Inventory metrics to PostgreSQL cache for user {user_id}")
            except Exception as e:
                logger.error(f"Error saving Zoho Inventory metrics to Postgres: {e}")
                db.rollback()
                return {"success": False, "error": "Zoho Inventory metrics sync failed"}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Zoho Inventory PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": "Zoho Inventory PostgreSQL cache sync failed"}

    async def full_sync(self, user_id: str, access_token: str, organization_id: str) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Zoho Inventory"""
        # Pipeline 1: Atom Memory
        # Triggered via zoho_inventory_memory_ingestion or similar
        
        # Pipeline 2: Postgres Cache
        cache_result = await self.sync_to_postgres_cache(user_id, access_token, organization_id)
        
        return {
            "success": True,
            "user_id": user_id,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }



def get_zoho_inventory_service(config: Dict[str, Any]) -> ZohoInventoryService:
    return ZohoInventoryService(tenant_id="default", config=config)

zoho_inventory_service = ZohoInventoryService(tenant_id="default", config={})
