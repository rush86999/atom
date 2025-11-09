#!/usr/bin/env python3
"""
Enhanced HubSpot Service
Provides improved HubSpot API integration with comprehensive error handling and monitoring
"""

import os
import json
import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from asyncpg import Pool

from enhanced_integration_service import EnhancedIntegrationService

logger = logging.getLogger(__name__)

class EnhancedHubSpotService(EnhancedIntegrationService):
    """Enhanced HubSpot API Service with comprehensive monitoring"""
    
    def __init__(self, user_id: str):
        super().__init__("HubSpot", user_id)
        self.api_base = "https://api.hubapi.com"
    
    def get_api_base_url(self) -> str:
        return self.api_base
    
    async def initialize(self, db_pool: Pool) -> bool:
        """Initialize HubSpot service with database pool"""
        try:
            from db_oauth_hubspot import get_user_hubspot_tokens
            
            self.db_pool = db_pool
            tokens = await get_user_hubspot_tokens(db_pool, self.user_id)
            
            if tokens and tokens.get("access_token"):
                self.access_token = tokens["access_token"]
                self.refresh_token = tokens.get("refresh_token")
                self._initialized = True
                self.status.status = "active"
                logger.info(f"HubSpot service initialized for user {self.user_id}")
                return True
            else:
                self.status.status = "inactive"
                self.status.error_message = "No HubSpot tokens found"
                logger.warning(f"No HubSpot tokens found for user {self.user_id}")
                return False
                
        except Exception as e:
            self.status.status = "error"
            self.status.error_message = str(e)
            logger.error(f"Failed to initialize HubSpot service: {e}")
            return False
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get HubSpot API headers with authentication"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    async def refresh_access_token(self) -> bool:
        """Refresh HubSpot access token"""
        try:
            refresh_url = "https://api.hubapi.com/oauth/v1/token"
            
            data = {
                "grant_type": "refresh_token",
                "client_id": os.getenv("HUBSPOT_CLIENT_ID"),
                "client_secret": os.getenv("HUBSPOT_CLIENT_SECRET"),
                "refresh_token": self.refresh_token
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(refresh_url, data=data)
                response.raise_for_status()
                
                token_data = response.json()
                
                # Update tokens
                self.access_token = token_data["access_token"]
                if "refresh_token" in token_data:
                    self.refresh_token = token_data["refresh_token"]
                
                # Update in database
                from db_oauth_hubspot import refresh_hubspot_tokens
                await refresh_hubspot_tokens(self.db_pool, self.user_id, token_data)
                
                logger.info("HubSpot token refreshed successfully")
                return True
                
        except Exception as e:
            logger.error(f"Failed to refresh HubSpot token: {e}")
            self.status.error_message = f"Token refresh failed: {e}"
            return False
    
    def _get_health_check_endpoint(self) -> Optional[str]:
        return "/crm/v3/objects/contacts?limit=1"
    
    # Enhanced Contact Management
    async def get_contacts(self, limit: int = 100, after: str = None, 
                          properties: List[str] = None,
                          archived: bool = False) -> Dict[str, Any]:
        """Get HubSpot contacts with enhanced parameters"""
        try:
            await self._ensure_initialized()
            
            params = {"limit": min(limit, 100), "archived": str(archived).lower()}
            if after:
                params["after"] = after
            if properties:
                params["properties"] = ",".join(properties)
            
            return await self._make_request("GET", "/crm/v3/objects/contacts", params=params)
            
        except Exception as e:
            logger.error(f"Failed to get HubSpot contacts: {e}")
            return {"success": False, "error": str(e)}
    
    async def create_contact(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new HubSpot contact"""
        try:
            await self._ensure_initialized()
            
            return await self._make_request("POST", "/crm/v3/objects/contacts", data=contact_data)
            
        except Exception as e:
            logger.error(f"Failed to create HubSpot contact: {e}")
            return {"success": False, "error": str(e)}
    
    async def update_contact(self, contact_id: str, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing HubSpot contact"""
        try:
            await self._ensure_initialized()
            
            return await self._make_request("PATCH", f"/crm/v3/objects/contacts/{contact_id}", data=contact_data)
            
        except Exception as e:
            logger.error(f"Failed to update HubSpot contact {contact_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def delete_contact(self, contact_id: str) -> Dict[str, Any]:
        """Delete a HubSpot contact"""
        try:
            await self._ensure_initialized()
            
            return await self._make_request("DELETE", f"/crm/v3/objects/contacts/{contact_id}")
            
        except Exception as e:
            logger.error(f"Failed to delete HubSpot contact {contact_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def search_contacts(self, search_query: str, limit: int = 10) -> Dict[str, Any]:
        """Search HubSpot contacts"""
        try:
            await self._ensure_initialized()
            
            search_data = {
                "query": search_query,
                "limit": limit,
                "filterGroups": [
                    {
                        "filters": [
                            {
                                "propertyName": "firstname",
                                "operator": "CONTAINS_TOKEN",
                                "value": search_query
                            },
                            {
                                "propertyName": "lastname",
                                "operator": "CONTAINS_TOKEN",
                                "value": search_query
                            },
                            {
                                "propertyName": "email",
                                "operator": "CONTAINS_TOKEN",
                                "value": search_query
                            }
                        ]
                    }
                ]
            }
            
            return await self._make_request("POST", "/crm/v3/objects/contacts/search", data=search_data)
            
        except Exception as e:
            logger.error(f"Failed to search HubSpot contacts: {e}")
            return {"success": False, "error": str(e)}
    
    # Enhanced Company Management
    async def get_companies(self, limit: int = 100, after: str = None,
                           properties: List[str] = None,
                           archived: bool = False) -> Dict[str, Any]:
        """Get HubSpot companies"""
        try:
            await self._ensure_initialized()
            
            params = {"limit": min(limit, 100), "archived": str(archived).lower()}
            if after:
                params["after"] = after
            if properties:
                params["properties"] = ",".join(properties)
            
            return await self._make_request("GET", "/crm/v3/objects/companies", params=params)
            
        except Exception as e:
            logger.error(f"Failed to get HubSpot companies: {e}")
            return {"success": False, "error": str(e)}
    
    async def create_company(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new HubSpot company"""
        try:
            await self._ensure_initialized()
            
            return await self._make_request("POST", "/crm/v3/objects/companies", data=company_data)
            
        except Exception as e:
            logger.error(f"Failed to create HubSpot company: {e}")
            return {"success": False, "error": str(e)}
    
    # Enhanced Deal Management
    async def get_deals(self, limit: int = 100, after: str = None,
                       properties: List[str] = None,
                       archived: bool = False) -> Dict[str, Any]:
        """Get HubSpot deals"""
        try:
            await self._ensure_initialized()
            
            params = {"limit": min(limit, 100), "archived": str(archived).lower()}
            if after:
                params["after"] = after
            if properties:
                params["properties"] = ",".join(properties)
            
            return await self._make_request("GET", "/crm/v3/objects/deals", params=params)
            
        except Exception as e:
            logger.error(f"Failed to get HubSpot deals: {e}")
            return {"success": False, "error": str(e)}
    
    async def create_deal(self, deal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new HubSpot deal"""
        try:
            await self._ensure_initialized()
            
            return await self._make_request("POST", "/crm/v3/objects/deals", data=deal_data)
            
        except Exception as e:
            logger.error(f"Failed to create HubSpot deal: {e}")
            return {"success": False, "error": str(e)}
    
    # Enhanced Engagements Management
    async def get_engagements(self, limit: int = 100, after: str = None) -> Dict[str, Any]:
        """Get HubSpot engagements"""
        try:
            await self._ensure_initialized()
            
            params = {"limit": min(limit, 100)}
            if after:
                params["after"] = after
            
            return await self._make_request("GET", "/engagements/v1/engagements/paged", params=params)
            
        except Exception as e:
            logger.error(f"Failed to get HubSpot engagements: {e}")
            return {"success": False, "error": str(e)}
    
    async def create_note(self, note_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a HubSpot note engagement"""
        try:
            await self._ensure_initialized()
            
            return await self._make_request("POST", "/engagements/v1/engagements", data=note_data)
            
        except Exception as e:
            logger.error(f"Failed to create HubSpot note: {e}")
            return {"success": False, "error": str(e)}
    
    async def create_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a HubSpot task engagement"""
        try:
            await self._ensure_initialized()
            
            return await self._make_request("POST", "/engagements/v1/engagements", data=task_data)
            
        except Exception as e:
            logger.error(f"Failed to create HubSpot task: {e}")
            return {"success": False, "error": str(e)}
    
    # Enhanced Lists Management
    async def get_contact_lists(self, limit: int = 100) -> Dict[str, Any]:
        """Get HubSpot contact lists"""
        try:
            await self._ensure_initialized()
            
            params = {"limit": min(limit, 250)}
            return await self._make_request("GET", "/marketing/v3/lists/", params=params)
            
        except Exception as e:
            logger.error(f"Failed to get HubSpot contact lists: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_list_memberships(self, list_id: str, limit: int = 100) -> Dict[str, Any]:
        """Get memberships for a specific contact list"""
        try:
            await self._ensure_initialized()
            
            params = {"limit": min(limit, 100)}
            return await self._make_request("GET", f"/marketing/v3/lists/{list_id}/memberships", params=params)
            
        except Exception as e:
            logger.error(f"Failed to get HubSpot list memberships: {e}")
            return {"success": False, "error": str(e)}
    
    # Enhanced Analytics and Reporting
    async def get_contact_analytics(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Get contact analytics for a date range"""
        try:
            await self._ensure_initialized()
            
            params = {
                "start": start_date,
                "end": end_date
            }
            
            return await self._make_request("GET", "/analytics/v2/views/contact?includeAll=true", params=params)
            
        except Exception as e:
            logger.error(f"Failed to get HubSpot contact analytics: {e}")
            return {"success": False, "error": str(e)}
    
    # Enhanced Webhook Management
    async def get_webhooks(self) -> Dict[str, Any]:
        """Get all HubSpot webhooks"""
        try:
            await self._ensure_initialized()
            
            return await self._make_request("GET", "/automation/v3/webhooks")
            
        except Exception as e:
            logger.error(f"Failed to get HubSpot webhooks: {e}")
            return {"success": False, "error": str(e)}
    
    async def create_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new HubSpot webhook"""
        try:
            await self._ensure_initialized()
            
            return await self._make_request("POST", "/automation/v3/webhooks", data=webhook_data)
            
        except Exception as e:
            logger.error(f"Failed to create HubSpot webhook: {e}")
            return {"success": False, "error": str(e)}
    
    async def update_webhook(self, webhook_id: int, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing HubSpot webhook"""
        try:
            await self._ensure_initialized()
            
            return await self._make_request("PATCH", f"/automation/v3/webhooks/{webhook_id}", data=webhook_data)
            
        except Exception as e:
            logger.error(f"Failed to update HubSpot webhook {webhook_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def delete_webhook(self, webhook_id: int) -> Dict[str, Any]:
        """Delete a HubSpot webhook"""
        try:
            await self._ensure_initialized()
            
            return await self._make_request("DELETE", f"/automation/v3/webhooks/{webhook_id}")
            
        except Exception as e:
            logger.error(f"Failed to delete HubSpot webhook {webhook_id}: {e}")
            return {"success": False, "error": str(e)}
    
    # Enhanced Pipeline Management
    async def get_pipelines(self, object_type: str = "deals") -> Dict[str, Any]:
        """Get HubSpot pipelines for a specific object type"""
        try:
            await self._ensure_initialized()
            
            return await self._make_request("GET", f"/crm/v3/pipelines/{object_type}")
            
        except Exception as e:
            logger.error(f"Failed to get HubSpot pipelines: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_pipeline_stages(self, pipeline_id: str, object_type: str = "deals") -> Dict[str, Any]:
        """Get stages for a specific pipeline"""
        try:
            await self._ensure_initialized()
            
            return await self._make_request("GET", f"/crm/v3/pipelines/{object_type}/{pipeline_id}/stages")
            
        except Exception as e:
            logger.error(f"Failed to get HubSpot pipeline stages: {e}")
            return {"success": False, "error": str(e)}
    
    # Enhanced Properties Management
    async def get_contact_properties(self) -> Dict[str, Any]:
        """Get all contact properties"""
        try:
            await self._ensure_initialized()
            
            params = {"archived": "false"}
            return await self._make_request("GET", "/crm/v3/properties/contacts", params=params)
            
        except Exception as e:
            logger.error(f"Failed to get HubSpot contact properties: {e}")
            return {"success": False, "error": str(e)}
    
    async def create_property(self, object_type: str, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new property for an object type"""
        try:
            await self._ensure_initialized()
            
            return await self._make_request("POST", f"/crm/v3/properties/{object_type}", data=property_data)
            
        except Exception as e:
            logger.error(f"Failed to create HubSpot property: {e}")
            return {"success": False, "error": str(e)}
    
    # Batch Operations
    async def create_contacts_batch(self, contacts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create multiple contacts in a batch"""
        try:
            await self._ensure_initialized()
            
            batch_data = {
                "inputs": contacts
            }
            
            return await self._make_request("POST", "/crm/v3/objects/contacts/batch/create", data=batch_data)
            
        except Exception as e:
            logger.error(f"Failed to create HubSpot contacts batch: {e}")
            return {"success": False, "error": str(e)}
    
    async def update_contacts_batch(self, contacts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Update multiple contacts in a batch"""
        try:
            await self._ensure_initialized()
            
            batch_data = {
                "inputs": contacts
            }
            
            return await self._make_request("POST", "/crm/v3/objects/contacts/batch/update", data=batch_data)
            
        except Exception as e:
            logger.error(f"Failed to update HubSpot contacts batch: {e}")
            return {"success": False, "error": str(e)}