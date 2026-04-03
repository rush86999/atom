"""
Freshdesk Service Integration
Complete Freshdesk API service for ATOM platform
Provides customer support, ticket management, and analytics capabilities
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
import httpx
from pydantic import BaseModel
from core.integration_service import IntegrationService

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class FreshdeskConfig:
    """Freshdesk configuration class"""
    api_key: str
    domain: str
    api_version: str = "v2"
    timeout: int = 30
    max_retries: int = 3


class FreshdeskService(IntegrationService):
    """Complete Freshdesk API service implementation"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(tenant_id, config)
        self.api_key = self.config.get("freshdesk_api_key") or os.getenv("FRESHDESK_API_KEY")
        self.domain = self.config.get("freshdesk_domain") or os.getenv("FRESHDESK_DOMAIN")
        self.api_version = self.config.get("freshdesk_api_version", "v2")
        self.timeout = self.config.get("freshdesk_timeout", 30)
        self.max_retries = self.config.get("freshdesk_max_retries", 3)
        
        self.base_url = f"https://{self.domain}.freshdesk.com/api/{self.api_version}" if self.domain else ""
        b64_creds = self._encode_credentials() if self.api_key else ""
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {b64_creds}" if b64_creds else ""
        }
        self.client = httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout
        )

    def get_capabilities(self) -> Dict[str, Any]:
        """
        Return Freshdesk service capabilities.

        Returns:
            Dict with operations, parameters, rate limits
        """
        return {
            "operations": [
                {
                    "id": "get_tickets",
                    "name": "Get Tickets",
                    "description": "Retrieve tickets with optional filtering",
                    "parameters": {
                        "page": {
                            "type": "integer",
                            "description": "Page number",
                            "required": False
                        },
                        "per_page": {
                            "type": "integer",
                            "description": "Tickets per page",
                            "required": False
                        },
                        "status": {
                            "type": "string",
                            "description": "Filter by status",
                            "required": False
                        },
                        "priority": {
                            "type": "string",
                            "description": "Filter by priority",
                            "required": False
                        }
                    },
                    "complexity": 1
                },
                {
                    "id": "create_ticket",
                    "name": "Create Ticket",
                    "description": "Create a new support ticket",
                    "parameters": {
                        "data": {
                            "type": "object",
                            "description": "Ticket data",
                            "required": True
                        }
                    },
                    "complexity": 3
                },
                {
                    "id": "search_tickets",
                    "name": "Search Tickets",
                    "description": "Search for tickets",
                    "parameters": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                            "required": False
                        }
                    },
                    "complexity": 1
                }
            ],
            "required_params": [],
            "optional_params": ["page", "per_page", "status", "priority", "query", "data"],
            "rate_limits": {
                "requests_per_minute": 100,
                "requests_per_hour": 5000
            },
            "supports_webhooks": True
        }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        try:
            if context and context.get("tenant_id") and context.get("tenant_id") != self.tenant_id:
                return {"success": False, "error": "Tenant mismatch", "details": {}}
                
            if operation == "get_tickets":
                res = await self.get_tickets(
                    page=parameters.get("page", 1),
                    per_page=parameters.get("per_page", 30)
                )
                return {"success": True, "result": res, "error": None, "details": {}}
            elif operation == "create_ticket":
                res = await self.create_ticket(parameters.get("data", parameters))
                return {"success": True, "result": res, "error": None, "details": {}}
            elif operation == "search_tickets":
                res = await self.search_tickets(parameters.get("query", ""))
                return {"success": True, "result": res, "error": None, "details": {}}
            else:
                raise NotImplementedError(f"Operation {operation} not supported for Freshdesk")
        except Exception as e:
            return {"success": False, "error": str(e), "details": {}}
            
    def _encode_credentials(self) -> str:
        """Encode API credentials for Basic Auth"""
        import base64
        credentials = f"{self.api_key}:X".encode('utf-8')
        return base64.b64encode(credentials).decode('utf-8')
    
    async def _handle_request(self, request_func, *args, **kwargs):
        """Handle HTTP requests with retry logic"""
        for attempt in range(self.max_retries):
            try:
                response = await request_func(*args, **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error on attempt {attempt + 1}: {e}")
                if attempt == self.max_retries - 1:
                    raise
                await httpx.AsyncClient().aclose()
            except httpx.RequestError as e:
                logger.error(f"Request error on attempt {attempt + 1}: {e}")
                if attempt == self.max_retries - 1:
                    raise
                await httpx.AsyncClient().aclose()
    
    # Ticket Management Methods
    
    async def create_ticket(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new support ticket"""
        try:
            url = f"{self.base_url}/tickets"
            response = await self._handle_request(
                self.client.post,
                url,
                json=ticket_data
            )
            logger.info(f"Created ticket: {response.get('id', 'unknown')}")
            return response
        except Exception as e:
            logger.error(f"Failed to create ticket: {e}")
            raise
    
    async def get_tickets(self, 
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
                        page: int = 1,
                        per_page: int = 30,
                        status: Optional[str] = None,
                        priority: Optional[str] = None,
                        created_since: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve tickets with optional filtering"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/tickets"
            params = {
                "page": page,
                "per_page": per_page
            }
            
            if status:
                params["status"] = status
            if priority:
                params["priority"] = priority
            if created_since:
                params["created_since"] = created_since
            
            response = await self._handle_request(
                self.client.get,
                url,
                params=params
            )
            logger.info(f"Retrieved {len(response)} tickets")
            return response
        except Exception as e:
            logger.error(f"Failed to get tickets: {e}")
            raise
    
    async def get_ticket(self, ticket_id: int) -> Dict[str, Any]:
        """Get specific ticket by ID"""
        try:
            url = f"{self.base_url}/tickets/{ticket_id}"
            response = await self._handle_request(self.client.get, url)
            logger.info(f"Retrieved ticket {ticket_id}")
            return response
        except Exception as e:
            logger.error(f"Failed to get ticket {ticket_id}: {e}")
            raise
    
    async def update_ticket(self, ticket_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing ticket"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/tickets/{ticket_id}"
            response = await self._handle_request(
                self.client.put,
                url,
                json=update_data
            )
            logger.info(f"Updated ticket {ticket_id}")
            return response
        except Exception as e:
            logger.error(f"Failed to update ticket {ticket_id}: {e}")
            raise
    
    async def delete_ticket(self, ticket_id: int) -> bool:
        """Delete a ticket"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/tickets/{ticket_id}"
            await self._handle_request(self.client.delete, url)
            logger.info(f"Deleted ticket {ticket_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete ticket {ticket_id}: {e}")
            raise
    
    async def add_ticket_note(self, ticket_id: int, note_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add note or comment to ticket"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/tickets/{ticket_id}/notes"
            response = await self._handle_request(
                self.client.post,
                url,
                json=note_data
            )
            logger.info(f"Added note to ticket {ticket_id}")
            return response
        except Exception as e:
            logger.error(f"Failed to add note to ticket {ticket_id}: {e}")
            raise
    
    async def get_ticket_conversations(self, ticket_id: int) -> List[Dict[str, Any]]:
        """Get all conversations for a ticket"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/tickets/{ticket_id}/conversations"
            response = await self._handle_request(self.client.get, url)
            logger.info(f"Retrieved {len(response)} conversations for ticket {ticket_id}")
            return response
        except Exception as e:
            logger.error(f"Failed to get conversations for ticket {ticket_id}: {e}")
            raise
    
    # Contact Management Methods
    
    async def create_contact(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new contact"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/contacts"
            response = await self._handle_request(
                self.client.post,
                url,
                json=contact_data
            )
            logger.info(f"Created contact: {response.get('id', 'unknown')}")
            return response
        except Exception as e:
            logger.error(f"Failed to create contact: {e}")
            raise
    
    async def get_contacts(self, page: int = 1, per_page: int = 30) -> Dict[str, Any]:
        """Retrieve contacts"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/contacts"
            params = {
                "page": page,
                "per_page": per_page
            }
            response = await self._handle_request(
                self.client.get,
                url,
                params=params
            )
            logger.info(f"Retrieved {len(response)} contacts")
            return response
        except Exception as e:
            logger.error(f"Failed to get contacts: {e}")
            raise
    
    async def get_contact(self, contact_id: int) -> Dict[str, Any]:
        """Get specific contact by ID"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/contacts/{contact_id}"
            response = await self._handle_request(self.client.get, url)
            logger.info(f"Retrieved contact {contact_id}")
            return response
        except Exception as e:
            logger.error(f"Failed to get contact {contact_id}: {e}")
            raise
    
    async def update_contact(self, contact_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing contact"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/contacts/{contact_id}"
            response = await self._handle_request(
                self.client.put,
                url,
                json=update_data
            )
            logger.info(f"Updated contact {contact_id}")
            return response
        except Exception as e:
            logger.error(f"Failed to update contact {contact_id}: {e}")
            raise
    
    # Company Management Methods
    
    async def create_company(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new company"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/companies"
            response = await self._handle_request(
                self.client.post,
                url,
                json=company_data
            )
            logger.info(f"Created company: {response.get('id', 'unknown')}")
            return response
        except Exception as e:
            logger.error(f"Failed to create company: {e}")
            raise
    
    async def get_companies(self, page: int = 1, per_page: int = 30) -> Dict[str, Any]:
        """Retrieve companies"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/companies"
            params = {
                "page": page,
                "per_page": per_page
            }
            response = await self._handle_request(
                self.client.get,
                url,
                params=params
            )
            logger.info(f"Retrieved {len(response)} companies")
            return response
        except Exception as e:
            logger.error(f"Failed to get companies: {e}")
            raise
    
    async def get_company(self, company_id: int) -> Dict[str, Any]:
        """Get specific company by ID"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/companies/{company_id}"
            response = await self._handle_request(self.client.get, url)
            logger.info(f"Retrieved company {company_id}")
            return response
        except Exception as e:
            logger.error(f"Failed to get company {company_id}: {e}")
            raise
    
    # Agent Management Methods
    
    async def get_agents(self) -> List[Dict[str, Any]]:
        """Retrieve all agents"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/agents"
            response = await self._handle_request(self.client.get, url)
            logger.info(f"Retrieved {len(response)} agents")
            return response
        except Exception as e:
            logger.error(f"Failed to get agents: {e}")
            raise
    
    async def get_agent(self, agent_id: int) -> Dict[str, Any]:
        """Get specific agent by ID"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/agents/{agent_id}"
            response = await self._handle_request(self.client.get, url)
            logger.info(f"Retrieved agent {agent_id}")
            return response
        except Exception as e:
            logger.error(f"Failed to get agent {agent_id}: {e}")
            raise
    
    # Group Management Methods
    
    async def get_groups(self) -> List[Dict[str, Any]]:
        """Retrieve all groups"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/groups"
            response = await self._handle_request(self.client.get, url)
            logger.info(f"Retrieved {len(response)} groups")
            return response
        except Exception as e:
            logger.error(f"Failed to get groups: {e}")
            raise
    
    async def get_group(self, group_id: int) -> Dict[str, Any]:
        """Get specific group by ID"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/groups/{group_id}"
            response = await self._handle_request(self.client.get, url)
            logger.info(f"Retrieved group {group_id}")
            return response
        except Exception as e:
            logger.error(f"Failed to get group {group_id}: {e}")
            raise
    
    # Analytics and Reporting Methods
    
    async def get_tickets_metrics(self, 
<<<<<<< HEAD

                             date_range: Optional[str] = None,
                             group_by: Optional[str] = None) -> Dict[str, Any]:
        """Get ticket metrics and analytics"""

=======
                             date_range: Optional[str] = None,
                             group_by: Optional[str] = None) -> Dict[str, Any]:
        """Get ticket metrics and analytics"""
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/reports/tickets"
            params = {}
            
            if date_range:
                params["date_range"] = date_range
            if group_by:
                params["group_by"] = group_by
            
            response = await self._handle_request(
                self.client.get,
                url,
                params=params
            )
            logger.info("Retrieved ticket metrics")
            return response
        except Exception as e:
            logger.error(f"Failed to get ticket metrics: {e}")
            raise
    
    async def get_satisfaction_ratings(self, 
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
                                   ticket_id: Optional[int] = None,
                                   date_range: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get customer satisfaction ratings"""
        try:
            url = f"{self.base_url}/surveys/satisfaction_ratings"
            params = {}
            
            if ticket_id:
                params["ticket_id"] = ticket_id
            if date_range:
                params["date_range"] = date_range
            
            response = await self._handle_request(
                self.client.get,
                url,
                params=params
            )
            logger.info(f"Retrieved {len(response)} satisfaction ratings")
            return response
        except Exception as e:
            logger.error(f"Failed to get satisfaction ratings: {e}")
            raise
    
    # Search Methods
    
    async def search_tickets(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search tickets with query and filters"""
        try:
            url = f"{self.base_url}/search/tickets"
            params = {"query": query}
            
            if filters:
                params.update(filters)
            
            response = await self._handle_request(
                self.client.get,
                url,
                params=params
            )
            logger.info(f"Found {len(response)} tickets for query: {query}")
            return response
        except Exception as e:
            logger.error(f"Failed to search tickets: {e}")
            raise
    
    async def search_contacts(self, query: str) -> List[Dict[str, Any]]:
        """Search contacts"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/search/contacts"
            params = {"query": query}
            
            response = await self._handle_request(
                self.client.get,
                url,
                params=params
            )
            logger.info(f"Found {len(response)} contacts for query: {query}")
            return response
        except Exception as e:
            logger.error(f"Failed to search contacts: {e}")
            raise
    
    # Health and Status Methods
    
<<<<<<< HEAD
    async def health_check(self) -> Dict[str, Any]:
        """Check Freshdesk API health status"""

=======
    def health_check(self) -> Dict[str, Any]:
        """Check Freshdesk API health status synchronously"""
        import requests
        if not self.api_key or not self.domain:
            return {
                "healthy": False,
                "message": "Missing credentials",
                "last_check": datetime.now(timezone.utc).isoformat()
            }
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/health"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            is_healthy = response.status_code < 500
            return {
                "healthy": is_healthy,
                "status": "healthy" if is_healthy else "unhealthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "last_check": datetime.now(timezone.utc).isoformat(),
                "message": "Connected" if is_healthy else f"Status code {response.status_code}",
                "api_response": response.text if response.status_code < 500 else None
            }
        except Exception as e:
            return {
                "healthy": False,
                "status": "unhealthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "last_check": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
                "message": str(e)
            }
    
    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/account"
            response = await self._handle_request(self.client.get, url)
            logger.info("Retrieved account information")
            return response
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            raise
    
    # Utility Methods
    
    async def upload_attachment(self, file_data: bytes, filename: str) -> Dict[str, Any]:
        """Upload file attachment"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/attachments"
            files = {"file": (filename, file_data)}
            
            # Create a new client for file upload
            upload_client = httpx.AsyncClient(
                headers=self.headers,
                timeout=self.timeout
            )
            
            response = await self._handle_request(
                upload_client.post,
                url,
                files=files
            )
            await upload_client.aclose()
            
            logger.info(f"Uploaded attachment: {filename}")
            return response
        except Exception as e:
            logger.error(f"Failed to upload attachment: {e}")
            raise
    
    def get_status_name(self, status_code: int) -> str:
        """Get human-readable status name"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        status_map = {
            2: "Open",
            3: "Pending", 
            4: "Resolved",
            5: "Closed"
        }
        return status_map.get(status_code, "Unknown")
    
    def get_priority_name(self, priority_code: int) -> str:
        """Get human-readable priority name"""
        priority_map = {
            1: "Low",
            2: "Medium",
            3: "High",
            4: "Urgent"
        }
        return priority_map.get(priority_code, "Unknown")
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
        logger.info("Freshdesk service client closed")

    async def sync_to_postgres_cache(self, workspace_id: str) -> Dict[str, Any]:
        """Sync Freshdesk analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric
            
            # Get tickets, contacts, and agents
            try:
                tickets = await self.get_tickets()
                ticket_count = len(tickets) if isinstance(tickets, list) else 0
            except Exception:
                ticket_count = 0
            
            try:
                contacts = await self.get_contacts()
                contact_count = len(contacts) if isinstance(contacts, list) else 0
            except Exception:
                contact_count = 0
            
            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("freshdesk_ticket_count", ticket_count, "count"),
                    ("freshdesk_contact_count", contact_count, "count"),
                ]
                
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        tenant_id=workspace_id,
                        integration_type="freshdesk",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            tenant_id=workspace_id,
                            integration_type="freshdesk",
                            metric_key=key,
                            value=float(value),
                            unit=unit
                        )
                        db.add(metric)
                    metrics_synced += 1
                
                db.commit()
                logger.info(f"Synced {metrics_synced} Freshdesk metrics to PostgreSQL cache for workspace {workspace_id}")
            except Exception as e:
                logger.error(f"Error saving Freshdesk metrics to Postgres: {e}")
                db.rollback()
                return {"success": False, "error": str(e)}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Freshdesk PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": str(e)}

    async def full_sync(self, workspace_id: str) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Freshdesk"""
        cache_result = await self.sync_to_postgres_cache(workspace_id)
        
        return {
            "success": True,
            "workspace_id": workspace_id,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Factory function for creating Freshdesk service
def create_freshdesk_service(api_key: str, domain: str, **kwargs) -> FreshdeskService:
    """Create Freshdesk service instance"""
<<<<<<< HEAD

    config = FreshdeskConfig(
        api_key=api_key,
        domain=domain,
=======
    config = {
        "freshdesk_api_key": api_key,
        "freshdesk_domain": domain,
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        **kwargs
    }
    return FreshdeskService(tenant_id="system", config=config)


# Utility functions for integration
async def test_freshdesk_connection(api_key: str, domain: str) -> bool:
    """Test Freshdesk API connection"""
    try:
        service = create_freshdesk_service(api_key, domain)
        result = service.health_check()
        await service.close()
        return result.get("healthy", False)
    except Exception as e:
        logger.error(f"Freshdesk connection test failed: {e}")
        return False


# Constants for Freshdesk
class FreshdeskConstants:
    """Freshdesk API constants"""
    
    # Ticket Status
    STATUS_OPEN = 2
    STATUS_PENDING = 3
    STATUS_RESOLVED = 4
    STATUS_CLOSED = 5
    
    # Ticket Priority
    PRIORITY_LOW = 1
    PRIORITY_MEDIUM = 2
    PRIORITY_HIGH = 3
    PRIORITY_URGENT = 4
    
    # Ticket Source
    SOURCE_EMAIL = 1
    SOURCE_PORTAL = 2
    SOURCE_PHONE = 3
    SOURCE_FORUM = 4
    SOURCE_TWITTER = 5
    SOURCE_FACEBOOK = 6
    SOURCE_CHAT = 7
    
    # Max Values
    MAX_ATTACHMENT_SIZE = 50 * 1024 * 1024  # 50MB
    MAX_TICKETS_PER_PAGE = 100
    MAX_RESULTS_PER_SEARCH = 1000


# Default configuration for development
DEFAULT_FRESHDESK_CONFIG = {
    "api_version": "v2",
    "timeout": 30,
    "max_retries": 3
}


# Export all components
__all__ = [
    "FreshdeskService",
    "FreshdeskConfig",
    "FreshdeskConstants",
    "create_freshdesk_service",
    "test_freshdesk_connection",
    "DEFAULT_FRESHDESK_CONFIG"
]


# Singleton instance removed - use IntegrationRegistry for per-tenant instances
