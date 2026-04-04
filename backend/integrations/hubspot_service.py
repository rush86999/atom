"""
HubSpot Service for ATOM Platform
Provides comprehensive HubSpot integration functionality
"""

import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta
import httpx
from fastapi import HTTPException

from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)

class HubSpotService(IntegrationService):
    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        """
        Initialize HubSpot service for a specific tenant.

        Args:
            tenant_id: Tenant UUID for multi-tenancy
            config: Tenant-specific configuration with access_token, refresh_token, etc.
        """
        super().__init__(tenant_id=tenant_id, config=config)
        self.base_url = "https://api.hubapi.com"
        self.access_token = config.get("access_token")
        self.refresh_token = config.get("refresh_token")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    def get_capabilities(self) -> Dict[str, Any]:
        """Return HubSpot integration capabilities"""
        return {
            "operations": [
                {"id": "read", "description": "Read contacts, companies, deals"},
                {"id": "create", "description": "Create contacts, companies, deals"},
                {"id": "update", "description": "Update existing records"},
                {"id": "delete", "description": "Delete records"},
                {"id": "search", "description": "Search HubSpot content"},
            ],
            "required_params": ["access_token"],
            "optional_params": ["refresh_token"],
            "rate_limits": {"requests_per_second": 10},
            "supports_webhooks": True,
        }

    async def health_check(self) -> Dict[str, Any]:
        """Health check for HubSpot service"""
        try:
            # Basic health check - verify service can be initialized
            return {
                "healthy": True,
                "message": "HubSpot service is healthy",
                "service": "hubspot",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {
                "healthy": False,
                "message": str(e),
                "service": "hubspot",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a HubSpot operation with tenant context.
        Consolidated dispatcher supporting both generic and entity-specific calls.
        """
        # Validate tenant context
        if context and 'tenant_id' in context:
            tenant_id = context.get('tenant_id')
            if tenant_id != self.tenant_id:
                return {
                    "success": False,
                    "error": f"Tenant mismatch: expected {self.tenant_id}, got {tenant_id}",
                }

        try:
            # Check if this is an entity-bound operation masquerading as a generic one
            # (Pre-Phase 227 style tools)
            if operation == "create_contact":
                return await self.execute_entity_operation("create", "contact", parameters, context)
            elif operation == "get_contacts" or operation == "list_contacts":
                return await self.execute_entity_operation("list", "contact", parameters, context)
            elif operation == "get_companies":
                return await self.execute_entity_operation("list", "company", parameters, context)
            elif operation == "get_deals":
                return await self.execute_entity_operation("list", "deal", parameters, context)
            
            # Additional generic operations
            elif operation == "search_content":
                result = await self.search_content(**parameters)
                return {"success": True, "result": result}
            
            else:
                return {
                    "success": False,
                    "error": f"Unsupported operation: {operation}",
                }
        except Exception as e:
            logger.error(f"HubSpot operation {operation} failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "operation": operation,
            }

    async def execute_entity_operation(
        self,
        operation: str,
        entity_type: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Standardized Entity Action Dispatch for HubSpot CRM.
        Maps dynamic tools to CRM-specific objects (Contacts, Companies, Deals).
        """
        try:
            # 1. Normalize entity type
            entity = entity_type.lower().rstrip('s') # contact, company, deal
            
            # 2. Get active token
            token = context.get("token") if context else None
            active_token = token or self.access_token

            # 3. Route to mapping
            if entity == "contact":
                if operation == "create":
                    result = await self.create_contact(token=active_token, **parameters)
                elif operation == "get":
                    result = await self.get_contact(token=active_token, **parameters)
                elif operation == "list":
                    result = await self.get_contacts(token=active_token, **parameters)
                else:
                    raise NotImplementedError(f"Operation {operation} not implemented for {entity}")
            
            elif entity == "company":
                if operation == "create":
                    result = await self.create_company(token=active_token, **parameters)
                elif operation == "get":
                    result = await self.get_company(token=active_token, **parameters)
                elif operation == "list":
                    result = await self.get_companies(token=active_token, **parameters)
                else:
                    raise NotImplementedError(f"Operation {operation} not implemented for {entity}")
            
            elif entity == "deal":
                if operation == "create":
                    result = await self.create_deal(token=active_token, **parameters)
                elif operation == "get":
                    result = await self.get_deal(token=active_token, **parameters)
                elif operation == "list":
                    result = await self.get_deals(token=active_token, **parameters)
                else:
                    raise NotImplementedError(f"Operation {operation} not implemented for {entity}")
            
            else:
                return {
                    "success": False,
                    "error": f"HubSpot entity {entity_type} not supported in unified dispatch"
                }

            return {"success": True, "result": result}

        except Exception as e:
            logger.error(f"HubSpot entity operation {operation} for {entity_type} failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "operation": operation,
                "entity_type": entity_type
            }

    async def authenticate(self, client_id: str, client_secret: str, redirect_uri: str, code: str) -> dict:
        """Authenticate with HubSpot OAuth"""
        try:
            token_url = "https://api.hubapi.com/oauth/v1/token"
            data = {
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            }

            response = await self.client.post(token_url, data=data)
            response.raise_for_status()

            token_data = response.json()
            self.access_token = token_data.get("access_token")
            
            return token_data

        except httpx.HTTPError as e:
            logger.error(f"HubSpot authentication failed: {e}")
            raise HTTPException(
                status_code=400, detail=f"Authentication failed: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error during HubSpot authentication: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    async def get_contacts(self, limit: int = 100, offset: int = 0, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get HubSpot contacts"""
        try:
            # Use provided token or fall back to instance token or env
            active_token = token or self.access_token or os.getenv("HUBSPOT_ACCESS_TOKEN")
            
            if not active_token:
                 raise HTTPException(status_code=401, detail="Not authenticated")

            headers = {"Authorization": f"Bearer {active_token}"}
            params = {
                "limit": limit,
                "properties": "email,firstname,lastname,company,phone,createdate,lastmodifieddate,lifecyclestage,hs_lead_status",
            }

            if offset > 0:
                params["after"] = offset

            response = await self.client.get(
                f"{self.base_url}/crm/v3/objects/contacts",
                headers=headers,
                params=params,
            )
            response.raise_for_status()

            data = response.json()
            return data.get("results", [])

        except httpx.HTTPError as e:
            logger.error(f"Failed to get HubSpot contacts: {e}")
            raise HTTPException(
                status_code=400, detail=f"Failed to get contacts: {str(e)}"
            )

    async def get_companies(self, limit: int = 100, offset: int = 0, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get HubSpot companies"""
        try:
            active_token = token or self.access_token or os.getenv("HUBSPOT_ACCESS_TOKEN")
            if not active_token:
                raise HTTPException(status_code=401, detail="Not authenticated")

            headers = {"Authorization": f"Bearer {active_token}"}
            params = {
                "limit": limit,
                "properties": "name,domain,industry,city,state,country,createdate,lastmodifieddate",
            }

            if offset > 0:
                params["after"] = offset

            response = await self.client.get(
                f"{self.base_url}/crm/v3/objects/companies",
                headers=headers,
                params=params,
            )
            response.raise_for_status()

            data = response.json()
            return data.get("results", [])

        except httpx.HTTPError as e:
            logger.error(f"Failed to get HubSpot companies: {e}")
            raise HTTPException(
                status_code=400, detail=f"Failed to get companies: {str(e)}"
            )

    async def get_deals(self, limit: int = 100, offset: int = 0, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get HubSpot deals"""
        try:
            active_token = token or self.access_token or os.getenv("HUBSPOT_ACCESS_TOKEN")
            if not active_token:
                raise HTTPException(status_code=401, detail="Not authenticated")

            headers = {"Authorization": f"Bearer {active_token}"}
            params = {
                "limit": limit,
                "properties": "dealname,amount,dealstage,pipeline,closedate,createdate,lastmodifieddate,hubspot_owner_id",
            }

            if offset > 0:
                params["after"] = offset

            response = await self.client.get(
                f"{self.base_url}/crm/v3/objects/deals", headers=headers, params=params
            )
            response.raise_for_status()

            data = response.json()
            return data.get("results", [])

        except httpx.HTTPError as e:
            logger.error(f"Failed to get HubSpot deals: {e}")
            raise HTTPException(
                status_code=400, detail=f"Failed to get deals: {str(e)}"
            )

    async def get_campaigns(self, limit: int = 100, offset: int = 0, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get HubSpot campaigns"""
        try:
            active_token = token or self.access_token or os.getenv("HUBSPOT_ACCESS_TOKEN")
            if not active_token:
                raise HTTPException(status_code=401, detail="Not authenticated")

            headers = {"Authorization": f"Bearer {active_token}"}
            params = {"limit": limit}

            if offset > 0:
                params["offset"] = offset

            response = await self.client.get(
                f"{self.base_url}/marketing/v3/campaigns",
                headers=headers,
                params=params,
            )
            response.raise_for_status()

            data = response.json()
            return data.get("campaigns", [])

        except httpx.HTTPError as e:
            logger.error(f"Failed to get HubSpot campaigns: {e}")
            raise HTTPException(
                status_code=400, detail=f"Failed to get campaigns: {str(e)}"
            )

    async def search_content(self, query: str, object_type: str = "contact") -> Dict[str, Any]:
        """Search HubSpot content"""
        try:
            if not self.access_token:
                self.access_token = os.getenv("HUBSPOT_ACCESS_TOKEN")
                if not self.access_token:
                    raise HTTPException(status_code=401, detail="Not authenticated")

            headers = {"Authorization": f"Bearer {self.access_token}"}

            search_url = (
                f"{self.base_url}/crm/v3/objects/{object_type}/search"
            )
            payload = {
                "query": query,
                "limit": 50,
                "properties": ["email", "firstname", "lastname", "company", "phone"],
            }

            response = await self.client.post(search_url, headers=headers, json=payload)
            response.raise_for_status()

            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"HubSpot search failed: {e}")
            raise HTTPException(status_code=400, detail=f"Search failed: {str(e)}")

    async def create_contact(self, email: str, first_name: Optional[str] = None, last_name: Optional[str] = None, company: Optional[str] = None, phone: Optional[str] = None, token: Optional[str] = None) -> Dict[str, Any]:
        """Create a new HubSpot contact"""
        try:
            active_token = token or self.access_token or os.getenv("HUBSPOT_ACCESS_TOKEN")
            if not active_token:
                raise HTTPException(status_code=401, detail="Not authenticated")

            headers = {
                "Authorization": f"Bearer {active_token}",
                "Content-Type": "application/json",
            }

            properties = {
                "email": email,
                "firstname": first_name,
                "lastname": last_name,
                "company": company,
                "phone": phone,
            }

            payload = {
                "properties": {k: v for k, v in properties.items() if v is not None}
            }

            response = await self.client.post(
                f"{self.base_url}/crm/v3/objects/contacts",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Failed to create HubSpot contact: {e}")
            raise HTTPException(
                status_code=400, detail=f"Failed to create contact: {str(e)}"
            )

    async def create_company(self, name: str, domain: Optional[str] = None, token: Optional[str] = None) -> Dict[str, Any]:
        """Create a new HubSpot company"""
        try:
            active_token = token or self.access_token or os.getenv("HUBSPOT_ACCESS_TOKEN")
            if not active_token:
                raise HTTPException(status_code=401, detail="Not authenticated")

            headers = {
                "Authorization": f"Bearer {active_token}",
                "Content-Type": "application/json",
            }

            properties = {
                "name": name,
                "domain": domain,
            }

            payload = {
                "properties": {k: v for k, v in properties.items() if v is not None}
            }

            response = await self.client.post(
                f"{self.base_url}/crm/v3/objects/companies",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Failed to create HubSpot company: {e}")
            raise HTTPException(
                status_code=400, detail=f"Failed to create company: {str(e)}"
            )

    async def create_deal(self, name: str, amount: float, company_id: Optional[str] = None, token: Optional[str] = None) -> Dict[str, Any]:
        """Create a new HubSpot deal"""
        try:
            active_token = token or self.access_token or os.getenv("HUBSPOT_ACCESS_TOKEN")
            if not active_token:
                raise HTTPException(status_code=401, detail="Not authenticated")

            headers = {
                "Authorization": f"Bearer {active_token}",
                "Content-Type": "application/json",
            }

            properties = {
                "dealname": name,
                "amount": str(amount),
                "dealstage": "appointmentscheduled", # Default stage
                "pipeline": "default"
            }

            payload = {
                "properties": properties
            }

            if company_id:
                payload["associations"] = [
                    {
                        "to": {"id": company_id},
                        "types": [
                            {
                                "associationCategory": "HUBSPOT_DEFINED",
                                "associationTypeId": 5 # deal_to_company
                            }
                        ]
                    }
                ]

            response = await self.client.post(
                f"{self.base_url}/crm/v3/objects/deals",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Failed to create HubSpot deal: {e}")
            raise HTTPException(
                status_code=400, detail=f"Failed to create deal: {str(e)}"
            )

    async def get_contact(self, contact_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Get a single HubSpot contact by ID"""
        return await self.get_object("contacts", contact_id, token)

    async def get_company(self, company_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Get a single HubSpot company by ID"""
        return await self.get_object("companies", company_id, token)

    async def get_deal(self, deal_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Get a single HubSpot deal by ID"""
        return await self.get_object("deals", deal_id, token)

    async def get_object(self, object_type: str, object_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Generic helper to get a CRM object by ID"""
        try:
            active_token = token or self.access_token
            if not active_token:
                raise HTTPException(status_code=401, detail="Not authenticated")

            headers = {"Authorization": f"Bearer {active_token}"}
            response = await self.client.get(
                f"{self.base_url}/crm/v3/objects/{object_type}/{object_id}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get HubSpot {object_type} {object_id}: {e}")
            raise HTTPException(status_code=400, detail=f"Failed to get {object_type}: {str(e)}")
        """Update an existing HubSpot contact"""
        return await self.update_object("contacts", contact_id, properties, token)

    async def update_deal(self, deal_id: str, properties: Dict[str, Any], token: Optional[str] = None) -> Dict[str, Any]:
        """Update an existing HubSpot deal"""
        return await self.update_object("deals", deal_id, properties, token)

    async def update_object(self, object_type: str, object_id: str, properties: Dict[str, Any], token: Optional[str] = None) -> Dict[str, Any]:
        """Update an existing HubSpot object (contact, deal, company, etc.)"""
        try:
            active_token = token or self.access_token or os.getenv("HUBSPOT_ACCESS_TOKEN")
            if not active_token:
                raise HTTPException(status_code=401, detail="Not authenticated")

            headers = {
                "Authorization": f"Bearer {active_token}",
                "Content-Type": "application/json",
            }

            payload = {"properties": properties}

            response = await self.client.patch(
                f"{self.base_url}/crm/v3/objects/{object_type}/{object_id}",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Failed to update HubSpot {object_type}: {e}")
            raise HTTPException(
                status_code=400, detail=f"Failed to update {object_type}: {str(e)}"
            )

    async def get_analytics(self, token: Optional[str] = None) -> Dict[str, Any]:
        """Get aggregated HubSpot analytics for dashboard"""
        try:
            active_token = token or self.access_token or os.getenv("HUBSPOT_ACCESS_TOKEN")
            if not active_token:
                return {"error": "Not authenticated"}

            # Fetch deals to calculate revenue and counts
            deals = await self.get_deals(limit=100, token=active_token)
            
            total_revenue = sum(float(d.get("properties", {}).get("amount") or 0) for d in deals)
            deal_count = len(deals)
            
            # Fetch contacts count
            # HubSpot search API can give total count
            headers = {"Authorization": f"Bearer {active_token}"}
            contact_response = await self.client.post(
                f"{self.base_url}/crm/v3/objects/contacts/search",
                headers=headers,
                json={"limit": 1}
            )
            contact_count = contact_response.json().get("total", 0) if contact_response.status_code == 200 else 0

            return {
                "total_revenue": total_revenue,
                "deal_count": deal_count,
                "contact_count": contact_count,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get HubSpot analytics: {e}")
            return {"error": str(e)}

    async def get_properties(self, object_type: str, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get properties for a specific HubSpot object type (contacts, companies, deals)"""
        try:
            active_token = token or self.access_token or os.getenv("HUBSPOT_ACCESS_TOKEN")
            if not active_token:
                raise HTTPException(status_code=401, detail="Not authenticated")

            headers = {"Authorization": f"Bearer {active_token}"}
            response = await self.client.get(
                f"{self.base_url}/crm/v3/properties/{object_type}",
                headers=headers
            )
            response.raise_for_status()
            return response.json().get("results", [])
        except Exception as e:
            logger.error(f"Failed to get HubSpot properties for {object_type}: {e}")
            return []

    async def health_check(self) -> dict:
        """Health check for HubSpot service"""
        try:
            # Basic health check - verify service can be initialized
            return {
                "ok": True,
                "status": "healthy",
                "service": "hubspot",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "unhealthy",
                "service": "hubspot",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
    async def sync_to_postgres_cache(self, workspace_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Sync HubSpot analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric
            
            # Get analytics data
            analytics = await self.get_analytics(token)
            
            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("hubspot_contact_count", analytics.get("total_contacts", 0), "count"),
                    ("hubspot_company_count", analytics.get("total_companies", 0), "count"),
                    ("hubspot_deal_count", analytics.get("total_deals", 0), "count"),
                    ("hubspot_pipeline_value", analytics.get("total_deal_value", 0), "currency"),
                ]
                
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        tenant_id=workspace_id,
                        integration_type="hubspot",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            tenant_id=workspace_id,
                            integration_type="hubspot",
                            metric_key=key,
                            value=float(value),
                            unit=unit
                        )
                        db.add(metric)
                    metrics_synced += 1
                
                db.commit()
                logger.info(f"Synced {metrics_synced} HubSpot metrics to PostgreSQL cache for workspace {workspace_id}")
            except Exception as e:
                logger.error(f"Error saving HubSpot metrics to Postgres: {e}")
                db.rollback()
                return {"success": False, "error": str(e)}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"HubSpot PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": str(e)}

    async def full_sync(self, workspace_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for HubSpot"""
        # Pipeline 1: Atom Memory
        # Triggered via hubspot_memory_ingestion or similar

        # Pipeline 2: Postgres Cache
        cache_result = await self.sync_to_postgres_cache(workspace_id, token)

        return {
            "success": True,
            "workspace_id": workspace_id,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def get_operations(self) -> List[Dict[str, Any]]:
        """
        Return list of available HubSpot operations.
        (Updated for Phase 227 Knowledge Graph patterns)
        """
        return [
            {
                "name": "create_contact",
                "description": "Create a new contact in HubSpot",
                "parameters": {'email': {'type': 'string', 'required': True}, 'first_name': {'type': 'string', 'required': False}, 'last_name': {'type': 'string', 'required': False}},
                "complexity": 3
            },
            {
                "name": "list_contacts",
                "description": "List contacts from HubSpot",
                "parameters": {'limit': {'type': 'integer', 'required': False}},
                "complexity": 1
            },
            {
                "name": "get_contact",
                "description": "Get a contact from HubSpot by ID",
                "parameters": {'contact_id': {'type': 'string', 'required': True}},
                "complexity": 1
            }
        ]

# NOTE: Legacy singleton instance removed - use IntegrationRegistry instead
# from core.integration_registry import IntegrationRegistry
# registry = IntegrationRegistry(db)
# hubspot_service = await registry.get_service_instance("hubspot", tenant_id)
