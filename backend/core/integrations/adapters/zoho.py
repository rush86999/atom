"""
Universal Zoho Integration Adapter

Provides OAuth-based integration with Zoho CRM, Books, Projects, and Inventory 
across multiple Data Centers (US, EU, IN, AU, CN) with intelligent Auto-DC discovery.
"""

import logging
import os
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
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
        token = self.db.query(IntegrationToken).filter(
            IntegrationToken.workspace_id == self.workspace_id,
            IntegrationToken.provider == "zoho"
        ).first()
        
        if token:
            self._access_token = token.access_token
            self._refresh_token = token.refresh_token
            self._token_expires_at = token.expires_at
            
            if token.instance_url:
                self.instance_url = token.instance_url

    async def refresh_token(self) -> bool:
        """Refresh Zoho access token using refresh token"""
        if not self._refresh_token:
            return False
            
        try:
            async with httpx.AsyncClient() as client:
                data = {
                    "refresh_token": self._refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token"
                }
                response = await client.post(self.DEFAULT_TOKEN_URL, data=data)
                response.raise_for_status()
                
                token_data = response.json()
                self._access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 3600)
                self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                
                # Update DB
                if self.db:
                    from core.models import IntegrationToken
                    token = self.db.query(IntegrationToken).filter(
                        IntegrationToken.workspace_id == self.workspace_id,
                        IntegrationToken.provider == "zoho"
                    ).first()
                    if token:
                        token.access_token = self._access_token
                        token.expires_at = self._token_expires_at
                        self.db.commit()
                
                return True
        except Exception as e:
            logger.error(f"Zoho token refresh failed: {e}")
            return False

    async def ensure_token(self):
        """Ensure we have a valid non-expired access token"""
        if not self._access_token:
            await self._load_token()
            
        if not self._access_token or (self._token_expires_at and self._token_expires_at < datetime.utcnow()):
            await self.refresh_token()

    async def get_oauth_url(self, scopes: Optional[List[str]] = None) -> str:
        """Generate Zoho OAuth authorization URL with expanded scopes"""
        if not scopes:
            scopes = [
                "ZohoCRM.modules.ALL",
                "ZohoCRM.users.READ",
                "ZohoBooks.fullaccess.all",
                "ZohoProjects.projects.ALL",
                "ZohoInventory.fullaccess.all"
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

    async def get_leads(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch leads from Zoho CRM"""
        try:
            base_url = self._get_base_url("crm")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/Leads",
                    headers={"Authorization": f"Zoho-oauthtoken {self._access_token}"},
                    params={"per_page": limit}
                )
                response.raise_for_status()
                data = response.json().get("data", [])
                return [self._map_lead(l) for l in data]
        except Exception as e:
            logger.error(f"Zoho CRM lead fetch failed: {e}")
            return []

    async def get_deals(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch deals from Zoho CRM"""
        try:
            base_url = self._get_base_url("crm")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/Deals",
                    headers={"Authorization": f"Zoho-oauthtoken {self._access_token}"},
                    params={"per_page": limit}
                )
                response.raise_for_status()
                data = response.json().get("data", [])
                return [self._map_deal(d) for d in data]
        except Exception as e:
            logger.error(f"Zoho CRM deal fetch failed: {e}")
            return []

    async def get_invoices(self, organization_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch invoices from Zoho Books"""
        try:
            base_url = self._get_base_url("books")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/invoices",
                    headers={"Authorization": f"Zoho-oauthtoken {self._access_token}"},
                    params={"organization_id": organization_id, "page_size": limit}
                )
                response.raise_for_status()
                data = response.json().get("invoices", [])
                return [self._map_invoice(i) for i in data]
        except Exception as e:
            logger.error(f"Zoho Books invoice fetch failed: {e}")
            return []

    async def get_portals(self) -> List[Dict[str, Any]]:
        """Fetch all portals from Zoho Projects"""
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
            logger.error(f"Zoho Projects portal fetch failed: {e}")
            return []

    async def get_projects(self, portal_id: str) -> List[Dict[str, Any]]:
        """Fetch all projects from a Zoho Projects portal"""
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
            logger.error(f"Zoho Projects project fetch failed: {e}")
            return []

    async def get_tasks(self, portal_id: str, project_id: str) -> List[Dict[str, Any]]:
        """Fetch tasks from Zoho Projects"""
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
            logger.error(f"Zoho Projects task fetch failed: {e}")
            return []

    async def get_items(self, organization_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch items from Zoho Inventory"""
        try:
            base_url = self._get_base_url("inventory")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/items",
                    headers={"Authorization": f"Zoho-oauthtoken {self._access_token}"},
                    params={"organization_id": organization_id, "page_size": limit}
                )
                response.raise_for_status()
                data = response.json().get("items", [])
                return [self._map_inventory_item(i) for i in data]
        except Exception as e:
            logger.error(f"Zoho Inventory item fetch failed: {e}")
            return []

    async def get_sales_orders(self, organization_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch sales orders from Zoho Inventory"""
        try:
            base_url = self._get_base_url("inventory")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/salesorders",
                    headers={"Authorization": f"Zoho-oauthtoken {self._access_token}"},
                    params={"organization_id": organization_id, "page_size": limit}
                )
                response.raise_for_status()
                data = response.json().get("salesorders", [])
                return [self._map_sales_order(s) for s in data]
        except Exception as e:
            logger.error(f"Zoho Inventory sales order fetch failed: {e}")
            return []

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
